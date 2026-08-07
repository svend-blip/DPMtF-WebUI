"""SQLite-backed LightWorkerStore (routers/lightworkers.py).

Replaces the InMemoryStore that run 007 shipped beside
``routers/lightworkers.py``. The router does not change; the store
is a drop-in for the same ``LightWorkerStore`` interface, and the
§20 properties now hold across process restarts.

What a database gets wrong that a Python dict cannot:

* **Atomic claim across processes.** InMemoryStore gets this from the
  GIL. A real race needs one conditional ``UPDATE ... WHERE
  state = 'offered'`` whose ``rowcount`` decides. A read-then-write
  passes every single-process test and loses against three real
  processes claiming one execution.
* **State survives.** A new instance on the same file sees what the
  previous one recorded. That property is the entire point of this
  run.
* **Idempotent completion and failure per
  (execution_id, attempt_id)** now also across process boundaries.

What this store raises on:

* ``ExecutionAlreadyCompleted`` — a *different* attempt_id arrives
  for an execution that is already completed or failed. Run 007's
  ledger left this case open; the resolution lives here.

The schema is owned by ``scripts/db/030_lightworker_executions.sql``
and applied on construction so a fresh database bootstraps.
Several processes may do so concurrently; every statement is
``IF NOT EXISTS`` so the race is benign.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from routers.lightworkers import LightWorkerStore


# Marker for the two terminal states of an execution.
_TERMINAL_STATES = ("completed", "failed")

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "db"
    / "030_lightworker_executions.sql"
)


class ExecutionAlreadyCompleted(ValueError):
    """Raised when a different attempt_id reports completion or failure
    on an execution that is already in a terminal state.

    A subclass of ``ValueError`` so anything catching broadly still
    catches it. Named, so the mounting run can map it to a status
    code without matching on message text.
    """


# Lazy claim expiry -- the queue must heal itself.
#
# A claimed execution blocks every future offer to its worker (§5.3), and
# nothing timed it out: EXEC-013 jammed the queue until a human closed it
# through the API, and two supervisor mistakes earlier the same day each
# cost a full 30-minute wait for the same reason. The heartbeats built on
# 2026-08-07 are what make a timeout SAFE: without them a timeout kills
# live, slow executions along with dead ones.
#
# Two thresholds, because the silent phases differ:
# - An execution that has heartbeats beats every ~15s while its role runs.
#   Five minutes of silence is a dead worker, not a slow model.
# - Before the FIRST heartbeat lies the loud part of the §14 sequence --
#   mirror fetch, allocator preflight, model load. Loading the 35B took
#   minutes on svend3060, legitimately heartbeat-free. Fifteen minutes
#   covers it with margin.
CLAIM_STALE_WITH_HEARTBEATS_SECONDS = 300
CLAIM_GRACE_NO_HEARTBEAT_SECONDS = 900


class SqliteLightWorkerStore(LightWorkerStore):
    """SQLite implementation of the ``LightWorkerStore`` interface."""

    def __init__(self, db_path: str) -> None:
        # One required positional argument, no default. A default
        # pointing at ``config.get_db_path()`` would put an
        # accidental write to the live chain database one typo away.
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            db_path,
            timeout=30.0,
            isolation_level=None,  # autocommit; we drive transactions explicitly
            check_same_thread=False,
        )
        # Three processes may construct the store on one file at the
        # same moment in the race criterion; without a busy timeout
        # you get ``database is locked`` instead of an answer.
        self._conn.execute("PRAGMA busy_timeout = 30000")
        # WAL lets readers proceed while a writer holds the lock, and
        # concurrent connections tolerate each other better.
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA foreign_keys = ON")

        self._apply_schema()

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def _apply_schema(self) -> None:
        schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        self._conn.executescript(schema_sql)

    # ------------------------------------------------------------------
    # store-only seed (used by tests and, later, by the dispatcher)
    # ------------------------------------------------------------------

    def offer(self, execution: Dict[str, Any]) -> None:
        """Seed an execution addressed to ``execution['worker_id']``.

        ``execution`` is a single positional dict with at least
        ``execution_id``, ``worker_id`` and ``target_role``. The
        original payload is stored in ``payload_json`` so
        ``offer_next`` can return the exact fields the seed put in,
        the same shape ``InMemoryStore.offer`` provides.
        """
        execution_id = execution["execution_id"]
        worker_id = execution["worker_id"]
        target_role = execution["target_role"]
        handoff_id = execution.get("handoff_id")
        payload_json = json.dumps(execution, sort_keys=True)
        now = _now_iso()

        self._conn.execute(
            """
            INSERT INTO lightworker_executions (
                execution_id, handoff_id, worker_id, target_role,
                state, attempt_id, payload_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'offered', NULL, ?, ?, ?)
            """,
            (execution_id, handoff_id, worker_id, target_role,
             payload_json, now, now),
        )

    # ------------------------------------------------------------------
    # LightWorkerStore implementation
    # ------------------------------------------------------------------

    def register(self, worker_id: str, capabilities: Dict[str, Any]) -> None:
        capabilities_json = json.dumps(capabilities, sort_keys=True)
        self._conn.execute(
            """
            INSERT INTO lightworker_worker_state (
                worker_id, capabilities_json, heartbeat_at
            )
            VALUES (?, ?, ?)
            ON CONFLICT(worker_id) DO UPDATE SET
                capabilities_json = excluded.capabilities_json,
                heartbeat_at = excluded.heartbeat_at
            """,
            (worker_id, capabilities_json, _now_iso()),
        )

    def heartbeat(self, worker_id: str) -> None:
        # A heartbeat without a register is unusual but not invalid —
        # record the liveness if a row exists, ignore otherwise.
        self._conn.execute(
            """
            UPDATE lightworker_worker_state
               SET heartbeat_at = ?
             WHERE worker_id = ?
            """,
            (_now_iso(), worker_id),
        )

    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """The stored payload for one execution, or None.

        Read-only and outside `LightWorkerStore`: the router never needs it,
        but the return path does — a completion arrives with an id and Father
        has to find the envelope it was offered under to know where the
        deliverable belongs.
        """
        row = self._conn.execute(
            "SELECT payload_json FROM lightworker_executions WHERE execution_id = ?",
            (execution_id,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def _expire_stale_claims(self, worker_id: str) -> None:
        """Fail claimed executions whose worker has stopped proving life.

        Called from offer_next -- lazy expiry, deliberately: the moment the
        worker polls again is the moment the queue can safely unblock, and
        it needs no new daemon. A worker that never polls again blocks
        nobody's offers either; the chain-watchdog's CRITICAL line covers
        alerting the Human in that case.
        """
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        stale_cut = (now - timedelta(
            seconds=CLAIM_STALE_WITH_HEARTBEATS_SECONDS)).isoformat()
        grace_cut = (now - timedelta(
            seconds=CLAIM_GRACE_NO_HEARTBEAT_SECONDS)).isoformat()

        rows = self._conn.execute(
            """
            SELECT e.execution_id, e.attempt_id, e.updated_at,
                   (SELECT MAX(h.heartbeat_at)
                      FROM lightworker_execution_heartbeats h
                     WHERE h.execution_id = e.execution_id) AS last_beat
              FROM lightworker_executions e
             WHERE e.worker_id = ? AND e.state = 'claimed'
            """,
            (worker_id,),
        ).fetchall()
        for execution_id, attempt_id, updated_at, last_beat in rows:
            if last_beat is not None:
                if last_beat >= stale_cut:
                    continue
                why = (f"claim expired: last heartbeat {last_beat} is older "
                       f"than {CLAIM_STALE_WITH_HEARTBEATS_SECONDS}s")
            else:
                if updated_at >= grace_cut:
                    continue
                why = (f"claim expired: no heartbeat ever arrived and the "
                       f"claim from {updated_at} exceeded the "
                       f"{CLAIM_GRACE_NO_HEARTBEAT_SECONDS}s grace for the "
                       f"pre-heartbeat phase (mirror/preflight/model load)")
            try:
                self.fail(
                    execution_id,
                    worker_id,
                    attempt_id or "ATTEMPT-1",
                    {
                        "execution_id": execution_id,
                        "attempt_id": attempt_id or "ATTEMPT-1",
                        "category": "WORKER_INTERRUPTED",
                        "retryability": True,
                        "summary": ("Expired by Father, not reported by the "
                                    "worker: " + why),
                    },
                )
            except ExecutionAlreadyCompleted:
                pass    # someone else closed it between SELECT and fail

    def offer_next(self, worker_id: str) -> Optional[Dict[str, Any]]:
        self._expire_stale_claims(worker_id)
        # §5.3: max_parallel_executions == 1. A worker holding a
        # live execution is offered no second one. 'claimed' is the
        # only live state we treat as "the worker is holding this";
        # 'delivered' means handed out but not yet claimed, and the
        # worker is not yet committed, mirroring InMemoryStore's
        # ``self._live`` which is populated only on claim.
        live = self._conn.execute(
            """
            SELECT 1
              FROM lightworker_executions
             WHERE worker_id = ?
               AND state = 'claimed'
             LIMIT 1
            """,
            (worker_id,),
        ).fetchone()
        if live is not None:
            return None

        row = self._conn.execute(
            """
            SELECT execution_id, payload_json
              FROM lightworker_executions
             WHERE worker_id = ?
               AND state = 'offered'
             ORDER BY created_at ASC, execution_id ASC
             LIMIT 1
            """,
            (worker_id,),
        ).fetchone()

        if row is None:
            return None

        execution_id, payload_json = row
        # Move to 'delivered' so a concurrent offer_next on a
        # different store instance does not hand it out twice. The
        # where clause guarantees we only succeed while state is
        # still 'offered' — same rowcount trick as claim.
        cur = self._conn.execute(
            """
            UPDATE lightworker_executions
               SET state = 'delivered',
                   updated_at = ?
             WHERE execution_id = ?
               AND state = 'offered'
            """,
            (_now_iso(), execution_id),
        )
        if cur.rowcount != 1:
            # Lost the race against another process; try again next call.
            return None

        # Return the original payload, exactly as InMemoryStore does.
        payload = json.loads(payload_json)
        # Drop the private _status InMemoryStore adds; it never leaves
        # the store.
        payload.pop("_status", None)
        return payload

    def claim(self, execution_id: str, worker_id: str) -> bool:
        # The atomic claim is one conditional UPDATE. rowcount is
        # the answer — True iff it was 1. A read-then-write passes
        # every single-threaded test and loses the three-process race.
        #
        # Accept either 'offered' or 'delivered': a worker that
        # fetched the execution via offer_next sees it in 'delivered',
        # while a fast-path claim without a prior /next (the rare
        # case) sees it in 'offered'. Both are pre-claim states.
        cur = self._conn.execute(
            """
            UPDATE lightworker_executions
               SET state = 'claimed',
                   attempt_id = ?,
                   updated_at = ?
             WHERE execution_id = ?
               AND worker_id = ?
               AND state IN ('offered', 'delivered')
            """,
            (worker_id, _now_iso(), execution_id, worker_id),
        )
        return cur.rowcount == 1

    def execution_heartbeat(
        self, execution_id: str, worker_id: str, attempt_id: str
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO lightworker_execution_heartbeats (
                execution_id, worker_id, attempt_id, heartbeat_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(execution_id, worker_id, attempt_id)
                DO UPDATE SET heartbeat_at = excluded.heartbeat_at
            """,
            (execution_id, worker_id, attempt_id, _now_iso()),
        )

    def record_event(
        self, execution_id: str, worker_id: str, event: Dict[str, Any]
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO lightworker_events (
                execution_id, worker_id, event_json, created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (execution_id, worker_id,
             json.dumps(event, sort_keys=True), _now_iso()),
        )

    def complete(
        self,
        execution_id: str,
        worker_id: str,
        attempt_id: str,
        result: Dict[str, Any],
    ) -> bool:
        return self._record_terminal(
            execution_id=execution_id,
            worker_id=worker_id,
            attempt_id=attempt_id,
            payload=result,
            table="lightworker_completions",
            payload_column="result_json",
            terminal_state="completed",
        )

    def fail(
        self,
        execution_id: str,
        worker_id: str,
        attempt_id: str,
        failure: Dict[str, Any],
    ) -> bool:
        return self._record_terminal(
            execution_id=execution_id,
            worker_id=worker_id,
            attempt_id=attempt_id,
            payload=failure,
            table="lightworker_failures",
            payload_column="failure_json",
            terminal_state="failed",
        )

    def _record_terminal(
        self,
        *,
        execution_id: str,
        worker_id: str,
        attempt_id: str,
        payload: Dict[str, Any],
        table: str,
        payload_column: str,
        terminal_state: str,
    ) -> bool:
        # Single transaction so the state read and the row insert are
        # not separable across processes. SQLite's BEGIN IMMEDIATE
        # acquires the write lock before any statements run; that is
        # what makes the two halves atomic.
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                """
                SELECT state FROM lightworker_executions
                 WHERE execution_id = ?
                """,
                (execution_id,),
            ).fetchone()

            if row is None:
                self._conn.execute("ROLLBACK")
                return False

            state = row[0]

            if state in _TERMINAL_STATES:
                # The execution is finished. The run-007 resolution:
                # a different attempt_id is refused loudly. A replay of
                # the same attempt_id is idempotent — INSERT OR IGNORE
                # tells us whether the row was new.
                existing = self._conn.execute(
                    f"""
                    SELECT attempt_id FROM {table}
                     WHERE execution_id = ?
                    """,
                    (execution_id,),
                ).fetchone()
                self._conn.execute("ROLLBACK")

                if existing is None:
                    # No row in this terminal table — the *other*
                    # terminal table holds the answer. A complete
                    # arriving on a failed execution, or vice versa,
                    # is the run-007 case.
                    raise ExecutionAlreadyCompleted(
                        f"execution {execution_id!r} is already in a "
                        f"terminal state ({state!r}); refusing "
                        f"attempt_id={attempt_id!r}"
                    )

                if existing[0] == attempt_id:
                    return False

                raise ExecutionAlreadyCompleted(
                    f"execution {execution_id!r} is already "
                    f"{state!r} for attempt_id={existing[0]!r}; "
                    f"refusing attempt_id={attempt_id!r}"
                )

            # INSERT OR IGNORE — the UNIQUE constraint enforces
            # idempotency per (execution_id, attempt_id). rowcount is
            # 1 if the row was new, 0 if it already existed.
            insert_sql = f"""
                INSERT OR IGNORE INTO {table} (
                    execution_id, attempt_id, worker_id, {payload_column}, created_at
                )
                VALUES (?, ?, ?, ?, ?)
            """
            cur = self._conn.execute(
                insert_sql,
                (execution_id, attempt_id, worker_id,
                 json.dumps(payload, sort_keys=True), _now_iso()),
            )

            if cur.rowcount == 1:
                # Move the execution to its terminal state.
                self._conn.execute(
                    """
                    UPDATE lightworker_executions
                       SET state = ?,
                           attempt_id = ?,
                           updated_at = ?
                     WHERE execution_id = ?
                    """,
                    (terminal_state, attempt_id, _now_iso(), execution_id),
                )
                self._conn.execute("COMMIT")
                return True

            # Same attempt_id already recorded — replay.
            self._conn.execute("ROLLBACK")
            return False
        except Exception:
            try:
                self._conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise

    def completion_count(self, execution_id: str, attempt_id: str) -> int:
        return self._terminal_count(
            "lightworker_completions", execution_id, attempt_id
        )

    def failure_count(self, execution_id: str, attempt_id: str) -> int:
        return self._terminal_count(
            "lightworker_failures", execution_id, attempt_id
        )

    def _terminal_count(
        self, table: str, execution_id: str, attempt_id: str
    ) -> int:
        row = self._conn.execute(
            f"""
            SELECT COUNT(*) FROM {table}
             WHERE execution_id = ? AND attempt_id = ?
            """,
            (execution_id, attempt_id),
        ).fetchone()
        return int(row[0]) if row else 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()