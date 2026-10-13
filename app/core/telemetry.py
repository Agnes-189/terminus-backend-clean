import json
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variable to hold trace ID across async execution contexts
trace_id_ctx: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


def get_current_trace_id() -> str:
    """Retrieves current execution trace ID or generates a fallback if missing."""
    tid = trace_id_ctx.get()
    if not tid:
        tid = f"tr-{uuid.uuid4().hex[:12]}"
        trace_id_ctx.set(tid)
    return tid


class StructuredJSONFormatter(logging.Formatter):
    """
    Formats standard Python log records as structured JSON payloads
    containing timestamps, log level, trace IDs, and context dictionaries.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id_ctx.get() or "no-trace-context",
            "module": record.module,
            "line": record.lineno,
        }

        # Include exception details if present
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        # Include custom extra fields attached to log records
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_payload["context"] = record.extra_data

        return json.dumps(log_payload)


def setup_telemetry_logging(log_level: str = "INFO"):
    """Initializes root logging handlers with JSON formatting."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers to avoid duplicate output
    root_logger.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(StructuredJSONFormatter())
    root_logger.addHandler(stream_handler)

    # Suppress noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
