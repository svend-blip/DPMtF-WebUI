"""Public facade for the Deterministic Patcher (spec §8).

`DeterministicPatcher` is the single entry point roles use. It performs
schema-level validation on the incoming `PatchRequest` and dispatches
to the appropriate engine based on `patch_mode`. It does not know how
any particular engine works — that is the engines' concern.

Schemas validated here:

  * `repo_path` is required and must be a string.
  * `patch_mode` is required and must be a known mode
    (`unified_diff` for now; `structural_python` is recognised but
    rejected with PATCH_UNSUPPORTED_OPERATION until the LibCST engine
    lands in a later handoff).
  * For `unified_diff`, the `patch` field must be a non-empty string.
  * For `structural_python`, the `operations` field must be a non-empty
    list of dicts. The contents are NOT validated here — the LibCST
    engine will own that.

Validation failures return a `PatchResult` with `error_code=PATCH_INVALID`
or `PATCH_UNSUPPORTED_OPERATION`. The facade NEVER raises for caller
mistakes; only `apply()`'s internal implementation may raise on truly
unexpected bugs (which the engines wrap into PATCH_INTERNAL_ERROR).
"""

from __future__ import annotations

from typing import List, Optional

from patcher.engines.git_diff_engine import GitDiffEngine
from patcher.engines.libcst_engine import LibCSTEngine
from patcher.errors import PATCH_INVALID, PATCH_UNSUPPORTED_OPERATION
from patcher.models import PatchRequest, PatchResult


# `structural_python` is recognised by name so callers can be explicit
# about intent — the engine it dispatches to (`LibCSTEngine`) was added
# in Phase 1B; the remaining four §37 operations still return
# PATCH_UNSUPPORTED_OPERATION at the engine layer for individual
# operation names not yet implemented.
_RECOGNISED_MODES = frozenset({"unified_diff", "structural_python"})


class DeterministicPatcher:
    """Facade that dispatches PatchRequests to the right engine.

    The facade owns no state — a single instance is safe to share across
    threads and calls. Engines are instantiated lazily on first dispatch
    so that import-time work stays minimal.
    """

    def __init__(self) -> None:
        self._git_engine = GitDiffEngine()
        self._libcst_engine = LibCSTEngine()

    # ── check ──────────────────────────────────────────────────────────
    def check(self, request: PatchRequest) -> PatchResult:
        """Dry-run validation. Never mutates the repository."""
        schema_error = _validate_schema(request, write_phase=False)
        if schema_error is not None:
            return schema_error

        if request.patch_mode == "unified_diff":
            return self._git_engine.check(request)

        # structural_python dispatches to LibCSTEngine (Phase 1B).
        return self._libcst_engine.check(request)

    # ── apply ──────────────────────────────────────────────────────────
    def apply(self, request: PatchRequest) -> PatchResult:
        """Apply the requested mutation. Atomic on failure."""
        schema_error = _validate_schema(request, write_phase=True)
        if schema_error is not None:
            return schema_error

        if request.patch_mode == "unified_diff":
            return self._git_engine.apply(request)

        # structural_python dispatches to LibCSTEngine (Phase 1B).
        return self._libcst_engine.apply(request)


# ── Schema validation ───────────────────────────────────────────────────


def _validate_schema(
    request: PatchRequest, write_phase: bool
) -> Optional[PatchResult]:
    """Reject malformed PatchRequests BEFORE dispatch.

    Returns a rejection PatchResult, or None if validation passed.
    `write_phase` is informational (some engines might want different
    behaviour in check vs apply); both phases share the same schema
    today.
    """
    if request is None:
        return _invalid("PatchRequest is None")

    if not request.repo_path or not isinstance(request.repo_path, str):
        return _invalid("repo_path is required and must be a string")

    if not request.patch_mode or not isinstance(request.patch_mode, str):
        return _invalid("patch_mode is required and must be a string")

    if request.patch_mode not in _RECOGNISED_MODES:
        return _unsupported(
            f"unknown patch_mode: {request.patch_mode!r}"
        )

    if request.patch_mode == "unified_diff":
        if not isinstance(request.patch, str) or not request.patch.strip():
            return _invalid("unified_diff requires a non-empty patch string")
        if request.operations is not None:
            # A unified_diff request carrying operations is a
            # contradictory payload — reject explicitly so callers learn
            # the distinction.
            return _invalid(
                "unified_diff requests must not carry operations; "
                "use patch_mode='structural_python' for operations"
            )

    if request.patch_mode == "structural_python":
        if not _is_nonempty_list_of_dicts(request.operations):
            return _invalid(
                "structural_python requires a non-empty operations list of objects"
            )

    # base_revision, if provided, must be a 40-char hex string. We
    # validate format here; semantic mismatch is the engine's concern.
    if request.base_revision is not None:
        br = request.base_revision
        if not (isinstance(br, str) and len(br) == 40 and _is_hex(br)):
            return _invalid(
                "base_revision must be a 40-character hex commit hash"
            )

    # allowed_paths, if provided, must be a list of strings.
    if request.allowed_paths is not None:
        if not isinstance(request.allowed_paths, list) or not all(
            isinstance(p, str) and p for p in request.allowed_paths
        ):
            return _invalid("allowed_paths must be a list of non-empty strings")

    return None


def _is_nonempty_list_of_dicts(value: object) -> bool:
    """True iff `value` is a non-empty list of dicts."""
    if not isinstance(value, list) or not value:
        return False
    return all(isinstance(item, dict) for item in value)


def _is_hex(s: str) -> bool:
    return all(c in "0123456789abcdefABCDEF" for c in s)


def _invalid(message: str) -> PatchResult:
    return PatchResult(
        status="rejected",
        applied=False,
        engine="deterministic_patcher",
        files_changed=[],
        files_rejected=[],
        operations_requested=0,
        operations_applied=0,
        resulting_diff=None,
        error_code=PATCH_INVALID,
        error=message,
    )


def _unsupported(message: str) -> PatchResult:
    return PatchResult(
        status="rejected",
        applied=False,
        engine="deterministic_patcher",
        files_changed=[],
        files_rejected=[],
        operations_requested=0,
        operations_applied=0,
        resulting_diff=None,
        error_code=PATCH_UNSUPPORTED_OPERATION,
        error=message,
    )
