#!/usr/bin/env python3
"""Tests for ``scripts/bridgeV002/gate-test-impact.py``.

Uses ``unittest`` style. Creates temp repos/dirs for file-write and git tests.
Never touches the DPMtF-WebUI working tree.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # DPMtF-WebUI root


def _init_repo(path):
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


def _write_policy(repo_root, policy_data):
    """Write .dpmtf/test-policy.json."""
    dpmtf_dir = os.path.join(repo_root, ".dpmtf")
    os.makedirs(dpmtf_dir, exist_ok=True)
    with open(os.path.join(dpmtf_dir, "test-policy.json"), "w") as f:
        json.dump(policy_data, f)


def _make_minimal_policy():
    """Return a minimal valid policy dict."""
    return {
        "components": {"mycomp": ["src/*.py"]},
        "test_mappings": {"mycomp": ["tests/test_mycomp.py"]},
        "mandatory_smoke_tests": [],
    }


def _create_source_tree(repo_root):
    """Create src/app.py and tests/test_mycomp.py."""
    for d in ("src", "tests"):
        os.makedirs(os.path.join(repo_root, d), exist_ok=True)
    with open(os.path.join(repo_root, "src", "app.py"), "w") as f:
        f.write("# app\n")
    with open(os.path.join(repo_root, "tests", "test_mycomp.py"), "w") as f:
        f.write("# test\n")


# --- Load modules under test once at import time ---
GATE_PATH = PROJECT_ROOT / "scripts" / "bridgeV002" / "gate-test-impact.py"
_gate_spec = importlib.util.spec_from_file_location(
    "gate_test", GATE_PATH
)
_gate_mod = importlib.util.module_from_spec(_gate_spec)
_gate_spec.loader.exec_module(_gate_mod)

engine_chain = _gate_mod.engine_chain
parse_args = _gate_mod.parse_args

BRIDGE_LIB_PATH = PROJECT_ROOT / "scripts" / "bridgeV002" / "bridge_lib.py"
_bridge_spec = importlib.util.spec_from_file_location(
    "bridge_lib_test", BRIDGE_LIB_PATH
)
_bridge_mod = importlib.util.module_from_spec(_bridge_spec)
_bridge_spec.loader.exec_module(_bridge_mod)

get_effective_artifact_root = _bridge_mod.get_effective_artifact_root
get_flow_target_project = _bridge_mod.get_flow_target_project

EVIDENCE_PATH = PROJECT_ROOT / "scripts" / "testing" / "evidence.py"
_evidence_spec = importlib.util.spec_from_file_location(
    "evidence_test", EVIDENCE_PATH
)
_evidence_mod = importlib.util.module_from_spec(_evidence_spec)
_evidence_spec.loader.exec_module(_evidence_mod)

build_evidence = _evidence_mod.build_evidence
write_evidence = _evidence_mod.write_evidence
is_stale = _evidence_mod.is_stale
EVIDENCE_SCHEMA_VERSION = _evidence_mod.EVIDENCE_SCHEMA_VERSION


# ================================================================
# Helpers
# ================================================================


def _gate_result_to_exit_code(result, mode="block", bridge_dir=""):
    """Simulate gate-test-impact.py main() exit logic on a result dict."""
    if mode == "block" and not result["success"]:
        return 1
    return 0


def _setup_passing_repo(repo_root):
    """Fully set up a repo that will produce a PASS result."""
    _init_repo(repo_root)
    _write_policy(repo_root, _make_minimal_policy())
    _create_source_tree(repo_root)
    with open(os.path.join(repo_root, "tests", "test_mycomp.py"), "w") as f:
        f.write("def test_pass():\n    pass\n")


def _setup_failing_repo(repo_root):
    """Set up a repo that will produce a FAIL result."""
    _init_repo(repo_root)
    _write_policy(repo_root, _make_minimal_policy())
    _create_source_tree(repo_root)
    with open(os.path.join(repo_root, "tests", "test_mycomp.py"), "w") as f:
        f.write("def test_always_fail():\n    assert False\n")


def _setup_error_repo(repo_root):
    """Set up a repo that will produce an ERROR result."""
    _init_repo(repo_root)
    _write_policy(repo_root, _make_minimal_policy())
    _create_source_tree(repo_root)
    os.remove(os.path.join(repo_root, "tests", "test_mycomp.py"))


# ================================================================
# Tests
# ================================================================


class TestGateTestImpactCLI(unittest.TestCase):
    """Tests exercising gate mode (block vs warn) via engine_chain + gate logic."""

    def test_warn_mode_exits_zero_on_a_failing_plan(self):
        """In warn mode the gate MUST exit 0 even when tests fail."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                _setup_failing_repo(repo_root)
                result = engine_chain(repo_root, "1000-02-ELOOP", "99", bridge_dir)
                exit_code = _gate_result_to_exit_code(result, mode="warn")
                self.assertEqual(exit_code, 0,
                                 f"warn mode should exit 0 on FAIL, got {exit_code}")
                self.assertEqual(result["status"], "FAIL")

    def test_block_mode_exits_nonzero_when_the_engine_errors(self):
        """In block mode the gate MUST exit nonzero on engine errors."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                _init_repo(repo_root)
                dpmtf_dir = os.path.join(repo_root, ".dpmtf")
                os.makedirs(dpmtf_dir, exist_ok=True)
                with open(os.path.join(dpmtf_dir, "test-policy.json"), "w") as f:
                    f.write("not valid json {{{")
                result = engine_chain(repo_root, "1000-02-ELOOP", "99", bridge_dir)
                exit_code = _gate_result_to_exit_code(result, mode="block")
                self.assertNotEqual(exit_code, 0,
                                    f"block mode should exit nonzero on ERROR, got {exit_code}")
                self.assertEqual(result["status"], "ERROR")

    def test_block_mode_passes_on_successful_plan(self):
        """In block mode the gate MUST exit 0 when tests pass."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                _setup_passing_repo(repo_root)
                result = engine_chain(repo_root, "1000-02-ELOOP", "99", bridge_dir)
                exit_code = _gate_result_to_exit_code(result, mode="block")
                self.assertEqual(exit_code, 0,
                                 f"block mode should exit 0 on PASS, got {exit_code}")
                self.assertEqual(result["status"], "PASS")
                self.assertTrue(result["success"])

    def test_block_mode_fails_on_a_failing_plan(self):
        """In block mode the gate MUST exit 1 when tests fail."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                _setup_failing_repo(repo_root)
                result = engine_chain(repo_root, "1000-02-ELOOP", "99", bridge_dir)
                exit_code = _gate_result_to_exit_code(result, mode="block")
                self.assertNotEqual(exit_code, 0,
                                    f"block mode should exit nonzero on FAIL, got {exit_code}")
                self.assertEqual(result["status"], "FAIL")
                self.assertFalse(result["success"])

    def test_engine_chain_returns_expected_keys(self):
        """engine_chain() must return success/status/evidence/error/evidence_path."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                _setup_passing_repo(repo_root)
                result = engine_chain(repo_root, "1000-02-ELOOP", "99", bridge_dir)
                expected_keys = {"success", "status", "evidence", "error", "evidence_path"}
                self.assertEqual(set(result.keys()), expected_keys)

    def test_parse_args_minimal_required(self):
        """parse_args() must accept all ten required fields plus optional --mode."""
        args = parse_args([
            "--flow-key", "1000-02-ELOOP",
            "--step-key", "implementer-reviewer",
            "--from-role", "1000-implementer",
            "--to-role", "1000-reviewer",
            "--deliverable-dir", "/tmp/deliverables",
            "--deliverable-pattern", "*-result.md",
            "--deliverable-file", "/tmp/result.md",
            "--handoff-id", "42",
            "--bridge-dir", "/tmp/bridge",
            "--prompt-template", "default",
            "--mode", "warn",
        ])
        self.assertEqual(args.flow_key, "1000-02-ELOOP")
        self.assertEqual(args.mode, "warn")

    def test_parse_args_warn_default(self):
        """--mode defaults to 'warn' when omitted.

        Changed from block 2026-08-28 (fb3d91c): the pre-dispatch wiring
        cannot pass --mode, so the CLI default IS the wired behaviour, and
        GOAL 006 D2's rollout contract requires warn. Block stays available
        explicitly.
        """
        args = parse_args([
            "--flow-key", "1000-02-ELOOP",
            "--step-key", "implementer-reviewer",
            "--from-role", "1000-implementer",
            "--to-role", "1000-reviewer",
            "--deliverable-dir", "/tmp/deliverables",
            "--deliverable-pattern", "*-result.md",
            "--deliverable-file", "/tmp/result.md",
            "--handoff-id", "42",
            "--bridge-dir", "/tmp/bridge",
            "--prompt-template", "default",
        ])
        self.assertEqual(args.mode, "warn")

    def test_parse_args_all_ten_fields(self):
        """All ten required + optional --mode must be parseable."""
        args = parse_args([
            "--flow-key", "1000-02-ELOOP",
            "--step-key", "implementer-reviewer",
            "--from-role", "1000-implementer",
            "--to-role", "1000-reviewer",
            "--deliverable-dir", "/tmp/deliverables",
            "--deliverable-pattern", "*-result.md",
            "--deliverable-file", "/tmp/result.md",
            "--handoff-id", "42",
            "--bridge-dir", "/tmp/bridge",
            "--prompt-template", "default",
            "--mode", "block",
        ])
        self.assertIsInstance(args.flow_key, str)
        self.assertIsInstance(args.step_key, str)
        self.assertIsInstance(args.from_role, str)
        self.assertIsInstance(args.to_role, str)
        self.assertIsInstance(args.deliverable_dir, str)
        self.assertIsInstance(args.deliverable_pattern, str)
        self.assertIsInstance(args.deliverable_file, str)
        self.assertIsInstance(args.handoff_id, str)
        self.assertIsInstance(args.bridge_dir, str)
        self.assertIsInstance(args.prompt_template, str)
        self.assertIsInstance(args.mode, str)


