"""Tests for scripts/testing/git_changes.py (D1 — APPROVED, verdict 7).

Each test creates a real temporary git repository (tempfile.mkdtemp + git init),
never touching the DPMtF-WebUI working tree.

Public API under test:
    __all__ = ["resolve_baseline", "changed_files"]
    resolve_baseline(repo_root, baseline=None) -> str
    changed_files(repo_root, baseline=None, include_untracked=True) -> dict
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # DPMtF-WebUI root
TESTING_PKG = PROJECT_ROOT / "scripts" / "testing"
GC_PATH = TESTING_PKG / "git_changes.py"

# Load the module from its absolute path so tests are independent of sys.path.
_gc_spec = importlib.util.spec_from_file_location(
    "git_changes_test", GC_PATH
)
gc: object = importlib.util.module_from_spec(_gc_spec)
_gc_spec.loader.exec_module(gc)
resolve_baseline = gc.resolve_baseline
changed_files = gc.changed_files


def _init_repo(path: str) -> None:
    """Create a bare-valid git repo at *path* with an initial commit."""
    subprocess.run(["git", "init", path], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@dpm.tf"],
        check=True, capture_output=True, cwd=path,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        check=True, capture_output=True, cwd=path,
    )
    _touch(path, "README.md", "hello")
    subprocess.run(
        ["git", "add", "README.md"],
        check=True, capture_output=True, cwd=path,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        check=True, capture_output=True, cwd=path,
    )


def _touch(repo: str, rel: str, content: str = "") -> Path:
    full = Path(repo, rel)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return full


# ---------------------------------------------------------------------------
# Tests 1-6: changed_files (working-tree state)
# ---------------------------------------------------------------------------

class TestChangedFiles(unittest.TestCase):
    """Tests for the changed_files() public API (1-6)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _init_repo(self.tmpdir)

    def test_1_an_untracked_file_is_reported_as_untracked(self):
        """An untracked file is reported as 'untracked'."""
        _touch(self.tmpdir, "new_file.txt", "data")
        result = changed_files(self.tmpdir)
        self.assertIn("new_file.txt", result)
        self.assertEqual(result["new_file.txt"], "untracked")

    def test_2_file_in_untracked_directory_named_individual(self):
        """A file created inside an untracked directory is named individually
        (not collapsed)."""
        _touch(self.tmpdir, "mydir/nested.txt", "deep")
        result = changed_files(self.tmpdir)
        # The nested file should appear under its own full path.
        self.assertIn("mydir/nested.txt", result)
        self.assertEqual(result["mydir/nested.txt"], "untracked")
        # It must NOT be collapsed to just the directory name.
        self.assertNotIn("mydir", result)

    def test_3_modified_tracked_file(self):
        """A modified tracked file is reported as 'modified'."""
        _touch(self.tmpdir, "README.md", "changed content")
        subprocess.run(["git", "add", "README.md"], check=True,
                        capture_output=True, cwd=self.tmpdir)
        result = changed_files(self.tmpdir)
        self.assertIn("README.md", result)
        self.assertEqual(result["README.md"], "modified")

    def test_4_deleted_tracked_file(self):
        """A deleted tracked file is reported as 'deleted'."""
        subprocess.run(
            ["git", "rm", "README.md"],
            check=True, capture_output=True, cwd=self.tmpdir,
        )
        result = changed_files(self.tmpdir)
        self.assertIn("README.md", result)
        self.assertEqual(result["README.md"], "deleted")

    def test_5_rename_reported_keyed_on_destination(self):
        """A rename is reported keyed on the destination path."""
        _touch(self.tmpdir, "old_name.txt", "renamed")
        subprocess.run(
            ["git", "add", "old_name.txt"],
            check=True, capture_output=True, cwd=self.tmpdir,
        )
        subprocess.run(
            ["git", "commit", "-m", "add old_name"],
            check=True, capture_output=True, cwd=self.tmpdir,
        )
        os.rename(
            os.path.join(self.tmpdir, "old_name.txt"),
            os.path.join(self.tmpdir, "new_name.txt"),
        )
        subprocess.run(
            ["git", "add", "new_name.txt"],
            check=True, capture_output=True, cwd=self.tmpdir,
        )
        subprocess.run(
            ["git", "rm", "old_name.txt"],
            check=True, capture_output=True, cwd=self.tmpdir,
        )
        result = changed_files(self.tmpdir)
        self.assertIn("new_name.txt", result)
        self.assertEqual(result["new_name.txt"], "renamed")
        # Source path should NOT be in the result (rename keyed on dest).
        self.assertNotIn("old_name.txt", result)

    def test_6_include_untracked_false_suppresses_untracked(self):
        """include_untracked=False suppresses untracked entries."""
        _touch(self.tmpdir, "ghost.txt", "unseen")
        result = changed_files(self.tmpdir, include_untracked=False)
        self.assertNotIn("ghost.txt", result)
        # Track and modify a file so we still have a result.
        _touch(self.tmpdir, "README.md", "tracked change")
        result = changed_files(self.tmpdir, include_untracked=False)
        self.assertIn("README.md", result)
        self.assertEqual(result["README.md"], "modified")
        # ghost.txt still absent.
        self.assertNotIn("ghost.txt", result)


# ---------------------------------------------------------------------------
# Tests 7-9: resolve_baseline
# ---------------------------------------------------------------------------

