import asyncio
import functools
import logging
import os
import random
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# --- 1. Error Codes & Domain Exception Hierarchy ---

class ErrorCode(str, Enum):
    RPC_FAILURE = "RPC_FAILURE"
    RPC_TIMEOUT = "RPC_TIMEOUT"
    TRANSACTION_REJECTED = "TRANSACTION_REJECTED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    DUPLICATE_TRANSACTION = "DUPLICATE_TRANSACTION"
    DLQ_ENQUEUED = "DLQ_ENQUEUED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class TerminusException(Exception):
    """Base exception for all Terminus engine failures with detailed recovery guidance."""
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        recovery_hint: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.recovery_hint = recovery_hint or "Retry the operation or check network status."
        self.details = details or {}


class RPCFailureException(TerminusException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.RPC_FAILURE,
            recovery_hint="Check RPC node availability; system will automatically attempt failover rotation.",
            details=details
        )


class TransactionRejectedException(TerminusException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.TRANSACTION_REJECTED,
            recovery_hint="Verify wallet SOL balance, prioritization fees, and transaction signature parameters.",
            details=details
        )


class CircuitOpenException(TerminusException):
    def __init__(self, circuit_name: str):
        super().__init__(
            message=f"Circuit breaker '{circuit_name}' is currently OPEN. Operations blocked.",
            error_code=ErrorCode.CIRCUIT_OPEN,
            recovery_hint="Subsystem is in cooling period after repeated failures. Retry shortly.",
            details={"circuit_name": circuit_name}
        )


class DuplicateTransactionException(TerminusException):
    def __init__(self, idempotency_key: str):
        super().__init__(
            message=f"Duplicate transaction attempt detected for key: {idempotency_key}",
            error_code=ErrorCode.DUPLICATE_TRANSACTION,
            recovery_hint="Use a unique idempotency key or retrieve result from original transaction.",
            details={"idempotency_key": idempotency_key}
        )


# --- 2. Alerting Engine ---

def trigger_alert(event_type: str, message: str, payload: Optional[Dict[str, Any]] = None):
    """Emits critical log entries and structured alert payloads for alerting systems."""
    alert_data = {
        "event_type": event_type,
        "timestamp": time.time(),
        "message": message,
        "details": payload or {}
    }
    logger.critical(f"🚨 [TERMINUS ALERT] {event_type.upper()}: {message} | Payload: {alert_data['details']}")


# --- 3. Circuit Breaker Pattern ---

class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Prevents cascading failures by blocking calls to failing downstream services.
    """
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exceptions: tuple = (Exception,)
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def __call__(self, func: Callable[..., Any]):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                self._before_call()
                try:
                    res = await func(*args, **kwargs)
                    self._on_success()
                    return res
                except self.expected_exceptions as e:
                    self._on_failure(e)
                    raise
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                self._before_call()
                try:
                    res = func(*args, **kwargs)
                    self._on_success()
                    return res
                except self.expected_exceptions as e:
                    self._on_failure(e)
                    raise
            return sync_wrapper

    def _before_call(self):
        now = time.time()
        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info(f"[CircuitBreaker:{self.name}] Entering HALF_OPEN state (testing recovery).")
            else:
                raise CircuitOpenException(self.name)

    def _on_success(self):
        if self.state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            logger.info(f"[CircuitBreaker:{self.name}] Target recovered. Resetting to CLOSED.")
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self, exc: Exception):
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            trigger_alert(
                event_type="CIRCUIT_BREAKER_TRIPPED",
                message=f"Circuit '{self.name}' OPENED after {self.failure_count} consecutive failures.",
                payload={"last_error": str(exc)}
            )


# --- 4. Exponential Backoff Retry Decorator ---

def with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Decorator executing retry attempts with exponential delay and randomized jitter.
    """
    def decorator(func: Callable[..., Any]):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                attempt = 0
                while True:
                    try:
                        return await func(*args, **kwargs)
                    except retryable_exceptions as exc:
                        attempt += 1
                        if attempt > max_retries:
                            logger.error(f"[Retry] Exceeded max retries ({max_retries}) for {func.__name__}: {exc}")
                            raise exc
                        delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                        if jitter:
                            delay = delay * (0.5 + random.random())
                        logger.warning(f"[Retry] {func.__name__} failed (attempt {attempt}/{max_retries}). Retrying in {delay:.2f}s...")
                        await asyncio.sleep(delay)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                attempt = 0
                while True:
                    try:
                        return func(*args, **kwargs)
                    except retryable_exceptions as exc:
                        attempt += 1
                        if attempt > max_retries:
                            logger.error(f"[Retry] Exceeded max retries ({max_retries}) for {func.__name__}: {exc}")
                            raise exc
                        delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                        if jitter:
                            delay = delay * (0.5 + random.random())
                        logger.warning(f"[Retry] {func.__name__} failed (attempt {attempt}/{max_retries}). Retrying in {delay:.2f}s...")
                        time.sleep(delay)
            return sync_wrapper
    return decorator


