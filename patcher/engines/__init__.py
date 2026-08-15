"""Concrete patch engines for the Deterministic Patcher.

`PatchEngine` (the abstract base) lives here alongside the
implementations. `GitDiffEngine` ships unified-diff mode; `LibCSTEngine`
ships structural_python mode (Phase 1B subset: `add_import`,
`replace_function`, `add_function`). The remaining four §37 operations
land in a later handoff.
"""

from patcher.engines.base import PatchEngine  # noqa: F401
from patcher.engines.git_diff_engine import GitDiffEngine  # noqa: F401
from patcher.engines.libcst_engine import LibCSTEngine  # noqa: F401


__all__ = ["GitDiffEngine", "LibCSTEngine", "PatchEngine"]
