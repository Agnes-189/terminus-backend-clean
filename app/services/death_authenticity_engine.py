from sqlalchemy.orm import Session
from app.models.death_certificate import DeathCertificateRecord, CertificateVerificationStatus

class AuthenticityScoringEngine:

    @staticmethod
    def check_for_fraud_and_duplicates(
        db: Session,
        document_hash: str,
        certificate_number: str,
        ssn_hash: str
    ) -> tuple[bool, str]:
        """Detects duplicate death certificate submissions across vaults."""
        
        # Check identical document upload
        if db.query(DeathCertificateRecord).filter(DeathCertificateRecord.document_hash == document_hash).first():
            return True, "Duplicate document payload detected"

        # Check identical State File Number / Certificate Number
        if db.query(DeathCertificateRecord).filter(DeathCertificateRecord.certificate_number == certificate_number).first():
            return True, "Death certificate number already registered in another claim"

        # Check identical SSN hash
        if ssn_hash and db.query(DeathCertificateRecord).filter(DeathCertificateRecord.decedent_ssn_hash == ssn_hash).first():
            return True, "Death record for this SSN has already been processed"

        return False, ""

    @staticmethod
    def calculate_score(
        seal_detected: bool,
        notary_stamp_detected: bool,
        qr_signature_valid: bool,
        vital_registry_matched: bool,
        is_duplicate: bool
    ) -> tuple[float, CertificateVerificationStatus]:
        """Calculates weighted authenticity score (0-100) and decides pass/fail status."""
        
        if is_duplicate:
            return 0.0, CertificateVerificationStatus.REJECTED

        score = 0.0

        # Weights
        # 1. Vital Registry match (50 Points)
        if vital_registry_matched:
            score += 50.0
        
        # 2. Official Seal (20 Points)
        if seal_detected:
            score += 20.0

        # 3. Valid Digital QR Signature (20 Points)
        if qr_signature_valid:
            score += 20.0

        # 4. Notary Stamp (10 Points)
        if notary_stamp_detected:
            score += 10.0

        # Threshold evaluation
        if score >= 70.0:
            status = CertificateVerificationStatus.VERIFIED
        elif score >= 40.0:
            status = CertificateVerificationStatus.SUSPICIOUS
        else:
            status = CertificateVerificationStatus.REJECTED

        return score, status