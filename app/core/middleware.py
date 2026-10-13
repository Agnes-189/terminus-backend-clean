import logging
import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram

from app.core.telemetry import trace_id_ctx

logger = logging.getLogger("terminus.middleware")

# --- Prometheus Metrics Definitions ---

HTTP_REQUESTS_TOTAL = Counter(
    "terminus_http_requests_total",
    "Total HTTP requests received by endpoint and status code.",
    ["method", "endpoint", "status_code"]
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "terminus_http_request_duration_seconds",
    "HTTP request duration latency distributions in seconds.",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

ANOMALY_ALERTS_TOTAL = Counter(
    "terminus_anomaly_alerts_total",
    "Total security anomalies or RPC failure spikes detected.",
    ["alert_type"]
)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware executing:
    1. Trace ID generation and context propagation (X-Trace-ID header).
    2. Request/response execution logging with latency profiling.
    3. Real-time Prometheus metric updates.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # 1. Extract or generate trace ID
        incoming_trace_id = request.headers.get("X-Trace-ID") or request.headers.get("X-Request-ID")
        trace_id = incoming_trace_id or f"tr-{uuid.uuid4().hex[:12]}"
        trace_id_token = trace_id_ctx.set(trace_id)

        endpoint_path = request.url.path

        try:
            response = await call_next(request)
            duration = time.time() - start_time
            status_code = response.status_code

            # 2. Record Prometheus Metrics
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=endpoint_path,
                status_code=str(status_code)
            ).inc()

            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=request.method,
                endpoint=endpoint_path
            ).observe(duration)

            # 3. Add trace ID to response headers
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Response-Time"] = f"{duration * 1000:.2f}ms"

            # 4. Structured Request Logging
            log_level = logging.WARNING if status_code >= 400 else logging.INFO
            logger.log(
                log_level,
                f"HTTP {request.method} {endpoint_path} -> {status_code} ({duration*1000:.2f}ms)",
                extra={"extra_data": {
                    "method": request.method,
                    "path": endpoint_path,
                    "status_code": status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "client_ip": request.client.host if request.client else "unknown"
                }}
            )

            if status_code >= 500:
                ANOMALY_ALERTS_TOTAL.labels(alert_type="5xx_server_error").inc()

            return response

        except Exception as exc:
            duration = time.time() - start_time
            ANOMALY_ALERTS_TOTAL.labels(alert_type="unhandled_exception").inc()
            logger.error(
                f"Unhandled Exception on {request.method} {endpoint_path}: {exc}",
                exc_info=True,
                extra={"extra_data": {
                    "method": request.method,
                    "path": endpoint_path,
                    "duration_ms": round(duration * 1000, 2)
                }}
            )
            raise exc
        finally:
            trace_id_ctx.reset(trace_id_token)
