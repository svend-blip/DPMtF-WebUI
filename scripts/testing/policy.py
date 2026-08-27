"""Deterministic test-policy model from ``.dpmtf/test-policy.json``."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, List

__all__ = ["load_policy", "Policy", "PolicyError"]

_VALID_TOP_LEVEL_KEYS = frozenset(
    [
        "components",
        "test_mappings",
        "component_dependencies",
        "mandatory_smoke_tests",
        "high_fanout_files",
        "full_regression_triggers",
        "test_command",
        "policy_hash",
    ]
)

_DICT_LIST_KEYS: frozenset[str] = frozenset(
    ["components", "test_mappings", "component_dependencies"]
)

_EMPTY_POLICY_BYTES: bytes = json.dumps(
    {}, separators=(",", ":"), sort_keys=True
).encode("utf-8")

_EMPTY_HASH: str = hashlib.sha256(_EMPTY_POLICY_BYTES).hexdigest()


class PolicyError(Exception):
    """Raised for malformed or ambiguous test-policy data."""


class Policy:
    """Immutable test-policy model loaded from a JSON file.

    Attributes
    ----------
    components:
        Mapping of component name → list of source-glob patterns.
    test_mappings:
        Mapping of component name → list of test-glob patterns.
    component_dependencies:
        Mapping of component name → list of component-name dependencies.
    mandatory_smoke_tests:
        List of test identifiers that must always run.
    high_fanout_files:
        List of source paths that touch many components.
    full_regression_triggers:
        List of file-glob patterns that trigger a full regression suite.
    test_command:
        Optional test-command template (``None`` when not set).
    policy_hash:
        64-character SHA-256 hex digest of the canonical serialization.
    is_empty:
        ``True`` when no policy file was found or it declared nothing.
    """

    __slots__ = (
        "components",
        "test_mappings",
        "component_dependencies",
        "mandatory_smoke_tests",
        "high_fanout_files",
        "full_regression_triggers",
        "test_command",
        "policy_hash",
        "is_empty",
        "_source_globs",
    )

    def __init__(
        self,
        components: dict[str, list[str]] | None = None,
        test_mappings: dict[str, list[str]] | None = None,
        component_dependencies: dict[str, list[str]] | None = None,
        mandatory_smoke_tests: list[str] | None = None,
        high_fanout_files: list[str] | None = None,
        full_regression_triggers: list[str] | None = None,
        test_command: list[str] | None = None,
        is_empty: bool = False,
    ) -> None:
        self.components: dict[str, list[str]] = components or {}
        self.test_mappings: dict[str, list[str]] = test_mappings or {}
        self.component_dependencies: dict[str, list[str]] = (
            component_dependencies or {}
        )
        self.mandatory_smoke_tests: list[str] = mandatory_smoke_tests or []
        self.high_fanout_files: list[str] = high_fanout_files or []
        self.full_regression_triggers: list[str] = full_regression_triggers or []
        self.test_command: list[str] | None = test_command
        self.is_empty: bool = is_empty
        # Pre-computed hash of canonical serialization
        self.policy_hash: str = _compute_policy_hash(self)
        # All source globs flattened for ``component_for`` lookups
        self._source_globs: list[tuple[str, str]] = self._build_source_globs(
            self.components
        )

    @staticmethod
    def _build_source_globs(components: dict[str, list[str]]) -> list[tuple[str, str]]:
        """Flatten ``{component: [globs]}`` → ``[(glob, component), ...]``."""
        out: list[tuple[str, str]] = []
        for comp, globs in components.items():
            for g in globs:
                out.append((g, comp))
        return out

    def component_for(self, path: str) -> str | None:
        """Resolve a source path to its owning component.

        Returns the component name when exactly one component's globs
        match the path, or ``None`` when no component claims it.

        Raises ``PolicyError`` when more than one component claims the
        same path — the error names the path and every claimant.
        """
        import fnmatch

        claimants: list[str] = []
        for glob_pattern, comp_name in self._source_globs:
            if fnmatch.fnmatch(path, glob_pattern):
                claimants.append(comp_name)

        if len(claimants) == 0:
            return None
        if len(claimants) == 1:
            return claimants[0]

        # Ambiguity: >1 component claims this path
        unique_claimants = list(dict.fromkeys(claimants))
        raise PolicyError(
            f"Ambiguous component ownership for path '{path}': "
            f"claimed by {', '.join(unique_claimants)}"
        )

    def _canonical_dict(self) -> dict[str, Any]:
        """Build a dict suitable for canonical serialization.

        Excludes ``None`` values entirely.
        """
        result: dict[str, Any] = {}

        if self.components:
            result["components"] = {k: v for k, v in self.components.items()}
        if self.test_mappings:
            result["test_mappings"] = {
                k: v for k, v in self.test_mappings.items()
            }
        if self.component_dependencies:
            result["component_dependencies"] = {
                k: v for k, v in self.component_dependencies.items()
            }
        if self.mandatory_smoke_tests:
            result["mandatory_smoke_tests"] = list(self.mandatory_smoke_tests)
        if self.high_fanout_files:
            result["high_fanout_files"] = list(self.high_fanout_files)
        if self.full_regression_triggers:
            result["full_regression_triggers"] = list(
                self.full_regression_triggers
            )
        if self.test_command is not None:
            result["test_command"] = list(self.test_command)

        return result


def _compute_policy_hash(policy: Policy) -> str:
    """Return the SHA-256 hex digest of *policy*'s canonical serialization."""
    data = policy._canonical_dict()
    canonical = json.dumps(data, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()


def _validate_value(key: str, value: Any) -> Any:
    """Validate that *value* matches the expected type for *key*.

    Returns the value unchanged on success, or raises ``PolicyError``.
    """
    # policy_hash in JSON is always ignored (computed fresh)
    if key == "policy_hash":
        return None

    # Special handling for test_command which can be list or null
    if key == "test_command":
        if value is None:
            return None
        if not isinstance(value, list):
            raise PolicyError(
                f"Key 'test_command' must be a list or null, got {type(value).__name__}"
            )
        for item in value:
            if not isinstance(item, str):
                raise PolicyError(
                    f"Items in 'test_command' must be strings, got {type(item).__name__}"
                )
        return value

    # Dict keys: must be dict[str, list[str]]
    if key in _DICT_LIST_KEYS:
        if not isinstance(value, dict):
            raise PolicyError(
                f"Key '{key}' must be a dict, got {type(value).__name__}"
            )
        for dict_key, dict_val in value.items():
            if not isinstance(dict_key, str):
                raise PolicyError(
                    f"Keys in '{key}' must be strings, got {type(dict_key).__name__}"
                )
            if not isinstance(dict_val, list):
                raise PolicyError(
                    f"Values in '{key}' must be lists, got {type(dict_val).__name__} for key '{dict_key}'"
                )
            for item in dict_val:
                if not isinstance(item, str):
                    raise PolicyError(
                        f"Items in '{key}[{dict_key}]' must be strings, got {type(item).__name__}"
                    )
        return value

    # List keys: must be list[str]
    if not isinstance(value, list):
        raise PolicyError(
            f"Key '{key}' must be a list, got {type(value).__name__}"
        )
    for item in value:
        if not isinstance(item, str):
            raise PolicyError(
                f"Items in '{key}' must be strings, got {type(item).__name__}"
            )
    return value


def _parse(raw: str) -> dict[str, Any]:
    """Parse a JSON string into a dict, raising ``PolicyError`` on failure.

    Internal seam: swap the parser when a future format change is approved.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise PolicyError(f"Malformed JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise PolicyError(
            "test-policy.json must contain a JSON object at the top level"
        )

    return data


def load_policy(repo_root: str) -> Policy:
    """Load the test policy from ``.dpmtf/test-policy.json``.

    Parameters
    ----------
    repo_root:
        Absolute path to the repository root.

    Returns
    -------
    Policy
        A policy object.  When the policy file does not exist, returns
        an empty ``Policy`` (``is_empty`` is ``True``).

    Raises
    ------
    PolicyError
        When the JSON is malformed, contains unknown top-level keys, or
        has wrong value types for known keys.
    """
    policy_path = os.path.join(repo_root, ".dpmtf", "test-policy.json")

    # Absent file → empty policy
    if not os.path.isfile(policy_path):
        return Policy(is_empty=True)

    try:
        with open(policy_path, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as exc:
        raise PolicyError(f"Cannot read policy file: {exc}") from exc

    data = _parse(raw)

    # Reject unknown top-level keys
    known_keys = set(_VALID_TOP_LEVEL_KEYS)
    for key in data:
        if key not in known_keys:
            raise PolicyError(f"Unknown top-level key: '{key}'")

    # Validate types and build Policy
    components: dict[str, list[str]] = {}
    test_mappings: dict[str, list[str]] = {}
    component_dependencies: dict[str, list[str]] = {}
    mandatory_smoke_tests: list[str] = []
    high_fanout_files: list[str] = []
    full_regression_triggers: list[str] = []
    test_command: list[str] | None = None

    for key, value in data.items():
        validated = _validate_value(key, value)

        if key == "components":
            components = validated
        elif key == "test_mappings":
            test_mappings = validated
        elif key == "component_dependencies":
            component_dependencies = validated
        elif key == "mandatory_smoke_tests":
            mandatory_smoke_tests = validated
        elif key == "high_fanout_files":
            high_fanout_files = validated
        elif key == "full_regression_triggers":
            full_regression_triggers = validated
        elif key == "test_command":
            test_command = validated
        # policy_hash in file is ignored; always computed fresh

    return Policy(
        components=components,
        test_mappings=test_mappings,
        component_dependencies=component_dependencies,
        mandatory_smoke_tests=mandatory_smoke_tests,
        high_fanout_files=high_fanout_files,
        full_regression_triggers=full_regression_triggers,
        test_command=test_command,
        is_empty=False,
    )
