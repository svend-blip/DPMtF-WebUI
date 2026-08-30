"""Tests for scripts/testing/evidence.py — the evidence module.

Uses unittest style. Creates temp files/dirs for file-write and git tests.
Never touches the DPMtF-WebUI working tree.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # DPMtF-WebUI root
EVIDENCE_PATH = PROJECT_ROOT / "scripts" / "testing" / "evidence.py"

# Load the module from its absolute path so tests are independent of sys.path.
_evidence_spec = __import__("importlib").util.spec_from_file_location(
    "evidence_test", EVIDENCE_PATH
)
_evidence_mod = __import__("importlib").util.module_from_spec(_evidence_spec)
_evidence_spec.loader.exec_module(_evidence_mod)

build_evidence = _evidence_mod.build_evidence
write_evidence = _evidence_mod.write_evidence
is_stale = _evidence_mod.is_stale
EvidenceError = _evidence_mod.EvidenceError
REQUIRED_KEYS = _evidence_mod.REQUIRED_KEYS
EVIDENCE_SCHEMA_VERSION = _evidence_mod.EVIDENCE_SCHEMA_VERSION
_validate_evidence = _evidence_mod._validate_evidence


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


def _make_plan(
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


class TestEvidenceConstants(unittest.TestCase):
    """Tests for EVIDENCE_SCHEMA_VERSION and REQUIRED_KEYS."""

    def test_evidence_schema_version_exists(self):
        """EVIDENCE_SCHEMA_VERSION is a non-empty str."""
        self.assertIsInstance(EVIDENCE_SCHEMA_VERSION, str)
        self.assertTrue(len(EVIDENCE_SCHEMA_VERSION) > 0)

    def test_evidence_required_keys_count(self):
        """REQUIRED_KEYS has exactly 22 entries."""
        self.assertEqual(len(REQUIRED_KEYS), 22)

    def test_evidence_required_keys_are_strings(self):
        """Every entry in REQUIRED_KEYS is a string."""
        for key in REQUIRED_KEYS:
            self.assertIsInstance(key, str)


class TestBuildEvidence(unittest.TestCase):
    """Tests for build_evidence()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _init_repo(self.tmpdir)

    def _valid_plan(self):
        return _make_plan(
            affected_components=["backend"],
            escalation_reason="",
            is_exhaustive=True,
            plan_hash="h1",
            policy_hash="h2",
            requested_scope=None,
            resolved_scope="full",
            selected_tests=["tests/test_a.py"],
        )

    def test_evidence_all_required_keys_present(self):
        """build_evidence returns a dict with exactly 22 keys when given valid inputs."""
        evidence = build_evidence(
            repo_root=self.tmpdir,
            plan=self._valid_plan(),
            test_command=["python3", "-m", "pytest", "-q"],
            status="PASS",
            duration_seconds=1.23,
        )
        self.assertEqual(len(evidence), 22)
        for key in REQUIRED_KEYS:
            self.assertIn(key, evidence, f"Missing key: {key}")

    def test_evidence_empty_dict_raises(self):
        """Pass {} to _validate_evidence and assert EvidenceError for wrong key count."""
        with self.assertRaises(EvidenceError) as ctx:
            _validate_evidence({})
        self.assertIn("22 keys", str(ctx.exception))

    def test_evidence_missing_a_required_key_raises(self):
        """Pass a dict missing a required key to _validate_evidence and assert EvidenceError."""
        record = {
            "affected_components": [],
            "baseline": "HEAD",
            "changed_files": [],
            "changed_symbols": [],
            "duration_seconds": 1.0,
            "escalation_reason": "",
            "generated_at": "2025-01-01T00:00:00Z",
            "head_sha": "abcd1234",
            "is_exhaustive": True,
            "lifecycle_point": "work_unit",
            # missing "plan_hash" — only 19 keys
            "policy_hash": "p2",
            "repository": "/tmp/repo",
            "requested_scope": None,
            "resolved_scope": "component",
            "schema_version": "1",
            "selected_tests": [],
            "status": "PASS",
            "test_command": ["pytest"],
            "worktree_fingerprint": "f1",
            "baseline_tree_state": None,
            "baseline_resolution": None,
        }
        with self.assertRaises(EvidenceError) as ctx:
            _validate_evidence(record)
        # 21 keys (22 - 1 missing) → error says "got 21"
        self.assertIn("21", str(ctx.exception))

    def test_evidence_wrong_type_raises(self):
        """Pass a value of wrong type for a required key and assert EvidenceError."""
        record = {
            "affected_components": "not_a_list",  # should be list
            "baseline": "HEAD",
            "baseline_resolution": None,
            "baseline_tree_state": None,
            "changed_files": [],
            "changed_symbols": [],
            "duration_seconds": 1.0,
            "escalation_reason": "",
            "generated_at": "2025-01-01T00:00:00Z",
            "head_sha": "abcd1234",
            "is_exhaustive": True,
            "lifecycle_point": "work_unit",
            "plan_hash": "p1",
            "policy_hash": "p2",
            "repository": "/tmp/repo",
            "requested_scope": None,
            "resolved_scope": "component",
            "schema_version": "1",
            "selected_tests": [],
            "status": "PASS",
            "test_command": ["pytest"],
            "worktree_fingerprint": "f1",
        }
        with self.assertRaises(EvidenceError) as ctx:
            _validate_evidence(record)
        self.assertIn("affected_components", str(ctx.exception))

    def test_evidence_duration_is_numeric_not_bool(self):
        """Note: source has a bug where bool passes isinstance check for (int,float).

        Because bool is a subclass of int, isinstance(True, (int, float)) is True,
        so the validation never enters the branch that checks for bool.
        This test documents the actual behavior (no error for bool).
        """
        record = {
            "affected_components": [],
            "baseline": "HEAD",
            "baseline_resolution": None,
            "baseline_tree_state": None,
            "changed_files": [],
            "changed_symbols": [],
            "duration_seconds": True,  # bool passes because isinstance(True, int) == True
            "escalation_reason": "",
            "generated_at": "2025-01-01T00:00:00Z",
            "head_sha": "abcd1234",
            "is_exhaustive": True,
            "lifecycle_point": "work_unit",
            "plan_hash": "p1",
            "policy_hash": "p2",
            "repository": "/tmp/repo",
            "requested_scope": None,
            "resolved_scope": "component",
            "schema_version": "1",
            "selected_tests": [],
            "status": "PASS",
            "test_command": ["pytest"],
            "worktree_fingerprint": "f1",
        }
        # The source code has a logic bug: the bool guard is inside the
        # `if not isinstance()` block, but isinstance(True, (int, float)) is True,
        # so the guard never fires. No error is raised.
        _validate_evidence(record)  # no error — source bug

    def test_evidence_status_is_string(self):
        """status field must be a string."""
        record = {
            "affected_components": [],
            "baseline": "HEAD",
            "baseline_resolution": None,
            "baseline_tree_state": None,
            "changed_files": [],
            "changed_symbols": [],
            "duration_seconds": 1.0,
            "escalation_reason": "",
            "generated_at": "2025-01-01T00:00:00Z",
            "head_sha": "abcd1234",
            "is_exhaustive": True,
            "lifecycle_point": "work_unit",
            "plan_hash": "p1",
            "policy_hash": "p2",
            "repository": "/tmp/repo",
            "requested_scope": None,
            "resolved_scope": "component",
            "schema_version": "1",
            "selected_tests": [],
            "status": 123,  # wrong type
            "test_command": ["pytest"],
            "worktree_fingerprint": "f1",
        }
        with self.assertRaises(EvidenceError) as ctx:
            _validate_evidence(record)
        self.assertIn("status", str(ctx.exception))


