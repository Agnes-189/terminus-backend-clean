import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Enum, Text
from app.core.database import Base


class TransactionType(str, enum.Enum):
    VAULT_INIT = "VAULT_INIT"
    CHALLENGE_TRIGGER = "CHALLENGE_TRIGGER"
    PROOF_OF_LIFE = "PROOF_OF_LIFE"
    CLAIM_SETTLEMENT = "CLAIM_SETTLEMENT"


class TransactionRecord(Base):
    __tablename__ = "transaction_records"

    id = Column(String, primary_key=True, index=True)  # Local UUID
    solana_signature = Column(String, unique=True, index=True, nullable=True)
    tx_type = Column(Enum(TransactionType), nullable=False)
    
    vault_owner = Column(String, nullable=False, index=True)
    payer_pubkey = Column(String, nullable=False)
    
    status = Column(String, default="PENDING", nullable=False)  # PENDING, CONFIRMED, FINALIZED, FAILED
    block_slot = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))