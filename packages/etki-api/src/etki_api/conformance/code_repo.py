"""CodeRepositoryProvider contract.

Documented semantics under test:
- ``list_modules`` returns ``CodeModule`` items with UNIQUE ids.
- ``get_impacted`` accepts ``None`` and unknown hints and returns a list
  (empty is fine) — never an exception.
- Impacted modules are a subset of the listed graph (by id).
"""

from __future__ import annotations

from typing import Any

import pytest

from etki_api.conformance.base import PortContract
from etki_api.models import CodeModule
from etki_api.ports import Capabilities


class CodeRepositoryProviderContract(PortContract):
    known_module_hint: str | None = None

    @pytest.mark.asyncio
    async def test_list_modules_normalized_unique_ids(self, provider: Any) -> None:
        modules = await provider.list_modules()
        assert isinstance(modules, list)
        for m in modules:
            assert isinstance(m, CodeModule)
            assert m.id
        ids = [m.id for m in modules]
        assert len(ids) == len(set(ids)), "modül id'leri benzersiz olmalı"

    @pytest.mark.asyncio
    async def test_none_hint_returns_list_not_error(self, provider: Any) -> None:
        assert isinstance(await provider.get_impacted(None), list)

    @pytest.mark.asyncio
    async def test_unknown_hint_returns_list_not_error(self, provider: Any) -> None:
        assert isinstance(await provider.get_impacted("zxqv-yok-boyle-modul"), list)

    @pytest.mark.asyncio
    async def test_impacted_is_subset_of_the_graph(self, provider: Any) -> None:
        if self.known_module_hint is None:
            pytest.skip("subclass declares no known_module_hint")
        listed = {m.id for m in await provider.list_modules()}
        impacted = await provider.get_impacted(self.known_module_hint)
        assert impacted, "bilinen ipucu en az bir modül döndürmeli"
        assert {m.id for m in impacted} <= listed

    def test_capabilities_declaration_is_stable(self, provider: Any) -> None:
        caps = provider.capabilities()
        assert isinstance(caps, Capabilities)
        assert provider.capabilities() == caps