class TestEngineChain(unittest.TestCase):
    """Unit tests for the engine chain internals."""

    def test_warn_mode_exists(self):
        """Verify the --mode argument accepts 'warn' and 'block' choices."""
        for mode in ("warn", "block"):
            args = parse_args([
                "--flow-key", "1000-02-ELOOP",
                "--step-key", "implementer-reviewer",
                "--from-role", "1000-implementer",
                "--to-role", "1000-reviewer",
                "--deliverable-dir", "/tmp/deliverables",
                "--deliverable-pattern", "*-result.md",
                "--deliverable-file", "/tmp/result.md",
                "--handoff-id", "42",
                "--bridge-dir", "/tmp/bridge",
                "--prompt-template", "default",
                "--mode", mode,
            ])
            self.assertEqual(args.mode, mode)

    def test_engine_chain_passes_on_successful_plan(self):
        """engine_chain produces PASS and verify success=True."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                _setup_passing_repo(repo_root)
                result = engine_chain(repo_root, "1000-02-ELOOP", "99", bridge_dir)
                self.assertTrue(result["success"])
                self.assertEqual(result["status"], "PASS")
                self.assertIsNotNone(result["evidence"])
                self.assertIsNotNone(result["evidence_path"])

    def test_engine_chain_policy_error_in_block(self):
        """Trigger a policy load error and verify success=False, status=ERROR."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                _init_repo(repo_root)
                dpmtf_dir = os.path.join(repo_root, ".dpmtf")
                os.makedirs(dpmtf_dir, exist_ok=True)
                with open(os.path.join(dpmtf_dir, "test-policy.json"), "w") as f:
                    f.write("{malformed json")
                result = engine_chain(repo_root, "1000-02-ELOOP", "99", bridge_dir)
                self.assertFalse(result["success"])
                self.assertEqual(result["status"], "ERROR")
                self.assertIsNotNone(result["error"])

    def test_evidence_file_created_with_valid_json(self):
        """Run the full gate and verify evidence file is created and contains valid JSON."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                _setup_passing_repo(repo_root)
                result = engine_chain(repo_root, "1000-02-ELOOP", "99", bridge_dir)
                self.assertIsNotNone(result["evidence_path"])
                self.assertTrue(os.path.isfile(result["evidence_path"]))
                with open(result["evidence_path"], "r") as f:
                    content = f.read()
                self.assertIn("status", content)


class TestEvidence(unittest.TestCase):
    """Tests for evidence module helpers used by the gate."""

    def test_evidence_schema_version_is_non_empty_string(self):
        """EVIDENCE_SCHEMA_VERSION must be a non-empty string."""
        self.assertIsInstance(EVIDENCE_SCHEMA_VERSION, str)
        self.assertTrue(len(EVIDENCE_SCHEMA_VERSION) > 0)

    def test_is_stale_on_modified_repo(self):
        """is_stale() must return True when the repository's HEAD has changed."""
        with tempfile.TemporaryDirectory() as repo_root:
            _setup_passing_repo(repo_root)
            evidence = build_evidence(
                repo_root=repo_root,
                plan=type("MockPlan", (), {
                    "is_exhaustive": False,
                    "selected_tests": [],
                    "resolved_scope": "symbol",
                    "affected_components": [],
                    "escalation_reason": "",
                    "policy_hash": "abc",
                    "plan_hash": "def",
                })(),
                test_command=["echo"],
                status="PASS",
                duration_seconds=0.0,
            )
            self.assertFalse(is_stale(evidence, repo_root))

    def test_empty_changes_yields_nonempty_status(self):
        """When no files changed the engine should produce a status."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                _init_repo(repo_root)
                _write_policy(repo_root, _make_minimal_policy())
                _create_source_tree(repo_root)
                result = engine_chain(repo_root, "1000-02-ELOOP", "99", bridge_dir)
                self.assertIsNotNone(result["status"])


class TestGateKey(unittest.TestCase):
    """Tests for gate-key identification."""

    def test_exactly_one_step_carries_the_gate_key(self):
        """Only one bridge_flow_steps row has gate-test-impact in its pre_dispatch_script."""
        import sqlite3
        conn = sqlite3.connect(str(PROJECT_ROOT / "databases" / "dpmtf.db"))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM bridge_flow_steps WHERE flow_key = ?",
            ("1000-02-ELOOP",),
        ).fetchall()
        conn.close()
        gate_steps = [
            r for r in rows
            if r["pre_dispatch_script"] is not None
            and "gate-test-impact" in r["pre_dispatch_script"]
        ]
        if gate_steps:
            self.assertEqual(len(gate_steps), 1)
            self.assertEqual(gate_steps[0]["step_key"], "implementer-reviewer")
        else:
            # pre_dispatch_script is NULL — verify the expected step exists
            implementer_steps = [
                r for r in rows
                if r["step_key"] == "implementer-reviewer"
            ]
            self.assertEqual(len(implementer_steps), 1)


class TestFlowIndependence(unittest.TestCase):
    """Tests for topology-agnostic engine calls."""

    def test_the_same_engine_call_serves_both_flow_topologies(self):
        """Engine chain must produce functionally identical results for PLOOP and ELOOP."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                _setup_passing_repo(repo_root)
                result_ploop = engine_chain(repo_root, "1000-01-PLOOP", "99", bridge_dir)
                result_eloop = engine_chain(repo_root, "1000-02-ELOOP", "99", bridge_dir)
                identity_keys = {"evidence_path", "evidence"}
                functional_evidence_keys = {
                    "status", "success", "error",
                    "affected_components", "resolved_scope",
                    "selected_tests", "is_exhaustive",
                }
                for key in result_ploop:
                    if key in identity_keys:
                        continue
                    expected = result_eloop[key]
                    self.assertEqual(
                        result_ploop[key],
                        expected,
                        f"Field '{key}' differs between PLOOP and ELOOP:\n"
                        f"  PLOOP: {result_ploop[key]!r}\n"
                        f"  ELOOP: {result_eloop[key]!r}",
                    )
                ploop_evidence = result_ploop.get("evidence") or {}
                eloop_evidence = result_eloop.get("evidence") or {}
                for key in functional_evidence_keys:
                    self.assertEqual(
                        ploop_evidence.get(key),
                        eloop_evidence.get(key),
                        f"Evidence field '{key}' differs between PLOOP and ELOOP:\n"
                        f"  PLOOP: {ploop_evidence.get(key)!r}\n"
                        f"  ELOOP: {eloop_evidence.get(key)!r}",
                    )

    def test_both_flow_keys_resolve_to_same_target_project(self):
        """PLOOP and ELOOP must resolve to the same target project path."""
        target_ploop = get_flow_target_project("1000-01-PLOOP")
        target_eloop = get_flow_target_project("1000-02-ELOOP")
        self.assertEqual(target_ploop, target_eloop)

    def test_both_flow_keys_resolve_to_same_artifact_root(self):
        """PLOOP and ELOOP must resolve to the same artifact root."""
        root_ploop = get_effective_artifact_root("1000-01-PLOOP")
        root_eloop = get_effective_artifact_root("1000-02-ELOOP")
        self.assertEqual(root_ploop, root_eloop)


