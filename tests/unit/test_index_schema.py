"""Marketplace index schema: round-trip, schema-version guard, lookup."""

import json

import pytest
from etki.plugin.index_schema import (
    IndexArtifact,
    IndexFile,
    IndexPlugin,
    IndexVersion,
    parse_index,
)

from etki_api import SecurityCapabilities


def _index() -> IndexFile:
    return IndexFile(
        generated_at="2026-07-15T12:00:00Z",
        plugins=[
            IndexPlugin(
                name="etki-plugin-linear",
                summary="Linear work items",
                ports=["work_items"],
                capabilities=SecurityCapabilities(network=True, endpoints=["api.linear.app"]),
                versions=[
                    IndexVersion(
                        version="0.1.0",
                        api_compat=">=0.1,<0.2",
                        artifact=IndexArtifact(
                            url="etki_plugin_linear-0.1.0.whl", sha256="ab" * 32
                        ),
                    )
                ],
            )
        ],
    )


def test_roundtrip():
    raw = _index().model_dump_json().encode()
    parsed = parse_index(raw)
    assert parsed == _index()
    assert parsed.get("etki-plugin-linear").versions[0].api_compat == ">=0.1,<0.2"
    assert parsed.get("yok") is None


def test_unknown_schema_version_is_a_hard_error():
    payload = json.loads(_index().model_dump_json())
    payload["schema_version"] = 99
    with pytest.raises(ValueError, match="99"):
        parse_index(json.dumps(payload).encode())