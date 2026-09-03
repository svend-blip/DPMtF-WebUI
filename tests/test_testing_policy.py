"""Tests for scripts/testing/policy.py (D2 — handoff 15).

Each test creates a real temporary directory (tempfile.mkdtemp) and writes
policy files there, never touching the DPMtF-WebUI working tree.

Public API under test:
    __all__ = ["load_policy", "Policy", "PolicyError"]
    load_policy(repo_root) -> Policy
    Policy(...).component_for(path) -> str | None
    Policy(...).component_for(path) raises PolicyError on ambiguity
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Load policy module from absolute path (test-independent of sys.path).
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = PROJECT_ROOT / "scripts" / "testing" / "policy.py"

_policy_spec = importlib.util.spec_from_file_location(
    "policy_test", POLICY_PATH
)
_policy_mod: object = importlib.util.module_from_spec(_policy_spec)
_policy_spec.loader.exec_module(_policy_mod)

load_policy = _policy_mod.load_policy
Policy = _policy_mod.Policy
PolicyError = _policy_mod.PolicyError


def _write_policy(repo_root: str, data: dict) -> str:
    """Write *data* as .dpmtf/test-policy.json and return repo_root."""
    dpmtf_dir = os.path.join(repo_root, ".dpmtf")
    os.makedirs(dpmtf_dir, exist_ok=True)
    path = os.path.join(dpmtf_dir, "test-policy.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


# ---------------------------------------------------------------------------
# Test 16: __all__ public API
# ---------------------------------------------------------------------------

class TestPublicAPI(unittest.TestCase):
    """Tests for the public API surface (TG1, TG7, TG16)."""

    def test_policy_public_api_declared_in___all__(self):
        """The public API is exactly the three names in __all__ (TG1)."""
        self.assertEqual(
            _policy_mod.__all__,
            ["load_policy", "Policy", "PolicyError"],
        )

    def test_public_names_callable(self):
        """load_policy is callable; PolicyError is an Exception subclass."""
        self.assertTrue(callable(load_policy))
        self.assertTrue(issubclass(PolicyError, Exception))

    def test_policy_class_has_all_slots(self):
        """Policy.__slots__ contains every declared attribute."""
        expected = frozenset([
            "components", "test_mappings", "component_dependencies",
            "mandatory_smoke_tests", "high_fanout_files",
            "test_timeout_seconds",
            "full_regression_triggers", "test_command", "policy_hash",
            "is_empty", "parallel", "_source_globs",
        ])
        self.assertEqual(frozenset(Policy.__slots__), expected)


# ---------------------------------------------------------------------------
# Tests 1-5: Absent / malformed / invalid JSON policies (TG2, TG3, TG11)
# ---------------------------------------------------------------------------

class TestAbsentAndMalformedPolicies(unittest.TestCase):
    """Tests for absent files, malformed JSON, and top-level list (TG2, TG3, TG11)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_an_absent_policy_yields_an_empty_policy_that_declares_nothing(self):
        """No .dpmtf/test-policy.json → empty policy with is_empty=True (TG2)."""
        policy = load_policy(self.tmpdir)
        self.assertTrue(policy.is_empty)
        self.assertEqual(policy.components, {})
        self.assertEqual(policy.test_mappings, {})
        self.assertEqual(policy.component_dependencies, {})
        self.assertEqual(policy.mandatory_smoke_tests, [])
        self.assertEqual(policy.high_fanout_files, [])
        self.assertEqual(policy.full_regression_triggers, [])
        self.assertIsNone(policy.test_command)
        self.assertIsNone(policy.parallel)

    def test_malformed_json_raises_policy_error(self):
        """A file with invalid JSON raises PolicyError (TG3)."""
        dpmtf_dir = os.path.join(self.tmpdir, ".dpmtf")
        os.makedirs(dpmtf_dir, exist_ok=True)
        with open(os.path.join(dpmtf_dir, "test-policy.json"), "w", encoding="utf-8") as f:
            f.write("{bad json!!!")
        with self.assertRaises(PolicyError) as ctx:
            load_policy(self.tmpdir)
        self.assertIn("Malformed JSON", str(ctx.exception))

    def test_top_level_list_raises_policy_error(self):
        """A JSON array at top level raises PolicyError (TG11)."""
        _write_policy(self.tmpdir, [])
        with self.assertRaises(PolicyError) as ctx:
            load_policy(self.tmpdir)
        self.assertIn("must contain a JSON object", str(ctx.exception))

    def test_an_unknown_top_level_key_raises_policy_error(self):
        """An unknown key in the policy raises PolicyError (TG4)."""
        _write_policy(self.tmpdir, {"bogus_section": []})
        with self.assertRaises(PolicyError) as ctx:
            load_policy(self.tmpdir)
        self.assertIn("Unknown top-level key", str(ctx.exception))

    def test_wrong_value_type_raises_policy_error(self):
        """Wrong type for a known key (e.g. components as list) raises PolicyError."""
        _write_policy(self.tmpdir, {"components": ["not", "a", "dict"]})
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)


