"""Per-project, per-source polling cursors — a small JSON store under `.etki/`.

The cursor is OPAQUE (the adapter alone knows its meaning). It is a pure
optimization: losing it only re-polls already-seen requests, which the host's
deterministic-request-id dedup absorbs — so no atomic-0600/secret handling is
needed (there are no secrets here), just a plain atomic replace.

Deliberately NOT stored on `projects.yaml`: the UI project setter rewrites that
file wholesale and would clobber a cursor.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CURSOR_FILE = Path(".etki/intake-cursors.json")

# Shape: {project_id: {source_adapter: cursor}}
_Cursors = dict[str, dict[str, str]]


def load(path: Path | None = None) -> _Cursors:
    # Resolve CURSOR_FILE at call time (not as a default arg) so tests can
    # redirect the store by monkeypatching the module constant.
    path = path or CURSOR_FILE
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    # Keep only well-typed {str: {str: str}} entries; ignore anything corrupt.
    out: _Cursors = {}
    for pid, sources in data.items():
        if isinstance(sources, dict):
            out[str(pid)] = {
                str(k): str(v) for k, v in sources.items() if isinstance(v, str)
            }
    return out


def get_cursor(project_id: str, source: str, path: Path | None = None) -> str | None:
    return load(path).get(project_id, {}).get(source)


def save_cursor(
    project_id: str, source: str, cursor: str | None, path: Path | None = None
) -> None:
    if cursor is None:
        return
    path = path or CURSOR_FILE
    data = load(path)
    data.setdefault(project_id, {})[source] = cursor
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
