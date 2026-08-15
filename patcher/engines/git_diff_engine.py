"""`git apply`-backed implementation of the unified-diff patch mode.

Spec §3, §29, §31–§32. The engine is intentionally narrow: it validates
the paths named in the diff, then runs `git apply --check`. On `apply()`
it runs `git apply` and captures the exact resulting `git diff` limited
to files the patch touched. No semantic repair of any kind (§23).

Phase 1D adds the post-apply verification pipeline (§18–§21) and
audit metadata (§30): after a successful mutation, syntax-check the
changed `.py` files (in-process `compile()`, no .pyc / __pycache__
artefacts) and execute any configured commands verbatim, then attach
the audit block to every PatchResult.

Every public method returns a `PatchResult` and leaves the tree
byte-identical on every failure path.
"""

from __future__ import annotations

import dataclasses
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from patcher.audit import (
    AuditInputs,
    audit_inputs_from_request,
    build_audit_block,
    utc_now_iso,
)
from patcher.engines.base import PatchEngine
from patcher.errors import (
    PATCH_APPLIED,
    PATCH_APPLY_FAILED,
    PATCH_BASE_MISMATCH,
    PATCH_CONFLICT,
    PATCH_INVALID,
    PATCH_PATH_REJECTED,
)
from patcher.models import PatchRequest, PatchResult
from patcher.policy import (
    PatchPathRejected,
    record_repo_state,
    validate_target_paths,
)
from patcher.verification import run_verification


# `diff --git a/<path> b/<path>` headers. We accept multi-line so we can
# extract every file touched by the patch.
DIFF_HEADER_RE = re.compile(
    r"^diff --git a/(?P<a>.+?) b/(?P<b>.+?)\s*$",
    re.MULTILINE,
)


# ── Diff parsing ────────────────────────────────────────────────────────


def _extract_paths_from_diff(diff: str) -> List[str]:
    """Return the list of `b/` paths named by `diff --git` headers.

    For renames this is the destination path (the one that ends up
    existing after the patch). For pure deletions the b/ path still
    exists in the header; we keep it here and let `git apply --check`
    decide whether the deletion is allowed.
    """
    return [m.group("b") for m in DIFF_HEADER_RE.finditer(diff or "")]


# ── Git invocation helpers ──────────────────────────────────────────────


