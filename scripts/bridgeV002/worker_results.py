"""Turn a worker's completion into the step's deliverable, then advance.

§23 ends with the sentence this module is built around:

    Worker completion is not equivalent to Father acceptance.
    Father performs authoritative validation.

So the order is validate, materialise, advance — never receive-and-forward. A
worker that reports success is making a claim, and §6.1 puts validation on
Father's side of the boundary.

## What is built

Inline deliverables. The worker sends the document's text in
``deliverable.content``; Father checks the declared ``sha256`` against what
actually arrived, writes it atomically to the step's deliverable path, and
only then signals the next role.

## What is not

**Artifact transfer.** §23's schema also allows ``artifact_reference`` — a
handle to content Father must fetch. Nothing fetches it, so a result carrying
only a reference is refused with a reason that says so rather than being
written as an empty file. §6.1 lists artifact transfer as Father's, and it is
the next piece.

**Patch mode.** ``result_mode: patch`` and ``patch_and_deliverable`` return a
git patch to apply (§17.1). Applying it is Father's job and is not written;
those modes are refused explicitly. Bridge roles produce documents, which is
why ``deliverable_only`` is what the envelope builder requests today.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from typing import Any, Dict, Optional

ACCEPTED_STATUS = "role_execution_completed"
# `patch` alone is deliberately absent: chains advance on deliverables, and
# a patch-only result has nothing to hand the next role. An implementer that
# changes code AND writes its result document is `patch_and_deliverable` --
# which is also what §17.3 describes and what the envelope builder emits for
# roles with primary_output_type='patch'.
SUPPORTED_RESULT_MODES = {"deliverable_only", "patch_and_deliverable"}


class ResultRejected(RuntimeError):
    """Father does not accept this result.

    The execution stays recorded — the worker did what it did — but the
    chain does not advance on it. Rejecting loudly beats writing a
    deliverable nobody can trust and letting a reviewer find out.
    """


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_result(result: Dict[str, Any]) -> str:
    """Return the deliverable's content, or raise with why it is unacceptable."""
    if not isinstance(result, dict) or not result:
        raise ResultRejected("result is empty")

    status = str(result.get("status", "")).strip()
    if status != ACCEPTED_STATUS:
        raise ResultRejected(
            f"status is {status!r}, not {ACCEPTED_STATUS!r} — a failed or "
            "partial execution does not advance the chain")

    mode = str(result.get("result_mode", "")).strip()
    if mode == "patch":
        raise ResultRejected(
            "result_mode 'patch' has no deliverable and chains advance on "
            "deliverables — use 'patch_and_deliverable'")
    if mode not in SUPPORTED_RESULT_MODES:
        raise ResultRejected(
            f"result_mode {mode!r} is not supported; accepted: "
            f"{sorted(SUPPORTED_RESULT_MODES)}")

    if mode == "patch_and_deliverable":
        _validate_patch_fields(result)

    deliverable = result.get("deliverable")
    if not isinstance(deliverable, dict) or not deliverable:
        raise ResultRejected("result carries no deliverable block")

    content = deliverable.get("content")
    if content is None:
        # §23 artifact_reference: content too large for the result JSON was
        # uploaded first (content-addressed) and the result names its hash.
        ref = str(deliverable.get("artifact_sha256", "")).strip().lower()
        if not ref:
            raise ResultRejected("deliverable has no inline content and no "
                                 "artifact_sha256 reference")
        content = _read_artifact(ref)
    if not isinstance(content, str) or not content.strip():
        raise ResultRejected("deliverable content is empty")

    declared = str(deliverable.get("sha256", "")).strip().lower()
    if declared:
        actual = _sha256(content)
        if declared != actual:
            raise ResultRejected(
                f"deliverable sha256 mismatch: declared {declared[:12]}…, "
                f"content hashes to {actual[:12]}…")
    return content


def _artifacts_dir() -> str:
    import config as _config
    return os.path.join(_config.get_bridge_dir(), "lightworker", "artifacts")


def _read_artifact(sha256: str) -> str:
    """Resolve an artifact reference to text, verifying the hash.

    The name promises the content; the promise is still checked, because a
    filesystem is writable by more than this code path and §23's stance is
    that Father verifies rather than trusts.
    """
    if len(sha256) != 64 or not all(c in "0123456789abcdef" for c in sha256):
        raise ResultRejected(f"artifact_sha256 {sha256!r} is not a sha256")
    path = os.path.join(_artifacts_dir(), sha256)
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        raise ResultRejected(
            f"artifact {sha256[:12]}… was referenced but never uploaded")
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ResultRejected(
            f"artifact {sha256[:12]}… does not hash to its own name")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ResultRejected(
            f"artifact {sha256[:12]}… is not utf-8 text; binary deliverables "
            "are not a thing a reviewer can read")


def _validate_patch_fields(result: Dict[str, Any]) -> None:
    """§17.1's fields, checked before anything touches a repository."""
    base = str(result.get("base_commit", "")).strip().lower()
    if len(base) != 40 or not all(c in "0123456789abcdef" for c in base):
        raise ResultRejected(
            f"base_commit {base!r} is not a full 40-hex sha — a patch "
            "against an unknown base is a patch against the wrong tree")
    patch = resolve_patch_text(result)
    if patch.strip():
        declared = str(result.get("checksum", "")).strip().lower()
        actual = _sha256(patch)
        if declared != actual:
            raise ResultRejected(
                f"patch checksum mismatch: declared {declared[:12]}…, "
                f"patch hashes to {actual[:12]}…")


