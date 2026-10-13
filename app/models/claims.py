import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Enum, Text, ForeignKey
from app.core.database import Base


class ClaimStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    VERIFYING = "VERIFYING"
    CHALLENGE_ACTIVE = "CHALLENGE_ACTIVE"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SETTLED = "SETTLED"


class ClaimRequest(Base):
    __tablename__ = "claim_requests"

    id = Column(String, primary_key=True, index=True)  # UUID
    vault_owner = Column(String, nullable=False, index=True)
    claimant_pubkey = Column(String, nullable=False, index=True)
    claim_type = Column(String, nullable=False)  # DEATH / INCAPACITATION
    
    document_id = Column(String, ForeignKey("document_store.id", ondelete="SET NULL"), nullable=True)
    oracle_job_id = Column(String, nullable=True)
    
    status = Column(Enum(ClaimStatus), default=ClaimStatus.SUBMITTED, nullable=False)
    rejection_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)
