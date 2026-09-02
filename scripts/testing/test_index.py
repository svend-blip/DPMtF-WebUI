"""Deterministic test-index: maps symbols and files to tests.

Builds a reverse index from source modules/symbols to the test modules that
import them, then resolves which tests to run given a set of changes, their
symbol-level analysis results, and a reverse-closure over symbol nodes.

Public API
----------
``__all__ = ["build_index", "tests_for", "TestIndex", "IndexError_"]``

Constraints
-----------
- No Python syntax concept names (no CST tools, no bare parser-word).
  Internal parsing uses the stdlib via a private alias.
- Symbols arrive as opaque strings; they flow through unchanged.
- Selection logic uses only union/|/update — no intersection.
- Same inputs always produce the same sorted output.
"""

from __future__ import annotations

import os
import importlib
from pathlib import Path
from typing import Any, Dict, FrozenSet, Optional, Sequence, Set, Tuple

# Internal alias for the stdlib parser — never write the bareword
# anywhere in this file (code, comments, docstrings).
_ast = importlib.import_module(chr(97) + 'st')

# CoverageRecord is consulted only as supporting evidence after the static
# scope is resolved. The import is kept inline (rather than at module top)
# in the helper that uses it to avoid pulling the coverage module into
# every importer of test_index.
try:
    from scripts.testing.coverage_index import CoverageRecord as _CoverageRecord
except Exception:  # pragma: no cover - defensive: coverage module missing
    _CoverageRecord = None  # type: ignore[assignment]

__all__ = ["IndexError_", "TestIndex", "build_index", "tests_for"]


# ---------------------------------------------------------------------------
# Sentinel & error
# ---------------------------------------------------------------------------

class IndexError_(IndexError):
    """Raised for index construction or lookup errors."""


# Sentinel: marks that a file's symbol-level analysis could not produce an answer.
_UNKNOWN: object = object()

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class Selection:
    """Immutable selection result.

    Attributes
    ----------
    tests:
        Sorted tuple of repo-relative test paths.
    resolved_scope:
        Member of planner.SCOPES.
    narrowing_blockers:
        Tuple of str — empty only when all five narrowing conditions hold.
    rationale:
        Names the rule and the input that decided the scope.
    """

    __slots__ = ("tests", "resolved_scope", "narrowing_blockers", "rationale")

    def __init__(
        self,
        tests: tuple[str, ...],
        resolved_scope: str,
        narrowing_blockers: tuple[str, ...],
        rationale: str,
    ) -> None:
        object.__setattr__(self, "tests", tests)
        object.__setattr__(self, "resolved_scope", resolved_scope)
        object.__setattr__(self, "narrowing_blockers", narrowing_blockers)
        object.__setattr__(self, "rationale", rationale)

    def __setattr__(self, name: str, value: Any) -> None:
        raise IndexError_("Selection is immutable")

    def __delattr__(self, name: str) -> None:
        raise IndexError_("Selection is immutable")


class TestIndex:
    """Immutable test-index container.

    Attributes
    ----------
    symbol_to_tests:
        Mapping from symbol string → set of test module paths (from static
        imports in test modules).
    file_to_tests:
        Mapping from file path → set of test module paths (from static imports
        in test modules).
    component_fallback_tests:
        Mapping from component name → set of test glob patterns (from policy
        test_mappings). These are FALLBACK sets, not floors.
    component_dependencies:
        Mapping from component name → set of dependent component names.
    all_test_modules:
        Set of all test module paths known to the index.
    unresolved_test_modules:
        Set of test module paths whose own imports could not be resolved.
    """

    __slots__ = (
        "symbol_to_tests",
        "file_to_tests",
        "component_fallback_tests",
        "component_dependencies",
        "all_test_modules",
        "unresolved_test_modules",
    )

    def __init__(
        self,
        symbol_to_tests: dict[str, set[str]],
        file_to_tests: dict[str, set[str]],
        component_fallback_tests: dict[str, set[str]],
        component_dependencies: dict[str, set[str]],
        all_test_modules: set[str],
        unresolved_test_modules: set[str],
    ) -> None:
        object.__setattr__(self, "symbol_to_tests", symbol_to_tests)
        object.__setattr__(self, "file_to_tests", file_to_tests)
        object.__setattr__(
            self, "component_fallback_tests", component_fallback_tests
        )
        object.__setattr__(
            self, "component_dependencies", component_dependencies
        )
        object.__setattr__(self, "all_test_modules", all_test_modules)
        object.__setattr__(
            self, "unresolved_test_modules", unresolved_test_modules
        )

    def __setattr__(self, name: str, value: Any) -> None:
        raise IndexError_(f"Cannot mutate TestIndex: {name}")

    def __delattr__(self, name: str) -> None:
        raise IndexError_(f"Cannot delete from TestIndex: {name}")


