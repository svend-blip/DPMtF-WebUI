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
import time
import sqlite3
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config  # noqa: E402
import bridge_lib  # noqa: E402 — for _harness_for_resource (stop-path resolves the harness by tmux_session)

RESOURCE_TYPES = ("tmux_session", "harness_process")

# Bounded wait after SIGTERM before declaring the process a survivor.
# A process that ignores SIGTERM (or that needs more time than this to
# wind down its own children) must NOT be reported stopped — the
# `work_unit` fresh-context stop relies on a verified kill.
_KILL_VERIFY_BOUND_SECONDS = 3.0
_KILL_VERIFY_POLL_INTERVAL = 0.1

# Today's exact behaviour, written as a literal — the FALLBACK ONLY. The
# consuming code never transcribes per-harness values; that transcription
# already lives in the harness_allocator oracle and must stay independent
# of the consuming code (GOAL.md §2 D4).
_DEFAULT_STOP_SPEC = {
    "signals": ["SIGTERM"],
    "grace_seconds": 3.0,
    "verify": "pid_gone",
}

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
    """SIGTERM a pid, then verify it actually exits within the kill bound.

    A surviving process must NOT be reported stopped: a pane-shell pid that
    ignores SIGTERM would silently defeat `work_unit` fresh-context stops.
    The verification polls `os.kill(pid, 0)` until it raises
    `ProcessLookupError` (the process is verifiably gone) or until the
    bounded wait elapses (a survivor; report False so the caller does not
    release the ownership claim).

    Returns:
        True when the process is verifiably gone (including already-dead
        at SIGTERM time — the ownership claim was stale and the
        verification was satisfied by the SIGTERM send itself).
        False when SIGTERM could not be sent (PermissionError/OSError) OR
        when the process is still alive after the bound.
    """
    if pid is None:
        return True  # already a non-claim
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True  # already dead at send time — claim was stale
    except (PermissionError, OSError):
        return False
    # Verify exit by polling os.kill(pid, 0) until ProcessLookupError
    # (process verifiably gone) or until the bounded wait elapses.
    deadline = time.monotonic() + _KILL_VERIFY_BOUND_SECONDS
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)  # signal 0 = existence check, no real signal sent
        except ProcessLookupError:
            return True
        except (PermissionError, OSError):
            # Race: another process used the pid, OR an EPERM barrier.
            # Treat as "no longer our process to verify" — honor the SIGTERM.
            return True
        time.sleep(_KILL_VERIFY_POLL_INTERVAL)
    return False  # process survived SIGTERM past the bound


def stop_spec_for(harness_key):
    """The allocator's StopSpec dict for ``harness_key``, or today's fallback.

    Thin delegate over ``harness_allocator.launchspec.get_stop_spec``.
    Returns a dict with EXACTLY the three bound keys ``signals`` (list of
    str), ``grace_seconds`` (int or float), ``verify`` (str).

    On ImportError (allocator package unavailable) or UnknownHarnessError
    (harness not registered — a ValueError subclass), returns a copy of
    ``_DEFAULT_STOP_SPEC`` so DPMtF keeps today's behaviour when the
    allocator is absent (GOAL.md §2).
    """
    try:
        import harness  # noqa: F401 — LATE import; harness imports runtime_owner, so top-level import cycles
        harness._standalone()  # ensure the allocator parent dir is on sys.path (cached, single resolver)
        import harness_allocator.launchspec as halaunchspec  # noqa: E402
        return halaunchspec.get_stop_spec(harness_key)
    except (ImportError, ValueError):
        return dict(_DEFAULT_STOP_SPEC)


def _harness_for_resource(resource_id, db_path=None):
    """The harness key for a harness_process ownership row, by session name.

    PRIMARY read: the active role whose ``tmux_session == resource_id``, its
    ``default_harness_source``. FALLBACK: ``allocator_client`` (the deprecated
    mirror start_coding still reads), then ``"opencode"`` (the resolve_harness
    default). Returns None when no active role maps to ``resource_id`` — the
    caller then applies the fallback stop spec.
    """
    if not resource_id:
        return None
    try:
        roles = bridge_lib.list_roles_from_db(db_path=db_path)
    except Exception:
        return None
    for role in roles:
        if (role.get("tmux_session") or "") == resource_id:
            return (
                role.get("default_harness_source")
                or role.get("allocator_client")
                or "opencode"
            ).strip().lower()
    return None


