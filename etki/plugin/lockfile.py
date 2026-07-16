"""`etki-plugins.lock` — the reproducibility record for installed plugins.

TOML (human-reviewable diffs, same format family as the manifest; the wiki
philosophy: git-versionable). Read with stdlib tomllib, written with tomli-w.
`etki plugin sync` reinstalls EXACTLY this state on a new machine / at
container build time; entries are kept sorted by name so diffs stay stable.
"""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from pathlib import Path

import tomli_w
from pydantic import BaseModel, Field

from etki_api import SecurityCapabilities

LOCKFILE_NAME = "etki-plugins.lock"
SCHEMA_VERSION = 1


class LockedPlugin(BaseModel):
    """One installed plugin distribution, pinned for byte-identical reinstall."""

    name: str
    source: str  # "git" | "local" | "verified"
    url: str = ""  # git URL / marketplace artifact URL; "" for local
    path: str = ""  # local wheel path (source == "local")
    ref: str = ""  # the tag/commit AS REQUESTED (documentation; commit is what installs)
    commit: str = ""  # resolved FULL sha (source == "git")
    sha256: str = ""  # wheel hash (local/verified installs — mandatory there)
    api_compat: str = ""
    capabilities: SecurityCapabilities = Field(default_factory=SecurityCapabilities)
    installed_at: str = ""  # ISO timestamp
    verified: bool = False  # True only via the signed marketplace path (Faz 5)


class Lockfile(BaseModel):
    version: int = SCHEMA_VERSION
    plugins: list[LockedPlugin] = Field(default_factory=list)

    def upsert(self, entry: LockedPlugin) -> None:
        self.plugins = sorted(
            [p for p in self.plugins if p.name != entry.name] + [entry],
            key=lambda p: p.name,
        )

    def remove(self, name: str) -> bool:
        before = len(self.plugins)
        self.plugins = [p for p in self.plugins if p.name != name]
        return len(self.plugins) != before

    def get(self, name: str) -> LockedPlugin | None:
        return next((p for p in self.plugins if p.name == name), None)


def load_lockfile(path: str | Path = LOCKFILE_NAME) -> Lockfile:
    """Missing file → empty lockfile; unknown schema version → hard error
    (a newer tool wrote it — do not guess)."""
    p = Path(path)
    if not p.exists():
        return Lockfile()
    with p.open("rb") as fh:
        data = tomllib.load(fh)
    version = data.get("version")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"{p}: bilinmeyen lockfile şema versiyonu {version!r} "
            f"(bu araç {SCHEMA_VERSION} bekliyor)"
        )
    return Lockfile(
        version=version,
        plugins=[LockedPlugin.model_validate(e) for e in data.get("plugin", [])],
    )


def save_lockfile(lockfile: Lockfile, path: str | Path = LOCKFILE_NAME) -> None:
    payload = {
        "version": lockfile.version,
        "plugin": [
            p.model_dump(mode="json")
            for p in sorted(lockfile.plugins, key=lambda p: p.name)
        ],
    }
    Path(path).write_text(tomli_w.dumps(payload), encoding="utf-8")


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