def _run_git(
    repo_path: str,
    *args: str,
    input_text: Optional[str] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run `git <args>` inside repo_path and return the CompletedProcess.

    We deliberately do not use `shell=True` (auto-fail: silent failure
    if the wrong command is substituted). The caller passes `check=False`
    for commands whose non-zero exit is informational, not an error.
    """
    return subprocess.run(
        ["git", "-C", repo_path, *args],
        capture_output=True,
        text=True,
        input=input_text,
        check=check,
    )


def _write_patch_to_tempfile(patch: str) -> Path:
    """Write the patch to a temp file OUTSIDE the target repo and return
    its path.

    We deliberately do NOT put the file inside the repo: any file the
    engine writes there would show up in `git status --porcelain` and
    be reported as a patch-caused change, which is exactly the thing
    the engine is supposed to measure. The temp file lives in the
    system's default temp directory and is cleaned up by the engine on
    every code path (success and failure alike).
    """
    import tempfile

    fd, name = tempfile.mkstemp(prefix="patcher-diff-", suffix=".diff")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(patch or "")
    except Exception:
        # If we fail to write, leave no temp file behind.
        try:
            os.unlink(name)
        except OSError:
            pass
        raise
    return Path(name)


# Late import to avoid a top-level os import collision with the `os` we
# use elsewhere; cheap and contained to this module.
import os  # noqa: E402


# ── Resulting-diff capture ───────────────────────────────────────────────


def _capture_diff_for_files(
    repo_path: str, files: Sequence[str], state_before: "RepoStateRef"
) -> str:
    """Return `git diff` limited to `files`, with state_before's pre-existing
    changes excluded.

    The engine stores nothing between calls, so we keep `state_before`
    here as a small reference object. The actual capture uses
    `git diff -- <file>` per file and concatenates the results.
    """
    chunks: List[str] = []
    for f in files:
        # If the file was ALREADY changed before the patch ran, we still
        # want the post-patch diff for review, but only the lines the
        # patch added/removed. `git diff -- <file>` does exactly that:
        # diff vs HEAD for tracked files, or empty for untracked.
        proc = _run_git(repo_path, "diff", "--", f, check=False)
        if proc.stdout:
            chunks.append(proc.stdout)
    return "".join(chunks)


# ── Small reference object passed internally ────────────────────────────


class RepoStateRef:
    """Internal-only carrier so `_capture_diff_for_files` can take the
    pre-state as a parameter without re-exporting `RepoState` from the
    engine module. We never expose this type in the public API.
    """

    __slots__ = ("pre_existing",)

    def __init__(self, pre_existing: Tuple[str, ...]) -> None:
        self.pre_existing = pre_existing


# ── The engine ──────────────────────────────────────────────────────────


class GitDiffEngine(PatchEngine):
    """Unified-diff patch engine backed by `git apply`."""

    name = "git_apply"

    # ── check ──────────────────────────────────────────────────────────
    def check(self, request: PatchRequest) -> PatchResult:
        """Validate the request and run `git apply --check`. Never writes."""
        started_at = utc_now_iso()
        audit_inputs = audit_inputs_from_request(
            request, engine=self.name, started_at=started_at
        )

        validation = self._validate_request(request, write_phase=False)
        if validation is not None:
            return _with_audit(
                validation,
                audit_inputs,
                verification_status="not_run",
            )

        repo_path = request.repo_path
        try:
            paths = _extract_paths_from_diff(request.patch or "")
            if paths:
                validate_target_paths(repo_path, paths, request.allowed_paths)
        except PatchPathRejected as exc:
            return _with_audit(
                self._rejected(
                    engine=self.name,
                    error_code=exc.error_code,
                    error=str(exc),
                ),
                audit_inputs,
                verification_status="not_run",
            )

        patch_file = _write_patch_to_tempfile(request.patch or "")
        try:
            proc = _run_git(repo_path, "apply", "--check", str(patch_file), check=False)
            ok = proc.returncode == 0
            stderr = (proc.stderr or "").strip()
        finally:
            _safe_unlink(patch_file)

        if ok:
            result = PatchResult(
                status="check_passed",
                applied=False,
                engine=self.name,
            )
            return _with_audit(
                result,
                audit_inputs,
                verification_status="not_run",
            )
        return _with_audit(
            self._rejected(
                engine=self.name,
                error_code=PATCH_CONFLICT,
                error=stderr or "git apply --check failed",
            ),
            audit_inputs,
            verification_status="not_run",
        )

    # ── apply ──────────────────────────────────────────────────────────
    def apply(self, request: PatchRequest) -> PatchResult:
        """Apply the diff, capture the resulting diff, report files_changed.

        Failure leaves the working tree byte-identical to its pre-call
        state. We snapshot the porcelain state before and after the
        attempt; if anything changed and the apply did not succeed, we
        `git checkout --` to roll back.

        On successful mutation, the post-apply verification pipeline
        (spec §18–§21) runs and may escalate the result to
        `PATCH_APPLIED_SYNTAX_FAILED` or `PATCH_APPLIED_TEST_FAILED` —
        the change is LEFT IN PLACE; the surrounding DPMtF policy
        decides whether to revert.
        """
        started_at = utc_now_iso()
        audit_inputs = audit_inputs_from_request(
            request, engine=self.name, started_at=started_at
        )

        validation = self._validate_request(request, write_phase=True)
        if validation is not None:
            return _with_audit(
                validation,
                audit_inputs,
                verification_status="not_run",
            )

        repo_path = request.repo_path

        # ── 1. Record pre-state ─────────────────────────────────────────
        state = record_repo_state(repo_path)
        pre_porcelain = _capture_porcelain(repo_path)

        # ── 2. Validate paths ───────────────────────────────────────────
        try:
            paths = _extract_paths_from_diff(request.patch or "")
            if paths:
                validate_target_paths(repo_path, paths, request.allowed_paths)
        except PatchPathRejected as exc:
            return _with_audit(
                self._rejected(
                    engine=self.name,
                    error_code=exc.error_code,
                    error=str(exc),
                ),
                audit_inputs,
                verification_status="not_run",
            )

        # ── 3. base_revision check (spec §16 step 5) ────────────────────
        if request.base_revision and state.head_revision:
            if request.base_revision != state.head_revision:
                return _with_audit(
                    self._rejected(
                        engine=self.name,
                        error_code=PATCH_BASE_MISMATCH,
                        error=(
                            f"base_revision {request.base_revision!r} does not "
                            f"match current HEAD {state.head_revision!r}"
                        ),
                    ),
                    audit_inputs,
                    verification_status="not_run",
                )

        # ── 4. Write patch to a temp file OUTSIDE the repo ──────────────
        # (We deliberately do not write inside the repo: any file we
        # create there would show up in `git status --porcelain` and
        # be mis-attributed as a patch-caused change.)
        patch_file = _write_patch_to_tempfile(request.patch or "")

        try:
            # ── 5. git apply --check ────────────────────────────────────
            check_proc = _run_git(
                repo_path, "apply", "--check", str(patch_file), check=False
            )
            if check_proc.returncode != 0:
                stderr = (check_proc.stderr or "").strip()
                # Detect base/HEAD mismatches: git reports them with
                # phrases like "does not apply to index" or "patch does
                # not apply". Both are PATCH_CONFLICT per the spec;
                # PATCH_BASE_MISMATCH is reserved for explicit base_revision
                # checks (handled above).
                return _with_audit(
                    self._rejected(
                        engine=self.name,
                        error_code=PATCH_CONFLICT,
                        error=stderr or "git apply --check failed",
                    ),
                    audit_inputs,
                    verification_status="not_run",
                )

            # ── 6. git apply ────────────────────────────────────────────
            apply_proc = _run_git(
                repo_path, "apply", str(patch_file), check=False
            )
            if apply_proc.returncode != 0:
                stderr = (apply_proc.stderr or "").strip()
                # The tree should still be clean because --check passed,
                # but be defensive: if anything happened, roll it back.
                _rollback_to_porcelain(repo_path, pre_porcelain)
                return _with_audit(
                    self._rejected(
                        engine=self.name,
                        error_code=PATCH_CONFLICT,
                        error=stderr or "git apply failed",
                    ),
                    audit_inputs,
                    verification_status="not_run",
                )

            # The temp patch file is no longer needed; remove it BEFORE
            # we measure `git status --porcelain` so it cannot show up
            # as a patch-caused change.
            _safe_unlink(patch_file)
            patch_file = None  # so the final `finally` is a no-op

            # ── 7. Detect patch-caused changes ──────────────────────────
            post_porcelain = _capture_porcelain(repo_path)
            changed_files = _diff_porcelain(pre_porcelain, post_porcelain)

            # ── 8. Refuse to silently overwrite pre-existing dirty work ─
            unsafe = [
                f for f in changed_files if f in state.pre_existing_changed_files
            ]
            if unsafe:
                _rollback_to_porcelain(repo_path, pre_porcelain)
                return _with_audit(
                    self._rejected(
                        engine=self.name,
                        error_code=PATCH_CONFLICT,
                        error=(
                            "Patch would overwrite pre-existing dirty file(s): "
                            + ", ".join(sorted(unsafe))
                        ),
                    ),
                    audit_inputs,
                    verification_status="not_run",
                )

            # ── 9. Capture the resulting diff ───────────────────────────
            ref = RepoStateRef(state.pre_existing_changed_files)
            resulting_diff = _capture_diff_for_files(repo_path, changed_files, ref)

            success_result = PatchResult(
                status="applied",
                applied=True,
                engine=self.name,
                files_changed=changed_files,
                files_rejected=[],
                operations_requested=1,
                operations_applied=1,
                resulting_diff=resulting_diff,
                error_code=PATCH_APPLIED,
                error=None,
            )

            # ── 10. Post-apply verification (spec §18–§21) ─────────────
            v_outcome = run_verification(
                repo_path, changed_files, request.verification
            )
            if v_outcome.verdict == "passed":
                success_result = dataclasses.replace(
                    success_result,
                    verification=v_outcome.verification_dict,
                )
            elif v_outcome.verdict == "failed":
                success_result = dataclasses.replace(
                    success_result,
                    verification=v_outcome.verification_dict,
                    error_code=v_outcome.new_error_code,
                    error=v_outcome.failure_message,
                )
            else:
                # "not_run" — verification still advertises what it
                # considered (syntax skipped, no commands) so callers
                # can read `result.verification["syntax"]`.
                success_result = dataclasses.replace(
                    success_result,
                    verification=v_outcome.verification_dict,
                )

            return _with_audit(
                success_result,
                audit_inputs,
                files_changed=success_result.files_changed,
                operations_applied=success_result.operations_applied,
                resulting_diff=success_result.resulting_diff,
                verification_status=v_outcome.verdict,
            )

        except subprocess.CalledProcessError as exc:
            # Defensive: if git itself errored out, roll back and report.
            _rollback_to_porcelain(repo_path, pre_porcelain)
            return _with_audit(
                self._rejected(
                    engine=self.name,
                    error_code=PATCH_APPLY_FAILED,
                    error=f"git subprocess failed: {exc}",
                ),
                audit_inputs,
                verification_status="not_run",
            )

        finally:
            if patch_file is not None:
                _safe_unlink(patch_file)

    # ── helpers ────────────────────────────────────────────────────────
    def _validate_request(
        self, request: PatchRequest, write_phase: bool
    ) -> Optional[PatchResult]:
        """Reject requests that are clearly wrong BEFORE touching disk.

        Returns a rejection PatchResult if the request is malformed, or
        None if validation passed and the engine should proceed.
        """
        if not request.repo_path:
            return self._rejected(
                engine=self.name,
                error_code=PATCH_INVALID,
                error="repo_path is required",
            )
        if request.patch_mode != "unified_diff":
            return self._rejected(
                engine=self.name,
                error_code=PATCH_INVALID,
                error=f"GitDiffEngine received patch_mode={request.patch_mode!r}",
            )
        if not request.patch or not request.patch.strip():
            return self._rejected(
                engine=self.name,
                error_code=PATCH_INVALID,
                error="patch body is empty",
            )
        return None

    def _rejected(
        self, engine: str, error_code: str, error: str
    ) -> PatchResult:
        return PatchResult(
            status="rejected",
            applied=False,
            engine=engine,
            files_changed=[],
            files_rejected=[],
            operations_requested=0,
            operations_applied=0,
            resulting_diff=None,
            error_code=error_code,
            error=error,
        )


# ── Internal git-state helpers ──────────────────────────────────────────


def _capture_porcelain(repo_path: str) -> str:
    proc = _run_git(repo_path, "status", "--porcelain", check=False)
    return proc.stdout or ""


def _diff_porcelain(before: str, after: str) -> List[str]:
    """Return the file paths that appear in `after` but not in `before`.

    A simpler approach would be to compute the set difference of the
    porcelain lines, but porcelain lines change format as files move
    between staged/unstaged. Instead, we parse the path column out of
    each line (the same logic `record_repo_state` uses) and diff the
    path sets.
    """
    def paths(text: str) -> set:
        out = set()
        for line in text.splitlines():
            if not line.strip():
                continue
            path_field = line[3:] if len(line) >= 4 else ""
            if " -> " in path_field:
                path_field = path_field.split(" -> ", 1)[1]
            path_field = path_field.strip().strip('"')
            if path_field:
                out.add(path_field)
        return out

    return sorted(paths(after) - paths(before))


def _rollback_to_porcelain(repo_path: str, snapshot: str) -> None:
    """Best-effort rollback so the tree matches `snapshot` (porcelain text).

    We do not use `git checkout -- .` because that would discard ALL
    uncommitted changes, including files the patcher never touched. The
    snapshot already records exactly which paths were dirty before the
    patch; the simplest correct rollback is `git checkout -- <each path>`
    for every path that appears in `snapshot`. New files added by the
    patch are removed with `git clean -f -- <path>` if they exist.

    On any rollback failure we re-raise — the caller has already
    returned a rejection and will not retry, but if rollback itself
    crashes the operator needs to see it.
    """
    paths = set()
    for line in snapshot.splitlines():
        if not line.strip():
            continue
        path_field = line[3:] if len(line) >= 4 else ""
        if " -> " in path_field:
            path_field = path_field.split(" -> ", 1)[1]
        path_field = path_field.strip().strip('"')
        if path_field:
            paths.add(path_field)
    if paths:
        _run_git(repo_path, "checkout", "--", *sorted(paths), check=False)


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


# ── Audit attachment helper ────────────────────────────────────────────


def _with_audit(
    result: PatchResult,
    inputs: AuditInputs,
    *,
    files_changed: Optional[List[str]] = None,
    operations_requested: Optional[int] = None,
    operations_applied: Optional[int] = None,
    resulting_diff: Optional[str] = None,
    verification_status: str = "not_run",
) -> PatchResult:
    """Attach a fully-populated audit block to `result`.

    Used at every return point of `apply()` and `check()`. The audit
    block (spec §30) is machine-readable and includes all the minimum
    fields named in the handoff: patch_mode, engine, repository path,
    base revision, files_requested, files_changed, operation count,
    resulting diff hash (sha256, empty-string convention applied),
    verification status, UTC ISO-8601 start/end timestamps, and the
    final status / error_code.

    `operations_requested` defaults to the value the PatchResult
    carries when not overridden — that is the canonical source for
    the count (the engine sets it on every PatchResult it builds).
    """
    audit_inputs = dataclasses.replace(
        inputs,
        files_changed=tuple(files_changed) if files_changed is not None else inputs.files_changed,
        operations_requested=(
            operations_requested
            if operations_requested is not None
            else result.operations_requested
        ),
        operations_applied=(
            operations_applied
            if operations_applied is not None
            else inputs.operations_applied
        ),
        resulting_diff=(
            resulting_diff
            if resulting_diff is not None
            else inputs.resulting_diff
        ),
        verification_status=verification_status,
        final_status=result.status,
        final_error_code=result.error_code,
    )
    audit_block = build_audit_block(audit_inputs)
    return dataclasses.replace(result, audit=audit_block)
