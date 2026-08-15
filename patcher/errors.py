"""Stable, machine-readable error codes for the Deterministic Patcher.

The constants here are the canonical names defined in spec §11 of
DETERMINISTIC_PATCHER_SPEC.md. They are reported verbatim in
PatchResult.error_code and must not encode orchestration decisions;
DPMtF decides what to do with them.
"""

# Schema-level rejection: missing fields, contradictory fields, wrong types.
PATCH_INVALID = "PATCH_INVALID"

# Unknown patch_mode (engine dispatch failure).
PATCH_UNSUPPORTED_OPERATION = "PATCH_UNSUPPORTED_OPERATION"

# Referenced target file does not exist on disk.
PATCH_FILE_NOT_FOUND = "PATCH_FILE_NOT_FOUND"

# Path security rejection: traversal, absolute outside-repo, symlink escape,
# unexpected repository root, or allowed_paths violation.
PATCH_PATH_REJECTED = "PATCH_PATH_REJECTED"

# base_revision (if supplied) does not match the current HEAD revision.
PATCH_BASE_MISMATCH = "PATCH_BASE_MISMATCH"

# Structural target not found (e.g. function/method/import missing).
PATCH_TARGET_NOT_FOUND = "PATCH_TARGET_NOT_FOUND"

# Structural target found but ambiguous (e.g. two methods with same name,
# duplicate import name in different modules).
PATCH_TARGET_AMBIGUOUS = "PATCH_TARGET_AMBIGUOUS"

# git apply --check (or equivalent) failed: diff does not apply cleanly.
PATCH_CONFLICT = "PATCH_CONFLICT"

# Generic apply failure (filesystem/IO/perms/etc.).
PATCH_APPLY_FAILED = "PATCH_APPLY_FAILED"

# Successful apply, all requested operations completed.
PATCH_APPLIED = "PATCH_APPLIED"

# Applied but post-apply syntax verification failed (e.g. py_compile error).
PATCH_APPLIED_SYNTAX_FAILED = "PATCH_APPLIED_SYNTAX_FAILED"

# Applied but configured lint command exited non-zero.
PATCH_APPLIED_LINT_FAILED = "PATCH_APPLIED_LINT_FAILED"

# Applied but configured test command exited non-zero.
PATCH_APPLIED_TEST_FAILED = "PATCH_APPLIED_TEST_FAILED"

# Unhandled internal error in the patcher (bug, not user input).
PATCH_INTERNAL_ERROR = "PATCH_INTERNAL_ERROR"


__all__ = [
    "PATCH_INVALID",
    "PATCH_UNSUPPORTED_OPERATION",
    "PATCH_FILE_NOT_FOUND",
    "PATCH_PATH_REJECTED",
    "PATCH_BASE_MISMATCH",
    "PATCH_TARGET_NOT_FOUND",
    "PATCH_TARGET_AMBIGUOUS",
    "PATCH_CONFLICT",
    "PATCH_APPLY_FAILED",
    "PATCH_APPLIED",
    "PATCH_APPLIED_SYNTAX_FAILED",
    "PATCH_APPLIED_LINT_FAILED",
    "PATCH_APPLIED_TEST_FAILED",
    "PATCH_INTERNAL_ERROR",
]
