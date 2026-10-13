import asyncio
import logging
from datetime import datetime, timedelta, timezone
from app.core.database import SessionLocal
from app.models.vault import Vault, VaultState
from app.models.oracle_job import OracleJob
from app.services.vault_state_machine import VaultStateMachineService
from app.services.notifications import NotificationService

logger = logging.getLogger("WatchdogService")


async def check_heartbeats():
    """
    Periodic Background Watchdog Loop:
    1. Checks user inactivity for 30-day reminders.
    2. Checks 44-day inactivity to send beneficiary warnings.
    3. Auto-enforces 30-day Vault challenge window expiration.
    """
    while True:
        try:
            db = SessionLocal()
            now = datetime.now(timezone.utc)

            # --- TASK A: 30-Day Check-In Reminders ---
            thirty_days_ago = now - timedelta(days=30)
            vaults_30d = db.query(Vault).filter(
                Vault.state == VaultState.ACTIVE,
                Vault.updated_at <= thirty_days_ago,
                Vault.updated_at > now - timedelta(days=44)
            ).all()

            for vault in vaults_30d:
                logger.info(f"🔔 [WATCHDOG] 30-day check-in alert triggered for: {vault.owner_pubkey}")
                NotificationService.dispatch(
                    db=db,
                    user_pubkey=vault.owner_pubkey,
                    template_name="checkin_reminder_30d",
                    variables={"username": vault.owner_pubkey[:8]}
                )

            # --- TASK B: 44-Day Beneficiary Inactivity Alert ---
            forty_four_days_ago = now - timedelta(days=44)
            vaults_44d = db.query(Vault).filter(
                Vault.state == VaultState.ACTIVE,
                Vault.updated_at <= forty_four_days_ago
            ).all()

            for vault in vaults_44d:
                logger.info(f"⚠️ [WATCHDOG] 44-day inactivity alert triggered for: {vault.owner_pubkey}")
                NotificationService.dispatch(
                    db=db,
                    user_pubkey=vault.owner_pubkey,
                    template_name="beneficiary_alert_44d",
                    variables={"username": vault.owner_pubkey[:8]}
                )

            # --- TASK C: Expired Challenge Windows (from Step 5) ---
            expired_vaults = db.query(Vault).filter(
                Vault.state == VaultState.IN_CHALLENGE,
                Vault.challenge_end_time <= now
            ).all()

            for vault in expired_vaults:
                logger.info(f"⌛ [WATCHDOG] Processing expired challenge for: {vault.owner_pubkey}")
                try:
                    VaultStateMachineService.process_expired_challenge(db, vault.owner_pubkey)
                except Exception as e:
                    logger.error(f"Error resolving challenge for {vault.owner_pubkey}: {str(e)}")

            db.close()
        except Exception as err:
            logger.error(f"Watchdog main execution error: {str(err)}")

        # Runs poll every 60 seconds
        await asyncio.sleep(60)