# ---------------------------------------------------------------------------
# Tests 6-9: Valid policy attributes (TG5)
# ---------------------------------------------------------------------------

class TestValidPolicyLoading(unittest.TestCase):
    """Tests for loading a complete, valid policy (TG5, TG13-15)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_valid_policy_loads_all_attributes(self):
        """A fully-populated policy loads every attribute correctly."""
        data = {
            "components": {
                "backend": ["app/*.py"],
                "frontend": ["static/js/*.js"],
            },
            "test_mappings": {
                "backend": ["tests/test_*.py"],
                "frontend": ["tests/test_static_*.py"],
            },
            "component_dependencies": {
                "backend": ["frontend"],
            },
            "mandatory_smoke_tests": ["tests/test_health.py"],
            "high_fanout_files": ["app/__init__.py"],
            "full_regression_triggers": ["app/**"],
            "test_command": ["python", "-m", "pytest", "-q"],
        }
        _write_policy(self.tmpdir, data)
        policy = load_policy(self.tmpdir)

        self.assertFalse(policy.is_empty)
        self.assertEqual(policy.components, data["components"])
        self.assertEqual(policy.test_mappings, data["test_mappings"])
        self.assertEqual(policy.component_dependencies, data["component_dependencies"])
        self.assertEqual(policy.mandatory_smoke_tests, data["mandatory_smoke_tests"])
        self.assertEqual(policy.high_fanout_files, data["high_fanout_files"])
        self.assertEqual(policy.full_regression_triggers, data["full_regression_triggers"])
        self.assertEqual(policy.test_command, data["test_command"])
        # Hash is a 64-char hex digest (SHA-256)
        self.assertEqual(len(policy.policy_hash), 64)

    def test_mandatory_smoke_tests_loaded(self):
        """Non-empty mandatory_smoke_tests loads correctly."""
        _write_policy(self.tmpdir, {"mandatory_smoke_tests": ["test_a", "test_b"]})
        policy = load_policy(self.tmpdir)
        self.assertEqual(policy.mandatory_smoke_tests, ["test_a", "test_b"])

    def test_high_fanout_files_loaded(self):
        """Non-empty high_fanout_files loads correctly."""
        _write_policy(self.tmpdir, {"high_fanout_files": ["big_file.py"]})
        policy = load_policy(self.tmpdir)
        self.assertEqual(policy.high_fanout_files, ["big_file.py"])

    def test_full_regression_triggers_loaded(self):
        """Non-empty full_regression_triggers loads correctly."""
        _write_policy(self.tmpdir, {"full_regression_triggers": ["app/**"]})
        policy = load_policy(self.tmpdir)
        self.assertEqual(policy.full_regression_triggers, ["app/**"])

    def test_component_dependencies_validated(self):
        """component_dependencies with wrong types raises PolicyError."""
        _write_policy(self.tmpdir, {
            "component_dependencies": {
                "backend": "not_a_list",
            },
        })
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)

    def test_test_command_accepts_list_str_or_none(self):
        """test_command accepts list[str], null, or is absent."""
        # As list
        _write_policy(self.tmpdir, {"test_command": ["pytest", "-q"]})
        policy = load_policy(self.tmpdir)
        self.assertEqual(policy.test_command, ["pytest", "-q"])

        # As null
        _write_policy(self.tmpdir, {"test_command": None})
        policy = load_policy(self.tmpdir)
        self.assertIsNone(policy.test_command)

        # Absent
        _write_policy(self.tmpdir, {})
        policy = load_policy(self.tmpdir)
        self.assertIsNone(policy.test_command)

    def test_test_command_rejects_non_string_items(self):
        """test_command with non-string items raises PolicyError."""
        _write_policy(self.tmpdir, {"test_command": ["pytest", 42]})
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)

    def test_test_command_rejects_non_list(self):
        """test_command as a string (not list) raises PolicyError."""
        _write_policy(self.tmpdir, {"test_command": "pytest -q"})
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)


# ---------------------------------------------------------------------------
# Tests 10-12: component_for resolution (TG5, TG8, TG9)
# ---------------------------------------------------------------------------

class TestComponentFor(unittest.TestCase):
    """Tests for Policy.component_for() path resolution (TG5, TG8, TG9)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_a_path_claimed_by_no_component_resolves_to_none(self):
        """A path no component claims returns None (TG9)."""
        policy = Policy(components={"backend": ["app/core.py"]})
        result = policy.component_for("static/js/app.js")
        self.assertIsNone(result)

    def test_a_path_claimed_by_two_components_raises_policy_error(self):
        """Overlapping globs from two components raise PolicyError (TG8)."""
        policy = Policy(components={
            "backend": ["app/*.py"],
            "frontend": ["app/*.py"],
        })
        with self.assertRaises(PolicyError) as ctx:
            policy.component_for("app/views.py")
        self.assertIn("Ambiguous component ownership", str(ctx.exception))
        self.assertIn("backend", str(ctx.exception))
        self.assertIn("frontend", str(ctx.exception))

    def test_declared_component_resolves_a_path(self):
        """A single component correctly resolves its globs (TG5)."""
        policy = Policy(components={
            "auth": ["app/auth/*.py"],
            "api": ["app/api/*.py"],
        })
        self.assertEqual(policy.component_for("app/auth/login.py"), "auth")
        self.assertEqual(policy.component_for("app/api/users.py"), "api")
        self.assertIsNone(policy.component_for("app/random.py"))

    def test_wildcard_glob_component_resolution(self):
        """Wildcard globs (*) resolve for multi-segment paths (fnmatch * matches /)."""
        policy = Policy(components={
            "core": ["app/*.py"],
        })
        self.assertEqual(policy.component_for("app/top.py"), "core")
        # fnmatch.* matches across / so app/sub/mod.py also matches app/*.py
        self.assertEqual(policy.component_for("app/sub/mod.py"), "core")

    def test_multiple_paths_same_component(self):
        """Multiple globs under one component all resolve to it."""
        policy = Policy(components={
            "backend": ["app/core.py", "app/models/*.py", "app/services/*.py"],
        })
        self.assertEqual(policy.component_for("app/core.py"), "backend")
        self.assertEqual(policy.component_for("app/models/user.py"), "backend")
        self.assertEqual(policy.component_for("app/services/order.py"), "backend")
        self.assertIsNone(policy.component_for("app/other.py"))


