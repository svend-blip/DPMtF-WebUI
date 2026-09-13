"""Deterministic knowledge-scope resolution for flows.

Each flow asks for knowledge about the repository it operates on. This module
binds that scope to the flow's ``bridge_flows.target_project_path`` so a flow
targeting ``FlowRunner`` receives ``flowrunner``, not the checkout's own scope.

Provider-neutral by design: it imports nothing from the provider layer and
only resolves the scope string. The provider and the scope guard receive that
string unchanged.
"""

import sqlite3
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "scripts" / "bridgeV002"))

import config  # noqa: E402
from bridge_lib import get_flow_target_project  # noqa: E402


def scope_for_target(target_path: str) -> str:
    """Return the knowledge scope for a filesystem target path.

    The scope is the lowercased final directory name with trailing slashes
    stripped: ``/home/x/FlowRunner/`` -> ``flowrunner`` and
    ``/home/x/AI_AdvisoryBoard`` -> ``ai_advisoryboard``. An empty path (or
    one whose final component is empty after stripping) returns the
    configured scope.
    """
    component = Path(str(target_path).rstrip("/")).name.lower()
    if not component:
        return config.get_knowledge_scope()
    return component


def scope_for_flow(flow_key: str | None) -> str:
    """Return the knowledge scope for a flow key.

    No flow key (``None`` or ``""``) resolves to the configured scope. A
    flow whose target is Father (resolved-path comparison) also keeps the
    configured scope. A missing database, a missing flow row, or a target
    that does not exist on disk all fall back to the configured scope.
    Never raises.
    """
    if not flow_key:
        return config.get_knowledge_scope()

    db_path = config.get_db_path()
    if not Path(db_path).exists():
        return config.get_knowledge_scope()

    try:
        target = get_flow_target_project(flow_key, db_path=db_path)
    except (ValueError, sqlite3.Error):
        return config.get_knowledge_scope()

    if Path(target).resolve() == Path(config.get_project_root()).resolve():
        return config.get_knowledge_scope()

    return scope_for_target(target)
