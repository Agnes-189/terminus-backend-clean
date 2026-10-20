import pytest
import time
from app.services.retry_utils import (
    CircuitBreaker,
    CircuitOpenException,
    IdempotencyTracker,
    DuplicateTransactionException,
    DeadLetterQueue,
    with_exponential_backoff
)


def test_circuit_breaker_trips_on_failures():
    cb = CircuitBreaker(name="test_cb", failure_threshold=2, recovery_timeout=10.0)

    @cb
    def failing_func():
        raise ValueError("Simulated downstream error")

    # First two calls trigger failures
    with pytest.raises(ValueError):
        failing_func()
    with pytest.raises(ValueError):
        failing_func()

    # Third call should fail fast with CircuitOpenException
    with pytest.raises(CircuitOpenException):
        failing_func()


def test_idempotency_tracker_prevents_duplicates():
    tracker = IdempotencyTracker(ttl_seconds=60)
    key = "tx_idempotency_key_001"

    tracker.record_start(key)
    assert tracker.is_processed(key) is True

    # Duplicate recording should raise error
    with pytest.raises(DuplicateTransactionException):
        tracker.record_start(key)

    tracker.record_success(key, result={"tx_hash": "0x123"})
    assert tracker.get_result(key) == {"tx_hash": "0x123"}


def test_dead_letter_queue():
    dlq = DeadLetterQueue(max_size=5)
    item = dlq.enqueue(
        task_name="sweep_assets",
        payload={"beneficiary_id": 12},
        error=RuntimeError("RPC Timeout"),
        retry_count=3
    )

    assert item["task_name"] == "sweep_assets"
    assert len(dlq.get_items()) == 1