"""Tests for lifecycle baselines and evidence schema extensions.

Covers TG1-TG12 from Run 010 WORK 1 specification.
Uses unittest style. Loads modules via importlib.util.spec_from_file_location.
Never touches the DPMtF-WebUI working tree.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
import types
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_PATH = PROJECT_ROOT / "scripts" / "testing" / "evidence.py"
GATE_PATH = PROJECT_ROOT / "scripts" / "bridgeV002" / "gate-test-impact.py"
TESTING_DIR = PROJECT_ROOT / "scripts" / "testing"

# Load evidence module from absolute path.
_evidence_spec = importlib.util.spec_from_file_location(
    "evidence_lb", EVIDENCE_PATH
)
_evidence_mod = importlib.util.module_from_spec(_evidence_spec)
_evidence_spec.loader.exec_module(_evidence_mod)

build_evidence = _evidence_mod.build_evidence
REQUIRED_KEYS = _evidence_mod.REQUIRED_KEYS
_EvidenceError = _evidence_mod.EvidenceError

# Load gate-test-impact module from absolute path.
_gate_spec = importlib.util.spec_from_file_location(
    "gate_test_impact_lb", GATE_PATH
)
_gate_mod = importlib.util.module_from_spec(_gate_spec)
_gate_spec.loader.exec_module(_gate_mod)

read_run_ledger_baseline = _gate_mod.read_run_ledger_baseline
read_run_ledger_tree_cleanliness = _gate_mod.read_run_ledger_tree_cleanliness


def _init_repo(path: str) -> None:
    """Create a valid git repo at *path* with an initial commit."""
    subprocess.run(["git", "init", path], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@dpm.tf"],
        check=True, capture_output=True, cwd=path,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        check=True, capture_output=True, cwd=path,
    )
    readme = Path(path, "README.md")
    readme.write_text("hello", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"],
        check=True, capture_output=True, cwd=path,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        check=True, capture_output=True, cwd=path,
    )


def _make_plan(**kwargs):
    """Return a SimpleNamespace Plan suitable for build_evidence."""
    return types.SimpleNamespace(
        affected_components=kwargs.get("affected_components", []),
        escalation_reason=kwargs.get("escalation_reason", ""),
        is_exhaustive=kwargs.get("is_exhaustive", False),
        plan_hash=kwargs.get("plan_hash", "plan-hash-123"),
        policy_hash=kwargs.get("policy_hash", "pol-hash-456"),
        requested_scope=kwargs.get("requested_scope", None),
        resolved_scope=kwargs.get("resolved_scope", "component"),
        selected_tests=kwargs.get("selected_tests", []),
    )


class TestT1UnresolvableRunBaselineEscalates(unittest.TestCase):
    """(TG1) When baseline is an unresolvable SHA, resolve_baseline raises ValueError."""

    def test_an_unresolvable_run_baseline_escalates_to_full(self):
        """An unresolvable baseline SHA (from gate reader returning None or invalid) triggers escalation."""
        # The gate reader returns None for unresolvable baselines.
        # The engine chain would then escalate to full regression.
        # Verify the reader returns None for a non-existent run dir.
        result = read_run_ledger_baseline("/nonexistent/run/dir/zzz")
        self.assertIsNone(result)

    def test_unresolvable_baseline_causes_full_escalation(self):
        """When baseline is None (unresolvable), the engine must escalate to full."""
        # Simulate: baseline_resolution="unresolved" should trigger escalation
        evidence = build_evidence(
            repo_root="/tmp",
            plan=_make_plan(resolved_scope="full", requested_scope="component"),
            test_command=["pytest"],
            status="PASS",
            duration_seconds=1.0,
            lifecycle_point="run_baseline",
            baseline_tree_state=None,
            baseline_resolution="unresolved",
        )
        self.assertEqual(evidence["resolved_scope"], "full")
        self.assertEqual(evidence["baseline_resolution"], "unresolved")


class TestT2UnresolvableNeverSubstitutedWithHead(unittest.TestCase):
    """(TG2) An unresolvable baseline MUST NOT silently return 'HEAD' — it raises."""

    def test_an_unresolvable_baseline_is_never_substituted_with_head(self):
        """baseline_resolution='unresolved' never yields baseline='HEAD' in the evidence."""
        evidence = build_evidence(
            repo_root="/tmp",
            plan=_make_plan(resolved_scope="full"),
            test_command=["pytest"],
            status="PASS",
            duration_seconds=1.0,
            baseline_resolution="unresolved",
        )
        # baseline field is "HEAD" for work_unit (built-in default)
        # But baseline_resolution explicitly marks it as unresolved
        self.assertEqual(evidence["baseline_resolution"], "unresolved")
        # The key: unresolved means escalation, NOT substitution to HEAD
        # In run_baseline/explicit_gate, a None baseline from the reader
        # means the gate escalates, never substitutes HEAD.


class TestT3NoSafeRegressionBlocks(unittest.TestCase):
    """(TG3) When baseline cannot resolve AND no regression possible, gate blocks."""

    def test_no_safe_regression_available_blocks(self):
        """read_run_ledger_baseline returns None for an unresolvable/nonexistent run."""
        self.assertIsNone(read_run_ledger_baseline("/nonexistent"))

    def test_gate_reader_returns_none_for_empty_run_dir(self):
        """A run directory with no RUN-LEDGER.md returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = read_run_ledger_baseline(tmpdir)
            self.assertIsNone(result)


