"""EmbeddingProvider contract.

Documented semantics under test:
- ``embed`` returns exactly one vector per input, aligned with input order.
- All vectors share one dimension; values are floats.
- Both ``kind`` values ("document", "query") are accepted.
- DETERMINISM: the port docs promise reproducible embeddings for a given
  model — the same input twice must yield the same vectors (this is what keeps
  semantic matching auditable).
"""

from __future__ import annotations

from typing import Any

import pytest

from etki_api.conformance.base import TURKISH_PROBE, PortContract


class EmbeddingProviderContract(PortContract):
    @pytest.mark.asyncio
    async def test_output_aligned_and_uniform(self, provider: Any) -> None:
        texts = ["ödeme entegrasyonu", TURKISH_PROBE, "csv export"]
        vectors = await provider.embed(texts, kind="document")
        assert len(vectors) == len(texts)
        dims = {len(v) for v in vectors}
        assert len(dims) == 1 and dims != {0}, "tüm vektörler aynı (sıfır olmayan) boyutta olmalı"
        assert all(isinstance(x, float) for v in vectors for x in v)

    @pytest.mark.asyncio
    async def test_query_kind_accepted(self, provider: Any) -> None:
        vectors = await provider.embed(["kapsamda mı?"], kind="query")
        assert len(vectors) == 1

    @pytest.mark.asyncio
    async def test_deterministic_for_same_input(self, provider: Any) -> None:
        first = await provider.embed(["aynı girdi"], kind="document")
        second = await provider.embed(["aynı girdi"], kind="document")
        assert first == second
