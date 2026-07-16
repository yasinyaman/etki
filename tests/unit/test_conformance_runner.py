"""Conformance runner: report schema + exit codes (subprocess — the runner
spawns its own pytest, which must not nest inside this one)."""

import json
import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "etki_api.conformance", *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_report_schema_and_success_exit(tmp_path):
    report_path = tmp_path / "report.json"
    proc = _run("etki-plugin-linear", "--report", str(report_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["plugin"] == "etki-plugin-linear"
    assert report["conformant"] is True
    assert report["failed"] == 0 and report["passed"] > 0
    # Version-compat matrix fields (consumed by the marketplace index in Faz 5).
    assert report["api_compat"] and report["etki_api_version"] and report["version"]
    assert report["ports"] == ["work_items"]
    assert all(r["outcome"] in ("passed", "failed", "skipped") for r in report["results"])
    assert "UYUMLU" in proc.stdout


def test_unknown_distribution_exits_2():
    proc = _run("boyle-bir-dagitim-yok")
    assert proc.returncode == 2
    assert "conformance:" in proc.stdout


def test_distribution_without_conformance_factory_exits_2():
    # etki-api itself has no etki.adapters entry point → the "no entry point"
    # branch; message must be actionable, not a traceback.
    proc = _run("etki-api")
    assert proc.returncode == 2
    assert "entry point" in proc.stdout
    assert "Traceback" not in proc.stderr


def test_verify_cli_delegates(tmp_path):
    report_path = tmp_path / "r.json"
    proc = subprocess.run(
        [sys.executable, "-m", "etki.plugin", "verify", "etki-plugin-linear",
         "--report", str(report_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(report_path.read_text(encoding="utf-8"))["conformant"] is True