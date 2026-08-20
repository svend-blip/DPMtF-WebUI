#!/usr/bin/env python3
"""bridge-broker: the narrow host-side seam for sandboxed role transitions.

preferred_cloud_harness Run 003 introduced this script as the single
narrow capability a sandboxed role (super-deep-deep4 in the DeepSeek
Harness sandbox; imple-codex-minimaxM3 in the Codex workspace-write
sandbox) uses to cross into host territory without gaining unrestricted
host filesystem or host tmux access.

The supervisor cannot write /home/svend/flows (read-only mount) and
cannot see the host tmux socket /tmp/tmux-1000 (invisible mount). What
it CAN do is write to /home/svend/DPMtF-WebUI/databases/dpmtf.db.
That is the seam.

Two queue tables, both owned by this broker:

1. `bridge_dispatch_queue` — the SIGNAL-TRANSITION queue (handoff 009).
   Each row is a request for dispatch.py to perform a signal transition
   (signal-send, signal-complete, signal-escalation, signal-answer).
   No content body; the handoff file is referenced via handoff_path.

2. `bridge_materialize_queue` — the ARTIFACT-MATERIALIZATION queue
   (handoff 010). Each row is a request for the broker's host-side
   executor to write a governed artifact (BACKLOG.md, RUN-LEDGER.md,
   <id>-handoff.md, END-REPORT.md) to its canonical destination under
   {bridge_dir}/{flow_key}/.... Content is carried inline in the row,
   not via a host path reference, so the sandboxed enqueue never has
   to read a host filesystem path.

Both queues are self-bootstrapped by `_ensure_schema` so a missing
table never causes an enqueue to fail. Migration files remain the
authoritative schema source.

Canonical destinations for materialize rows are COMPUTED from
(flow_key, run_id, handoff_id, artifact_type), NEVER caller-supplied.
The materialize code path rejects any caller-supplied destination path.
This is the binding constraint from the Human amendment to GOAL.md
Run 003.

dispatch.py's evidence-gate and scope-fence validation are unchanged —
this broker is additive. The manual recovery path (running
`dispatch.py --signal-complete ...` directly) remains intact.

Usage:
    bridge_broker.py enqueue   --flow FLOW --from-role ROLE --to-role ROLE \\
                                --id N --action {signal-send|signal-complete|...} \\
                                [--handoff-path PATH]
    bridge_broker.py materialize --flow FLOW --type {backlog|run-ledger|handoff|end-report} \\
                                  [--run-id N] [--id N] \\
                                  --content "..." (or --content-stdin)
    bridge_broker.py process-once   [--db-path PATH]
    bridge_broker.py daemon         [--interval SECONDS] [--db-path PATH]
    bridge_broker.py status         [--limit N] [--db-path PATH] [--queue {dispatch|materialize|both}]
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path


# ── paths ────────────────────────────────────────────────

_HERE = Path(__file__).resolve().parent
_DISPATCH_PY = _HERE / "dispatch.py"


def _get_db_path() -> str:
    """Resolve the DPMtF DB path the same way dispatch.py does."""
    try:
        import config as _cfg  # noqa: WPS433 (deliberate in-script import)
        return _cfg.get_db_path()
    except Exception:
        # Standalone fallback: relative to Father repo root.
        return str(_HERE.parent.parent / "databases" / "dpmtf.db")


def _get_bridge_dir() -> str:
    """Resolve the bridge root (where canonical artifacts live).

    Defaults to /home/svend/flows, but is read from DPMTF_BRIDGE_DIR
    env var via config.get_bridge_dir() if available.
    """
    try:
        import config as _cfg  # noqa: WPS433
        bdir = _cfg.get_bridge_dir()
        if bdir:
            return str(bdir)
    except Exception:
        pass
    # Fallback: hardcoded canonical path.
    return "/home/svend/flows"


# ── enums / constants ───────────────────────────────────

# The four governed artifact types the broker accepts. Anything else
# is rejected. These names are part of the binding constraint from
# the Human amendment to GOAL.md Run 003.
_ARTIFACT_TYPES = ("backlog", "run-ledger", "handoff", "end-report")

# Append vs replace per artifact type. Computed once.
_ARTIFACT_MODE = {
    "backlog": "replace",
    "run-ledger": "append",
    "handoff": "create",
    "end-report": "replace",
}

# Size limit for inline --content to keep the queue DB bounded.
_MAX_CONTENT_BYTES = 4 * 1024 * 1024  # 4 MiB

# ── DB helpers ───────────────────────────────────────────

_SCHEMA_DISPATCH_SQL = """
CREATE TABLE IF NOT EXISTS bridge_dispatch_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_key TEXT NOT NULL,
    from_role TEXT NOT NULL,
    to_role TEXT NOT NULL,
    handoff_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('signal-send', 'signal-complete', 'signal-escalation', 'signal-answer')),
    handoff_path TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    claimed_at TEXT,
    processed_at TEXT,
    error_msg TEXT,
    broker_pid INTEGER
);
"""

# 010: companion table for artifact materialization. The broker
# self-bootstraps this schema inline (matching 058's pattern); the
# authoritative schema source would be a future migration file
# (out of scope for 010 — the broker's inline schema is the single
# source of truth today and the broker never accepts arbitrary paths
# or schema definitions).
_SCHEMA_MATERIALIZE_SQL = """
CREATE TABLE IF NOT EXISTS bridge_materialize_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_key TEXT NOT NULL,
    run_id INTEGER,
    handoff_id INTEGER,
    artifact_type TEXT NOT NULL CHECK (artifact_type IN ('backlog', 'run-ledger', 'handoff', 'end-report')),
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    claimed_at TEXT,
    processed_at TEXT,
    error_msg TEXT,
    broker_pid INTEGER
);
CREATE INDEX IF NOT EXISTS bridge_materialize_queue_status_idx
    ON bridge_materialize_queue(status, id);