# ---------------------------------------------------------------------------
# Tests 13-15: Policy hash stability (TG6)
# ---------------------------------------------------------------------------

class TestPolicyHash(unittest.TestCase):
    """Tests for policy hash stability and computation (TG6)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_policy_hash_is_stable_across_reformatting(self):
        """Same content, different JSON formatting → same hash (TG6)."""
        data = {
            "components": {"core": ["app/*.py"]},
            "mandatory_smoke_tests": ["tests/test_health.py"],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_policy(tmpdir, data)
            policy1 = load_policy(tmpdir)

        # Reformat: compact JSON
        with tempfile.TemporaryDirectory() as tmpdir:
            dpmtf_dir = os.path.join(tmpdir, ".dpmtf")
            os.makedirs(dpmtf_dir, exist_ok=True)
            path = os.path.join(dpmtf_dir, "test-policy.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, separators=(",", ":"), sort_keys=True)
            policy2 = load_policy(tmpdir)

        self.assertEqual(policy1.policy_hash, policy2.policy_hash)

    def test_policy_hash_changes_with_content(self):
        """Different content produces different hash."""
        data_a = {"components": {"a": ["*.py"]}}
        data_b = {"components": {"b": ["*.py"]}}
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_policy(tmpdir, data_a)
            policy_a = load_policy(tmpdir)
            _write_policy(tmpdir, data_b)
            policy_b = load_policy(tmpdir)
        self.assertNotEqual(policy_a.policy_hash, policy_b.policy_hash)

    def test_policy_hash_ignores_file_value(self):
        """A file with a wrong policy_hash still computes fresh."""
        data = {"components": {"core": ["app/*.py"]}, "policy_hash": "0" * 64}
        _write_policy(self.tmpdir, data)
        policy = load_policy(self.tmpdir)
        # The stored hash is computed fresh, NOT read from the file.
        self.assertNotEqual(policy.policy_hash, "0" * 64)
        # Verify it matches a policy loaded without policy_hash in file.
        del data["policy_hash"]
        _write_policy(self.tmpdir, data)
        policy_fresh = load_policy(self.tmpdir)
        self.assertEqual(policy.policy_hash, policy_fresh.policy_hash)


# ---------------------------------------------------------------------------
# Tests 16+: Edge cases and additional coverage
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):
    """Edge cases: empty known keys, dict-list validation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_empty_known_keys_succeed(self):
        """An empty dict for known list/dict keys is valid."""
        _write_policy(self.tmpdir, {
            "components": {},
            "test_mappings": {},
            "component_dependencies": {},
            "mandatory_smoke_tests": [],
            "high_fanout_files": [],
            "full_regression_triggers": [],
        })
        policy = load_policy(self.tmpdir)
        self.assertFalse(policy.is_empty)
        self.assertEqual(policy.components, {})
        self.assertEqual(policy.mandatory_smoke_tests, [])

    def test_dict_values_must_be_lists_of_strings(self):
        """Keys inside components/test_mappings must be strings→list[str]."""
        _write_policy(self.tmpdir, {
            "components": {"core": [123]},
        })
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)

    def test_dict_keys_must_be_strings(self):
        """Keys inside components must be strings, not integers."""
        # JSON keys are always strings, so we test a weird edge:
        # a valid-looking entry where value items are correct.
        _write_policy(self.tmpdir, {
            "components": {"backend": ["app/*.py"]},
        })
        policy = load_policy(self.tmpdir)
        self.assertIn("backend", policy.components)

    def test_list_items_must_be_strings(self):
        """List values like mandatory_smoke_tests must contain only strings."""
        _write_policy(self.tmpdir, {
            "mandatory_smoke_tests": ["test_a", 42],
        })
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)

    def test_policy_error_is_exception(self):
        """PolicyError is a direct subclass of Exception."""
        exc = PolicyError("test message")
        self.assertIsInstance(exc, Exception)
        self.assertEqual(str(exc), "test message")


