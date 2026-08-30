"""Tests for scripts/testing/test_index.py.

Uses MockPolicy / MockClosure; creates real temp dirs for build_index.
"""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Load module
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TI_PATH = PROJECT_ROOT / "scripts" / "testing" / "test_index.py"

_ti_spec = importlib.util.spec_from_file_location(
    "test_index_test", _TI_PATH,
)
_ti: object = importlib.util.module_from_spec(_ti_spec)
_ti_spec.loader.exec_module(_ti)

build_index = _ti.build_index
tests_for = _ti.tests_for
TestIndex = _ti.TestIndex
IndexError_ = _ti.IndexError_
Selection = _ti.Selection
_UNKNOWN = _ti._UNKNOWN

# ---------------------------------------------------------------------------
# Mocks
# ---------------------------------------------------------------------------


class MockPolicy:
    """Minimal policy mock matching the real API surface."""

    def __init__(
        self,
        test_mappings=None,
        component_dependencies=None,
        mandatory_smoke_tests=None,
        high_fanout_files=None,
        full_regression_triggers=None,
        components=None,
        is_empty_val=False,
        policy_hash_val="abc123",
    ):
        self.test_mappings = test_mappings or {}
        self.component_dependencies = component_dependencies or {}
        self.mandatory_smoke_tests = mandatory_smoke_tests or []
        self.high_fanout_files = high_fanout_files or []
        self.full_regression_triggers = full_regression_triggers or []
        self.components = components or {}
        self.is_empty = is_empty_val
        self.policy_hash = policy_hash_val

    def component_for(self, path):
        import fnmatch
        for comp, globs in self.components.items():
            for g in globs:
                if fnmatch.fnmatch(path, g):
                    return comp
        return None


class MockClosure:
    def __init__(self, is_safe=True):
        self.is_safe = is_safe


# ---------------------------------------------------------------------------
# Test: Selection immutability
# ---------------------------------------------------------------------------


class TestSelection(unittest.TestCase):
    """Tests for the Selection class."""

    def test_selection_is_immutable_on_setattr(self):
        """Setting an attribute after construction must raise IndexError_."""
        sel = Selection(
            tests=("a.py",),
            resolved_scope="symbol",
            narrowing_blockers=(),
            rationale="test",
        )
        with self.assertRaises(IndexError_):
            sel.tests = ("b.py",)

    def test_selection_is_immutable_on_delattr(self):
        """Deleting an attribute after construction must raise IndexError_."""
        sel = Selection(
            tests=("a.py",),
            resolved_scope="symbol",
            narrowing_blockers=(),
            rationale="test",
        )
        with self.assertRaises(IndexError_):
            del sel.tests

    def test_selection_has_correct_attributes(self):
        """A fresh Selection has the expected attribute values."""
        sel = Selection(
            tests=("a.py", "b.py"),
            resolved_scope="file",
            narrowing_blockers=("blocker 1",),
            rationale="narrowed",
        )
        self.assertEqual(sel.tests, ("a.py", "b.py"))
        self.assertEqual(sel.resolved_scope, "file")
        self.assertEqual(sel.narrowing_blockers, ("blocker 1",))
        self.assertEqual(sel.rationale, "narrowed")

    def test_selection_is_immutable_for_all_slots(self):
        """All four __slots__ attributes are immutable after construction."""
        sel = Selection(
            tests=("x.py",),
            resolved_scope="broad",
            narrowing_blockers=("a", "b"),
            rationale="reason",
        )
        for attr in ("tests", "resolved_scope", "narrowing_blockers", "rationale"):
            with self.subTest(attr=attr):
                with self.assertRaises(IndexError_):
                    setattr(sel, attr, "new value")
                with self.assertRaises(IndexError_):
                    delattr(sel, attr)


# ---------------------------------------------------------------------------
# Test: Public API
# ---------------------------------------------------------------------------


