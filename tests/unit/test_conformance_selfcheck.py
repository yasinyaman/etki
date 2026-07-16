"""Conformance suite self-check (Faz 4 pull-ahead payoff): the contract classes
run against etki's OWN fakes and the linear plugin's conformance double — an
instant regression net keeping suite ↔ engine expectations consistent. If a
contract here starts failing, either the fake or the written contract drifted."""

import pytest
from etki.adapters.fakes.code_repo import FakeCodeRepositoryProvider
from etki.adapters.fakes.document import FakeDocumentSourceProvider
from etki.adapters.fakes.work_item import FakeWorkItemProvider

from etki_api.conformance import (
    CodeRepositoryProviderContract,
    DocumentSourceProviderContract,
    EmbeddingProviderContract,
    LLMClientContract,
    RegistryMetadataProviderContract,
    RerankProviderContract,
    WorkItemProviderContract,
)
from etki_api.models import PackageMetadata
from etki_plugin_linear import PLUGIN


class TestFakeWorkItemsConformance(WorkItemProviderContract):
    known_item_id = "WI-101"

    @pytest.fixture
    def provider(self):
        return FakeWorkItemProvider()


class TestEmptyWorkItemsConformance(WorkItemProviderContract):
    """The documented `[]` (no-history) construction must also conform."""

    @pytest.fixture
    def provider(self):
        return FakeWorkItemProvider([])


class TestFakeCodeRepoConformance(CodeRepositoryProviderContract):
    known_module_hint = "reporting"

    @pytest.fixture
    def provider(self):
        return FakeCodeRepositoryProvider()


class TestFakeDocumentsConformance(DocumentSourceProviderContract):
    @pytest.fixture
    def provider(self):
        return FakeDocumentSourceProvider()


class TestLinearPluginConformance(WorkItemProviderContract):
    """The plugin's own spec.conformance() double — what `etki plugin verify`
    exercises, collected here directly for fast feedback."""

    known_item_id = "ENG-1"

    @pytest.fixture
    def provider(self):
        return PLUGIN.conformance()["work_items"]


# --- Minimal in-test doubles for the ports etki has no fakes for -------------


class _EchoLLM:
    async def complete_json(self, *, system: str, user: str) -> dict:
        return {"ok": True}


class _HashEmbedder:
    async def embed(self, texts, *, kind="document"):
        return [[float(len(t) % 7), float(sum(map(ord, t)) % 100)] for t in texts]


class _LengthReranker:
    async def rerank(self, query, documents):
        return [float(len(d)) for d in documents]


class _StaticRegistry:
    async def latest(self, ecosystem, name):
        if name == "fastapi":
            return PackageMetadata(name="fastapi", ecosystem=ecosystem, latest_version="1.0")
        return None


class TestLLMContractSelfCheck(LLMClientContract):
    @pytest.fixture
    def provider(self):
        return _EchoLLM()


class TestEmbeddingContractSelfCheck(EmbeddingProviderContract):
    @pytest.fixture
    def provider(self):
        return _HashEmbedder()


class TestRerankContractSelfCheck(RerankProviderContract):
    @pytest.fixture
    def provider(self):
        return _LengthReranker()


class TestRegistryMetadataContractSelfCheck(RegistryMetadataProviderContract):
    known_package = ("pypi", "fastapi")

    @pytest.fixture
    def provider(self):
        return _StaticRegistry()