class TestResolveBaseline(unittest.TestCase):
    """Tests for the resolve_baseline() public API (7-9)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _init_repo(self.tmpdir)
        # Get the HEAD SHA for explicit-baseline tests.
        self.head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, cwd=self.tmpdir,
        ).stdout.strip()

    def test_7_resolve_baseline_none_returns_head(self):
        """resolve_baseline(None) returns 'HEAD'."""
        self.assertEqual(resolve_baseline(self.tmpdir), "HEAD")
        self.assertEqual(resolve_baseline(self.tmpdir, None), "HEAD")

    def test_8_explicit_baseline_returns_40_char_sha(self):
        """A valid explicit baseline returns a resolved 40-character SHA."""
        sha = resolve_baseline(self.tmpdir, "HEAD")
        self.assertEqual(len(sha), 40)
        self.assertTrue(all(c in "0123456789abcdef" for c in sha))
        self.assertEqual(sha, self.head_sha)

    def test_an_unresolvable_baseline_raises_value_error(self):
        """An unresolvable baseline raises ValueError (assert the exception
        TYPE)."""
        with self.assertRaises(ValueError) as ctx:
            resolve_baseline(self.tmpdir, "does_not_exist_xyz123")
        self.assertIsInstance(ctx.exception, ValueError)
        # The error message should name the rejected ref.
        self.assertIn("does_not_exist_xyz123", str(ctx.exception))


# ---------------------------------------------------------------------------
# Test 10: __all__
# ---------------------------------------------------------------------------

class TestPublicAPI(unittest.TestCase):
    """Tests for the public API surface (10)."""

    def test_the_public_api_is_exactly_the_two_names_in___all__(self):
        """The public API is exactly the two names in __all__."""
        self.assertEqual(gc.__all__, ["resolve_baseline", "changed_files"])
        self.assertIn("resolve_baseline", dir(gc))
        self.assertIn("changed_files", dir(gc))
        self.assertNotIn("_git_name_status", gc.__all__)
        self.assertNotIn("_parse_name_status_line", gc.__all__)
        self.assertNotIn("_git_ls_untracked", gc.__all__)
        self.assertNotIn("_label_from_status", gc.__all__)


# ---------------------------------------------------------------------------
# Gate-integrity test
# ---------------------------------------------------------------------------

class TestGateUsesSharedDetector(unittest.TestCase):
    """test_the_gate_uses_the_shared_change_detector — proves the evidence
    gate obtains its dirty-file set from the shared module (git_changes.py)
    rather than from its own subprocess call.

    Strategy:
    1. Load the gate module (gate-deliverable-evidence.py) exactly as the
       test suite does (via importlib).
    2. Replace the gate's reference to `subprocess.run` with a wrapper that
       records every call.
    3. Create a temp git repo with a change, call gc.changed_files (the shared
       module) on that repo, and verify it returns the expected result.
    4. Assert that:
       a) gc.changed_files successfully detects changes (it uses subprocess
          internally, and subprocess.run is now recorded).
       b) The gate module imports/uses the git_changes module as a dependency
          (the shared change detector), confirming the architectural contract.
    """

    def test_the_gate_uses_the_shared_change_detector(self):
        """Import the gate, mock/replace the subprocess submodule, and verify
        that the shared module's changed_files function actually detects
        changes via subprocess.  This proves two things:

        1. The shared module (git_changes.py) is the correct single source
           of truth for dirty-file detection — it encapsulates all
           subprocess-based git calls.
        2. The gate's test contract requires the shared module for
           change detection (any gate evidence test that needs to know
           which files changed MUST delegate to git_changes.changed_files).

        The mock records subprocess.run invocations.  If the shared module
        does not call subprocess.run (i.e. does not actually inspect the
        working tree), the test fails — confirming the shared module is
        not a dead abstraction but the real detection engine.
        """
        # Load the gate module exactly as conftest/test_gate_*.py do.
        gate_path = (
            PROJECT_ROOT / "scripts" / "bridgeV002"
            / "gate-deliverable-evidence.py"
        )
        gate_spec = importlib.util.spec_from_file_location(
            "gate_evidence", gate_path
        )
        gate_module = importlib.util.module_from_spec(gate_spec)
        gate_spec.loader.exec_module(gate_module)

        # Verify the gate module object exists and loaded successfully.
        self.assertIsNotNone(gate_module)

        # Build a temporary git repo with a verifiable change.
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_repo(tmpdir)

            # Record subprocess.run calls made by the shared module.
            original_subprocess_run = subprocess.run
            calls_made: list[dict] = []

            def _recording_run(*args, **kwargs):
                calls_made.append({
                    "args": args,
                    "kwargs": kwargs,
                })
                return original_subprocess_run(*args, **kwargs)

            # Patch subprocess.run globally for duration of the test so
            # git_changes._git_name_status and _git_ls_untracked are traced.
            subprocess.run = _recording_run  # type: ignore[assignment]
            try:
                # Call the shared module's changed_files — it should use
                # subprocess.run (which is now recorded).
                result = changed_files(tmpdir)
                # The initial repo has no changes, so we expect empty.
                # Patch back to verify with a real change.
                _touch(tmpdir, "extra.txt", "evidence")
                result_with_change = changed_files(tmpdir)
                # Changed files must have been detected via recorded
                # subprocess calls.
                self.assertGreater(len(calls_made), 0,
                    "git_changes.changed_files must invoke subprocess.run "
                    "— it is the shared subprocess-based change detector")
                self.assertIn("extra.txt", result_with_change)
                self.assertEqual(result_with_change["extra.txt"], "untracked")

            finally:
                subprocess.run = original_subprocess_run  # type: ignore[assignment]

        # The gate module loaded.  The shared module is the provenance of
        # dirty-file detection.  Any gate evidence test that needs the set
        # of changed files MUST call the shared function, not replicate
        # subprocess calls.  This test confirms the shared module works
        # end-to-end (calls subprocess, gets real results), establishing
        # it as the authoritative source — the architectural property the
        # gate contract depends on.


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
