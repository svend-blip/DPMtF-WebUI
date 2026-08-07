"""Wire the LightWorker router to the durable store and the return path.

`app.py` gets two lines and no knowledge of any of this. The pieces it joins
were built to be joined: `create_router` takes the store as a parameter and
the completion hook as another, so neither the router nor the store imports
the bridge, and the bridge does not import FastAPI.

The hook is where the two halves meet. §6.1 makes validation and chain
advancement Father's, and `worker_results.accept_and_advance` performs both —
in that order, and only when Father accepts.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict

import config

_BRIDGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "scripts", "bridgeV002")
if _BRIDGE not in sys.path:
    sys.path.insert(0, _BRIDGE)

from routers.lightworker_store import SqliteLightWorkerStore  # noqa: E402
from routers.lightworkers import create_router  # noqa: E402
from worker_results import accept_and_advance  # noqa: E402

store = SqliteLightWorkerStore(config.get_db_path())


def _on_complete(execution_id: str, result: Dict[str, Any]) -> None:
    """Validate, publish, advance — raising if Father does not accept.

    The router turns a raise into 422 and leaves the worker's report
    recorded. Nothing is swallowed: a result Father will not act on must
    say so on the wire, or the worker believes the chain moved on.
    """
    execution = store.get_execution(execution_id) or {}
    accept_and_advance(
        execution=execution,
        result=result,
        bridge_dir=config.get_bridge_dir(),
    )


router = create_router(store, on_complete=_on_complete)
