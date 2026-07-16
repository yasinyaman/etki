"""Plugin installer: git (pinned) and local-wheel (hash-mandatory) paths.

Load-bearing rules, all pinned by tests:
- Branch refs are REJECTED (`git ls-remote` classification) — only tags and
  commits install; a tag resolves to its FULL commit SHA and the SHA is what
  gets installed and locked (tags can move, SHAs can't).
- The confirmation prompt reads `etki-plugin.toml` from a shallow clone /
  the wheel WITHOUT importing plugin code.
- A local wheel's SHA-256 is verified BEFORE any install subprocess runs.
- Installs go through `uv pip install` (with dependencies) followed by
  `uv pip check` — a dependency conflict prints a loud warning naming the
  plugin (the reproducible path remains container build-time `sync`).
"""

from __future__ import annotations

import hashlib
import logging
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

from etki.adapters.git_clone import GitCloneError, _validate_git_url
from etki.plugin.lockfile import (
    LockedPlugin,
    load_lockfile,
    now_iso,
    save_lockfile,
)
from etki_api import PluginManifest, SecurityCapabilities
from etki_api.manifest import MANIFEST_FILENAME, load_manifest

logger = logging.getLogger("etki")

_HEX_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")


class InstallError(RuntimeError):
    """User-facing install failure (CLI prints the message, no traceback)."""


def _run(cmd: list[str], *, timeout: float = 300.0) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _ls_remote(url: str, ref: str) -> list[tuple[str, str]]:
    """[(sha, refname)] for `ref` (+ its peeled `^{}` form for annotated tags)."""
    proc = _run(["git", "ls-remote", url, ref, f"{ref}^{{}}"])
    if proc.returncode != 0:
        raise InstallError(f"git ls-remote başarısız ({url}): {proc.stderr.strip()}")
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 2:
            rows.append((parts[0].strip(), parts[1].strip()))
    return rows


def _validate_ref(ref: str) -> None:
    """A ref must not look like a git option (leading '-' → argument injection)."""
    if not ref or ref.startswith("-"):
        raise InstallError(f"geçersiz ref (boş ya da '-' ile başlıyor): {ref!r}")


def resolve_git_ref(url: str, ref: str) -> str:
    """ref → FULL commit sha. Branches are a hard error; a commit-ish that the
    remote doesn't advertise is accepted as-is (verified by the fetch).

    The URL is validated (scheme allow-list; `ext::`/`file:`/leading-'-' rejected) BEFORE any
    git subprocess runs, so a hostile URL cannot execute a transport helper (`ext::sh -c …`)
    ahead of the capability-confirmation prompt."""
    try:
        _validate_git_url(url)
    except GitCloneError as exc:
        raise InstallError(str(exc)) from exc
    _validate_ref(ref)
    rows = _ls_remote(url, ref)
    if any(name.startswith("refs/heads/") for _, name in rows):
        raise InstallError(
            f"{ref!r} bir BRANCH — reddedildi. Yalnızca tag veya commit kurulur "
            "(branch oynar, kurulum tekrarlanamaz olur)."
        )
    # Annotated tag: prefer the peeled commit (refs/tags/x^{}), else the tag object.
    peeled = [sha for sha, name in rows if name.endswith("^{}")]
    if peeled:
        return peeled[0]
    tags = [sha for sha, name in rows if name.startswith("refs/tags/")]
    if tags:
        return tags[0]
    if _HEX_COMMIT.match(ref):
        return ref  # bare commit sha — the shallow fetch will verify existence
    raise InstallError(f"{ref!r} uzak depoda tag/commit olarak bulunamadı ({url}).")


def fetch_manifest_from_git(url: str, commit: str, workdir: str | Path) -> PluginManifest:
    """Shallow-fetches exactly `commit` and reads etki-plugin.toml — plugin code
    is NEVER imported/executed for the confirmation prompt."""
    wd = Path(workdir)
    for cmd in (
        ["git", "init", "-q", str(wd)],
        ["git", "-C", str(wd), "fetch", "-q", "--depth", "1", url, commit],
        ["git", "-C", str(wd), "checkout", "-q", "FETCH_HEAD"],
    ):
        proc = _run(cmd)
        if proc.returncode != 0:
            raise InstallError(f"{' '.join(cmd[:3])} başarısız: {proc.stderr.strip()}")
    try:
        return load_manifest(wd)
    except FileNotFoundError:
        raise InstallError(
            f"depo {MANIFEST_FILENAME} içermiyor — bu bir Etki plugin'i değil "
            "(ya da manifest'ini henüz eklememiş)."
        ) from None


def read_manifest_from_wheel(wheel: Path) -> PluginManifest | None:
    """etki-plugin.toml from the wheel root, when the author shipped it as data;
    None when absent (the prompt then warns instead of showing capabilities)."""
    try:
        with zipfile.ZipFile(wheel) as zf:
            for name in zf.namelist():
                if Path(name).name == MANIFEST_FILENAME:
                    with tempfile.TemporaryDirectory() as tmp:
                        target = Path(zf.extract(name, tmp))
                        return load_manifest(target)
    except Exception:  # noqa: BLE001 — a malformed wheel fails later, loudly, in uv
        return None
    return None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _uv_pip(args: list[str], *, python: str | None) -> subprocess.CompletedProcess:
    cmd = ["uv", "pip", *args]
    if python:
        cmd += ["--python", python]
    return _run(cmd, timeout=600.0)


def _pip_check_warn(name: str, python: str | None) -> None:
    proc = _uv_pip(["check"], python=python)
    if proc.returncode != 0:
        logger.warning(
            "bağımlılık çakışması (uv pip check) — sorumlu plugin: %s\n%s",
            name,
            (proc.stdout + proc.stderr).strip(),
        )


