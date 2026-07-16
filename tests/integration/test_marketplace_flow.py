"""PLUGIN FAZ 5 EXIT GATE — the full verified chain against a LOCAL fixture
index, network-free:

1. `install <name> --index <fixture>` → hash verified → installed into a
   throwaway venv → lockfile entry `verified = true`.
2. Corrupted sha256 AND corrupted signature each abort with an untouched
   lockfile.
3. `mirror` (mocked remote): signature verified ONLINE-side, artifacts
   hash-checked, `mirror-manifest.json` written → offline install from the
   mirror succeeds; a tampered mirrored wheel aborts."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from etki.plugin import installer, marketplace, signing
from etki.plugin.index_schema import IndexArtifact, IndexFile, IndexPlugin, IndexVersion
from etki.plugin.installer import InstallError
from etki.plugin.lockfile import load_lockfile

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


def _fixture_index_dir(base: Path, wheel: Path, *, sha256: str | None = None) -> Path:
    """A local marketplace dir: index.json + the wheel next to it."""
    index_dir = base / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(wheel, index_dir / wheel.name)
    index = IndexFile(
        generated_at="2026-07-15T12:00:00Z",
        plugins=[
            IndexPlugin(
                name="etki-plugin-linear",
                summary="Linear work items",
                ports=["work_items"],
                versions=[
                    IndexVersion(
                        version="0.1.0",
                        api_compat=">=0.1,<0.2",
                        artifact=IndexArtifact(
                            url=wheel.name,
                            sha256=sha256 or installer.sha256_of(wheel),
                        ),
                    )
                ],
            )
        ],
    )
    (index_dir / "index.json").write_bytes(index.model_dump_json(indent=2).encode())
    return index_dir


def _fresh_venv(base: Path) -> str:
    venv = base / "venv"
    if venv.exists():
        shutil.rmtree(venv)
    _uv("venv", str(venv), "--python", sys.executable)
    return str(venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python"))


def test_verified_install_end_to_end(linear_wheel, tmp_path):
    index_dir = _fixture_index_dir(tmp_path, linear_wheel)
    lock_path = tmp_path / "etki-plugins.lock"
    python = _fresh_venv(tmp_path)

    entry = marketplace.install_verified(
        "etki-plugin-linear",
        str(index_dir),
        yes=True,
        python=python,
        lockfile_path=lock_path,
        uv_args=_OFFLINE,
    )
    assert entry.verified is True and entry.source == "verified"
    locked = load_lockfile(lock_path).get("etki-plugin-linear")
    assert locked is not None and locked.verified is True
    assert "etki-plugin-linear" in _uv("pip", "freeze", "--python", python).stdout


def test_corrupted_sha256_aborts_with_untouched_lockfile(linear_wheel, tmp_path):
    index_dir = _fixture_index_dir(tmp_path, linear_wheel, sha256="0" * 64)
    lock_path = tmp_path / "etki-plugins.lock"
    python = _fresh_venv(tmp_path)
    with pytest.raises(InstallError, match="SHA-256 index'le uyuşmuyor"):
        marketplace.install_verified(
            "etki-plugin-linear", str(index_dir), yes=True,
            python=python, lockfile_path=lock_path, uv_args=_OFFLINE,
        )
    assert not lock_path.exists(), "başarısız kurulum lockfile'a DOKUNMAMALI"
    assert "etki-plugin-linear" not in _uv("pip", "freeze", "--python", python).stdout


def test_corrupted_signature_aborts_with_untouched_lockfile(
    linear_wheel, tmp_path, monkeypatch
):
    index_dir = _fixture_index_dir(tmp_path, linear_wheel)
    (index_dir / "index.json.sigstore").write_bytes(b"bozuk-bundle")

    class _Failing:
        def verify(self, artifact, bundle_json, *, identity, issuer):
            raise ValueError("imza geçersiz")

    monkeypatch.setattr(signing, "_load_sigstore_verifier", lambda: _Failing())
    lock_path = tmp_path / "etki-plugins.lock"
    with pytest.raises(signing.SigningError, match="BAŞARISIZ"):
        marketplace.install_verified(
            "etki-plugin-linear", str(index_dir), yes=True, lockfile_path=lock_path
        )
    assert not lock_path.exists()


def test_mirror_then_offline_install(linear_wheel, tmp_path, monkeypatch):
    """Online side: mirror verifies the signature + hashes; inner side installs
    from the directory hash-only (no network — _http_get would raise)."""
    source = _fixture_index_dir(tmp_path, linear_wheel)
    index_raw = (source / "index.json").read_bytes()
    wheel_raw = (source / linear_wheel.name).read_bytes()
    remote = {
        "https://plugins.example.com/index.json": index_raw,
        "https://plugins.example.com/index.json.sigstore": b"fake-bundle",
        f"https://plugins.example.com/{linear_wheel.name}": wheel_raw,
    }
    monkeypatch.setattr(marketplace, "_http_get", lambda url: remote[url])

    class _OkVerifier:
        def __init__(self):
            self.calls = 0

        def verify(self, artifact, bundle_json, *, identity, issuer):
            self.calls += 1
            assert artifact == index_raw and bundle_json == b"fake-bundle"

    verifier = _OkVerifier()
    monkeypatch.setattr(signing, "_load_sigstore_verifier", lambda: verifier)

    mirror_dir = tmp_path / "mirror"
    mirrored = marketplace.mirror("https://plugins.example.com/index.json", mirror_dir)
    assert mirrored == ["etki-plugin-linear@0.1.0"]
    assert verifier.calls >= 1, "imza MIRROR anında (online tarafta) doğrulanmalı"
    manifest = json.loads((mirror_dir / "mirror-manifest.json").read_text(encoding="utf-8"))
    assert manifest["signature_verified"] is True and manifest["identity"]

    # Inner side: no network at all — installs must resolve from the directory.
    def no_network(url):
        raise AssertionError(f"air-gapped kurulum ağa çıkmamalı: {url}")

    monkeypatch.setattr(marketplace, "_http_get", no_network)
    # sigstore absent inside → PRESENT bundle degrades to a warning (hash rules).
    monkeypatch.setattr(
        signing, "_load_sigstore_verifier",
        lambda: (_ for _ in ()).throw(signing.SigningError("sigstore kurulu değil — ...")),
    )
    python = _fresh_venv(tmp_path)
    lock_path = tmp_path / "etki-plugins.lock"
    entry = marketplace.install_verified(
        "etki-plugin-linear", str(mirror_dir), yes=True,
        python=python, lockfile_path=lock_path, uv_args=_OFFLINE,
    )
    assert entry.verified is True

    # Tampered mirrored wheel: hash rule catches it even with signature skipped.
    (mirror_dir / linear_wheel.name).write_bytes(b"tampered")
    python = _fresh_venv(tmp_path)
    with pytest.raises(InstallError, match="uyuşmuyor"):
        marketplace.install_verified(
            "etki-plugin-linear", str(mirror_dir), yes=True,
            python=python, lockfile_path=tmp_path / "l2.lock", uv_args=_OFFLINE,
        )
    assert not (tmp_path / "l2.lock").exists()