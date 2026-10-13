import asyncio
import logging
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.orchestrator import MasterOracleOrchestrator

logger = logging.getLogger("CeleryClaimWorker")

@celery_app.task(bind=True, name="app.tasks.process_claim_task", max_retries=3, default_retry_delay=5)
def process_claim_task(self, file_bytes: bytes, filename: str, username: str, vault_owner: str, claimant_pubkey: str):
    """Asynchronous Celery task wrapping MasterOracleOrchestrator pipeline execution."""
    logger.info(f"⚙️ [CELERY WORKER] Processing task {self.request.id} for user: {username}")
    db = SessionLocal()
    try:
        orchestrator = MasterOracleOrchestrator(db=db)
        result = asyncio.run(
            orchestrator.execute_claim_workflow(
                username=username,
                vault_owner=vault_owner,
                claimant_pubkey=claimant_pubkey,
                file_bytes=file_bytes,
                filename=filename
            )
        )
        logger.info(f"✅ [CELERY WORKER] Completed task {self.request.id}")
        return result
    except Exception as exc:
        logger.error(f"❌ [CELERY WORKER] Task {self.request.id} failed: {str(exc)}")
        raise self.retry(exc=exc)
    finally:
        db.close()
