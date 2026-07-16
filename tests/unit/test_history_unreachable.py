"""U3.2 (plugin UI plan): an UNREACHABLE effort source is distinguishable in the
frozen evidence from a genuine zero-hit search — while decision, confidence,
effort and risk follow the exact same path (the failure flag is text-only)."""

from etki.adapters.fakes.code_repo import FakeCodeRepositoryProvider
from etki.adapters.fakes.document import FakeDocumentSourceProvider
from etki.adapters.fakes.seed import SEED_BASELINE
from etki.adapters.fakes.work_item import FakeWorkItemProvider
from etki.engine.triage import TriageEngine


class _UnreachableProvider(FakeWorkItemProvider):
    """Remote PM environment down: every similarity query raises."""

    async def find_similar(self, description: str, *, limit: int = 5):  # noqa: ANN201
        raise RuntimeError("bağlantı yok")


def _engine(provider: FakeWorkItemProvider) -> TriageEngine:
    return TriageEngine(
        provider,
        FakeCodeRepositoryProvider(),
        FakeDocumentSourceProvider(),
        SEED_BASELINE.model_copy(deep=True),
        index_freshness="2026-06-21",
    )


async def test_unreachable_source_changes_evidence_text_not_the_decision():
    text = "raporlama ekranına csv aktarımı eklensin"
    zero_hit = await _engine(FakeWorkItemProvider([])).triage(text, request_id="R-ZERO")
    unreachable = await _engine(_UnreachableProvider([])).triage(text, request_id="R-DOWN")

    assert zero_hit.decisions and len(zero_hit.decisions) == len(unreachable.decisions)
    for a, b in zip(zero_hit.decisions, unreachable.decisions, strict=True):
        # Byte-identical decision path (only the frozen wording may differ):
        assert a.decision == b.decision
        assert a.confidence == b.confidence
        assert a.effort_estimate == b.effort_estimate
        assert a.risk == b.risk

        # …but the evidence tells the two facts apart:
        assert any("ulaşılamadı" in n for n in b.evidence.assumptions)
        assert all("ulaşılamadı" not in n for n in a.evidence.assumptions)
        hist_a = a.evidence.source_coverage[-1]
        hist_b = b.evidence.source_coverage[-1]
        assert hist_a.covered is False and hist_b.covered is False
        assert hist_a.detail == "benzer iş yok"
        assert hist_b.detail == "kaynağa ulaşılamadı"
