"""Tests for `patcher.engines.GitDiffEngine` and the public facade's
dispatch to it.

These tests build tiny git repositories in tmp_path. They never touch
the project repository itself.

Coverage:

  * Valid unified diff applies and the resulting diff is captured.
  * Invalid diff and a failed `git apply --check` each change NOTHING
    on disk (tree byte-identical before/after).
  * Path traversal / absolute external / symlink escape / allowed_paths
    violation are each rejected with PATCH_PATH_REJECTED and no write.
  * `check()` writes nothing.
  * Pre-existing dirty file is recorded and never overwritten
    (PATCH_CONFLICT).
  * `base_revision` mismatch returns PATCH_BASE_MISMATCH with no write.
  * `structural_python` mode returns PATCH_UNSUPPORTED_OPERATION.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Tuple

import pytest

from patcher import DeterministicPatcher, PatchRequest
from patcher.errors import (
    PATCH_APPLIED,
    PATCH_BASE_MISMATCH,
    PATCH_CONFLICT,
    PATCH_INVALID,
    PATCH_PATH_REJECTED,
    PATCH_UNSUPPORTED_OPERATION,
)
from patcher.engines import GitDiffEngine, PatchEngine


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture()
def git_repo(tmp_path: Path) -> Tuple[str, str]:
    """Return (repo_path, base_revision) for a tiny seeded repo."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, check=check,
        )

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    (repo / "lib.py").write_text("VERSION = 1\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    base = git("rev-parse", "HEAD").stdout.strip()
    return str(repo), base


def _diff_for(repo_path: str, filename: str, old: str, new: str) -> str:
    """Build a unified diff for `filename` from old to new without relying
    on the test process running `git diff`. We synthesize the diff text
    directly so the test does not depend on `git config` user values.
    """
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)

    def _hunk(old_lines, new_lines):
        return (
            "@@ -1 +1 @@\n"
            + "".join(f"-{l}" for l in old_lines)
            + "".join(f"+{l}" for l in new_lines)
        )

    return (
        f"diff --git a/{filename} b/{filename}\n"
        "index 0000000..0000000 100644\n"
        f"--- a/{filename}\n"
        f"+++ b/{filename}\n"
        + _hunk(old_lines, new_lines)
    )


def _tree_sha(repo_path: str) -> str:
    """Hash every file's contents into a stable tree fingerprint.

    Used to verify byte-identity before/after a call. We deliberately
    avoid `git write-tree` because that requires a clean index.
    """
    out = []
    for root, _dirs, files in os.walk(repo_path):
        if ".git" in root.split(os.sep):
            continue
        for fn in sorted(files):
            p = Path(root) / fn
            rel = p.relative_to(repo_path).as_posix()
            with open(p, "rb") as f:
                data = f.read()
            out.append(f"{rel}={data!r}")
    return "|".join(out)


# ── PatchEngine contract ────────────────────────────────────────────────


class TestPatchEngineBase:
    def test_base_engine_methods_raise_not_implemented(self):
        class _StubEngine(PatchEngine):
            pass

        stub = _StubEngine()
        req = PatchRequest(repo_path="/x", patch_mode="unified_diff", patch="x")
        with pytest.raises(NotImplementedError):
            stub.check(req)
        with pytest.raises(NotImplementedError):
            stub.apply(req)


# ── Apply: happy path ──────────────────────────────────────────────────


class TestApplyValid:
    def test_valid_diff_applies_and_captures_resulting_diff(self, git_repo):
        repo, _ = git_repo
        patcher = DeterministicPatcher()
        diff = _diff_for(repo, "lib.py", "VERSION = 1\n", "VERSION = 2\n")
        req = PatchRequest(repo_path=repo, patch_mode="unified_diff", patch=diff)

        result = patcher.apply(req)

        assert result.applied is True
        assert result.status == "applied"
        assert result.engine == "git_apply"
        assert result.error_code == PATCH_APPLIED
        assert result.error is None
        assert result.files_changed == ["lib.py"]
        assert result.operations_requested == 1
        assert result.operations_applied == 1
        assert result.resulting_diff is not None
        assert "diff --git a/lib.py" in result.resulting_diff
        assert "VERSION = 2" in result.resulting_diff

        # The file really did change on disk.
        assert (Path(repo) / "lib.py").read_text(encoding="utf-8") == "VERSION = 2\n"

    def test_multi_file_diff_is_tracked(self, git_repo):
        repo, _ = git_repo
        patcher = DeterministicPatcher()
        diff_a = _diff_for(repo, "README.md", "hello\n", "world\n")
        diff_b = _diff_for(repo, "lib.py", "VERSION = 1\n", "VERSION = 2\n")
        combined = diff_a + "\n" + diff_b

        result = patcher.apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=combined,
        ))
        assert result.applied is True
        assert set(result.files_changed) == {"README.md", "lib.py"}


# ── Apply: failures leave the tree untouched ───────────────────────────