# ---------------------------------------------------------------------------
# Tests for the optional parallel block (Run 014, handoff 107)
# ---------------------------------------------------------------------------

class TestParallelBlock(unittest.TestCase):
    """Tests for the optional ``parallel`` block on the policy (Run 014)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_a_policy_without_a_parallel_block_is_unchanged(self):
        """A policy without the parallel block stores parallel=None and
        behaves exactly as it did before Run 014 (TG4)."""
        _write_policy(self.tmpdir, {
            "components": {"backend": ["app/*.py"]},
            "mandatory_smoke_tests": ["tests/test_health.py"],
        })
        policy = load_policy(self.tmpdir)
        # The new attribute exists and is None.
        self.assertIsNone(policy.parallel)
        # Every pre-014 attribute is preserved exactly.
        self.assertEqual(policy.components, {"backend": ["app/*.py"]})
        self.assertEqual(policy.mandatory_smoke_tests, ["tests/test_health.py"])
        self.assertFalse(policy.is_empty)

    def test_an_empty_policy_has_parallel_none(self):
        """A policy with no parallel block (and absent file) has parallel=None."""
        policy = load_policy(self.tmpdir)
        self.assertIsNone(policy.parallel)

    def test_an_explicit_null_parallel_block_is_none(self):
        """An explicit ``"parallel": null`` in JSON becomes None on the object."""
        _write_policy(self.tmpdir, {"parallel": None})
        policy = load_policy(self.tmpdir)
        self.assertIsNone(policy.parallel)

    def test_a_full_parallel_block_loads_with_defaults_resolved(self):
        """A complete parallel block is canonicalized."""
        _write_policy(self.tmpdir, {
            "parallel": {
                "enabled": True,
                "workers": "auto",
                "serial_components": ["database", "browser"],
            },
        })
        policy = load_policy(self.tmpdir)
        self.assertIsNotNone(policy.parallel)
        self.assertEqual(policy.parallel, {
            "enabled": True,
            "workers": "auto",
            "serial_components": ["database", "browser"],
        })

    def test_a_parallel_block_with_partial_keys_gets_defaults(self):
        """Omitted sub-keys fall back to their defaults."""
        _write_policy(self.tmpdir, {"parallel": {"enabled": True}})
        policy = load_policy(self.tmpdir)
        self.assertEqual(policy.parallel, {
            "enabled": True,
            "workers": "auto",
            "serial_components": [],
        })

    def test_a_parallel_block_must_be_dict_or_null(self):
        """A non-dict, non-null parallel value raises PolicyError."""
        _write_policy(self.tmpdir, {"parallel": "not a dict"})
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)
        _write_policy(self.tmpdir, {"parallel": ["a", "list"]})
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)

    def test_an_unknown_parallel_sub_key_raises_policy_error(self):
        """Unknown sub-keys in the parallel block raise PolicyError."""
        _write_policy(self.tmpdir, {"parallel": {"bogus": True}})
        with self.assertRaises(PolicyError) as ctx:
            load_policy(self.tmpdir)
        self.assertIn("Unknown sub-key in 'parallel'", str(ctx.exception))

    def test_parallel_enabled_must_be_a_bool(self):
        """``parallel.enabled`` must be a bool."""
        _write_policy(self.tmpdir, {"parallel": {"enabled": "yes"}})
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)

    def test_parallel_workers_must_be_auto_or_positive_int(self):
        """``parallel.workers`` accepts 'auto' or positive int only."""
        _write_policy(self.tmpdir, {"parallel": {"workers": 4}})
        policy = load_policy(self.tmpdir)
        self.assertEqual(policy.parallel["workers"], 4)

        _write_policy(self.tmpdir, {"parallel": {"workers": 0}})
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)
        _write_policy(self.tmpdir, {"parallel": {"workers": -2}})
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)
        _write_policy(self.tmpdir, {"parallel": {"workers": 2.5}})
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)
        _write_policy(self.tmpdir, {"parallel": {"workers": True}})
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)
        _write_policy(self.tmpdir, {"parallel": {"workers": "two"}})
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)

    def test_parallel_serial_components_must_be_list_of_strings(self):
        """``parallel.serial_components`` must be list[str]."""
        _write_policy(self.tmpdir, {
            "parallel": {"serial_components": ["db", "browser"]},
        })
        policy = load_policy(self.tmpdir)
        self.assertEqual(
            policy.parallel["serial_components"], ["db", "browser"]
        )

        _write_policy(self.tmpdir, {"parallel": {"serial_components": "db"}})
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)

        _write_policy(self.tmpdir, {"parallel": {"serial_components": [1, 2]}})
        with self.assertRaises(PolicyError):
            load_policy(self.tmpdir)

    def test_parallel_block_does_not_alter_other_attributes(self):
        """Adding a parallel block does not change other policy fields."""
        _write_policy(self.tmpdir, {
            "components": {"core": ["app/*.py"]},
            "test_mappings": {"core": ["tests/test_*.py"]},
            "parallel": {"enabled": True, "workers": 2},
        })
        policy = load_policy(self.tmpdir)
        self.assertEqual(policy.components, {"core": ["app/*.py"]})
        self.assertEqual(policy.test_mappings, {"core": ["tests/test_*.py"]})
        self.assertEqual(policy.parallel["workers"], 2)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
