import re
import hashlib

# Standard Incapacitation / Severe Impairment ICD-10 Codes
INCAPACITATION_ICD10_MAP = {
    "R40.20": ("Unspecified coma", IncapacitationSeverity.TOTAL_PERMANENT),
    "R40.1": ("Somnolence / Stupor", IncapacitationSeverity.TOTAL_TEMPORARY),
    "G30.9": ("Alzheimers disease, unspecified", IncapacitationSeverity.TOTAL_PERMANENT),
    "F03.90": ("Unspecified dementia, without behavioral disturbance", IncapacitationSeverity.TOTAL_PERMANENT),
    "G93.1": ("Anoxic brain damage", IncapacitationSeverity.TOTAL_PERMANENT),
    "S06.9X0A": ("Unspecified intracranial injury", IncapacitationSeverity.TOTAL_TEMPORARY),
}

class MedicalParserService:

    @staticmethod
    def calculate_document_hash(file_bytes: bytes) -> str:
        return hashlib.sha256(file_bytes).hexdigest()

    @staticmethod
    def redact_phi(text: str) -> str:
        """Masks SSNs, Phone Numbers, Emails, and Dates from medical text."""
        # Redact SSNs
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED SSN]', text)
        # Redact Emails
        text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[REDACTED EMAIL]', text)
        # Redact Phone Numbers
        text = re.sub(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '[REDACTED PHONE]', text)
        # Redact Dates (MM/DD/YYYY or YYYY-MM-DD)
        text = re.sub(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b', '[REDACTED DATE]', text)
        return text

    @classmethod
    def parse_text(cls, raw_text: str):
        redacted_summary = cls.redact_phi(raw_text)
        
        # Regex search for ICD-10 codes (e.g., G30.9, R40.20)
        icd10_matches = re.findall(r'\b[A-TV-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?\b', raw_text.upper())
        found_icd10 = list(set(icd10_matches))

        # Regex search for CPT codes (5-digit medical procedural codes)
        cpt_matches = re.findall(r'\b\d{5}\b', raw_text)
        found_cpt = list(set(cpt_matches))

        # Determine incapacitation threshold
        highest_severity = IncapacitationSeverity.NONE
        meets_threshold = False

        for code in found_icd10:
            if code in INCAPACITATION_ICD10_MAP:
                _, severity = INCAPACITATION_ICD10_MAP[code]
                meets_threshold = True
                if severity == IncapacitationSeverity.TOTAL_PERMANENT:
                    highest_severity = IncapacitationSeverity.TOTAL_PERMANENT
                elif severity == IncapacitationSeverity.TOTAL_TEMPORARY and highest_severity != IncapacitationSeverity.TOTAL_PERMANENT:
                    highest_severity = IncapacitationSeverity.TOTAL_TEMPORARY

        return {
            "redacted_summary": redacted_summary,
            "icd10_codes": found_icd10,
            "cpt_codes": found_cpt,
            "incapacitation_severity": highest_severity,
            "meets_legal_threshold": meets_threshold,
        }