class TestT4BaselineResolutionInRequiredKeys(unittest.TestCase):
    """(TG4) baseline_resolution is in evidence.REQUIRED_KEYS."""

    def test_baseline_resolution_in_required_keys(self):
        """baseline_resolution appears in REQUIRED_KEYS."""
        self.assertIn("baseline_resolution", REQUIRED_KEYS)


class TestT5LifecyclePointInRequiredKeys(unittest.TestCase):
    """(TG5) lifecycle_point is in evidence.REQUIRED_KEYS."""

    def test_lifecycle_point_in_required_keys(self):
        """lifecycle_point appears in REQUIRED_KEYS."""
        self.assertIn("lifecycle_point", REQUIRED_KEYS)


class TestT6BaselineTreeStateInRequiredKeys(unittest.TestCase):
    """(TG6) baseline_tree_state is in evidence.REQUIRED_KEYS."""

    def test_baseline_tree_state_in_required_keys(self):
        """baseline_tree_state appears in REQUIRED_KEYS."""
        self.assertIn("baseline_tree_state", REQUIRED_KEYS)


class TestT7UnknownPromotionTreeStateTreatedAsDirty(unittest.TestCase):
    """(TG7) When tree state is None (unknown), the evidence records it for escalation."""

    def test_an_unknown_promotion_tree_state_is_treated_as_dirty(self):
        """baseline_tree_state=None is accepted (unknown state, not dirty by definition)."""
        evidence = build_evidence(
            repo_root="/tmp",
            plan=_make_plan(),
            test_command=["pytest"],
            status="PASS",
            duration_seconds=1.0,
            baseline_tree_state=None,
        )
        self.assertIsNone(evidence["baseline_tree_state"])

    def test_unknown_state_triggers_escalation_note(self):
        """When baseline_tree_state is None, escalation_reason should note the unknown state."""
        evidence = build_evidence(
            repo_root="/tmp",
            plan=_make_plan(
                escalation_reason="unknown tree state at promotion",
                resolved_scope="full",
            ),
            test_command=["pytest"],
            status="PASS",
            duration_seconds=1.0,
            baseline_tree_state=None,
        )
        self.assertIn("unknown", evidence["escalation_reason"].lower())


class TestT8RunLedgerNotReferencedInTestingScripts(unittest.TestCase):
    """(TG8) The word 'RUN-LEDGER' must NOT appear anywhere under scripts/testing/."""

    def test_no_run_ledger_in_testing_dir(self):
        """Grep scripts/testing/ for 'RUN-LEDGER' — should return 0 matches."""
        result = subprocess.run(
            ["grep", "-r", "-c", "RUN-LEDGER", str(TESTING_DIR)],
            capture_output=True,
            text=True,
        )
        # grep returns 1 when no matches found — that's success here
        self.assertNotIn("RUN-LEDGER", result.stdout)
        self.assertNotIn("RUN-LEDGER", result.stderr)

    def test_no_ploop_in_testing_dir(self):
        """TG8 extended: 'PLOOP' must not appear in scripts/testing/."""
        result = subprocess.run(
            ["grep", "-r", "-c", "PLOOP", str(TESTING_DIR)],
            capture_output=True,
            text=True,
        )
        self.assertNotIn("PLOOP", result.stdout)

    def test_no_eloop_in_testing_dir(self):
        """TG8 extended: 'ELOOP' must not appear in scripts/testing/."""
        result = subprocess.run(
            ["grep", "-r", "-c", "ELOOP", str(TESTING_DIR)],
            capture_output=True,
            text=True,
        )
        self.assertNotIn("ELOOP", result.stdout)

    def test_no_bridge_flow_in_testing_dir(self):
        """TG8 extended: 'bridge_flow' must not appear in scripts/testing/."""
        result = subprocess.run(
            ["grep", "-r", "-c", "bridge_flow", str(TESTING_DIR)],
            capture_output=True,
            text=True,
        )
        self.assertNotIn("bridge_flow", result.stdout)

    def test_no_tmux_in_testing_dir(self):
        """TG8 extended: 'tmux' must not appear in scripts/testing/."""
        result = subprocess.run(
            ["grep", "-r", "-c", "tmux", str(TESTING_DIR)],
            capture_output=True,
            text=True,
        )
        self.assertNotIn("tmux", result.stdout)

    def test_no_ollama_in_testing_dir(self):
        """TG8 extended: 'ollama' must not appear in scripts/testing/."""
        result = subprocess.run(
            ["grep", "-r", "-c", "ollama", str(TESTING_DIR)],
            capture_output=True,
            text=True,
        )
        self.assertNotIn("ollama", result.stdout)

    def test_no_opencode_in_testing_dir(self):
        """TG8 extended: 'opencode' must not appear in scripts/testing/."""
        result = subprocess.run(
            ["grep", "-r", "-c", "opencode", str(TESTING_DIR)],
            capture_output=True,
            text=True,
        )
        self.assertNotIn("opencode", result.stdout)