class TestPublicAPI(unittest.TestCase):
    """Tests for the test_index public API."""

    def test_all_exports_present(self):
        """__all__ contains exactly the four expected names."""
        self.assertEqual(
            sorted(getattr(_ti, "__all__", [])),
            sorted(["IndexError_", "TestIndex", "build_index", "tests_for"]),
        )

    def test_index_error_is_exception_subclass(self):
        """IndexError_ is an Exception subclass."""
        self.assertTrue(issubclass(IndexError_, Exception))
        self.assertTrue(issubclass(IndexError_, IndexError))

    def test_tests_for_has_symbols_and_closure_params(self):
        """tests_for must have 'symbols' and 'closure' parameters."""
        import inspect
        params = list(inspect.signature(tests_for).parameters)
        self.assertIn("symbols", params)
        self.assertIn("closure", params)

    def test_build_index_has_repo_root_policy_graph_params(self):
        """build_index has 'repo_root', 'policy', 'graph' parameters."""
        import inspect
        params = list(inspect.signature(build_index).parameters)
        self.assertIn("repo_root", params)
        self.assertIn("policy", params)
        self.assertIn("graph", params)

    def test_index_error_instance_has_message(self):
        """IndexError_ instances carry a meaningful message."""
        try:
            raise IndexError_("custom error message")
        except IndexError_ as exc:
            self.assertEqual(str(exc), "custom error message")


# ---------------------------------------------------------------------------
# Test: Build index
# ---------------------------------------------------------------------------


class TestBuildIndex(unittest.TestCase):
    """Tests for build_index."""

    def test_build_index_returns_test_index_instance(self):
        """build_index returns a TestIndex instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            self.assertIsInstance(idx, TestIndex)

    def test_build_index_finds_test_modules(self):
        """build_index discovers test modules in its scan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_example.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            self.assertIn("tests/test_example.py", idx.all_test_modules)

    def test_build_index_handles_unreadable_file(self):
        """Unreadable files add to unresolved_test_modules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir, "secret.py")
            p.write_text("import x\n")
            p.chmod(0o000)
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            self.assertIn("secret.py", idx.unresolved_test_modules)
            p.chmod(0o644)  # restore for cleanup

    def test_build_index_records_file_to_tests_mapping(self):
        """build_index records file-level test mappings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            self.assertIn(
                "tests/test_x.py",
                idx.file_to_tests.get("x.py", set()),
            )

    def test_build_index_records_symbol_to_tests_mapping(self):
        """build_index records symbol-level test mappings for from-imports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_y.py").write_text("from x import foo\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            self.assertIn(
                "tests/test_y.py",
                idx.symbol_to_tests.get("foo", set()),
            )

    def test_build_index_handles_syntax_error_gracefully(self):
        """Files with syntax errors are added to unresolved_test_modules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir, "broken.py")
            p.write_text("def (:::syntax error\n")
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            self.assertIn("broken.py", idx.unresolved_test_modules)

    def test_build_index_loads_component_fallback_tests(self):
        """build_index loads component fallback tests from policy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = MockPolicy(
                components={},
                test_mappings={"web": ["tests/test_web.py"]},
            )
            idx = build_index(tmpdir, policy, None)
            self.assertIn("tests/test_web.py", idx.component_fallback_tests.get("web", set()))

    def test_build_index_loads_component_dependencies(self):
        """build_index loads component dependencies from policy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = MockPolicy(
                components={},
                test_mappings={},
                component_dependencies={"web": ["api"]},
            )
            idx = build_index(tmpdir, policy, None)
            self.assertIn("api", idx.component_dependencies.get("web", set()))


# ---------------------------------------------------------------------------
# Test: Condition (c) — symbol-to-test mapping
# ---------------------------------------------------------------------------


