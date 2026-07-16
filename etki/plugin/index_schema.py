"""Verified-marketplace index schema — shared by this CLI and the external
`etki-plugins` repo's CI (single source of truth: the SIGNED `index.json`;
every UI/CLI view is a projection of it, wiki-style).

Each version entry carries the SHA-256 of its artifact and the etki-api
compat range measured by its conformance report — the fields
`python -m etki_api.conformance` emits."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from etki_api import SecurityCapabilities

INDEX_FILENAME = "index.json"
BUNDLE_FILENAME = "index.json.sigstore"
MIRROR_MANIFEST = "mirror-manifest.json"
SCHEMA_VERSION = 1


class IndexArtifact(BaseModel):
    url: str  # absolute URL (remote index) or a path relative to the mirror dir
    sha256: str


class IndexVersion(BaseModel):
    version: str
    api_compat: str  # PEP 440 range against etki-api, from the conformance report
    artifact: IndexArtifact
    conformance_report: str = ""  # link/path to the machine-readable report
    released_at: str = ""


class IndexPlugin(BaseModel):
    name: str
    summary: str = ""
    source_repo: str = ""
    ports: list[str] = Field(default_factory=list)
    capabilities: SecurityCapabilities = Field(default_factory=SecurityCapabilities)
    versions: list[IndexVersion] = Field(default_factory=list)


class IndexFile(BaseModel):
    schema_version: int = SCHEMA_VERSION
    generated_at: str = ""
    plugins: list[IndexPlugin] = Field(default_factory=list)

    def get(self, name: str) -> IndexPlugin | None:
        return next((p for p in self.plugins if p.name == name), None)


def parse_index(raw: bytes) -> IndexFile:
    """Bytes → IndexFile; unknown schema version is a hard error (a newer
    marketplace wrote it — never guess)."""
    data = json.loads(raw)
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"bilinmeyen index şema versiyonu {version!r} (bu araç {SCHEMA_VERSION} bekliyor)"
        )
    return IndexFile.model_validate(data)
