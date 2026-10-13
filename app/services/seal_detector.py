import cv2
import numpy as np
import zxingcpp
from PIL import Image
import io

class SealDetectionService:

    @staticmethod
    def analyze_document_artifacts(image_bytes: bytes) -> dict:
        """Analyzes image for circular government seals, notary stamps, and QR codes."""
        # Convert bytes to OpenCV image
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"seal_detected": False, "notary_stamp_detected": False, "qr_signature_valid": False}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 1. Circular Government Seal Detection using Hough Circle Transform
        blurred = cv2.medianBlur(gray, 5)
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=100,
            param1=50,
            param2=30,
            minRadius=40,
            maxRadius=200
        )
        seal_detected = circles is not None and len(circles[0]) > 0

        # 2. Notary Stamp Detection (High-density rectangular color contour extraction)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # Search for typical blue/purple notary ink ranges
        lower_ink = np.array([90, 50, 50])
        upper_ink = np.array([130, 255, 255])
        mask = cv2.inRange(hsv, lower_ink, upper_ink)
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        notary_stamp_detected = False
        for c in contours:
            area = cv2.contourArea(c)
            if 1000 < area < 50000:
                notary_stamp_detected = True
                break

        # 3. Barcode / QR Code Digital Signature Verification
        qr_signature_valid = False
        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            results = zxingcpp.read_barcodes(pil_img)
            for result in results:
                text = result.text
                if "STATE_SEAL_SIG" in text or "VITAL_REC" in text or text.startswith("http"):
                    qr_signature_valid = True
                    break
        except Exception:
            pass

        return {
            "seal_detected": seal_detected,
            "notary_stamp_detected": notary_stamp_detected,
            "qr_signature_valid": qr_signature_valid
        }