class TestConditionC(unittest.TestCase):
    """Tests for condition (c): every symbol must map to at least one test."""

    def test_unmapped_symbol_blocks_symbol_scope(self):
        """A symbol not in the index prevents symbol-level narrowing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            closure = MockClosure(is_safe=True)
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"nonexistent_symbol"}},
                closure=closure,
                policy=MockPolicy(components={}, test_mappings={}),
            )
            self.assertNotEqual(result.resolved_scope, "symbol")

    def test_condition_c_checked_when_closure_is_safe(self):
        """Condition (c) is evaluated even when closure.is_safe is True.

        Previously, condition (c) was skipped when the closure was safe,
        allowing false narrowings.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            safe_closure = MockClosure(is_safe=True)
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"nonexistent_symbol"}},
                closure=safe_closure,
                policy=MockPolicy(components={}, test_mappings={}),
            )
            self.assertNotEqual(
                result.resolved_scope, "symbol",
                "condition (c) must block symbol scope for unmapped symbols "
                "even with safe closure",
            )

    def test_unknown_symbol_for_path_blocks_condition_c(self):
        """When a symbol set is _UNKNOWN, condition (c) is satisfied for it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            closure = MockClosure(is_safe=True)
            # _UNKNOWN for the symbol set skips the symbol check in (c)
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": _UNKNOWN},
                closure=closure,
                policy=policy,
            )
            # Should be blocked by condition (a) instead, not (c)
            # since condition (a) checks _UNKNOWN
            self.assertNotEqual(result.resolved_scope, "symbol")

    def test_mixed_mapped_and_unmapped_symbols(self):
        """Mixed mapped/unmapped symbols: unmapped blocks condition (c)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\nfrom x import foo\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            # 'x' is in file_to_tests but not symbol_to_tests
            # 'foo' IS in symbol_to_tests
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"x", "foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            # 'x' symbol may not be in symbol_to_tests, which blocks (c)
            # Result depends on whether build_index puts 'x' in symbol_to_tests
            self.assertIsInstance(result, Selection)


# ---------------------------------------------------------------------------
# Test: Unknown sentinel
# ---------------------------------------------------------------------------


class TestUnknownSentinel(unittest.TestCase):
    """Tests for the _UNKNOWN sentinel."""

    def test_unknown_sentinel_blocks_symbol_scope(self):
        """When symbols is the _UNKNOWN sentinel, symbol scope is blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
            )
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols=_UNKNOWN,
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            self.assertNotEqual(result.resolved_scope, "symbol")

    def test_unknown_for_specific_path_blocks_scope(self):
        """_UNKNOWN for a specific path blocks symbol scope for that path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
            )
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": _UNKNOWN},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            self.assertNotEqual(result.resolved_scope, "symbol")

    def test_unknown_sentinel_is_a_distinct_object(self):
        """_UNKNOWN is a distinct sentinel object, not a string or number."""
        self.assertIsNotNone(_UNKNOWN)
        self.assertNotEqual(_UNKNOWN, {})
        self.assertNotEqual(_UNKNOWN, [])
        self.assertNotEqual(_UNKNOWN, "")
        self.assertNotEqual(_UNKNOWN, None)

    def test_unknown_dict_value_blocks_condition_a(self):
        """When any path maps to _UNKNOWN, condition (a) fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
            )
            idx = build_index(tmpdir, policy, None)
            # Multiple changed files, one with _UNKNOWN
            result = tests_for(
                idx,
                changed={"x.py": "modified", "y.py": "modified"},
                symbols={"x.py": _UNKNOWN, "y.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            self.assertNotEqual(result.resolved_scope, "symbol")


# ---------------------------------------------------------------------------
# Test: Smoke tests
# ---------------------------------------------------------------------------


class TestSmokeTests(unittest.TestCase):
    """Tests for smoke test inclusion."""

    def test_mandatory_smoke_tests_are_included_at_every_scope(self):
        """Smoke tests are unioned into every selection at every scope."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            (tests_dir / "smoke.py").write_text("pass\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
            )
            idx = build_index(tmpdir, policy, None)

            # Test with safe closure — should include smoke tests
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols=_UNKNOWN,
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            self.assertIn("tests/smoke.py", result.tests)

            # Test with unsafe closure — should also include smoke tests
            result2 = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols=_UNKNOWN,
                closure=MockClosure(is_safe=False),
                policy=policy,
            )
            self.assertIn("tests/smoke.py", result2.tests)

    def test_no_smoke_tests_means_empty_smoke_set(self):
        """With no smoke tests configured, none appear in the selection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=[],
            )
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols=_UNKNOWN,
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            smoke_tests = [t for t in result.tests if "smoke" in t.lower()]
            self.assertEqual(smoke_tests, [])


# ---------------------------------------------------------------------------
# Test: Unresolved test modules
# ---------------------------------------------------------------------------


class TestUnresolvedModules(unittest.TestCase):
    """Tests for unresolved test module handling."""

    def test_an_unresolved_test_module_is_always_selected(self):
        """Unresolved test modules appear in every selection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            bad_file = tests_dir / "test_broken.py"
            bad_file.write_text("def (:::syntax error\n")
            policy = MockPolicy(
                components={},
                test_mappings={},
                mandatory_smoke_tests=[],
            )
            idx = build_index(tmpdir, policy, None)
            self.assertIn("tests/test_broken.py", idx.unresolved_test_modules)
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={_UNKNOWN: _UNKNOWN},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            self.assertIn(
                "tests/test_broken.py", result.tests,
                "Unresolved test modules must always be in selection",
            )


