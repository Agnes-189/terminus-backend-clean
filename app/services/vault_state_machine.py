import uuid
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.vault import Vault, VaultState, VaultChallenge, ClaimType, ChallengeStatus
from app.models.oracle_job import OracleJob, JobStatus

logger = logging.getLogger("VaultStateMachine")

# Legal State Transition Matrix
ALLOWED_TRANSITIONS = {
    VaultState.ACTIVE: [VaultState.IN_CHALLENGE],
    VaultState.IN_CHALLENGE: [VaultState.ACTIVE, VaultState.DECEASED, VaultState.INCAPACITATED, VaultState.DISPUTED],
    VaultState.INCAPACITATED: [VaultState.SETTLED, VaultState.DISPUTED],
    VaultState.DECEASED: [VaultState.SETTLED, VaultState.DISPUTED],
    VaultState.DISPUTED: [VaultState.ACTIVE, VaultState.DECEASED, VaultState.INCAPACITATED, VaultState.SETTLED],
    VaultState.SETTLED: []  # Terminal state
}


class VaultStateMachineService:
    @staticmethod
    def validate_transition(current_state: VaultState, target_state: VaultState):
        """Ensures state transitions strictly follow legal lifecycle rules."""
        allowed = ALLOWED_TRANSITIONS.get(current_state, [])
        if target_state not in allowed:
            raise ValueError(
                f"Invalid state transition: Cannot move from {current_state.value} to {target_state.value}."
            )

    @classmethod
    def initiate_challenge(
        cls,
        db: Session,
        vault_owner: str,
        claimant_pubkey: str,
        claim_type: ClaimType,
        oracle_job_id: str,
        staked_lamports: int  # Fixed: replaced undefined Float with built-in int
    ) -> VaultChallenge:
        """
        Transitions Vault from ACTIVE to IN_CHALLENGE after validating ZK/OCR proofs and stake.
        """
        vault = db.query(Vault).filter(Vault.owner_pubkey == vault_owner).first()
        if not vault:
            # Auto-register vault if not existing
            vault = Vault(owner_pubkey=vault_owner, state=VaultState.ACTIVE)
            db.add(vault)
            db.commit()

        cls.validate_transition(vault.state, VaultState.IN_CHALLENGE)

        # 1. Enforce Stake Validation
        if staked_lamports < vault.required_stake_lamports:
            raise ValueError(
                f"Insufficient stake: Provided {staked_lamports} lamports, required {vault.required_stake_lamports}."
            )

        # 2. Validate Evidence Workflow
        oracle_job = db.query(OracleJob).filter(OracleJob.id == oracle_job_id).first()
        if not oracle_job or oracle_job.status != JobStatus.CONFIRMED:
            raise ValueError("Valid verified Oracle job proof is required to initiate challenge.")

        ocr_data = oracle_job.ocr_data or {}
        confidence = ocr_data.get("confidence_score", 0.0)
        doc_type = ocr_data.get("document_type")

        # Specific Claim Validation Workflows
        if claim_type == ClaimType.DEATH and doc_type != "DEATH_CERTIFICATE":
            raise ValueError("Death claims require a verified Death Certificate.")
        elif claim_type == ClaimType.INCAPACITATION and doc_type not in ["MEDICAL_RECORD", "LEGAL_DOCUMENT"]:
            raise ValueError("Incapacitation claims require verified Medical or Legal Records.")

        # 3. Create Challenge Entry & Start Timer (30 days default)
        now = datetime.now(timezone.utc)
        challenge_id = f"chal_{uuid.uuid4().hex[:12]}"
        
        challenge = VaultChallenge(
            id=challenge_id,
            vault_owner=vault_owner,
            claimant_pubkey=claimant_pubkey,
            claim_type=claim_type,
            proof_job_id=oracle_job_id,
            ocr_confidence=confidence,
            zk_proof_hash=str(oracle_job.zk_proof_payload),
            staked_amount_lamports=staked_lamports,
            status=ChallengeStatus.PENDING
        )

        vault.state = VaultState.IN_CHALLENGE
        vault.active_challenge_id = challenge_id
        vault.challenge_start_time = now
        vault.challenge_end_time = now + timedelta(days=vault.challenge_period_days)

        db.add(challenge)
        db.commit()
        
        logger.info(f"⚔️️ [CHALLENGE STARTED] Vault {vault_owner} in challenge until {vault.challenge_end_time}")
        return challenge

    @classmethod
    def defend_challenge(cls, db: Session, vault_owner: str, proof_of_life_sig: str) -> dict:
        """
        Vault Owner responds (Proof of Life).
        Transitions state back to ACTIVE and slashes claimant stake.
        """
        vault = db.query(Vault).filter(Vault.owner_pubkey == vault_owner).first()
        if not vault or vault.state != VaultState.IN_CHALLENGE:
            raise ValueError("Vault is not currently in challenge state.")

        cls.validate_transition(vault.state, VaultState.ACTIVE)

        challenge = db.query(VaultChallenge).filter(VaultChallenge.id == vault.active_challenge_id).first()
        if challenge:
            # Execute Stake Slashing Logic
            challenge.slashed = True
            challenge.slashed_recipient = vault_owner  # Slashed stake awarded to vault owner
            challenge.status = ChallengeStatus.DEFENDED_SLASHED
            challenge.resolved_at = datetime.now(timezone.utc)

        # Revert Vault back to ACTIVE state
        vault.state = VaultState.ACTIVE
        vault.active_challenge_id = None
        vault.challenge_start_time = None
        vault.challenge_end_time = None

        db.commit()
        logger.info(f"🛡️ [CHALLENGE DEFENDED] Vault {vault_owner} restored to ACTIVE. Claimant stake slashed.")
        
        return {
            "status": "ACTIVE",
            "message": "Proof of life accepted. Vault state restored to ACTIVE.",
            "slashed_amount_lamports": challenge.staked_amount_lamports if challenge else 0
        }

    @classmethod
    def process_expired_challenge(cls, db: Session, vault_owner: str) -> dict:
        """
        Enforces Challenge Period Timeout.
        If timeout expired without owner response, state transitions to DECEASED/INCAPACITATED.
        """
        vault = db.query(Vault).filter(Vault.owner_pubkey == vault_owner).first()
        if not vault or vault.state != VaultState.IN_CHALLENGE:
            return {"status": "NO_OP", "reason": "Vault not in challenge."}

        now = datetime.now(timezone.utc)
        # Ensure timeout enforcement
        end_time = vault.challenge_end_time
        if end_time and end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        if end_time and now < end_time:
            time_left = end_time - now
            raise ValueError(f"Challenge window has not expired yet. Remaining: {time_left}")

        challenge = db.query(VaultChallenge).filter(VaultChallenge.id == vault.active_challenge_id).first()
        target_state = VaultState.DECEASED if challenge and challenge.claim_type == ClaimType.DEATH else VaultState.INCAPACITATED

        cls.validate_transition(vault.state, target_state)

        vault.state = target_state
        if challenge:
            challenge.status = ChallengeStatus.EXPIRED_VALIDATED
            challenge.resolved_at = now

        db.commit()
        logger.info(f"⌛ [CHALLENGE EXPIRED] Vault {vault_owner} state transitioned to {target_state.value}.")

        return {
            "vault_owner": vault_owner,
            "new_state": target_state.value,
            "message": f"Challenge window expired without dispute. Vault marked as {target_state.value}."
        }

    @classmethod
    def resolve_settlement(cls, db: Session, vault_owner: str, payout_address: str) -> dict:
        """Executes full or partial claim payout settlement."""
        vault = db.query(Vault).filter(Vault.owner_pubkey == vault_owner).first()
        if not vault or vault.state not in [VaultState.DECEASED, VaultState.INCAPACITATED]:
            raise ValueError("Vault must be in DECEASED or INCAPACITATED state to execute settlement.")

        cls.validate_transition(vault.state, VaultState.SETTLED)
        
        vault.state = VaultState.SETTLED
        db.commit()
        
        logger.info(f"💸 [VAULT SETTLED] Vault {vault_owner} funds released to {payout_address}")
        return {
            "status": "SETTLED",
            "payout_address": payout_address,
            "vault_owner": vault_owner
        }