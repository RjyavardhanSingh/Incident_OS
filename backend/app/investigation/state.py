"""Pure investigation/step state-transition logic.

This module is intentionally free of I/O so it can be unit-tested and shared
by the API orchestrator and the worker pool.
"""
from app.models.investigation import (
    INVESTIGATION_STATUS_ANALYZING,
    INVESTIGATION_STATUS_COLLECTING,
    INVESTIGATION_STATUS_CREATED,
    INVESTIGATION_STATUS_FAILED,
    STEP_STATUS_COMPLETED,
    STEP_STATUS_FAILED,
    STEP_STATUS_PENDING,
    STEP_STATUS_RUNNING,
)

STEP_TRANSITIONS: dict[str, set[str]] = {
    STEP_STATUS_PENDING: {STEP_STATUS_RUNNING, STEP_STATUS_FAILED},
    STEP_STATUS_RUNNING: {STEP_STATUS_COMPLETED, STEP_STATUS_FAILED},
    STEP_STATUS_FAILED: {STEP_STATUS_PENDING},
}

INVESTIGATION_TRANSITIONS: dict[str, set[str]] = {
    INVESTIGATION_STATUS_CREATED: {INVESTIGATION_STATUS_COLLECTING},
    INVESTIGATION_STATUS_COLLECTING: {INVESTIGATION_STATUS_ANALYZING},
    INVESTIGATION_STATUS_ANALYZING: {INVESTIGATION_STATUS_FAILED},
    INVESTIGATION_STATUS_FAILED: set(),
}

TERMINAL_STEP_STATUSES = {STEP_STATUS_COMPLETED, STEP_STATUS_FAILED}
STEP_TERMINAL = "terminal"
STEP_RETRYABLE = "retryable"


def step_transition(current: str, target: str) -> bool:
    """Return True when the step state transition is legal."""
    return target in STEP_TRANSITIONS.get(current, set())


def investigation_transition(current: str, target: str) -> bool:
    """Return True when the investigation state transition is legal."""
    return target in INVESTIGATION_TRANSITIONS.get(current, set())


def step_claim_status(statuses: list[str]) -> str:
    """Classify a step given its current status for claim/retry handling.

    - STEP_TERMINAL: already COMPLETED/FAILED, no work should run.
    - STEP_RETRYABLE: FAILED and eligible for a retry.
    """
    if set(statuses) & {STEP_STATUS_COMPLETED, STEP_STATUS_FAILED}:
        return STEP_TERMINAL
    return STEP_RETRYABLE


def all_steps_terminal(step_statuses: list[str]) -> bool:
    """True when every step reached a terminal state (COMPLETED or FAILED)."""
    return bool(step_statuses) and all(s in TERMINAL_STEP_STATUSES for s in step_statuses)


def next_retry_attempt(attempt: int) -> int:
    return attempt + 1
