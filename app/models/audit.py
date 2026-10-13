from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from app.core.database import Base


class SystemAuditLog(Base):
    __tablename__ = "system_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_pubkey = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)  # e.g. "VAULT_UPDATE", "BENEFICIARY_ADDED"
    entity_type = Column(String, nullable=False)  # e.g. "VAULT", "CLAIM", "USER"
    entity_id = Column(String, nullable=False)
    
    payload_changes = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))