class TestApplyFailuresLeaveTreeUntouched:
    def test_invalid_diff_changes_nothing(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        patcher = DeterministicPatcher()
        req = PatchRequest(
            repo_path=repo,
            patch_mode="unified_diff",
            patch="this is not a diff\n@@ nope @@\n",
        )
        result = patcher.apply(req)
        assert result.applied is False
        assert result.error_code == PATCH_CONFLICT
        assert _tree_sha(repo) == before

    def test_diff_targeting_wrong_line_changes_nothing(self, git_repo):
        """A syntactically-valid diff whose hunk targets a non-existent
        line must be refused by `git apply --check` and leave the tree
        untouched.
        """
        repo, _ = git_repo
        before = _tree_sha(repo)
        # lib.py starts with `VERSION = 1\n` — replace a line that does
        # not exist.
        broken = (
            "diff --git a/lib.py b/lib.py\n"
            "@@ -10,3 +10,3 @@\n"
            "-nope1\n-nope2\n-nope3\n"
            "+new1\n+new2\n+new3\n"
        )
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=broken,
        ))
        assert result.applied is False
        assert result.error_code == PATCH_CONFLICT
        assert _tree_sha(repo) == before

    def test_check_failure_changes_nothing(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        broken = (
            "diff --git a/lib.py b/lib.py\n"
            "@@ -10,3 +10,3 @@\n"
            "-nope\n-nope2\n-nope3\n"
            "+new\n+new2\n+new3\n"
        )
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=broken,
        ))
        assert result.applied is False
        assert result.error_code == PATCH_CONFLICT
        assert _tree_sha(repo) == before

    def test_path_traversal_in_diff_is_rejected_no_write(self, git_repo, tmp_path):
        repo, _ = git_repo
        before = _tree_sha(repo)
        # Build a diff that *would* create ../escape.py if the engine
        # were sloppy. `git apply` itself rejects ".." in paths, but the
        # engine's path validation must reject it FIRST.
        evil = (
            "diff --git a/../escape.py b/../escape.py\n"
            "@@ -0,0 +1 @@\n"
            "+evil\n"
        )
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=evil,
        ))
        assert result.applied is False
        assert result.error_code == PATCH_PATH_REJECTED
        assert _tree_sha(repo) == before

    def test_absolute_external_path_in_diff_rejected(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        evil = (
            "diff --git a//etc/passwd b//etc/passwd\n"
            "@@ -1 +1 @@\n"
            "-x\n"
            "+y\n"
        )
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=evil,
        ))
        assert result.applied is False
        assert result.error_code == PATCH_PATH_REJECTED
        assert _tree_sha(repo) == before

    def test_symlink_escape_via_diff_rejected(self, git_repo, tmp_path):
        repo, _ = git_repo
        outside = tmp_path / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        link = Path(repo) / "link"
        os.symlink(str(outside), str(link))
        before = _tree_sha(repo)
        evil = (
            "diff --git a/link b/link\n"
            "@@ -1 +1 @@\n"
            "-secret\n"
            "+different\n"
        )
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=evil,
        ))
        assert result.applied is False
        assert result.error_code == PATCH_PATH_REJECTED
        assert _tree_sha(repo) == before

    def test_allowed_paths_violation_rejected(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        diff = _diff_for(repo, "README.md", "hello\n", "world\n")
        req = PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=diff,
            allowed_paths=["lib.py"],
        )
        result = DeterministicPatcher().apply(req)
        assert result.applied is False
        assert result.error_code == PATCH_PATH_REJECTED
        assert _tree_sha(repo) == before


# ── check() never writes ────────────────────────────────────────────────


class TestCheckWritesNothing:
    def test_check_does_not_mutate_tree(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        diff = _diff_for(repo, "lib.py", "VERSION = 1\n", "VERSION = 2\n")
        result = DeterministicPatcher().check(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=diff,
        ))
        assert result.applied is False
        assert result.status == "check_passed"
        assert _tree_sha(repo) == before

    def test_check_reports_failure_on_bad_diff(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        result = DeterministicPatcher().check(PatchRequest(
            repo_path=repo, patch_mode="unified_diff",
            patch="not a diff at all\n",
        ))
        assert result.applied is False
        assert result.error_code == PATCH_CONFLICT
        assert result.status == "rejected"
        assert _tree_sha(repo) == before

    def test_check_rejects_path_traversal(self, git_repo):
        repo, _ = git_repo
        evil = (
            "diff --git a/../escape.py b/../escape.py\n"
            "@@ -0,0 +1 @@\n"
            "+x\n"
        )
        result = DeterministicPatcher().check(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=evil,
        ))
        assert result.error_code == PATCH_PATH_REJECTED


# ── Pre-existing dirty tree handling ──────────────────────────────────


