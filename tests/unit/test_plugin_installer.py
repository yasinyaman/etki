"""Installer unit tests — every subprocess mocked; the load-bearing rules:
branch rejection, tag→SHA resolution, hash-before-install."""

import subprocess

import pytest
from etki.plugin import installer
from etki.plugin.installer import InstallError
from etki.plugin.lockfile import load_lockfile

_URL = "https://github.com/acme/etki-plugin-acme"
_SHA = "1234567890abcdef1234567890abcdef12345678"


def _proc(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


def test_branch_ref_is_a_hard_error(monkeypatch):
    monkeypatch.setattr(
        installer, "_run", lambda cmd, **kw: _proc(f"{_SHA}\trefs/heads/main\n")
    )
    with pytest.raises(InstallError, match="BRANCH"):
        installer.resolve_git_ref(_URL, "main")


def test_annotated_tag_resolves_to_peeled_commit(monkeypatch):
    tag_obj = "f" * 40
    monkeypatch.setattr(
        installer,
        "_run",
        lambda cmd, **kw: _proc(
            f"{tag_obj}\trefs/tags/v1.2.0\n{_SHA}\trefs/tags/v1.2.0^{{}}\n"
        ),
    )
    assert installer.resolve_git_ref(_URL, "v1.2.0") == _SHA


def test_bare_commit_ish_is_accepted(monkeypatch):
    monkeypatch.setattr(installer, "_run", lambda cmd, **kw: _proc(""))
    assert installer.resolve_git_ref(_URL, _SHA) == _SHA


def test_unknown_ref_is_an_error(monkeypatch):
    monkeypatch.setattr(installer, "_run", lambda cmd, **kw: _proc(""))
    with pytest.raises(InstallError, match="bulunamadı"):
        installer.resolve_git_ref(_URL, "boyle-tag-yok")


def test_sha256_mismatch_aborts_BEFORE_any_install(tmp_path, monkeypatch):
    wheel = tmp_path / "etki_plugin_acme-1.0.0-py3-none-any.whl"
    wheel.write_bytes(b"not-a-real-wheel")
    calls: list[list[str]] = []
    monkeypatch.setattr(installer, "_run", lambda cmd, **kw: calls.append(cmd) or _proc())
    with pytest.raises(InstallError, match="SHA-256 uyuşmuyor"):
        installer.install_wheel(wheel, sha256="0" * 64, lockfile_path=tmp_path / "l.lock")
    assert calls == [], "hash uyuşmazlığında HİÇBİR subprocess çalışmamalı"
    assert not (tmp_path / "l.lock").exists(), "lockfile'a da yazılmamalı"


def test_wheel_install_writes_lockfile(tmp_path, monkeypatch):
    wheel = tmp_path / "etki_plugin_acme-1.0.0-py3-none-any.whl"
    wheel.write_bytes(b"payload")
    digest = installer.sha256_of(wheel)
    monkeypatch.setattr(installer, "_run", lambda cmd, **kw: _proc())
    lock_path = tmp_path / "l.lock"
    entry = installer.install_wheel(wheel, sha256=digest, lockfile_path=lock_path)
    assert entry.source == "local" and entry.sha256 == digest
    assert load_lockfile(lock_path).get("etki-plugin-acme") is not None


def test_dependency_conflict_warns_with_plugin_name(tmp_path, monkeypatch, caplog):
    wheel = tmp_path / "etki_plugin_acme-1.0.0-py3-none-any.whl"
    wheel.write_bytes(b"payload")

    def fake_run(cmd, **kw):
        if "check" in cmd:
            return subprocess.CompletedProcess(cmd, 1, stdout="conflict!", stderr="")
        return _proc()

    monkeypatch.setattr(installer, "_run", fake_run)
    with caplog.at_level("WARNING", logger="etki"):
        installer.install_wheel(
            wheel, sha256=installer.sha256_of(wheel), lockfile_path=tmp_path / "l.lock"
        )
    assert any("etki-plugin-acme" in r.message for r in caplog.records)


def test_sync_reverifies_local_hash(tmp_path, monkeypatch):
    wheel = tmp_path / "etki_plugin_acme-1.0.0-py3-none-any.whl"
    wheel.write_bytes(b"payload")
    monkeypatch.setattr(installer, "_run", lambda cmd, **kw: _proc())
    lock_path = tmp_path / "l.lock"
    installer.install_wheel(wheel, sha256=installer.sha256_of(wheel), lockfile_path=lock_path)
    wheel.write_bytes(b"tampered!")  # file changed after locking
    with pytest.raises(InstallError, match="uyuşmuyor"):
        installer.sync(lockfile_path=lock_path)