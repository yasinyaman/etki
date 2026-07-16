"""UI-writable plugin state — ONLY the enable/disable toggle.

Deliberately the single thing the UI may change about plugins: disabling an
already-installed plugin is safe to expose (it can't become an install
vector); everything else (policy, install, remove) is operator/CLI-only.
Stored in `.etki/plugins.json`, read by `PluginRegistry.load()`."""

from __future__ import annotations

import json
from pathlib import Path

STATE_FILE = Path(".etki/plugins.json")


def load_disabled(path: str | Path = STATE_FILE) -> set[str]:
    p = Path(path)
    if not p.exists():
        return set()
    try:
        return set(json.loads(p.read_text(encoding="utf-8")).get("disabled", []))
    except Exception:  # noqa: BLE001 — a corrupt state file must not kill startup
        return set()


def set_disabled(name: str, disabled: bool, path: str | Path = STATE_FILE) -> set[str]:
    p = Path(path)
    current = load_disabled(p)
    if disabled:
        current.add(name)
    else:
        current.discard(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"disabled": sorted(current)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return current
