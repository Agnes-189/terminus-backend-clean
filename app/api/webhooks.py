import os
import logging
from fastapi import APIRouter, Request, HTTPException, Header, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from app.services.event_processor import (
    event_processor,
    verify_webhook_signature,
    SolanaEventParser,
)
from app.services.retry_utils import dead_letter_queue

logger = logging.getLogger(__name__)

router = APIRouter()


class GenericWebhookPayload(BaseModel):
    event_type: str = Field(..., example="VAULT_CHALLENGED")
    signature: str = Field(..., example="5K...txSignature")
    vault_address: Optional[str] = Field(None, example="VaultPubKey111111111111111111111111111111")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)


@router.post("/solana", summary="Solana Program Event Webhook Endpoint")
async def handle_solana_webhook(
    request: Request,
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
    x_webhook_timestamp: Optional[str] = Header(None, alias="X-Webhook-Timestamp"),
):
    """
    Ingests Solana program webhooks (e.g. Helius / QuickNode / Anchor events).
    Validates HMAC signature, prevents replay attacks, parses logs, and enqueues events.
    """
    body_bytes = await request.body()
    secret = os.getenv("WEBHOOK_SECRET", "default_webhook_secret_key_change_me")

    # 1. Signature Verification & Replay Protection (if signature headers present)
    if x_webhook_signature and x_webhook_timestamp:
        is_valid = verify_webhook_signature(
            payload_bytes=body_bytes,
            signature=x_webhook_signature,
            secret=secret,
            timestamp_str=x_webhook_timestamp
        )
        if not is_valid:
            logger.warning("[Webhook API] Invalid or expired webhook signature.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired webhook signature."
            )

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    # 2. Extract Event Data
    event_data = SolanaEventParser.extract_event_data(payload)

    # Parse logs if present in payload
    if "logs" in payload and isinstance(payload["logs"], list):
        parsed_log_events = SolanaEventParser.parse_logs(payload["logs"])
        if parsed_log_events:
            event_data["event_type"] = parsed_log_events[0]["event_type"]

    # 3. Enqueue for Idempotent Processing
    enqueued = await event_processor.enqueue_event(event_data)

    return {
        "success": True,
        "enqueued": enqueued,
        "signature": event_data["signature"],
        "event_type": event_data["event_type"]
    }


@router.get("/dlq", summary="Inspect Dead-Letter Queue (DLQ) Failed Events")
async def get_dlq_events(limit: int = 50):
    """Returns unrecoverable or failed webhook events from Dead Letter Queue."""
    return {
        "queue_size": len(dead_letter_queue.get_items(limit=1000)),
        "items": dead_letter_queue.get_items(limit=limit)
    }
