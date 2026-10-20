import re
import logging
from typing import Dict, Any

logger = logging.getLogger("PrivacyEngine")


class PrivacyEngine:
    """
    Automated PII scrubbing utility to sanitize sensitive medical details 
    and personal identifiers before database persistence or telemetry logging.
    """

    @staticmethod
    def redact_pii(text: str) -> str:
        """Scubs common PII patterns from raw string data."""
        if not text or not isinstance(text, str):
            return text

        # 1. Redact Social Security Numbers (SSN) / Tax IDs
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED_SSN]', text)

        # 2. Redact Email Addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', '[REDACTED_EMAIL]', text)

        # 3. Redact Phone Numbers
        text = re.sub(r'\b\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b', '[REDACTED_PHONE]', text)

        # 4. Redact Standard National IDs / Passports (8-10 alphanumeric standalone strings)
        text = re.sub(r'\b[A-Z0-9]{8,10}\b', '[REDACTED_ID]', text)

        return text

    @classmethod
    def sanitize_ocr_payload(cls, ocr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitizes raw OCR dict structures before DB storage or task queue dispatch."""
        if not isinstance(ocr_data, dict):
            return ocr_data

        sanitized = ocr_data.copy()

        # Scrub raw extracted text fields
        for field in ["raw_text", "extracted_text", "notes", "full_text"]:
            if field in sanitized and isinstance(sanitized[field], str):
                sanitized[field] = cls.redact_pii(sanitized[field])

        # Scrub nested document metadata if present
        if "metadata" in sanitized and isinstance(sanitized["metadata"], dict):
            sanitized["metadata"] = cls.sanitize_ocr_payload(sanitized["metadata"])

        return sanitized
