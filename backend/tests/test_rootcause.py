import uuid
from datetime import datetime, timezone

from app.models.correlation import (
    CANDIDATE_STATUS_ACCEPTED,
    CANDIDATE_STATUS_PENDING,
    CANDIDATE_STATUS_REJECTED,
    RootCauseCandidate,
)
from app.models.root_cause import (
    ROOT_CAUSE_SELECTION_FALLBACK,
    ROOT_CAUSE_SELECTION_VERIFIED,
    RootCause,
)
from app.rootcause.engine import _selection
from app.schemas.root_cause import RootCauseOut

NOW = datetime(2026, 8, 9, 15, 0, 0, tzinfo=timezone.utc)


def _candidate(rank, status=CANDIDATE_STATUS_PENDING, confidence=0.5):
    return RootCauseCandidate(
        rank=rank,
        status=status,
        confidence=confidence,
        root_cause_type="error_burst",
        title="Error burst on payments",
        summary="A burst of error logs during the incident window.",
        evidence_chain=[{"step": 1}],
        related_services=["payments"],
    )


def test_verified_mode_picks_highest_ranked_accepted():
    candidates = [
        _candidate(1, CANDIDATE_STATUS_ACCEPTED, 0.9),
        _candidate(2, CANDIDATE_STATUS_ACCEPTED, 0.8),
        _candidate(3, CANDIDATE_STATUS_PENDING, 0.7),
    ]
    mode, best, reasoning = _selection(candidates)
    assert mode == ROOT_CAUSE_SELECTION_VERIFIED
    assert best.rank == 1
    assert "passing" in reasoning.lower()


def test_verified_skips_higher_ranked_but_rejected():
    candidates = [
        _candidate(1, CANDIDATE_STATUS_REJECTED, 0.95),
        _candidate(2, CANDIDATE_STATUS_ACCEPTED, 0.85),
    ]
    mode, best, _ = _selection(candidates)
    assert mode == ROOT_CAUSE_SELECTION_VERIFIED
    assert best.rank == 2


def test_fallback_when_none_verified():
    candidates = [
        _candidate(1, CANDIDATE_STATUS_REJECTED, 0.9),
        _candidate(2, CANDIDATE_STATUS_PENDING, 0.8),
    ]
    mode, best, reasoning = _selection(candidates)
    assert mode == ROOT_CAUSE_SELECTION_FALLBACK
    assert best.rank == 1
    assert "unverified" in reasoning.lower()


def test_root_cause_schema_roundtrip():
    rc = RootCause(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        selection_mode=ROOT_CAUSE_SELECTION_VERIFIED,
        root_cause_type="error_burst",
        title="Error burst on payments",
        summary="A burst of error logs during the incident window.",
        confidence=0.9,
        evidence_chain=[{"step": 1}],
        related_services=["payments"],
        reasoning="Highest-ranked candidate with independent checks passing.",
        created_at=NOW,
    )
    out = RootCauseOut.model_validate(rc)
    assert out.selection_mode == ROOT_CAUSE_SELECTION_VERIFIED
    assert out.root_cause_type == "error_burst"
    assert out.confidence == 0.9
    assert out.related_services == ["payments"]
