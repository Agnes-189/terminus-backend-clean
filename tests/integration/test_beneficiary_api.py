import pytest


def test_generate_beneficiary_wallet_endpoint(client):
    response = client.post(
        "/api/v1/beneficiary/wallet/generate",
        json={"beneficiary_id": 1, "account_index": 0}
    )
    assert response.status_code == 201
    data = response.json()
    assert "public_key" in data
    assert "encrypted_private_key" in data


def test_health_metrics_endpoint(client):
    response = client.get("/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "subsystems" in data
    assert data["subsystems"]["cron_metrics"]["system_status"] in ["healthy", "degraded"]