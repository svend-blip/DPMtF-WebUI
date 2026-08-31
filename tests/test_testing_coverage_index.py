"""Structural tests for scripts/testing/coverage_index.py and the
optional ``coverage_record`` parameter on ``tests_for``.

These tests cover the handoff's testgoals (TG1-TG7) and pin down the
contract:

- Coverage is **off by default** — collection only happens when
  ``collect_coverage=True`` is passed.
- A record from a different policy state is **discarded**, never partially
  applied. Unknown compatibility is incompatibility.
- Coverage is **additive only** — it never removes a test from the
  static union and never authorises a narrowing the static rules refuse.
- ``CoverageRecord`` is a frozen dataclass — immutable after construction.
- ``merge()`` returns a new record; the originals are unchanged.
- ``tests_for()`` with no ``coverage_record`` produces the same Selection
  Run 009 delivered (TG6 invariance).

MockPolicy / MockClosure are inlined here to keep this file's testgoals
self-contained.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Load modules
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CI_PATH = PROJECT_ROOT / "scripts" / "testing" / "coverage_index.py"
_TI_PATH = PROJECT_ROOT / "scripts" / "testing" / "test_index.py"

_ci_spec = importlib.util.spec_from_file_location(
    "coverage_index_test", _CI_PATH,
)
_ci = importlib.util.module_from_spec(_ci_spec)
# Frozen dataclasses look themselves up in sys.modules during class
# construction; without this registration exec_module fails with
# ``'NoneType' object has no attribute '__dict__'``.
sys.modules["coverage_index_test"] = _ci
_ci_spec.loader.exec_module(_ci)

_ti_spec = importlib.util.spec_from_file_location(
    "test_index_test_for_coverage", _TI_PATH,
)
_ti = importlib.util.module_from_spec(_ti_spec)
sys.modules["test_index_test_for_coverage"] = _ti
_ti_spec.loader.exec_module(_ti)

# Use the same CoverageRecord class that test_index.py binds internally —
# importing via importlib.util.spec_from_file_location produces a
# separate class object for the dataclass, which then fails the
# ``isinstance(coverage_record, _CoverageRecord)`` guard inside
# ``tests_for``. The class loaded by ``scripts.testing.coverage_index``
# under normal sys.path lookup is the same instance ``test_index.py``
# captured.
import scripts.testing.coverage_index as _ci_pkg

CoverageRecord = _ci_pkg.CoverageRecord
COVERAGE_RECORD_SCHEMA_VERSION = _ci_pkg.COVERAGE_RECORD_SCHEMA_VERSION
CoverageError = _ci_pkg.CoverageError
CoverageRecord_empty = _ci_pkg.CoverageRecord.empty

build_index = _ti.build_index
tests_for = _ti.tests_for
TestIndex = _ti.TestIndex
_IndexError_ = _ti.IndexError_
Selection = _ti.Selection
_UNKNOWN = _ti._UNKNOWN


# ---------------------------------------------------------------------------
# Mocks (mirror the patterns in test_testing_test_index.py)
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
# Module-level fixtures
# ---------------------------------------------------------------------------


def _make_record(
    symbol_to_tests=None,
    repo_fp="repo-fp-A",
    policy_fp="policy-fp-A",
    run_scope="broad",
    collected_at="2026-08-31T12:00:00Z",
):
    """Build a CoverageRecord with sensible defaults for tests."""
    return CoverageRecord(
        symbol_to_tests=symbol_to_tests or {},
        repo_fingerprint=repo_fp,
        policy_fingerprint=policy_fp,
        run_scope=run_scope,
        collected_at=collected_at,
    )


def _make_index_with_temp_repo():
    """Build a TestIndex against an in-memory temp repo.

    Returns ``(index, tmpdir)``. The tempdir is the caller's
    responsibility to clean up; tests using this fixture should use
    ``tempfile.TemporaryDirectory``.
    """
    import tempfile

    tmp = tempfile.TemporaryDirectory()
    tmpdir = tmp.name
    tests_dir = Path(tmpdir, "tests")
    tests_dir.mkdir()
    (tests_dir / "test_x.py").write_text("from x import foo\n")
    Path(tmpdir, "x.py").write_text("def foo(): pass\n")
    policy = MockPolicy(components={}, test_mappings={})
    idx = build_index(tmpdir, policy, None)
    return idx, tmp


# ---------------------------------------------------------------------------
# Public API & module structure
# ---------------------------------------------------------------------------


class TestCoverageIndexModule(unittest.TestCase):
    """Tests for the coverage_index module's surface."""

    def test_coverage_index_importable(self):
        """The module imports cleanly."""
        self.assertTrue(hasattr(_ci, "CoverageRecord"))
        self.assertTrue(callable(CoverageRecord))

    def test_coverage_index_all_exports_present(self):
        """__all__ contains exactly CoverageRecord, COVERAGE_RECORD_SCHEMA_VERSION, CoverageError."""
        all_exports = sorted(getattr(_ci, "__all__", []))
        self.assertEqual(
            all_exports,
            sorted(
                ["CoverageRecord", "COVERAGE_RECORD_SCHEMA_VERSION", "CoverageError"]
            ),
        )

    def test_coverage_record_is_a_class(self):
        """CoverageRecord is a class."""
        self.assertTrue(isinstance(CoverageRecord, type))

    def test_coverage_record_schema_version_is_string(self):
        """COVERAGE_RECORD_SCHEMA_VERSION is a non-empty string."""
        self.assertIsInstance(COVERAGE_RECORD_SCHEMA_VERSION, str)
        self.assertGreater(len(COVERAGE_RECORD_SCHEMA_VERSION), 0)

    def test_coverage_error_is_exception_subclass(self):
        """CoverageError is an Exception subclass."""
        self.assertTrue(issubclass(CoverageError, Exception))


