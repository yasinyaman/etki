"""Decision/triage write-back: localized compose, best-effort posting, dedup
guard, and the copilot mode filters."""

import asyncio

from etki.adapters.fakes.code_repo import FakeCodeRepositoryProvider
from etki.adapters.fakes.document import FakeDocumentSourceProvider
from etki.adapters.fakes.intake import FakeResponseChannel
from etki.adapters.fakes.seed import SEED_BASELINE
from etki.adapters.fakes.work_item import FakeWorkItemProvider
from etki.core.enums import PmoDecision
from etki.core.models import SourceRef
from etki.engine.triage import TriageEngine
from etki.hitl.service import ApprovalService
from etki.intake.respond import DecisionResponder, ResponderBinding, compose_response
from etki.persistence.memory_repo import InMemoryCaseFileRepository


def _case(status=PmoDecision.PENDING):
    engine = TriageEngine(
        FakeWorkItemProvider(),
        FakeCodeRepositoryProvider(),
        FakeDocumentSourceProvider(),
        SEED_BASELINE.model_copy(deep=True),
        index_freshness="2026-06-21",
    )
    case = asyncio.run(
        engine.triage("Raporlama ekranına CSV dışa aktarım", request_id="REQ-1")
    )
    case.project_id = "demo"
    case.status = status
    case.source_ref = SourceRef(source="fake", external_id="10001", key="DEMO-1")
    return case


# --- compose -----------------------------------------------------------------


def test_compose_localizes_and_includes_effort():
    case = _case()
    tr = compose_response(case, kind="triage", language="tr")
    assert tr.external_id == "10001"
    assert "otomatik ön değerlendirme" in tr.text
    assert "tahmini efor" in tr.text  # effort range line
    assert "PMO onayındadır" in tr.text  # disclaimer
    en = compose_response(case, kind="triage", language="en")
    assert "automatic pre-assessment" in en.text
    assert "estimated effort" in en.text


def test_compose_decision_kind_carries_outcome():
    case = _case(status=PmoDecision.APPROVE)
    resp = compose_response(case, kind="decision", language="tr")
    assert "PMO kararı" in resp.text
    assert "onaylandı" in resp.text  # outcome_APPROVE
    assert resp.kind == "decision"


def test_case_link_only_with_public_base_url():
    case = _case()
    assert compose_response(case, kind="triage", language="tr").case_url is None
    with_link = compose_response(
        case, kind="triage", language="tr", public_base_url="https://etki.example.com/"
    )
    assert with_link.case_url == "https://etki.example.com/ui/casefiles/REQ-1"
    assert "https://etki.example.com/ui/casefiles/REQ-1" in with_link.text


# --- DecisionResponder -------------------------------------------------------


def _responder(repo, channel, mode="on_decision"):
    r = DecisionResponder(repo)
    r.bindings["demo"] = ResponderBinding("fake", channel, mode, "tr")
    return r


def test_on_decision_posts_once_and_audits():
    repo = InMemoryCaseFileRepository()
    case = _case(status=PmoDecision.APPROVE)
    repo.save_case(case)
    channel = FakeResponseChannel()
    responder = _responder(repo, channel)

    responder.on_decision(case)
    assert len(channel.posted) == 1
    assert channel.posted[0].kind == "decision"
    audit = [e for e in repo.list_audit("REQ-1") if e.action == "RESPONSE_POSTED"]
    assert len(audit) == 1 and audit[0].detail["ok"] is True
    # Dedup guard: a second call must not double-post.
    responder.on_decision(case)
    assert len(channel.posted) == 1


def test_channel_failure_is_recorded_not_raised():
    repo = InMemoryCaseFileRepository()
    case = _case(status=PmoDecision.APPROVE)
    repo.save_case(case)
    errors: list[tuple[str, str]] = []
    responder = DecisionResponder(repo, on_error=lambda pid, msg: errors.append((pid, msg)))
    responder.bindings["demo"] = ResponderBinding(
        "fake", FakeResponseChannel(fail=True), "on_decision", "tr"
    )

    responder.on_decision(case)  # must not raise
    audit = [e for e in repo.list_audit("REQ-1") if e.action == "RESPONSE_POSTED"]
    assert len(audit) == 1 and audit[0].detail["ok"] is False
    assert errors and errors[0][0] == "demo"


def test_decide_never_blocked_by_write_back_failure():
    repo = InMemoryCaseFileRepository()
    case = _case()
    repo.save_case(case)
    responder = _responder(repo, FakeResponseChannel(fail=True))
    approval = ApprovalService(repo, on_decided=responder.on_decision)

    result = approval.decide(
        "REQ-1", 0, PmoDecision.APPROVE, actor="pmo",
        current_baseline=SEED_BASELINE.model_copy(deep=True),
    )
    assert result.case.status in (PmoDecision.APPROVE, PmoDecision.CONVERT_TO_CR)  # decision landed
    audit = [e for e in repo.list_audit("REQ-1") if e.action == "RESPONSE_POSTED"]
    assert len(audit) == 1 and audit[0].detail["ok"] is False


def test_no_source_ref_means_no_post():
    repo = InMemoryCaseFileRepository()
    case = _case(status=PmoDecision.APPROVE)
    case.source_ref = None
    repo.save_case(case)
    channel = FakeResponseChannel()
    responder = _responder(repo, channel)
    responder.on_decision(case)
    assert channel.posted == []


def test_on_triage_mode_skips_the_decision_hook():
    repo = InMemoryCaseFileRepository()
    case = _case(status=PmoDecision.APPROVE)
    repo.save_case(case)
    channel = FakeResponseChannel()
    responder = _responder(repo, channel, mode="on_triage")
    responder.on_decision(case)  # on_triage → decision hook is a no-op
    assert channel.posted == []
