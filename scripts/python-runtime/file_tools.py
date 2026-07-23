"""File tools — safe path resolution and file operations.

The runtime's security boundary: all file access goes through safe_resolve,
which rejects absolute paths, .. traversal, and symlink escapes.
"""
from __future__ import annotations

import os
from pathlib import Path

MAX_FILE_BYTES = 200_000


def safe_resolve(project_root: str, rel_path: str) -> Path:
    """Resolve a relative path against project_root, rejecting escapes.

    Rejects:
    - Absolute paths
    - .. traversal
    - Symlink components that escape project root
    """
    if os.path.isabs(rel_path):
        raise ValueError(f"absolute paths not allowed: {rel_path}")
    root = Path(project_root).resolve()
    if ".." in Path(rel_path).parts:
        raise ValueError(f"'..' not allowed: {rel_path}")
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(f"path escapes project root: {rel_path}")
    # Check each path component for symlinks
    p = root
    for part in Path(rel_path).parts:
        p = p / part
        if p.is_symlink():
            raise ValueError(f"symlink component not allowed: {rel_path}")
    return target


def read_file(project_root: str, rel_path: str) -> str:
    """Read a file safely. Returns content or raises."""
    target = safe_resolve(project_root, rel_path)
    if not target.is_file():
        raise FileNotFoundError(f"file not found: {rel_path}")
    if target.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"file too large: {rel_path}")
    return target.read_text()


def apply_patch(project_root: str, rel_path: str, content: str) -> int:
    """Write a file safely. Returns bytes written."""
    target = safe_resolve(project_root, rel_path)
    if len(content.encode()) > MAX_FILE_BYTES:
        raise ValueError(f"content too large for {rel_path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return len(content)


def list_changed_files(project_root: str) -> list[str]:
    """List files changed via git diff."""
    import subprocess
    result = subprocess.run(
        ["git", "-C", project_root, "diff", "--name-only"],
        capture_output=True, text=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f] if result.stdout.strip() else []