CREATE INDEX IF NOT EXISTS bridge_materialize_queue_flow_idx
    ON bridge_materialize_queue(flow_key, status, id);
"""


def _open_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Apply 058 + 010 inline schemas.

    Both inline mirrors of the broker queue tables. Idempotent.
    The migration files (058, future 059) remain the authoritative
    schema sources for code review; this inline duplication is the
    broker's self-bootstrap, used when migrations have not been
    applied yet (e.g., a fresh test DB).
    """
    conn.executescript(_SCHEMA_DISPATCH_SQL)
    conn.executescript(_SCHEMA_MATERIALIZE_SQL)
    conn.commit()


# ── canonical destination derivation ─────────────────────

def _canonical_destination(
    flow_key: str, run_id: int | None, handoff_id: int | None,
    artifact_type: str,
) -> str:
    """Compute the canonical write destination from identity + type.

    NEVER accepts a caller-supplied path. The destination is a pure
    function of (flow_key, run_id, handoff_id, artifact_type) — so the
    broker can never be tricked into writing to an arbitrary host
    path. If any input does not match the artifact type's expected
    identity, this raises (validation has already enforced it; the
    raise is a defensive belt-and-braces).
    """
    if artifact_type not in _ARTIFACT_TYPES:
        raise ValueError(
            f"unknown artifact_type: {artifact_type!r}; "
            f"must be one of {_ARTIFACT_TYPES}"
        )
    bridge_dir = _get_bridge_dir()
    if artifact_type in ("backlog", "run-ledger", "end-report"):
        if not isinstance(run_id, int) or run_id < 1:
            raise ValueError(
                f"run_id must be a positive integer for "
                f"artifact_type={artifact_type!r}"
            )
    if artifact_type == "handoff":
        if not isinstance(handoff_id, int) or handoff_id < 1:
            raise ValueError(
                "handoff_id must be a positive integer for "
                "artifact_type='handoff'"
            )

    if artifact_type == "backlog":
        return f"{bridge_dir}/{flow_key}/runs/{run_id:03d}/BACKLOG.md"
    if artifact_type == "run-ledger":
        return f"{bridge_dir}/{flow_key}/runs/{run_id:03d}/RUN-LEDGER.md"
    if artifact_type == "handoff":
        return f"{bridge_dir}/{flow_key}/handoffs/{handoff_id:03d}-handoff.md"
    if artifact_type == "end-report":
        return f"{bridge_dir}/{flow_key}/runs/{run_id:03d}/END-REPORT.md"
    # Defensive — unreachable given the check above.
    raise ValueError(f"unhandled artifact_type: {artifact_type!r}")  # pragma: no cover


