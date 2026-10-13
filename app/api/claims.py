from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.orm import Session
from celery.result import AsyncResult
from app.core.database import get_db
from app.services.orchestrator import MasterOracleOrchestrator
from app.tasks.claim_tasks import process_claim_task

router = APIRouter(tags=["Claims Orchestrator"])


@router.post("/verify-and-trigger")
async def verify_and_trigger_claim(
    username: str = Form(...),
    vault_owner: str = Form(...),
    claimant_pubkey: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Synchronous claim verification pipeline execution."""
    try:
        file_bytes = await file.read()
        orchestrator = MasterOracleOrchestrator(db=db)
        result = await orchestrator.execute_claim_workflow(
            username=username,
            vault_owner=vault_owner,
            claimant_pubkey=claimant_pubkey,
            file_bytes=file_bytes,
            filename=file.filename
        )

        if result["status"] in ["FAILED", "ROLLED_BACK"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=result
            )

        return {"status": "success", "data": result}

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Master Orchestrator execution error: {str(e)}"
        )


@router.post("/verify-and-trigger-async", status_code=status.HTTP_202_ACCEPTED)
async def verify_and_trigger_claim_async(
    username: str = Form(...),
    vault_owner: str = Form(...),
    claimant_pubkey: str = Form(...),
    file: UploadFile = File(...)
):
    """Asynchronous claim verification: enqueues Celery task and returns immediately."""
    try:
        file_bytes = await file.read()
        task = process_claim_task.delay(
            file_bytes=file_bytes,
            filename=file.filename,
            username=username,
            vault_owner=vault_owner,
            claimant_pubkey=claimant_pubkey
        )
        return {
            "status": "queued",
            "message": "Claim verification queued successfully.",
            "task_id": task.id,
            "status_url": f"/api/v1/claims/jobs/{task.id}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue claim task: {str(e)}"
        )


@router.get("/jobs/{task_id}")
async def get_claim_job_status(task_id: str):
    """Polls Celery worker result by task_id."""
    task_result = AsyncResult(task_id)
    response = {
        "task_id": task_id,
        "status": task_result.status,
    }
    if task_result.ready():
        if task_result.successful():
            response["result"] = task_result.result
        else:
            response["error"] = str(task_result.result)
    return response