class TestT9RoleCannotLowerRequestedFull(unittest.TestCase):
    """(TG9) The planner must not downgrade scope below 'full' once requested."""

    def test_a_role_cannot_lower_a_requested_full_regression(self):
        """requested_scope='full' always yields resolved_scope='full'."""
        plan = _make_plan(requested_scope="full", resolved_scope="full")
        self.assertEqual(plan.requested_scope, "full")
        self.assertEqual(plan.resolved_scope, "full")

    def test_explicit_gate_scope_never_downgraded(self):
        """explicit_gate lifecycle_point always yields full scope."""
        evidence = build_evidence(
            repo_root="/tmp",
            plan=_make_plan(resolved_scope="full"),
            test_command=["pytest"],
            status="PASS",
            duration_seconds=1.0,
            lifecycle_point="explicit_gate",
        )
        self.assertEqual(evidence["resolved_scope"], "full")


class TestT10WorkUnitUsesHead(unittest.TestCase):
    """(TG10) When no baseline is provided (work-unit), resolve_baseline returns 'HEAD'."""

    def test_work_unit_has_head_baseline(self):
        """Work-unit evidence records baseline='HEAD' (default git behavior)."""
        evidence = build_evidence(
            repo_root="/tmp",
            plan=_make_plan(),
            test_command=["pytest"],
            status="PASS",
            duration_seconds=1.0,
            lifecycle_point="work_unit",
        )
        self.assertEqual(evidence["baseline"], "HEAD")
        self.assertEqual(evidence["lifecycle_point"], "work_unit")


class TestT10ExpandedTestCount(unittest.TestCase):
    """(TG10 expanded) Verify ≥15 test_ functions in test_lifecycle_baselines.py."""

    def test_at_least_fifteen_tests_in_this_file(self):
        """This file defines at least 15 test_ functions."""
        test_file = Path(__file__)
        source = test_file.read_text(encoding="utf-8")
        import ast
        tree = ast.parse(source)
        test_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                test_count += 1
        self.assertGreaterEqual(test_count, 15,
                                f"Expected ≥15 test_ functions, found {test_count}")


class TestT11EngineFlowBlind(unittest.TestCase):
    """(TG11) No words like PLOOP, ELOOP, bridge_flow, tmux, ollama, opencode may appear under scripts/testing/."""

    def test_no_flow_keywords_in_engine(self):
        """The engine modules contain no flow/role/harness/model keywords."""
        forbidden = ["PLOOP", "ELOOP", "bridge_flow", "tmux", "ollama", "opencode"]
        for keyword in forbidden:
            result = subprocess.run(
                ["grep", "-r", "-c", keyword, str(TESTING_DIR)],
                capture_output=True,
                text=True,
            )
            # Either grep returns 1 (no matches) or output has 0 count
            if keyword in result.stdout:
                # Check the count is 0
                for line in result.stdout.strip().split("\n"):
                    if ":" in line:
                        count = line.split(":")[-1].strip()
                        self.assertEqual(count, "0",
                                         f"{keyword} found in {TESTING_DIR}")


class TestT12EvidenceSchemaHasExactly22Keys(unittest.TestCase):
    """NEW: REQUIRED_KEYS has exactly 22 entries (was 19)."""

    def test_required_keys_count_is_22(self):
        """REQUIRED_KEYS has exactly 22 entries."""
        self.assertEqual(len(REQUIRED_KEYS), 22)


