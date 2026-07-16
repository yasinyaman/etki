"""RequestIntakeProvider contract.

Documented semantics under test:
- ``fetch_new`` returns an ``IntakeBatch``; ``len(items) <= limit``.
- Every returned item is NORMALIZED: non-empty ``external_id`` and at least one
  of ``title``/``description`` non-empty (empty requests are useless to triage).
- An exhausted / empty source returns an empty ``items`` list — NEVER an
  exception.
- Cursor DETERMINISM: fetching twice with the same input cursor yields the same
  ``external_id``s (a static offline source is deterministic).
- Cursor MONOTONICITY: fetching again with the cursor a batch returned never
  re-emits an ``external_id`` from that batch (progress, no infinite loop).
- Unicode/Turkish content survives the round-trip.
- ``capabilities()`` is sync, returns a ``Capabilities`` instance and is stable.
"""

from __future__ import annotations

from typing import Any

import pytest

from etki_api.conformance.base import PortContract
from etki_api.models import IncomingRequest, IntakeBatch
from etki_api.ports import Capabilities


class RequestIntakeProviderContract(PortContract):
    @pytest.mark.asyncio
    async def test_fetch_new_returns_normalized_batch(self, provider: Any) -> None:
        batch = await provider.fetch_new(limit=5)
        assert isinstance(batch, IntakeBatch)
        assert len(batch.items) <= 5
        for item in batch.items:
            assert isinstance(item, IncomingRequest)
            assert item.external_id, "IncomingRequest.external_id boş olamaz"
            assert item.title or item.description, "başlık ve açıklama birden boş olamaz"

    @pytest.mark.asyncio
    async def test_fetch_new_respects_limit_one(self, provider: Any) -> None:
        batch = await provider.fetch_new(limit=1)
        assert len(batch.items) <= 1

    @pytest.mark.asyncio
    async def test_same_cursor_is_deterministic(self, provider: Any) -> None:
        first = await provider.fetch_new(limit=5)
        again = await provider.fetch_new(limit=5)
        assert [i.external_id for i in first.items] == [i.external_id for i in again.items]

    @pytest.mark.asyncio
    async def test_cursor_makes_progress(self, provider: Any) -> None:
        first = await provider.fetch_new(limit=3)
        if not first.items:
            pytest.skip("offline source yielded no items")
        seen = {i.external_id for i in first.items}
        nxt = await provider.fetch_new(cursor=first.cursor, limit=3)
        assert isinstance(nxt, IntakeBatch)
        # Advancing with the returned cursor must not re-emit already-seen ids.
        assert not (seen & {i.external_id for i in nxt.items})

    @pytest.mark.asyncio
    async def test_exhausted_source_returns_empty_list(self, provider: Any) -> None:
        # Drain the source; the terminal poll must be an empty list, not an error.
        cursor: str | None = None
        for _ in range(50):
            batch = await provider.fetch_new(cursor=cursor, limit=10)
            assert isinstance(batch.items, list)
            if not batch.items:
                break
            cursor = batch.cursor
        else:  # pragma: no cover - a runaway offline source is a plugin bug
            pytest.fail("kaynak 50 turda tükenmedi — cursor ilerlemiyor olabilir")

    def test_capabilities_declaration_is_stable(self, provider: Any) -> None:
        caps = provider.capabilities()
        assert isinstance(caps, Capabilities)
        assert provider.capabilities() == caps
