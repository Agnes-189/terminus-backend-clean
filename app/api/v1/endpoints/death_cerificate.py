import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.death_certificate import DeathCertificateRecord, VitalRegistryCheckLog, JurisdictionType
from app.services.seal_detector import SealDetectionService
from app.services.vital_registry import VitalRegistryService
from app.services.death_authenticity_engine import AuthenticityScoringEngine

router = APIRouter(prefix="/death-certificate", tags=["Death Certificate Attestation"])


@router.post("/verify", status_code=status.HTTP_201_CREATED)
async def verify_death_certificate(
    claim_id: str = Form(...),
    vault_owner: str = Form(...),
    certificate_number: str = Form(...),          # Entry/Serial number on certificate
    decedent_full_name: str = Form(...),
    decedent_national_id: str = Form(None),        # Kenya National ID / Passport / SSN
    date_of_death: str = Form(...),                 # YYYY-MM-DD
    country_code: str = Form("KE"),                 # ISO 3166-1 alpha-2 code (Default: KE)
    subdivision_code: str = Form(None),             # ISO 3166-2 County/State code (e.g., KE-30)
    issuing_authority: str = Form(...),             # e.g. "Civil Registration Services"
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Verifies death certificate authenticity against global and national registry gateways."""
    file_bytes = await file.read()
    doc_hash = hashlib.sha256(file_bytes).hexdigest()
    id_hash = hashlib.sha256(decedent_national_id.encode()).hexdigest() if decedent_national_id else None

    # 1. Anti-Fraud & Duplicate Check
    is_duplicate, fraud_reason = AuthenticityScoringEngine.check_for_fraud_and_duplicates(
        db, doc_hash, certificate_number, id_hash
    )
    if is_duplicate:
        raise HTTPException(status_code=400, detail=f"Verification failed: {fraud_reason}")

    # 2. Image Processing (Seal/Notary/QR code detection)
    artifacts = SealDetectionService.analyze_document_artifacts(file_bytes)

    # 3. Dynamic Gateway Route by Country Code
    registry_res = await VitalRegistryService.verify_record(
        country_code=country_code,
        certificate_number=certificate_number,
        date_of_death_str=date_of_death,
        national_id_hash=id_hash
    )

    # 4. Authenticity Scoring (0.0 to 100.0)
    score, status_result = AuthenticityScoringEngine.calculate_score(
        seal_detected=artifacts["seal_detected"],
        notary_stamp_detected=artifacts["notary_stamp_detected"],
        qr_signature_valid=artifacts["qr_signature_valid"],
        vital_registry_matched=registry_res["matched"],
        is_duplicate=is_duplicate
    )

    # 5. Save Record
    dod_dt = datetime.strptime(date_of_death, "%Y-%m-%d")
    masked_name = f"{decedent_full_name[0]}. ***{decedent_full_name.split()[-1]}"

    cert_record = DeathCertificateRecord(
        claim_id=claim_id,
        vault_owner=vault_owner,
        document_hash=doc_hash,
        certificate_number=certificate_number,
        decedent_national_id_hash=id_hash,
        decedent_full_name_masked=masked_name,
        date_of_death=dod_dt,
        country_code=country_code.upper(),
        subdivision_code=subdivision_code.upper() if subdivision_code else None,
        issuing_authority=issuing_authority,
        seal_detected=artifacts["seal_detected"],
        notary_stamp_detected=artifacts["notary_stamp_detected"],
        qr_signature_valid=artifacts["qr_signature_valid"],
        vital_registry_matched=registry_res["matched"],
        vital_registry_ref=registry_res.get("vital_registry_ref"),
        authenticity_score=score,
        is_duplicate_record=is_duplicate,
        verification_status=status_result,
        rejection_reason=fraud_reason if is_duplicate else None
    )
    db.add(cert_record)
    db.flush()

    # Log Registry Activity
    check_log = VitalRegistryCheckLog(
        certificate_record_id=cert_record.id,
        registry_name=registry_res["registry_name"],
        country_code=country_code.upper(),
        query_payload_masked={"cert_num": certificate_number, "country": country_code},
        response_code=registry_res["response_code"],
        matched=registry_res["matched"],
        raw_response_digest=registry_res["digest"]
    )
    db.add(check_log)
    db.commit()

    return {
        "record_id": cert_record.id,
        "country": cert_record.country_code,
        "verification_status": cert_record.verification_status,
        "authenticity_score": cert_record.authenticity_score,
        "registry_reference": cert_record.vital_registry_ref
    }