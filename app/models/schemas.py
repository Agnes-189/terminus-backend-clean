from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from app.models.user import UserRole
from app.models.vault import VaultState, ClaimType, ChallengeStatus
from app.models.document import DocumentType
from app.models.claims import ClaimStatus
from app.models.transaction import TransactionType


# --- AUTH SCHEMAS ---
class UserRegisterRequest(BaseModel):
    pubkey: str = Field(..., example="4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU")
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.OWNER


class UserLoginRequest(BaseModel):
    email_or_pubkey: str
    password: str


class MFAVerifyRequest(BaseModel):
    user_pubkey: str
    totp_code: str = Field(..., min_length=6, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class UserProfileResponse(BaseModel):
    pubkey: str
    email: str
    role: UserRole
    mfa_enabled: bool
    created_at: datetime


# --- VAULT & CHALLENGE SCHEMAS ---
class VaultStateResponse(BaseModel):
    vault_owner: str
    state: VaultState
    challenge_period_days: int
    required_stake_lamports: float
    active_challenge_id: Optional[str] = None
    challenge_start_time: Optional[datetime] = None
    challenge_end_time: Optional[datetime] = None


class ChallengeInitiateRequest(BaseModel):
    vault_owner: str
    claimant_pubkey: str
    claim_type: ClaimType
    oracle_job_id: str
    staked_lamports: float = 1_000_000_000.0


class DefendChallengeRequest(BaseModel):
    vault_owner: str
    proof_of_life_sig: str


# --- DOCUMENT & CLAIM SCHEMAS ---
class OCRAnalysisResponse(BaseModel):
    document_type: DocumentType
    confidence_score: float
    extracted_entities: Dict[str, Any]


class ClaimCreateRequest(BaseModel):
    vault_owner: str
    claimant_pubkey: str
    claim_type: ClaimType


class ClaimResponse(BaseModel):
    id: str
    vault_owner: str
    claimant_pubkey: str
    claim_type: str
    status: ClaimStatus
    created_at: datetime


# --- REGISTRY SCHEMAS ---
class BeneficiaryCreateRequest(BaseModel):
    vault_owner: str
    beneficiary_pubkey: str
    allocation_percentage: float = Field(..., gt=0, le=100)
    legal_document_hash: Optional[str] = None


class BeneficiaryResponse(BaseModel):
    id: str
    vault_owner: str
    beneficiary_pubkey: str
    allocation_percentage: float
    is_verified: bool


class FiduciaryCreateRequest(BaseModel):
    vault_owner: str
    fiduciary_pubkey: str
    powers_granted: str
    attestation_hash: str


class FiduciaryResponse(BaseModel):
    id: str
    vault_owner: str
    fiduciary_pubkey: str
    powers_granted: str
    is_active: bool


# --- TRANSACTION & AUDIT SCHEMAS ---
class TransactionResponse(BaseModel):
    id: str
    solana_signature: Optional[str]
    tx_type: TransactionType
    vault_owner: str
    status: str
    timestamp: datetime


class SystemAuditLogResponse(BaseModel):
    id: int
    actor_pubkey: str
    action: str
    entity_type: str
    entity_id: str
    timestamp: datetime