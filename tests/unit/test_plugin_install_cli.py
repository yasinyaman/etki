"""Install CLI: policy gate first (no subprocess before refusal), prompt shows
declared capabilities, branch rejection surfaces cleanly; runtime `blocked`
enforcement for non-editable dists under verified_only."""

import subprocess

import etki.adapters.plugins as plugins_mod
import pytest
from etki.plugin import installer, policy
from etki.plugin.__main__ import main


def test_verified_only_blocks_git_install_before_any_network(monkeypatch, capsys):
    monkeypatch.setenv(policy.ENV_VAR, "verified_only")
    calls = []
    monkeypatch.setattr(installer, "_run", lambda cmd, **kw: calls.append(cmd))
    code = main(["install", "git+https://github.com/x/y@v1.0.0", "--yes"])
    assert code == 3  # policy exit code, scriptable
    out = capsys.readouterr().out
    assert "ETKI_PLUGIN_POLICY" in out and "yönetici kilidi" in out
    assert calls == [], "policy reddi ağdan/subprocess'ten ÖNCE gelmeli"


def test_wheel_install_requires_allow_local(monkeypatch, capsys):
    monkeypatch.setenv(policy.ENV_VAR, "allow_git")  # git yes, local no
    assert main(["install", "./x.whl", "--sha256", "0" * 64, "--yes"]) == 3
    assert "allow_local" in capsys.readouterr().out


def test_git_ref_is_mandatory(monkeypatch, capsys):
    monkeypatch.setenv(policy.ENV_VAR, "allow_git")
    assert main(["install", "git+https://github.com/x/y", "--yes"]) == 2
    assert "ref zorunlu" in capsys.readouterr().out


def test_branch_rejection_surfaces_as_install_error(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv(policy.ENV_VAR, "allow_git")
    monkeypatch.setattr(
        installer,
        "_run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 0, stdout="a" * 40 + "\trefs/heads/main\n", stderr=""
        ),
    )
    code = main(
        ["install", "git+https://github.com/x/y@main", "--yes",
         "--lockfile", str(tmp_path / "l.lock")]
    )
    assert code == 1
    assert "BRANCH" in capsys.readouterr().out


def test_prompt_shows_declared_capabilities(monkeypatch, capsys, tmp_path):
    """The confirmation screen renders manifest capabilities and an explicit
    'unverified' warning; a 'no' answer installs nothing."""
    monkeypatch.setenv(policy.ENV_VAR, "allow_local")
    wheel = tmp_path / "etki_plugin_acme-1.0.0-py3-none-any.whl"
    import zipfile

    with zipfile.ZipFile(wheel, "w") as zf:
        zf.writestr(
            "etki-plugin.toml",
            '[plugin]\nname = "etki-plugin-acme"\napi_compat = ">=0.1,<0.2"\n'
            "[plugin.capabilities]\nnetwork = true\nendpoints = [\"acme.example.com\"]\n",
        )
    digest = installer.sha256_of(wheel)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    code = main(["install", str(wheel), "--sha256", digest,
                 "--lockfile", str(tmp_path / "l.lock")])
    out = capsys.readouterr().out
    assert code == 1 and "Vazgeçildi" in out
    assert "ağ erişimi" in out and "acme.example.com" in out
    assert "doğrulanmamış" in out
    assert not (tmp_path / "l.lock").exists()


class _FakeDist:
    """Non-editable installed distribution (as a user's manual pip install)."""

    version = "1.0.0"

    def read_text(self, name):
        return "{}" if name == "direct_url.json" else None


def test_non_editable_dist_is_blocked_under_verified_only(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # empty lockfile world
    monkeypatch.setenv(policy.ENV_VAR, "verified_only")
    assert plugins_mod._should_block("etki-plugin-acme", _FakeDist()) is not None
    monkeypatch.setenv(policy.ENV_VAR, "allow_git")
    assert plugins_mod._should_block("etki-plugin-acme", _FakeDist()) is None


def test_editable_and_unattributed_dists_are_exempt(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(policy.ENV_VAR, "verified_only")

    class _Editable(_FakeDist):
        def read_text(self, name):
            return '{"dir_info": {"editable": true}}'

    assert plugins_mod._should_block("x", _Editable()) is None  # dev working tree
    assert plugins_mod._should_block("x", None) is None  # fabricated/test EP


def test_verified_lockfile_entry_unblocks(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(policy.ENV_VAR, "verified_only")
    from etki.plugin.lockfile import LockedPlugin, Lockfile, save_lockfile

    lock = Lockfile()
    lock.upsert(
        LockedPlugin(name="etki-plugin-acme", source="verified", sha256="x", verified=True)
    )
    save_lockfile(lock)  # cwd/etki-plugins.lock — what _should_block reads
    assert plugins_mod._should_block("etki-plugin-acme", _FakeDist()) is None
    with pytest.raises(AssertionError):
        assert plugins_mod._should_block("etki-plugin-baska", _FakeDist()) is None