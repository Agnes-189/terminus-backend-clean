from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.medical import MedicalProofRecord, DoctorAttestation
from app.services.medical_parser import MedicalParserService
from app.services.npi_verifier import NPIVerificationService
from app.services.fhir_service import FHIRIntegrationService

router = APIRouter(prefix="/medical", tags=["Medical Proof Validation"])


@router.post("/upload-proof", status_code=status.HTTP_201_CREATED)
async def upload_medical_proof(
    claim_id: str = Form(...),
    vault_owner: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Uploads medical text record, scrubs PHI, extracts ICD-10 codes, and evaluates legal threshold."""
    contents = await file.read()
    raw_text = contents.decode("utf-8", errors="ignore")

    doc_hash = MedicalParserService.calculate_document_hash(contents)
    
    # Check duplicate
    existing = db.query(MedicalProofRecord).filter(MedicalProofRecord.document_hash == doc_hash).first()
    if existing:
        raise HTTPException(status_code=400, detail="This medical document has already been submitted.")

    parsed_data = MedicalParserService.parse_text(raw_text)

    proof_record = MedicalProofRecord(
        claim_id=claim_id,
        vault_owner=vault_owner,
        document_hash=doc_hash,
        icd10_codes=parsed_data["icd10_codes"],
        cpt_codes=parsed_data["cpt_codes"],
        incapacitation_severity=parsed_data["incapacitation_severity"],
        meets_legal_threshold=parsed_data["meets_legal_threshold"],
        parsed_summary_redacted=parsed_data["redacted_summary"]
    )
    db.add(proof_record)
    db.commit()
    db.refresh(proof_record)

    return {
        "message": "Medical record processed successfully (PHI masked)",
        "proof_record_id": proof_record.id,
        "document_hash": proof_record.document_hash,
        "meets_legal_threshold": proof_record.meets_legal_threshold,
        "severity": proof_record.incapacitation_severity,
        "extracted_icd10": proof_record.icd10_codes
    }


@router.post("/parse-fhir", status_code=status.HTTP_201_CREATED)
async def parse_fhir_payload(
    claim_id: str,
    vault_owner: str,
    fhir_bundle: dict,
    db: Session = Depends(get_db)
):
    """Integrates directly with Healthcare Systems via FHIR R4 JSON Payload."""
    fhir_data = FHIRIntegrationService.parse_fhir_condition(fhir_bundle)
    
    import json
    doc_hash = MedicalParserService.calculate_document_hash(json.dumps(fhir_bundle).encode())

    proof_record = MedicalProofRecord(
        claim_id=claim_id,
        vault_owner=vault_owner,
        document_hash=doc_hash,
        icd10_codes=fhir_data["icd10_codes"],
        incapacitation_severity=fhir_data["incapacitation_severity"],
        meets_legal_threshold=fhir_data["meets_legal_threshold"],
        parsed_summary_redacted="[FHIR R4 Ingestion - Protected Health Data Cleaned]"
    )
    db.add(proof_record)
    db.commit()
    db.refresh(proof_record)

    return {
        "message": "FHIR bundle processed successfully",
        "proof_record_id": proof_record.id,
        "meets_legal_threshold": proof_record.meets_legal_threshold
    }


@router.post("/attest", status_code=status.HTTP_201_CREATED)
async def submit_doctor_attestation(
    proof_record_id: str,
    doctor_npi: str,
    license_state: str,
    license_number: str,
    signature: str,
    db: Session = Depends(get_db)
):
    """Submits doctor attestation and validates NPI status with CMS NPI Registry."""
    proof = db.query(MedicalProofRecord).filter(MedicalProofRecord.id == proof_record_id).first()
    if not proof:
        raise HTTPException(status_code=404, detail="Medical proof record not found.")

    # Verify NPI
    npi_result = await NPIVerificationService.verify_doctor_npi(doctor_npi, license_state)

    attestation = DoctorAttestation(
        proof_record_id=proof_record_id,
        doctor_npi=doctor_npi,
        doctor_name_redacted=npi_result.get("doctor_name", "Dr. [REDACTED]"),
        medical_license_state=license_state,
        medical_license_number=license_number,
        verification_status=npi_result["status"],
        signature=signature
    )
    db.add(attestation)
    db.commit()
    db.refresh(attestation)

    return {
        "attestation_id": attestation.id,
        "npi_verification_status": attestation.verification_status,
        "details": npi_result.get("reason")
    }