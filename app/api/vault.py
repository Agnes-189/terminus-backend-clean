from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.vault import Vault, ClaimType
from app.services.vault_state_machine import VaultStateMachineService

router = APIRouter()


@router.get("/state/{vault_owner}")
async def get_vault_state(vault_owner: str, db: Session = Depends(get_db)):
    """Fetches real-time state, challenge windows, and rules for a given vault."""
    vault = db.query(Vault).filter(Vault.owner_pubkey == vault_owner).first()
    if not vault:
        return {"vault_owner": vault_owner, "state": "ACTIVE", "active_challenge": None}

    return {
        "vault_owner": vault.owner_pubkey,
        "state": vault.state.value,
        "challenge_period_days": vault.challenge_period_days,
        "required_stake_lamports": vault.required_stake_lamports,
        "active_challenge_id": vault.active_challenge_id,
        "challenge_start_time": vault.challenge_start_time,
        "challenge_end_time": vault.challenge_end_time,
    }


@router.post("/initiate-challenge")
async def initiate_challenge(
    vault_owner: str = Form(...),
    claimant_pubkey: str = Form(...),
    claim_type: ClaimType = Form(...),
    oracle_job_id: str = Form(...),
    staked_lamports: float = Form(1_000_000_000.0),
    db: Session = Depends(get_db)
):
    """Initiates a timed challenge window with proof and stake validation."""
    try:
        challenge = VaultStateMachineService.initiate_challenge(
            db=db,
            vault_owner=vault_owner,
            claimant_pubkey=claimant_pubkey,
            claim_type=claim_type,
            oracle_job_id=oracle_job_id,
            staked_lamports=staked_lamports
        )
        return {"status": "SUCCESS", "challenge_id": challenge.id, "state": "IN_CHALLENGE"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/defend")
async def defend_challenge(
    vault_owner: str = Form(...),
    proof_of_life_sig: str = Form(...),
    db: Session = Depends(get_db)
):
    """Vault owner submits proof of life to cancel challenge and slash claimant stake."""
    try:
        result = VaultStateMachineService.defend_challenge(
            db=db,
            vault_owner=vault_owner,
            proof_of_life_sig=proof_of_life_sig
        )
        return {"status": "SUCCESS", "data": result}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/resolve-settlement")
async def resolve_settlement(
    vault_owner: str = Form(...),
    payout_address: str = Form(...),
    db: Session = Depends(get_db)
):
    """Executes final payout settlement once challenge expires or is validated."""
    try:
        result = VaultStateMachineService.resolve_settlement(
            db=db,
            vault_owner=vault_owner,
            payout_address=payout_address
        )
        return {"status": "SUCCESS", "data": result}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))