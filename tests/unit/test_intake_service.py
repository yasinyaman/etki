"""Intake polling cycle: request-id determinism, cursor store, dedup, ordering,
per-project isolation."""

import asyncio

from etki.adapters.fakes.code_repo import FakeCodeRepositoryProvider
from etki.adapters.fakes.document import FakeDocumentSourceProvider
from etki.adapters.fakes.intake import FakeRequestIntakeProvider
from etki.adapters.fakes.seed import SEED_BASELINE
from etki.adapters.fakes.work_item import FakeWorkItemProvider
from etki.api.context import AdapterHealth, AppContext
from etki.config import Settings
from etki.core.enums import PmoDecision
from etki.engine.triage import TriageEngine
from etki.hitl.service import ApprovalService
from etki.intake import cursors
from etki.intake.respond import DecisionResponder
from etki.intake.service import IntakeBinding, build_request_id, run_intake_cycle
from etki.persistence.memory_repo import InMemoryCaseFileRepository

from etki_api.models import IncomingRequest

# --- build_request_id --------------------------------------------------------


def test_request_id_is_deterministic():
    item = IncomingRequest(external_id="PROJ-1", title="x")
    a = build_request_id("demo", "jira", item)
    b = build_request_id("demo", "jira", item)
    assert a == b == "REQ-demo-jira-PROJ-1"


def test_request_id_sanitizes_and_disambiguates_unsafe_keys():
    safe = build_request_id("demo", "jira", IncomingRequest(external_id="a/b#c", title="x"))
    assert safe.startswith("REQ-demo-jira-a-b-c-")  # unsafe chars → hash suffix
    # Distinct raw ids that sanitize to the same prefix stay distinct.
    other = build_request_id("demo", "jira", IncomingRequest(external_id="a b c", title="x"))
    assert safe != other


# --- cursors -----------------------------------------------------------------


def test_cursor_roundtrip(tmp_path):
    path = tmp_path / "cursors.json"
    assert cursors.get_cursor("demo", "jira", path) is None
    cursors.save_cursor("demo", "jira", "42", path)
    assert cursors.get_cursor("demo", "jira", path) == "42"


def test_corrupt_cursor_file_degrades_to_empty(tmp_path):
    path = tmp_path / "cursors.json"
    path.write_text("{ not json", encoding="utf-8")
    assert cursors.load(path) == {}


def test_save_cursor_ignores_none(tmp_path):
    path = tmp_path / "cursors.json"
    cursors.save_cursor("demo", "jira", None, path)
    assert not path.exists()


# --- cycle helpers -----------------------------------------------------------


def _engine() -> TriageEngine:
    return TriageEngine(
        FakeWorkItemProvider(),
        FakeCodeRepositoryProvider(),
        FakeDocumentSourceProvider(),
        SEED_BASELINE.model_copy(deep=True),
        index_freshness="2026-06-21",
    )


def _ctx(repo, engines, responder, intake) -> AppContext:
    return AppContext(
        engines=engines,
        consumed={pid: {} for pid in engines},
        projects=[{"id": pid, "name": pid} for pid in engines],
        repo=repo,
        approval=ApprovalService(repo, on_decided=responder.on_decision),
        default_project=next(iter(engines)),
        user_store=None,  # not used by the cycle
        responder=responder,
        intake=intake,
        adapter_health={pid: [AdapterHealth("request_intake", "fake")] for pid in engines},
    )


def test_cycle_creates_pending_cases_with_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(cursors, "CURSOR_FILE", tmp_path / "c.json")
    repo = InMemoryCaseFileRepository()
    responder = DecisionResponder(repo)
    intake = {
        "demo": IntakeBinding("fake", FakeRequestIntakeProvider(page_size=10), "on_decision", "tr")
    }
    ctx = _ctx(repo, {"demo": _engine()}, responder, intake)

    created = asyncio.run(run_intake_cycle(ctx, Settings()))
    assert created == 3  # all seed items in one page
    cases = repo.list_cases("demo")
    assert len(cases) == 3
    for c in cases:
        assert c.status == PmoDecision.PENDING
        assert c.source_ref is not None and c.source_ref.source == "fake"
        assert c.pre_analysis  # deterministic pre-analysis attached
    # TRIAGED audit written for each.
    assert all(repo.list_audit(c.request_id)[0].action == "TRIAGED" for c in cases)


def test_cycle_dedups_on_second_run(tmp_path, monkeypatch):
    monkeypatch.setattr(cursors, "CURSOR_FILE", tmp_path / "c.json")
    repo = InMemoryCaseFileRepository()
    responder = DecisionResponder(repo)
    # page_size 10 → the first run drains everything; the cursor advances past the end.
    intake = {
        "demo": IntakeBinding("fake", FakeRequestIntakeProvider(page_size=10), "on_decision", "tr")
    }
    ctx = _ctx(repo, {"demo": _engine()}, responder, intake)
    settings = Settings()

    assert asyncio.run(run_intake_cycle(ctx, settings)) == 3
    # Reset the cursor so the SAME items are re-served → dedup must catch them.
    cursors.save_cursor("demo", "fake", "0", tmp_path / "c.json")
    assert asyncio.run(run_intake_cycle(ctx, settings)) == 0
    assert len(repo.list_cases("demo")) == 3


def test_cursor_not_advanced_when_triage_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(cursors, "CURSOR_FILE", tmp_path / "c.json")
    repo = InMemoryCaseFileRepository()
    responder = DecisionResponder(repo)
    engine = _engine()

    # Fail on the SECOND triage; the first case is recorded, the cursor stays put.
    calls = {"n": 0}
    real_triage = engine.triage

    async def flaky(text, *, request_id):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return await real_triage(text, request_id=request_id)

    engine.triage = flaky  # type: ignore[method-assign]
    intake = {
        "demo": IntakeBinding("fake", FakeRequestIntakeProvider(page_size=10), "on_decision", "tr")
    }
    ctx = _ctx(repo, {"demo": engine}, responder, intake)

    asyncio.run(run_intake_cycle(ctx, Settings()))
    assert cursors.get_cursor("demo", "fake", tmp_path / "c.json") is None  # not advanced
    assert len(repo.list_cases("demo")) == 1  # only the first item recorded
    # A degraded health mark is recorded for the project.
    assert any(h.state == "degraded" for h in ctx.adapter_health["demo"])


def test_one_project_failure_does_not_stop_others(tmp_path, monkeypatch):
    monkeypatch.setattr(cursors, "CURSOR_FILE", tmp_path / "c.json")
    repo = InMemoryCaseFileRepository()
    responder = DecisionResponder(repo)

    class _Boom(FakeRequestIntakeProvider):
        async def fetch_new(self, *, cursor=None, limit=20):
            raise RuntimeError("kaynak patladı")

    intake = {
        "a": IntakeBinding("fake", _Boom(), "on_decision", "tr"),
        "b": IntakeBinding(
            "fake", FakeRequestIntakeProvider(page_size=10), "on_decision", "tr"
        ),
    }
    ctx = _ctx(repo, {"a": _engine(), "b": _engine()}, responder, intake)

    created = asyncio.run(run_intake_cycle(ctx, Settings()))
    assert created == 3  # project b fully processed
    assert repo.list_cases("a") == []
    assert len(repo.list_cases("b")) == 3
    assert any(h.state == "degraded" for h in ctx.adapter_health["a"])
    assert all(h.state == "ok" for h in ctx.adapter_health["b"])
