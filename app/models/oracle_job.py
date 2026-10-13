import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Enum, Text, Float, JSON
from app.core.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    OCR_PROCESSING = "OCR_PROCESSING"
    ZK_PROOF_GENERATING = "ZK_PROOF_GENERATING"
    SOLANA_STAGING = "SOLANA_STAGING"
    SOLANA_BROADCASTING = "SOLANA_BROADCASTING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class OracleJob(Base):
    __tablename__ = "oracle_jobs"

    id = Column(String, primary_key=True, index=True)  # UUID
    username = Column(String, nullable=False)
    vault_owner = Column(String, nullable=False)
    claimant_pubkey = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Staged Pipeline Outputs
    ocr_data = Column(JSON, nullable=True)
    zk_proof_payload = Column(JSON, nullable=True)
    oracle_signature = Column(String, nullable=True)
    solana_tx_signature = Column(String, nullable=True)
    
    # Audit & Error Tracking
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


class OracleAuditLog(Base):
    __tablename__ = "oracle_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, nullable=False, index=True)
    from_status = Column(String, nullable=False)
    to_status = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))