from datetime import UTC, datetime

from etki.core.enums import Decision, PmoDecision
from etki.core.models import (
    AuditEvent,
    Baseline,
    CaseFile,
    EffortEstimate,
    Override,
    TriageDecision,
)
from etki.kpi import calibration_suggestions, compute_kpis, effort_pool_status
from etki.persistence.memory_repo import InMemoryCaseFileRepository


def test_effort_pool_status_thresholds():
    assert "normal" in effort_pool_status(10, 100)["status"]
    assert "uyarı" in effort_pool_status(70, 100)["status"]
    assert "kritik" in effort_pool_status(90, 100)["status"]


def test_effort_pool_zero_pool_is_safe():
    assert effort_pool_status(5, 0)["ratio"] == 0.0


def test_calibration_suggestions_counts_transitions():
    overrides = [
        Override(case_id="c1", decision_index=0,
                 system_decision=Decision.GRAY_AREA, human_decision=Decision.IN_SCOPE),
        Override(case_id="c2", decision_index=0,
                 system_decision=Decision.GRAY_AREA, human_decision=Decision.IN_SCOPE),
    ]
    out = calibration_suggestions(overrides)
    assert out
    assert "GRAY_AREA" in out[0] and "IN_SCOPE" in out[0]
    assert out[0].startswith("2×")


def test_approval_speed_survives_mixed_naive_and_aware_timestamps():
    """Old audit rows (pre-UTC web.py) are naive; new ones aware. The metric
    must neither crash (TypeError on aware-naive subtraction) nor absorb the
    server's UTC offset — naive is treated as UTC."""
    repo = InMemoryCaseFileRepository()
    case = CaseFile(
        request_id="REQ-tz-1",
        raw_request="talep",
        status=PmoDecision.APPROVE,
        decisions=[
            TriageDecision(
                request_id="REQ-tz-1",
                decision=Decision.IN_SCOPE,
                effort_estimate=EffortEstimate(low=1, high=2),
            )
        ],
    )
    repo.save_case(case)
    repo.append_audit(AuditEvent(
        case_id="REQ-tz-1", seq=1, action="TRIAGED",
        at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
    ))
    # A naive PRE_ANALYSIS event appended after the decision (no status guard).
    repo.append_audit(AuditEvent(
        case_id="REQ-tz-1", seq=2, action="PRE_ANALYSIS",
        at=datetime(2026, 7, 1, 13, 0),
    ))
    kpis = compute_kpis(repo, Baseline(contract_id="C"), consumed_by_category={})
    assert kpis["avg_cr_approval_hours"] == 3.0
