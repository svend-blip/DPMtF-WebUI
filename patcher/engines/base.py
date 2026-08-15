"""Base class for deterministic patch engines (spec §36).

Concrete engines (`GitDiffEngine` for unified diffs, and — in a later
handoff — `LibCSTEngine` for structural Python transformations) inherit
from `PatchEngine` and override `check()` and `apply()`.

The two methods take a `PatchRequest` and return a `PatchResult`. The
facade (`patcher.service.DeterministicPatcher`) is responsible for any
schema-level validation and dispatch; engines receive a request that
already passes the facade's checks.
"""

from __future__ import annotations

from patcher.models import PatchRequest, PatchResult


class PatchEngine:
    """Abstract base for deterministic patch engines.

    `check()` validates the request against the engine's semantics
    WITHOUT mutating the repository. `apply()` performs the mutation.

    Both methods must be safe to call multiple times in succession and
    must return a `PatchResult` on every code path — never raise to the
    caller except for genuinely unexpected internal errors (which should
    surface as `PATCH_INTERNAL_ERROR`).
    """

    name: str = "patch_engine"

    def check(self, request: PatchRequest) -> PatchResult:  # noqa: D401
        """Dry-run validation. Must NOT mutate the repository."""
        raise NotImplementedError(
            f"{type(self).__name__}.check() is not implemented"
        )

    def apply(self, request: PatchRequest) -> PatchResult:  # noqa: D401
        """Apply the requested mutation. Must be atomic on failure."""
        raise NotImplementedError(
            f"{type(self).__name__}.apply() is not implemented"
        )
