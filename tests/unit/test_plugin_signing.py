"""signing.py wiring: the unit boundary is OUR plumbing (exact bytes + bundle +
pinned identity reach the verifier), not sigstore's cryptography — that runs
live in a scheduled workflow once the external index repo exists."""

import pytest
from etki.plugin import signing


class _RecordingVerifier:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[dict] = []

    def verify(self, artifact, bundle_json, *, identity, issuer):
        self.calls.append(
            {"artifact": artifact, "bundle": bundle_json, "identity": identity, "issuer": issuer}
        )
        if self.fail:
            raise ValueError("imza geçersiz")


def test_exact_bytes_and_pinned_identity_reach_the_verifier(monkeypatch):
    monkeypatch.delenv(signing.ENV_IDENTITY, raising=False)
    fake = _RecordingVerifier()
    signing.verify_index_bytes(b"index-bytes", b"bundle-bytes", _verifier=fake)
    (call,) = fake.calls
    assert call["artifact"] == b"index-bytes"  # raw bytes, parsed only AFTER verify
    assert call["bundle"] == b"bundle-bytes"
    assert call["identity"] == signing.DEFAULT_IDENTITY
    assert call["issuer"] == signing.DEFAULT_ISSUER
    assert "etki-plugins" in call["identity"]  # pinned to the index repo's workflow


def test_identity_env_override(monkeypatch):
    monkeypatch.setenv(signing.ENV_IDENTITY, "https://github.com/fork/x/.github/workflows/r.yml@refs/tags/")
    fake = _RecordingVerifier()
    signing.verify_index_bytes(b"i", b"b", _verifier=fake)
    assert fake.calls[0]["identity"].startswith("https://github.com/fork/x/")


def test_verification_failure_is_a_signing_error():
    with pytest.raises(signing.SigningError, match="BAŞARISIZ"):
        signing.verify_index_bytes(b"tampered", b"b", _verifier=_RecordingVerifier(fail=True))


def test_missing_sigstore_gives_an_actionable_message(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_sigstore(name, *args, **kwargs):
        if name.startswith("sigstore"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_sigstore)
    with pytest.raises(signing.SigningError, match=r"etki\[plugins\]"):
        signing.verify_index_bytes(b"i", b"b")