# ── validation ───────────────────────────────────────────

def _validate_known_flow(conn: sqlite3.Connection, flow_key: str) -> str | None:
    """Reject arbitrary unchecked flow_key strings.

    Returns an error message if flow_key is not in bridge_flows, else
    None. Uses the same DB connection as the caller (so the read is
    consistent with the broker's other DB activity).
    """
    if not isinstance(flow_key, str) or not flow_key:
        return f"flow_key must be a non-empty string"
    row = conn.execute(
        "SELECT 1 FROM bridge_flows WHERE flow_key = ? LIMIT 1",
        (flow_key,),
    ).fetchone()
    if row is None:
        return f"unknown flow_key: {flow_key!r} (not in bridge_flows)"
    return None


def _validate_materialize_identity(
    artifact_type: str, run_id: int | None, handoff_id: int | None,
    content: str,
) -> str | None:
    """Validate the identity inputs without touching the filesystem.

    Returns an error message on first failure, None if all checks pass.
    This is the sandbox-safe validation that runs at enqueue time
    (no filesystem access).

    Filesystem validation (run dir exists, handoff file absent, etc.)
    happens host-side in `_process_one_materialize` to keep the
    enqueue step purely DB-bound.
    """
    if artifact_type not in _ARTIFACT_TYPES:
        return (
            f"unknown artifact_type: {artifact_type!r}; "
            f"must be one of {_ARTIFACT_TYPES}"
        )

    if artifact_type in ("backlog", "run-ledger", "end-report"):
        if not isinstance(run_id, int) or run_id < 1:
            return (
                f"run_id must be a positive integer for "
                f"artifact_type={artifact_type!r}"
            )
        if handoff_id is not None:
            return (
                f"handoff_id must not be supplied for "
                f"artifact_type={artifact_type!r}"
            )

    if artifact_type == "handoff":
        if not isinstance(handoff_id, int) or handoff_id < 1:
            return (
                "handoff_id must be a positive integer for "
                "artifact_type='handoff'"
            )
        if run_id is not None:
            return (
                "run_id must not be supplied for "
                "artifact_type='handoff'"
            )

    if not isinstance(content, str) or len(content) == 0:
        return "content must be a non-empty string"
    if len(content.encode("utf-8")) > _MAX_CONTENT_BYTES:
        return (
            f"content too large: {len(content)} chars "
            f"(max {_MAX_CONTENT_BYTES} bytes)"
        )

    return None


# ── dispatch.py subprocess wrapper ──────────────────────

def _run_dispatch(row: sqlite3.Row) -> tuple[int, str]:
    """Invoke dispatch.py with the row's fields.

    Returns (returncode, error_message). The dispatch.py subprocess is
    called with the same command-line shape dispatch.py's main() expects.

    dispatch.py's main() always exits 0 — its success/failure is
    internal to the function — so the broker inspects the captured output
    for an "ERROR:" line. An "ERROR:" line indicates the dispatch failed
    (e.g. target session not running). The trace.log is the source of
    truth for the actual outcome; an ERROR: line is the broker's local
    signal that the dispatch did not complete cleanly.

    The from-role is always passed; the to-role is required for
    signal-send/signal-escalation/signal-answer and omitted for
    signal-complete (which infers from the DB).
    """
    cmd = [sys.executable, str(_DISPATCH_PY), "--db-flow", row["flow_key"]]

    action = row["action"]
    if action == "signal-send":
        cmd.append("--signal-send")
        cmd.extend(["--from-role", row["from_role"]])
        cmd.extend(["--to-role", row["to_role"]])
    elif action == "signal-complete":
        cmd.append("--signal-complete")
        cmd.extend(["--from-role", row["from_role"]])
    elif action == "signal-escalation":
        cmd.append("--signal-escalation")
        cmd.extend(["--from-role", row["from_role"]])
        cmd.extend(["--to-role", row["to_role"]])
    elif action == "signal-answer":
        cmd.append("--signal-answer")
        cmd.extend(["--from-role", row["from_role"]])
        cmd.extend(["--to-role", row["to_role"]])
    else:
        return (2, f"unknown action: {action!r}")

    cmd.extend(["--id", str(row["handoff_id"])])

    # Capture output for the broker's error_msg and ERROR detection;
    # never let it pollute the broker's own stdout (the chain_advancement
    # caller expects enqueue to be silent).
    try:
        completed = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        return (124, "dispatch.py timed out after 300s")
    except Exception as exc:  # noqa: BLE001
        return (1, f"dispatch.py spawn failed: {exc}")

    # dispatch.py's main() always exits 0, so inspect the captured
    # stdout for an "ERROR:" line — that is the broker's local signal
    # that the dispatch did not complete cleanly. The trace.log entry
    # dispatched.py emitted remains the canonical record.
    out = ((completed.stdout or "") + (completed.stderr or "")).strip()
    if completed.returncode != 0:
        return (completed.returncode, out[:2000])

    # Look for ERROR: in the dispatch.py output. Use a strict prefix
    # match so we do not catch the literals inside the dispatch.py
    # help text or the broker's own stderr.
    has_error = any(
        line.lstrip().startswith("ERROR")
        for line in out.splitlines()
    )
    if has_error:
        # Cap the message size so a chatty dispatch.py does not
        # blow up the queue row.
        return (1, out[:2000])
    return (0, "")


