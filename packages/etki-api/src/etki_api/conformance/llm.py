"""LLMClient contract.

Documented semantics under test: ``complete_json`` returns a ``dict`` (the
engine's fallback logic relies on the type, not the content)."""

from __future__ import annotations

from typing import Any

import pytest

from etki_api.conformance.base import PortContract


class LLMClientContract(PortContract):
    system_prompt = "You are a JSON API. Answer with a single JSON object."
    user_prompt = 'Return {"ok": true}.'

    @pytest.mark.asyncio
    async def test_complete_json_returns_a_dict(self, provider: Any) -> None:
        out = await provider.complete_json(system=self.system_prompt, user=self.user_prompt)
        assert isinstance(out, dict)
