"""ResponseChannel contract.

Documented semantics under test:
- ``post_response`` to a KNOWN target completes without error (Turkish/unicode
  text accepted).
- ``post_response`` to an UNKNOWN target RAISES — failures must surface to the
  host, never be silently swallowed by the adapter (the host is the only
  best-effort layer).
- ``capabilities()`` is sync, returns a ``Capabilities`` instance and is stable.

The subclass declares ``known_target_id`` (an id the offline double accepts);
``unknown_target_id`` defaults to a value the double must reject.
"""

from __future__ import annotations

from typing import Any

import pytest

from etki_api.conformance.base import TURKISH_PROBE, PortContract
from etki_api.models import OutboundResponse
from etki_api.ports import Capabilities


class ResponseChannelContract(PortContract):
    known_target_id: str = "OK-1"
    unknown_target_id: str = "YOK-999"

    @pytest.mark.asyncio
    async def test_post_to_known_target_succeeds(self, provider: Any) -> None:
        resp = OutboundResponse(external_id=self.known_target_id, text=TURKISH_PROBE)
        # Must not raise.
        assert await provider.post_response(resp) is None

    @pytest.mark.asyncio
    async def test_post_to_unknown_target_raises(self, provider: Any) -> None:
        resp = OutboundResponse(external_id=self.unknown_target_id, text="x")
        with pytest.raises(Exception):  # noqa: B017,PT011 — any surfaced error satisfies the contract
            await provider.post_response(resp)

    def test_capabilities_declaration_is_stable(self, provider: Any) -> None:
        caps = provider.capabilities()
        assert isinstance(caps, Capabilities)
        assert provider.capabilities() == caps
