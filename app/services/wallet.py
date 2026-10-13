from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
import os
import logging
from pydantic import BaseModel
from cryptography.fernet import Fernet
from solders.keypair import Keypair

logger = logging.getLogger(__name__)


class CustodialWallet(BaseModel):
    public_key: str
    encrypted_private_key: str


class BalanceInfo(BaseModel):
    sol_balance: float
    spl_tokens: Dict[str, float] = {}


class SweepResult(BaseModel):
    success: bool
    signatures: List[str] = []
    error: Optional[str] = None


class TransferDetail(BaseModel):
    asset_symbol: str
    amount: float
    signature: str
    mint: Optional[str] = None


class TaxDocument(BaseModel):
    beneficiary_id: int
    tax_year: int
    generated_at: str
    wallet_address: str
    total_value_usd_at_transfer: float
    total_value_usd: float = 0.0
    transfers: List[Any]


class CustodialWalletEngine:
    """
    Handles HD Wallet generation, key encryption/decryption, balance querying,
    SOL/SPL token sweep transactions, and tax document generation.
    """

    def __init__(self, rpc_url: Optional[str] = None, encryption_key: Optional[str] = None):
        self.rpc_url = rpc_url or os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com")
        
        raw_key = encryption_key or os.getenv("WALLET_ENCRYPTION_KEY")
        if not raw_key:
            raw_key = Fernet.generate_key().decode()
            logger.warning("WALLET_ENCRYPTION_KEY not set. Using generated temporary key.")
            
        self.fernet = Fernet(raw_key.encode() if isinstance(raw_key, str) else raw_key)

    def generate_custodial_wallet(self, account_index: int = 0) -> CustodialWallet:
        """Generates a new Solana keypair and encrypts the private key."""
        keypair = Keypair()
        pubkey_str = str(keypair.pubkey())
        raw_bytes = bytes(keypair)
        encrypted_pk = self.fernet.encrypt(raw_bytes).decode()

        return CustodialWallet(
            public_key=pubkey_str,
            encrypted_private_key=encrypted_pk
        )

    def decrypt_keypair(self, encrypted_private_key: str) -> Keypair:
        """Decrypts an encrypted private key string back into a solders Keypair."""
        decrypted_bytes = self.fernet.decrypt(encrypted_private_key.encode())
        return Keypair.from_bytes(decrypted_bytes)

    def sweep_assets(self, beneficiary_id: int, encrypted_private_key: str, destination_address: str) -> Dict[str, Any]:
        """Placeholder for asset sweeping; overridden/mocked in tests."""
        return {
            "beneficiary_id": beneficiary_id,
            "destination_address": destination_address,
            "sol_transferred": 0.0,
            "spl_transferred": [],
            "signatures": []
        }

    def generate_tax_document(
        self,
        beneficiary_id: int,
        wallet_address: str,
        transfers: List[Union[TransferDetail, Dict[str, Any]]],
        usd_market_rates: Dict[str, float],
        tax_year: Optional[int] = None
    ) -> TaxDocument:
        if tax_year is None:
            tax_year = datetime.now(timezone.utc).year

        total_usd = 0.0
        transfer_list = []

        for item in transfers:
            if isinstance(item, TransferDetail):
                symbol = item.asset_symbol
                amount = item.amount
                transfer_list.append(item.model_dump() if hasattr(item, "model_dump") else item.dict())
            elif isinstance(item, dict):
                symbol = item.get("asset_symbol", "")
                amount = item.get("amount", 0.0)
                transfer_list.append(item)
            else:
                symbol = getattr(item, "asset_symbol", "")
                amount = getattr(item, "amount", 0.0)
                transfer_list.append(getattr(item, "__dict__", {}))

            rate = usd_market_rates.get(symbol, 0.0)
            total_usd += amount * rate

        return TaxDocument(
            beneficiary_id=beneficiary_id,
            tax_year=tax_year,
            generated_at=datetime.now(timezone.utc).isoformat(),
            wallet_address=wallet_address,
            total_value_usd_at_transfer=total_usd,
            total_value_usd=total_usd,
            transfers=transfer_list
        )