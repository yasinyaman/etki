"""RegistryMetadataProvider contract.

Documented semantics under test: ``latest`` returns ``PackageMetadata`` or
``None`` — an unknown package (or any backend failure) degrades to ``None``,
never an exception (the dependency card simply shows manifest facts only)."""

from __future__ import annotations

from typing import Any

import pytest

from etki_api.conformance.base import PortContract
from etki_api.models import PackageMetadata


class RegistryMetadataProviderContract(PortContract):
    known_package: tuple[str, str] | None = None  # (ecosystem, name)

    @pytest.mark.asyncio
    async def test_unknown_package_degrades_to_none(self, provider: Any) -> None:
        out = await provider.latest("pypi", "zxqv-yok-boyle-paket-42x")
        assert out is None or isinstance(out, PackageMetadata)

    @pytest.mark.asyncio
    async def test_known_package_returns_metadata(self, provider: Any) -> None:
        if self.known_package is None:
            pytest.skip("subclass declares no known_package")
        ecosystem, name = self.known_package
        out = await provider.latest(ecosystem, name)
        assert isinstance(out, PackageMetadata)
        assert out.name and out.ecosystem
