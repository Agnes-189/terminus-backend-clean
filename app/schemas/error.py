from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    error_code: str = Field(..., example="RPC_FAILURE", description="Machine-readable error identifier.")
    message: str = Field(..., example="Solana RPC endpoint failed to respond.", description="Human-readable error description.")
    recovery_hint: Optional[str] = Field(
        None,
        example="Retry the operation after exponential backoff delay.",
        description="Actionable instruction to resolve or recover from the error."
    )
    details: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        example={"rpc_url": "https://api.devnet.solana.com"},
        description="Structured context and error metadata."
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        example="2026-09-30T19:42:00Z",
        description="UTC timestamp of the error event."
    )
    path: Optional[str] = Field(None, example="/api/v1/vault/sweep", description="Endpoint path where error occurred.")


class StandardErrorResponse(BaseModel):
    success: bool = Field(False, example=False)
    error: ErrorDetail


class RateLimitErrorResponse(BaseModel):
    success: bool = Field(False, example=False)
    error: ErrorDetail = Field(
        default={
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": "Too many requests. Rate limit exceeded.",
            "recovery_hint": "Please wait until X-RateLimit-Reset epoch time before making additional requests.",
            "details": {"limit": 100, "window_seconds": 60},
            "timestamp": "2026-09-30T19:42:00Z",
            "path": "/api/v1/vault"
        }
    )
