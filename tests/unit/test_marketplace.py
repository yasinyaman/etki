"""Marketplace client: search matching, compat-aware version resolution."""

import pytest
from etki.plugin import marketplace
from etki.plugin.index_schema import IndexArtifact, IndexFile, IndexPlugin, IndexVersion
from etki.plugin.installer import InstallError

from etki_api import __version__ as api_version


def _version(v: str, compat: str) -> IndexVersion:
    return IndexVersion(
        version=v, api_compat=compat, artifact=IndexArtifact(url=f"x-{v}.whl", sha256="0" * 64)
    )


_INDEX = IndexFile(
    plugins=[
        IndexPlugin(
            name="etki-plugin-linear",
            summary="Linear work items adapter",
            ports=["work_items"],
            versions=[
                _version("0.1.0", ">=0.1,<0.2"),
                _version("0.2.0", ">=0.1,<0.2"),  # highest compatible → wins
                _version("9.0.0", ">=99.0"),  # incompatible with installed etki-api
            ],
        ),
        IndexPlugin(name="etki-plugin-acme", summary="Acme tracker", ports=["documents"]),
    ]
)


def test_search_matches_name_summary_and_ports():
    assert [p.name for p in marketplace.search(_INDEX, "linear")] == ["etki-plugin-linear"]
    assert [p.name for p in marketplace.search(_INDEX, "tracker")] == ["etki-plugin-acme"]
    assert [p.name for p in marketplace.search(_INDEX, "work_items")] == ["etki-plugin-linear"]
    assert marketplace.search(_INDEX, "zxqv") == []


def test_resolve_picks_highest_COMPATIBLE_version():
    plugin, version = marketplace.resolve(_INDEX, "etki-plugin-linear")
    assert version.version == "0.2.0"  # 9.0.0 skipped: needs etki-api >=99


def test_resolve_unknown_name_lists_known():
    with pytest.raises(InstallError, match="etki-plugin-acme"):
        marketplace.resolve(_INDEX, "boyle-plugin-yok")


def test_resolve_no_compatible_version_names_the_installed_api():
    index = IndexFile(
        plugins=[IndexPlugin(name="p", versions=[_version("1.0", ">=99.0")])]
    )
    with pytest.raises(InstallError, match=api_version):
        marketplace.resolve(index, "p")