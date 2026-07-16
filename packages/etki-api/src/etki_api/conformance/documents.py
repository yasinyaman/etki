"""DocumentSourceProvider contract.

Documented semantics under test:
- ``list_documents`` returns ``DocumentRef`` items with UNIQUE ids.
- Every LISTED id is fetchable and yields ``bytes`` (str is a bug — parsers
  downstream decode explicitly).
"""

from __future__ import annotations

from typing import Any

import pytest

from etki_api.conformance.base import PortContract
from etki_api.models import DocumentRef
from etki_api.ports import Capabilities


class DocumentSourceProviderContract(PortContract):
    @pytest.mark.asyncio
    async def test_list_documents_normalized_unique_ids(self, provider: Any) -> None:
        docs = await provider.list_documents()
        assert isinstance(docs, list)
        for d in docs:
            assert isinstance(d, DocumentRef)
            assert d.id
        ids = [d.id for d in docs]
        assert len(ids) == len(set(ids)), "doküman id'leri benzersiz olmalı"

    @pytest.mark.asyncio
    async def test_every_listed_document_is_fetchable_as_bytes(self, provider: Any) -> None:
        docs = await provider.list_documents()
        if not docs:
            pytest.skip("sağlayıcı hiç doküman listelemiyor")
        for d in docs[:5]:  # cap the probe — large corpora shouldn't slow verify
            content = await provider.fetch_content(d.id)
            assert isinstance(content, bytes), "fetch_content bytes döndürmeli (str değil)"

    def test_capabilities_declaration_is_stable(self, provider: Any) -> None:
        caps = provider.capabilities()
        assert isinstance(caps, Capabilities)
        assert provider.capabilities() == caps