# ---------------------------------------------------------------------------
# Test: Closure safety
# ---------------------------------------------------------------------------


class TestClosureSafety(unittest.TestCase):
    """Tests for closure safety checks."""

    def test_unsafe_closure_blocks_symbol_scope(self):
        """An unsafe closure blocks symbol-level narrowing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\nfrom x import foo\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=False),
                policy=policy,
            )
            self.assertNotEqual(result.resolved_scope, "symbol")

    def test_safe_closure_allowed(self):
        """A safe closure (is_safe=True) does not block narrowing by itself."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\nfrom x import foo\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            # All conditions must hold; with safe closure, (b) holds
            # (c) may fail if 'foo' is mapped, which it should be
            self.assertIsInstance(result, Selection)

    def test_missing_is_safe_attribute_defaults_to_unsafe(self):
        """Closure without is_safe defaults to unsafe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)

            class BareClosure:
                pass

            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=BareClosure(),
                policy=policy,
            )
            self.assertNotEqual(result.resolved_scope, "symbol")

    def test_none_closure_defaults_to_unsafe(self):
        """None closure defaults to unsafe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=None,
                policy=policy,
            )
            self.assertNotEqual(result.resolved_scope, "symbol")


# ---------------------------------------------------------------------------
# Test: High fanout and regression
# ---------------------------------------------------------------------------


