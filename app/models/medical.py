import uuid
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Float, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.core.database import Base


class MedicalVerificationStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    SUSPICIOUS = "SUSPICIOUS"
    REJECTED = "REJECTED"


class MedicalProofRecord(Base):
    __tablename__ = "medical_proof_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id = Column(String(36), ForeignKey("claim_requests.id"), nullable=False, index=True)
    vault_owner = Column(String(64), nullable=False, index=True)
    
    # Medical Artifact Details
    document_hash = Column(String(64), nullable=False, unique=True)
    record_type = Column(String(64), nullable=False)  # FHIR_R4, EMR_EXTRACT, DIAGNOSIS_REPORT
    icd_codes = Column(JSON, nullable=True)           # e.g., ["R99", "I46.9"]
    cpt_codes = Column(JSON, nullable=True)
    
    # PHI Scrubbing & FHIR Metadata
    phi_scrubbed = Column(Boolean, default=True)
    fhir_resource_id = Column(String(128), nullable=True)
    
    # Global Jurisdiction (ISO 3166-1) & Status
    country_code = Column(String(2), nullable=False, default="KE", index=True)
    verification_status = Column(SQLEnum(MedicalVerificationStatus), default=MedicalVerificationStatus.PENDING)
    rejection_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    doctor_attestations = relationship("DoctorAttestation", back_populates="medical_record", cascade="all, delete-orphan")


class DoctorAttestation(Base):
    __tablename__ = "doctor_attestations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    medical_record_id = Column(String(36), ForeignKey("medical_proof_records.id"), nullable=True, index=True)
    claim_id = Column(String(36), ForeignKey("claim_requests.id"), nullable=False, index=True)
    
    # Global Practitioner Identifiers
    doctor_full_name = Column(String(255), nullable=False)
    licensing_number = Column(String(128), nullable=False, index=True)  # KMPDC Reg No. (KE) / NPI (US) / GMC (UK)
    licensing_body = Column(String(255), nullable=False)                # e.g., "KMPDC", "CMS", "GMC"
    country_code = Column(String(2), nullable=False, index=True)       # ISO 3166-1 alpha-2 (e.g., "KE")
    subdivision_code = Column(String(10), nullable=True)               # ISO 3166-2 (e.g., "KE-30")
    
    # Licensing Verification Outcome
    license_active = Column(Boolean, default=False)
    registry_verified = Column(Boolean, default=False)
    registry_reference = Column(String(128), nullable=True)
    
    # Attestation Details
    facility_name = Column(String(255), nullable=False)
    attestation_digest = Column(String(64), nullable=False)
    verification_status = Column(SQLEnum(MedicalVerificationStatus), default=MedicalVerificationStatus.PENDING)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    medical_record = relationship("MedicalProofRecord", back_populates="doctor_attestations")