def resolve_patch_text(result: Dict[str, Any]) -> str:
    """The patch, inline or redeemed from an artifact reference."""
    if "patch" in result and result.get("patch") is not None:
        return str(result.get("patch", ""))
    ref = str(result.get("patch_artifact_sha256", "")).strip().lower()
    if ref:
        return _read_artifact(ref)
    return ""


def apply_patch_to_branch(
    *,
    target_project: str,
    base_commit: str,
    patch: str,
    branch: str,
    message: str,
) -> str:
    """Apply a worker's patch on a dedicated branch; return the new commit.

    Never the working tree, never master: the patch lands in a throwaway
    worktree checked out at the EXACT base commit the worker built against
    (§16.1 cuts both ways), is committed there, and only the branch ref
    survives. Reviewing and merging stay human-gated — §16.6 keeps the
    push pen in Father's hand, and this keeps the merge pen in the
    Human's. The branch is force-moved on re-application so a rework of
    the same handoff owns its own branch rather than colliding with its
    first attempt.
    """
    import subprocess
    import tempfile

    def _git(args, **kw):
        r = subprocess.run(["git", "-C", target_project] + args,
                           capture_output=True, text=True, timeout=120, **kw)
        if r.returncode != 0:
            raise ResultRejected(
                f"git {' '.join(args[:2])} failed while applying the patch: "
                f"{(r.stderr or r.stdout).strip()[:300]}")
        return r.stdout.strip()

    _git(["cat-file", "-e", f"{base_commit}^{{commit}}"])
    tmp = tempfile.mkdtemp(prefix="lw-apply-")
    try:
        _git(["worktree", "add", "--detach", tmp, base_commit])
        apply = subprocess.run(
            ["git", "-C", tmp, "apply", "--index", "--whitespace=nowarn"],
            input=patch, capture_output=True, text=True, timeout=120)
        if apply.returncode != 0:
            raise ResultRejected(
                "the patch does not apply cleanly at its own base_commit: "
                + (apply.stderr or apply.stdout).strip()[:300])
        subprocess.run(
            ["git", "-C", tmp, "-c", "user.name=lightworker",
             "-c", "user.email=lightworker@dpmtf.local",
             "commit", "-m", message],
            capture_output=True, text=True, timeout=120, check=True)
        sha = subprocess.run(
            ["git", "-C", tmp, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30, check=True
        ).stdout.strip()
        _git(["branch", "-f", branch, sha])
        return sha
    finally:
        subprocess.run(["git", "-C", target_project, "worktree", "remove",
                        "--force", tmp], capture_output=True, timeout=60)


def write_deliverable(content: str, path: str) -> str:
    """Publish the deliverable atomically. Returns the path written.

    A half-written result file is worse than none: the next role reads it
    and reviews a truncated document without knowing.
    """
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".partial")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return path


def accept_and_advance(
    *,
    execution: Dict[str, Any],
    result: Dict[str, Any],
    bridge_dir: str,
    signal: Optional[Any] = None,
) -> str:
    """Validate a worker's result, publish it, and signal the next role.

    `signal` is injected so this is testable without dispatching anything.
    The default is dispatch's own `signal_complete`, because §6.1 makes
    chain advancement Father's — the worker never does it (§5.2).
    """
    content = validate_result(result)

    envelope = execution.get("envelope") or {}
    mode = str(result.get("result_mode", "")).strip()
    if mode == "patch_and_deliverable":
        repo = (envelope.get("repository") or {})
        envelope_base = str(repo.get("base_commit", "")).strip().lower()
        result_base = str(result.get("base_commit", "")).strip().lower()
        if envelope_base and result_base != envelope_base:
            # The worker built where Father told it to, or the patch is
            # against the wrong tree. Cross-checked HERE because only the
            # envelope knows what Father dispatched.
            raise ResultRejected(
                f"patch base_commit {result_base[:12]}… is not the "
                f"envelope's {envelope_base[:12]}…")
        patch = resolve_patch_text(result)
        if patch.strip():
            import bridge_lib
            target = bridge_lib.get_flow_target_project(
                envelope.get("flow_key") or execution.get("flow_key"))
            flow = envelope.get("flow_key") or execution.get("flow_key")
            hid = envelope.get("handoff_id") or execution.get("handoff_id")
            sha = apply_patch_to_branch(
                target_project=target,
                base_commit=result_base,
                patch=patch,
                branch=f"lightworker/{flow}-{hid}",
                message=(f"lightworker {execution.get('execution_id','')}: "
                         f"handoff {hid} by "
                         f"{envelope.get('target_role','unknown role')}\n\n"
                         f"Applied by Father from a verified patch; review "
                         f"and merge stay human-gated."),
            )
            result["applied_commit"] = sha
    handoff = envelope.get("handoff") or {}
    relative = handoff.get("expected_deliverable") or ""
    if not relative:
        raise ResultRejected(
            "the offer carries no expected_deliverable; Father cannot know "
            "where this result belongs")

    path = write_deliverable(content, os.path.join(bridge_dir, relative))

    if signal is None:  # pragma: no cover - exercised by the live chain
        from dispatch import signal_complete as signal

    signal(
        envelope.get("flow_key") or execution.get("flow_key"),
        None,
        envelope.get("target_role") or execution.get("target_role"),
        envelope.get("handoff_id") or execution.get("handoff_id"),
        bridge_dir=bridge_dir,
    )
    return path