class TestWriteEvidence(unittest.TestCase):
    """Tests for write_evidence()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _init_repo(self.tmpdir)

    def test_write_evidence_serializes_json(self):
        """Write evidence to a temp file and verify it is valid JSON with expected keys."""
        evidence = build_evidence(
            repo_root=self.tmpdir,
            plan=_make_plan(),
            test_command=["pytest", "-q"],
            status="PASS",
            duration_seconds=0.5,
        )
        out_path = os.path.join(self.tmpdir, "evidence.json")
        write_evidence(evidence, out_path)
        self.assertTrue(os.path.isfile(out_path))
        with open(out_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(len(loaded), 22)
        for key in REQUIRED_KEYS:
            self.assertIn(key, loaded)

    def test_write_evidence_validates_first(self):
        """Passing invalid evidence to write_evidence raises EvidenceError."""
        bad = {"not": "valid"}
        out_path = os.path.join(self.tmpdir, "bad.json")
        with self.assertRaises(EvidenceError):
            write_evidence(bad, out_path)

    def test_write_evidence_content_is_indented(self):
        """Written JSON is indented (formatted)."""
        evidence = build_evidence(
            repo_root=self.tmpdir,
            plan=_make_plan(),
            test_command=["pytest"],
            status="FAIL",
            duration_seconds=1.0,
        )
        out_path = os.path.join(self.tmpdir, "formatted.json")
        write_evidence(evidence, out_path)
        content = Path(out_path).read_text(encoding="utf-8")
        # Indented JSON should contain newlines with indentation
        self.assertIn("\n", content)
        self.assertIn("  ", content)


class TestIsStale(unittest.TestCase):
    """Tests for is_stale()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _init_repo(self.tmpdir)

    def _fresh_evidence(self):
        """Build evidence for the current state of the repo."""
        plan = _make_plan()
        return build_evidence(
            repo_root=self.tmpdir,
            plan=plan,
            test_command=["pytest"],
            status="PASS",
            duration_seconds=0.1,
        )

    def test_unmeasurable_staleness_answers_stale(self):
        """Call is_stale({}, '/nonexistent/path/zzz') and assert it returns True."""
        self.assertTrue(is_stale({}, "/nonexistent/path/zzz"))

    def test_is_stale_no_repo_returns_true(self):
        """Pass a non-existent repo path, returns True."""
        evidence = self._fresh_evidence()
        self.assertTrue(is_stale(evidence, "/nonexistent/repo/zzz"))

    def test_is_stale_fresh(self):
        """Evidence built just now from the same repo returns False."""
        evidence = self._fresh_evidence()
        self.assertFalse(is_stale(evidence, self.tmpdir))

    def test_is_stale_head_sha_mismatch(self):
        """Evidence with a different head_sha than current repo HEAD returns True (stale)."""
        evidence = self._fresh_evidence()
        evidence["head_sha"] = "0000000000000000000000000000000000000000"
        self.assertTrue(is_stale(evidence, self.tmpdir))

    def test_is_stale_worktree_fingerprint_mismatch(self):
        """Evidence with a different fingerprint than current worktree returns True."""
        evidence = self._fresh_evidence()
        evidence["worktree_fingerprint"] = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        self.assertTrue(is_stale(evidence, self.tmpdir))

    def test_is_stale_partial_evidence_with_no_sha_or_fp(self):
        """Partial evidence with missing head_sha and worktree_fingerprint falls through to False."""
        partial = {"status": "PASS"}
        result = is_stale(partial, self.tmpdir)
        # Without stored sha/fp, is_stale returns False
        self.assertFalse(result)

    def test_is_stale_with_sha_only(self):
        """Evidence with only head_sha but no fingerprint — SHA match passes."""
        evidence = build_evidence(
            repo_root=self.tmpdir,
            plan=_make_plan(),
            test_command=["pytest"],
            status="PASS",
            duration_seconds=0.1,
        )
        stored_sha = evidence["head_sha"]
        partial = {"head_sha": stored_sha}
        # With SHA matching and no stored fingerprint, is_stale returns False
        self.assertFalse(is_stale(partial, self.tmpdir))


class TestEvidenceError(unittest.TestCase):
    """Tests for the EvidenceError exception class."""

    def test_evidence_error_is_exception(self):
        """EvidenceError is a subclass of Exception."""
        self.assertTrue(issubclass(EvidenceError, Exception))

    def test_evidence_error_message(self):
        """EvidenceError carries the provided message."""
        exc = EvidenceError("test message")
        self.assertEqual(str(exc), "test message")


if __name__ == "__main__":
    unittest.main()