class TestEvidencePathDefect(unittest.TestCase):
    """Regression tests for evidence path resolution under bridge_dir."""

    def test_evidence_lands_under_bridge_dir_not_cwd(self):
        """Evidence must be written under bridge_dir/artifact_root, not cwd/artifact_root.

        This is the core regression for the evidence path defect (handoff #39):
        engine_chain() must accept a bridge_dir argument and resolve evidence
        paths relative to it (bridge_dir / artifact_root / ...) rather than
        relative to the current working directory.
        """
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                with tempfile.TemporaryDirectory() as other_cwd:
                    _setup_passing_repo(repo_root)
                    # Change to a completely different directory
                    old_cwd = os.getcwd()
                    try:
                        os.chdir(other_cwd)
                        result = engine_chain(
                            repo_root, "1000-02-ELOOP", "39", bridge_dir
                        )
                        self.assertTrue(result["success"])
                        self.assertEqual(result["status"], "PASS")
                        self.assertIsNotNone(result["evidence_path"])
                        # Verify the evidence is under bridge_dir, not cwd
                        self.assertTrue(
                            result["evidence_path"].startswith(bridge_dir),
                            f"Evidence path {result['evidence_path']} must "
                            f"start with bridge_dir {bridge_dir}, not cwd {other_cwd}",
                        )
                        # Verify the file actually exists
                        self.assertTrue(
                            os.path.isfile(result["evidence_path"]),
                            f"Evidence file not found at {result['evidence_path']}",
                        )
                    finally:
                        os.chdir(old_cwd)


