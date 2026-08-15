"""Audit metadata for the Deterministic Patcher (spec §30).

Every patch invocation should be traceable. Per spec §30 the patcher
populates a machine-readable audit block on every PatchResult with at
minimum:

  * patch_mode
  * engine
  * repository path
  * base revision (HEAD at invocation, when the target is a git repo)
  * files_requested
  * files_changed
  * operation count
  * resulting diff hash (sha256 of the captured diff; empty-diff
    convention stated below)
  * verification status
  * start / end timestamps (UTC ISO-8601)
  * final status

The patcher never introduces a new logging subsystem or writes its own
files (spec §30, handoff §3). Callers persist the audit block via
existing DPMtF run/artifact mechanisms — the patcher only returns it.

Empty-diff convention: when an apply is a no-change (e.g. an
idempotent `add_import` second run, or an `unified_diff` request whose
diff happens to be byte-identical to the on-disk content), the
resulting diff is None (or ""). The `resulting_diff_hash` for such
cases is the sha256 of the empty string — i.e.
`sha256("") = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`
— which is stable and unambiguous.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

from patcher.models import PatchRequest, PatchResult


# Stable hash for the empty diff. Computed once at module load.
EMPTY_DIFF_SHA256 = hashlib.sha256(b"").hexdigest()


# ── Repo metadata capture ───────────────────────────────────────────────


@dataclass(frozen=True)
class RepoMetadata:
    """Snapshot of repository facts at invocation time (spec §30, §31).

    The patcher invokes git to capture:

      * the repository's HEAD revision (or "" for an empty repo);
      * whether the working tree was clean at invocation;
      * the absolute path the request named as `repo_path`.

    All other audit fields are derived from the PatchRequest /
    PatchResult already in scope.
    """

    repo_path: str
    head_revision: str
    is_clean: bool


def capture_repo_metadata(repo_path: str) -> RepoMetadata:
    """Record the repository facts the audit block needs.

    Implementation notes:

      * We use `git rev-parse HEAD` for the commit hash; a missing
        HEAD (empty repo) is reported as "".
      * We use `git status --porcelain` for the dirty flag; an empty
        output means the tree was clean at invocation.
      * Any subprocess failure is swallowed: the audit block records
        what it could; the patcher's primary responsibility is the
        mutation, not the audit metadata.
    """
    head = _safe_git(repo_path, ("rev-parse", "HEAD")).strip()
    status_out = _safe_git(repo_path, ("status", "--porcelain"))
    return RepoMetadata(
        repo_path=str(Path(repo_path).resolve(strict=False)),
        head_revision=head,
        is_clean=(status_out.strip() == ""),
    )


def _safe_git(repo_path: str, args: Sequence[str]) -> str:
    """Run `git <args>` inside `repo_path` and return stdout.

    Swallows subprocess failures (exit non-zero, missing binary, etc.)
    so the audit block is best-effort and never crashes the patcher.
    """
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "-C", repo_path, *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, FileNotFoundError):
        return ""
    return proc.stdout or ""


# ── Audit block construction ────────────────────────────────────────────


@dataclass(frozen=True)
class AuditInputs:
    """The data needed to build the audit block.

    Captured at the start of the apply() call so timestamps reflect
    the actual invocation. The patcher fills each field once it is
    known (some — like `files_changed` — are only known after the
    mutation succeeds).
    """

    started_at_utc: str
    repo_metadata: RepoMetadata
    patch_mode: str
    engine: str
    files_requested: tuple  # tuple of str, hashable for dataclass frozen
    operations_requested: int
    files_changed: tuple = ()
    operations_applied: int = 0
    resulting_diff: Optional[str] = None
    verification_status: Optional[str] = None
    final_status: Optional[str] = None
    final_error_code: Optional[str] = None


def build_audit_block(
    inputs: AuditInputs,
    *,
    ended_at_utc: Optional[str] = None,
) -> Dict[str, Any]:
    """Render the audit block to a JSON-serializable dict.

    Keys are stable and match the spec §30 enumeration, plus a few
    derived fields callers may find useful (e.g. `resulting_diff_hash`
    is what the spec actually asks for; `resulting_diff_length` is a
    convenience).

    Args:
        inputs: the captured data.
        ended_at_utc: ISO-8601 UTC timestamp marking completion of
            this invocation. When None, the audit uses the current
            UTC time at the moment of the call.

    Returns:
        A JSON-serializable dict suitable for `PatchResult.audit`.
    """
    if ended_at_utc is None:
        ended_at_utc = _utc_now_iso()

    diff = inputs.resulting_diff or ""
    diff_hash = hashlib.sha256(diff.encode("utf-8")).hexdigest()

    return {
        "started_at": inputs.started_at_utc,
        "ended_at": ended_at_utc,
        "patch_mode": inputs.patch_mode,
        "engine": inputs.engine,
        "repository": inputs.repo_metadata.repo_path,
        "base_revision": inputs.repo_metadata.head_revision,
        "repo_was_clean_at_invocation": inputs.repo_metadata.is_clean,
        "files_requested": list(inputs.files_requested),
        "files_changed": list(inputs.files_changed),
        "operations_requested": inputs.operations_requested,
        "operations_applied": inputs.operations_applied,
        "resulting_diff_hash": diff_hash,
        "resulting_diff_empty": (diff == ""),
        "resulting_diff_length": len(diff),
        "verification_status": inputs.verification_status,
        "final_status": inputs.final_status,
        "final_error_code": inputs.final_error_code,
    }


# ── Convenience helpers used by the engines ─────────────────────────────


def utc_now_iso() -> str:
    """Return the current UTC time as ISO-8601 with explicit `Z` suffix.

    The handoff requires UTC ISO-8601; we use `Z` rather than `+00:00`
    for compactness and machine-readability.
    """
    return _utc_now_iso()


def diff_sha256(diff: Optional[str]) -> str:
    """Return the sha256 of `diff` (or the empty-string hash for None).

    Public so the engines / CLI can compute the hash directly without
    going through `build_audit_block`.
    """
    if diff is None:
        return EMPTY_DIFF_SHA256
    return hashlib.sha256(diff.encode("utf-8")).hexdigest()


def files_requested_for(request: PatchRequest) -> tuple:
    """Compute the `files_requested` tuple for a PatchRequest.

    For unified_diff requests the request does not name files
    explicitly; we still report the files named in the diff headers
    (best-effort). For structural_python requests the operations
    carry a `file` field per op; we return the unique files in input
    order.

    The result is a tuple (frozen dataclass compatibility).
    """
    if request.patch_mode == "structural_python" and request.operations:
        seen: list = []
        seen_set: set = set()
        for op in request.operations:
            if not isinstance(op, dict):
                continue
            f = op.get("file")
            if not isinstance(f, str) or not f:
                continue
            if f not in seen_set:
                seen_set.add(f)
                seen.append(f)
        return tuple(seen)

    if request.patch_mode == "unified_diff" and request.patch:
        return tuple(_extract_paths_from_diff(request.patch))

    return ()


def _extract_paths_from_diff(diff: str) -> Iterable[str]:
    """Yield each `b/<path>` named by a `diff --git` header.

    Mirrors the GitDiffEngine's extractor; duplicated here because the
    audit module must not import the engines (it is consumed by both
    engines and the facade — keeping it engine-agnostic).
    """
    import re

    pat = re.compile(
        r"^diff --git a/(?P<a>.+?) b/(?P<b>.+?)\s*$",
        re.MULTILINE,
    )
    for m in pat.finditer(diff):
        yield m.group("b")


__all__ = [
    "AuditInputs",
    "EMPTY_DIFF_SHA256",
    "RepoMetadata",
    "audit_inputs_from_request",
    "build_audit_block",
    "capture_repo_metadata",
    "diff_sha256",
    "files_requested_for",
    "utc_now_iso",
]


def _utc_now_iso() -> str:
    """Internal helper: ISO-8601 UTC with `Z` suffix and microseconds."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def audit_inputs_from_request(
    request: PatchRequest,
    *,
    engine: str,
    started_at: Optional[str] = None,
) -> AuditInputs:
    """Convenience: build an `AuditInputs` snapshot for a request.

    The patcher engines call this at the start of an apply() to capture
    the inputs that are stable for the whole call (timestamps,
    requested files, etc.). Mutable fields (`files_changed`,
    `operations_applied`, `resulting_diff`, etc.) are filled in by the
    caller once the mutation is known.

    Args:
        request: the incoming PatchRequest.
        engine: the engine name reporting the audit ("git_apply",
            "libcst", or "deterministic_patcher" for facade-level
            rejections).
        started_at: ISO-8601 timestamp marking invocation start. When
            None, the audit uses the current UTC time.
    """
    repo_metadata = capture_repo_metadata(request.repo_path)
    operations_requested = (
        len(request.operations) if request.operations else 0
    )
    return AuditInputs(
        started_at_utc=started_at if started_at is not None else _utc_now_iso(),
        repo_metadata=repo_metadata,
        patch_mode=request.patch_mode,
        engine=engine,
        files_requested=files_requested_for(request),
        operations_requested=operations_requested,
    )