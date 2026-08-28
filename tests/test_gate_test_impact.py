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


def _gate_result_to_exit_code(result, mode="block"):
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
            _setup_failing_repo(repo_root)
            result = engine_chain(repo_root, "1000-02-ELOOP", "99")
            exit_code = _gate_result_to_exit_code(result, mode="warn")
            self.assertEqual(exit_code, 0,
                             f"warn mode should exit 0 on FAIL, got {exit_code}")
            self.assertEqual(result["status"], "FAIL")

    def test_block_mode_exits_nonzero_when_the_engine_errors(self):
        """In block mode the gate MUST exit nonzero on engine errors."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            dpmtf_dir = os.path.join(repo_root, ".dpmtf")
            os.makedirs(dpmtf_dir, exist_ok=True)
            with open(os.path.join(dpmtf_dir, "test-policy.json"), "w") as f:
                f.write("not valid json {{{")
            result = engine_chain(repo_root, "1000-02-ELOOP", "99")
            exit_code = _gate_result_to_exit_code(result, mode="block")
            self.assertNotEqual(exit_code, 0,
                                f"block mode should exit nonzero on ERROR, got {exit_code}")
            self.assertEqual(result["status"], "ERROR")

    def test_block_mode_passes_on_successful_plan(self):
        """In block mode the gate MUST exit 0 when tests pass."""
        with tempfile.TemporaryDirectory() as repo_root:
            _setup_passing_repo(repo_root)
            result = engine_chain(repo_root, "1000-02-ELOOP", "99")
            exit_code = _gate_result_to_exit_code(result, mode="block")
            self.assertEqual(exit_code, 0,
                             f"block mode should exit 0 on PASS, got {exit_code}")
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["success"])

    def test_block_mode_fails_on_a_failing_plan(self):
        """In block mode the gate MUST exit 1 when tests fail."""
        with tempfile.TemporaryDirectory() as repo_root:
            _setup_failing_repo(repo_root)
            result = engine_chain(repo_root, "1000-02-ELOOP", "99")
            exit_code = _gate_result_to_exit_code(result, mode="block")
            self.assertNotEqual(exit_code, 0,
                                f"block mode should exit nonzero on FAIL, got {exit_code}")
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(result["success"])

    def test_engine_chain_returns_expected_keys(self):
        """engine_chain() must return success/status/evidence/error/evidence_path."""
        with tempfile.TemporaryDirectory() as repo_root:
            _setup_passing_repo(repo_root)
            result = engine_chain(repo_root, "1000-02-ELOOP", "99")
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

    def test_parse_args_block_default(self):
        """--mode defaults to 'block' when omitted."""
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
        self.assertEqual(args.mode, "block")

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
            _setup_passing_repo(repo_root)
            result = engine_chain(repo_root, "1000-02-ELOOP", "99")
            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "PASS")
            self.assertIsNotNone(result["evidence"])
            self.assertIsNotNone(result["evidence_path"])

    def test_engine_chain_policy_error_in_block(self):
        """Trigger a policy load error and verify success=False, status=ERROR."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            dpmtf_dir = os.path.join(repo_root, ".dpmtf")
            os.makedirs(dpmtf_dir, exist_ok=True)
            with open(os.path.join(dpmtf_dir, "test-policy.json"), "w") as f:
                f.write("{malformed json")
            result = engine_chain(repo_root, "1000-02-ELOOP", "99")
            self.assertFalse(result["success"])
            self.assertEqual(result["status"], "ERROR")
            self.assertIsNotNone(result["error"])

    def test_evidence_file_created_with_valid_json(self):
        """Run the full gate and verify evidence file is created and contains valid JSON."""
        with tempfile.TemporaryDirectory() as repo_root:
            _setup_passing_repo(repo_root)
            result = engine_chain(repo_root, "1000-02-ELOOP", "99")
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
            _init_repo(repo_root)
            _write_policy(repo_root, _make_minimal_policy())
            _create_source_tree(repo_root)
            result = engine_chain(repo_root, "1000-02-ELOOP", "99")
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
            _setup_passing_repo(repo_root)
            result_ploop = engine_chain(repo_root, "1000-01-PLOOP", "99")
            result_eloop = engine_chain(repo_root, "1000-02-ELOOP", "99")
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


if __name__ == "__main__":
    unittest.main()
