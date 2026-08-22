#!/usr/bin/env python3
"""Harness resolution and launch-command building for DPMtF roles.

The preferred_cloud_harness flow treats *role*, *model*, *harness* and
*execution lifecycle* as related but separable concerns. This module is the
DPMtF-side seam: it preserves the historical consumer surface tested by the
flow regression suite (``resolve_harness``, ``is_native``, ``missing_env``,
``describe_missing``, ``build_launch_command``, ``build_dsh_invocation``,
``build_task_invocation``) while delegating the actual harness identity and
command-shape logic to the standalone ``harness_allocator`` companion
package located via ``config.get_project_path`` (or the ``HARNESS_ALLOCATOR_PATH`` env var).

Delegation boundary (this module never duplicates what the standalone already
owns):

- ``resolve_harness`` — *identity*, with a DPMtF-only fallback to
  ``"opencode"`` so existing role rows without ``default_harness_source`` keep
  working. No silent harness substitution beyond that explicit fallback.
- ``is_native`` / ``missing_env`` / ``describe_missing`` — thin delegates.
- ``build_launch_command`` / ``build_dsh_invocation`` / ``build_task_invocation`` —
  call the standalone's argv builders and re-render to a shell-quoted
  string. The argv-list form is what the standalone's ``execute`` consumes
  for the actual ``subprocess.Popen``; this module continues to expose the
  historical shell-string form so ``harness_terminal.execute`` and any other
  consumer keeps working byte-for-byte.

The model identity still lives in ``bridge_roles.default_model_alias`` (DPMtF
resolves the model first via Model Allocator); this module only renders the
already-resolved alias into the harness's native CLI. No ``resolve_model()``
responsibility, no silent model/harness substitution.

The standalone package is located through ``config.get_project_path`` (or
the ``HARNESS_ALLOCATOR_PATH`` environment variable for tests), never a
hardcoded path. ``config.py`` is out of scope and is never edited here.
"""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config  # noqa: E402

#: Harnesses DPMtF launches directly (the model allocator has no client for them).
#: Re-exported for tests that assert against the historical public attribute.
NATIVE_HARNESSES = ("dsh", "codex")

#: env var -> human description, for a safe, useful error when a credential is missing.
#: Re-exported: delegate answers come from the standalone, but the surface stays.
REQUIRED_ENV = {
    "dsh": {"DEEPSEEK_API_KEY": "DeepSeek Harness direct DeepSeek API"},
    "codex": {"MINIMAX_API_KEY": "Codex MiniMax M3 provider"},
}


def _standalone():
    """The approved standalone ``harness_allocator`` package, lazily imported.

    Located via ``HARNESS_ALLOCATOR_PATH`` (env var override) or
    ``config.get_project_path('harness-allocator')``. Never a hardcoded
    path. Cached on the module so the import cost is paid once.
    """
    cached = getattr(_standalone, "_cache", None)
    if cached is not None:
        return cached
    env_path = os.environ.get("HARNESS_ALLOCATOR_PATH")
    pkg_dir = env_path or config.get_project_path("harness-allocator")
    pkg_parent = str(Path(pkg_dir).resolve())
    if pkg_parent not in sys.path:
        sys.path.insert(0, pkg_parent)
    import harness_allocator as ha  # noqa: E402 — late import by design
    _standalone._cache = ha
    return ha


def resolve_harness(role_config):
    """The harness key for a role, falling back to opencode when no source is set.

    ``role_config`` is a mapping of bridge_roles columns (the same shape
    ``load_role_from_db`` returns). The delegation to the standalone returns
    the empty string when the role carries no harness key; we apply the
    DPMtF-only explicit fallback to ``"opencode"`` here so existing rows
    without ``default_harness_source`` keep routing through the default harness
    (no silent harness substitution beyond that one explicit default).
    """
    ha = _standalone()
    role_dict = role_config if isinstance(role_config, dict) else {}
    harness_key = ha.resolve_harness(role_dict)
    return harness_key or "opencode"


def is_native(harness):
    """True when DPMtF builds the launch command itself for this harness."""
    return _standalone().is_native(harness)


