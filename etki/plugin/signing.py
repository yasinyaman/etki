"""Sigstore verification of the marketplace index (keyless, GitHub OIDC).

Ships behind the OPTIONAL extra `etki[plugins]` — the base install and
air-gapped images never pull sigstore. The air-gapped compromise (locked in
the plan): the SIGNATURE is verified on the ONLINE side at mirror time;
inside the closed environment SHA-256 is mandatory and the signature is
optional. `_verifier` is the test seam — the unit boundary is OUR plumbing
(real bytes + bundle + pinned identity reach the verifier), not sigstore's
cryptography (that runs live in a scheduled workflow once the index repo
exists)."""

from __future__ import annotations

import os
from typing import Protocol

# Identity pin: the ONLY workflow allowed to sign the index. Overridable for
# forks/self-hosted marketplaces via env — still env-only, like the policy.
DEFAULT_IDENTITY = (
    "https://github.com/yasinyaman/etki-plugins/.github/workflows/release.yml@refs/tags/"
)
DEFAULT_ISSUER = "https://token.actions.githubusercontent.com"
ENV_IDENTITY = "ETKI_PLUGIN_INDEX_IDENTITY"
ENV_ISSUER = "ETKI_PLUGIN_INDEX_ISSUER"


class SigningError(RuntimeError):
    """Verification failure or missing tooling — callers print, never traceback."""


class IndexVerifier(Protocol):
    """What signing needs from sigstore (or a test fake)."""

    def verify(
        self, artifact: bytes, bundle_json: bytes, *, identity: str, issuer: str
    ) -> None: ...


def _load_sigstore_verifier() -> IndexVerifier:
    try:
        from sigstore.models import Bundle
        from sigstore.verify import Verifier, policy
    except ImportError:
        raise SigningError(
            "sigstore kurulu değil — imza doğrulaması için `etki[plugins]` extra'sını "
            "kurun: uv pip install 'etki[plugins]'. (Air-gapped ortamda imza opsiyoneldir; "
            "SHA-256 zorunluluğu her durumda geçerli.)"
        ) from None

    class _Sigstore:
        def verify(
            self, artifact: bytes, bundle_json: bytes, *, identity: str, issuer: str
        ) -> None:
            bundle = Bundle.from_json(bundle_json)
            Verifier.production().verify_artifact(
                artifact,
                bundle,
                policy.Identity(identity=identity, issuer=issuer),
            )

    return _Sigstore()


def expected_identity() -> tuple[str, str]:
    return (
        os.environ.get(ENV_IDENTITY, DEFAULT_IDENTITY),
        os.environ.get(ENV_ISSUER, DEFAULT_ISSUER),
    )


def verify_index_bytes(
    index_raw: bytes,
    bundle_raw: bytes,
    *,
    _verifier: IndexVerifier | None = None,
) -> None:
    """Raises SigningError unless `index_raw` is exactly what the pinned
    identity signed. The EXACT downloaded bytes are verified — parse afterwards."""
    identity, issuer = expected_identity()
    verifier = _verifier if _verifier is not None else _load_sigstore_verifier()
    try:
        verifier.verify(index_raw, bundle_raw, identity=identity, issuer=issuer)
    except SigningError:
        raise
    except Exception as exc:  # noqa: BLE001 — normalize sigstore's exception zoo
        raise SigningError(f"index imza doğrulaması BAŞARISIZ: {exc}") from exc
