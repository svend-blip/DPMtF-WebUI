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
    store=None,
) -> str:
    """Record an execution addressed to `worker_id`. Returns its id.

    The offer carries only what dispatch knows. It is deliberately not a §13
    envelope — see the module docstring — and a worker reading this will find
    no repository, no base commit and no result contract.
    """
    eid = execution_id(handoff_id, to_role_key)
    (store or _store()).offer({
        "execution_id": eid,
        "handoff_id": handoff_id,
        "worker_id": worker_id,
        "target_role": to_role_key,
        "flow_key": flow_key,
        "handoff_path": handoff_path,
        "envelope_complete": False,
    })
    return eid