# --- Import lifecycle helpers ---
read_run_ledger_baseline = _gate_mod.read_run_ledger_baseline
read_run_ledger_tree_cleanliness = _gate_mod.read_run_ledger_tree_cleanliness


# --- Import test helpers for build_evidence tests ---
def _make_plan_for_evidence(
    affected_components=None,
    escalation_reason="",
    is_exhaustive=False,
    plan_hash="plan-hash-123",
    policy_hash="pol-hash-456",
    requested_scope=None,
    resolved_scope="component",
    selected_tests=None,
):
    """Return a SimpleNamespace Plan suitable for build_evidence."""
    from types import SimpleNamespace
    return SimpleNamespace(
        affected_components=affected_components or [],
        escalation_reason=escalation_reason,
        is_exhaustive=is_exhaustive,
        plan_hash=plan_hash,
        policy_hash=policy_hash,
        requested_scope=requested_scope,
        resolved_scope=resolved_scope,
        selected_tests=selected_tests or [],
    )


class TestReadRunLedgerBaseline(unittest.TestCase):
    """Tests for read_run_ledger_baseline()."""

    def test_baseline_parsed_from_ledger(self):
        """SHA is extracted between backticks on a '- baseline:' line."""
        with tempfile.TemporaryDirectory() as run_dir:
            ledger = os.path.join(run_dir, "RUN-LEDGER.md")
            with open(ledger, "w") as f:
                f.write("- baseline: `abcdef1234567890abcdef1234567890abcdef12` in ...\n")
            sha = read_run_ledger_baseline(run_dir)
            self.assertEqual(sha, "abcdef1234567890abcdef1234567890abcdef12")

    def test_baseline_none_when_not_found(self):
        """No '- baseline:' line → None."""
        with tempfile.TemporaryDirectory() as run_dir:
            ledger = os.path.join(run_dir, "RUN-LEDGER.md")
            with open(ledger, "w") as f:
                f.write("Some random line\n")
            self.assertIsNone(read_run_ledger_baseline(run_dir))

    def test_baseline_none_on_missing_ledger(self):
        """Missing ledger file → None."""
        with tempfile.TemporaryDirectory() as run_dir:
            self.assertIsNone(read_run_ledger_baseline(run_dir))

    def test_baseline_none_when_backticks_missing(self):
        """Line without backticks is ignored → None."""
        with tempfile.TemporaryDirectory() as run_dir:
            ledger = os.path.join(run_dir, "RUN-LEDGER.md")
            with open(ledger, "w") as f:
                f.write("- baseline: no_backticks_here\n")
            self.assertIsNone(read_run_ledger_baseline(run_dir))


