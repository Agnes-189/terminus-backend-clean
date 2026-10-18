import pytest
import pytest_asyncio
from typing import AsyncGenerator
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.services.wallet import CustodialWalletEngine

# In-Memory SQLite Database for Isolated Testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Provides a fresh, isolated database session per test function."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden database dependency."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    # Yield TestClient directly without entering 'with TestClient(app)'
    # to avoid triggering blocking app lifespan/startup hooks.
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTPX client for testing asynchronous API routes."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_wallet_engine(mocker):
    """
    Globally mocks external Solana RPC calls across CustodialWalletEngine methods
    for all tests automatically.
    """
    mocker.patch.object(
        CustodialWalletEngine,
        "get_wallet_balances",
        create=True,
        return_value=mocker.MagicMock(
            sol_balance=1.5,
            spl_tokens=[{
                "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "token_account": "MockTokenAccount123",
                "amount": "100000000",
                "decimals": 6,
                "ui_amount": 100.0
            }]
        )
    )
    mocker.patch.object(
        CustodialWalletEngine,
        "sweep_assets",
        create=True,
        return_value={
            "success": True,
            "signatures": ["5K8mock_signature_solana_tx"],
            "error": None
        }
    )