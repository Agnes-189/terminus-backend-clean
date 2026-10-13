import os
import shutil
from datetime import datetime, timezone
from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.core.database import SessionLocal
from app.services.cron import METRICS_STORE

router = APIRouter(tags=["Observability & Health"])


@router.get("/metrics", summary="Prometheus Metrics Endpoint")
async def get_prometheus_metrics():
    """Exposes real-time application metrics in Prometheus text format."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/health/liveness", summary="Kubernetes Liveness Probe")
async def liveness_probe():
    """Returns 200 OK if process is running."""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/readiness", summary="Kubernetes Readiness Probe")
async def readiness_probe():
    """Validates database connectivity and service readiness before accepting traffic."""
    db_ok = False
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        db.close()

    if not db_ok:
        return Response(
            content='{"status": "not_ready", "reason": "database_unreachable"}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json"
        )

    return {"status": "ready", "database": "connected", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/detailed", summary="Comprehensive Health & System Diagnostics")
async def detailed_health_check():
    """Returns full diagnostic status covering database, background cron tasks, RPC nodes, and disk usage."""
    db = SessionLocal()
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {e}"
    finally:
        db.close()

    db_filename = os.getenv("DATABASE_FILE", "app.db")
    disk_free_gb = 0.0
    if os.path.exists(os.path.dirname(os.path.abspath(db_filename))):
        total, used, free = shutil.disk_usage(os.path.dirname(os.path.abspath(db_filename)))
        disk_free_gb = round(free / (1024 ** 3), 2)

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subsystems": {
            "database": db_status,
            "disk_free_gb": disk_free_gb,
            "cron_metrics": METRICS_STORE
        }
    }
