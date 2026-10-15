import pytest


@pytest.mark.asyncio
async def test_full_inheritance_lifecycle(async_client, mocker):
    # 1. Generate Custodial Wallet
    gen_resp = await async_client.post(
        "/api/v1/beneficiary/wallet/generate",
        json={"beneficiary_id": 99, "account_index": 0}
    )
    assert gen_resp.status_code == 201
    wallet_data = gen_resp.json()
    enc_key = wallet_data["encrypted_private_key"]
    pub_key = wallet_data["public_key"]

    # 2. Mock Solana RPC Sweep in CustodialWalletEngine
    mocker.patch(
        "app.services.wallet.CustodialWalletEngine.sweep_assets",
        return_value={
            "beneficiary_id": 99,
            "destination_address": "DestAddress1111111111111111111111111111111",
            "sol_transferred": 1.495,
            "spl_transferred": [],
            "signatures": ["mock_tx_signature_abc123"]
        }
    )

    # 3. Execute Asset Sweep
    sweep_resp = await async_client.post(
        "/api/v1/beneficiary/sweep-assets",
        json={
            "beneficiary_id": 99,
            "encrypted_private_key": enc_key,
            "destination_address": "DestAddress1111111111111111111111111111111"
        }
    )
    assert sweep_resp.status_code == 200
    sweep_data = sweep_resp.json()
    assert sweep_data["sol_transferred"] > 0
    assert "mock_tx_signature_abc123" in sweep_data["signatures"]

    # 4. Fetch Tax Document
    tax_resp = await async_client.get(
        f"/api/v1/beneficiary/99/tax-document?wallet_address={pub_key}"
    )
    assert tax_resp.status_code == 200
    tax_data = tax_resp.json()
    assert tax_data["beneficiary_id"] == 99
    assert tax_data["total_value_usd"] >= 0.0