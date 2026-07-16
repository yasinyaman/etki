"""etki.mcp_tools entry-point group: registration + per-tool isolation."""

from importlib import metadata
from importlib.metadata import EntryPoint

from etki import mcp_server


def sample_tool(query: str) -> str:
    """A plugin-contributed MCP tool (test fixture)."""
    return f"ok:{query}"


def test_plugin_tools_register_and_broken_ones_are_skipped(monkeypatch):
    eps = [
        EntryPoint("iyi", f"{__name__}:sample_tool", "etki.mcp_tools"),
        EntryPoint("bozuk", f"{__name__}:boyle_bir_sey_yok", "etki.mcp_tools"),
    ]
    monkeypatch.setattr(metadata, "entry_points", lambda group: eps)
    assert mcp_server._register_plugin_tools() == 1  # good in, broken skipped, no raise