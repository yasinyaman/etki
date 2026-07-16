"""End-to-end intake gate: fake tracker → triage → PENDING case → PMO decision
→ write-back, all through the real AppContext/ApprovalService wiring.

Uses the sync decide() path (asyncio.run inside the responder) so posting is
deterministic — no fire-and-forget timing."""

import asyncio

from etki.adapters.fakes.code_repo import FakeCodeRepositoryProvider
from etki.adapters.fakes.document import FakeDocumentSourceProvider
from etki.adapters.fakes.intake import FakeRequestIntakeProvider, FakeResponseChannel
from etki.adapters.fakes.seed import SEED_BASELINE
from etki.adapters.fakes.work_item import FakeWorkItemProvider
from etki.api.context import AdapterHealth, AppContext
from etki.config import Settings
from etki.core.enums import PmoDecision
from etki.engine.triage import TriageEngine
from etki.hitl.service import ApprovalService
from etki.intake import cursors
from etki.intake.respond import DecisionResponder, ResponderBinding
from etki.intake.service import IntakeBinding, run_intake_cycle
from etki.persistence.memory_repo import InMemoryCaseFileRepository


def _build(mode: str, channel: FakeResponseChannel, tmp_path, monkeypatch):
    monkeypatch.setattr(cursors, "CURSOR_FILE", tmp_path / "c.json")
    engine = TriageEngine(
        FakeWorkItemProvider(),
        FakeCodeRepositoryProvider(),
        FakeDocumentSourceProvider(),
        SEED_BASELINE.model_copy(deep=True),
        index_freshness="2026-06-21",
    )
    repo = InMemoryCaseFileRepository()
    responder = DecisionResponder(repo)
    responder.bindings["demo"] = ResponderBinding("fake", channel, mode, "tr")
    approval = ApprovalService(repo, on_decided=responder.on_decision)
    ctx = AppContext(
        engines={"demo": engine},
        consumed={"demo": {}},
        projects=[{"id": "demo", "name": "demo"}],
        repo=repo,
        approval=approval,
        default_project="demo",
        user_store=None,
        responder=responder,
        intake={"demo": IntakeBinding("fake", FakeRequestIntakeProvider(page_size=10), mode, "tr")},
        adapter_health={"demo": [AdapterHealth("request_intake", "fake")]},
    )
    return ctx, repo, channel


def test_on_decision_flow_posts_after_pmo_decides(tmp_path, monkeypatch):
    ctx, repo, channel = _build("on_decision", FakeResponseChannel(), tmp_path, monkeypatch)

    created = asyncio.run(run_intake_cycle(ctx, Settings()))
    assert created == 3
    # on_decision mode: nothing posted during intake.
    assert channel.posted == []

    pending = [c for c in repo.list_cases("demo") if c.status == PmoDecision.PENDING]
    assert len(pending) == 3
    target = pending[0]
    ctx.approval.decide(
        target.request_id, 0, PmoDecision.APPROVE, actor="pmo",
        current_baseline=ctx.engines["demo"].baseline,
    )
    # Exactly one decision-kind post for the decided case.
    assert len(channel.posted) == 1
    assert channel.posted[0].kind == "decision"
    assert channel.posted[0].external_id == target.source_ref.external_id


def test_both_mode_posts_triage_then_decision(tmp_path, monkeypatch):
    ctx, repo, channel = _build("both", FakeResponseChannel(), tmp_path, monkeypatch)

    asyncio.run(run_intake_cycle(ctx, Settings()))
    # both mode: a triage recommendation per created case.
    assert len(channel.posted) == 3
    assert {p.kind for p in channel.posted} == {"triage"}

    case = repo.list_cases("demo")[0]
    ctx.approval.decide(
        case.request_id, 0, PmoDecision.APPROVE, actor="pmo",
        current_baseline=ctx.engines["demo"].baseline,
    )
    kinds = [p.kind for p in channel.posted if p.external_id == case.source_ref.external_id]
    assert "triage" in kinds and "decision" in kinds  # distinct triggers
    triggers = {
        e.detail["trigger"]
        for e in repo.list_audit(case.request_id) if e.action == "RESPONSE_POSTED"
    }
    assert triggers == {"triage", "decision"}


def test_channel_failure_never_blocks_approval(tmp_path, monkeypatch):
    ctx, repo, channel = _build(
        "on_decision", FakeResponseChannel(fail=True), tmp_path, monkeypatch
    )
    asyncio.run(run_intake_cycle(ctx, Settings()))
    case = repo.list_cases("demo")[0]

    result = ctx.approval.decide(
        case.request_id, 0, PmoDecision.APPROVE, actor="pmo",
        current_baseline=ctx.engines["demo"].baseline,
    )
    assert result.case.status in (PmoDecision.APPROVE, PmoDecision.CONVERT_TO_CR)
    assert channel.posted == []  # the failed post recorded nothing
    posted = [e for e in repo.list_audit(case.request_id) if e.action == "RESPONSE_POSTED"]
    assert len(posted) == 1 and posted[0].detail["ok"] is False


def test_manual_case_without_source_ref_never_posts(tmp_path, monkeypatch):
    ctx, repo, channel = _build("on_decision", FakeResponseChannel(), tmp_path, monkeypatch)
    # A hand-entered (non-intake) triage: no source_ref.
    case = asyncio.run(
        ctx.engines["demo"].triage("El ile girilen bir talep", request_id="REQ-MANUAL")
    )
    case.project_id = "demo"
    ctx.approval.record_triage(case)
    ctx.approval.decide(
        "REQ-MANUAL", 0, PmoDecision.APPROVE, actor="pmo",
        current_baseline=ctx.engines["demo"].baseline,
    )
    assert channel.posted == []
    assert [e for e in repo.list_audit("REQ-MANUAL") if e.action == "RESPONSE_POSTED"] == []