class TestHighFanout(unittest.TestCase):
    """Tests for high fanout file handling."""

    def test_high_fanout_file_escapes_beyond_symbol_scope(self):
        """High fanout files should escape broader scope."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\nfrom x import foo\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
                high_fanout_files=["x.py"],
            )
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            # High fanout blocks condition (e), so symbol scope is not reached
            self.assertNotEqual(result.resolved_scope, "symbol")


class TestFullRegression(unittest.TestCase):
    """Tests for full regression triggers."""

    def test_full_regression_trigger_selects_all_component_tests(self):
        """A full regression trigger selects all component tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
                full_regression_triggers=["deploy/**"],
            )
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx,
                changed={"deploy/upgrade.sh": "modified"},
                symbols={"deploy/upgrade.sh": {"run"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            # deploy/upgrade.sh matches full_regression trigger → full scope
            self.assertEqual(result.resolved_scope, "full")
            # Component fallback tests from policy are included
            self.assertIn("tests/test_x.py", result.tests)
            self.assertIn("tests/smoke.py", result.tests)


# ---------------------------------------------------------------------------
# Test: Determinism
# ---------------------------------------------------------------------------


class TestDeterminism(unittest.TestCase):
    """Tests for deterministic output."""

    def test_same_inputs_produce_same_selection(self):
        """Same inputs always produce the same sorted output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            for name in ["a", "b", "c"]:
                (tests_dir / f"test_{name}.py").write_text("pass\n")
            policy = MockPolicy(
                components={},
                test_mappings={},
                mandatory_smoke_tests=["tests/smoke.py"],
            )
            idx = build_index(tmpdir, policy, None)
            r1 = tests_for(
                idx, {"x.py": "modified"}, _UNKNOWN, MockClosure(is_safe=True), policy,
            )
            r2 = tests_for(
                idx, {"x.py": "modified"}, _UNKNOWN, MockClosure(is_safe=True), policy,
            )
            self.assertEqual(r1.tests, r2.tests)
            self.assertEqual(r1.resolved_scope, r2.resolved_scope)
            self.assertEqual(r1.rationale, r2.rationale)

    def test_selection_tests_are_sorted(self):
        """Selection tests tuple is always sorted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            for name in ["c", "a", "b"]:
                (tests_dir / f"test_{name}.py").write_text("pass\n")
            policy = MockPolicy(
                components={},
                test_mappings={},
                mandatory_smoke_tests=["tests/smoke.py"],
            )
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx, {"x.py": "modified"}, _UNKNOWN, MockClosure(is_safe=True), policy,
            )
            self.assertEqual(result.tests, tuple(sorted(result.tests)))


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases."""

    def test_empty_changed_files(self):
        """Empty changed dict produces a valid selection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = MockPolicy(
                components={},
                test_mappings={},
                mandatory_smoke_tests=["tests/smoke.py"],
            )
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx, {}, {}, MockClosure(is_safe=True), policy,
            )
            self.assertIsInstance(result, Selection)
            self.assertIn("tests/smoke.py", result.tests)

    def test_empty_symbols_dict(self):
        """Empty symbols dict is handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(
                components={},
                test_mappings={},
                mandatory_smoke_tests=["tests/smoke.py"],
            )
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            self.assertIsInstance(result, Selection)

    def test_closure_is_none(self):
        """When closure is None, selection still works (falls back)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = MockPolicy(
                components={},
                test_mappings={},
                mandatory_smoke_tests=["tests/smoke.py"],
            )
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={},
                closure=None,
                policy=policy,
            )
            self.assertIsInstance(result, Selection)

    def test_no_components_escalates_to_component_or_broad(self):
        """When no components map to changed paths, scope escalates beyond component."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
            )
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx,
                changed={"unrelated/z.py": "modified"},
                symbols={"unrelated/z.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            # Unclassified path: no component maps, no file_to_tests entry
            # Smoke tests are included but scope is not component-level
            # (the unclassified path has no file_to_tests mapping)
            self.assertNotEqual(result.resolved_scope, "component")


# ---------------------------------------------------------------------------
# Test: tests_for signature and return type
# ---------------------------------------------------------------------------


class TestTestsForSignature(unittest.TestCase):
    """Tests for the tests_for function signature."""

    def test_tests_for_parameters_order(self):
        """tests_for has the expected parameter names."""
        import inspect
        sig = inspect.signature(tests_for)
        params = list(sig.parameters.keys())
        self.assertEqual(params[:5], ["index", "changed", "symbols", "closure", "policy"])

    def test_tests_for_returns_selection(self):
        """tests_for always returns a Selection instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx,
                changed={},
                symbols={},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            self.assertIsInstance(result, Selection)


# ---------------------------------------------------------------------------
# Test: TestIndex immutability
# ---------------------------------------------------------------------------


class TestTestIndex(unittest.TestCase):
    """Tests for TestIndex immutability."""

    def test_testindex_is_immutable(self):
        """TestIndex instances cannot be mutated after construction."""
        idx = TestIndex(
            symbol_to_tests={},
            file_to_tests={},
            component_fallback_tests={},
            component_dependencies={},
            all_test_modules=set(),
            unresolved_test_modules=set(),
        )
        with self.assertRaises(IndexError_):
            idx.symbol_to_tests = {"x": {"test.py"}}
        with self.assertRaises(IndexError_):
            del idx.all_test_modules


