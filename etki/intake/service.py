"""The intake polling cycle: pull new requests → triage → PENDING case.

One cycle per tick (or per `python -m etki.intake` run). Per-project isolation:
one project's failure degrades ITS adapter health and the loop continues.
Idempotency is a deterministic ``request_id`` (the case PK) + a ``get_case``
short-circuit — no dedup table. The cursor advances only after a project's whole
batch is recorded, so a mid-batch failure just re-polls (dedup absorbs it).
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from etki import process_log
from etki.config import Settings
from etki.core.models import IncomingRequest, SourceRef
from etki.core.ports import RequestIntakeProvider
from etki.i18n import set_locale
from etki.intake import cursors

if TYPE_CHECKING:
    from etki.api.context import AppContext

logger = logging.getLogger(__name__)

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


@dataclass
class IntakeBinding:
    adapter: str
    provider: RequestIntakeProvider
    mode: str  # on_decision | on_triage | both
    language: str


def build_request_id(project_id: str, adapter: str, item: IncomingRequest) -> str:
    """Deterministic, filesystem/URL-safe case id. When sanitization changes the
    external id (unsafe chars) a short hash suffix keeps distinct ids distinct."""
    raw = item.external_id
    safe = _SAFE.sub("-", raw)[:40]
    if safe != raw:
        safe = f"{safe}-{hashlib.sha1(raw.encode()).hexdigest()[:6]}"
    return f"REQ-{project_id}-{adapter}-{safe}"


async def run_intake_cycle(ctx: AppContext, settings: Settings) -> int:
    """Polls every configured project once. Returns the number of NEW cases
    created across all projects."""
    # Late import avoids a module-level api↔intake cycle and keeps the deterministic
    # pre-analysis (pure) as the single source of that text.
    from etki.api.web import _deterministic_pre_analysis

    total = 0
    for pid, binding in ctx.intake.items():
        try:
            cursor = cursors.get_cursor(pid, binding.adapter)
            batch = await binding.provider.fetch_new(
                cursor=cursor, limit=settings.intake_batch_limit
            )
            for item in batch.items:
                request_id = build_request_id(pid, binding.adapter, item)
                if ctx.repo.get_case(request_id) is not None:
                    continue  # dedup — already triaged in a previous cycle
                text = f"{item.title}\n\n{item.description}".strip()
                if not text:
                    continue
                case = await ctx.engines[pid].triage(text, request_id=request_id)
                case.project_id = pid
                case.source_ref = SourceRef(
                    source=binding.adapter,
                    external_id=item.external_id,
                    key=item.key,
                    url=item.url,
                    reporter=item.reporter,
                )
                try:
                    set_locale(binding.language)
                    case.pre_analysis = _deterministic_pre_analysis(case)
                except Exception:  # noqa: BLE001 — pre-analysis is optional
                    logger.warning("ön analiz üretilemedi: %s", request_id, exc_info=True)
                ctx.approval.record_triage(case)
                process_log.log_event(
                    "intake",
                    pid,
                    {"request_id": request_id, "key": item.key, "adapter": binding.adapter},
                )
                if binding.mode in ("on_triage", "both") and ctx.responder is not None:
                    # Failure never stops the loop (respond_now swallows + audits).
                    await ctx.responder.respond_now(case, kind="triage")
                total += 1
            # Whole batch recorded → it is safe to advance the cursor.
            cursors.save_cursor(pid, binding.adapter, batch.cursor)
        except Exception as exc:  # noqa: BLE001 — isolate one project's failure
            ctx._set_health(pid, "request_intake", "degraded", f"{type(exc).__name__}: {exc}")
            logger.exception("[%s] talep alma turu başarısız", pid)
            continue
    return total
