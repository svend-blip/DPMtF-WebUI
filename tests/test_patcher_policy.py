"""Tests for `patcher.policy` — path security (spec §14) and repo state
recording (spec §31–§32).

The fixtures in this file build tiny git repositories on disk; they
never touch the project repository itself. The `bare_repo` fixture
skips initialising an empty repo so we can test empty-repo state
recording separately.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from patcher.errors import PATCH_PATH_REJECTED
from patcher.policy import (
    PatchPathRejected,
    RepoState,
    record_repo_state,
    validate_target_path,
    validate_target_paths,
)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """A real git repo with one commit. Used by all path/state tests."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=check,
        )

    git("init", "-q")
    git("config", "user.email", "test@test")
    git("config", "user.name", "test")
    (repo / "README.md").write_text("# seed\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    return repo


@pytest.fixture()
def bare_repo(tmp_path: Path) -> Path:
    """A real but empty git repo (no commits)."""
    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(
        ["git", "-C", str(repo), "init", "-q"],
        capture_output=True, text=True, check=True,
    )
    return repo


# ── Path validation: positive cases ─────────────────────────────────────


class TestValidateTargetPathPositive:
    def test_simple_relative_path_accepted(self, git_repo: Path):
        out = validate_target_path(str(git_repo), "README.md")
        assert out == "README.md"

    def test_nested_relative_path_accepted(self, git_repo: Path):
        out = validate_target_path(str(git_repo), "src/lib/helper.py")
        assert out == "src/lib/helper.py"

    def test_absolute_path_inside_repo_accepted(self, git_repo: Path):
        absolute = str(git_repo / "README.md")
        out = validate_target_path(str(git_repo), absolute)
        assert out == "README.md"


# ── Path validation: negative cases (spec §14) ─────────────────────────


class TestValidateTargetPathNegative:
    def test_dotdot_traversal_rejected(self, git_repo: Path):
        with pytest.raises(PatchPathRejected) as ei:
            validate_target_path(str(git_repo), "../escape.py")
        assert ei.value.error_code == PATCH_PATH_REJECTED

    def test_deep_traversal_rejected(self, git_repo: Path):
        with pytest.raises(PatchPathRejected):
            validate_target_path(str(git_repo), "a/../../etc/passwd")

    def test_absolute_path_outside_repo_rejected(self, git_repo: Path):
        with pytest.raises(PatchPathRejected):
            validate_target_path(str(git_repo), "/etc/passwd")

    def test_symlink_to_outside_rejected(self, git_repo: Path, tmp_path: Path):
        outside = tmp_path / "outside_secret.txt"
        outside.write_text("secret", encoding="utf-8")
        link = git_repo / "escape_link"
        os.symlink(str(outside), str(link))
        with pytest.raises(PatchPathRejected):
            validate_target_path(str(git_repo), "escape_link")

    def test_directory_symlink_to_outside_rejected(self, git_repo: Path, tmp_path: Path):
        outside_dir = tmp_path / "external_dir"
        outside_dir.mkdir()
        (outside_dir / "secret.txt").write_text("x", encoding="utf-8")
        link_dir = git_repo / "ext"
        os.symlink(str(outside_dir), str(link_dir))
        with pytest.raises(PatchPathRejected):
            validate_target_path(str(git_repo), "ext/secret.txt")

    def test_repo_root_does_not_exist_rejected(self, tmp_path: Path):
        with pytest.raises(PatchPathRejected):
            validate_target_path(str(tmp_path / "missing"), "x.py")

    def test_repo_root_is_a_file_rejected(self, tmp_path: Path):
        not_a_dir = tmp_path / "not_a_dir"
        not_a_dir.write_text("nope", encoding="utf-8")
        with pytest.raises(PatchPathRejected):
            validate_target_path(str(not_a_dir), "x.py")

    def test_candidate_is_none_rejected(self, git_repo: Path):
        with pytest.raises(PatchPathRejected):
            validate_target_path(str(git_repo), None)  # type: ignore[arg-type]

    def test_empty_string_after_normalization_rejected(self, git_repo: Path):
        with pytest.raises(PatchPathRejected):
            validate_target_path(str(git_repo), "")

    def test_dot_only_rejected(self, git_repo: Path):
        with pytest.raises(PatchPathRejected):
            validate_target_path(str(git_repo), ".")


# ── allowed_paths enforcement ──────────────────────────────────────────


class TestAllowedPaths:
    def test_allowed_path_accepts_listed(self, git_repo: Path):
        out = validate_target_path(
            str(git_repo), "README.md", allowed_paths=["README.md"]
        )
        assert out == "README.md"

    def test_allowed_path_directory_accepts_contents(self, git_repo: Path):
        (git_repo / "src").mkdir()
        (git_repo / "src" / "a.py").write_text("x", encoding="utf-8")
        out = validate_target_path(
            str(git_repo), "src/a.py", allowed_paths=["src/"]
        )
        assert out == "src/a.py"

    def test_disallowed_path_rejected(self, git_repo: Path):
        with pytest.raises(PatchPathRejected):
            validate_target_path(
                str(git_repo), "README.md", allowed_paths=["src/"]
            )

    def test_partial_match_without_trailing_slash_still_requires_directory(
        self, git_repo: Path
    ):
        """`src` without trailing slash should NOT match `src_backup`."""
        (git_repo / "src").mkdir()
        (git_repo / "src_backup").mkdir()
        with pytest.raises(PatchPathRejected):
            validate_target_path(
                str(git_repo), "src_backup/x.py", allowed_paths=["src"]
            )


# ── Bulk validation ─────────────────────────────────────────────────────


class TestValidateTargetPaths:
    def test_validates_all_in_order(self, git_repo: Path):
        out = validate_target_paths(str(git_repo), ["README.md", "a/b.py"])
        assert out == ["README.md", "a/b.py"]

    def test_first_failure_short_circuits(self, git_repo: Path):
        with pytest.raises(PatchPathRejected):
            validate_target_paths(str(git_repo), ["README.md", "../x", "ok.py"])


# ── Repo state recording ───────────────────────────────────────────────


class TestRepoState:
    def test_clean_repo_reports_clean(self, git_repo: Path):
        state = record_repo_state(str(git_repo))
        assert state.is_clean is True
        assert state.pre_existing_changed_files == ()
        # HEAD revision should be a 40-char hex string.
        assert len(state.head_revision) == 40
        assert all(c in "0123456789abcdef" for c in state.head_revision)

    def test_dirty_file_is_recorded(self, git_repo: Path):
        (git_repo / "README.md").write_text("mutated locally\n", encoding="utf-8")
        state = record_repo_state(str(git_repo))
        assert state.is_clean is False
        assert "README.md" in state.pre_existing_changed_files

    def test_empty_repo_yields_empty_head_and_clean(self, bare_repo: Path):
        state = record_repo_state(str(bare_repo))
        assert state.head_revision == ""
        assert state.is_clean is True
        assert state.pre_existing_changed_files == ()

    def test_new_untracked_file_is_listed(self, git_repo: Path):
        (git_repo / "draft.txt").write_text("not tracked", encoding="utf-8")
        state = record_repo_state(str(git_repo))
        assert "draft.txt" in state.pre_existing_changed_files

    def test_state_is_frozen(self, git_repo: Path):
        state = record_repo_state(str(git_repo))
        with pytest.raises(Exception):
            state.head_revision = "abc"  # type: ignore[misc]
