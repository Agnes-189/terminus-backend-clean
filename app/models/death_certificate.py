import uuid
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Float, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.core.database import Base


class CertificateVerificationStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    SUSPICIOUS = "SUSPICIOUS"
    REJECTED = "REJECTED"


class DeathCertificateRecord(Base):
    __tablename__ = "death_certificate_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id = Column(String(36), ForeignKey("claim_requests.id"), nullable=False, index=True)
    vault_owner = Column(String(64), nullable=False, index=True)
    
    # Hashes & Identifiers
    document_hash = Column(String(64), nullable=False, unique=True)
    certificate_number = Column(String(128), nullable=False, index=True)  # Entry/Serial No.
    
    # Decedent Data (Privacy Masked)
    decedent_national_id_hash = Column(String(64), nullable=True, index=True)
    decedent_full_name_masked = Column(String(255), nullable=False)
    date_of_death = Column(DateTime, nullable=False)
    
    # ISO 3166 Global Jurisdiction
    country_code = Column(String(2), nullable=False, index=True)  # e.g., "KE", "US", "NG"
    subdivision_code = Column(String(10), nullable=True)         # e.g., "KE-30"
    issuing_authority = Column(String(255), nullable=False)
    
    # Visual & Digital Verification Artifacts
    seal_detected = Column(Boolean, default=False)
    notary_stamp_detected = Column(Boolean, default=False)
    qr_signature_valid = Column(Boolean, default=False)
    
    # Vital Registry Integration
    vital_registry_matched = Column(Boolean, default=False)
    vital_registry_ref = Column(String(128), nullable=True)
    
    # Scoring & Verification Outcome
    authenticity_score = Column(Float, default=0.0)
    is_duplicate_record = Column(Boolean, default=False)
    verification_status = Column(SQLEnum(CertificateVerificationStatus), default=CertificateVerificationStatus.PENDING)
    rejection_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    registry_checks = relationship("VitalRegistryCheckLog", back_populates="certificate_record", cascade="all, delete-orphan")


class VitalRegistryCheckLog(Base):
    __tablename__ = "vital_registry_check_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    certificate_record_id = Column(String(36), ForeignKey("death_certificate_records.id"), nullable=False, index=True)
    
    registry_name = Column(String(255), nullable=False)
    country_code = Column(String(2), nullable=False)
    query_payload_masked = Column(JSON, nullable=False)
    response_code = Column(String(32), nullable=False)
    matched = Column(Boolean, default=False)
    raw_response_digest = Column(String(64), nullable=False)
    
    checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    certificate_record = relationship("DeathCertificateRecord", back_populates="registry_checks")