class TestPreExistingDirtyTree:
    def test_unsafe_overwrite_of_dirty_file_returns_conflict(
        self, git_repo
    ):
        repo, _ = git_repo
        # Pre-existing modification to lib.py.
        (Path(repo) / "lib.py").write_text("local edit\n", encoding="utf-8")

        # Build a diff that would overwrite lib.py.
        diff = _diff_for(repo, "lib.py", "VERSION = 1\n", "VERSION = 2\n")
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=diff,
        ))
        # Either PATCH_CONFLICT (the diff's own context disagrees with
        # the on-disk content) or PATCH_BASE_MISMATCH is acceptable per
        # spec §32. We assert the rejection happens and no write
        # occurred.
        assert result.applied is False
        assert result.error_code in (PATCH_CONFLICT, "PATCH_BASE_MISMATCH")
        assert (Path(repo) / "lib.py").read_text(encoding="utf-8") == "local edit\n"

    def test_safe_application_to_unrelated_file_succeeds_with_dirty_tree(
        self, git_repo
    ):
        repo, _ = git_repo
        # Pre-existing modification that does NOT intersect the patch.
        (Path(repo) / "README.md").write_text("dirty local edit\n", encoding="utf-8")
        diff = _diff_for(repo, "lib.py", "VERSION = 1\n", "VERSION = 2\n")
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=diff,
        ))
        assert result.applied is True
        # The dirty file was preserved.
        assert (Path(repo) / "README.md").read_text(encoding="utf-8") == "dirty local edit\n"
        # The patched file moved.
        assert (Path(repo) / "lib.py").read_text(encoding="utf-8") == "VERSION = 2\n"


# ── base_revision handling ─────────────────────────────────────────────


class TestBaseRevision:
    def test_matching_base_revision_succeeds(self, git_repo):
        repo, base = git_repo
        diff = _diff_for(repo, "lib.py", "VERSION = 1\n", "VERSION = 2\n")
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=diff,
            base_revision=base,
        ))
        assert result.applied is True
        assert result.error_code == PATCH_APPLIED

    def test_mismatched_base_revision_returns_base_mismatch(self, git_repo):
        repo, _ = git_repo
        diff = _diff_for(repo, "lib.py", "VERSION = 1\n", "VERSION = 2\n")
        bogus = "f" * 40
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=diff,
            base_revision=bogus,
        ))
        assert result.applied is False
        assert result.error_code == PATCH_BASE_MISMATCH
        # No write occurred.
        assert (Path(repo) / "lib.py").read_text(encoding="utf-8") == "VERSION = 1\n"

    def test_malformed_base_revision_rejected_at_facade(self, git_repo):
        repo, _ = git_repo
        diff = _diff_for(repo, "lib.py", "VERSION = 1\n", "VERSION = 2\n")
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=diff,
            base_revision="not-a-hash",
        ))
        assert result.applied is False
        assert result.error_code == PATCH_INVALID


# ── structural_python mode dispatch ───────────────────────────────────
# Phase 1B: structural_python is dispatched to LibCSTEngine. The
# facade no longer returns PATCH_UNSUPPORTED_OPERATION for this mode;
# the engine handles it. Unknown operation NAMES (e.g. replace_method)
# still return PATCH_UNSUPPORTED_OPERATION at the engine layer — see
# tests/test_patcher_cst_engine.py for the engine-level coverage.


class TestStructuralPythonDispatch:
    def test_structural_python_check_dispatches_to_libcst(self, git_repo):
        repo, _ = git_repo
        result = DeterministicPatcher().check(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_import",
                "file": "lib.py",
                "module": "os",
            }],
        ))
        assert result.applied is False
        assert result.engine == "libcst"
        assert result.error_code == PATCH_APPLIED
        assert result.status == "check_passed"

    def test_structural_python_apply_dispatches_to_libcst(self, git_repo):
        repo, _ = git_repo
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_import",
                "file": "lib.py",
                "module": "os",
            }],
        ))
        assert result.applied is True
        assert result.engine == "libcst"
        assert result.error_code == PATCH_APPLIED
        assert result.status == "applied"
        assert result.files_changed == ["lib.py"]
        # The import actually landed in the file.
        assert "import os" in (Path(repo) / "lib.py").read_text(encoding="utf-8")

    def test_unknown_mode_returns_unsupported(self, git_repo):
        repo, _ = git_repo
        result = DeterministicPatcher().check(PatchRequest(
            repo_path=repo, patch_mode="quantum_diff",
            patch="x",
        ))
        assert result.error_code == PATCH_UNSUPPORTED_OPERATION


# ── Schema-level rejections from the facade ────────────────────────────


class TestFacadeSchemaValidation:
    def test_missing_repo_path(self, git_repo):
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path="", patch_mode="unified_diff", patch="x",
        ))
        assert result.error_code == PATCH_INVALID

    def test_empty_patch_body(self, git_repo):
        repo, _ = git_repo
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch="",
        ))
        assert result.error_code == PATCH_INVALID

    def test_unified_diff_with_operations_rejected(self, git_repo):
        repo, _ = git_repo
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch="x",
            operations=[{"operation": "add_import"}],
        ))
        assert result.error_code == PATCH_INVALID

    def test_structural_python_without_operations_rejected(self, git_repo):
        repo, _ = git_repo
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
        ))
        assert result.error_code == PATCH_INVALID

    def test_engine_directly_rejects_wrong_mode(self, git_repo):
        repo, _ = git_repo
        engine = GitDiffEngine()
        req = PatchRequest(repo_path=repo, patch_mode="structural_python",
                           operations=[{"operation": "add_import"}])
        result = engine.check(req)
        assert result.error_code == PATCH_INVALID
