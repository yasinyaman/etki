"""RerankProvider contract.

Documented semantics under test: ``rerank`` returns one float score per
document, aligned with the input order (raw logits — no normalization
assumed)."""

from __future__ import annotations

from typing import Any

import pytest

from etki_api.conformance.base import TURKISH_PROBE, PortContract


class RerankProviderContract(PortContract):
    @pytest.mark.asyncio
    async def test_scores_aligned_with_documents(self, provider: Any) -> None:
        docs = ["ödeme ekranı hata veriyor", TURKISH_PROBE, "csv export raporlama"]
        scores = await provider.rerank("raporlama csv", docs)
        assert len(scores) == len(docs)
        assert all(isinstance(s, float) for s in scores)
