"""Adapter conformance suite ("AdapterBench") — contract tests per port.

EtkiBench measures decision quality; THIS suite measures adapter contract
compliance — the technical basis of the Verified marketplace tier. The ports
are `runtime_checkable Protocol`s, which only check method PRESENCE; these
tests pin the documented SEMANTICS (see the "Port contracts" section of the
plugin guide).

Usage (plugin author): install ``etki-api[conformance]``, subclass the contract
class for each port you provide and supply the ``provider`` fixture with an
OFFLINE instance (canned data / mock transport — never live credentials):

    from etki_api.conformance import WorkItemProviderContract

    class TestAcmeConformance(WorkItemProviderContract):
        known_item_id = "ACME-1"

        @pytest.fixture
        def provider(self):
            return offline_acme_provider()

Or declare a ``conformance`` factory on your ``PluginSpec`` and run the whole
suite without writing any test code:

    python -m etki_api.conformance <your-dist-name> --report out.json

This package needs the ``conformance`` extra (pytest); plain ``import etki_api``
never touches it.
"""

from etki_api.conformance.code_repo import CodeRepositoryProviderContract
from etki_api.conformance.documents import DocumentSourceProviderContract
from etki_api.conformance.embedding import EmbeddingProviderContract
from etki_api.conformance.llm import LLMClientContract
from etki_api.conformance.registry_metadata import RegistryMetadataProviderContract
from etki_api.conformance.rerank import RerankProviderContract
from etki_api.conformance.work_items import WorkItemProviderContract

# PortName → contract class (the runner binds spec.conformance() instances here).
CONTRACTS: dict[str, type] = {
    "work_items": WorkItemProviderContract,
    "code_repo": CodeRepositoryProviderContract,
    "documents": DocumentSourceProviderContract,
    "llm": LLMClientContract,
    "embedding": EmbeddingProviderContract,
    "rerank": RerankProviderContract,
    "registry_metadata": RegistryMetadataProviderContract,
}

__all__ = [
    "CONTRACTS",
    "CodeRepositoryProviderContract",
    "DocumentSourceProviderContract",
    "EmbeddingProviderContract",
    "LLMClientContract",
    "RegistryMetadataProviderContract",
    "RerankProviderContract",
    "WorkItemProviderContract",
]
