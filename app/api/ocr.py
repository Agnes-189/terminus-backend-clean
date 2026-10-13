import os
import shutil
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from app.services.ocr_engine import OCREngineService
from app.services.blockchain import generate_zk_proof
from app.services.solana_client import trigger_challenge

logger = logging.getLogger(__name__)

router = APIRouter()
TEMP_DIR = "temp_uploads"

# Ensure temp directory exists
os.makedirs(TEMP_DIR, exist_ok=True)


@router.post("/process-document")
async def process_document(file: UploadFile = File(...)):
    """
    Standalone OCR testing endpoint.
    Extracts text, classifies document type, and outputs confidence score.
    Reads file directly in memory without saving to disk.
    """
    try:
        file_bytes = await file.read()
        result = OCREngineService.process_document(file_bytes, file.filename)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OCR processing failed: {str(e)}"
        )


@router.post("/verify-claim")
async def verify_claim(
    username: str = Form(...),
    vault_owner: str = Form(...),
    claimant_pubkey: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Full Production Claim Pipeline:
    1. Receives Claim Document
    2. Runs Real AI OCR & Field Extraction Engine
    3. Generates Real Groth16 Zero-Knowledge Proof
    4. KDPA Compliance: Immediately purges sensitive files from disk
    5. Triggers Solana On-Chain Challenge via AI Oracle Keypair
    """
    path = os.path.join(TEMP_DIR, file.filename)

    try:
        # Save file temporarily for image preprocessing
        with open(path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 1. Real AI OCR & Entity Extraction
        print(f"🔍 [AI OCR Engine] Processing document for '{username}'...")
        with open(path, "rb") as f:
            file_bytes = f.read()

        ocr_result = OCREngineService.process_document(file_bytes, file.filename)
        confidence_score = ocr_result["confidence_score"]
        doc_type = ocr_result["document_type"]

        print(f"📊 [OCR RESULT] Type: {doc_type} | Confidence: {confidence_score}")

        # Quality check threshold
        if confidence_score < 0.50:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Document confidence too low ({confidence_score}). Please upload a clearer copy."
            )

        # 2. Real ZK-Proof Generation via Groth16 / snarkjs
        print("🔐 [ZK-PROOF] Generating Groth16 Zero-Knowledge Proof...")
        zk_proof = await generate_zk_proof(
            filename=file.filename,
            confidence_score=confidence_score
        )

        # 3. KDPA Compliance: Delete sensitive image immediately
        if os.path.exists(path):
            os.remove(path)
            print(f"🗑️ [KDPA COMPLIANCE] {file.filename} purged from server disk.")

        # 4. Trigger Solana Challenge
        try:
            solana_res = await trigger_challenge(
                vault_owner=vault_owner,
                claimant_pubkey=claimant_pubkey,
                claim_type=2,  # 2 = Deceased / Death Certificate
            )

            return {
                "status": "SUCCESS",
                "document_analysis": ocr_result,
                "zk_proof": zk_proof,
                "solana_tx": solana_res.get("tx_signature"),
                "vault_pda": solana_res.get("vault_pda"),
                "message": "AI Verification complete. Real ZK Proof generated & Solana Challenge triggered."
            }

        except Exception as sol_err:
            print(f"❌ [SOLANA ERROR] {str(sol_err)}")
            return {
                "status": "OCR_SUCCESS_SOLANA_FAIL",
                "document_analysis": ocr_result,
                "zk_proof": zk_proof,
                "error": f"Document verified & ZK proof generated, but on-chain trigger failed: {str(sol_err)}"
            }

    except Exception as e:
        # Guarantee file purging even if processing crashes
        if os.path.exists(path):
            os.remove(path)
            print(f"🗑️ [KDPA COMPLIANCE] Emergency purge executed for {file.filename}.")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))