#!/usr/bin/env python3
"""Ownership registry for flow-owned runtime resources (Stop-servers lifecycle).

The rule behind the Stop-servers button: **DPMtF started it -> DPMtF may stop
it; externally/manually started -> DPMtF must not stop it.** The model
allocator already tracks its own runtimes (llama.cpp/SGLang pid files, model
leases); this is the small, general registry for the harness side of the
preferred_cloud_harness flow, where a role's runtime is a tmux-resident coding
harness rather than an allocator-managed server.

Backing table: ``flow_runtime_resources`` (migration 056).

- ``tmux_session``    — a session start_tmuxflow.py created for a flow.
- ``harness_process`` — a persistent harness DPMtF launched, with its pid.

A stop is ALWAYS by the recorded pid/session, never by executable name. A row
with a NULL pid is recorded-but-unkillable-by-pid and degrades to a no-op
rather than a guess; the tmux session remains the authoritative teardown for
tmux-resident harnesses.
"""

from __future__ import annotations

import os
import signal
import sqlite3
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config  # noqa: E402

RESOURCE_TYPES = ("tmux_session", "harness_process")

_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS flow_runtime_resources (
    flow_key TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    pid INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (flow_key, resource_type, resource_id)
)
"""


def _db(db_path=None):
    return db_path or config.get_db_path()


def _connect(db_path=None):
    conn = sqlite3.connect(_db(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute(_TABLE_DDL)
    return conn


def record(flow_key, resource_type, resource_id, pid=None, db_path=None):
    """Mark a runtime resource as DPMtF-started and therefore DPMtF-owned."""
    if resource_type not in RESOURCE_TYPES:
        raise ValueError(f"unknown resource_type: {resource_type!r}")
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO flow_runtime_resources "
            "(flow_key, resource_type, resource_id, pid) VALUES (?, ?, ?, ?)",
            (flow_key, resource_type, resource_id, pid),
        )
        conn.commit()
    finally:
        conn.close()


def list_for_flow(flow_key, resource_type=None, db_path=None):
    """Owned resources for a flow, newest first. Empty list when none/table missing."""
    conn = _connect(db_path)
    try:
        if resource_type:
            rows = conn.execute(
                "SELECT flow_key, resource_type, resource_id, pid, created_at "
                "FROM flow_runtime_resources WHERE flow_key = ? AND resource_type = ? "
                "ORDER BY created_at DESC",
                (flow_key, resource_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT flow_key, resource_type, resource_id, pid, created_at "
                "FROM flow_runtime_resources WHERE flow_key = ? ORDER BY created_at DESC",
                (flow_key,),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def is_owned(flow_key, resource_id, db_path=None):
    """True when this flow recorded ownership of ``resource_id``."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM flow_runtime_resources WHERE flow_key = ? AND resource_id = ?",
            (flow_key, resource_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def release(flow_key, resource_id, db_path=None):
    """Drop the ownership claim for a resource."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "DELETE FROM flow_runtime_resources WHERE flow_key = ? AND resource_id = ?",
            (flow_key, resource_id),
        )
        conn.commit()
    finally:
        conn.close()


def _default_kill(pid):
    """SIGTERM a pid. True when stopped or already gone; False when it could not be."""
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except ProcessLookupError:
        return True  # already dead — the ownership claim is stale
    except (PermissionError, OSError):
        return False


def stop_owned_harness_processes(flow_key, db_path=None, _kill=None):
    """Stop only flow-owned ``harness_process`` resources, by recorded pid.

    Anything not recorded by this flow is never touched — that is the whole
    ownership rule. ``_kill`` is injectable for tests (default: SIGTERM).
    Returns the list of resource_ids that were stopped (and released).
    """
    kill = _kill or _default_kill
    stopped = []
    for row in list_for_flow(flow_key, resource_type="harness_process", db_path=db_path):
        pid = row.get("pid")
        if not pid:
            continue
        if kill(pid):
            release(flow_key, row["resource_id"], db_path=db_path)
            stopped.append(row["resource_id"])
    return stopped


if __name__ == "__main__":
    print("runtime_owner — ownership registry for flow-owned runtime resources")