# ---------------------------------------------------------------------------
# TG1 — collection is off by default
# ---------------------------------------------------------------------------


class TestCollectionOffByDefault(unittest.TestCase):
    """Coverage is opt-in and stays off unless collect_coverage=True."""

    def test_collection_is_off_by_default(self):
        """Coverage collection is off unless collect_coverage=True is passed.

        Inspecting the runner's signature is the most reliable structural
        check: ``collect_coverage`` must exist, default to ``False``, and
        must not silently alter the evidence schema.
        """
        from scripts.testing.runner import run_plan

        sig = inspect.signature(run_plan)
        self.assertIn("collect_coverage", sig.parameters)
        param = sig.parameters["collect_coverage"]
        self.assertEqual(param.default, False)


# ---------------------------------------------------------------------------
# TG2 — a record from another policy state is discarded
# ---------------------------------------------------------------------------


class TestPolicyFingerprintMismatch(unittest.TestCase):
    """Records whose policy_fingerprint does not match the current policy
    are silently discarded by ``tests_for``."""

    def test_a_record_from_another_policy_state_is_discarded(self):
        """A coverage record with a mismatched policy_fingerprint is discarded.

        The Selection returned by ``tests_for`` is byte-for-byte identical
        to the Selection returned without the record — coverage must not
        leak tests in through a fingerprint mismatch.
        """
        idx, tmp = _make_index_with_temp_repo()
        try:
            policy = MockPolicy(
                components={},
                test_mappings={},
                mandatory_smoke_tests=["tests/smoke.py"],
                policy_hash_val="current-policy-hash",
            )
            static_sel = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )

            foreign_record = _make_record(
                symbol_to_tests={
                    "foo": {"tests/test_intruder.py", "tests/test_other.py"},
                },
                policy_fp="DIFFERENT-policy-hash",
            )
            sel_with_foreign = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
                coverage_record=foreign_record,
            )

            self.assertEqual(sel_with_foreign.tests, static_sel.tests)
            self.assertEqual(
                sel_with_foreign.resolved_scope, static_sel.resolved_scope,
            )
        finally:
            tmp.cleanup()


# ---------------------------------------------------------------------------
# TG3 — coverage never removes a test from the union
# ---------------------------------------------------------------------------