def _dist_name_from_wheel(wheel: Path) -> tuple[str, str]:
    parts = wheel.name.split("-")
    if len(parts) < 2:
        raise InstallError(f"wheel adı çözümlenemedi: {wheel.name}")
    return parts[0].replace("_", "-"), parts[1]


def install_wheel(
    wheel_path: str | Path,
    *,
    sha256: str,
    python: str | None = None,
    lockfile_path: str | Path | None = None,
    uv_args: list[str] | None = None,
) -> LockedPlugin:
    """Local/offline install — the air-gapped path. Hash is MANDATORY and
    checked before anything is installed. `uv_args` is the documented escape
    hatch for offline resolution (e.g. ["--find-links", dir, "--no-deps"])."""
    wheel = Path(wheel_path)
    if not wheel.exists():
        raise InstallError(f"wheel bulunamadı: {wheel}")
    actual = sha256_of(wheel)
    if actual != sha256.lower():
        raise InstallError(
            f"SHA-256 uyuşmuyor — kurulum İPTAL (hiçbir şey kurulmadı).\n"
            f"  beklenen: {sha256}\n  dosyanın: {actual}"
        )
    manifest = read_manifest_from_wheel(wheel)
    name, version = _dist_name_from_wheel(wheel)
    proc = _uv_pip(["install", str(wheel), *(uv_args or [])], python=python)
    if proc.returncode != 0:
        raise InstallError(f"uv pip install başarısız:\n{proc.stderr.strip()}")
    _pip_check_warn(name, python)
    entry = LockedPlugin(
        name=manifest.name if manifest else name,
        source="local",
        path=str(wheel.resolve()),
        sha256=actual,
        api_compat=manifest.api_compat if manifest else "",
        capabilities=manifest.capabilities if manifest else SecurityCapabilities(),
        installed_at=now_iso(),
        verified=False,
    )
    _lock_upsert(entry, lockfile_path)
    return entry


def install_git(
    url: str,
    ref: str,
    *,
    python: str | None = None,
    lockfile_path: str | Path | None = None,
    manifest: PluginManifest | None = None,
    uv_args: list[str] | None = None,
) -> LockedPlugin:
    """Community path: tag/commit only; installs the RESOLVED sha. The caller
    (CLI) fetches the manifest first for the confirmation prompt and passes it
    in so the clone isn't repeated."""
    commit = resolve_git_ref(url, ref)
    if manifest is None:
        with tempfile.TemporaryDirectory(prefix="etki-plugin-") as tmp:
            manifest = fetch_manifest_from_git(url, commit, tmp)
    proc = _uv_pip(["install", f"git+{url}@{commit}", *(uv_args or [])], python=python)
    if proc.returncode != 0:
        raise InstallError(f"uv pip install başarısız:\n{proc.stderr.strip()}")
    _pip_check_warn(manifest.name, python)
    entry = LockedPlugin(
        name=manifest.name,
        source="git",
        url=url,
        ref=ref,
        commit=commit,
        api_compat=manifest.api_compat,
        capabilities=manifest.capabilities,
        installed_at=now_iso(),
        verified=False,
    )
    _lock_upsert(entry, lockfile_path)
    return entry


def sync(
    *,
    python: str | None = None,
    lockfile_path: str | Path | None = None,
    uv_args: list[str] | None = None,
) -> list[str]:
    """Reinstalls EXACTLY the locked state (new machine / CI / container build /
    disaster recovery). Local wheels are re-hash-verified before install."""
    lock = load_lockfile(lockfile_path or "etki-plugins.lock")
    installed: list[str] = []
    for entry in lock.plugins:
        if entry.source == "local":
            wheel = Path(entry.path)
            if not wheel.exists():
                raise InstallError(f"{entry.name}: kilitli wheel yok olmuş: {wheel}")
            if sha256_of(wheel) != entry.sha256:
                raise InstallError(
                    f"{entry.name}: wheel içeriği lockfile'daki hash'le uyuşmuyor — "
                    "dosya değişmiş, kurulum İPTAL."
                )
            spec = str(wheel)
        elif entry.source == "git":
            spec = f"git+{entry.url}@{entry.commit}"
        else:  # "verified" — the signed marketplace path lands in Faz 5
            raise InstallError(
                f"{entry.name}: source={entry.source!r} sync'i henüz desteklenmiyor (Faz 5)."
            )
        proc = _uv_pip(["install", spec, *(uv_args or [])], python=python)
        if proc.returncode != 0:
            raise InstallError(f"{entry.name} sync başarısız:\n{proc.stderr.strip()}")
        installed.append(entry.name)
    return installed


def remove(
    name: str,
    *,
    python: str | None = None,
    lockfile_path: str | Path | None = None,
) -> bool:
    """Uninstalls + drops the lockfile entry. Returns False when not locked."""
    lock_path = lockfile_path or "etki-plugins.lock"
    lock = load_lockfile(lock_path)
    if lock.get(name) is None:
        return False
    proc = _uv_pip(["uninstall", name], python=python)
    if proc.returncode != 0:
        raise InstallError(f"uv pip uninstall başarısız:\n{proc.stderr.strip()}")
    lock.remove(name)
    save_lockfile(lock, lock_path)
    return True


def _lock_upsert(entry: LockedPlugin, lockfile_path: str | Path | None) -> None:
    path = lockfile_path or "etki-plugins.lock"
    lock = load_lockfile(path)
    lock.upsert(entry)
    save_lockfile(lock, path)
