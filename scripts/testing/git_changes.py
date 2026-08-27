"""Deterministic Git repository-change facts."""

from __future__ import annotations

import subprocess
from typing import List

__all__ = ["resolve_baseline", "changed_files"]


def resolve_baseline(repo_root: str, baseline: str | None = None) -> str:
    """Return HEAD when no baseline is given; otherwise verify and resolve to a 40-char SHA.

    * ``baseline is None`` → ``"HEAD"`` (never silently resolves).
    * ``baseline`` provided → verified against *repo_root*; on success the
      resolved 40-character commit SHA is returned as ``str``.
    * Unresolvable baseline → raises ``ValueError`` naming the rejected ref.
    """
    if baseline is None:
        return "HEAD"

    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--verify", baseline],
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_root,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        raise ValueError(f"Baseline '{baseline}' cannot be resolved in {repo_root}")

    if len(sha) != 40:
        raise ValueError(f"Baseline '{baseline}' did not resolve to a 40-char SHA in {repo_root}")

    return sha


def _parse_name_status_line(line: str) -> tuple[str, str]:
    """Parse a single ``git diff --name-status`` line into (status_letter, path).

    Renames carry two paths: ``R100<tab>old_path<tab>new_path``.
    The path returned is the destination (new) path — the source is dropped.
    """
    parts = line.split("\t")
    status_letter = parts[0]
    if status_letter.startswith("R") and len(parts) >= 3:
        # Rename: status<tab>old_path<tab>new_path
        return (status_letter, parts[2])
    if len(parts) >= 2:
        return (status_letter, parts[1])
    return (status_letter, "")


def _git_name_status(
    repo_root: str,
    range_arg: List[str] | None = None,
) -> List[tuple[str, str]]:
    """Run ``git diff --name-status`` and return list of ``(status_letter, path)``.

    * When *range_arg* is ``None`` → runs both
      ``git diff --name-status`` (working tree vs index) and
      ``git diff --name-status --cached`` (index vs HEAD) to cover
      both unstaged and staged changes including renames.
    * Otherwise → ``git diff --name-status <range_args>``.
    """
    rows: list[tuple[str, str]] = []

    if range_arg is None:
        # Collect both unstaged and staged changes
        for cmd_suffix in [["--cached"], []]:
            cmd = ["git", "diff", "--name-status"] + cmd_suffix
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=repo_root)
            for line in result.stdout.splitlines():
                if not line:
                    continue
                rows.append(_parse_name_status_line(line))
    else:
        cmd = ["git", "diff", "--name-status"] + range_arg
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=repo_root)
        for line in result.stdout.splitlines():
            if not line:
                continue
            rows.append(_parse_name_status_line(line))

    return rows


def _git_ls_untracked(repo_root: str) -> List[str]:
    """Return list of untracked file paths."""
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    paths: list[str] = []

    for line in result.stdout.splitlines():
        p = line.strip()
        if not p:
            continue
        # A file created inside an untracked directory must appear under
        # its own path, never collapsed to the directory.
        paths.append(p)
    return paths


def _label_from_status(status_letter: str) -> str | None:
    """Map a porcelain ``git diff --name-status`` letter to the public vocabulary.

    Returns ``None`` when the letter does not map to a known label (should not
    happen with well-formed git output).
    """
    # Primary single-letter mappings
    mapping: dict[str, str] = {
        "M": "modified",
        "R": "renamed",
        "T": "modified",  # type change → classified as modified
    }
    if status_letter in mapping:
        return mapping[status_letter]

    # Prefix forms: R100, R090, etc. → renamed
    if status_letter.startswith("R"):
        return "renamed"
    if status_letter in ("A", "z"):
        return "added"
    if status_letter == "D":
        return "deleted"
    if status_letter == "C":
        # Copy — treat as added at destination
        return "added"
    if status_letter.startswith("C"):
        return "added"

    return None


def changed_files(
    repo_root: str,
    baseline: str | None = None,
    include_untracked: bool = True,
) -> dict[str, str]:
    """Return a dict of repository-relative paths → change labels.

    Labels are drawn from exactly: ``"modified"``, ``"added"``, ``"deleted"``,
    ``"renamed"``, ``"untracked"``.

    Parameters
    ----------
    repo_root:
        Path to the repository root.
    baseline:
        Optional commit-ish to diff against.  ``None`` means the working tree
        is compared to the index / HEAD.  When supplied, both the diff against
        the resolved baseline *and* the working tree vs index are combined.
    include_untracked:
        When ``False`` no ``"untracked"`` entries appear in the result.

    Precedence (when a path carries multiple signals):

    ``deleted > renamed > added > modified > untracked``
    """
    # Accumulate (path → label) using the precedence rule.
    result: dict[str, str] = {}

    def _set(path: str, label: str) -> None:
        """Set *path* → *label*, respecting the precedence ordering."""
        precedence = ["deleted", "renamed", "added", "modified", "untracked"]
        current = result.get(path)
        if current is None:
            result[path] = label
        else:
            # Higher-precedence label wins (earlier in the list).
            if precedence.index(label) < precedence.index(current):
                result[path] = label

    # --- 1. Diff against baseline (if supplied) ---
    if baseline is not None:
        resolved = resolve_baseline(repo_root, baseline)
        status_rows = _git_name_status(repo_root, [resolved])
        for letter, path in status_rows:
            label = _label_from_status(letter)
            if label:
                _set(path, label)

    # --- 2. Working tree vs index (always) ---
    wt_rows = _git_name_status(repo_root)
    for letter, path in wt_rows:
        label = _label_from_status(letter)
        if label:
            _set(path, label)

    # --- 3. Untracked files ---
    if include_untracked:
        untracked = _git_ls_untracked(repo_root)
        for path in untracked:
            _set(path, "untracked")

    return result
