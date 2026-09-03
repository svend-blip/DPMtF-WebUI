"""Deterministic evidence builder for the test-impact subsystem.

Builds a machine-readable evidence record from git metadata, a test plan,
and execution results. Used by the evidence-gathering step (Run 005) in the
1000 flow.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

__all__ = [
    "build_evidence",
    "write_evidence",
    "is_stale",
    "EVIDENCE_SCHEMA_VERSION",
    "EvidenceError",
]

EVIDENCE_SCHEMA_VERSION: str = "1"

REQUIRED_KEYS: List[str] = sorted([
    "affected_components",
    "baseline",
    "changed_files",
    "changed_symbols",
    "duration_seconds",
    "escalation_reason",
    "generated_at",
    "head_sha",
    "is_exhaustive",
    "lifecycle_point",
    "plan_hash",
    "policy_hash",
    "repository",
    "requested_scope",
    "resolved_scope",
    "schema_version",
    "selected_tests",
    "status",
    "test_command",
    "worktree_fingerprint",
    "baseline_tree_state",
    "baseline_resolution",
])


class EvidenceError(Exception):
    """Raised when an evidence record is missing required keys or has wrong types."""


# ── Type validation ───────────────────────────────────────────────────────


_TYPE_MAP: Dict[str, type] = {
    "affected_components": list,
    "baseline": str,
    "baseline_resolution": (str, type(None)),
    "baseline_tree_state": (str, type(None)),
    "changed_files": list,
    "changed_symbols": list,
    "duration_seconds": (int, float),
    "escalation_reason": str,
    "generated_at": str,
    "head_sha": str,
    "is_exhaustive": bool,
    "lifecycle_point": str,
    "plan_hash": str,
    "policy_hash": str,
    "repository": str,
    "requested_scope": (str, type(None)),
    "resolved_scope": str,
    "schema_version": str,
    "selected_tests": list,
    "status": str,
    "test_command": list,
    "worktree_fingerprint": str,
}


# Documented additive fields (Run 014): present only when the runner adds
# them, never part of the 22-key core schema, and nothing downstream may
# require them.
_ADDITIVE_KEYS: Dict[str, type] = {
    "parallel_executed": bool,
    "parallel_workers": int,
    "stdout_tail": str,
    "stderr_tail": str,
}


def _validate_evidence(record: Dict[str, Any]) -> None:
    """Validate that a record contains all required keys with correct types.

    The 22-key core schema is exact; Run 014's documented additive keys
    are permitted on top, and any other extra key is still an error.

    Raises EvidenceError if validation fails.
    """
    core_count = sum(1 for k in record if k not in _ADDITIVE_KEYS)
    if core_count != 22:
        raise EvidenceError(
            f"Evidence must have exactly 22 keys (excluding additive), got {core_count}"
        )
    for key, expected_type in _ADDITIVE_KEYS.items():
        if key in record and not isinstance(record[key], expected_type):
            raise EvidenceError(
                f"Additive key '{key}' must be {expected_type.__name__}"
            )

    for key in REQUIRED_KEYS:
        if key not in record:
            raise EvidenceError(f"Missing required key: {key}")

    for key, expected_type in _TYPE_MAP.items():
        if key not in record:
            continue
        value = record[key]
        if not isinstance(value, expected_type):
            # Special handling: bool is subclass of int, so check bool first
            if expected_type == (int, float) and isinstance(value, bool):
                raise EvidenceError(
                    f"Key '{key}' must be numeric, got bool"
                )
            else:
                raise EvidenceError(
                    f"Key '{key}' has wrong type: "
                    f"expected {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )


# ── Git helpers ───────────────────────────────────────────────────────────


def _git_rev_parse_head(repo_root: str) -> str:
    """Resolve HEAD SHA, or return 'HEAD' if unavailable."""
    proc = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    return "HEAD"


def _git_repo_url(repo_root: str) -> str:
    """Return remote URL or best-effort repo name."""
    try:
        proc = subprocess.run(
            ["git", "-C", repo_root, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except (OSError, FileNotFoundError):
        pass
    return os.path.basename(os.path.abspath(repo_root))


def _git_diff_name_status(repo_root: str) -> List[str]:
    """Return sorted list of file paths from `git diff --name-status`."""
    try:
        proc = subprocess.run(
            ["git", "-C", repo_root, "diff", "--name-status"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return []
        result: List[str] = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                result.append(parts[1])
            elif len(parts) == 1:
                result.append(parts[0])
        return sorted(result)
    except (OSError, FileNotFoundError):
        return []


def _compute_worktree_fingerprint(repo_root: str) -> str:
    """Compute a 64-char SHA-256 hex fingerprint of the working tree.

    Parses `git diff --name-status`, builds sorted [status, path] pairs,
    converts to canonical string, and SHA-256 hashes it.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", repo_root, "diff", "--name-status"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            # If we cannot read diff, fingerprint the empty string
            pairs: List[List[str]] = []
        else:
            pairs = []
            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    pairs.append(parts)
                elif len(parts) == 1:
                    pairs.append([parts[0], ""])
        pairs.sort()
        canonical = "\n".join(f"{s}\t{p}" for s, p in pairs)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    except (OSError, FileNotFoundError):
        return hashlib.sha256(b"").hexdigest()


