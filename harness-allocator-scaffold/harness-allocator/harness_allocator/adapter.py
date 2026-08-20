"""HarnessAdapter — builds the shell command that launches or runs a harness.

All string builders, no process spawning, so the surface is unit-testable
without touching an API. The allocator owns command syntax here; callers ask
for behaviour (``execute``), not a command string.

Model boundary: ``model_target`` is the ALREADY-RESOLVED model target supplied
by Model Allocator (upstream of this package). This module only renders it into
a harness's native CLI syntax — it never resolves, selects, defaults, or
substitutes a model.
"""

from __future__ import annotations

import shlex

from . import config
from .definition import model_target_identity


def build_launch_command(harness, model_target=None, task=None, cfg=None) -> str:
    """The shell command that starts a native harness.

    - ``codex`` -> the resident TUI command (``codex -m <model_target>``).
    - ``dsh``   -> the one-shot headless invocation (``dsh --profile <profile>
      [--patch <patch>] [task]``).

    ``model_target`` is the already-resolved target, rendered verbatim (codex)
    or not used for selection at all (dsh, whose model is pinned by the
    profile/patch the caller configured). Raises ``ValueError`` for a
    non-native harness. ``cfg`` defaults to this package's own config and is
    injectable for tests.
    """
    if cfg is None:
        cfg = config
    if harness == "codex":
        return _codex_command(model_target, cfg)
    if harness == "dsh":
        return build_dsh_invocation(model_target, task, cfg)
    raise ValueError(f"not a native harness: {harness!r}")


def build_dsh_invocation(model_target=None, task=None, cfg=None) -> str:
    """The one-shot DeepSeek Harness invocation.

    ``dsh --profile <profile> [--patch <patch>] [task]``. ``task`` is quoted
    and appended as the final argument; profile and patch come from ``cfg``
    (``headless`` / empty by default). ``model_target`` is accepted for
    call-shape compatibility and deliberately NOT used: the DeepSeek Harness
    model is pinned by the profile/patch the caller (Model Allocator) resolved,
    so the allocator must not re-select it here.
    """
    if cfg is None:
        cfg = config
    parts = shlex.split(cfg.get_dsh_bin())
    parts += ["--profile", cfg.get_dsh_profile()]
    patch = (cfg.get_dsh_patch_path() or "").strip()
    if patch:
        parts += ["--patch", patch]
    if task:
        parts += [task]
    return " ".join(shlex.quote(part) for part in parts)


def build_task_invocation(harness, model_target=None, task=None, cfg=None) -> str:
    """Build the shell command that executes ``task`` through ``harness``.

    The harness-neutral entry point the terminal uses: one-shot harnesses
    return the single command that runs ``task``; resident TUIs (codex,
    claude-code, opencode) have no one-shot form and raise.
    """
    if harness == "dsh":
        return build_dsh_invocation(model_target, task, cfg)
    raise ValueError(f"no one-shot task invocation for harness {harness!r}")


def _codex_command(model_target, cfg) -> str:
    """``codex -m <model_target>`` — the resolved target passed through verbatim.

    Codex's provider is configured at the user level (its catalog), which the
    allocator deliberately does not duplicate. Rendering the caller-supplied
    target here is expression, not selection: the identity came from Model
    Allocator and is neither looked up nor defaulted.
    """
    parts = [cfg.get_codex_bin()]
    model = model_target_identity(model_target)
    if model:
        parts += ["-m", model]
    return " ".join(shlex.quote(part) for part in parts)
