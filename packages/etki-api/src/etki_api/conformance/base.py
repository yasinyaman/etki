"""Shared base for port contract classes."""

from __future__ import annotations

import pytest


class PortContract:
    """Subclass per port; the plugin author overrides the ``provider`` fixture
    with an OFFLINE instance of their adapter. Async tests carry an explicit
    ``@pytest.mark.asyncio`` so the suite works in third-party repos regardless
    of their ``asyncio_mode`` (auto or strict)."""

    @pytest.fixture
    def provider(self) -> object:
        raise NotImplementedError(
            "Conformance: override the `provider` fixture in your subclass and "
            "return an OFFLINE instance of your adapter (canned data / mock "
            "transport — the suite must run credential-free in CI)."
        )


# Turkish/unicode probe used across ports — adapters must survive non-ASCII text.
TURKISH_PROBE = "ödeme ekranında %10 aşım — çağrı ücreti İĞÜŞÖÇ"
NONSENSE_PROBE = "zxqv yokböylekelime 42x9q"
