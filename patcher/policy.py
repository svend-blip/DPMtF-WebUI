"""Path security and repository state helpers for the Deterministic Patcher.

This module implements the two responsibilities that the engines and the
service layer rely on before any mutation can occur:

  1. Path validation against the selected `repo_path` (spec §14): reject
     `../` traversal, absolute paths outside the repo, symlink escape
     and unexpected repository roots BEFORE any write. When
     `allowed_paths` is configured, paths outside it are also rejected.
  2. Repository state recording (spec §31–§32): capture HEAD revision,
     the dirty/clean flag, and the list of files changed BEFORE the
     patch runs, so the engine can distinguish patch-caused changes
     from pre-existing ones.

The functions here have no side effects on disk other than the read-only
git invocations needed to record state. They never write to the repo.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, List, Optional, Sequence, Tuple

from patcher.errors import PATCH_PATH_REJECTED


# ── Exceptions ──────────────────────────────────────────────────────────


class PatchPathRejected(ValueError):
    """Raised when a candidate path fails path-security validation.

    Carries the stable machine-readable error code so callers can wrap
    it directly into a PatchResult.error_code field.

    The optional `offending_path` attribute carries the repo-relative
    POSIX path the validator refused to touch, when one is meaningful
    (`../` traversal, symlink escape at a known prefix or terminal,
    `allowed_paths` violation). Where the validator rejected the
    repository root itself (rather than an in-repo file), or where the
    candidate was `None`, `offending_path` is `None` — the error
    message still names the problematic input, but no repo-relative
    file path is meaningful.

    Engine catch sites read `exc.offending_path` and populate
    `PatchResult.files_rejected` with it so the review side can SEE
    which file was rejected, not only read about it in the error
    string.
    """

    def __init__(
        self,
        message: str,
        *,
        offending_path: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.error_code: str = PATCH_PATH_REJECTED
        self.offending_path: Optional[str] = offending_path


# ── Repository state ────────────────────────────────────────────────────


@dataclass(frozen=True)
class RepoState:
    """Snapshot of the repository BEFORE a patch attempt.

    - head_revision: the full 40-char commit hash at HEAD, or "" for an
      empty repository with no commits yet.
    - is_clean: True iff `git status --porcelain` produced no output
      (note: untracked files inside the repo are NOT considered dirty
      unless they would be touched by the patch; we follow the same
      policy as `git apply --check` and treat an empty `git status
      --porcelain` output as clean).
    - pre_existing_changed_files: the file paths listed by `git status
      --porcelain` at record time. The engine uses this set to detect
      when a patch would overwrite a pre-existing modification and
      raise PATCH_CONFLICT / PATCH_BASE_MISMATCH.
    """

    head_revision: str
    is_clean: bool
    pre_existing_changed_files: Tuple[str, ...]


# ── Path validation ─────────────────────────────────────────────────────


def _normalize_repo_root(repo_path: str) -> Path:
    """Return the canonical realpath of `repo_path` (no symlink resolution
    beyond what realpath itself does).

    Raises PatchPathRejected if the path does not exist or is not a
    directory.
    """
    try:
        rp = Path(repo_path).resolve(strict=True)
    except (FileNotFoundError, RuntimeError) as exc:
        raise PatchPathRejected(
            f"Repository root does not exist or is not resolvable: {repo_path}"
        ) from exc
    if not rp.is_dir():
        raise PatchPathRejected(
            f"Repository root is not a directory: {repo_path}"
        )
    return rp


def _normalize_under_root(repo_root: Path, candidate: str) -> PurePosixPath:
    """Resolve `candidate` relative to `repo_root`, returning a POSIX-style
    relative path. The result is purely lexical at this point — symlink
    resolution against the filesystem happens separately so we can report
    a useful error for symlink escapes.
    """
    # os.path.normpath collapses `.` and `..` lexically, but does not
    # touch the filesystem. Strip a leading "./" so the result is clean.
    raw = candidate.replace("\\", "/")
    if os.path.isabs(raw):
        joined = Path(os.path.normpath(raw))
    else:
        joined = Path(os.path.normpath(raw))
    # If absolute, refuse here — callers must not bypass the repo via an
    # absolute candidate at all, but be defensive anyway.
    if joined.is_absolute():
        # Re-anchor: if the absolute path is under repo_root, keep the
        # part below it. Otherwise reject.
        try:
            rel = joined.relative_to(repo_root)
        except ValueError as exc:
            raise PatchPathRejected(
                f"Absolute path is outside repository: {candidate!r}"
            ) from exc
        return PurePosixPath(rel.as_posix())

    # Relative candidate. Anchor it under repo_root and verify it stays
    # there after normalization.
    anchored = (repo_root / joined).resolve(strict=False)
    try:
        rel = anchored.relative_to(repo_root)
    except ValueError as exc:
        # The normalized relative path walked above the repo root — i.e.
        # `../` traversal.
        raise PatchPathRejected(
            f"Path escapes repository via '..': {candidate!r}",
            offending_path=candidate,
        ) from exc
    return PurePosixPath(rel.as_posix())


def _check_symlink_escape(repo_root: Path, candidate: str) -> None:
    """Walk the candidate's ancestors and refuse any symlink that points
    outside the repository root.

    We split the candidate into segments and check each parent directory
    that exists on disk. If any of those parents is a symlink whose
    resolved target leaves repo_root, we reject.
    """
    # Resolve every existing prefix of the candidate and confirm it stays
    # under repo_root. This catches both "the candidate itself is a
    # symlink to outside" and "an intermediate dir is a symlink to
    # outside".
    parts = PurePosixPath(candidate).parts
    for i in range(1, len(parts)):
        partial = repo_root.joinpath(*parts[:i])
        if not partial.exists():
            # A missing intermediate component is fine — the patcher will
            # create it. We only flag symlink escapes for paths that
            # ALREADY exist.
            continue
        if partial.is_symlink():
            real = partial.resolve(strict=False)
            try:
                real.relative_to(repo_root)
            except ValueError as exc:
                raise PatchPathRejected(
                    f"Symlink escape: {partial.as_posix()} -> {real}",
                    offending_path=partial.as_posix(),
                ) from exc

    # Finally check the candidate itself if it already exists.
    full = repo_root.joinpath(candidate)
    if full.exists() and full.is_symlink():
        real = full.resolve(strict=False)
        try:
            real.relative_to(repo_root)
        except ValueError as exc:
            raise PatchPathRejected(
                f"Symlink escape: {candidate} -> {real}",
                offending_path=candidate,
            ) from exc


def _check_allowed(
    candidate_posix: PurePosixPath, allowed_paths: Sequence[str]
) -> None:
    """Refuse the candidate if it does not match any allowed_paths entry.

    `allowed_paths` entries are repo-relative POSIX-style prefixes
    ("app/", "tests"). A trailing slash distinguishes "directory only"
    from "any path with this prefix"; we treat every entry as a prefix
    match by normalizing the entry to end with "/" if it does not already.
    """
    candidate = candidate_posix.as_posix()
    for entry in allowed_paths:
        if not entry:
            continue
        normalized = entry.replace("\\", "/").rstrip("/") + "/"
        if candidate.startswith(normalized) or candidate + "/" == normalized:
            return
    raise PatchPathRejected(
        f"Path is not in allowed_paths: {candidate!r}",
        offending_path=candidate,
    )


def validate_target_path(
    repo_path: str,
    candidate: str,
    allowed_paths: Optional[Sequence[str]] = None,
) -> str:
    """Validate `candidate` against the security rules of spec §14.

    Returns the validated repo-relative POSIX path on success. Raises
    `PatchPathRejected` (carrying `error_code=PATCH_PATH_REJECTED`) on
    any of:

      * repository root does not exist
      * absolute candidate outside the repo
      * `../` traversal that escapes the repo
      * symlink (intermediate or terminal) pointing outside the repo
      * allowed_paths violation when allowed_paths is non-empty

    The function performs NO writes. It is safe to call repeatedly and
    is the gate that the engines call BEFORE invoking `git apply`.
    """
    if candidate is None:
        raise PatchPathRejected("Candidate path is None")

    repo_root = _normalize_repo_root(repo_path)
    rel = _normalize_under_root(repo_root, candidate)

    # Empty string after normalization is "the repo root itself" — there
    # is no file at the root to mutate, so reject.
    if rel.as_posix() in ("", "."):
        raise PatchPathRejected(
            "Candidate path resolves to the repository root, not a file"
        )

    _check_symlink_escape(repo_root, rel.as_posix())

    if allowed_paths:
        _check_allowed(rel, allowed_paths)

    return rel.as_posix()


def validate_target_paths(
    repo_path: str,
    candidates: Iterable[str],
    allowed_paths: Optional[Sequence[str]] = None,
) -> List[str]:
    """Apply `validate_target_path` to every candidate, returning the list
    of validated paths in input order. Raises PatchPathRejected at the
    first failure — atomicity for the validation step.
    """
    out: List[str] = []
    for c in candidates:
        out.append(validate_target_path(repo_path, c, allowed_paths))
    return out


# ── Repository state recording ──────────────────────────────────────────


def _run_git(repo_path: str, *args: str) -> str:
    """Run `git <args>` inside repo_path and return stdout.

    Raises subprocess.CalledProcessError on non-zero exit so the caller
    can decide whether the error is meaningful. We do not swallow git
    failures: silent failures are an auto-fail pattern.
    """
    proc = subprocess.run(
        ["git", "-C", repo_path, *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


def record_repo_state(repo_path: str) -> RepoState:
    """Snapshot the repository BEFORE a patch attempt (spec §31–§32).

    Records:

      * HEAD revision (full 40-char hash; "" for an empty repo).
      * dirty/clean flag, derived from `git status --porcelain`.
      * the list of files reported by `git status --porcelain` so the
        engine can refuse to silently overwrite pre-existing work.

    The function never raises for an empty repository: an unborn HEAD
    yields head_revision="" and is_clean=True.
    """
    # ── HEAD revision ──────────────────────────────────────────────────
    head = ""
    try:
        head = _run_git(repo_path, "rev-parse", "HEAD").strip()
    except subprocess.CalledProcessError:
        # Empty repo (no commits yet) — leave head as "" and treat the
        # repo as clean. We do NOT reject: per spec §32 we must not
        # auto-reject dirty trees, and an unborn HEAD is a special case
        # of that — the patcher is allowed to apply a patch that
        # creates the very first commit content.
        pass

    # ── git status --porcelain ──────────────────────────────────────────
    try:
        porcelain = _run_git(repo_path, "status", "--porcelain")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Failed to record repository state: git status failed in {repo_path}"
        ) from exc

    changed: List[str] = []
    for line in porcelain.splitlines():
        # Format: "XY path" — the first two columns are status flags,
        # the rest (after a single space) is the path. For renames the
        # path field is "old -> new"; we keep "new" because that is the
        # file that will end up changed post-patch.
        if not line.strip():
            continue
        # The path begins at column 3 (after the two status chars and a
        # space), but we split on the first space to be defensive.
        path_field = line[3:] if len(line) >= 4 else ""
        if " -> " in path_field:
            path_field = path_field.split(" -> ", 1)[1]
        # Strip surrounding quotes git adds for paths with special chars.
        path_field = path_field.strip().strip('"')
        if path_field:
            changed.append(path_field)

    return RepoState(
        head_revision=head,
        is_clean=(len(changed) == 0),
        pre_existing_changed_files=tuple(changed),
    )
