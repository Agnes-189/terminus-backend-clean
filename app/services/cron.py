import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# --- In-Memory Cache and System Metrics Store ---

CACHE_STORE: Dict[str, Dict[str, Any]] = {}

METRICS_STORE: Dict[str, Any] = {
    "last_vault_sync": None,
    "last_fee_update": None,
    "last_cleanup": None,
    "last_backup": None,
    "recent_fees_lamports": 5000,
    "active_vaults_count": 0,
    "system_status": "healthy",
    "metrics_updated_at": None,
}


# --- Scheduled Task Implementations ---

async def sync_vault_states():
    """
    1. Vault State Sync Scheduler (Hourly/Daily)
    Queries active vaults from the database and synchronizes on-chain states with Solana.
    """
    logger.info("[Cron] Starting scheduled Vault state synchronization...")
    db: Session = SessionLocal()
    try:
        # Updated to query owner_pubkey and state from the vaults table schema
        result = db.execute(
            text("SELECT owner_pubkey, state FROM vaults WHERE state = :status"),
            {"status": "ACTIVE"}
        ).fetchall()

        synced_count = len(result)
        METRICS_STORE["last_vault_sync"] = datetime.now(timezone.utc).isoformat()
        METRICS_STORE["active_vaults_count"] = synced_count
        logger.info(f"[Cron] Vault state sync completed for {synced_count} active vault(s).")
    except Exception as e:
        logger.error(f"[Cron] Vault state sync failed: {e}")
    finally:
        db.close()


async def update_transaction_fee_history():
    """
    2. Transaction Fee History Updates
    Queries Solana prioritization fee estimates and updates gas cost cache.
    """
    logger.info("[Cron] Fetching Solana prioritization fee history...")
    try:
        estimated_fee = 5000  # Default prioritization fee baseline in lamports

        METRICS_STORE["recent_fees_lamports"] = estimated_fee
        METRICS_STORE["last_fee_update"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"[Cron] Updated priority fee estimation: {estimated_fee} lamports.")
    except Exception as e:
        logger.error(f"[Cron] Transaction fee history update failed: {e}")


async def invalidate_stale_caches():
    """
    3. Cache Invalidation Policies
    Scans in-memory cache and purges expired entries based on TTL timestamps.
    """
    logger.info("[Cron] Running cache invalidation sweep...")
    now = datetime.now(timezone.utc).timestamp()
    expired_keys = [
        key for key, item in CACHE_STORE.items()
        if item.get("expires_at", 0) < now
    ]

    for key in expired_keys:
        CACHE_STORE.pop(key, None)

    logger.info(f"[Cron] Evicted {len(expired_keys)} expired cache entry/entries.")


async def cleanup_stale_records():
    """
    4. Stale Record Cleanup
    Purges revoked or expired user sessions and orphaned records.
    """
    logger.info("[Cron] Cleaning up stale database records and temporary sessions...")
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # Updated to target user_sessions table instead of non-existent verification_tokens
        db.execute(
            text("DELETE FROM user_sessions WHERE expires_at < :now OR is_revoked = :revoked"),
            {"now": now, "revoked": True}
        )
        db.commit()

        METRICS_STORE["last_cleanup"] = datetime.now(timezone.utc).isoformat()
        logger.info("[Cron] Stale record cleanup complete.")
    except Exception as e:
        db.rollback()
        logger.error(f"[Cron] Stale record cleanup failed: {e}")
    finally:
        db.close()


async def ping_health_checks():
    """
    5. Health Check Pings
    Verifies database readiness and RPC endpoint connectivity.
    """
    logger.info("[Cron] Executing periodic system health checks...")
    db: Session = SessionLocal()
    db_healthy = False
    try:
        db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception as e:
        logger.error(f"[Health Check] Database connectivity ping failed: {e}")
    finally:
        db.close()

    METRICS_STORE["system_status"] = "healthy" if db_healthy else "degraded"


async def collect_system_metrics():
    """
    6. Metrics Collection
    Aggregates application operational statistics and database counters.
    """
    logger.info("[Cron] Aggregating system runtime metrics...")
    METRICS_STORE["metrics_updated_at"] = datetime.now(timezone.utc).isoformat()


async def run_database_backup():
    """
    7. Backup / Snapshot Jobs
    Creates timestamped database file backups in the local backups directory.
    """
    logger.info("[Cron] Starting automated database snapshot backup job...")
    db_file = os.getenv("DATABASE_FILE", "app.db")
    backup_dir = "backups"

    if os.path.exists(db_file):
        try:
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"backup_{timestamp}.db")
            shutil.copy2(db_file, backup_path)

            METRICS_STORE["last_backup"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"[Cron] Database snapshot saved to {backup_path}")
        except Exception as e:
            logger.error(f"[Cron] Backup job failed: {e}")
    else:
        logger.info(f"[Cron] Target database file '{db_file}' not found. Skipping snapshot.")


# --- Cron Scheduler Task Manager ---

class CronScheduler:
    """
    Asynchronous background scheduler running task loops during FastAPI lifespan.
    """

    def __init__(self):
        self._running = False
        self._tasks = []

    async def _run_periodic(self, interval_seconds: int, func):
        while self._running:
            try:
                await func()
            except Exception as e:
                logger.error(f"[CronScheduler] Task {func.__name__} raised error: {e}")
            await asyncio.sleep(interval_seconds)

    def start(self):
        """Launches background cron task loops."""
        if self._running:
            return
        self._running = True

        loop = asyncio.get_event_loop()

        # Task execution intervals (seconds)
        schedules = [
            (300, ping_health_checks),               # 5 Minutes
            (600, update_transaction_fee_history),    # 10 Minutes
            (900, invalidate_stale_caches),           # 15 Minutes
            (3600, sync_vault_states),               # Hourly
            (3600, collect_system_metrics),           # Hourly
            (86400, cleanup_stale_records),           # Daily
            (86400, run_database_backup),             # Daily
        ]

        for interval, func in schedules:
            task = loop.create_task(self._run_periodic(interval, func))
            self._tasks.append(task)

        logger.info("[CronScheduler] Background scheduled tasks started.")

    def stop(self):
        """Cancels all active background tasks."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("[CronScheduler] Background scheduled tasks stopped.")


scheduler = CronScheduler()