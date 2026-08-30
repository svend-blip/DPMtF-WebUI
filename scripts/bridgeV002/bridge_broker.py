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
    bridge_broker.py materialize --flow FLOW --type {backlog|run-ledger|handoff|end-report|escalation-response} \\
                                  [--run-id N] [--id N] [--role ROLE] \\
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
from datetime import datetime, timezone
from pathlib import Path

# The ONE canonical artifact-root resolver (two-flow spec §1/§2). A local
# `artifact_root or flow_key` reimplementation here would be exactly the
# scattering the specification forbids. bridge_lib self-inserts the project
# root for its config import, and both the CLI (script dir on sys.path) and
# the tests (explicit insert) can already import it.
import bridge_lib



# Run 025 D2: bounded backoff for transient "target session not running"
# failures inside _process_one. _RETRY_SLEEP is the seam tests
# monkeypatch to a no-op so the bound stays observable (the broker
# never sleeps in tests; the live process sleeps between retries).
_RETRY_BACKOFF_SECONDS: tuple[int, ...] = (30, 60, 120)
_RETRY_SLEEP = time.sleep

# Parser-inert prefix for the retry trace line — see
# `_write_retry_trace_line`. The existing trace consumers expect the
# standard `{UTC-ts} | {direction} | {id} | {event} | ...` shape at
# offset 0; lines starting with `delivery_retry | ` have a shifted
# layout and are deliberately invisible to them.
_RETRY_TRACE_PREFIX = "delivery_retry"

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

    config.get_bridge_dir() first, DPMTF_BRIDGE_DIR second, then a LOUD
    failure. The old fallback returned a hardcoded home path — the one
    auto-fail pattern this repo's own standard names — and a broker that
    guesses its artifact root writes canonical files somewhere silently
    wrong, which is strictly worse than stopping.
    """
    try:
        import config as _cfg  # noqa: WPS433
        bdir = _cfg.get_bridge_dir()
        if bdir:
            return str(bdir)
    except Exception:
        pass
    env_dir = os.environ.get("DPMTF_BRIDGE_DIR")
    if env_dir:
        return env_dir
    raise RuntimeError(
        "bridge dir unresolved: config.get_bridge_dir() unavailable "
        "and DPMTF_BRIDGE_DIR unset"
    )


# ── enums / constants ───────────────────────────────────

# The governed artifact types the broker accepts. Anything else is
# rejected. The first four are the binding constraint from the Human
# amendment to GOAL.md Run 003; `escalation-response` is the narrow
# Run 004 extension for supervisor escalation answers.
_ARTIFACT_TYPES = (
    "backlog", "run-ledger", "handoff", "end-report", "escalation-response",
    # Two-flow spec §3: the planning supervisor materializes the Run contract
    # DRAFT through this queue. "goal" is deliberately NOT a type here:
    # GOAL.md means the Human approved the Run (spec §4), and the queue is
    # the sandboxed roles' only write channel into the artifact root — so a
    # role physically cannot produce GOAL.md. Promotion is the host-side
    # `promote-goal` command, which records who approved.
    "goal-draft",
)

# Append vs replace per artifact type. Computed once.
_ARTIFACT_MODE = {
    "backlog": "replace",
    "run-ledger": "append",
    "handoff": "create",
    "end-report": "replace",
    "escalation-response": "create",
    # Replace, not create: the Human requesting changes produces a REVISED
    # draft for the same run (spec §4's revision loop), and each revision
    # supersedes the last. GOAL.md itself is never written through here.
    "goal-draft": "replace",
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
# or schema definitions). Run 004 adds `role_key` (identity input for
# escalation-response) and the `escalation-response` artifact type.
_MATERIALIZE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bridge_materialize_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_key TEXT NOT NULL,
    run_id INTEGER,
    handoff_id INTEGER,
    role_key TEXT,
    artifact_type TEXT NOT NULL CHECK (artifact_type IN ('backlog', 'run-ledger', 'handoff', 'end-report', 'escalation-response')),
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    claimed_at TEXT,
    processed_at TEXT,
    error_msg TEXT,
    broker_pid INTEGER
);
"""

_MATERIALIZE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS bridge_materialize_queue_status_idx
    ON bridge_materialize_queue(status, id);
CREATE INDEX IF NOT EXISTS bridge_materialize_queue_flow_idx
    ON bridge_materialize_queue(flow_key, status, id);
"""

_SCHEMA_MATERIALIZE_SQL = _MATERIALIZE_TABLE_SQL + _MATERIALIZE_INDEX_SQL


def _open_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Apply 058 + 010 inline schemas, then migrate if required.

    Both inline mirrors of the broker queue tables. Idempotent.
    The migration files (058, future 059) remain the authoritative
    schema sources for code review; this inline duplication is the
    broker's self-bootstrap, used when migrations have not been
    applied yet (e.g., a fresh test DB).
    """
    conn.executescript(_SCHEMA_DISPATCH_SQL)
    conn.executescript(_SCHEMA_MATERIALIZE_SQL)
    _migrate_materialize_schema(conn)
    conn.commit()