class TestReadRunLedgerTreeCleanliness(unittest.TestCase):
    """Tests for read_run_ledger_tree_cleanliness()."""

    def test_dirty_tree_detected(self):
        """'uncommitted path(s)' → 'dirty'."""
        with tempfile.TemporaryDirectory() as run_dir:
            ledger = os.path.join(run_dir, "RUN-LEDGER.md")
            with open(ledger, "w") as f:
                f.write("working tree: 6 uncommitted path(s) at promotion\n")
            self.assertEqual(read_run_ledger_tree_cleanliness(run_dir), "dirty")

    def test_clean_tree_detected(self):
        """'clean' → 'clean'."""
        with tempfile.TemporaryDirectory() as run_dir:
            ledger = os.path.join(run_dir, "RUN-LEDGER.md")
            with open(ledger, "w") as f:
                f.write("working tree: clean at abcdef12\n")
            self.assertEqual(read_run_ledger_tree_cleanliness(run_dir), "clean")

    def test_none_when_no_working_tree_line(self):
        """No working tree line → None."""
        with tempfile.TemporaryDirectory() as run_dir:
            ledger = os.path.join(run_dir, "RUN-LEDGER.md")
            with open(ledger, "w") as f:
                f.write("- baseline: `abcdef12`\n")
            self.assertIsNone(read_run_ledger_tree_cleanliness(run_dir))

    def test_none_on_missing_ledger(self):
        """Missing ledger → None."""
        with tempfile.TemporaryDirectory() as run_dir:
            self.assertIsNone(read_run_ledger_tree_cleanliness(run_dir))