def missing_env(harness):
    """Environment variable names required by a native harness that are unset.

    Returns a list (possibly empty). A non-native harness returns an empty list.
    """
    return _standalone().missing_env(harness)


def describe_missing(harness, missing):
    """A one-line, human-safe error naming what is missing (never the value)."""
    return _standalone().describe_missing(harness, missing)


def get_codex_fresh_context_policy() -> str:
    """The optional Codex fresh-context policy from the standalone allocator."""
    return _standalone().get_codex_fresh_context_policy()


def _model_target_from_role(role_config):
    """Extract the already-resolved model target from a role mapping.

    Pure passthrough: returns the empty string when the role carries no
    model. The standalone package never resolves a model from the role —
    it only ever reads what DPMtF already resolved upstream.
    """
    if not isinstance(role_config, dict):
        return ""
    return (role_config.get("default_model_alias") or "").strip()


def build_launch_command(harness, role_config, cfg=None, task=None):
    """The shell command that starts a native harness.

    - ``codex`` returns the resident TUI command (``codex -m <model>``).
    - ``dsh`` returns the one-shot headless invocation (``dsh --profile
      headless --patch <patch> [task]``).

    Returns a single shell string. Raises ValueError for a non-native harness.
    ``cfg`` defaults to this project's config module and is injectable for
    tests. The implementation delegates to the standalone ``build_launch_argv``
    and renders the resulting argv as a shell-quoted string.
    """
    if cfg is None:
        cfg = config
    if harness == "codex":
        return _codex_command(role_config, cfg)
    if harness == "dsh":
        return build_dsh_invocation(role_config, task, cfg)
    raise ValueError(f"not a native harness: {harness!r}")


def build_dsh_invocation(role_config, task=None, cfg=None):
    """The one-shot DeepSeek Harness invocation: `dsh --profile <profile>
    --patch <patch> [task]`.

    ``task`` is the supervisor turn's prompt/context. When it is supplied it
    is appended as the final argv element; when it is omitted the command
    still resolves (for dry-run resolution and command-surface tests) with
    the profile and patch intact. The profile is whatever
    ``cfg.get_dsh_profile()`` resolves — ``headless`` by default, per the
    verified execution path.

    Implementation: delegates to the standalone ``build_dsh_argv`` and joins
    the resulting argv as a shell-quoted string, so the DPMtF-side string
    surface and the standalone's argv surface never diverge.
    """
    if cfg is None:
        cfg = config
    ha = _standalone()
    argv = ha.build_dsh_argv(
        model_target=_model_target_from_role(role_config),
        task=task,
        cfg=cfg,
    )
    return " ".join(shlex.quote(part) for part in argv)


def build_task_invocation(harness, role_config, task, cfg=None):
    """Build the shell command that executes ``task`` through ``harness``.

    The harness-neutral entry point the Harness Terminal uses: for one-shot
    harnesses it returns the single command that runs ``task``; resident TUIs
    (codex, claude-code, opencode) have no one-shot form and raise, because
    they are driven interactively rather than through the terminal.
    Delegates to the standalone ``build_task_argv`` and re-renders to a
    shell-quoted string.
    """
    if cfg is None:
        cfg = config
    ha = _standalone()
    argv = ha.build_task_argv(
        harness,
        model_target=_model_target_from_role(role_config),
        task=task,
        cfg=cfg,
    )
    return " ".join(shlex.quote(part) for part in argv)


def _codex_command(role_config, cfg):
    """`codex -m <model>` — model selected explicitly, provider from user config.

    Codex's MiniMax M3 provider is configured at the user level (its catalog),
    which the flow deliberately does not duplicate. Passing the model here is
    selection, not configuration — the same way a Claude Code role names its
    alias.

    Implementation: delegates to the standalone ``build_launch_argv('codex', ...)``
    so the argv shape and the shell-quoted string stay in sync.
    """
    ha = _standalone()
    argv = ha.build_launch_argv(
        "codex",
        model_target=_model_target_from_role(role_config),
        cfg=cfg,
    )
    return " ".join(shlex.quote(part) for part in argv)


if __name__ == "__main__":
    print("Harness resolution module — command builder and credential checks only.")
