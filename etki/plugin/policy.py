"""Plugin installation policy — the deployment owner's admin lock.

Read DIRECTLY from the environment, deliberately NOT a `Settings` field: the
UI-managed `.etki/llm.json` settings source has TOP priority over env there,
and this one value must never be UI-writable. Making it a plain env read gives
the inverse priority structurally instead of via an exclusion hack (pinned by
test_plugin_policy.py).

Levels are ordered, each includes the previous:

    verified_only (default) — only signed marketplace installs (Faz 5) and the
                              hash-verified offline mirror path
    allow_git                — + git installs pinned to tag/commit
    allow_local              — + local wheel installs (hash mandatory)

Unknown values FAIL CLOSED to verified_only (a typo must not open the gate).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("etki")

ENV_VAR = "ETKI_PLUGIN_POLICY"
DEFAULT_POLICY = "verified_only"

_LEVELS = {"verified_only": 0, "allow_git": 1, "allow_local": 2}
_ACTION_REQUIRES = {"git": 1, "local": 2}


def current_policy() -> str:
    raw = os.environ.get(ENV_VAR, DEFAULT_POLICY).strip().lower()
    if raw not in _LEVELS:
        logger.warning(
            "%s=%r tanınmadı; fail-closed → %s (geçerli: %s)",
            ENV_VAR,
            raw,
            DEFAULT_POLICY,
            ", ".join(_LEVELS),
        )
        return DEFAULT_POLICY
    return raw


def allows(action: str) -> bool:
    """action: "git" | "local"."""
    return _LEVELS[current_policy()] >= _ACTION_REQUIRES[action]


def refusal_message(action: str) -> str:
    return (
        f"{ENV_VAR}={current_policy()} bu kurulum türüne izin vermiyor "
        f"({action!r} için en az {_min_level_name(action)} gerekir). "
        "Bu bir yönetici kilididir; yalnızca ortam değişkeniyle değiştirilir — UI'dan asla."
    )


def _min_level_name(action: str) -> str:
    need = _ACTION_REQUIRES[action]
    return next(name for name, lvl in _LEVELS.items() if lvl == need)