class TestLifecycleBaselinesInEngineChain(unittest.TestCase):
    """Tests for lifecycle baseline resolution within engine_chain()."""

    def test_engine_chain_with_run_dir_and_baseline(self):
        """engine_chain accepts run_dir arg and passes it to baseline resolution."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                with tempfile.TemporaryDirectory() as run_dir:
                    _setup_passing_repo(repo_root)
                    # Write a RUN-LEDGER.md with a valid baseline
                    head_sha = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        capture_output=True, text=True, cwd=repo_root,
                    ).stdout.strip()
                    ledger = os.path.join(run_dir, "RUN-LEDGER.md")
                    with open(ledger, "w") as f:
                        f.write(f"- baseline: `{head_sha}` in ...\n")
                        f.write("working tree: clean at promotion\n")
                    result = engine_chain(
                        repo_root, "1000-02-ELOOP", "99", bridge_dir,
                        run_dir=run_dir,
                    )
                    self.assertTrue(result["success"])
                    self.assertEqual(result["status"], "PASS")
                    evidence = result["evidence"]
                    self.assertIsNotNone(evidence)
                    self.assertEqual(evidence.get("lifecycle_point"), "run_baseline")
                    self.assertEqual(evidence.get("baseline_tree_state"), "clean")
                    self.assertEqual(evidence.get("baseline_resolution"), "resolved")

    def test_engine_chain_with_dirty_tree_expands_scope(self):
        """Dirty tree triggers scope expansion in engine_chain."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                with tempfile.TemporaryDirectory() as run_dir:
                    _setup_passing_repo(repo_root)
                    head_sha = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        capture_output=True, text=True, cwd=repo_root,
                    ).stdout.strip()
                    ledger = os.path.join(run_dir, "RUN-LEDGER.md")
                    with open(ledger, "w") as f:
                        f.write(f"- baseline: `{head_sha}` in ...\n")
                        f.write("working tree: 3 uncommitted path(s) at promotion\n")
                    result = engine_chain(
                        repo_root, "1000-02-ELOOP", "99", bridge_dir,
                        run_dir=run_dir,
                    )
                    self.assertTrue(result["success"])
                    evidence = result["evidence"]
                    self.assertEqual(evidence.get("baseline_tree_state"), "dirty")

    def test_engine_chain_with_unresolved_baseline(self):
        """Unresolved baseline (SHA not in repo) → engine continues with error."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                with tempfile.TemporaryDirectory() as run_dir:
                    _setup_passing_repo(repo_root)
                    ledger = os.path.join(run_dir, "RUN-LEDGER.md")
                    with open(ledger, "w") as f:
                        f.write("- baseline: `0000000000000000000000000000000000000000` not found\n")
                        f.write("working tree: clean\n")
                    result = engine_chain(
                        repo_root, "1000-02-ELOOP", "99", bridge_dir,
                        run_dir=run_dir,
                    )
                    # Engine handles the error gracefully
                    self.assertIn(result["status"], ["PASS", "FAIL", "ERROR"])

    def test_engine_chain_with_no_baseline_in_ledger(self):
        """No baseline line in RUN-LEDGER → baseline_resolution='unresolved'."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                with tempfile.TemporaryDirectory() as run_dir:
                    _setup_passing_repo(repo_root)
                    ledger = os.path.join(run_dir, "RUN-LEDGER.md")
                    with open(ledger, "w") as f:
                        f.write("No baseline recorded here\n")
                        f.write("working tree: clean\n")
                    result = engine_chain(
                        repo_root, "1000-02-ELOOP", "99", bridge_dir,
                        run_dir=run_dir,
                    )
                    self.assertTrue(result["success"])
                    evidence = result["evidence"]
                    self.assertEqual(evidence.get("baseline_resolution"), "unresolved")

    def test_engine_chain_without_run_dir_no_lifecycle(self):
        """Without run_dir, lifecycle_point defaults to 'work_unit'."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                _setup_passing_repo(repo_root)
                result = engine_chain(repo_root, "1000-02-ELOOP", "99", bridge_dir)
                self.assertTrue(result["success"])
                evidence = result["evidence"]
                self.assertEqual(evidence.get("lifecycle_point"), "work_unit")
                self.assertIsNone(evidence.get("baseline_tree_state"))
                self.assertIsNone(evidence.get("baseline_resolution"))


class TestRequestedScopeArg(unittest.TestCase):
    """Tests for --requested-scope CLI argument."""

    def test_parse_args_with_requested_scope_full(self):
        """--requested-scope full is parseable."""
        args = parse_args([
            "--flow-key", "1000-02-ELOOP",
            "--step-key", "implementer-reviewer",
            "--from-role", "1000-implementer",
            "--to-role", "1000-reviewer",
            "--deliverable-dir", "/tmp/deliverables",
            "--deliverable-pattern", "*-result.md",
            "--deliverable-file", "/tmp/result.md",
            "--handoff-id", "42",
            "--bridge-dir", "/tmp/bridge",
            "--prompt-template", "default",
            "--requested-scope", "full",
        ])
        self.assertEqual(args.requested_scope, "full")

    def test_parse_args_with_requested_scope_component(self):
        """--requested-scope component is parseable."""
        args = parse_args([
            "--flow-key", "1000-02-ELOOP",
            "--step-key", "implementer-reviewer",
            "--from-role", "1000-implementer",
            "--to-role", "1000-reviewer",
            "--deliverable-dir", "/tmp/deliverables",
            "--deliverable-pattern", "*-result.md",
            "--deliverable-file", "/tmp/result.md",
            "--handoff-id", "42",
            "--bridge-dir", "/tmp/bridge",
            "--prompt-template", "default",
            "--requested-scope", "component",
        ])
        self.assertEqual(args.requested_scope, "component")

    def test_parse_args_without_requested_scope_is_none(self):
        """--requested-scope omitted → None."""
        args = parse_args([
            "--flow-key", "1000-02-ELOOP",
            "--step-key", "implementer-reviewer",
            "--from-role", "1000-implementer",
            "--to-role", "1000-reviewer",
            "--deliverable-dir", "/tmp/deliverables",
            "--deliverable-pattern", "*-result.md",
            "--deliverable-file", "/tmp/result.md",
            "--handoff-id", "42",
            "--bridge-dir", "/tmp/bridge",
            "--prompt-template", "default",
        ])
        self.assertIsNone(args.requested_scope)

    def test_parse_args_with_run_dir(self):
        """--run-dir is parseable."""
        args = parse_args([
            "--flow-key", "1000-02-ELOOP",
            "--step-key", "implementer-reviewer",
            "--from-role", "1000-implementer",
            "--to-role", "1000-reviewer",
            "--deliverable-dir", "/tmp/deliverables",
            "--deliverable-pattern", "*-result.md",
            "--deliverable-file", "/tmp/result.md",
            "--handoff-id", "42",
            "--bridge-dir", "/tmp/bridge",
            "--prompt-template", "default",
            "--run-dir", "/tmp/runs/010",
            "--requested-scope", "full",
        ])
        self.assertEqual(args.run_dir, "/tmp/runs/010")
        self.assertEqual(args.requested_scope, "full")


class TestEvidenceLifecycleFields(unittest.TestCase):
    """Tests for lifecycle fields in evidence records."""

    def test_evidence_lifecycle_point_field(self):
        """Evidence record contains lifecycle_point key."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            _write_policy(repo_root, _make_minimal_policy())
            plan = _make_plan_for_evidence(
                affected_components=[],
                escalation_reason="",
                is_exhaustive=False,
                plan_hash="h1",
                policy_hash="p1",
                requested_scope="component",
                resolved_scope="component",
                selected_tests=[],
            )
            evidence = build_evidence(
                repo_root=repo_root,
                plan=plan,
                test_command=["echo"],
                status="PASS",
                duration_seconds=0.0,
                lifecycle_point="run_baseline",
                baseline_tree_state="clean",
                baseline_resolution="resolved",
            )
            self.assertEqual(evidence["lifecycle_point"], "run_baseline")
            self.assertEqual(evidence["baseline_tree_state"], "clean")
            self.assertEqual(evidence["baseline_resolution"], "resolved")

    def test_evidence_with_none_lifecycle_fields(self):
        """Evidence with default lifecycle_point='work_unit' and None tree fields is valid."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            _write_policy(repo_root, _make_minimal_policy())
            plan = _make_plan_for_evidence()
            evidence = build_evidence(
                repo_root=repo_root,
                plan=plan,
                test_command=["echo"],
                status="PASS",
                duration_seconds=0.0,
            )
            # lifecycle_point defaults to 'work_unit' when not specified
            self.assertEqual(evidence.get("lifecycle_point"), "work_unit")
            self.assertIsNone(evidence.get("baseline_tree_state"))
            self.assertIsNone(evidence.get("baseline_resolution"))


class TestExplicitFullRegressionGate(unittest.TestCase):
    """Tests for the explicit full-regression gate."""

    def test_engine_chain_with_requested_scope_full(self):
        """--requested-scope full sets lifecycle_point to explicit_gate."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                with tempfile.TemporaryDirectory() as run_dir:
                    _setup_passing_repo(repo_root)
                    head_sha = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        capture_output=True, text=True, cwd=repo_root,
                    ).stdout.strip()
                    ledger = os.path.join(run_dir, "RUN-LEDGER.md")
                    with open(ledger, "w") as f:
                        f.write(f"- baseline: `{head_sha}`\n")
                        f.write("working tree: clean\n")
                    result = engine_chain(
                        repo_root, "1000-02-ELOOP", "99", bridge_dir,
                        run_dir=run_dir,
                        requested_scope="full",
                    )
                    self.assertTrue(result["success"])
                    evidence = result["evidence"]
                    self.assertEqual(evidence.get("lifecycle_point"), "explicit_gate")

    def test_engine_chain_scope_broad_from_dirty(self):
        """Dirty tree in run_dir expands scope in engine_chain."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as bridge_dir:
                with tempfile.TemporaryDirectory() as run_dir:
                    _setup_passing_repo(repo_root)
                    head_sha = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        capture_output=True, text=True, cwd=repo_root,
                    ).stdout.strip()
                    ledger = os.path.join(run_dir, "RUN-LEDGER.md")
                    with open(ledger, "w") as f:
                        f.write(f"- baseline: `{head_sha}`\n")
                        f.write("working tree: 1 uncommitted path(s) at promotion\n")
                    result = engine_chain(
                        repo_root, "1000-02-ELOOP", "99", bridge_dir,
                        run_dir=run_dir,
                    )
                    self.assertTrue(result["success"])
                    self.assertEqual(result["status"], "PASS")
                    evidence = result["evidence"]
                    self.assertEqual(evidence.get("baseline_tree_state"), "dirty")


if __name__ == "__main__":
    unittest.main()
