"""One-shot intake CLI: `python -m etki.intake`.

Polls every configured project once and triages new requests into PENDING
cases. The cron-friendly alternative to the in-app `ETKI_INTAKE_POLL_MINUTES`
loop (same `run_intake_cycle`).
"""

from __future__ import annotations

import asyncio
import logging

from etki.api.context import get_context
from etki.config import Settings
from etki.intake.service import run_intake_cycle


async def run() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    ctx = get_context()
    if not ctx.intake:
        print("Talep alma yapılandırılmış proje yok (connectors.request_intake).")
        return
    created = await run_intake_cycle(ctx, settings)
    print(f"Talep alma turu tamam: {created} yeni vaka oluşturuldu ({len(ctx.intake)} proje).")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
