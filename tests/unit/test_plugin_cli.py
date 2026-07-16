"""`python -m etki.plugin list` — human and machine output."""

import json

from etki.plugin.__main__ import main


def test_list_shows_the_installed_linear_plugin(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "etki-plugin-linear" in out
    assert "[active]" in out
    assert "work_items" in out


def test_list_json_is_machine_readable(capsys):
    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    names = {p["name"]: p for p in payload["plugins"]}
    linear = names["etki-plugin-linear"]
    assert linear["state"] == "active"
    assert linear["ports"] == ["work_items"]
    assert any(s.startswith("etki-plugin-linear@") for s in payload["stamp"])