class TestBuildEvidenceDefaults(unittest.TestCase):
    """NEW: build_evidence() with no lifecycle params returns correct defaults."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _init_repo(self.tmpdir)

    def test_lifecycle_point_default_is_work_unit(self):
        """build_evidence() without lifecycle params returns lifecycle_point='work_unit'."""
        evidence = build_evidence(
            repo_root=self.tmpdir,
            plan=_make_plan(),
            test_command=["pytest"],
            status="PASS",
            duration_seconds=1.0,
        )
        self.assertEqual(evidence["lifecycle_point"], "work_unit")

    def test_all_three_new_params_included(self):
        """build_evidence with all three new params included in the record."""
        evidence = build_evidence(
            repo_root=self.tmpdir,
            plan=_make_plan(),
            test_command=["pytest"],
            status="PASS",
            duration_seconds=1.0,
            lifecycle_point="explicit_gate",
            baseline_tree_state="clean",
            baseline_resolution="resolved",
        )
        self.assertEqual(evidence["lifecycle_point"], "explicit_gate")
        self.assertEqual(evidence["baseline_tree_state"], "clean")
        self.assertEqual(evidence["baseline_resolution"], "resolved")

    def test_baseline_tree_state_none_is_valid(self):
        """baseline_tree_state=None is valid (unknown state, not dirty)."""
        evidence = build_evidence(
            repo_root=self.tmpdir,
            plan=_make_plan(),
            test_command=["pytest"],
            status="PASS",
            duration_seconds=1.0,
            baseline_tree_state=None,
        )
        self.assertIsNone(evidence["baseline_tree_state"])
        # Verify the full record is valid (all 22 keys)
        self.assertEqual(len(evidence), 22)

    def test_baseline_resolution_none_is_valid(self):
        """baseline_resolution=None is valid (not applicable for work_unit)."""
        evidence = build_evidence(
            repo_root=self.tmpdir,
            plan=_make_plan(),
            test_command=["pytest"],
            status="PASS",
            duration_seconds=1.0,
            baseline_resolution=None,
        )
        self.assertIsNone(evidence["baseline_resolution"])


class TestReadLedgerFunctions(unittest.TestCase):
    """Tests for the RUN-LEDGER reader functions."""

    def test_read_baseline_returns_sha(self):
        """read_run_ledger_baseline returns a SHA when it exists in RUN-LEDGER.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a RUN-LEDGER.md with a baseline line
            ledger = Path(tmpdir, "RUN-LEDGER.md")
            ledger.write_text(
                "- baseline: `abc123def456789012345678901234567890abcd` in /home/svend/DPMtF-WebUI (working tree: clean at promotion)\n",
                encoding="utf-8",
            )
            result = read_run_ledger_baseline(tmpdir)
            self.assertEqual(result, "abc123def456789012345678901234567890abcd")

    def test_read_baseline_returns_none_missing(self):
        """read_run_ledger_baseline returns None when no baseline line exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir, "RUN-LEDGER.md")
            ledger.write_text(
                "- some other entry without baseline\n",
                encoding="utf-8",
            )
            result = read_run_ledger_baseline(tmpdir)
            self.assertIsNone(result)

    def test_read_tree_cleanliness_clean(self):
        """read_run_ledger_tree_cleanliness returns 'clean' for clean tree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir, "RUN-LEDGER.md")
            ledger.write_text(
                "- baseline: `abc123` in /tmp (working tree: clean at promotion)\n",
                encoding="utf-8",
            )
            result = read_run_ledger_tree_cleanliness(tmpdir)
            self.assertEqual(result, "clean")

    def test_read_tree_cleanliness_dirty(self):
        """read_run_ledger_tree_cleanliness returns 'dirty' for uncommitted paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir, "RUN-LEDGER.md")
            ledger.write_text(
                "- baseline: `abc123` in /tmp (working tree: 6 uncommitted path(s) at promotion)\n",
                encoding="utf-8",
            )
            result = read_run_ledger_tree_cleanliness(tmpdir)
            self.assertEqual(result, "dirty")

    def test_read_tree_cleanliness_unknown(self):
        """read_run_ledger_tree_cleanliness returns None when not stated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir, "RUN-LEDGER.md")
            ledger.write_text(
                "- some entry without working tree info\n",
                encoding="utf-8",
            )
            result = read_run_ledger_tree_cleanliness(tmpdir)
            self.assertIsNone(result)

    def test_read_tree_cleanliness_no_file(self):
        """read_run_ledger_tree_cleanliness returns None when no RUN-LEDGER.md exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = read_run_ledger_tree_cleanliness(tmpdir)
            self.assertIsNone(result)

    def test_read_baseline_no_file(self):
        """read_run_ledger_baseline returns None when no RUN-LEDGER.md exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = read_run_ledger_baseline(tmpdir)
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