# ── materialize host-side write ─────────────────────────

def _process_one_materialize(conn: sqlite3.Connection) -> bool:
    """Claim one pending materialize row and write its artifact.

    Returns True if a row was processed, False if the queue is empty.
    Performs all filesystem validation host-side (run dir exists,
    run is active / no END-REPORT.md for backlog/run-ledger, handoff
    file does not already exist, etc.). On any validation failure the
    row is marked failed with a clear error_msg; the filesystem is
    left untouched.
    """
    cur = conn.execute(
        """
        UPDATE bridge_materialize_queue
        SET status = 'processing',
            claimed_at = datetime('now'),
            broker_pid = ?
        WHERE id = (
            SELECT id FROM bridge_materialize_queue
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT 1
        )
        """,
        (os.getpid(),),
    )
    conn.commit()
    if cur.rowcount == 0:
        return False

    row = conn.execute(
        """
        SELECT id, flow_key, run_id, handoff_id, artifact_type, content
        FROM bridge_materialize_queue
        WHERE broker_pid = ? AND status = 'processing'
        ORDER BY id DESC LIMIT 1
        """,
        (os.getpid(),),
    ).fetchone()
    assert row is not None  # we just claimed it

    rc, err = _write_materialize_artifact(conn, row)
    if rc == 0:
        conn.execute(
            """
            UPDATE bridge_materialize_queue
            SET status = 'completed',
                processed_at = datetime('now'),
                error_msg = NULL
            WHERE id = ?
            """,
            (row["id"],),
        )
    else:
        conn.execute(
            """
            UPDATE bridge_materialize_queue
            SET status = 'failed',
                processed_at = datetime('now'),
                error_msg = ?
            WHERE id = ?
            """,
            ((err or f"materialize exited {rc}")[:2000], row["id"]),
        )
    conn.commit()
    return True


