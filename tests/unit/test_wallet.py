import pytest
from app.services.wallet import CustodialWalletEngine, TaxDocument, TransferDetail


def test_custodial_wallet_generation():
    engine = CustodialWalletEngine()
    wallet = engine.generate_custodial_wallet(account_index=0)

    assert wallet.public_key is not None
    assert len(wallet.public_key) >= 32
    assert wallet.encrypted_private_key is not None
    assert wallet.encrypted_private_key != wallet.public_key


def test_private_key_encryption_decryption_roundtrip():
    engine = CustodialWalletEngine()
    wallet = engine.generate_custodial_wallet()

    # Decrypt keypair and ensure pubkey matches
    keypair = engine.decrypt_keypair(wallet.encrypted_private_key)
    assert str(keypair.pubkey()) == wallet.public_key


def test_tax_document_generation():
    engine = CustodialWalletEngine()
    transfers = [
        TransferDetail(asset_symbol="SOL", amount=2.0, signature="tx_sig_1"),
        TransferDetail(mint="USDC_MINT", asset_symbol="USDC", amount=150.0, signature="tx_sig_2")
    ]

    rates = {"SOL": 150.0, "USDC": 1.0}
    tax_doc = engine.generate_tax_document(
        beneficiary_id=101,
        wallet_address="MockWallet123",
        transfers=transfers,
        usd_market_rates=rates
    )

    assert tax_doc.beneficiary_id == 101
    assert tax_doc.total_value_usd == 450.0  # (2.0 * 150.0) + (150.0 * 1.0)
    assert len(tax_doc.transfers) == 2