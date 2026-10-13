import io
import re
from datetime import datetime
from typing import Dict, Any, Tuple, List
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from pdf2image import convert_from_bytes
import numpy as np
import cv2


class OCREngineService:
    @staticmethod
    def preprocess_image(image: Image.Image) -> Image.Image:
        """
        Enhances document image quality for higher OCR accuracy:
        Grayscale -> Binarization/Thresholding -> Denoising -> Contrast Enhancement
        """
        # Convert PIL image to OpenCV format (numpy array)
        open_cv_image = np.array(image.convert("RGB"))
        open_cv_image = open_cv_image[:, :, ::-1].copy()

        # 1. Grayscale
        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)

        # 2. Denoise
        denoised = cv2.fastNlMeansDenoising(gray, h=10)

        # 3. Adaptive Thresholding (Binarization)
        thresh = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        # Convert back to PIL Image
        processed_pil = Image.fromarray(thresh)
        return processed_pil

    @classmethod
    def load_document_pages(cls, file_bytes: bytes, filename: str) -> List[Image.Image]:
        """Handles PDF, PNG, JPG, JPEG formats and extracts PIL images."""
        extension = filename.lower().split(".")[-1]

        if extension == "pdf":
            # Convert PDF bytes into a list of PIL Images
            return convert_from_bytes(file_bytes)
        elif extension in ["png", "jpg", "jpeg", "webp", "tiff"]:
            return [Image.open(io.BytesIO(file_bytes))]
        else:
            raise ValueError(f"Unsupported file format: {extension}")

    @classmethod
    def extract_raw_text(cls, pages: List[Image.Image]) -> Tuple[str, float]:
        """
        Runs Tesseract OCR across all pages, extracting raw text
        and calculating average character confidence.
        """
        full_text = ""
        total_confidence = 0.0
        word_count = 0

        for page in pages:
            processed_page = cls.preprocess_image(page)
            
            # Extract detailed OCR data (word bounds, confidence)
            ocr_data = pytesseract.image_to_data(
                processed_page, output_type=pytesseract.Output.DICT
            )

            full_text += pytesseract.image_to_string(processed_page) + "\n"

            # Compute average confidence across detected words
            confidences = [
                int(c) for c in ocr_data["conf"] if int(c) > 0
            ]
            if confidences:
                total_confidence += sum(confidences)
                word_count += len(confidences)

        avg_confidence = (total_confidence / word_count / 100.0) if word_count > 0 else 0.5
        return full_text, avg_confidence

    @classmethod
    def classify_document(cls, text: str) -> Tuple[str, float]:
        """Classifies document type based on key domain terms."""
        text_lower = text.lower()

        keywords = {
            "DEATH_CERTIFICATE": ["death certificate", "cause of death", "deceased", "register of deaths", "certify that the deceased"],
            "MEDICAL_RECORD": ["medical record", "hospital", "physician", "patient", "diagnosis", "clinical summary"],
            "LEGAL_DOCUMENT": ["power of attorney", "last will", "testament", "notary public", "affidavit", "court order"]
        }

        scores = {}
        for doc_type, terms in keywords.items():
            matches = sum(1 for term in terms if term in text_lower)
            scores[doc_type] = matches / len(terms)

        best_match = max(scores, key=scores.get)
        confidence = scores[best_match]

        if confidence == 0:
            return "UNKNOWN", 0.3

        return best_match, round(min(0.99, 0.6 + (confidence * 0.4)), 2)

    @classmethod
    def extract_fields(cls, text: str) -> Dict[str, Any]:
        """Extracts key entities (Deceased Name, Event Date, Registration Number)."""
        extracted = {
            "extracted_name": None,
            "event_date": None,
            "certificate_number": None,
            "has_official_seal": False
        }

        # 1. Name Detection Heuristics
        name_patterns = [
            r"(?:name of deceased|deceased name|name):\s*([A-Za-z\s]{3,30})",
            r"(?:certify that|late)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["extracted_name"] = match.group(1).strip()
                break

        # 2. Date Detection (e.g., YYYY-MM-DD, DD/MM/YYYY, Month DD YYYY)
        date_patterns = [
            r"\b(\d{4}-\d{2}-\d{2})\b",
            r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
            r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b"
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["event_date"] = match.group(1).strip()
                break

        # 3. Certificate / Reg Number Detection
        cert_match = re.search(r"(?:cert|reg|no|number)[:\s]*([A-Z0-9\-]{5,15})", text, re.IGNORECASE)
        if cert_match:
            extracted["certificate_number"] = cert_match.group(1).strip()

        # 4. Stamp / Seal Keyword Heuristic
        seal_keywords = ["official seal", "registrar", "republic", "notary", "stamped", "signed"]
        extracted["has_official_seal"] = any(kw in text.lower() for kw in seal_keywords)

        return extracted

    @classmethod
    def process_document(cls, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Master execution pipeline converting raw bytes into structured data & confidence scores."""
        pages = cls.load_document_pages(file_bytes, filename)
        raw_text, ocr_confidence = cls.extract_raw_text(pages)
        doc_type, classification_confidence = cls.classify_document(raw_text)
        fields = cls.extract_fields(raw_text)

        # Composite confidence score calculation
        overall_confidence = round((ocr_confidence * 0.5) + (classification_confidence * 0.5), 2)

        return {
            "document_type": doc_type,
            "confidence_score": overall_confidence,
            "ocr_quality": round(ocr_confidence, 2),
            "extracted_fields": fields,
            "raw_text_snippet": raw_text[:200].replace("\n", " "),
            "pages_processed": len(pages)
        }
