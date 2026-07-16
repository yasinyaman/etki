"""Plugin policy: env-only read, fail-closed default, INVERSE-priority proof.

The LLM settings deliberately let `.etki/llm.json` (UI) beat env; the plugin
policy must be the exact opposite — a UI-writable admin lock is no lock. The
proof test writes a policy key into the JSON source and asserts it is ignored."""

import json

from etki.plugin import policy


def test_default_is_verified_only(monkeypatch):
    monkeypatch.delenv(policy.ENV_VAR, raising=False)
    assert policy.current_policy() == "verified_only"
    assert not policy.allows("git")
    assert not policy.allows("local")


def test_levels_are_ordered(monkeypatch):
    monkeypatch.setenv(policy.ENV_VAR, "allow_git")
    assert policy.allows("git") and not policy.allows("local")
    monkeypatch.setenv(policy.ENV_VAR, "allow_local")
    assert policy.allows("git") and policy.allows("local")


def test_unknown_value_fails_closed(monkeypatch):
    monkeypatch.setenv(policy.ENV_VAR, "allow_everything_lol")
    assert policy.current_policy() == "verified_only"


def test_ui_settings_source_cannot_touch_the_policy(tmp_path, monkeypatch):
    """Write plugin_policy into .etki/llm.json (the TOP-priority Settings
    source) → the policy must not see it: it reads os.environ directly and is
    not a Settings field at all."""
    monkeypatch.chdir(tmp_path)
    ui = tmp_path / ".etki"
    ui.mkdir()
    (ui / "llm.json").write_text(
        json.dumps({"plugin_policy": "allow_local"}), encoding="utf-8"
    )
    monkeypatch.delenv(policy.ENV_VAR, raising=False)

    from etki.config import Settings

    settings = Settings()
    assert not hasattr(settings, "plugin_policy")  # not a Settings field, by design
    assert policy.current_policy() == "verified_only"  # UI file had no effect

    monkeypatch.setenv(policy.ENV_VAR, "allow_git")  # env, the ONLY channel, wins
    assert policy.current_policy() == "allow_git"