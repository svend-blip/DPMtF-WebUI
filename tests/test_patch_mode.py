"""patch_and_deliverable: the worker's patch lands on a branch, never master.

§42 line 17 and the second half of line 20 -- the last unanswered lines, and
the capability LightWorker exists for: implementers that change code. The
patch is applied in a throwaway worktree at the EXACT base commit the worker
built against, committed there, and only the branch ref survives. Review and
merge stay human-gated; §16.6 keeps the push pen in Father's hand and this
keeps the merge pen in the Human's.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import pytest

from worker_results import (
    ResultRejected,
    accept_and_advance,
    apply_patch_to_branch,
    validate_result,
)


def _sha(t):
    return hashlib.sha256(t.encode()).hexdigest()


@pytest.fixture
def repo(tmp_path):
    """A real target repository with one commit, plus a worker-style patch."""
    r = tmp_path / "target"
    r.mkdir()

    def git(*a, **kw):
        return subprocess.run(["git", "-C", str(r)] + list(a),
                              capture_output=True, text=True, check=True, **kw)

    git("init", "-q")
    (r / "app.py").write_text("VERSION = 1\n", encoding="utf-8")
    git("add", "-A")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed")
    base = git("rev-parse", "HEAD").stdout.strip()

    # Byg patchen som workeren gør: ændr i et worktree, commit, diff base..HEAD
    wt = tmp_path / "wt"
    git("worktree", "add", "-q", "--detach", str(wt), base)
    (wt / "app.py").write_text("VERSION = 2\n", encoding="utf-8")
    (wt / "new_module.py").write_text("def hello():\n    return 'hi'\n",
                                      encoding="utf-8")
    subprocess.run(["git", "-C", str(wt), "add", "-A"], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", str(wt), "-c", "user.name=w",
                    "-c", "user.email=w@w", "commit", "-q", "-m", "work"],
                   check=True, capture_output=True)
    patch = subprocess.run(
        ["git", "-C", str(wt), "diff", "--binary", "--full-index",
         base, "HEAD"],
        capture_output=True, text=True, check=True).stdout
    git("worktree", "remove", "--force", str(wt))
    return str(r), base, patch


def _result(base, patch):
    return {
        "status": "role_execution_completed",
        "result_mode": "patch_and_deliverable",
        "deliverable": {"path": "x/001-result.md",
                        "content": "# report\n",
                        "sha256": _sha("# report\n")},
        "base_commit": base,
        "result_commit": "f" * 40,
        "checksum": _sha(patch),
        "patch": patch,
    }


class TestValidation:

    def test_a_wrong_checksum_is_refused(self, repo):
        _, base, patch = repo
        r = _result(base, patch)
        r["checksum"] = "0" * 64
        with pytest.raises(ResultRejected, match="checksum mismatch"):
            validate_result(r)

    def test_a_short_base_commit_is_refused(self, repo):
        _, _, patch = repo
        with pytest.raises(ResultRejected, match="40-hex"):
            validate_result(_result("abc123", patch))

    def test_pure_patch_mode_is_refused_with_the_reason(self, repo):
        _, base, patch = repo
        r = _result(base, patch)
        r["result_mode"] = "patch"
        with pytest.raises(ResultRejected, match="chains advance on deliverables"):
            validate_result(r)


class TestApplication:

    def test_the_patch_lands_on_a_branch_with_new_files_included(self, repo):
        target, base, patch = repo
        sha = apply_patch_to_branch(
            target_project=target, base_commit=base, patch=patch,
            branch="lightworker/test-001", message="applied")
        shown = subprocess.run(
            ["git", "-C", target, "show",
             "lightworker/test-001:new_module.py"],
            capture_output=True, text=True, check=True).stdout
        assert "def hello" in shown
        version = subprocess.run(
            ["git", "-C", target, "show", "lightworker/test-001:app.py"],
            capture_output=True, text=True, check=True).stdout
        assert version == "VERSION = 2\n"
        assert len(sha) == 40

    def test_master_is_untouched(self, repo):
        """The whole point: an unreviewed patch must not move any existing
        ref. Only the lightworker/ branch is new."""
        target, base, patch = repo
        head_before = subprocess.run(
            ["git", "-C", target, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
        apply_patch_to_branch(
            target_project=target, base_commit=base, patch=patch,
            branch="lightworker/test-002", message="applied")
        head_after = subprocess.run(
            ["git", "-C", target, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
        assert head_after == head_before
        status = subprocess.run(
            ["git", "-C", target, "status", "--porcelain"],
            capture_output=True, text=True, check=True).stdout
        assert status == ""

    def test_a_patch_that_does_not_apply_is_refused(self, repo):
        target, base, _ = repo
        broken = "diff --git a/app.py b/app.py\n@@ nonsense @@\n"
        with pytest.raises(ResultRejected, match="does not apply cleanly"):
            apply_patch_to_branch(
                target_project=target, base_commit=base, patch=broken,
                branch="lightworker/test-003", message="x")

    def test_no_worktree_is_left_behind_on_failure(self, repo):
        target, base, _ = repo
        try:
            apply_patch_to_branch(
                target_project=target, base_commit=base, patch="garbage",
                branch="lightworker/test-004", message="x")
        except ResultRejected:
            pass
        wt = subprocess.run(["git", "-C", target, "worktree", "list"],
                            capture_output=True, text=True, check=True).stdout
        assert "lw-apply-" not in wt


class TestAcceptAndAdvance:

    def test_the_base_commit_is_cross_checked_against_the_envelope(self, repo, tmp_path):
        """Only the envelope knows what Father dispatched. A patch echoing a
        different base built against the wrong tree, however cleanly it
        applies somewhere."""
        target, base, patch = repo
        execution = {"envelope": {
            "repository": {"base_commit": "a" * 40},
            "handoff": {"expected_deliverable": "x/001-result.md"},
            "flow_key": "lw", "handoff_id": "001", "target_role": "r",
        }}
        with pytest.raises(ResultRejected, match="is not the"):
            accept_and_advance(execution=execution,
                               result=_result(base, patch),
                               bridge_dir=str(tmp_path),
                               signal=lambda *a, **k: None)
