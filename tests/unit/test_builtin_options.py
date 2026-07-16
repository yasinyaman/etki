"""U4.1 (plugin UI plan): builtin work-item adapters validate through the typed
models in adapters/options.py — sample options build, a missing required key is
a field-level message (not a bare KeyError), extra keys pass through."""

import pytest
from etki.adapters.registry import build_work_items
from etki.config import ConnectorConfig

# Plain values on purpose (no env: refs): _secret resolves references at build
# time and an undefined variable would fail the test for the wrong reason.
SAMPLES: dict[str, dict] = {
    "file": {"path": "samples/demo_project/work_items.json"},
    "jira": {"base_url": "https://x", "email": "e@x", "api_token": "t"},
    "gitlab": {"base_url": "https://x", "project": "grp/proj", "token": "t"},
    "redmine": {"base_url": "https://x", "api_key": "k"},
    "azure_devops": {"organization": "o", "project": "p", "pat": "t"},
}


@pytest.mark.parametrize(("adapter", "options"), SAMPLES.items())
def test_builtin_sample_options_build(adapter: str, options: dict) -> None:
    provider = build_work_items(ConnectorConfig(adapter=adapter, options=options))
    assert provider is not None


@pytest.mark.parametrize("adapter", list(SAMPLES))
def test_missing_required_option_names_the_field(adapter: str) -> None:
    with pytest.raises(ValueError) as exc:  # pydantic.ValidationError subclasses ValueError
        build_work_items(ConnectorConfig(adapter=adapter, options={}))
    first_required = next(iter(SAMPLES[adapter]))
    assert first_required in str(exc.value)


def test_extra_keys_pass_through() -> None:
    options = {**SAMPLES["jira"], "gelecek_alan": "x"}
    assert build_work_items(ConnectorConfig(adapter="jira", options=options)) is not None
