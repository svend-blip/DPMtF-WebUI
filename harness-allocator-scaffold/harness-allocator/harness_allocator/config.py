"""Configuration surface for the Harness Allocator.

Single source of truth for the harness launcher paths, profiles and patch
overlays this package owns. Independent of any orchestrator: it reads only
environment variables and an optional ``harness-allocator.ini`` next to the
project root, never another project's config module.

Sources (in priority order):

1. Environment variables (secrets, infrastructure)
2. ``harness-allocator.ini`` ``[harness]`` section (app-config defaults)
3. Hardcoded fallbacks (last resort, for development only)

There is no ``.env`` loader here: credentials are supplied by the process
environment, so a harness invoked through this package inherits them the way
its own CLI expects.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

#: The ini next to the project root. Optional — env vars cover the defaults.
_INI_PATH = Path(__file__).resolve().parent.parent / "harness-allocator.ini"

_config = configparser.ConfigParser()
if _INI_PATH.exists():
    _config.read(_INI_PATH, encoding="utf-8")


def _ini(section, key, fallback=None):
    return _config.get(section, key, fallback=fallback)


def get_codex_bin() -> str:
    """Codex CLI launcher. Env ``CODEX_BIN``, ini ``[harness] codex_bin``, or ``codex``."""
    env = os.environ.get("CODEX_BIN")
    if env:
        return env
    configured = _ini("harness", "codex_bin")
    return configured or "codex"


def get_dsh_bin() -> str:
    """DeepSeek Harness launcher. Env ``DSH_BIN``, ini ``[harness] dsh_bin``, or npx.

    The default is ``npx @deepseek-ai/dsh`` — the verified non-browser path —
    rather than a hardcoded absolute path, so the harness resolves on any
    machine that has the package installed or reachable via the registry.
    """
    env = os.environ.get("DSH_BIN")
    if env:
        return env
    configured = _ini("harness", "dsh_bin")
    return configured or "npx @deepseek-ai/dsh"


def get_dsh_profile() -> str:
    """DeepSeek Harness profile. Env ``DSH_PROFILE``, ini ``[harness] dsh_profile``, or ``headless``.

    ``headless`` is the one-shot profile: ``dsh --profile headless <task>``
    answers one task, prints the result, and exits. That matches the
    stateless-per-wakeup terminal design.
    """
    env = os.environ.get("DSH_PROFILE")
    if env:
        return env
    configured = _ini("harness", "dsh_profile")
    return configured or "headless"


def get_dsh_patch_path() -> str:
    """Path to the DeepSeek Harness patch overlay for the resolved model target.

    Env ``DSH_V4_PRO_PATCH``, ini ``[harness] dsh_v4_pro_patch``, or empty
    (no overlay). The patch is the caller's already-resolved model-target
    embodiment (Model Allocator sets the env/ini); this getter only passes it
    through. Empty means no overlay is pinned — this package never chooses a
    model, so it never substitutes a patch of its own.
    """
    env = os.environ.get("DSH_V4_PRO_PATCH")
    if env:
        return env
    configured = _ini("harness", "dsh_v4_pro_patch")
    return configured or ""