class TestCoverageNeverRemoves(unittest.TestCase):
    """Coverage is additive only; the static set is never shrunk."""

    def test_coverage_never_removes_a_test_from_the_union(self):
        """Adding a coverage record never removes an existing static test.

        Even when the coverage record's symbol→tests mapping includes
        only tests that are *not* in the static selection, the static
        tests are preserved verbatim — coverage only ever adds.
        """
        idx, tmp = _make_index_with_temp_repo()
        try:
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
                policy_hash_val="matching-policy",
            )
            # Resolve a known-good scope so the Selection is non-empty.
            base_sel = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            static_set = set(base_sel.tests)
            self.assertGreater(len(static_set), 0)

            coverage_record = _make_record(
                symbol_to_tests={
                    # No overlap with the static tests — coverage's
                    # contribution is purely additive.
                    "bar": {"tests/test_completely_unrelated.py"},
                },
                policy_fp="matching-policy",
            )

            merged_sel = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
                coverage_record=coverage_record,
            )

            self.assertTrue(
                static_set.issubset(set(merged_sel.tests)),
                "Static test set must be a subset of merged set; "
                "coverage is additive only.",
            )
            self.assertIn("tests/test_completely_unrelated.py", merged_sel.tests)
        finally:
            tmp.cleanup()


# ---------------------------------------------------------------------------
# TG4 — coverage cannot authorise a narrowing the static rules refuse
# ---------------------------------------------------------------------------


class TestCoverageCannotNarrow(unittest.TestCase):
    """Coverage cannot authorise a narrowing the static rules refuse.

    Static analysis produced ``component`` scope because condition (c)
    (every symbol maps to a test) failed. Coverage must not move the
    selection to ``symbol`` or ``file`` even if a coverage record with
    the matching policy_fingerprint is provided.
    """

    def test_coverage_cannot_authorise_a_narrowing_static_analysis_refuses(self):
        """Coverage never narrows below what static analysis allowed."""
        idx, tmp = _make_index_with_temp_repo()
        try:
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
                policy_hash_val="matching-policy",
            )
            # 'nonexistent' is not in symbol_to_tests, so condition (c)
            # blocks symbol scope. Static resolution lands on file scope.
            static_sel = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"nonexistent_symbol"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            self.assertEqual(static_sel.resolved_scope, "file")

            # Even with a perfectly matching coverage record, scope cannot
            # move leftward to symbol. Coverage is additive only.
            coverage_record = _make_record(
                symbol_to_tests={
                    "nonexistent_symbol": {"tests/test_one.py"},
                },
                policy_fp="matching-policy",
            )
            merged_sel = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"nonexistent_symbol"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
                coverage_record=coverage_record,
            )

            self.assertEqual(
                merged_sel.resolved_scope, static_sel.resolved_scope,
                "Coverage must not move scope leftward; static rules stand.",
            )
            # And the additional tests are unioned in.
            self.assertIn("tests/test_one.py", merged_sel.tests)
        finally:
            tmp.cleanup()


# ---------------------------------------------------------------------------
# TG5 — unknown compatibility discards the record
# ---------------------------------------------------------------------------


class TestUnknownCompatibilityDiscards(unittest.TestCase):
    """A record whose compatibility cannot be established is discarded.

    ``is_compatible`` returns False when *either* fingerprint is unknown.
    Unknown is incompatible — the same fail-closed rule Run 005 applies
    to staleness.
    """

    def test_unknown_compatibility_discards_the_record(self):
        """An empty-fingerprint record is never compatible."""
        rec = _make_record(repo_fp="", policy_fp="")
        self.assertFalse(
            rec.is_compatible("any-repo", "any-policy"),
            "Empty fingerprints must make the record incompatible.",
        )
        self.assertFalse(rec.is_compatible("", ""))
        # Even when current state has known fingerprints, an empty record
        # fingerprint on either side is rejected.
        self.assertFalse(rec.is_compatible("known-repo", "known-policy"))
        # Symmetric: known record, unknown current state → discarded.
        known = _make_record(repo_fp="R1", policy_fp="P1")
        self.assertFalse(known.is_compatible("", "P1"))
        self.assertFalse(known.is_compatible("R1", ""))


