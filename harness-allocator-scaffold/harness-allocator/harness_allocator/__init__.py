"""Harness Allocator — a standalone, harness-neutral allocator for coding harnesses.

Resolves a role to a harness key, builds the invocation, runs one-shot turns
with atomic framed task transport, and reports status. Independent of any
orchestrator's flows, verdicts, roles, governance, dispatch, and bridge
database.

Primary interface::

    execute(role, harness, model_target, cwd, task) -> {status, output, error,
                                                        elapsed, pid, ...}

Model boundary: ``model_target`` is the already-resolved model target supplied
by Model Allocator. This package never resolves, selects, or substitutes a
model — it only renders the target into the harness's native CLI and reports
its identity.

The package is stdlib-only and owns its own config surface (``config``), which
reads environment variables and an optional ``harness-allocator.ini`` next to
the project root — never another project's config.
"""

from __future__ import annotations

from .adapter import build_dsh_invocation, build_launch_command, build_task_invocation
from .config import get_codex_bin, get_dsh_bin, get_dsh_patch_path, get_dsh_profile
from .definition import (
    NATIVE_HARNESSES,
    REQUIRED_ENV,
    HarnessDefinition,
    describe_missing,
    is_native,
    missing_env,
    model_target_identity,
    resolve_harness,
    resolve_role_key,
)
from .invoke import DEFAULT_HEARTBEAT_INTERVAL, execute, run_command
from .status import DUPLICATE_REQUEST, ERROR, READY, RUNNING, SUCCESS
from .terminal import HARNESS_LABELS, MODEL_LABELS, main, render_banner, run_terminal
from .transport import (
    HEADER_MAGIC,
    FrameReader,
    PayloadIdentity,
    RequestFrame,
    TransportError,
    compute_identity,
    encode_request,
    extract_frame,
    make_request_id,
)

__version__ = "0.2.0"

__all__ = [
    "execute",
    "run_command",
    "run_terminal",
    "main",
    "render_banner",
    "HarnessDefinition",
    "resolve_harness",
    "resolve_role_key",
    "model_target_identity",
    "is_native",
    "missing_env",
    "describe_missing",
    "build_launch_command",
    "build_dsh_invocation",
    "build_task_invocation",
    "get_codex_bin",
    "get_dsh_bin",
    "get_dsh_profile",
    "get_dsh_patch_path",
    "NATIVE_HARNESSES",
    "REQUIRED_ENV",
    "HARNESS_LABELS",
    "MODEL_LABELS",
    "READY",
    "RUNNING",
    "SUCCESS",
    "ERROR",
    "DUPLICATE_REQUEST",
    "DEFAULT_HEARTBEAT_INTERVAL",
    "RequestFrame",
    "PayloadIdentity",
    "TransportError",
    "compute_identity",
    "encode_request",
    "extract_frame",
    "make_request_id",
    "FrameReader",
    "HEADER_MAGIC",
    "__version__",
]
