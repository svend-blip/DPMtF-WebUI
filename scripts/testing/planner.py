"""Deterministic test-plan engine with monotonic scope ladder.

The scope ladder: symbol < file < component < broad < full.
In Run 004 only component, broad, and full are reachable.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from typing import Any

__all__ = ["plan_tests", "SCOPES", "PlanError", "TestPlan"]

SCOPES: tuple[str, ...] = ("symbol", "file", "component", "broad", "full")

_REACHABLE: set[str] = frozenset(("component", "broad", "full"))


class PlanError(Exception):
    """Raised for invalid or unresolvable planning inputs."""


class TestPlan:
    """Immutable test-plan result.

    Attributes
    ----------
    requested_scope:
        Caller's hint, or ``None``.
    resolved_scope:
        Deterministic scope, member of ``SCOPES``.
    selected_tests:
        Sorted list of repo-relative test paths.
    affected_components:
        Sorted list of component names with changed paths.
    escalation_reason:
        Always non-empty; names the deciding rule.
    policy_hash:
        SHA-256 from ``policy.policy_hash``.
    plan_hash:
        64-char SHA-256 over canonical serialization.
    is_exhaustive:
        ``True`` when ``resolved_scope`` is ``"broad"`` or ``"full"``.
    """

    __slots__ = (
        "requested_scope",
        "resolved_scope",
        "selected_tests",
        "affected_components",
        "escalation_reason",
        "policy_hash",
        "plan_hash",
        "is_exhaustive",
    )

    def __init__(
        self,
        *,
        requested_scope: str | None,
        resolved_scope: str,
        selected_tests: list[str],
        affected_components: list[str],
        escalation_reason: str,
        policy_hash: str,
    ) -> None:
        self.requested_scope = requested_scope
        self.resolved_scope = resolved_scope
        self.selected_tests = sorted(selected_tests)
        self.affected_components = sorted(affected_components)
        self.escalation_reason = escalation_reason
        self.policy_hash = policy_hash
        # Set is_exhaustive eagerly (computed from resolved_scope)
        self.is_exhaustive = resolved_scope in ("broad", "full")
        # Compute plan_hash eagerly — canonical serialization over all fields
        canonical = {
            "affected_components": self.affected_components,
            "escalation_reason": self.escalation_reason,
            "is_exhaustive": self.is_exhaustive,
            "policy_hash": self.policy_hash,
            "requested_scope": self.requested_scope,
            "resolved_scope": self.resolved_scope,
            "selected_tests": self.selected_tests,
        }
        serialized = json.dumps(
            canonical, sort_keys=True, separators=(", ", ": ")
        )
        self.plan_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _scope_index(scope: str) -> int:
    """Return numeric index of scope in SCOPES.

    Parameters
    ----------
    scope:
        A scope string that must be a member of ``SCOPES``.

    Returns
    -------
    int
        The zero-based index of *scope* within ``SCOPES``.
    """
    try:
        return SCOPES.index(scope)
    except ValueError:
        raise PlanError(f"Unknown scope: '{scope}' not in {SCOPES}")


def _scope_max(a: str, b: str) -> str:
    """Return the stronger of two scopes.

    Parameters
    ----------
    a:
        First scope string.
    b:
        Second scope string.

    Returns
    -------
    str
        The stronger scope (higher index in SCOPES).
    """
    if _scope_index(a) >= _scope_index(b):
        return a
    return b


def _segment_to_regex(segment: str) -> str:
    """Convert a single glob segment to a regex pattern.

    ``*`` within the segment matches any non-empty sequence of
    characters that does not include ``/``.  ``?`` matches any
    single non-``/`` character.  All other characters are escaped.

    Parameters
    ----------
    segment:
        A single path segment (no ``/`` characters) from the glob
        pattern, e.g. ``*.py`` or ``test_??``.

    Returns
    -------
    str
        A regex string that matches the segment.
    """
    regex_parts: list[str] = []
    i = 0
    n = len(segment)
    while i < n:
        c = segment[i]
        if c == "*":
            regex_parts.append("[^/]*")
            i += 1
        elif c == "?":
            regex_parts.append("[^/]")
            i += 1
        else:
            regex_parts.append(re.escape(c))
            i += 1
    return "".join(regex_parts)


def _match_glob(path: str, pattern: str) -> bool:
    """Match path against glob pattern.

    Handles ``**`` as a recursive directory wildcard (zero or more
    path components). Plain ``*`` matches any characters within a
    single path component (does NOT cross ``/`` boundaries).

    Parameters
    ----------
    path:
        The file path to check.
    pattern:
        The glob pattern to match against.

    Returns
    -------
    bool
        ``True`` if *path* matches *pattern*.
    """
    if "**" not in pattern:
        # No recursive wildcards — split by / and match component-by-component.
        # This ensures * does not cross path boundaries (unlike fnmatch).
        path_parts = path.split("/")
        pattern_parts = pattern.split("/")
        if len(path_parts) != len(pattern_parts):
            return False
        for pp, pat in zip(path_parts, pattern_parts):
            regex = _segment_to_regex(pat)
            if not re.fullmatch(regex, pp):
                return False
        return True

    # Has ** wildcards — convert to regex in one pass.
    regex_parts: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*" and i + 1 < n and pattern[i + 1] == "*":
            # ** wildcard
            if i + 2 < n and pattern[i + 2] == "/":
                # **/ → (.+/)? (zero or more directories with trailing /)
                regex_parts.append("(.+/)?")
                i += 3  # skip **/
            elif regex_parts and regex_parts[-1] == "/":
                # /** at end → (/.*)? (zero or more trailing directories)
                regex_parts.pop()  # remove the trailing /
                regex_parts.append("(/.*)?")
                i += 2
            else:
                # standalone ** → .*
                regex_parts.append(".*")
                i += 2
        elif c == "*":
            regex_parts.append("[^/]*")
            i += 1
        elif c == "/":
            regex_parts.append("/")
            i += 1
        else:
            regex_parts.append(re.escape(c))
            i += 1

    regex = "".join(regex_parts)
    return bool(re.fullmatch(regex, path))


def _component_for_path(
    policy: Any, path: str
) -> tuple[str | None, list[str]]:
    """Resolve path against policy to find component(s).

    Parameters
    ----------
    policy:
        A ``Policy`` instance.
    path:
        The source file path to classify.

    Returns
    -------
    tuple[str | None, list[str]]
        ``(component_or_none, list_of_claimant_names)``.

    Raises
    ------
    PlanError
        When ``policy.component_for()`` raises ``PolicyError``
        (ambiguous ownership), the error is re-raised as ``PlanError``.
    """
    try:
        comp = policy.component_for(path)
    except PolicyError as exc:
        # Re-raise as PlanError with the original message
        raise PlanError(str(exc)) from exc

    if comp is not None:
        return (comp, [comp])
    return (None, [])


def _is_high_fanout(path: str, policy: Any) -> bool:
    """Check if path matches any high_fanout_files entry.

    Parameters
    ----------
    path:
        The file path to check.
    policy:
        A ``Policy`` instance with ``high_fanout_files``.

    Returns
    -------
    bool
        ``True`` if *path* matches any high-fanout pattern.
    """
    for pattern in policy.high_fanout_files:
        if _match_glob(path, pattern):
            return True
    return False


def _is_full_regression_trigger(path: str, policy: Any) -> bool:
    """Check if path matches any full_regression_triggers entry.

    Parameters
    ----------
    path:
        The file path to check.
    policy:
        A ``Policy`` instance with ``full_regression_triggers``.

    Returns
    -------
    bool
        ``True`` if *path* matches any full-regression pattern.
    """
    for pattern in policy.full_regression_triggers:
        if _match_glob(path, pattern):
            return True
    return False


def _collect_dependent_components(
    component: str,
    dependencies: dict[str, list[str]],
) -> set[str]:
    """Return component and every component that transitively depends on it.

    ``dependencies`` maps component → its own dependencies.
    We want reverse dependencies: components whose dependency chain
    reaches *component*.

    Parameters
    ----------
    component:
        The target component to find reverse dependencies for.
    dependencies:
        Mapping of component name to its direct dependencies.

    Returns
    -------
    set[str]
        The target component plus all components that depend on it.
    """
    # Build reverse map from all known components (keys + referenced values)
    all_components: set[str] = set(dependencies)
    for deps in dependencies.values():
        all_components.update(deps)

    reverse: dict[str, set[str]] = {comp: set() for comp in all_components}
    for comp, deps in dependencies.items():
        for dep in deps:
            if dep in reverse:
                reverse[dep].add(comp)

    # BFS from component through reverse map
    result: set[str] = {component}
    queue: deque[str] = deque([component])

    while queue:
        current = queue.popleft()
        for dependent in reverse.get(current, set()):
            if dependent not in result:
                result.add(dependent)
                queue.append(dependent)

    return result


def _collect_tests_for_components(
    components: set[str],
    policy: Any,
) -> set[str]:
    """Collect all test-glob entries for components from policy.test_mappings.

    Parameters
    ----------
    components:
        Set of component names.
    policy:
        A ``Policy`` instance with ``test_mappings``.

    Returns
    -------
    set[str]
        All test-glob patterns associated with the given components.
    """
    tests: set[str] = set()
    for comp in components:
        if comp in policy.test_mappings:
            tests.update(policy.test_mappings[comp])
    return tests


def _resolve_scope_for_change(
    path: str,
    policy: Any,
) -> tuple[str, str]:
    """Determine scope and reason for a single changed path.

    Classification rules (first match wins):

    1. ``full_regression_triggers`` matches → ``(full, reason)``
    2. No component + high_fanout → ``(broad, reason)``
    3. No component + no high_fanout → ``(broad, reason)``
    4. Component + no test mapping → ``(broad, reason)``
    5. Component + has test mapping → ``(component, reason)``

    Parameters
    ----------
    path:
        The changed file path.
    policy:
        A ``Policy`` instance.

    Returns
    -------
    tuple[str, str]
        ``(scope_str, reason_str)``.
    """
    # Rule 1: full regression trigger
    if _is_full_regression_trigger(path, policy):
        reason = (
            f"path '{path}' matches full_regression_triggers pattern"
        )
        return ("full", reason)

    # Rule 1b: high fanout escalates to broad regardless of component
    if _is_high_fanout(path, policy):
        reason = (
            f"path '{path}' is a high_fanout_file"
        )
        return ("broad", reason)

    # Resolve component
    comp, claimants = _component_for_path(policy, path)

    if comp is None:
        # No component claims this path
        reason = (
            f"path '{path}' has no owning component"
        )
        return ("broad", reason)

    # Component found — check test mapping
    if comp in policy.test_mappings and policy.test_mappings[comp]:
        reason = (
            f"path '{path}' belongs to component '{comp}' with test mappings"
        )
        return ("component", reason)
    else:
        reason = (
            f"path '{path}' belongs to component '{comp}' but has no test mappings"
        )
        return ("broad", reason)


def plan_tests(
    repo_root: str,
    policy: Any,
    changes: dict[str, str],
    requested_scope: str | None = None,
) -> TestPlan:
    """Deterministic test-plan engine with monotonic scope ladder.

    The scope ladder: symbol < file < component < broad < full.
    In this Run only component, broad, and full are reachable.
    A deterministic rule may move rightward when uncertainty or impact grows.
    Nothing moves leftward.

    ``requested_scope`` is a HINT. If deterministic resolution is stronger,
    the resolution wins. The difference is recorded in ``escalation_reason``.

    Parameters
    ----------
    repo_root:
        Absolute path to the repository root (unused by the engine itself;
        included for API compatibility with callers).
    policy:
        A ``Policy`` instance with component definitions, test mappings,
        dependencies, high-fanout lists, and regression triggers.
    changes:
        Dict of repository-relative paths to change labels
        (e.g. ``{"src/app.py": "modified", "tests/test_app.py": "added"}``).
    requested_scope:
        Optional caller hint for minimum scope strength. May be
        overridden upward by deterministic rules.

    Returns
    -------
    TestPlan
        A deterministic test plan with resolved scope, selected tests,
        and affected components.

    Raises
    ------
    PlanError
        When planning inputs are invalid or unresolvable.
    """
    # Start with requested_scope as the baseline resolution
    if requested_scope and requested_scope in SCOPES:
        current_scope = requested_scope
        escalation_reason = (
            f"requested scope: {requested_scope}"
        )
    else:
        current_scope = SCOPES[0]  # "symbol" — weakest possible
        escalation_reason = "no requested scope provided"

    # Empty policy — no components, mappings, or triggers — forces full regression
    if (
        not policy.components
        and not policy.test_mappings
        and not policy.high_fanout_files
        and not policy.full_regression_triggers
        and not policy.component_dependencies
    ):
        current_scope = "full"
        escalation_reason = "policy has no components, test mappings, or triggers — full regression required"

    # Track all per-path resolutions for the escalation reason
    path_resolutions: list[tuple[str, str, str]] = []

    # Process each changed path individually
    all_affected_components: set[str] = set()
    all_tests: set[str] = set()

    for path, label in changes.items():
        per_path_scope, reason = _resolve_scope_for_change(path, policy)
        path_resolutions.append((path, per_path_scope, reason))

        # Monotonicity: resolved scope is the MAX of all per-path scopes
        current_scope = _scope_max(current_scope, per_path_scope)

        # Collect affected components
        if per_path_scope == "component":
            comp, claimants = _component_for_path(policy, path)
            if comp:
                all_affected_components.add(comp)
                # Also collect reverse dependencies (components that depend on this one)
                reverse_deps = _collect_dependent_components(
                    comp, policy.component_dependencies
                )
                for dep_comp in reverse_deps:
                    if dep_comp != comp:
                        all_affected_components.add(dep_comp)

    # Build escalation reason summary
    if current_scope != (requested_scope or SCOPES[0]):
        escalation_reason = (
            f"escalated from {requested_scope or 'symbol'} to {current_scope} "
            f"due to {len(path_resolutions)} path(s) requiring stronger scope"
        )
    elif len(path_resolutions) == 1:
        escalation_reason = path_resolutions[0][2]
    else:
        escalation_reason = (
            f"resolved to {current_scope} across {len(path_resolutions)} path(s); "
            f"strongest per-path scope is {current_scope}"
        )

    # Collect tests based on resolved scope
    if current_scope == "component" and all_affected_components:
        test_globs = _collect_tests_for_components(
            all_affected_components, policy
        )
        # test_globs are glob patterns; for component scope we collect the patterns
        all_tests.update(test_globs)
    elif current_scope in ("broad", "full"):
        # For broad/full, collect all test mappings across all components
        all_tests.update(_collect_tests_for_components(
            set(policy.test_mappings.keys()), policy
        ))

    # Mandatory smoke tests are included at every scope level
    all_tests.update(policy.mandatory_smoke_tests)

    return TestPlan(
        requested_scope=requested_scope,
        resolved_scope=current_scope,
        selected_tests=sorted(all_tests),
        affected_components=sorted(all_affected_components),
        escalation_reason=escalation_reason,
        policy_hash=policy.policy_hash,
    )