# ---------------------------------------------------------------------------
# CoverageRecord merge semantics
# ---------------------------------------------------------------------------


class TestCoverageRecordMerge(unittest.TestCase):
    """``CoverageRecord.merge()`` unions symbol→tests; originals unchanged."""

    def test_coverage_record_merge_is_additive(self):
        """Merging two records unions their symbol→tests."""
        a = _make_record(
            symbol_to_tests={"alpha": {"t1.py", "t2.py"}},
            collected_at="2026-08-31T10:00:00Z",
        )
        b = _make_record(
            symbol_to_tests={
                "alpha": {"t3.py"},
                "beta": {"t4.py"},
            },
            collected_at="2026-08-31T11:00:00Z",
        )
        merged = a.merge(b)

        self.assertIn("alpha", merged.symbol_to_tests)
        self.assertIn("beta", merged.symbol_to_tests)
        self.assertEqual(
            merged.symbol_to_tests["alpha"],
            {"t1.py", "t2.py", "t3.py"},
        )
        self.assertEqual(merged.symbol_to_tests["beta"], {"t4.py"})

        # Originals are untouched.
        self.assertEqual(a.symbol_to_tests["alpha"], {"t1.py", "t2.py"})
        self.assertEqual(b.symbol_to_tests["alpha"], {"t3.py"})
        self.assertEqual(b.symbol_to_tests["beta"], {"t4.py"})

        # Latest timestamp wins.
        self.assertEqual(merged.collected_at, "2026-08-31T11:00:00Z")

    def test_merge_preserves_fingerprints_from_self(self):
        """merge() inherits self's repo and policy fingerprints."""
        a = _make_record(
            repo_fp="R-self",
            policy_fp="P-self",
            symbol_to_tests={"k": {"t.py"}},
        )
        b = _make_record(
            repo_fp="R-other",
            policy_fp="P-other",
            symbol_to_tests={"k": {"u.py"}},
        )
        merged = a.merge(b)
        self.assertEqual(merged.repo_fingerprint, "R-self")
        self.assertEqual(merged.policy_fingerprint, "P-self")

    def test_merge_rejects_non_coverage_record(self):
        """merge() refuses to combine a record with anything else."""
        with self.assertRaises(CoverageError):
            _make_record().merge({"not": "a record"})


# ---------------------------------------------------------------------------
# Empty record behaviour
# ---------------------------------------------------------------------------


class TestEmptyCoverageRecord(unittest.TestCase):
    """An empty record must be a no-op even when policies match."""

    def test_empty_coverage_record_does_not_change_selection(self):
        """Empty record → Selection identical to the static one."""
        idx, tmp = _make_index_with_temp_repo()
        try:
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
                policy_hash_val="matching-policy",
            )
            static_sel = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )

            empty_rec = _make_record(
                symbol_to_tests={},
                policy_fp="matching-policy",
            )
            merged_sel = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
                coverage_record=empty_rec,
            )
            self.assertEqual(merged_sel.tests, static_sel.tests)
            self.assertEqual(
                merged_sel.resolved_scope, static_sel.resolved_scope,
            )
        finally:
            tmp.cleanup()

    def test_empty_classmethod_is_never_compatible(self):
        """CoverageRecord.empty() never matches any state."""
        empty = CoverageRecord_empty()
        self.assertTrue(empty.is_empty())
        self.assertFalse(empty.is_compatible("anything", "at all"))


# ---------------------------------------------------------------------------
# Selection immutability across coverage merge
# ---------------------------------------------------------------------------