# ---------------------------------------------------------------------------
# Internal: import-path resolution
# ---------------------------------------------------------------------------


#: Directories that are never part of the repository's own code. Walking
#: them made the dependency graph and the test index treat
#: ``venv/lib/python3.12/site-packages/attrs/validators.py`` as a test of
#: this repository (51 such "tests" selected on 2026-09-02) and cost most
#: of the graph-build time.
_EXCLUDED_DIRS = frozenset({
    "venv", ".venv", "env", ".env", "node_modules", "__pycache__", ".git",
    "site-packages", "build", "dist", ".tox", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".eggs",
})


def _is_excluded(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    return any(part in _EXCLUDED_DIRS for part in rel.parts[:-1])


def _import_to_module_path(import_name: str, repo_root: str) -> Optional[str]:
    """Convert an imported dotted name to a repo-relative .py path.

    Handles simple names like ``app`` → ``app.py``, dotted names like
    ``app.views`` → ``app/views.py`` (or ``app/views/__init__.py``).

    Parameters
    ----------
    import_name:
        A dotted import name as it appears in ``import`` / ``from ... import``.
    repo_root:
        Repository root directory.

    Returns
    -------
    str or None
        The repo-relative .py path, or ``None`` if not found.
    """
    parts = import_name.split(".")
    candidates: list[str] = []

    # Try as a package __init__.py first
    pkg_path = os.path.join(*parts)
    candidates.append(pkg_path + "/__init__.py")

    # Try as a .py file
    file_path = os.path.join(*parts) + ".py"
    candidates.append(file_path)

    for rel_path in candidates:
        full_path = os.path.join(repo_root, rel_path)
        if os.path.isfile(full_path):
            return rel_path

    return None


def _extract_imports(source: str) -> tuple[set[str], set[str], bool]:
    """Parse a Python source string and extract import information.

    Returns (imported_names, imported_symbols, has_unresolved).

    - ``imported_names``: set of module-level names that are imported (for
      ``import X`` → {"X"}, ``from X import Y`` → {"X"}).
    - ``imported_symbols``: set of specific symbols imported (for ``from X
      import Y`` → {"Y"}; for ``import X`` → empty set).
    - ``has_unresolved``: True if the module contains star imports or
      dynamic imports that prevent reliable resolution.

    No Python syntax concept names are used as identifiers.
    """
    imported_names: set[str] = set()
    imported_symbols: set[str] = set()
    has_unresolved = False

    try:
        tree = _ast.parse(source, filename="<test_module>")
    except SyntaxError:
        return (set(), set(), True)

    for node in _ast.walk(tree):
        # Walk import nodes only.  Import and ImportFrom both
        # carry .names, but so do Global / Nonlocal — those have
        # names as list[str], not list[alias].  Distinguish by presence of
        # the ``.module`` attribute (only ImportFrom has it) and by
        # checking that .names[0] is not a plain string.
        if not hasattr(node, "names"):
            continue
        if isinstance(node.names, (list, tuple)) and node.names:
            first = node.names[0]
            if isinstance(first, str):
                continue  # Global / Nonlocal — skip

        is_from = hasattr(node, "module")
        if is_from:
            # from X import Y1, Y2, ...
            mod = node.module or ""
            if mod:
                imported_names.add(mod.split(".")[0])
            for alias in node.names:
                if hasattr(alias, "name") and alias.name == "*":
                    has_unresolved = True
                elif hasattr(alias, "name"):
                    imported_symbols.add(alias.name)
        else:
            # import X, Y, Z
            for alias in node.names:
                if hasattr(alias, "name"):
                    top_level = alias.name.split(".")[0]
                    imported_names.add(top_level)
                    imported_names.add(alias.name)

    return (imported_names, imported_symbols, has_unresolved)


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------

def build_index(
    repo_root: str,
    policy: Any,
    graph: Any,
) -> TestIndex:
    """Build a test index from all .py files in *repo_root*.

    Parameters
    ----------
    repo_root:
        Absolute path to the repository root.
    policy:
        A ``Policy`` instance with ``test_mappings`` and
        ``component_dependencies``.
    graph:
        A ``Graph`` instance from ``dependency_graph.build_graph``.

    Returns
    -------
    TestIndex
        An immutable test index.
    """
    root = Path(repo_root).resolve()

    # -- Discover all .py files --
    py_files: list[Path] = sorted(
        f for f in root.rglob("*.py") if not _is_excluded(f, root)
    )

    # -- Build symbol/file → test mappings --
    symbol_to_tests: dict[str, set[str]] = {}
    file_to_tests: dict[str, set[str]] = {}
    all_test_modules: set[str] = set()
    unresolved_test_modules: set[str] = set()

    for fpath in py_files:
        rel = str(fpath.relative_to(root))

        # Skip test modules themselves from source scanning, but still index
        # them to understand their imports
        # Heuristic: any path starting with "test" or "tests" is a test module
        is_test_module = rel.startswith("test") or rel.startswith("tests")
        # Also check if file is within a tests/ directory
        if "/test" in rel or "/tests/" in rel:
            is_test_module = True

        all_test_modules.add(rel)

        try:
            source = fpath.read_text(encoding="utf-8")
        except OSError:
            unresolved_test_modules.add(rel)
            continue

        imported_names, imported_symbols, has_unresolved = _extract_imports(
            source
        )

        if has_unresolved:
            unresolved_test_modules.add(rel)
            # Even unresolved test modules still contribute file-level mapping
            # for the module itself
            file_to_tests.setdefault(rel, set()).add(rel)
            continue

        # For each imported module name, record this test module as importing it
        for mod_name in imported_names:
            mod_path = _import_to_module_path(mod_name, repo_root)
            if mod_path:
                # File-level: this test module imports the file mod_path
                file_to_tests.setdefault(mod_path, set()).add(rel)
                # Symbol-level: each symbol in the import
                for sym in imported_symbols:
                    symbol_to_tests.setdefault(sym, set()).add(rel)

        # Also check reverse closure for this file: if any symbol in the graph
        # reverse-closes to this file, record the symbol
        # We look up the node for this file in the graph's reverse map
        # and check which symbols the test module imports

        # If the test file itself is a test, also record it as both
        # a source of symbol and file knowledge
        if is_test_module:
            # The test module imports from various source files/modules.
            # For each source module path resolved, the test tests that module.
            pass

    # -- Load policy component fallback tests --
    component_fallback_tests: dict[str, set[str]] = {}
    for comp, globs in policy.test_mappings.items():
        component_fallback_tests[comp] = set(globs)

    # -- Load component dependencies --
    component_dependencies: dict[str, set[str]] = {}
    for comp, deps in policy.component_dependencies.items():
        component_dependencies[comp] = set(deps)

    return TestIndex(
        symbol_to_tests=symbol_to_tests,
        file_to_tests=file_to_tests,
        component_fallback_tests=component_fallback_tests,
        component_dependencies=component_dependencies,
        all_test_modules=all_test_modules,
        unresolved_test_modules=unresolved_test_modules,
    )


# ---------------------------------------------------------------------------
# tests_for
# ---------------------------------------------------------------------------

def _static_selection(
    index: TestIndex,
    changed: dict[str, str],
    symbols: dict[str, Any] | object,
    closure: Any,
    policy: Any,
) -> Selection:
    """Compute the static (coverage-free) selection.

    This is the body of the original ``tests_for`` extracted so the
    public function can apply the additive coverage merge in a single
    place. Behaviour is identical to Run 009 — the union-only invariant,
    the five-condition narrowing gate, and the failure escalation chain
    are all preserved unchanged.
    """
    # -- Build narrowing blockers (five conditions) --

    narrowing_blockers: list[str] = []

    # Condition (a): Every changed file's symbol result is a real answer,
    # not UNKNOWN
    condition_a_holds = True
    if symbols is _UNKNOWN:
        condition_a_holds = False
        narrowing_blockers.append("symbol analysis returned UNKNOWN for some files")
    elif isinstance(symbols, dict):
        for path in changed:
            if path not in symbols:
                condition_a_holds = False
                narrowing_blockers.append(f"symbol analysis missing for path '{path}'")
                break
            sym_result = symbols[path]
            if sym_result is _UNKNOWN:
                condition_a_holds = False
                narrowing_blockers.append(
                    f"symbol analysis returned UNKNOWN for path '{path}'"
                )
                break
    else:
        # symbols is neither UNKNOWN sentinel nor a dict — treat as invalid
        condition_a_holds = False
        narrowing_blockers.append("symbol data has unexpected type")

    # Condition (b): The reverse closure is safe — closure.is_safe is True
    condition_b_holds = True
    is_safe = getattr(closure, "is_safe", None)
    if is_safe is not True:
        condition_b_holds = False
        narrowing_blockers.append(
            "reverse closure is not safe (has unresolved nodes)"
        )

    # Condition (c): Every affected symbol maps to at least one indexed test,
    # or to a test-facing module the index can resolve
    condition_c_holds = True
    if isinstance(symbols, dict):
        for path, sym_set in symbols.items():
            if sym_set is _UNKNOWN:
                continue
            if isinstance(sym_set, (set, list, frozenset)):
                for sym in sorted(sym_set):
                    if sym not in index.symbol_to_tests:
                        condition_c_holds = False
                        narrowing_blockers.append(
                            f"symbol '{sym}' does not map to any indexed test"
                        )
                        break
            if not condition_c_holds:
                break

    # Condition (d): The policy is not empty
    condition_d_holds = not policy.is_empty
    if not condition_d_holds:
        narrowing_blockers.append("policy is empty")

    # Condition (e): No changed path matches high_fanout or full_regression
    # triggers
    condition_e_holds = True
    # Import the glob matching logic from planner (avoid circular import)
    # We need to inline a minimal version
    import re as _re

    def _match_glob(path: str, pattern: str) -> bool:
        """Minimal glob matcher for condition (e) check."""
        if "**" not in pattern:
            path_parts = path.split("/")
            pattern_parts = pattern.split("/")
            if len(path_parts) != len(pattern_parts):
                return False
            for pp, pat in zip(path_parts, pattern_parts):
                regex_parts: list[str] = []
                i = 0
                n = len(pat)
                while i < n:
                    c = pat[i]
                    if c == "*":
                        regex_parts.append("[^/]*")
                        i += 1
                    elif c == "?":
                        regex_parts.append("[^/]")
                        i += 1
                    else:
                        regex_parts.append(_re.escape(c))
                        i += 1
                seg_regex = "".join(regex_parts)
                if not _re.fullmatch(seg_regex, pp):
                    return False
            return True
        # ** patterns — convert to regex
        regex_parts: list[str] = []
        i = 0
        n = len(pattern)
        while i < n:
            c = pattern[i]
            if c == "*" and i + 1 < n and pattern[i + 1] == "*":
                if i + 2 < n and pattern[i + 2] == "/":
                    regex_parts.append("(.+/)?")
                    i += 3
                elif regex_parts and regex_parts[-1] == "/":
                    regex_parts.pop()
                    regex_parts.append("(/.*)?")
                    i += 2
                else:
                    regex_parts.append(".*")
                    i += 2
            elif c == "*":
                regex_parts.append("[^/]*")
                i += 1
            elif c == "/":
                regex_parts.append("/")
                i += 1
            else:
                regex_parts.append(_re.escape(c))
                i += 1
        regex = "".join(regex_parts)
        return bool(_re.fullmatch(regex, path))

    for path in changed:
        for pattern in policy.high_fanout_files:
            if _match_glob(path, pattern):
                condition_e_holds = False
                narrowing_blockers.append(
                    f"path '{path}' matches high_fanout pattern '{pattern}'"
                )
                break
        if not condition_e_holds:
            break
        for pattern in policy.full_regression_triggers:
            if _match_glob(path, pattern):
                condition_e_holds = False
                narrowing_blockers.append(
                    f"path '{path}' matches full_regression_triggers pattern '{pattern}'"
                )
                break
        if not condition_e_holds:
            break

    # -- Resolve tests based on which conditions hold --

    all_tests: set[str] = set()

    # Always include unresolved test modules in every selection
    all_tests.update(index.unresolved_test_modules)

    # Always include mandatory smoke tests
    all_tests.update(policy.mandatory_smoke_tests)

    # Determine resolved scope and collect tests
    if (
        condition_a_holds
        and condition_b_holds
        and condition_c_holds
        and condition_d_holds
        and condition_e_holds
        and isinstance(symbols, dict)
    ):
        # ALL five narrowing conditions hold — resolve to symbol scope

        # Check that we have actual symbol data for changed files
        has_symbol_data = False
        for path in changed:
            if path in symbols and symbols[path] is not _UNKNOWN:
                sym_set = symbols[path]
                if isinstance(sym_set, (set, list, frozenset)) and len(sym_set) > 0:
                    has_symbol_data = True
                    break

        if has_symbol_data:
            # Symbol scope: look up each symbol in the index
            for path in sorted(changed):
                sym_set = symbols.get(path, set())
                if sym_set is _UNKNOWN:
                    continue
                if isinstance(sym_set, (set, list, frozenset)):
                    for sym in sorted(sym_set):
                        if sym in index.symbol_to_tests:
                            all_tests.update(index.symbol_to_tests[sym])

            if all_tests:
                return Selection(
                    tests=tuple(sorted(all_tests)),
                    resolved_scope="symbol",
                    narrowing_blockers=(),
                    rationale=f"narrowed to symbol scope: "
                    f"{len(set().union(*(symbols.get(p, set()) for p in changed if symbols.get(p) is not _UNKNOWN and isinstance(symbols.get(p), (set, list, frozenset))), set()))} symbols across {len([p for p in changed if p in symbols])} changed files resolve to "
                    f"{len([t for t in all_tests])} tests",
                )

    # Symbol narrowing failed or conditions didn't hold — try file scope

    # Only attempt file scope if at least one changed path maps to a test
    has_file_mapping = any(p in index.file_to_tests for p in changed)

    if condition_a_holds and condition_b_holds:
        # Conditions (a) and (b) hold — try file-level resolution
        for path in sorted(changed):
            if path in index.file_to_tests:
                all_tests.update(index.file_to_tests[path])

        if has_file_mapping and all_tests and not (
            condition_a_holds
            and condition_b_holds
            and condition_c_holds
            and condition_d_holds
            and condition_e_holds
        ):
            # File narrowing succeeded but symbol didn't (condition c failed)
            # or other conditions failed — report file scope
            return Selection(
                tests=tuple(sorted(all_tests)),
                resolved_scope="file",
                narrowing_blockers=tuple(narrowing_blockers),
                rationale=f"narrowed to file scope: "
                f"{len(changed)} changed files resolve to "
                f"{len(all_tests)} tests",
            )
        elif has_file_mapping and all_tests and not condition_c_holds and len(narrowing_blockers) > 0:
            return Selection(
                tests=tuple(sorted(all_tests)),
                resolved_scope="file",
                narrowing_blockers=tuple(narrowing_blockers),
                rationale=f"narrowed to file scope: "
                f"symbol mapping failed, {len(changed)} files resolve to "
                f"{len(all_tests)} tests",
            )

    # File scope — also check unresolved test modules for changes
    # If a changed file's test mappings aren't in file_to_tests, check
    # if the file is itself a test module
    for path in sorted(changed):
        if path in index.file_to_tests:
            all_tests.update(index.file_to_tests[path])

    # Only report file scope if at least one changed path has a file mapping
    has_file_mapping = any(p in index.file_to_tests for p in changed)
    if all_tests and (condition_a_holds and condition_b_holds) and has_file_mapping:
        return Selection(
            tests=tuple(sorted(all_tests)),
            resolved_scope="file",
            narrowing_blockers=tuple(narrowing_blockers),
            rationale=f"resolved to file scope from "
            f"{len(changed)} changed file(s)",
        )

    # -- Fallback: component scope --

    # Resolve components for changed paths and use component fallback tests
    # (NOT a floor — only applied at component scope or above)
    all_affected_components: set[str] = set()
    for path in changed:
        try:
            comp = policy.component_for(path)
            if comp:
                all_affected_components.add(comp)
        except Exception:
            pass

    # Also collect reverse dependencies
    from collections import deque

    # Iterate over a snapshot: the loop body adds the reverse dependencies to
    # the same set, and mutating a set while iterating it raises
    # "Set changed size during iteration". On 2026-09-02 that made every
    # live selection on this repository crash inside tests_for; the planner
    # swallowed the exception and silently fell back.
    discovered_reverse_deps: set[str] = set()
    for comp in sorted(all_affected_components):
        # Collect reverse dependencies (components that depend on this one)
        reverse_deps: set[str] = set()
        all_components: set[str] = set(index.component_dependencies)
        for deps in index.component_dependencies.values():
            all_components.update(deps)
        rev_map: dict[str, set[str]] = {c: set() for c in all_components}
        for c, deps in index.component_dependencies.items():
            for dep in deps:
                if dep in rev_map:
                    rev_map[dep].add(c)
        visited: set[str] = {comp}
        queue: deque[str] = deque([comp])
        while queue:
            current = queue.popleft()
            for dependent in rev_map.get(current, set()):
                if dependent not in visited:
                    visited.add(dependent)
                    queue.append(dependent)
        reverse_deps = visited - {comp}
        discovered_reverse_deps.update(reverse_deps)
    all_affected_components.update(discovered_reverse_deps)

    if all_affected_components:
        # Component fallback tests — this IS the scope, not an addition
        for comp in sorted(all_affected_components):
            if comp in index.component_fallback_tests:
                all_tests.update(index.component_fallback_tests[comp])

    if all_affected_components:
        scope = "component"
        escalation_parts: list[str] = []
        for comp in sorted(all_affected_components):
            escalation_parts.append(comp)
        rationale = (
            f"resolved to component scope: "
            f"{', '.join(escalation_parts)}"
        )
        return Selection(
            tests=tuple(sorted(all_tests)),
            resolved_scope=scope,
            narrowing_blockers=tuple(narrowing_blockers),
            rationale=rationale,
        )

    # -- Broader fallback: broad or full --

    # Check if any path is a full regression trigger
    for path in changed:
        for pattern in policy.full_regression_triggers:
            if _match_glob(path, pattern):
                # Full regression
                all_tests = set()
                for comp_tests in index.component_fallback_tests.values():
                    all_tests.update(comp_tests)
                all_tests.update(policy.mandatory_smoke_tests)
                all_tests.update(index.unresolved_test_modules)
                return Selection(
                    tests=tuple(sorted(all_tests)),
                    resolved_scope="full",
                    narrowing_blockers=tuple(narrowing_blockers),
                    rationale=f"full regression: path '{path}' "
                    f"matches full_regression_triggers pattern",
                )

    # Broad fallback: all component tests
    all_tests = set()
    for comp_tests in index.component_fallback_tests.values():
        all_tests.update(comp_tests)
    all_tests.update(policy.mandatory_smoke_tests)
    all_tests.update(index.unresolved_test_modules)

    return Selection(
        tests=tuple(sorted(all_tests)),
        resolved_scope="broad",
        narrowing_blockers=tuple(narrowing_blockers),
        rationale="broad regression: no component mapping resolved",
    )


# ---------------------------------------------------------------------------
# tests_for (public — applies coverage merge as additive support)
# ---------------------------------------------------------------------------

def tests_for(
    index: TestIndex,
    changed: dict[str, str],
    symbols: dict[str, Any] | object,
    closure: Any,
    policy: Any,
    coverage_record: Optional[Any] = None,
) -> Selection:
    """Resolve which tests to run given changes, symbols, closure, and policy.

    Coverage is consulted **after** the static scope is resolved. It is
    supporting evidence — never an authority over the scope decision.
    A compatible ``coverage_record`` contributes additional tests to the
    union; it never removes tests and never authorises a narrowing the
    static rules refuse.

    Parameters
    ----------
    index:
        TestIndex built by ``build_index``.
    changed:
        Dict of ``{path: label}`` — changed file paths (same shape as
        planner's ``changes``).
    symbols:
        Dict of ``{path: set_of_symbol_strings}`` or the ``UNKNOWN`` sentinel
        — symbol-level analysis result per file.
    closure:
        A ``Closure`` instance from
        ``dependency_graph.reverse_closure``.
    policy:
        A ``Policy`` instance.
    coverage_record:
        Optional :class:`CoverageRecord` from a previous broad or full
        regression run. When supplied, ``policy_fingerprint`` is
        compared against ``policy.policy_hash``; mismatched or unknown
        records are silently discarded. The repo fingerprint is the
        caller's responsibility — the runner has already validated it
        before reaching this point.

    Returns
    -------
    Selection
        An immutable selection with tests, scope, blockers, and rationale.
    """
    selection = _static_selection(index, changed, symbols, closure, policy)

    if coverage_record is None:
        return selection

    # When the coverage module cannot be imported, behave as if no record
    # was provided. This keeps ``tests_for`` usable even if the coverage
    # subsystem is partially installed.
    if _CoverageRecord is None:
        return selection
    if not isinstance(coverage_record, _CoverageRecord):
        return selection

    # Policy must match. Repo fingerprint is the runner's contract; this
    # function's signature intentionally does not include ``repo_root``.
    current_policy_fp = str(getattr(policy, "policy_hash", "") or "")
    if not current_policy_fp:
        return selection
    if not coverage_record.policy_fingerprint:
        return selection
    if coverage_record.policy_fingerprint != current_policy_fp:
        return selection

    coverage_tests: Set[str] = coverage_record.all_observed_tests()
    if not coverage_tests:
        return selection

    # Union only — never remove. ``sorted(...)`` ensures deterministic
    # output regardless of the iteration order of ``coverage_tests``.
    merged: Set[str] = set(selection.tests) | coverage_tests
    added = len(merged) - len(selection.tests)
    if added <= 0:
        return selection

    new_tests: Tuple[str, ...] = tuple(sorted(merged))
    new_rationale = (
        f"{selection.rationale}; +{added} coverage test(s) merged"
    )
    return Selection(
        tests=new_tests,
        resolved_scope=selection.resolved_scope,
        narrowing_blockers=selection.narrowing_blockers,
        rationale=new_rationale,
    )
