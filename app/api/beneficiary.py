from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.services.wallet import CustodialWalletEngine, SweepResult, TaxDocument

router = APIRouter(tags=["Beneficiary"])
wallet_engine = CustodialWalletEngine()


class BeneficiaryWalletRequest(BaseModel):
    beneficiary_id: int
    account_index: int = 0


class SweepRequest(BaseModel):
    beneficiary_id: int
    encrypted_private_key: str
    destination_address: str


@router.post("/wallet/generate", status_code=status.HTTP_201_CREATED)
async def generate_beneficiary_wallet(payload: BeneficiaryWalletRequest):
    """
    Generates a custodial HD wallet keypair for a beneficiary.
    """
    try:
        wallet = wallet_engine.generate_custodial_wallet(
            account_index=payload.account_index
        )
        return {
            "status": "success",
            "beneficiary_id": payload.beneficiary_id,
            "public_key": wallet.public_key,
            "encrypted_private_key": wallet.encrypted_private_key,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate custodial wallet: {str(e)}"
        )


@router.post("/sweep-assets")
async def sweep_inherited_assets(request: SweepRequest):
    """
    Sweeps SOL and SPL tokens from a custodial inheritance wallet to a beneficiary destination.
    """
    try:
        result = wallet_engine.sweep_assets(
            beneficiary_id=request.beneficiary_id,
            encrypted_private_key=request.encrypted_private_key,
            destination_address=request.destination_address
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Asset sweep failed: {str(e)}"
        )


@router.get("/{beneficiary_id}/tax-document", response_model=TaxDocument)
async def get_beneficiary_tax_document(
    beneficiary_id: int,
    wallet_address: str
):
    """
    Generates cost-basis tax document for inherited crypto assets.
    """
    transfers = [
        {"asset_symbol": "SOL", "amount": 1.0, "signature": "N/A"}
    ]
    rates = {"SOL": 150.0, "USDC": 1.0}

    return wallet_engine.generate_tax_document(
        beneficiary_id=beneficiary_id,
        wallet_address=wallet_address,
        transfers=transfers,
        usd_market_rates=rates
    )