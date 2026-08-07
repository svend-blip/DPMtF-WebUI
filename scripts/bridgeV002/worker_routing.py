"""Route a handoff to a remote LightWorker instead of a local tmux session.

A role whose `bridge_roles.execution_target` is set does not run on this host.
There is no tmux session to inject into; the work belongs to the named worker,
which polls for it over the §20 protocol.

**This module is inert until a role is given a target.** No row sets
`execution_target` today, so `worker_target()` returns None for every role and
dispatch takes the path it always has. That is deliberate, and it is the same
discipline migration 029 used when it added the column without filling it: a
routing change that activates itself the moment it is merged gives you no
moment to look at it.

## What is built here, and what is not

Built: the decision, and an offer carrying what dispatch knows — the ids, the
role, the flow, and where the compiled handoff sits.

**Not built: the §13 execution envelope.** A worker needs a repository triple
with an exact base commit, a governance payload and a result contract before
it can execute anything, and dispatch does not have those to hand. An offer
without an envelope is a claim ticket, not a job.

**Not built: the return path.** When the worker reports a result, something
must turn it into the step's deliverable and signal the next role. Nothing
does that yet.

So a role given an `execution_target` today would be offered work it cannot
perform, and no result would come back. Setting one is not a configuration
change; it is the next piece of work.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def worker_target(role_data: Dict[str, Any]) -> Optional[str]:
    """The worker a role executes on, or None when it runs on this host.

    Empty strings count as unset: a column defaulted to '' by some other
    migration must not silently route a role off-box.
    """
    target = (role_data or {}).get("execution_target")
    if target is None:
        return None
    target = str(target).strip()
    return target or None


def execution_id(handoff_id: str, to_role_key: str) -> str:
    """`EXEC-123-IMPLE01`, the form §5.1 and §16.4 both use."""
    return f"EXEC-{handoff_id}-{to_role_key.upper()}"


def _store():
    """The durable store, imported late so this module stays importable.

    dispatch.py loads at the top of every signal; a hard dependency on
    FastAPI's router package would make an unrelated import error break
    every local dispatch on the machine.
    """
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    from routers.lightworker_store import SqliteLightWorkerStore  # noqa: E402
    import config as dpmtf_config  # noqa: E402

    return SqliteLightWorkerStore(dpmtf_config.get_db_path())


def offer_to_worker(
    *,
    worker_id: str,
    handoff_id: str,
    flow_key: str,
    to_role_key: str,
    handoff_path: str,
    payload: Optional[Dict[str, Any]] = None,
    to_role_data: Optional[Dict[str, Any]] = None,
    target_project: Optional[str] = None,
    store=None,
) -> str:
    """Record an execution addressed to `worker_id`. Returns its id.

    The offer carries the §13 envelope when Father can assemble one, which
    needs the step payload, the role row and the flow's target project. It
    raises `EnvelopeIncomplete` rather than offering a partial envelope: a
    worker discovers a missing base commit only after cloning a repository
    and starting a model, and that is an expensive way to learn.
    """
    eid = execution_id(handoff_id, to_role_key)
    offer: Dict[str, Any] = {
        "execution_id": eid,
        "handoff_id": handoff_id,
        "worker_id": worker_id,
        "target_role": to_role_key,
        "flow_key": flow_key,
        "handoff_path": handoff_path,
    }
    if payload is not None and to_role_data is not None and target_project:
        offer["envelope"] = build_envelope(
            worker_id=worker_id, handoff_id=handoff_id, payload=payload,
            to_role_data=to_role_data, target_project=target_project,
            handoff_path=handoff_path,
        )
        offer["envelope_complete"] = True
    else:
        offer["envelope_complete"] = False
    (store or _store()).offer(offer)
    return eid


# ---------------------------------------------------------------------------
# §13 execution envelope
# ---------------------------------------------------------------------------
#
# The worker's `envelope_validator.py` is the specification here, not §13's
# prose. It is committed in DPMtF-LightWorker and it rejects, among others:
# a schema_version outside its allow-list, a model_source that is not
# `model_allocator`, a worker_id that is not its own, a base_commit that is
# not a full 40-hex SHA, an absolute or `..`-bearing deliverable path, and
# shell metacharacters in any id. Build to that, and a rejection is a real
# disagreement rather than a formatting quarrel.

SCHEMA_VERSION = "1"
MODEL_SOURCE = "model_allocator"


class EnvelopeIncomplete(RuntimeError):
    """Father cannot assemble a valid envelope from what it has.

    Raised rather than shipping a partial one. A worker that claims an
    execution and finds a missing base commit has already created a
    disposable worktree and started a model.
    """


def _git(args, cwd):
    import subprocess
    p = subprocess.run(["git", "-C", cwd, *args], capture_output=True,
                       text=True, timeout=30)
    return p.stdout.strip() if p.returncode == 0 else ""


def build_envelope(
    *,
    worker_id: str,
    handoff_id: str,
    payload: Dict[str, Any],
    to_role_data: Dict[str, Any],
    target_project: str,
    handoff_path: str,
    attempt_id: str = "ATTEMPT-1",
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble the §13 envelope for one role execution.

    Every field comes from something Father already knows. Where it does not
    know — a target project that is not a git repository, a role with no
    alias — this raises rather than guessing, because the guess would be
    discovered by the worker after it had built a worktree.
    """
    base_commit = _git(["rev-parse", "HEAD"], target_project)
    if len(base_commit) != 40 or not all(c in "0123456789abcdef" for c in base_commit):
        raise EnvelopeIncomplete(
            f"{target_project} gave no full base commit (got {base_commit!r}); "
            "§16.1 requires the exact SHA and the worker rejects anything else")

    clone_url = _git(["remote", "get-url", "origin"], target_project)
    if not clone_url:
        raise EnvelopeIncomplete(
            f"{target_project} has no origin to clone from; the worker needs a "
            "read-only URL (§16.2) and cannot reach this host's filesystem")

    model_alias = (to_role_data.get("default_model_alias") or "").strip()
    if not model_alias:
        raise EnvelopeIncomplete(
            f"role {to_role_data.get('role_key')!r} has no default_model_alias; "
            "§6.2 makes the alias Father's to choose and the worker resolves it")

    try:
        with open(handoff_path, "r", encoding="utf-8") as fh:
            handoff_content = fh.read()
    except OSError as exc:
        raise EnvelopeIncomplete(f"cannot read the compiled handoff: {exc}") from exc

    governance_content = ""
    gov = (to_role_data.get("governance_file") or "").strip()
    if gov:
        gov_path = gov if os.path.isabs(gov) else os.path.join(
            PROJECT_ROOT, "docs", "governance-templates-v2", gov)
        try:
            with open(gov_path, "r", encoding="utf-8") as fh:
                governance_content = fh.read()
        except OSError as exc:
            raise EnvelopeIncomplete(
                f"role governance {gov_path} is unreadable: {exc}. §19 says "
                "Father sends the governance rather than granting the worker "
                "a path into Father's tree") from exc

    # Relative by construction: the validator rejects absolute paths and `..`.
    expected = os.path.join(payload.get("deliverable_dir", ""),
                            payload.get("deliverable_file", ""))
    if not expected or os.path.isabs(expected) or ".." in expected.split(os.sep):
        raise EnvelopeIncomplete(
            f"deliverable path {expected!r} is not a safe relative path")

    return {
        "schema_version": SCHEMA_VERSION,
        "execution_id": execution_id(handoff_id, payload.get("to_role", "")),
        "job_id": job_id or f"JOB-{payload.get('flow_key', 'flow')}-{handoff_id}",
        "handoff_id": handoff_id,
        "attempt_id": attempt_id,
        "flow_key": payload.get("flow_key", ""),
        "step_key": payload.get("step_key", ""),
        "source_role": payload.get("from_role", ""),
        "target_role": payload.get("to_role", ""),
        "worker_id": worker_id,
        "model_source": MODEL_SOURCE,
        "model_alias": model_alias,
        "client": (to_role_data.get("allocator_client") or "opencode").strip(),
        "repository": {
            "project_key": os.path.basename(target_project.rstrip("/")),
            "clone_url": clone_url,
            "base_commit": base_commit,
        },
        "handoff": {
            "content": handoff_content,
            "governance_content": governance_content,
            "expected_deliverable": expected,
        },
        "result_contract": {
            # Bridge roles produce a document, not a patch (§17.2). A role
            # that should return a patch says so via primary_output_type.
            "mode": ("patch_and_deliverable"
                     if (to_role_data.get("primary_output_type") or "") == "patch"
                     else "deliverable_only"),
            "tests_required": False,
            "local_result_commit_required": False,
        },
    }