def _kill_by_spec(pid, spec):
    """Apply a StopSpec to ``pid``: send the signals ladder, wait the grace
    bound, verify per ``verify``. Returns True iff the pid is verifiably gone.

    For the codex/fallback spec (signals ["SIGTERM"], grace_seconds 3.0,
    verify "pid_gone") this is byte-identical to today's _default_kill.

    Short-circuit semantics (mirroring ``_default_kill``): once any signal
    in the ladder raises ``ProcessLookupError`` (pid already gone), the
    kill has succeeded — stop sending further signals and return True.
    A missing or empty ``signals`` ladder degrades to ``["SIGTERM"]`` so
    defensive callers cannot accidentally send no signals at all.
    """
    if pid is None:
        return True  # already a non-claim; the row will keep its pid=None
    signals = spec.get("signals") or ["SIGTERM"]
    if not signals:
        signals = ["SIGTERM"]
    grace = float(spec.get("grace_seconds", 3.0))
    # verify: today's only option is "pid_gone"; defensive default.
    for sig_name in signals:
        try:
            os.kill(pid, getattr(signal, sig_name))
        except ProcessLookupError:
            return True  # already dead — kill succeeded; stop ladder
        except (PermissionError, OSError):
            return False  # cannot signal — kill failed
    # All ladder signals sent; poll for the total grace bound.
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)  # existence check, no real signal
        except ProcessLookupError:
            return True
        except (PermissionError, OSError):
            # Race: another process used the pid, OR an EPERM barrier.
            # Treat as "no longer our process to verify" — honor the sends.
            return True
        time.sleep(_KILL_VERIFY_POLL_INTERVAL)
    return False  # survived past the bound


def stop_owned_harness_processes(flow_key, db_path=None, _kill=None):
    """Stop only flow-owned ``harness_process`` resources, by recorded pid.

    Anything not recorded by this flow is never touched — that is the whole
    ownership rule. ``_kill`` is injectable for tests (default: spec-driven
    kill via the harness's declared StopSpec). A resource is released only
    when the kill returns True (i.e. the process was verifiably gone,
    per the verified-kill contract). A surviving process keeps its
    ownership row and is NOT reported in the returned list.

    Spec resolution: PRIMARY — the row's harness via ``_harness_for_resource``
    (which walks bridge_roles by tmux_session). If the row's harness
    resolves, the spec is read through ``stop_spec_for``. If it does not
    resolve (no active role maps to the row's resource_id), the
    ``_DEFAULT_STOP_SPEC`` is applied directly — the same behaviour the
    pre-D2 code had, and the same behaviour the fallback path inside
    ``stop_spec_for`` returns. ZERO observable change for codex
    (signals=["SIGTERM"], grace_seconds=3.0, verify="pid_gone").

    Returns the list of resource_ids whose processes were verifiably
    stopped (and whose ownership rows were released).
    """
    stopped = []
    for row in list_for_flow(flow_key, resource_type="harness_process", db_path=db_path):
        pid = row.get("pid")
        if not pid:
            continue  # pid=None → no kill attempt; leave the row in place
        if _kill is not None:
            # Test seam: an injected _kill OVERRIDES the spec-driven path
            # (the contract test_stop_owned_releases_pid_none_rows_with_no_kill_attempt
            #  exercises this).
            killed = _kill(pid)
        else:
            harness_key = _harness_for_resource(row["resource_id"], db_path=db_path)
            if harness_key is not None:
                spec = stop_spec_for(harness_key)
            else:
                spec = _DEFAULT_STOP_SPEC
            killed = _kill_by_spec(pid, spec)
        if killed:
            release(flow_key, row["resource_id"], db_path=db_path)
            stopped.append(row["resource_id"])
    return stopped



def release_for_flow(flow_key, db_path=None):
    """Release EVERY runtime ownership claim for a flow.

    Used by stop_tmuxflow after the tmux teardown so Stop tmux/Servers does
    not accumulate dead ownership rows. Returns the list of resource_ids
    that were released (both `tmux_session` and `harness_process` types).
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT resource_id FROM flow_runtime_resources "
            "WHERE flow_key = ?",
            (flow_key,),
        ).fetchall()
        resource_ids = [row["resource_id"] for row in rows]
        conn.execute(
            "DELETE FROM flow_runtime_resources WHERE flow_key = ?",
            (flow_key,),
        )
        conn.commit()
    finally:
        conn.close()
    return resource_ids


if __name__ == "__main__":
    print("runtime_owner — ownership registry for flow-owned runtime resources")
