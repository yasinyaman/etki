import pytest
from etki.core.enums import Polarity
from etki.core.models import BestMatch, CaseFile, EffortEstimate, Risk, ScopeItem, TriageDecision
from pydantic import ValidationError


def test_effort_estimate_rejects_inverted_range():
    # Architecture invariant: an estimate must always be a valid range (low <= high).
    with pytest.raises(ValidationError):
        EffortEstimate(low=10, high=5)


def test_effort_estimate_allows_valid_range():
    est = EffortEstimate(low=5, high=10, basis="test")
    assert est.low <= est.high


def test_scope_item_defaults_to_included():
    item = ScopeItem(id="X", contract_id="C", description="bir madde")
    assert item.polarity is Polarity.INCLUDED


def test_polarity_has_excluded():
    assert Polarity.EXCLUDED == "EXCLUDED"


def test_risk_accepts_only_canonical_turkish_literals():
    assert Risk(probability="yüksek", impact="orta").probability == "yüksek"
    with pytest.raises(ValidationError):
        Risk(probability="high")
    with pytest.raises(ValidationError):
        Risk(impact="düsük")  # ascii-typed variant is NOT canonical


def test_confidence_and_similarity_bounds():
    est = EffortEstimate(low=1, high=2)
    TriageDecision(request_id="R", decision="IN_SCOPE", confidence=1.0, effort_estimate=est)
    with pytest.raises(ValidationError):
        TriageDecision(request_id="R", decision="IN_SCOPE", confidence=1.2, effort_estimate=est)
    with pytest.raises(ValidationError):
        TriageDecision(request_id="R", decision="IN_SCOPE", confidence=-0.1, effort_estimate=est)
    assert BestMatch(similarity=-0.4).similarity == -0.4  # cosine floor stays open
    with pytest.raises(ValidationError):
        BestMatch(similarity=1.5)


def test_old_persisted_payload_still_loads():
    """Backward-compat smoke: a pre-plugin, pre-UTC, money-era payload dict
    (naive ChatTurn.at, no plugin_set key, money string in cr_draft.cost)
    must keep validating — old DB rows are frozen history."""
    payload = {
        "request_id": "REQ-old-1",
        "raw_request": "Rapor ekranına filtre eklensin",
        "status": "APPROVE",
        "chat_turns": [{"question": "soru", "answer": "cevap", "at": "2026-06-01T10:00:00"}],
        "decisions": [
            {
                "request_id": "REQ-old-1",
                "decision": "CR_CANDIDATE",
                "confidence": 0.75,
                "effort_estimate": {"low": 12.0, "high": 18.0, "unit": "hour", "basis": "eski"},
                "risk": {"probability": "düşük", "impact": "orta", "level": "MEDIUM"},
                "cr_draft": {"impact_analysis": "eski analiz", "cost": "36.000 TL"},
                "decided_at": "2026-06-01T09:00:00+00:00",
            }
        ],
    }
    case = CaseFile.model_validate(payload)
    assert case.decisions[0].plugin_set == []
    assert case.decisions[0].cr_draft.cost == "36.000 TL"
    assert case.chat_turns[0].at.tzinfo is None  # frozen naive history loads as-is
