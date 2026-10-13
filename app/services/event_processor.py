import asyncio
import base64
import hashlib
import hmac
import logging
import os
import time
from enum import Enum
from typing import Any, Dict, Optional, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.services.retry_utils import dead_letter_queue, idempotency_tracker

logger = logging.getLogger(__name__)


# --- 1. Event Types ---

class VaultEventType(str, Enum):
    VAULT_CREATED = "VAULT_CREATED"
    VAULT_CHALLENGED = "VAULT_CHALLENGED"
    VAULT_UNLOCKED = "VAULT_UNLOCKED"
    VAULT_CLAIMED = "VAULT_CLAIMED"
    HEARTBEAT_PINGED = "HEARTBEAT_PINGED"
    UNKNOWN = "UNKNOWN"


# --- 2. Webhook Signature Validation & Replay Protection ---

def verify_webhook_signature(
    payload_bytes: bytes,
    signature: str,
    secret: str,
    timestamp_str: str,
    max_age_seconds: int = 300
) -> bool:
    """
    Validates HMAC-SHA256 signature and enforces a strict time window to prevent replay attacks.
    """
    if not signature or not secret or not timestamp_str:
        return False

    # Replay protection check
    try:
        timestamp = float(timestamp_str)
        if abs(time.time() - timestamp) > max_age_seconds:
            logger.warning(f"[Webhook Security] Rejected expired signature (delta: {abs(time.time() - timestamp)}s)")
            return False
    except ValueError:
        return False

    # Compute expected signature: HMAC-SHA256(secret, timestamp + "." + payload)
    message = f"{timestamp_str}.".encode("utf-8") + payload_bytes
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_sig, signature.lower())


# --- 3. Solana Program Event Parser ---

class SolanaEventParser:
    """
    Parses raw Solana program logs and transaction metadata into structured Terminus events.
    Supports Anchor program log formats and standard Helius/QuickNode webhooks.
    """

    @staticmethod
    def parse_logs(logs: List[str]) -> List[Dict[str, Any]]:
        events = []
        for log in logs:
            if "Instruction: CreateVault" in log or "Program log: Event: VaultCreated" in log:
                events.append({"event_type": VaultEventType.VAULT_CREATED, "raw_log": log})
            elif "Instruction: TriggerChallenge" in log or "Program log: Event: VaultChallenged" in log:
                events.append({"event_type": VaultEventType.VAULT_CHALLENGED, "raw_log": log})
            elif "Instruction: UnlockVault" in log or "Program log: Event: VaultUnlocked" in log:
                events.append({"event_type": VaultEventType.VAULT_UNLOCKED, "raw_log": log})
            elif "Instruction: ClaimInheritance" in log or "Program log: Event: VaultClaimed" in log:
                events.append({"event_type": VaultEventType.VAULT_CLAIMED, "raw_log": log})
            elif "Instruction: PingHeartbeat" in log or "Program log: Event: HeartbeatPinged" in log:
                events.append({"event_type": VaultEventType.HEARTBEAT_PINGED, "raw_log": log})
        return events

    @staticmethod
    def extract_event_data(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts normalized transaction data from standard Solana RPC/webhook payloads."""
        tx_signature = payload.get("signature") or payload.get("txHash") or f"evt_{time.time()}"
        vault_address = payload.get("vault_address") or payload.get("account")
        event_type_str = payload.get("event_type", "UNKNOWN")

        try:
            event_type = VaultEventType(event_type_str)
        except ValueError:
            event_type = VaultEventType.UNKNOWN

        return {
            "signature": tx_signature,
            "vault_address": vault_address,
            "event_type": event_type,
            "timestamp": payload.get("timestamp", time.time()),
            "details": payload.get("details", {})
        }


# --- 4. Event Processing Handlers ---

class EventProcessor:
    """
    Idempotent vault state updater and queue worker.
    """

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def enqueue_event(self, event_data: Dict[str, Any]) -> bool:
        tx_sig = event_data.get("signature")

        # Idempotency Check: Prevent duplicate processing of the same transaction signature
        if tx_sig and idempotency_tracker.is_processed(tx_sig):
            logger.info(f"[EventProcessor] Skipping duplicate event transaction: {tx_sig}")
            return False

        if tx_sig:
            idempotency_tracker.record_start(tx_sig)

        await self._queue.put(event_data)
        return True

    async def start_worker(self):
        self._running = True
        logger.info("[EventProcessor] Background webhook event queue worker started.")
        while self._running:
            try:
                event_data = await self._queue.get()
                await self._process_single_event(event_data)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[EventProcessor] Queue worker loop error: {e}")

    def stop_worker(self):
        self._running = False

    async def _process_single_event(self, event_data: Dict[str, Any]):
        tx_sig = event_data.get("signature")
        event_type = event_data.get("event_type")
        vault_address = event_data.get("vault_address")

        logger.info(f"[EventProcessor] Processing event '{event_type}' for Vault '{vault_address}' (Tx: {tx_sig})")

        db: Session = SessionLocal()
        try:
            if vault_address:
                if event_type == VaultEventType.VAULT_CHALLENGED:
                    db.execute(
                        text("UPDATE vaults SET is_active = :status WHERE vault_address = :addr"),
                        {"status": False, "addr": vault_address}
                    )
                elif event_type == VaultEventType.VAULT_UNLOCKED:
                    db.execute(
                        text("UPDATE vaults SET is_active = :status WHERE vault_address = :addr"),
                        {"status": True, "addr": vault_address}
                    )
                elif event_type == VaultEventType.HEARTBEAT_PINGED:
                    db.execute(
                        text("UPDATE vaults SET updated_at = CURRENT_TIMESTAMP WHERE vault_address = :addr"),
                        {"addr": vault_address}
                    )

                db.commit()

            if tx_sig:
                idempotency_tracker.record_success(tx_sig, result={"status": "PROCESSED"})

        except Exception as exc:
            db.rollback()
            logger.error(f"[EventProcessor] Failed processing event (Tx: {tx_sig}): {exc}")
            # Enqueue failed event to Dead Letter Queue for auditing
            dead_letter_queue.enqueue(
                task_name="process_solana_event",
                payload=event_data,
                error=exc
            )
        finally:
            db.close()


event_processor = EventProcessor()