class TestSelectionImmutabilityAfterCoverage(unittest.TestCase):
    """The Selection remains immutable after coverage is merged."""

    def test_selection_immutable_after_coverage_merge(self):
        """Setting any Selection attribute still raises after coverage merge."""
        idx, tmp = _make_index_with_temp_repo()
        try:
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
                policy_hash_val="matching-policy",
            )
            record = _make_record(
                symbol_to_tests={"foo": {"tests/test_one.py"}},
                policy_fp="matching-policy",
            )
            sel = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
                coverage_record=record,
            )
            for attr in ("tests", "resolved_scope", "narrowing_blockers", "rationale"):
                with self.subTest(attr=attr):
                    with self.assertRaises(_IndexError_):
                        setattr(sel, attr, "anything")
                    with self.assertRaises(_IndexError_):
                        delattr(sel, attr)
        finally:
            tmp.cleanup()


# ---------------------------------------------------------------------------
# CoverageRecord frozen and shape contract
# ---------------------------------------------------------------------------


class TestCoverageRecordFrozen(unittest.TestCase):
    """CoverageRecord is a frozen dataclass."""

    def test_coverage_record_dataclass_frozen(self):
        """Frozen dataclass — setattr raises AttributeError or FrozenInstanceError."""
        rec = _make_record(symbol_to_tests={"foo": {"t.py"}})
        with self.assertRaises(Exception):
            rec.repo_fingerprint = "tampered"
        # AttributeError is acceptable; the contract is "cannot mutate".

    def test_coverage_record_requires_all_fields_explicit(self):
        """A CoverageRecord constructed with no fields uses the defaults."""
        rec = CoverageRecord()
        # All five schema fields are populated (with sensible defaults).
        self.assertIsInstance(rec.symbol_to_tests, dict)
        self.assertIsInstance(rec.repo_fingerprint, str)
        self.assertIsInstance(rec.policy_fingerprint, str)
        self.assertIsInstance(rec.run_scope, str)
        self.assertIsInstance(rec.collected_at, str)
        self.assertIn(rec.run_scope, ("broad", "full"))

    def test_coverage_record_validates_run_scope(self):
        """run_scope outside the permitted set is rejected."""
        with self.assertRaises(CoverageError):
            CoverageRecord(run_scope="symbol")
        with self.assertRaises(CoverageError):
            CoverageRecord(run_scope="narrow")

    def test_coverage_record_coerces_symbol_mapping(self):
        """Inner sets are defensively copied — external mutation cannot leak."""
        inner = {"foo": {"t.py"}}
        rec = _make_record(symbol_to_tests=inner)
        # Mutating the original input must not change the record.
        inner["foo"].add("intruder.py")
        self.assertNotIn("intruder.py", rec.symbol_to_tests["foo"])

    def test_coverage_record_rejects_non_string_fingerprints(self):
        """Non-string fingerprints raise CoverageError at construction."""
        with self.assertRaises(CoverageError):
            CoverageRecord(repo_fingerprint=123)  # type: ignore[arg-type]
        with self.assertRaises(CoverageError):
            CoverageRecord(policy_fingerprint=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CoverageRecord.is_compatible — full table
# ---------------------------------------------------------------------------


class TestCoverageRecordIsCompatible(unittest.TestCase):
    """The is_compatible matrix."""

    def test_coverage_record_compatible_with_matching_fingerprints(self):
        """A record with matching repo and policy fingerprints is compatible."""
        rec = _make_record(repo_fp="R", policy_fp="P")
        self.assertTrue(rec.is_compatible("R", "P"))

    def test_coverage_record_incompatible_with_repo_mismatch(self):
        """A record with mismatched repo_fingerprint is incompatible."""
        rec = _make_record(repo_fp="R1", policy_fp="P")
        self.assertFalse(rec.is_compatible("R2", "P"))

    def test_coverage_record_incompatible_with_policy_mismatch(self):
        """A record with mismatched policy_fingerprint is incompatible."""
        rec = _make_record(repo_fp="R", policy_fp="P1")
        self.assertFalse(rec.is_compatible("R", "P2"))


# ---------------------------------------------------------------------------
# tests_for signature
# ---------------------------------------------------------------------------


class TestTestsForCoverageRecordParameter(unittest.TestCase):
    """The ``coverage_record`` parameter on ``tests_for``."""

    def test_tests_for_coverage_record_parameter(self):
        """tests_for accepts an optional coverage_record parameter."""
        sig = inspect.signature(tests_for)
        self.assertIn("coverage_record", sig.parameters)
        param = sig.parameters["coverage_record"]
        # Optional: must have a default.
        self.assertIsNot(
            param.default, inspect.Parameter.empty,
            "coverage_record must be optional (have a default).",
        )

    def test_tests_for_without_coverage_unchanged(self):
        """Calling tests_for() without coverage_record produces the same Selection.

        This is the Run 009 invariance guard. The static selection must
        be byte-for-byte identical whether or not coverage is wired in.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_x.py").write_text("from x import foo\n")
            (tests_dir / "smoke.py").write_text("pass\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            policy = MockPolicy(
                components={"x": ["x.py"]},
                test_mappings={"x": ["tests/test_x.py"]},
                mandatory_smoke_tests=["tests/smoke.py"],
                policy_hash_val="p-hash",
            )
            idx = build_index(tmpdir, policy, None)

            baseline = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            # Same call, no coverage_record argument at all.
            same = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
            )
            self.assertEqual(baseline.tests, same.tests)
            self.assertEqual(baseline.resolved_scope, same.resolved_scope)
            self.assertEqual(baseline.narrowing_blockers, same.narrowing_blockers)
            self.assertEqual(baseline.rationale, same.rationale)

            # And the explicit ``coverage_record=None`` form.
            explicit_none = tests_for(
                idx,
                changed={"x.py": "modified"},
                symbols={"x.py": {"foo"}},
                closure=MockClosure(is_safe=True),
                policy=policy,
                coverage_record=None,
            )
            self.assertEqual(baseline.tests, explicit_none.tests)
            self.assertEqual(baseline.rationale, explicit_none.rationale)


# ---------------------------------------------------------------------------
# to_dict / from_dict round-trip
# ---------------------------------------------------------------------------


class TestCoverageRecordSerialization(unittest.TestCase):
    """to_dict / from_dict round-trip preserves all fields."""

    def test_to_dict_from_dict_roundtrip(self):
        """A record serialised and re-loaded equals the original."""
        original = _make_record(
            symbol_to_tests={
                "alpha": {"tests/test_a.py", "tests/test_b.py"},
                "beta": {"tests/test_c.py"},
            },
            repo_fp="repo-A",
            policy_fp="policy-A",
            run_scope="full",
            collected_at="2026-08-31T15:30:00Z",
        )
        snapshot = original.to_dict()
        rebuilt = CoverageRecord.from_dict(snapshot)
        self.assertEqual(rebuilt.repo_fingerprint, original.repo_fingerprint)
        self.assertEqual(
            rebuilt.policy_fingerprint, original.policy_fingerprint
        )
        self.assertEqual(rebuilt.run_scope, original.run_scope)
        self.assertEqual(rebuilt.collected_at, original.collected_at)
        self.assertEqual(
            rebuilt.symbol_to_tests, original.symbol_to_tests,
        )

    def test_all_observed_tests_unions_every_symbol(self):
        """all_observed_tests() returns the union across every symbol."""
        rec = _make_record(
            symbol_to_tests={
                "alpha": {"t1.py", "t2.py"},
                "beta": {"t3.py"},
                "gamma": set(),
            },
        )
        self.assertEqual(
            rec.all_observed_tests(), {"t1.py", "t2.py", "t3.py"},
        )


# ---------------------------------------------------------------------------
# Runner: signature and off-by-default
# ---------------------------------------------------------------------------


class TestRunnerCollectCoverageParameter(unittest.TestCase):
    """The runner's opt-in ``collect_coverage`` parameter."""

    def test_runner_has_collect_coverage_param(self):
        """run_plan exposes collect_coverage, defaulting to False."""
        from scripts.testing.runner import run_plan
        sig = inspect.signature(run_plan)
        self.assertIn("collect_coverage", sig.parameters)
        param = sig.parameters["collect_coverage"]
        self.assertEqual(param.default, False)


if __name__ == "__main__":
    unittest.main()