# ── Public API ────────────────────────────────────────────────────────────


def build_evidence(
    repo_root: str,
    plan: Any,
    test_command: Sequence[str],
    status: str,
    duration_seconds: float,
    lifecycle_point: str = "work_unit",
    baseline_tree_state: str | None = None,
    baseline_resolution: str | None = None,
    stdout_tail: str = "",
    stderr_tail: str = "",
) -> Dict[str, Any]:
    """Build a fully populated evidence dict from a test plan and result.

    Args:
        repo_root: path to the repository root.
        plan: a TestPlan object from planner.plan_tests().
        test_command: the test command to record.
        status: one of "PASS", "FAIL", "ERROR".
        duration_seconds: execution duration.
        lifecycle_point: one of "work_unit", "run_baseline", "explicit_gate".
        baseline_tree_state: "clean", "dirty", or None for unknown.
        baseline_resolution: "resolved", "unresolved", or None if N/A.
        stdout_tail: last 40 lines of test stdout (additive field).
        stderr_tail: last 40 lines of test stderr (additive field).

    Returns:
        A dict with all 22 required keys.

    Raises:
        EvidenceError: if any required key is missing or wrong type.
    """
    head_sha = _git_rev_parse_head(repo_root)
    repository = _git_repo_url(repo_root)
    changed_files = _git_diff_name_status(repo_root)
    changed_symbols: List[str] = []  # populated after Run 007
    worktree_fingerprint = _compute_worktree_fingerprint(repo_root)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    record: Dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "repository": repository,
        "baseline": "HEAD",
        "head_sha": head_sha,
        "worktree_fingerprint": worktree_fingerprint,
        "changed_files": changed_files,
        "changed_symbols": changed_symbols,
        "affected_components": list(getattr(plan, "affected_components", [])),
        "requested_scope": getattr(plan, "requested_scope", None),
        "resolved_scope": getattr(plan, "resolved_scope", ""),
        "escalation_reason": getattr(plan, "escalation_reason", ""),
        "selected_tests": list(getattr(plan, "selected_tests", [])),
        "is_exhaustive": bool(getattr(plan, "is_exhaustive", False)),
        "policy_hash": str(getattr(plan, "policy_hash", "")),
        "plan_hash": str(getattr(plan, "plan_hash", "")),
        "test_command": list(test_command),
        "status": status,
        "duration_seconds": float(duration_seconds),
        "lifecycle_point": lifecycle_point,
        "baseline_tree_state": baseline_tree_state,
        "baseline_resolution": baseline_resolution,
    }
    if stdout_tail:
        record["stdout_tail"] = stdout_tail
    if stderr_tail:
        record["stderr_tail"] = stderr_tail

    _validate_evidence(record)
    return record


def write_evidence(evidence: Dict[str, Any], path: str) -> None:
    """Write the evidence dict to `path` as formatted JSON.

    Args:
        evidence: the evidence dict from build_evidence().
        path: filesystem path to write to.

    Raises:
        EvidenceError: if evidence is invalid.
    """
    _validate_evidence(evidence)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)
        f.write("\n")


def is_stale(evidence: Dict[str, Any], repo_root: str) -> bool:
    """Check whether evidence is still valid for the repository.

    Returns True if any check fails or cannot be computed.

    Args:
        evidence: an evidence dict (may be partial for checking).
        repo_root: path to the repository root.

    Returns:
        True if the evidence is stale or cannot be verified.
    """
    try:
        if not os.path.isdir(repo_root):
            return True

        current_sha = _git_rev_parse_head(repo_root)
        stored_sha = evidence.get("head_sha")
        if stored_sha is not None and current_sha != stored_sha:
            return True

        current_fingerprint = _compute_worktree_fingerprint(repo_root)
        stored_fp = evidence.get("worktree_fingerprint")
        if stored_fp is not None and current_fingerprint != stored_fp:
            return True

        return False
    except Exception:
        return True
