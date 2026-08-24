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


def _profile_from_role(role_config):
    """The resolved ``harness_profile`` for a role (or ``""`` when absent).

    The role mapping may carry the key as ``harness_profile`` (D2b's
    ``get_flow_roles`` shape) or as ``default_harness_profile`` (the
    ``load_role_from_db`` shape used by ``relaunch_in_session``). Both
    forms are accepted here so callers do not have to normalise.
    Strips whitespace and returns the empty string on any falsy value —
    the empty string is the "today's behaviour" sentinel for the
    standalone adapter.
    """
    if not isinstance(role_config, dict):
        return ""
    raw = role_config.get("harness_profile")
    if raw is None or raw == "":
        raw = role_config.get("default_harness_profile")
    return (raw or "").strip()


def _apply_codex_profile_env(profile):
    """Export ``CODEX_PROFILE`` when ``profile`` is non-empty; pop it when empty.

    The D1 adapter (harness-allocator) reads the profile through its
    config module, which checks ``CODEX_PROFILE`` from the env first.
    Setting it here makes DPMtF's launch path observable to the adapter
    without DPMtF ever editing its own config.py.

    The contract is asymmetric: a non-empty profile is exported (and
    left set — the role is mid-launch, the env should reflect the
    resolved profile); an empty / absent profile is UNSET (the env var
    MUST NOT carry over from a previous launch — that would silently
    activate a stale profile on a profile-less role).

    Returns the profile string for caller convenience.
    """
    if profile:
        os.environ["CODEX_PROFILE"] = profile
    else:
        os.environ.pop("CODEX_PROFILE", None)
    return profile


class _ProfileAwareCfg:
    """Wraps a DPMtF config with the profile getters the D1 adapter reads.

    Run 024 / D2: the standalone adapter's ``_codex_argv`` reads the
    profile via ``getattr(cfg, "get_codex_profile", lambda: "")()``.
    DPMtF's ``config`` module has no ``get_codex_profile``; left bare,
    the adapter's ``getattr`` falls through to the empty-string lambda
    and the profile is silently ignored.

    This wrapper forwards every other attribute to the wrapped config
    (so today's add-dirs, sandbox, workdir, etc. all keep resolving
    from the real DPMtF values), and exposes the three profile getters
    the adapter calls. The profile getters read from the env, NOT from
    the DPMtF config — the contract is "DPMtF exports CODEX_PROFILE,
    the adapter reads it"; the values live where D2 set them, not
    where some other module might shadow them.

    The gpu sandbox / add-dirs getters carry the DPMtF-side defaults
    (``danger-full-access`` / ``[]``) when no override env is set.
    config.py is OUT OF SCOPE and is never edited here — defaults are
    inlined below because the run-024 §3 fence forbids touching
    config.py.
    """
    def __init__(self, base_cfg):
        # __getattr__ runs only on MISSING attributes, so the attributes
        # we set explicitly below take precedence. Setting them to
        # None here is fine — __getattr__ will not be consulted.
        object.__setattr__(self, "_base", base_cfg)

    def __getattr__(self, name):
        # Forward every other attribute to the real DPMtF config.
        return getattr(self._base, name)

    def get_codex_profile(self):
        """Env ``CODEX_PROFILE`` (set by D2 right before this call).

        Strips whitespace and returns ``""`` when absent — the
        standalone adapter treats empty profile as "today's behaviour".
        """
        env = os.environ.get("CODEX_PROFILE")
        if env is None:
            return ""
        return env.strip()

    def get_codex_profile_gpu_sandbox(self):
        """Override channel for the gpu sandbox mode (DPMtF default: ``danger-full-access``).

        Reads ``CODEX_PROFILE_GPU_SANDBOX`` from the env when set, else
        returns the DPMtF-side default. config.py is out of scope, so
        the default is inlined.
        """
        env = os.environ.get("CODEX_PROFILE_GPU_SANDBOX")
        if env is not None and env.strip():
            return env.strip()
        return "danger-full-access"

    def get_codex_profile_gpu_add_dirs(self):
        """Override channel for the gpu add-dirs (DPMtF default: ``[]``).

        Reads ``CODEX_PROFILE_GPU_ADD_DIRS`` from the env when set
        (colon- or comma-separated), else returns the DPMtF-side
        default of an empty list. config.py is out of scope, so the
        default is inlined.
        """
        raw = os.environ.get("CODEX_PROFILE_GPU_ADD_DIRS")
        if raw is None or not raw.strip():
            return []
        return [p.strip() for p in raw.replace(",", ":").split(":") if p.strip()]


def _codex_command(role_config, cfg):
    """`codex -m <model>` — model selected explicitly, provider from user config.

    Codex's MiniMax M3 provider is configured at the user level (its catalog),
    which the flow deliberately does not duplicate. Passing the model here is
    selection, not configuration — the same way a Claude Code role names its
    alias.

    Implementation: delegates to the standalone ``build_launch_argv('codex', ...)``
    so the argv shape and the shell-quoted string stay in sync.

    Run 024 / D2: the resolved ``harness_profile`` from ``role_config`` is
    exported as ``CODEX_PROFILE`` in the launch environment BEFORE the
    adapter renders the argv. NULL / empty profile unsets the env var, so
    today's launch is byte-identical. The adapter sees the profile
    through a ``_ProfileAwareCfg`` wrapper around the DPMtF config so the
    profile getters resolve from the env without editing config.py.
    """
    profile = _profile_from_role(role_config)
    _apply_codex_profile_env(profile)
    ha = _standalone()
    # ALWAYS wrap so the adapter's ``getattr(cfg, "get_codex_profile")``
    # call returns the env-driven value rather than falling through to
    # the empty-string lambda. When profile is empty the wrapper still
    # reads "" from the env (the env is unset) and the profile-less
    # argv path is byte-identical to today.
    effective_cfg = _ProfileAwareCfg(cfg if cfg is not None else config)
    argv = ha.build_launch_argv(
        "codex",
        model_target=_model_target_from_role(role_config),
        cfg=effective_cfg,
    )
    return " ".join(shlex.quote(part) for part in argv)


if __name__ == "__main__":
    print("Harness resolution module — command builder and credential checks only.")