# --- 5. RPC Endpoint Failover Manager ---

class RPCFailoverManager:
    """
    Manages primary and fallback RPC endpoints with automatic failure detection and rotation.
    """
    def __init__(self, endpoints: Optional[List[str]] = None):
        env_fallbacks = os.getenv("SOLANA_RPC_FALLBACKS", "").split(",")
        primary = os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com")

        raw_list = (endpoints or []) + [primary] + [ep.strip() for ep in env_fallbacks if ep.strip()]
        self.endpoints = list(dict.fromkeys(raw_list))
        self.current_index = 0
        self.unhealthy_endpoints: Dict[str, float] = {}
        self.cooldown_seconds = 60.0

    def get_current_endpoint(self) -> str:
        now = time.time()
        for ep, bad_time in list(self.unhealthy_endpoints.items()):
            if now - bad_time > self.cooldown_seconds:
                self.unhealthy_endpoints.pop(ep, None)

        for i in range(len(self.endpoints)):
            idx = (self.current_index + i) % len(self.endpoints)
            ep = self.endpoints[idx]
            if ep not in self.unhealthy_endpoints:
                self.current_index = idx
                return ep

        return self.endpoints[self.current_index]

    def mark_unhealthy(self, endpoint: str):
        self.unhealthy_endpoints[endpoint] = time.time()
        logger.warning(f"[RPCFailover] Endpoint '{endpoint}' marked unhealthy. Rotating RPC node...")
        self.current_index = (self.current_index + 1) % len(self.endpoints)
        trigger_alert(
            event_type="RPC_FAILOVER_ROTATION",
            message=f"RPC failure on {endpoint}. Rotated to {self.get_current_endpoint()}",
            payload={"unhealthy_endpoints": list(self.unhealthy_endpoints.keys())}
        )


rpc_manager = RPCFailoverManager()


# --- 6. Idempotency Tracker ---

class IdempotencyTracker:
    """
    Registry preventing duplicate execution of sensitive requests or financial transactions.
    """
    def __init__(self, ttl_seconds: int = 86400):
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, Dict[str, Any]] = {}

    def is_processed(self, idempotency_key: str) -> bool:
        now = time.time()
        entry = self._store.get(idempotency_key)
        if not entry:
            return False
        if now - entry["created_at"] > self.ttl_seconds:
            self._store.pop(idempotency_key, None)
            return False
        return True

    def record_start(self, idempotency_key: str):
        if self.is_processed(idempotency_key):
            raise DuplicateTransactionException(idempotency_key)
        self._store[idempotency_key] = {
            "status": "PROCESSING",
            "created_at": time.time(),
            "result": None
        }

    def record_success(self, idempotency_key: str, result: Any = None):
        if idempotency_key in self._store:
            self._store[idempotency_key]["status"] = "COMPLETED"
            self._store[idempotency_key]["result"] = result

    def get_result(self, idempotency_key: str) -> Optional[Any]:
        entry = self._store.get(idempotency_key)
        if entry and entry["status"] == "COMPLETED":
            return entry.get("result")
        return None


idempotency_tracker = IdempotencyTracker()


# --- 7. Dead-Letter Queue (DLQ) ---

class DeadLetterQueue:
    """
    Captures unrecoverable tasks for audit logs and manual replay.
    """
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._queue: List[Dict[str, Any]] = []

    def enqueue(
        self,
        task_name: str,
        payload: Dict[str, Any],
        error: Exception,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        item = {
            "id": f"dlq_{int(time.time()*1000)}_{random.randint(1000, 9999)}",
            "task_name": task_name,
            "payload": payload,
            "error": str(error),
            "error_type": error.__class__.__name__,
            "retry_count": retry_count,
            "enqueued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        if len(self._queue) >= self.max_size:
            self._queue.pop(0)

        self._queue.append(item)
        logger.error(f"[DLQ] Pushed failed task '{task_name}' to Dead Letter Queue (ID: {item['id']}). Reason: {error}")

        if len(self._queue) % 10 == 0:
            trigger_alert(
                event_type="DLQ_THRESHOLD_WARNING",
                message=f"Dead Letter Queue size reached {len(self._queue)} items.",
                payload={"queue_size": len(self._queue)}
            )

        return item

    def get_items(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._queue[-limit:]

    def clear(self):
        self._queue.clear()


dead_letter_queue = DeadLetterQueue()
