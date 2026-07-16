"""Lockfile: round-trip, stable ordering, schema-version guard."""

import pytest
from etki.plugin.lockfile import (
    LockedPlugin,
    Lockfile,
    load_lockfile,
    save_lockfile,
)

from etki_api import SecurityCapabilities


def _entry(name: str, **kw) -> LockedPlugin:
    return LockedPlugin(name=name, source="git", url="https://x/y", commit="a" * 40, **kw)


def test_roundtrip_preserves_everything(tmp_path):
    path = tmp_path / "etki-plugins.lock"
    lock = Lockfile()
    lock.upsert(
        LockedPlugin(
            name="etki-plugin-acme",
            source="local",
            path="/opt/wheels/acme.whl",
            sha256="deadbeef",
            api_compat=">=0.1,<0.2",
            capabilities=SecurityCapabilities(network=True, endpoints=["acme.example.com"]),
            installed_at="2026-07-15T10:00:00Z",
        )
    )
    save_lockfile(lock, path)
    loaded = load_lockfile(path)
    assert loaded.plugins == lock.plugins


def test_missing_file_is_an_empty_lockfile(tmp_path):
    assert load_lockfile(tmp_path / "yok.lock").plugins == []


def test_unknown_schema_version_is_a_hard_error(tmp_path):
    path = tmp_path / "l.lock"
    path.write_text("version = 99\n", encoding="utf-8")
    with pytest.raises(ValueError, match="99"):
        load_lockfile(path)


def test_ordering_is_stable_and_upsert_replaces(tmp_path):
    path = tmp_path / "l.lock"
    lock = Lockfile()
    for name in ("zeta", "alfa", "orta"):
        lock.upsert(_entry(name))
    lock.upsert(_entry("orta", ref="v2"))  # replace, not duplicate
    save_lockfile(lock, path)
    loaded = load_lockfile(path)
    assert [p.name for p in loaded.plugins] == ["alfa", "orta", "zeta"]
    assert loaded.get("orta").ref == "v2"
    # Byte-stable: saving the same state twice yields identical files (diff-friendly).
    first = path.read_text(encoding="utf-8")
    save_lockfile(loaded, path)
    assert path.read_text(encoding="utf-8") == first