def _migrate_materialize_schema(conn: sqlite3.Connection) -> None:
    """Bring a pre-Run-004 materialize table up to date.

    The Run 003 table had neither a `role_key` column nor the
    `escalation-response` artifact type in its CHECK constraint. SQLite
    cannot add a column to a CHECK or alter the CHECK in place, so the
    table is rebuilt: old rows are copied verbatim (their `role_key`
    stays NULL — the type did not exist then), then the old table is
    dropped. Idempotent: an already-current table is left untouched.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type = 'table' AND name = 'bridge_materialize_queue'"
    ).fetchone()
    if row is None:
        return
    table_sql = row[0] or ""
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(bridge_materialize_queue)")}
    if "role_key" in cols and "escalation-response" in table_sql:
        return      # already current

    conn.executescript(
        """
        DROP INDEX IF EXISTS bridge_materialize_queue_status_idx;
        DROP INDEX IF EXISTS bridge_materialize_queue_flow_idx;
        ALTER TABLE bridge_materialize_queue
            RENAME TO bridge_materialize_queue_old;
        """
        + _MATERIALIZE_TABLE_SQL
        + _MATERIALIZE_INDEX_SQL
        + """
        INSERT INTO bridge_materialize_queue
            (id, flow_key, run_id, handoff_id, role_key, artifact_type,
             content, status, created_at, claimed_at, processed_at,
             error_msg, broker_pid)
        SELECT id, flow_key, run_id, handoff_id, NULL, artifact_type,
               content, status, created_at, claimed_at, processed_at,
               error_msg, broker_pid
        FROM bridge_materialize_queue_old;
        DROP TABLE bridge_materialize_queue_old;
        """
    )


# ── canonical destination derivation ─────────────────────

def _canonical_destination(
    flow_key: str, run_id: int | None, handoff_id: int | None,
    artifact_type: str, role_key: str | None = None,
) -> str:
    """Compute the canonical write destination from identity + type.

    NEVER accepts a caller-supplied path. The destination is a pure
    function of (flow_key, run_id, handoff_id, role_key, artifact_type)
    — so the broker can never be tricked into writing to an arbitrary
    host path. If any input does not match the artifact type's expected
    identity, this raises (validation has already enforced it; the
    raise is a defensive belt-and-braces).
    """
    if artifact_type not in _ARTIFACT_TYPES:
        raise ValueError(
            f"unknown artifact_type: {artifact_type!r}; "
            f"must be one of {_ARTIFACT_TYPES}"
        )
    bridge_dir = _get_bridge_dir()
    # The destination keys on the flow's EFFECTIVE artifact root, not the
    # flow key itself (two-flow spec §1): flows sharing a root share these
    # paths. The function remains pure in the security sense — the root
    # comes from the flow's own registered row, never from the caller.
    root = bridge_lib.get_effective_artifact_root(flow_key)
    if artifact_type in ("backlog", "run-ledger", "end-report", "goal-draft"):
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
    if artifact_type == "escalation-response":
        if not isinstance(handoff_id, int) or handoff_id < 1:
            raise ValueError(
                "handoff_id must be a positive integer for "
                "artifact_type='escalation-response'"
            )
        if not isinstance(role_key, str) or not role_key:
            raise ValueError(
                "role_key must be a non-empty string for "
                "artifact_type='escalation-response'"
            )

    if artifact_type == "goal-draft":
        return f"{bridge_dir}/{root}/runs/{run_id:03d}/GOAL-DRAFT.md"
    if artifact_type == "backlog":
        return f"{bridge_dir}/{root}/runs/{run_id:03d}/BACKLOG.md"
    if artifact_type == "run-ledger":
        return f"{bridge_dir}/{root}/runs/{run_id:03d}/RUN-LEDGER.md"
    if artifact_type == "handoff":
        return f"{bridge_dir}/{root}/handoffs/{handoff_id:03d}-handoff.md"
    if artifact_type == "end-report":
        return f"{bridge_dir}/{root}/runs/{run_id:03d}/END-REPORT.md"
    if artifact_type == "escalation-response":
        # Matches dispatch.py signal_answer's lookup:
        #   {bridge_dir}/escalations/{handoff_id}-{from_role}-response.md
        return f"{bridge_dir}/escalations/{handoff_id:03d}-{role_key}-response.md"
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


def _validate_role_in_flow(
    conn: sqlite3.Connection, flow_key: str, role_key: str,
) -> str | None:
    """Reject a role_key that is not a member of this flow's chain.

    escalation-response is written BY the answering role and read back by
    dispatch.py signal_answer as
    `{handoff_id}-{from_role}-response.md`. The role must therefore be a
    real role in `bridge_roles` AND appear as a from_role or to_role in
    this flow's steps — an arbitrary role string would write a response
    file signal_answer will never look up.
    """
    if not isinstance(role_key, str) or not role_key:
        return "role_key must be a non-empty string"
    row = conn.execute(
        "SELECT 1 FROM bridge_roles WHERE role_key = ? LIMIT 1",
        (role_key,),
    ).fetchone()
    if row is None:
        return f"unknown role_key: {role_key!r} (not in bridge_roles)"
    row = conn.execute(
        """
        SELECT 1 FROM bridge_flow_steps
        WHERE flow_key = ? AND (from_role = ? OR to_role = ?)
        LIMIT 1
        """,
        (flow_key, role_key, role_key),
    ).fetchone()
    if row is None:
        return (
            f"role_key {role_key!r} is not a member of flow "
            f"{flow_key!r} (not in bridge_flow_steps)"
        )
    return None


def _validate_materialize_identity(
    artifact_type: str, run_id: int | None, handoff_id: int | None,
    role_key: str | None, content: str,
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

    if artifact_type in ("backlog", "run-ledger", "end-report", "goal-draft"):
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
        if role_key is not None:
            return (
                f"role_key must not be supplied for "
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
        if role_key is not None:
            return "role_key must not be supplied for artifact_type='handoff'"

    if artifact_type == "escalation-response":
        if not isinstance(handoff_id, int) or handoff_id < 1:
            return (
                "handoff_id must be a positive integer for "
                "artifact_type='escalation-response'"
            )
        if run_id is not None:
            return (
                "run_id must not be supplied for "
                "artifact_type='escalation-response'"
            )
        if not isinstance(role_key, str) or not role_key:
            return (
                "role_key must be a non-empty string for "
                "artifact_type='escalation-response'"
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

def _is_transient_failure(err: str) -> bool:
    """Return True when the dispatch error is a transient session failure.

    Run 025 D2: the session-check failure path inside dispatch.py emits
    `ERROR: target session '<role>' is not running\n`. The substring
    `is not running` is the canonical signature; a NON-transient error
    (e.g. a real subprocess crash) does NOT contain that substring and
    fails fast — there is no retry.
    """
    if not err:
        return False
    return "is not running" in err


def _write_retry_trace_line(
    bridge_dir: str, flow_key: str, from_role: str, to_role: str,
    handoff_id: object, attempt_n: int, backoff: int,
) -> None:
    """Append ONE parser-inert retry trace line to bridge_dir/trace.log.

    Run 025 D2. The line is parser-inert BY DESIGN — it starts with the
    literal token `delivery_retry | ` so the position-shifted fields
    match no existing trace consumer (which expects the dispatch.log
    layout starting at offset 0). A future tooling change is free to
    parse this prefix; until then the line is invisible to dispatch.py /
    the broker's own `_last_relevant_trace_event` reader.

    The write is defensive: a missing/unreadable bridge dir or trace
    file is silently skipped (the broker never WRITES a file it
    cannot reach — the original "no-touch" contract still holds).
    """
    if not bridge_dir:
        return
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return
    line = (
        f"{_RETRY_TRACE_PREFIX} | {ts} | {flow_key} | "
        f"{from_role}->{to_role} | {handoff_id} | attempt {attempt_n}/3 | "
        f"backoff {backoff}s | session check failed, retrying\n"
    )
    trace_log = os.path.join(bridge_dir, "trace.log")
    try:
        with open(trace_log, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        return


def _dispatch_with_retry(row: sqlite3.Row) -> tuple[int, str, int]:
    """Call _run_dispatch with bounded retry on transient failures.

    Run 025 D2 — returns (final_rc, final_err, retries_used). The caller
    (`_process_one`) uses `final_rc` to choose completed/requeue/failed,
    and `final_err` as the row's error_msg on failure. `retries_used`
    is for tests; the live broker reads the row state, not the count.

    Bounded: initial attempt + 3 retries = 4 _run_dispatch
    invocations total. Between attempts the broker sleeps for the
    matching backoff (30s, 60s, 120s) via _RETRY_SLEEP — tests
    monkeypatch that seam to a no-op so the bound is observable in
    milliseconds rather than minutes.

    Non-transient failures short-circuit the retry loop and return the
    raw error message unchanged (today's `else: mark failed` behavior).
    """
    bridge_dir = _get_bridge_dir()
    rc, err = _run_dispatch(row)
    if rc == 0:
        return rc, err, 0
    if not _is_transient_failure(err):
        return rc, err, 0

    retries_used = 0
    for attempt_n, backoff in enumerate(_RETRY_BACKOFF_SECONDS, start=1):
        _RETRY_SLEEP(backoff)
        _write_retry_trace_line(
            bridge_dir,
            flow_key=row["flow_key"],
            from_role=row["from_role"],
            to_role=row["to_role"],
            handoff_id=row["handoff_id"],
            attempt_n=attempt_n,
            backoff=backoff,
        )
        retries_used += 1
        rc, err = _run_dispatch(row)
        if rc == 0:
            return rc, err, retries_used
        if not _is_transient_failure(err):
            return rc, err, retries_used

    # Retries exhausted with only transient failures — 4 total attempts,
    # backoff 30s/60s/120s. Compose an error_msg that names BOTH the
    # attempt count and the backoff (so a future operator reading the
    # row knows the broker DID try, not that it gave up).
    final_err = (
        f"transient-session retry exhausted: 4 attempts, "
        f"backoff 30s/60s/120s; last error: {err or ''}"
    )
    return rc, final_err, retries_used


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
    # D3 (Run 032 GOAL.md §1 D3) reorders the precedence so
    # REFUSED_INJECTION is detected BEFORE the rc != 0 check.
    # dispatch.py's _dispatch_main_run wrapper (D3) exits 1 when the
    # dispatch callable returns False -- which is true for BOTH a
    # transient busy-pane refusal (rc=2 requeue) and a hard pre-dispatch
    # / harness refusal (rc=1 failed). The dispatch.py output already
    # distinguishes the two by prefix: REFUSED_INJECTION: -> requeue,
    # everything else with an "ERROR:" line -> failed. Checking the
    # refusal prefix first preserves the Run 006 D6(b) requeue contract.
    out = ((completed.stdout or "") + (completed.stderr or "")).strip()

    # Look for REFUSED_INJECTION: in the dispatch.py output FIRST so a
    # busy-pane refusal still requeues even when the wrapper exits 1.
    # Strict prefix match -- do not catch literals inside dispatch.py's
    # help text or the broker's own stderr.
    has_refusal = any(
        line.lstrip().startswith("REFUSED_INJECTION")
        for line in out.splitlines()
    )
    if has_refusal:
        # Distinct return code (2) so _process_one can map this to a
        # requeue-with-backoff outcome (Run 006 D6(b)). The dispatch
        # deliberately logged nothing to trace.log, so the refused
        # delivery is invisible to recover_orphaned_rows -- exactly the
        # "refuse, never drop" outcome GOAL.md §1 D6 binds.
        return (2, out[:2000])
    if completed.returncode != 0:
        # dispatch.py exited nonzero without a REFUSED_INJECTION line.
        # D3 (Run 032 §1 D3): a pre-dispatch script refusal, a
        # dead-harness refusal (D1), an unhandled exception during
        # injection, etc. all exit 1 via _dispatch_main_run. The broker
        # maps anything but 2 to a `failed` row with error_msg set.
        return (completed.returncode, out[:2000])
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
        SELECT id, flow_key, run_id, handoff_id, role_key, artifact_type,
               content
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
    role_key = row["role_key"]
    artifact_type = row["artifact_type"]
    content = row["content"]

    # Compute canonical destination — never caller-supplied.
    try:
        dest = _canonical_destination(
            flow_key, run_id, handoff_id, artifact_type, role_key,
        )
    except (TypeError, ValueError) as exc:
        return (2, f"canonical-destination error: {exc}")

    dest_path = Path(dest)

    # Filesystem validation per artifact type.
    parent = dest_path.parent

    if artifact_type in ("backlog", "run-ledger", "end-report", "goal-draft"):
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

    if artifact_type == "escalation-response":
        # The escalations directory is created by the escalation path
        # (dispatch.py signal_escalation). Refuse to invent it, and
        # refuse to overwrite an existing response.
        if not parent.exists() or not parent.is_dir():
            return (
                1,
                f"escalations directory missing: {parent} "
                f"(artifact_type=escalation-response, handoff_id={handoff_id})",
            )
        if dest_path.exists():
            return (
                1,
                f"escalation response already exists: {dest_path}; "
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

    Handoff-id normalization (Run 006 D5): `args.handoff_id` is run
    through `normalize_handoff_id` BEFORE the idempotency check AND
    before the INSERT, so the stored `bridge_dispatch_queue.handoff_id`
    is always zero-padded (e.g. '21' -> '021'). That makes dispatch.py's
    `--id 042` resolve the canonical `042-handoff.md` correctly (the
    live orphan is dispatch row 47, handoff_id stored unpadded '21').
    """
    db_path = args.db_path or _get_db_path()
    conn = _open_db(db_path)
    _ensure_schema(conn)

    # Normalize handoff_id to its canonical zero-padded form. Must
    # run BEFORE the idempotency check AND the INSERT so both see the
    # same value (otherwise a '21' enqueue and a '021' enqueue for the
    # same transition would each be treated as a fresh row, double-
    # dispatching; --observed live 2026-08-21 as dispatch row 47).
    args.handoff_id = normalize_handoff_id(args.handoff_id)

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

    # Idempotency (Run 025 D1): a completed row for this exact
    # (flow, from, to, id, action) suppresses a new enqueue ONLY IF its
    # delivery actually reached the receiver. A row whose dispatch ended
    # in a gate rejection (gate_rejected / gate_escalation_required in
    # trace, per the SENDER of THIS transition) does NOT suppress —
    # last-relevant-event-wins:
    #   * last relevant trace event is a REJECTION  -> do NOT suppress
    #   * last relevant trace event is a DELIVERY   -> suppress
    #   * no relevant trace evidence                -> suppress (pre-025)
    #
    # REJECTION events: gate_rejected, gate_escalation_required.
    # DELIVERY events:  dispatched, signal_complete, signal_complete_to_human.
    #
    # The trace anchor matches dispatch.py:_gate_rejection_state's anchor
    # by SENDER (parts[1].split('->')[0] == from_role) and handoff_id
    # (parts[2] == str(handoff_id)), not by literal enqueue to_role — a
    # signal-complete enqueue self-addresses (from == to == sender) while
    # the trace records the callback direction sender->reviewer.
    #
    # cmd_enqueue READS the bridge dir (trace.log); its no-touch contract
    # now means "never WRITES". The read is defensive: missing or
    # unreadable trace.log -> no evidence -> suppress (row stands).
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
        last_event = _last_relevant_trace_event(
            bridge_dir=_get_bridge_dir(),
            from_role=args.from_role,
            handoff_id=args.handoff_id,
        )
        if last_event != "rejection":
            # Delivered (last_event == "delivery") or no evidence
            # (last_event is None) -> row stands -> suppress.
            conn.close()
            return 0
        # last_event == "rejection": the gate turned this delivery back,
        # so the re-enqueue must NOT be silently swallowed. Fall through
        # to INSERT below.

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

    role_key = getattr(args, "role_key", None)

    # Normalize handoff_id for consistency with cmd_enqueue (Run 006 D5).
    # The materialize queue column is INTEGER, so we re-cast back to int
    # for storage; the canonical destination in `_canonical_destination`
    # uses `handoff_id:03d`, which works correctly for either an int or
    # a zero-padded numeric string — keeping the same 011-handoff.md /
    # 042-handoff.md shape the enqueue side already produced.
    if args.handoff_id is not None:
        normalized = normalize_handoff_id(args.handoff_id)
        try:
            args.handoff_id = int(normalized)
        except (TypeError, ValueError):
            # Defensive: a non-numeric normalized form is rejected by
            # the integer validation that runs next. Leave the original
            # value so the error message names it.
            pass

    # Read content (inline or from stdin).
    if args.content_stdin:
        content = sys.stdin.read()
    else:
        content = args.content or ""

    # Identity validation (artifact_type + run_id/handoff_id/role_key
    # + content).
    identity_err = _validate_materialize_identity(
        args.artifact_type, args.run_id, args.handoff_id, role_key, content,
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

    # Role validation against bridge_roles + bridge_flow_steps.
    if args.artifact_type == "escalation-response":
        role_err = _validate_role_in_flow(conn, args.flow_key, role_key)
        if role_err is not None:
            print(f"bridge_broker: ERROR {role_err}", file=sys.stderr)
            conn.close()
            return 1

    # Idempotency semantics (handoff 012 fix). Four modes:
    #   - handoff (create, one-shot per handoff_id): skip if ANY
    #     'completed' row exists for (flow_key, handoff_id, 'handoff').
    #     Preserves exclusive-create / refuse-overwrite.
    #   - end-report (replace, one-shot per run_id): skip if ANY
    #     'completed' row exists for (flow_key, run_id, 'end-report').
    #     Preserves refuse-overwrite.
    #   - escalation-response (create, one-shot per handoff_id + role):
    #     skip if ANY 'completed' row exists for
    #     (flow_key, handoff_id, role_key, 'escalation-response').
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
        # D3 (Run 025): the ENQUEUE idempotency is keyed on the
        # DESTINATION FILE'S ABSENCE, not on a prior 'completed' row —
        # a superseded park that has been archived away host-side may
        # be re-closed, because the durable anchor is the file's
        # presence, not the row's history.
        #
        # TWO-LAYER NOTE (GOAL.md §2, INTENDED): the enqueue step
        # here is sandbox-safe and cannot always reach /home/svend/flows;
        # when the canonical-destination computation fails or the file
        # is not visible to the sandbox, exists() returns False and the
        # enqueue proceeds — the host-side _write_materialize_artifact
        # refuse-if-exists check remains the authoritative gate, so a
        # sandbox-blind enqueue still does NOT silently overwrite.
        existing = None
        try:
            dest = _canonical_destination(
                flow_key=args.flow_key,
                run_id=args.run_id,
                handoff_id=args.handoff_id,
                artifact_type=args.artifact_type,
                role_key=role_key,
            )
        except (TypeError, ValueError):
            dest = None
        if dest is not None and os.path.exists(dest):
            # Destination is present — refuse (silently, matching the
            # pre-D3 "completed row exists" convention; the host-side
            # write check would refuse again with the same outcome).
            conn.close()
            return 0
    elif args.artifact_type == "escalation-response":
        # one-shot per (handoff_id, role_key) (refuse-overwrite).
        existing = conn.execute(
            """
            SELECT id FROM bridge_materialize_queue
            WHERE flow_key = ? AND handoff_id = ? AND role_key = ?
              AND artifact_type = ? AND status = 'completed'
            ORDER BY id DESC LIMIT 1
            """,
            (args.flow_key, args.handoff_id, role_key, args.artifact_type),
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
            (flow_key, run_id, handoff_id, role_key, artifact_type,
             content, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """,
        (args.flow_key, args.run_id, args.handoff_id, role_key,
         args.artifact_type, content),
    )
    conn.commit()
    conn.close()
    # Be silent on success — same convention as `enqueue`.
    return 0


# ── the original signal-transition process ──────────────

# Backoff applied when inject_prompt refuses to paste into a busy
# or menu pane (Run 006 D6(b)). The refused row is requeued with
# `claimed_at` set to a future time, so the next claim skips it until
# the backoff elapses — a persistently-busy pane does not produce a
# tight re-claim loop.
_REFUSAL_BACKOFF_SECONDS = 10


def _process_one(conn: sqlite3.Connection) -> bool:
    """Claim one pending signal row, dispatch it, update status.

    Returns True if a row was processed, False if the queue is empty.

    Claim guard (Run 006 D6(a)): at most ONE 'processing' dispatch
    row per flow_key at any moment. A pending row for a flow that
    already has an in-flight row stays 'pending' until the in-flight
    row completes or fails. A row for a DIFFERENT flow is never
    blocked. The materialize queue is unaffected (the guard only
    inspects bridge_dispatch_queue).

    Backoff (Run 006 D6(b)): pending rows whose `claimed_at` is in
    the future are skipped (they are waiting out a refusal requeue).
    """
    # Atomic claim: only one broker processes any given row, and only
    # one row per flow at a time. The `claimed_at < now()` filter
    # honors the refusal-backoff (requeued rows wait out the window).
    cur = conn.execute(
        """
        UPDATE bridge_dispatch_queue
        SET status = 'processing',
            claimed_at = datetime('now'),
            broker_pid = ?
        WHERE id = (
            SELECT id FROM bridge_dispatch_queue
            WHERE status = 'pending'
              AND (claimed_at IS NULL OR claimed_at < datetime('now'))
              AND flow_key NOT IN (
                  SELECT DISTINCT flow_key FROM bridge_dispatch_queue
                  WHERE status = 'processing'
              )
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

    rc, err, _retries = _dispatch_with_retry(row)

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
    elif rc == 2:
        # Inject_prompt refused to paste (busy pane or interactive
        # menu/selector). Requeue with backoff so a persistently-busy
        # pane does not cause a tight re-claim loop. The row is NOT
        # marked completed (nothing was delivered) and NOT marked
        # failed (it deserves a retry), so the next claim picks it up
        # after the backoff window — bound by Run 006 GOAL.md §1 D6
        # "refuse, never drop".
        conn.execute(
            """
            UPDATE bridge_dispatch_queue
            SET status = 'pending',
                claimed_at = datetime('now', ?),
                broker_pid = NULL,
                error_msg = NULL,
                processed_at = NULL
            WHERE id = ?
            """,
            (f"+{_REFUSAL_BACKOFF_SECONDS} seconds", row["id"]),
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


def cmd_promote_goal(args: argparse.Namespace) -> int:
    """Promote an approved GOAL-DRAFT.md to GOAL.md — the recorded approval.

    Two-flow spec §4: GOAL.md means the Human approved this Run, and the
    planning supervisor must not be able to self-authorize the transition.
    The mechanics enforce that split: the materialize queue — the sandboxed
    roles' only write channel into the artifact root — refuses type "goal",
    so the ONLY path to GOAL.md is this host-side command, and it requires
    --approved-by naming who approved. The promotion renames the draft (a
    revision loop produces a fresh draft, not a second GOAL) and appends the
    approval event to the run's RUN-LEDGER so the record survives the
    session that performed it.

    Deterministic and refusing rather than clever: no draft -> error;
    GOAL.md already present -> error (a promoted Run is promoted once);
    closed run -> error.
    """
    flow_key = args.flow
    run_id = int(args.run_id)
    approved_by = (args.approved_by or "").strip()
    if not approved_by:
        print("ERROR: --approved-by must name who approved", file=sys.stderr)
        return 2

    bridge_dir = _get_bridge_dir()
    root = bridge_lib.get_effective_artifact_root(flow_key)
    run_dir = Path(bridge_dir) / root / "runs" / f"{run_id:03d}"
    # Hybrid draft channel (Human decision 2026-08-26): the planning
    # supervisor delivers the draft as an ORDINARY step deliverable,
    # 1000/goals/{ID}-GOAL-DRAFT.md, and the deliverable id BECOMES the run
    # id — so "only PLOOP allocates Run IDs" is enforced by the flow's own
    # id counter rather than by convention. Dispatch writes the id
    # unpadded; the run directory is padded. The broker goal-draft type
    # remains a second, equivalent source (runs/NNN/GOAL-DRAFT.md).
    goals_draft = Path(bridge_dir) / root / "goals" / f"{run_id}-GOAL-DRAFT.md"
    run_draft = run_dir / "GOAL-DRAFT.md"
    draft = goals_draft if goals_draft.exists() else run_draft
    goal = run_dir / "GOAL.md"
    end_report = run_dir / "END-REPORT.md"

    if end_report.exists():
        print(f"ERROR: run {run_id:03d} is closed ({end_report}); "
              f"nothing to promote", file=sys.stderr)
        return 1
    if goal.exists():
        print(f"ERROR: {goal} already exists — a Run is promoted once; a "
              f"revision needs a NEW draft and a new approval", file=sys.stderr)
        return 1
    if not draft.exists():
        print(f"ERROR: no draft at {goals_draft} or {run_draft}",
              file=sys.stderr)
        return 1

    # Parse gate (Human decision 2026-08-26): a contract that cannot be
    # read mechanically is refused AT APPROVAL, not discovered when the
    # decomposer stands mid-run with it. Readability only — the criteria
    # themselves must be red before a run, so nothing is executed here.
    import check_testgoals
    draft_text = draft.read_text(encoding="utf-8")
    try:
        criteria = check_testgoals.parse_block(draft_text)
    except check_testgoals.CriterionError as exc:
        print(f"REFUSED: testgoals block malformed — {exc}", file=sys.stderr)
        print("Fix the draft and promote again; nothing was moved.",
              file=sys.stderr)
        return 1
    if not criteria:
        print("WARNING: draft has no ```testgoals block — promoting anyway "
              "(hand-validation per 461); the ELOOP landing will need "
              "criteria from somewhere", file=sys.stderr)

    # OD-3 (Human decision 2026-08-26): a Run's baseline is the target
    # repository's HEAD at promotion, recorded durably beside the approver.
    # It is the honest answer to "what did the Human approve this Run
    # against", it needs no schema, and it cannot drift, because a Run is
    # promoted once.
    #
    # The dirty-file count travels with it because a baseline is only
    # meaningful against a clean tree: if the target holds uncommitted work
    # at promotion, the recorded commit describes something other than what
    # is on disk, and the evidence gate compares the working tree rather
    # than git history. Promotion does not refuse a dirty tree — the
    # workspace's own dpmtf.db is permanently dirty by design — but an
    # unrecorded dirty tree would let a later reader mistake the baseline
    # for a full description of the starting state. Recording the count
    # makes the caveat legible instead of silent.
    baseline_line = "- baseline: NOT RECORDED (no target project for flow)\n"
    try:
        target = bridge_lib.get_flow_target_project(flow_key)
    except Exception as exc:  # pragma: no cover - defensive
        target = None
        baseline_line = f"- baseline: NOT RECORDED (lookup failed: {exc})\n"
    if target:
        head = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        )
        if head.returncode == 0:
            sha = head.stdout.strip()
            dirty = subprocess.run(
                ["git", "-C", str(target), "status", "--porcelain",
                 "--untracked-files=all"],
                capture_output=True, text=True,
            )
            files = [ln for ln in dirty.stdout.splitlines() if ln.strip()]
            state = ("clean" if not files
                     else f"{len(files)} uncommitted path(s) at promotion")
            baseline_line = (f"- baseline: `{sha}` in {target} "
                             f"(working tree: {state})\n")
        else:
            baseline_line = (f"- baseline: NOT RECORDED ({target} is not a "
                             f"git repository)\n")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    draft.rename(goal)
    ledger = run_dir / "RUN-LEDGER.md"
    entry = (f"\n## {stamp} — GOAL promoted (recorded Human approval)\n"
             f"- GOAL-DRAFT.md -> GOAL.md by `promote-goal`, "
             f"approved-by: {approved_by}\n"
             f"- flow: {flow_key} (artifact root: {root})\n"
             + baseline_line)
    if ledger.exists():
        ledger.write_text(ledger.read_text(encoding="utf-8") + entry,
                          encoding="utf-8")
    else:
        ledger.write_text(f"# RUN-LEDGER — run {run_id:03d}\n" + entry,
                          encoding="utf-8")
    print(f"PROMOTED: {goal} (approved-by: {approved_by})")
    return 0


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


# ── public helpers (Run 006 D4 / D5) ────────────────────────


def normalize_handoff_id(value) -> str:
    """Zero-pad a numeric handoff_id to three digits.

    Accepts an int or a str. Numeric values are zero-padded to three
    digits so the stored id and dispatch.py's `--id` flag always match
    the canonical `<id>-handoff.md` filename:

        '21'  -> '021'    (str, unpadded)
        '7'   -> '007'    (str, unpadded)
        21    -> '021'    (int)
        '021' -> '021'    (str, already padded, idempotent)
        '100' -> '100'    (str, three digits already, idempotent)

    A value that is not a plain non-negative integer is returned
    unchanged (defensive pass-through) — this flow only ever uses
    numeric handoff ids, but a non-numeric caller must not crash the
    helper. (bool is treated as the int it is a subclass of; it is not
    a valid handoff id and will fail downstream validation.)

    Names and semantics are bound by preferred_cloud_harness Run 006
    GOAL.md section 2 (D5); reviewers and criteria import this name.
    """
    # bool is a subclass of int — handle explicitly so True/False do
    # not silently get padded into '001'/'000'.
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:03d}"
    if isinstance(value, str):
        s = value.strip()
        if s.isdigit():
            return f"{int(s):03d}"
        return value
    return str(value)


def _last_relevant_trace_event(
    bridge_dir: str, from_role: str, handoff_id: object,
) -> str | None:
    """Return the LAST relevant trace event for `from_role` + `handoff_id`.

    Run 025 D1 idempotency guard — returns one of:
      * "delivery"  — last matching event is a DELIVERY
        (dispatched / signal_complete / signal_complete_to_human)
      * "rejection" — last matching event is a REJECTION
        (gate_rejected / gate_escalation_required)
      * None        — no relevant evidence in the trace (defensive: a
        missing or unreadable trace.log is treated as no evidence)

    The trace is scanned in line order; "last" means the LAST matching
    line in append-only trace.log (a later line is a later event).
    Timestamp parsing is deliberately skipped — append-only log order
    is the source of truth (mirrors the run-019 ordering lesson; if two
    events share a second-resolution timestamp, the later line in the
    file is the later event).

    The SENDER anchor (parts[1].split('->')[0] == from_role) mirrors
    dispatch.py:_gate_rejection_state's anchor exactly: a signal-complete
    enqueue self-addresses (from_role == to_role == sender) while the
    trace records the callback direction sender->reviewer, so matching
    by literal enqueue to_role would miss the line. parts[2] is the
    handoff_id (str-coerced for parity with dispatch's `parts[2] ==
    str(handoff_id)` rule).
    """
    trace_log = os.path.join(bridge_dir, "trace.log")
    try:
        with open(trace_log, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        # Missing/unreadable trace -> no evidence -> caller suppresses.
        return None

    handoff_str = str(handoff_id)
    delivery_events = (
        "dispatched", "signal_complete", "signal_complete_to_human",
    )
    rejection_events = ("gate_rejected", "gate_escalation_required")

    last_event: str | None = None
    for line in lines:
        parts = line.split(" | ")
        if len(parts) < 4:
            continue
        # parts[1] is the direction "from->to". Match by SENDER so a
        # signal-complete enqueue's self-addressed from_role still
        # catches the callback direction line in the trace.
        direction_sender = parts[1].split("->", 1)[0].strip()
        if direction_sender != from_role:
            continue
        if parts[2] != handoff_str:
            continue
        if parts[3] in delivery_events:
            last_event = "delivery"
        elif parts[3] in rejection_events:
            last_event = "rejection"
        # Any other event name for this sender+handoff is ignored —
        # only DELIVERY and REJECTION decide suppression.
    return last_event


def _trace_records_delivery(
    trace_lines: list[str], from_role: str, to_role: str,
    handoff_id: object,
) -> bool:
    """True iff any trace line records a delivery of this transition.

    Mirrors dispatch.py:transition_recently_delivered's delivery
    semantics exactly (so recover_orphaned_rows and dispatch.py agree
    on what "already delivered" means): split the line on " | ", and
    accept it when

        parts[1] == f"{from_role}->{to_role}"
        parts[2] == str(handoff_id)
        parts[3] in ('dispatched', 'signal_complete',
                     'signal_complete_to_human')

    'dispatched' is signal-send (handoff dispatched to the next role);
    'signal_complete' is the callback injection; 'signal_complete_to_human'
    is the Human-targeted variant. Failed attempts (gate_rejected,
    signal_complete_failed, gate_rejection_undelivered) do NOT count
    — that matches dispatch.py.
    """
    direction = f"{from_role}->{to_role}"
    handoff_str = str(handoff_id)
    for line in trace_lines:
        parts = line.split(" | ")
        if len(parts) < 4:
            continue
        if parts[1] != direction or parts[2] != handoff_str:
            continue
        if parts[3] in (
            "dispatched", "signal_complete", "signal_complete_to_human",
        ):
            return True
    return False


def recover_orphaned_rows(
    conn: sqlite3.Connection, trace_path: str | None = None,
) -> int:
    """Requeue or complete orphaned 'processing' rows.

    A row in `bridge_dispatch_queue` with status='processing' is
    ORPHANED when its broker_pid is NULL or no live process owns that
    pid (os.kill(pid, 0) raises ProcessLookupError). For each orphaned
    row:

      - if `trace_path` (default `os.path.join(_get_bridge_dir(),
        'trace.log')`) already records a completed delivery of that
        exact transition (see `_trace_records_delivery`), mark the row
        status='completed' (set processed_at, clear claimed_at /
        broker_pid / error_msg);
      - otherwise REQUEUE it: status='pending', clear claimed_at /
        broker_pid / error_msg so the daemon re-claims it.

    Returns the count of rows recovered (requeued + completed) as an
    int. A PermissionError from os.kill (PID exists but not ours) is
    NOT an orphan — that row still has a live owner.

    Names and signature are bound by preferred_cloud_harness Run 006
    GOAL.md section 2 (D4); reviewers and criteria import this name.

    Called once at daemon startup (cmd_daemon) with the daemon's own
    DB connection.
    """
    if trace_path is None:
        trace_path = os.path.join(_get_bridge_dir(), "trace.log")
    try:
        with open(trace_path, "r", encoding="utf-8") as f:
            trace_lines = f.read().splitlines()
    except OSError:
        trace_lines = []

    rows = conn.execute(
        """
        SELECT id, flow_key, from_role, to_role, handoff_id,
               action, broker_pid
        FROM bridge_dispatch_queue
        WHERE status = 'processing'
        ORDER BY id ASC
        """,
    ).fetchall()

    recovered = 0
    for row in rows:
        pid = row["broker_pid"]
        is_orphan = pid is None
        if not is_orphan:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                is_orphan = True
            except PermissionError:
                # The PID exists; we just don't own it. Treat as live.
                is_orphan = False
            except OSError:
                # Any other OS-level failure to query the PID (e.g. on
                # exotic platforms) — treat defensively as an orphan
                # so the row does not stay stuck forever.
                is_orphan = True
        if not is_orphan:
            continue

        delivered = _trace_records_delivery(
            trace_lines, row["from_role"], row["to_role"],
            row["handoff_id"],
        )
        if delivered:
            conn.execute(
                """
                UPDATE bridge_dispatch_queue
                SET status = 'completed',
                    processed_at = datetime('now'),
                    claimed_at = NULL,
                    broker_pid = NULL,
                    error_msg = NULL
                WHERE id = ?
                """,
                (row["id"],),
            )
        else:
            conn.execute(
                """
                UPDATE bridge_dispatch_queue
                SET status = 'pending',
                    claimed_at = NULL,
                    broker_pid = NULL,
                    error_msg = NULL
                WHERE id = ?
                """,
                (row["id"],),
            )
        recovered += 1
    if recovered:
        conn.commit()
    return recovered


def cmd_daemon(args: argparse.Namespace) -> int:
    """Process pending rows forever (host-side deployment step).

    Polls both queues in priority order: materialize first, then
    signal transitions. Sleeps `interval` seconds when both queues
    are empty.

    Startup recovery (Run 006 D4): before the poll loop, run
    `recover_orphaned_rows` once on the daemon's own DB connection.
    Any `processing` row whose `broker_pid` is dead (or NULL) is
    either requeued (status='pending') or marked completed if the
    trace already records a delivery for that transition. Without
    this, a pre-delivery kill of the broker leaves the row stuck
    in 'processing' forever and silently loses the delivery (the
    live orphan was dispatch row 36, handoff 018, observed
    2026-08-21).
    """
    db_path = args.db_path or _get_db_path()
    conn = _open_db(db_path)
    _ensure_schema(conn)
    interval = max(0.5, float(args.interval))
    recovered = recover_orphaned_rows(conn)
    if recovered:
        print(
            f"bridge_broker: recovered {recovered} orphaned row(s) "
            f"at startup",
            file=sys.stderr,
        )
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
        help="Handoff id (required for handoff / escalation-response type).",
    )
    pm.add_argument(
        "--role", default=None, dest="role_key",
        help="Answering role key (required for escalation-response type).",
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
    pg = sub.add_parser(
        "promote-goal",
        help="Host-side: promote runs/NNN/GOAL-DRAFT.md to GOAL.md, "
             "recording who approved. The queue refuses type 'goal', so "
             "this is the only path to a promoted Run contract.",
    )
    pg.add_argument("--flow", required=True)
    pg.add_argument("--run-id", required=True)
    pg.add_argument("--approved-by", required=True)
    pg.set_defaults(func=cmd_promote_goal)

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
