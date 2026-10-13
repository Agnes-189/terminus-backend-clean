from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, Boolean, Text
from app.core.database import Base


class BeneficiaryRegistry(Base):
    __tablename__ = "beneficiary_registry"

    id = Column(String, primary_key=True, index=True)  # UUID
    vault_owner = Column(String, nullable=False, index=True)
    beneficiary_pubkey = Column(String, nullable=False, index=True)
    
    allocation_percentage = Column(Float, nullable=False, default=100.0)
    legal_document_hash = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class FiduciaryRegistry(Base):
    __tablename__ = "fiduciary_registry"

    id = Column(String, primary_key=True, index=True)  # UUID
    vault_owner = Column(String, nullable=False, index=True)
    fiduciary_pubkey = Column(String, nullable=False, index=True)
    
    powers_granted = Column(Text, nullable=False)  # JSON or CSV list of power scope
    attestation_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))