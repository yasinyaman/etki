"""In-memory RequestIntakeProvider + ResponseChannel — test fixtures and the
offline conformance doubles for the two intake ports.

The cursor is a stringified item offset: deterministic paging, empty batch at
exhaustion. ``FakeResponseChannel`` records posts and, matching the conformance
contract, RAISES for an unknown target id (``"YOK-999"``) so the host's
best-effort/error-audit path is exercised.
"""

from __future__ import annotations

from etki.core.ports import Capabilities
from etki_api.models import IncomingRequest, IntakeBatch, OutboundResponse

# A small deterministic offline corpus (Turkish content — unicode round-trip).
SEED_INCOMING: list[IncomingRequest] = [
    IncomingRequest(
        external_id="10001",
        key="DEMO-1",
        title="Raporlama ekranına CSV dışa aktarım eklensin",
        description="Kullanıcılar rapor tablosunu CSV olarak indirebilmeli.",
        reporter="ayse",
        url="https://tracker.example/browse/DEMO-1",
    ),
    IncomingRequest(
        external_id="10002",
        key="DEMO-2",
        title="Ödeme ekranında kripto para desteği",
        description="Bitcoin ile ödeme alınabilsin mi?",
        reporter="mehmet",
        url="https://tracker.example/browse/DEMO-2",
    ),
    IncomingRequest(
        external_id="10003",
        key="DEMO-3",
        title="Giriş sayfası logosu güncellensin",
        description="Yeni marka logosu yüklenecek.",
        reporter="zeynep",
        url="https://tracker.example/browse/DEMO-3",
    ),
]


class FakeRequestIntakeProvider:
    def __init__(
        self, items: list[IncomingRequest] | None = None, page_size: int = 2
    ) -> None:
        self._items = list(items) if items is not None else list(SEED_INCOMING)
        self._page_size = max(1, page_size)

    async def fetch_new(
        self, *, cursor: str | None = None, limit: int = 20
    ) -> IntakeBatch:
        offset = int(cursor) if cursor and cursor.isdigit() else 0
        page = self._items[offset : offset + min(limit, self._page_size)]
        next_cursor = str(offset + len(page)) if page else cursor
        return IntakeBatch(items=page, cursor=next_cursor)

    def capabilities(self) -> Capabilities:
        return Capabilities(supports_webhooks=False, supports_realtime=False)


class FakeResponseChannel:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.posted: list[OutboundResponse] = []

    async def post_response(self, response: OutboundResponse) -> None:
        if response.external_id == "YOK-999":
            raise KeyError(f"hedef bulunamadı: {response.external_id}")
        if self.fail:
            raise RuntimeError("fake kanal hatası")
        self.posted.append(response)

    def capabilities(self) -> Capabilities:
        return Capabilities(supports_webhooks=False, supports_realtime=False)