def _write_materialize_artifact(
    conn: sqlite3.Connection, row: sqlite3.Row,
) -> tuple[int, str]:
    """Validate filesystem state and write the artifact atomically.

    Returns (rc, err_msg). rc == 0 means the artifact was written;
    rc != 0 means validation failed and the filesystem was NOT touched.
    """
    flow_key = row["flow_key"]
    run_id = row["run_id"]
    handoff_id = row["handoff_id"]
    artifact_type = row["artifact_type"]
    content = row["content"]

    # Compute canonical destination — never caller-supplied.
    try:
        dest = _canonical_destination(flow_key, run_id, handoff_id, artifact_type)
    except (TypeError, ValueError) as exc:
        return (2, f"canonical-destination error: {exc}")

    dest_path = Path(dest)

    # Filesystem validation per artifact type.
    parent = dest_path.parent

    if artifact_type in ("backlog", "run-ledger", "end-report"):
        # The run directory must exist (sanity — runs are created by
        # the Human at run-opening time, the broker does not create
        # them).
        if not parent.exists():
            return (
                1,
                f"run directory missing: {parent} "
                f"(artifact_type={artifact_type}, run_id={run_id})",
            )
        if not parent.is_dir():
            return (
                1,
                f"run path is not a directory: {parent}",
            )

    if artifact_type in ("backlog", "run-ledger"):
        # Run must be ACTIVE — no END-REPORT.md may exist unless the
        # write is the END-REPORT itself.
        end_report = parent / "END-REPORT.md"
        if end_report.exists():
            return (
                1,
                f"run is closed (END-REPORT.md exists at {end_report}); "
                f"refusing to write {artifact_type}",
            )

    if artifact_type == "end-report":
        # Refuse to silently overwrite an existing END-REPORT.md —
        # a run can be closed only once.
        if dest_path.exists():
            return (
                1,
                f"END-REPORT.md already exists at {dest_path}; "
                f"refusing to overwrite",
            )

    if artifact_type == "handoff":
        # Refuse to overwrite an existing handoff file — a handoff
        # that already exists has been dispatched or staged; do not
        # clobber it.
        if dest_path.exists():
            return (
                1,
                f"handoff file already exists: {dest_path}; "
                f"refusing to overwrite",
            )

    # All validation passed — perform the write.
    try:
        mode = _ARTIFACT_MODE[artifact_type]
        if mode == "append":
            # Append (create if absent). Open in append mode so we
            # never truncate the existing file.
            with open(dest_path, "a", encoding="utf-8") as f:
                f.write(content)
        elif mode == "create":
            # Exclusive create — fail if file already exists (we
            # already checked above, but the O_CREAT|O_EXCL is the
            # authoritative atomic primitive).
            fd = os.open(
                str(dest_path),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o644,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception:
                # If the write fails after the file is created,
                # clean up so we don't leave a 0-byte orphan.
                try:
                    os.unlink(str(dest_path))
                except OSError:
                    pass
                raise
        elif mode == "replace":
            # Replace (overwrite). Atomic rename pattern: write to a
            # sibling temp file, then rename.
            tmp = dest_path.with_suffix(dest_path.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, dest_path)
        else:
            return (2, f"unknown artifact mode: {mode!r}")
    except FileExistsError as exc:
        # Race: another process created the file between our check
        # and the open. Treat as a validation failure.
        return (1, f"target file already exists: {exc}")
    except OSError as exc:
        return (1, f"filesystem write failed: {exc}")

    return (0, "")


# ── the original signal-transition enqueue ──────────────

def cmd_enqueue(args: argparse.Namespace) -> int:
    """Sandbox-safe: write a queue row and return.

    Does NOT touch /home/svend/flows or /tmp/tmux-1000. The DB IS
    writable from inside the supervisor's sandbox (verified), so the
    enqueue itself works. No tmux has-session check here — that's the
    broker daemon's job on the host side (TG9: the seam is the queue
    row, not the visibility; the supervisor never sees the host tmux
    socket).

    Idempotency: if a row with the same (flow_key, from_role, to_role,
    handoff_id, action, status='completed') already exists, return 0
    without writing a duplicate. This matches dispatch.py's
    transition_recently_delivered guard (semantically: a delivered
    dispatch stays delivered).
    """
    db_path = args.db_path or _get_db_path()
    conn = _open_db(db_path)
    _ensure_schema(conn)

    # Validate handoff_path exists if provided — this is the broker's
    # narrow scope-fence check (a missing handoff file would fail
    # dispatch.py:signal_send's own check at line ~3149, so failing
    # fast here is not a regression, just clearer failure mode).
    if args.handoff_path:
        if not os.path.exists(args.handoff_path):
            print(
                f"bridge_broker: ERROR handoff file missing: {args.handoff_path}",
                file=sys.stderr,
            )
            conn.close()
            return 1

    # Idempotency: a completed row for this exact (flow, from, to, id, action)
    # is the same dispatch the bridge already performed.
    existing = conn.execute(
        """
        SELECT id FROM bridge_dispatch_queue
        WHERE flow_key = ? AND from_role = ? AND to_role = ?
          AND handoff_id = ? AND action = ? AND status = 'completed'
        ORDER BY id DESC LIMIT 1
        """,
        (args.flow_key, args.from_role, args.to_role,
         args.handoff_id, args.action),
    ).fetchone()
    if existing is not None:
        # Already delivered; nothing to do.
        conn.close()
        return 0

    conn.execute(
        """
        INSERT INTO bridge_dispatch_queue
            (flow_key, from_role, to_role, handoff_id, action,
             handoff_path, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """,
        (args.flow_key, args.from_role, args.to_role,
         args.handoff_id, args.action, args.handoff_path),
    )
    conn.commit()
    conn.close()
    # Be silent on success — the supervisor's chain_advancement is
    # `nohup ... &` and expects a quiet completion.
    return 0


# ── the materialize enqueue (sandbox-safe) ──────────────

def cmd_materialize(args: argparse.Namespace) -> int:
    """Sandbox-safe: write a materialize queue row and return.

    Validates DB-only constraints (artifact_type enumerated, flow_key
    known, run_id/handoff_id identity checks, content non-empty and
    bounded). Does NOT touch /home/svend/flows or /tmp/tmux-1000.

    Rejects any caller-supplied destination path: the broker computes
    the canonical destination from (flow_key, run_id, handoff_id,
    artifact_type) inside `_canonical_destination` — there is no CLI
    flag that accepts a destination path. The handoff's binding
    constraint from the Human amendment (GOAL.md Run 003).

    Filesystem validation (run dir exists, run is active / no
    END-REPORT.md, handoff file does not already exist) happens
    host-side in `_process_one_materialize` so the enqueue step
    touches nothing under the bridge dir.
    """
    db_path = args.db_path or _get_db_path()
    conn = _open_db(db_path)
    _ensure_schema(conn)

    # Read content (inline or from stdin).
    if args.content_stdin:
        content = sys.stdin.read()
    else:
        content = args.content or ""

    # Identity validation (artifact_type + run_id/handoff_id + content).
    identity_err = _validate_materialize_identity(
        args.artifact_type, args.run_id, args.handoff_id, content,
    )
    if identity_err is not None:
        print(f"bridge_broker: ERROR {identity_err}", file=sys.stderr)
        conn.close()
        return 1

    # Flow validation against bridge_flows.
    flow_err = _validate_known_flow(conn, args.flow_key)
    if flow_err is not None:
        print(f"bridge_broker: ERROR {flow_err}", file=sys.stderr)
        conn.close()
        return 1

    # Idempotency semantics (handoff 012 fix). Three modes:
    #   - handoff (create, one-shot per handoff_id): skip if ANY
    #     'completed' row exists for (flow_key, handoff_id, 'handoff').
    #     Preserves exclusive-create / refuse-overwrite.
    #   - end-report (replace, one-shot per run_id): skip if ANY
    #     'completed' row exists for (flow_key, run_id, 'end-report').
    #     Preserves refuse-overwrite.
    #   - run-ledger (append, multi-write per run_id) and backlog
    #     (replace, multi-write per run_id): skip ONLY if a 'pending' or
    #     'completed' row for (flow_key, run_id, artifact_type) already
    #     holds IDENTICAL content. 'failed' rows never suppress a
    #     request (retry is always allowed).
    #
    # Net effect: a second run-ledger append with DIFFERENT content is
    # enqueued (not dropped); a second backlog replace with DIFFERENT
    # content is enqueued (not dropped); an immediate repeat of IDENTICAL
    # content is dropped (no duplicate content); a retry after a 'failed'
    # row is allowed.
    if args.artifact_type == "handoff":
        # one-shot per handoff_id (exclusive-create).
        existing = conn.execute(
            """
            SELECT id FROM bridge_materialize_queue
            WHERE flow_key = ? AND handoff_id = ?
              AND artifact_type = ? AND status = 'completed'
            ORDER BY id DESC LIMIT 1
            """,
            (args.flow_key, args.handoff_id, args.artifact_type),
        ).fetchone()
    elif args.artifact_type == "end-report":
        # one-shot per run_id (refuse-overwrite).
        existing = conn.execute(
            """
            SELECT id FROM bridge_materialize_queue
            WHERE flow_key = ? AND run_id = ?
              AND artifact_type = ? AND status = 'completed'
            ORDER BY id DESC LIMIT 1
            """,
            (args.flow_key, args.run_id, args.artifact_type),
        ).fetchone()
    else:
        # run-ledger or backlog (multi-write per run_id).
        # Skip only if a 'pending' or 'completed' row already holds
        # IDENTICAL content. 'failed' rows never suppress a request.
        existing = conn.execute(
            """
            SELECT id FROM bridge_materialize_queue
            WHERE flow_key = ? AND run_id = ?
              AND artifact_type = ?
              AND status IN ('pending', 'completed')
              AND content = ?
            ORDER BY id DESC LIMIT 1
            """,
            (args.flow_key, args.run_id,
             args.artifact_type, content),
        ).fetchone()
    if existing is not None:
        conn.close()
        return 0

    conn.execute(
        """
        INSERT INTO bridge_materialize_queue
            (flow_key, run_id, handoff_id, artifact_type,
             content, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
        """,
        (args.flow_key, args.run_id, args.handoff_id,
         args.artifact_type, content),
    )
    conn.commit()
    conn.close()
    # Be silent on success — same convention as `enqueue`.
    return 0


# ── the original signal-transition process ──────────────

def _process_one(conn: sqlite3.Connection) -> bool:
    """Claim one pending signal row, dispatch it, update status.

    Returns True if a row was processed, False if the queue is empty.
    """
    # Atomic claim: only one broker processes any given row.
    cur = conn.execute(
        """
        UPDATE bridge_dispatch_queue
        SET status = 'processing',
            claimed_at = datetime('now'),
            broker_pid = ?
        WHERE id = (
            SELECT id FROM bridge_dispatch_queue
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT 1
        )
        """,
        (os.getpid(),),
    )
    conn.commit()
    if cur.rowcount == 0:
        return False

    row = conn.execute(
        """
        SELECT id, flow_key, from_role, to_role, handoff_id, action,
               handoff_path
        FROM bridge_dispatch_queue
        WHERE broker_pid = ? AND status = 'processing'
        ORDER BY id DESC LIMIT 1
        """,
        (os.getpid(),),
    ).fetchone()

    rc, err = _run_dispatch(row)

    if rc == 0:
        conn.execute(
            """
            UPDATE bridge_dispatch_queue
            SET status = 'completed',
                processed_at = datetime('now'),
                error_msg = NULL
            WHERE id = ?
            """,
            (row["id"],),
        )
    else:
        conn.execute(
            """
            UPDATE bridge_dispatch_queue
            SET status = 'failed',
                processed_at = datetime('now'),
                error_msg = ?
            WHERE id = ?
            """,
            (err or f"dispatch.py exited {rc}", row["id"]),
        )
    conn.commit()
    return True


def cmd_process_once(args: argparse.Namespace) -> int:
    """Process exactly one pending row (host-side only).

    Tries the materialize queue first (lower frequency, often larger
    payloads), then the signal queue. Returns 0 always; if both queues
    are empty prints a notice.
    """
    db_path = args.db_path or _get_db_path()
    conn = _open_db(db_path)
    _ensure_schema(conn)
    if _process_one_materialize(conn):
        conn.close()
        return 0
    if _process_one(conn):
        conn.close()
        return 0
    conn.close()
    print("bridge_broker: no pending rows")
    return 0


def cmd_daemon(args: argparse.Namespace) -> int:
    """Process pending rows forever (host-side deployment step).

    Polls both queues in priority order: materialize first, then
    signal transitions. Sleeps `interval` seconds when both queues
    are empty.
    """
    db_path = args.db_path or _get_db_path()
    conn = _open_db(db_path)
    _ensure_schema(conn)
    interval = max(0.5, float(args.interval))
    try:
        while True:
            if _process_one_materialize(conn):
                continue
            if _process_one(conn):
                continue
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nbridge_broker: daemon interrupted", file=sys.stderr)
    finally:
        conn.close()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Print the most recent queue rows.

    Default: prints both queues. --queue dispatch|materialize|both
    filters to one.
    """
    db_path = args.db_path or _get_db_path()
    conn = _open_db(db_path)
    _ensure_schema(conn)
    limit = max(1, int(args.limit))
    queue = getattr(args, "queue", "both")

    any_printed = False

    if queue in ("both", "dispatch"):
        rows = conn.execute(
            """
            SELECT id, flow_key, from_role, to_role, handoff_id, action,
                   status, created_at, processed_at
            FROM bridge_dispatch_queue
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        if rows:
            any_printed = True
            for row in rows:
                direction = f"{row['from_role']}->{row['to_role']}"
                print(
                    f"[dispatch] id={row['id']} {row['flow_key']} "
                    f"{direction} id={row['handoff_id']} "
                    f"action={row['action']} status={row['status']} "
                    f"created={row['created_at']} "
                    f"processed={row['processed_at']}"
                )

    if queue in ("both", "materialize"):
        rows = conn.execute(
            """
            SELECT id, flow_key, run_id, handoff_id, artifact_type,
                   status, created_at, processed_at
            FROM bridge_materialize_queue
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        if rows:
            any_printed = True
            for row in rows:
                ident = (
                    f"handoff_id={row['handoff_id']}"
                    if row["handoff_id"] is not None
                    else f"run_id={row['run_id']}"
                )
                print(
                    f"[materialize] id={row['id']} {row['flow_key']} "
                    f"{ident} type={row['artifact_type']} "
                    f"status={row['status']} created={row['created_at']} "
                    f"processed={row['processed_at']}"
                )

    conn.close()
    if not any_printed:
        print("bridge_broker: queue is empty")
        return 0
    return 0


# ── CLI entry ────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bridge_broker.py",
        description=(
            "bridge-broker: the narrow host-side seam for sandboxed role "
            "transitions (preferred_cloud_harness Run 003)."
        ),
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    # enqueue (signal transition)
    pe = sub.add_parser(
        "enqueue",
        help="Sandbox-safe: write a request row to the dispatch queue.",
    )
    pe.add_argument("--flow", required=True, dest="flow_key")
    pe.add_argument("--from-role", required=True, dest="from_role")
    pe.add_argument("--to-role", required=True, dest="to_role")
    pe.add_argument("--id", required=True, dest="handoff_id")
    pe.add_argument(
        "--action",
        required=True,
        choices=("signal-send", "signal-complete",
                 "signal-escalation", "signal-answer"),
    )
    pe.add_argument("--handoff-path", default=None)
    pe.add_argument("--db-path", default=None)
    pe.set_defaults(func=cmd_enqueue)

    # materialize (artifact write)
    pm = sub.add_parser(
        "materialize",
        help=(
            "Sandbox-safe: queue a request to write a governed artifact "
            "(BACKLOG.md / RUN-LEDGER.md / <id>-handoff.md / "
            "END-REPORT.md) to its canonical destination."
        ),
    )
    pm.add_argument("--flow", required=True, dest="flow_key")
    pm.add_argument(
        "--type", required=True, dest="artifact_type",
        choices=_ARTIFACT_TYPES,
        help="Governed artifact type.",
    )
    pm.add_argument(
        "--run-id", type=int, default=None,
        help="Run id (required for backlog/run-ledger/end-report).",
    )
    pm.add_argument(
        "--id", type=int, default=None, dest="handoff_id",
        help="Handoff id (required for handoff type).",
    )
    content_group = pm.add_mutually_exclusive_group(required=True)
    content_group.add_argument(
        "--content", default=None,
        help="Inline content for the artifact.",
    )
    content_group.add_argument(
        "--content-stdin", action="store_true",
        help="Read content from stdin.",
    )
    pm.add_argument("--db-path", default=None)
    pm.set_defaults(func=cmd_materialize)

    # process-once
    pp = sub.add_parser(
        "process-once",
        help="Host-side: process EXACTLY one pending row, then exit.",
    )
    pp.add_argument("--db-path", default=None)
    pp.set_defaults(func=cmd_process_once)

    # daemon
    pd = sub.add_parser(
        "daemon",
        help="Host-side deployment: poll both queues forever.",
    )
    pd.add_argument("--interval", default=2.0)
    pd.add_argument("--db-path", default=None)
    pd.set_defaults(func=cmd_daemon)

    # status
    ps = sub.add_parser(
        "status",
        help="Print the most recent queue rows (default: 50).",
    )
    ps.add_argument("--limit", default=50)
    ps.add_argument("--db-path", default=None)
    ps.add_argument(
        "--queue", default="both",
        choices=("both", "dispatch", "materialize"),
        help="Which queue to display.",
    )
    ps.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
