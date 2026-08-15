"""Deterministic Patcher — execution infrastructure for DPMtF.

This package is the strictly additive capability that separates LLM
reasoning from repository mutation (see
`docs/specs/DETERMINISTIC_PATCHER_SPEC.md`). It exposes:

  * `PatchRequest`, `PatchResult` — machine-readable I/O types.
  * `DeterministicPatcher` — the public facade with `check()` / `apply()`.
  * Error-code constants under `patcher.errors`.
  * The engines subpackage (`GitDiffEngine`, `LibCSTEngine`).
  * The post-apply verification pipeline (`patcher.verification`).
  * The audit-metadata builder (`patcher.audit`).

The package does NOT import any model allocator, bridge, or LLM client;
it is pure deterministic infrastructure (spec §6, §23–§24).
"""

from patcher.errors import (  # noqa: F401
    PATCH_APPLIED,
    PATCH_APPLIED_LINT_FAILED,
    PATCH_APPLIED_SYNTAX_FAILED,
    PATCH_APPLIED_TEST_FAILED,
    PATCH_APPLY_FAILED,
    PATCH_BASE_MISMATCH,
    PATCH_CONFLICT,
    PATCH_FILE_NOT_FOUND,
    PATCH_INTERNAL_ERROR,
    PATCH_INVALID,
    PATCH_PATH_REJECTED,
    PATCH_TARGET_AMBIGUOUS,
    PATCH_TARGET_NOT_FOUND,
    PATCH_UNSUPPORTED_OPERATION,
)
from patcher.models import (  # noqa: F401
    PatchRequest,
    PatchResult,
    request_from_dict,
    request_to_dict,
)
from patcher.policy import (  # noqa: F401
    PatchPathRejected,
    RepoState,
    record_repo_state,
    validate_target_path,
    validate_target_paths,
)
from patcher.service import DeterministicPatcher  # noqa: F401


__all__ = [
    "DeterministicPatcher",
    "PatchPathRejected",
    "PatchRequest",
    "PatchResult",
    "RepoState",
    "PATCH_APPLIED",
    "PATCH_APPLIED_LINT_FAILED",
    "PATCH_APPLIED_SYNTAX_FAILED",
    "PATCH_APPLIED_TEST_FAILED",
    "PATCH_APPLY_FAILED",
    "PATCH_BASE_MISMATCH",
    "PATCH_CONFLICT",
    "PATCH_FILE_NOT_FOUND",
    "PATCH_INTERNAL_ERROR",
    "PATCH_INVALID",
    "PATCH_PATH_REJECTED",
    "PATCH_TARGET_AMBIGUOUS",
    "PATCH_TARGET_NOT_FOUND",
    "PATCH_UNSUPPORTED_OPERATION",
    "record_repo_state",
    "request_from_dict",
    "request_to_dict",
    "validate_target_path",
    "validate_target_paths",
]
