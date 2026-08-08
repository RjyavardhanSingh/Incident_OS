from app.investigation.state import (
    all_steps_terminal,
    investigation_transition,
    step_claim_status,
    step_transition,
    next_retry_attempt,
    STEP_RETRYABLE,
    STEP_TERMINAL,
)


def test_step_transitions_pending():
    assert step_transition("PENDING", "RUNNING")
    assert step_transition("PENDING", "FAILED")
    assert not step_transition("PENDING", "COMPLETED")


def test_step_transitions_running():
    assert step_transition("RUNNING", "COMPLETED")
    assert step_transition("RUNNING", "FAILED")
    assert not step_transition("RUNNING", "PENDING")


def test_step_retry_does_not_skip_attempt():
    assert step_transition("FAILED", "PENDING")
    assert not step_transition("FAILED", "RUNNING")


def test_investigation_transitions():
    assert investigation_transition("CREATED", "COLLECTING")
    assert investigation_transition("COLLECTING", "ANALYZING")
    assert not investigation_transition("CREATED", "ANALYZING")
    assert not investigation_transition("READY", "COLLECTING")


def test_claim_status_terminal():
    assert step_claim_status(["COMPLETED"]) == STEP_TERMINAL
    assert step_claim_status(["FAILED"]) == STEP_TERMINAL
    assert step_claim_status(["PENDING"]) == STEP_RETRYABLE
    assert step_claim_status(["RUNNING"]) == STEP_RETRYABLE


def test_all_steps_terminal():
    assert all_steps_terminal(["COMPLETED", "COMPLETED", "FAILED"])
    assert not all_steps_terminal(["COMPLETED", "RUNNING"])
    assert not all_steps_terminal([])


def test_next_retry_attempt():
    assert next_retry_attempt(1) == 2
