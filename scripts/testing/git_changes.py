"""Deterministic Git repository-change facts."""

from __future__ import annotations

import subprocess
from typing import List

__all__ = ["resolve_baseline", "changed_files", "changed_ranges"]


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


def changed_ranges(
    repo_root: str,
    baseline: str | None = None,
) -> dict[str, list[tuple[int, int]]]:
    """Return changed line ranges per file from ``git diff -U0``.

    Parameters
    ----------
    repo_root:
        Path to the repository root.
    baseline:
        Optional commit-ish to diff against.  ``None`` means the working tree
        is compared to the index / HEAD.  When supplied, both the diff against
        the resolved baseline *and* the working tree vs index are combined.

    Returns
    -------
    ``dict[str, list[tuple[int, int]]]``
        Repository-relative paths → list of ``(start, end)`` tuples
        (1-based inclusive line ranges in the NEW file).  A file with no
        textual diff (added, deleted, renamed-only) maps to ``[]``.
    """
    result: dict[str, list[tuple[int, int]]] = {}

    def _collect_status(
        range_arg: List[str] | None = None,
    ) -> List[tuple[str, str]]:
        """Collect name-status rows for the given diff range."""
        rows: list[tuple[str, str]] = []
        if range_arg is None:
            for cmd_suffix in [["--cached"], []]:
                cmd = ["git", "diff", "--name-status"] + cmd_suffix
                r = subprocess.run(
                    cmd, check=True, capture_output=True, text=True,
                    cwd=repo_root,
                )
                for line in r.stdout.splitlines():
                    if not line:
                        continue
                    rows.append(_parse_name_status_line(line))
        else:
            cmd = ["git", "diff", "--name-status"] + range_arg
            r = subprocess.run(
                cmd, check=True, capture_output=True, text=True,
                cwd=repo_root,
            )
            for line in r.stdout.splitlines():
                if not line:
                    continue
                rows.append(_parse_name_status_line(line))
        return rows

    # Collect changed paths to know which files exist in result.
    all_status: List[tuple[str, str]] = []
    if baseline is not None:
        resolved = resolve_baseline(repo_root, baseline)
        all_status.extend(_collect_status([resolved]))
    all_status.extend(_collect_status(None))

    for letter, path in all_status:
        label = _label_from_status(letter)
        if label:
            if label in ("added", "renamed", "deleted"):
                result.setdefault(path, [])
            else:
                result.setdefault(path, [])  # will be filled by diff below

    # Add untracked paths (no diff → empty ranges).
    for path in _git_ls_untracked(repo_root):
        if path not in result:
            result.setdefault(path, [])

    # Parse git diff -U0 hunks.
    _hunks: dict[str, List[tuple[int, int]]] = {}

    def _parse_diff_output(diff_output: str) -> None:
        """Extract hunks from a ``git diff -U0`` output string.
        
        The hunk header gives us the exact range:
        @@ -old_start,old_count +new_start,new_count @@
        
        We use new_start and new_count directly — no line counting.
        """
        current_file = ""

        for line in diff_output.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:]
                continue
            if line.startswith("@@ "):
                parts = line.split()
                for p in parts:
                    if p.startswith("+") and not p.startswith("@@"):
                        coords = p[1:]  # strip leading '+'
                        if "," in coords:
                            new_start, new_count = coords.split(",", 1)
                        else:
                            new_start = coords
                            new_count = "1"
                        hunk_start = int(new_start)
                        hunk_end = int(new_start) + int(new_count) - 1
                        _hunks.setdefault(current_file, [])
                        _hunks[current_file].append((hunk_start, hunk_end))



    # Collect diffs to parse.
    if baseline is not None:
        resolved = resolve_baseline(repo_root, baseline)
        for suffix in [["--cached", resolved], [resolved]]:
            try:
                r = subprocess.run(
                    ["git", "diff", "-U0"] + suffix,
                    check=True, capture_output=True, text=True,
                    cwd=repo_root,
                )
                _parse_diff_output(r.stdout)
            except subprocess.CalledProcessError:
                continue

    for suffix in [["--cached"], []]:
        try:
            r = subprocess.run(
                ["git", "diff", "-U0"] + suffix,
                check=True, capture_output=True, text=True,
                cwd=repo_root,
            )
            _parse_diff_output(r.stdout)
        except subprocess.CalledProcessError:
            continue

    # Merge hunks per file.
    for f, hunks in _hunks.items():
        hunks.sort()
        collapsed: list[tuple[int, int]] = [hunks[0]]
        for s, e in hunks[1:]:
            last_s, last_e = collapsed[-1]
            if s <= last_e + 1:
                collapsed[-1] = (last_s, max(last_e, e))
            else:
                collapsed.append((s, e))
        result[f] = collapsed

    return result