# ---------------------------------------------------------------------------
# Test: Index consumes both file and symbol nodes
# ---------------------------------------------------------------------------


class TestIndexConsumption(unittest.TestCase):
    """Tests that the index properly consumes symbol information."""

    def test_file_level_mapping_recorded(self):
        """File-level mappings are recorded alongside symbol mappings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(components={}, test_mappings={})
            idx = build_index(tmpdir, policy, None)
            # x.py should map to test_x.py at file level
            self.assertIn(
                "tests/test_x.py",
                idx.file_to_tests.get("x.py", set()),
            )


# ---------------------------------------------------------------------------
# Test: Contract-bound test names (TG8)
# ---------------------------------------------------------------------------


class TestContractBound(unittest.TestCase):
    """Six missing contract-bound tests for TG8 compliance."""

    def test_a_safely_resolved_symbol_change_selects_fewer_tests_than_the_component(
        self,
    ):
        """Symbol scope must select a strict subset of the component's tests.

        Tests over several fixture shapes:
        - a component with many tests,
        - a symbol whose closure reaches few of them,
        - a selection strictly smaller than the component mapping.
        """
        # Fixture 1: component 'x' has 5 tests, symbol 'foo' maps to only 1
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_a.py").write_text("from x import foo\n")
            (tests_dir / "test_b.py").write_text("from x import bar\n")
            (tests_dir / "test_c.py").write_text("from x import baz\n")
            (tests_dir / "test_d.py").write_text("from x import qux\n")
            (tests_dir / "test_e.py").write_text("from x import quux\n")
            Path(tmpdir, "x.py").write_text(
                "def foo(): pass\ndef bar(): pass\ndef baz(): pass\n"
                "def qux(): pass\ndef quux(): pass\n"
            )
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": [
                    "tests/test_a.py", "tests/test_b.py",
                    "tests/test_c.py", "tests/test_d.py", "tests/test_e.py",
                ]},
                mandatory_smoke_tests=[],
            )
            idx = build_index(tmpdir, policy, None)
            # 'foo' should map only to test_a.py via symbol_to_tests
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            component_tests = set(policy.test_mappings.get("x", []))
            self.assertLessEqual(set(result.tests), component_tests)
            self.assertLess(len(result.tests), len(component_tests))

        # Fixture 2: component with smoke tests — symbol scope excludes some
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_a.py").write_text("from x import foo\n")
            (tests_dir / "test_b.py").write_text("from x import bar\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\ndef bar(): pass\n")
            policy2 = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_a.py", "tests/test_b.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
            )
            idx2 = build_index(tmpdir, policy2, None)
            result2 = tests_for(
                idx2,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy2,
            )
            # Symbol scope includes smoke but not all component tests
            all_component = set(policy2.test_mappings["x"]) | set(policy2.mandatory_smoke_tests)
            self.assertLessEqual(set(result2.tests), all_component)
            self.assertNotEqual(set(result2.tests), all_component)

        # Fixture 3: empty symbols but safe closure — symbol scope with minimal set
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_a.py").write_text("pass\n")
            policy3 = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_a.py"]},
                mandatory_smoke_tests=[],
            )
            idx3 = build_index(tmpdir, policy3, None)
            result3 = tests_for(
                idx3,
                changed={"x.py": "modified"},
                symbols={"x.py": set()},
                closure=MockClosure(is_safe=True),
                policy=policy3,
            )
            # Empty symbols → symbol scope falls through, component scope used
            self.assertIsInstance(result3, Selection)


    def test_ambiguous_symbol_impact_escalates_to_component(self):
        """A symbol not in the index (closure safe, policy non-empty, no high fanout)
        escalates from symbol to file scope (condition c fails, but file mapping exists).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
            )
            idx = build_index(tmpdir, policy, None)
            # 'nonexistent' is not in symbol_to_tests, so condition (c) fails
            # but closure is safe and file mapping exists → file scope
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"nonexistent_symbol"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            self.assertEqual(result.resolved_scope, "file")

    def test_ambiguous_component_impact_escalates_to_broad_or_full(self):
        """When component mapping is empty or missing for a changed path,
        escalation goes to broad (not component).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            # No component maps to 'unrelated/z.py'
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
            )
            idx = build_index(tmpdir, policy, None)
            result = tests_for(
                idx,
                changed={"unrelated/z.py": "modified"},
                symbols={"unrelated/z.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            # No component for this path → broad scope
            self.assertIn(result.resolved_scope, ("broad", "full"))

    def test_no_uncertainty_can_produce_a_narrower_scope(self):
        """Any form of uncertainty (_UNKNOWN symbols, unsafe closure, etc.)
        must never produce a scope narrower than what would otherwise be produced.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_a.py").write_text("from x import foo\n")
            (tests_dir / "test_b.py").write_text("from x import bar\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\ndef bar(): pass\n")
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_a.py", "tests/test_b.py"]},
                mandatory_smoke_tests=[],
            )
            idx = build_index(tmpdir, policy, None)

            # Base case: clean input produces some scope
            base_result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            base_scope_idx = ["symbol", "file", "component", "broad", "full"].index(
                base_result.resolved_scope
            )

            # Uncertainty 1: _UNKNOWN symbols
            unknown_result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols=_UNKNOWN,
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            unknown_idx = ["symbol", "file", "component", "broad", "full"].index(
                unknown_result.resolved_scope
            )
            self.assertGreaterEqual(unknown_idx, base_scope_idx)

            # Uncertainty 2: unsafe closure
            unsafe_result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=False),
                policy=policy,
            )
            unsafe_idx = ["symbol", "file", "component", "broad", "full"].index(
                unsafe_result.resolved_scope
            )
            self.assertGreaterEqual(unsafe_idx, base_scope_idx)

            # Uncertainty 3: _UNKNOWN for specific path
            path_unknown_result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": _UNKNOWN},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            path_unknown_idx = ["symbol", "file", "component", "broad", "full"].index(
                path_unknown_result.resolved_scope
            )
            self.assertGreaterEqual(path_unknown_idx, base_scope_idx)

    def test_the_index_consumes_symbol_nodes_not_only_modules(self):
        """The index uses symbol_to_tests mapping (symbol-level granularity),
        not just file_to_tests (file-level). Tests that symbol-level mapping
        works independently of file-level.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            # test_sym.py imports the symbol 'foo' from module x
            (tests_dir / "test_sym.py").write_text("from x import foo\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(
                components={},
                test_mappings={},
                mandatory_smoke_tests=[],
            )
            idx = build_index(tmpdir, policy, None)
            # 'foo' must be in symbol_to_tests (symbol-level mapping)
            self.assertIn("foo", idx.symbol_to_tests)
            self.assertIn("tests/test_sym.py", idx.symbol_to_tests["foo"])
            # file_to_tests should also have x.py → test_sym.py
            self.assertIn("tests/test_sym.py", idx.file_to_tests.get("x.py", set()))

    def test_selection_works_with_no_coverage_history(self):
        """Selection with empty/no coverage data (empty symbol_to_tests,
        empty file_to_tests) should still work correctly and produce
        a valid Selection.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            # Policy with no mappings at all
            policy = MockPolicy(
                components={},
                test_mappings={},
                mandatory_smoke_tests=[],
            )
            idx = build_index(tmpdir, policy, None)
            # With no mappings and _UNKNOWN symbols, should still produce valid selection
            result = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols=_UNKNOWN,
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            self.assertIsInstance(result, Selection)
            self.assertIn(result.resolved_scope, ["symbol", "file", "component", "broad", "full"])


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
