"""PLUGIN FAZ 3 EXIT GATE (network-free):

Build the linear plugin wheel → hash-verified install into a throwaway uv venv
→ lockfile written → wipe the venv → `sync` → `uv pip freeze` byte-identical
to the first install. Resolution is offline (`--no-deps` + the built wheel);
policy blocking and branch rejection are covered by the CLI unit tests."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from etki.plugin import installer

_REPO = Path(__file__).resolve().parents[2]
_OFFLINE = ["--no-deps", "--offline"]


def _uv(*args: str) -> subprocess.CompletedProcess:
    proc = subprocess.run(["uv", *args], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, f"uv {' '.join(args)}:\n{proc.stderr}"
    return proc


@pytest.fixture(scope="module")
def linear_wheel(tmp_path_factory) -> Path:
    dist = tmp_path_factory.mktemp("dist")
    _uv("build", "--package", "etki-plugin-linear", "--wheel", "--out-dir", str(dist),
        "--project", str(_REPO))
    (wheel,) = dist.glob("etki_plugin_linear-*.whl")
    return wheel


def _fresh_venv(base: Path) -> str:
    venv = base / "venv"
    if venv.exists():
        shutil.rmtree(venv)
    _uv("venv", str(venv), "--python", sys.executable)
    py = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    return str(py)


def _freeze(python: str) -> str:
    return _uv("pip", "freeze", "--python", python).stdout


def test_install_wipe_sync_is_byte_identical(linear_wheel, tmp_path, monkeypatch):
    monkeypatch.setenv("ETKI_PLUGIN_POLICY", "allow_local")
    lock_path = tmp_path / "etki-plugins.lock"

    python = _fresh_venv(tmp_path)
    entry = installer.install_wheel(
        linear_wheel,
        sha256=installer.sha256_of(linear_wheel),
        python=python,
        lockfile_path=lock_path,
        uv_args=_OFFLINE,
    )
    assert entry.name == "etki-plugin-linear"
    assert lock_path.exists()
    first_freeze = _freeze(python)
    assert "etki-plugin-linear" in first_freeze

    # Disaster recovery: the venv is GONE, only the lockfile (+ wheel) remains.
    python = _fresh_venv(tmp_path)
    assert "etki-plugin-linear" not in _freeze(python)
    installed = installer.sync(python=python, lockfile_path=lock_path, uv_args=_OFFLINE)
    assert installed == ["etki-plugin-linear"]
    assert _freeze(python) == first_freeze, "sync bit-bit aynı ortamı vermeli"


def test_remove_uninstalls_and_drops_the_lock_entry(linear_wheel, tmp_path, monkeypatch):
    monkeypatch.setenv("ETKI_PLUGIN_POLICY", "allow_local")
    lock_path = tmp_path / "etki-plugins.lock"
    python = _fresh_venv(tmp_path)
    installer.install_wheel(
        linear_wheel,
        sha256=installer.sha256_of(linear_wheel),
        python=python,
        lockfile_path=lock_path,
        uv_args=_OFFLINE,
    )
    assert installer.remove("etki-plugin-linear", python=python, lockfile_path=lock_path)
    assert "etki-plugin-linear" not in _freeze(python)
    from etki.plugin.lockfile import load_lockfile

    assert load_lockfile(lock_path).plugins == []