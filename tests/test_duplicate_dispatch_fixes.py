"""Regression tests for the duplicate-prompt dispatch bugs (handoffs 309-313).

Two root causes are locked down here:

1. auto_prepend_xml_sections copied the convention content_template —
   including the <chain_advancement> prompt block with wrongly resolved
   placeholders ({next_role} -> source_role, {flow_run_id} -> "") — into
   deliverable files. The next role executed the embedded command verbatim
   and re-signaled as the WRONG role, looping duplicate prompts into
   review01/review02 (19 duplicates in 22 minutes for handoff 311).

2. Scheduler._advance_chain re-dispatched signal_complete on a wall-clock
   cooldown with no awareness of whether the target role was working.
   It must only nudge when a role demonstrably wrote its deliverable but
   never signaled (chain_watchdog semantics): trace-log recency, pane
   activity, deliverable age, and a persistent per-step nudge budget.
"""
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))
sys.path.insert(0, str(PROJECT_ROOT))

from job_queue.scheduler import Scheduler
from bridge_lib import auto_prepend_xml_sections
from dispatch import transition_recently_delivered


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _setup_jobs_db(tmp_path):
    db = str(tmp_path / "jq.db")
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY, workflow_run_id TEXT, flow_key TEXT NOT NULL,
            step_key TEXT, role_key TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'DRAFT',
            allocator_alias TEXT, handoff_id TEXT, idempotency_key TEXT UNIQUE,
            retry_count INTEGER DEFAULT 0, max_retries INTEGER DEFAULT 3,
            lease_owner TEXT, lease_expires_at TEXT, heartbeat_at TEXT,
            priority INTEGER DEFAULT 0, goal TEXT NOT NULL, target_project TEXT NOT NULL,
            scope_version TEXT, checkpoint_path TEXT, context_fit_state TEXT,
            parent_job_id TEXT, continuation_index INTEGER,
            created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS job_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL, event_type TEXT NOT NULL,
            from_state TEXT, to_state TEXT, actor TEXT, detail TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()
    return db


def _steps(base: Path):
    return [
        {"step_key": "s1", "from_role": "archi01", "to_role": "imple01",
         "deliverable_dir": str(base / "handoffs"), "deliverable_pattern": "{ID}-handoff.md"},
        {"step_key": "s2", "from_role": "imple01", "to_role": "review01",
         "deliverable_dir": str(base / "results"), "deliverable_pattern": "{ID}-result.md"},
        {"step_key": "s3", "from_role": "review01", "to_role": "review02",
         "deliverable_dir": str(base / "reviews"), "deliverable_pattern": "{ID}-review01.md"},
        {"step_key": "s4", "from_role": "review02", "to_role": "human",
         "deliverable_dir": str(base / "verdicts"), "deliverable_pattern": "{ID}-verdict.md"},
    ]


def _mk_sched(tmp_path):
    sched = Scheduler(db_path=_setup_jobs_db(tmp_path))
    sched.nudge_state_path = tmp_path / "nudge-state.json"
    sched.stall_minutes = 10
    sched.max_nudges = 2
    sched.fast_nudge_minutes = 2
    sched.idle_confirmations = 2
    return sched


def _job(hid="42"):
    return SimpleNamespace(job_id="JOB-TEST", flow_key="strict_review", handoff_id=hid)


def _write(path: Path, content="content", age_minutes=0.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if age_minutes:
        old = time.time() - age_minutes * 60
        os.utime(path, (old, old))


def _trace_line(bridge: Path, from_role, to_role, hid, event, age_minutes=0.0):
    from datetime import datetime, timezone, timedelta
    ts = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
    line = (f"{ts.strftime('%Y-%m-%dT%H:%M:%SZ')} | {from_role}->{to_role} | "
            f"{hid} | {event} | manual | test\n")
    bridge.mkdir(parents=True, exist_ok=True)
    with open(bridge / "trace.log", "a", encoding="utf-8") as f:
        f.write(line)


def _run_advance(sched, job, base, monkeypatch, pane_active=False,
                 active_sessions=None):
    """Run _advance_chain with tmux sessions named after their role keys.

    active_sessions: iterable of role keys whose panes show activity.
    pane_active=True is a legacy shorthand for "every pane is active".
    """
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", str(base))
    calls = []
    active = set(active_sessions or [])

    def fake_run(cmd, **kwargs):
        # Patching subprocess.run mutates the SHARED module, so tmux calls
        # from the stall wake-up (dispatch.inject_prompt) land here too.
        # These tests assert on signal-complete nudges only — filter tmux.
        if not (cmd and cmd[0] == "tmux"):
            calls.append(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    def fake_pane_active(self, session):
        return pane_active or session in active

    with patch("bridge_lib.load_flow_from_db",
               return_value={"steps": _steps(base)}), \
         patch("bridge_lib.load_role_from_db",
               side_effect=lambda rk, db_path=None: {"tmux_session": rk}), \
         patch.object(Scheduler, "_pane_active", new=fake_pane_active), \
         patch("job_queue.scheduler.subprocess.run", side_effect=fake_run):
        sched._advance_chain(job)
    return calls


# ---------------------------------------------------------------------------
# _advance_chain guards
# ---------------------------------------------------------------------------

def test_no_nudge_while_role_is_still_working(tmp_path, monkeypatch):
    """Missing next deliverable means the target role is (probably) working.

    imple01's result exists, review01's does not, but the review01->review02
    signal was delivered recently per trace.log — no re-dispatch allowed.
    """
    base = tmp_path / "bridge"
    sched = _mk_sched(tmp_path)
    _write(base / "handoffs" / "42-handoff.md", age_minutes=60)
    _write(base / "results" / "42-result.md", age_minutes=30)
    _trace_line(base, "archi01", "imple01", "42", "dispatched", age_minutes=60)
    _trace_line(base, "imple01", "review01", "42", "signal_complete", age_minutes=3)

    calls = _run_advance(sched, _job(), base, monkeypatch)
    assert calls == [], "must not re-dispatch while delivery is recent"


def test_no_nudge_when_target_pane_active(tmp_path, monkeypatch):
    """An active target pane means the role is working — never re-inject."""
    base = tmp_path / "bridge"
    sched = _mk_sched(tmp_path)
    _write(base / "handoffs" / "42-handoff.md", age_minutes=60)
    _write(base / "results" / "42-result.md", age_minutes=30)

    calls = _run_advance(sched, _job(), base, monkeypatch, pane_active=True)
    assert calls == []


def test_no_nudge_when_deliverable_is_fresh(tmp_path, monkeypatch):
    """A fresh deliverable means the role gets time to signal on its own."""
    base = tmp_path / "bridge"
    sched = _mk_sched(tmp_path)
    _write(base / "handoffs" / "42-handoff.md", age_minutes=60)
    _write(base / "results" / "42-result.md", age_minutes=1)

    calls = _run_advance(sched, _job(), base, monkeypatch)
    assert calls == []


def test_nudge_fires_for_stalled_step(tmp_path, monkeypatch):
    """Old deliverable + no trace + idle pane = the role forgot to signal."""
    base = tmp_path / "bridge"
    sched = _mk_sched(tmp_path)
    _write(base / "handoffs" / "42-handoff.md", age_minutes=90)
    _write(base / "results" / "42-result.md", age_minutes=30)

    calls = _run_advance(sched, _job(), base, monkeypatch)
    assert len(calls) == 1
    cmd = calls[0]
    assert "--signal-complete" in cmd
    assert cmd[cmd.index("--from-role") + 1] == "imple01"
    assert cmd[cmd.index("--id") + 1] == "42"


def test_nudge_budget_is_capped_and_persistent(tmp_path, monkeypatch):
    """At most max_nudges per (flow, id, step) — even across instances."""
    base = tmp_path / "bridge"
    sched = _mk_sched(tmp_path)
    _write(base / "handoffs" / "42-handoff.md", age_minutes=90)
    _write(base / "results" / "42-result.md", age_minutes=30)

    total = []
    total += _run_advance(sched, _job(), base, monkeypatch)
    total += _run_advance(sched, _job(), base, monkeypatch)
    total += _run_advance(sched, _job(), base, monkeypatch)

    # New instance, same state file — budget must survive restarts
    sched2 = _mk_sched(tmp_path)
    sched2.nudge_state_path = sched.nudge_state_path
    total += _run_advance(sched2, _job(), base, monkeypatch)

    assert len(total) == 2, f"expected exactly 2 nudges, got {len(total)}"


def test_only_own_handoff_id_is_considered(tmp_path, monkeypatch):
    """Files belonging to other handoff IDs must never trigger a dispatch."""
    base = tmp_path / "bridge"
    sched = _mk_sched(tmp_path)
    # Deliverables exist for id 99 — the job tracks id 42 (nothing written yet)
    _write(base / "handoffs" / "99-handoff.md", age_minutes=90)
    _write(base / "results" / "99-result.md", age_minutes=90)

    calls = _run_advance(sched, _job("42"), base, monkeypatch)
    assert calls == []


# ---------------------------------------------------------------------------
# Fast-path nudge: writer pane idle beats the 12-minute wall clock
# ---------------------------------------------------------------------------

def test_fast_nudge_after_writer_idle_confirmations(tmp_path, monkeypatch):
    """Deliverable past fast_nudge_minutes + writer pane idle on two
    consecutive ticks -> nudge fires long before stall_minutes."""
    base = tmp_path / "bridge"
    sched = _mk_sched(tmp_path)
    _write(base / "handoffs" / "42-handoff.md", age_minutes=60)
    _write(base / "results" / "42-result.md", age_minutes=3)  # < stall (10)

    first = _run_advance(sched, _job(), base, monkeypatch)
    assert first == [], "first idle observation must only count, not dispatch"

    second = _run_advance(sched, _job(), base, monkeypatch)
    assert len(second) == 1, "second consecutive idle observation dispatches"
    assert second[0][second[0].index("--from-role") + 1] == "imple01"


def test_no_fast_nudge_while_writer_pane_active(tmp_path, monkeypatch):
    """A writer that is still generating never triggers the fast path."""
    base = tmp_path / "bridge"
    sched = _mk_sched(tmp_path)
    _write(base / "handoffs" / "42-handoff.md", age_minutes=60)
    _write(base / "results" / "42-result.md", age_minutes=3)

    calls = []
    for _ in range(3):
        calls += _run_advance(sched, _job(), base, monkeypatch,
                              active_sessions=["imple01"])
    assert calls == []


def test_no_fast_nudge_below_min_age(tmp_path, monkeypatch):
    """The model gets fast_nudge_minutes to run its own signal first."""
    base = tmp_path / "bridge"
    sched = _mk_sched(tmp_path)
    _write(base / "handoffs" / "42-handoff.md", age_minutes=60)
    _write(base / "results" / "42-result.md", age_minutes=1)  # < fast (2)

    calls = []
    for _ in range(3):
        calls += _run_advance(sched, _job(), base, monkeypatch)
    assert calls == []


def test_writer_activity_resets_idle_confirmations(tmp_path, monkeypatch):
    """Idle -> active -> idle must restart the confirmation count."""
    base = tmp_path / "bridge"
    sched = _mk_sched(tmp_path)
    _write(base / "handoffs" / "42-handoff.md", age_minutes=60)
    _write(base / "results" / "42-result.md", age_minutes=3)

    assert _run_advance(sched, _job(), base, monkeypatch) == []
    assert _run_advance(sched, _job(), base, monkeypatch,
                        active_sessions=["imple01"]) == []
    assert _run_advance(sched, _job(), base, monkeypatch) == [], \
        "after a reset the first idle tick must only count again"
    assert len(_run_advance(sched, _job(), base, monkeypatch)) == 1


# ---------------------------------------------------------------------------
# signal_complete idempotency guard
# ---------------------------------------------------------------------------

def test_transition_recently_delivered(tmp_path):
    base = tmp_path / "bridge"
    _trace_line(base, "review01", "review02", "42", "signal_complete",
                age_minutes=3)

    assert transition_recently_delivered(
        str(base), "review01", "review02", "42", within_minutes=10) is True
    assert transition_recently_delivered(
        str(base), "review01", "review02", "42", within_minutes=2) is False, \
        "delivery older than the window must not count"
    assert transition_recently_delivered(
        str(base), "imple01", "review01", "42", within_minutes=10) is False
    assert transition_recently_delivered(
        str(base), "review01", "review02", "43", within_minutes=10) is False


def test_failed_signals_do_not_count_as_delivery(tmp_path):
    base = tmp_path / "bridge"
    _trace_line(base, "review01", "review02", "42", "signal_complete_failed",
                age_minutes=1)
    assert transition_recently_delivered(
        str(base), "review01", "review02", "42", within_minutes=10) is False


# ---------------------------------------------------------------------------
# LeaseRegistry: persistence across process boundaries + stop_model param
# ---------------------------------------------------------------------------

def test_lease_survives_process_boundary(tmp_path):
    """acquire() in one dispatch process must be visible to release() in the
    next — an in-memory-only lease made had_lease always False, so from-role
    models were never stopped at handoff (VRAM pile-up)."""
    from job_queue.model_lease import LeaseRegistry
    old_db = LeaseRegistry._db_path
    try:
        LeaseRegistry._db_path = str(tmp_path / "leases.db")
        LeaseRegistry.reset()
        with patch.object(LeaseRegistry, "_start_model"), \
             patch.object(LeaseRegistry, "_stop_model") as stop:
            LeaseRegistry.acquire("42", "alias-a")
            LeaseRegistry.reset()  # simulate a NEW dispatch process
            assert LeaseRegistry.release("42", "alias-a") is True
            stop.assert_called_once_with("alias-a")
    finally:
        LeaseRegistry._db_path = old_db
        LeaseRegistry.reset()


def test_lease_release_without_stop(tmp_path):
    """stop_model=False releases bookkeeping without unloading — for
    transitions where both aliases resolve to the same real model."""
    from job_queue.model_lease import LeaseRegistry
    old_db = LeaseRegistry._db_path
    try:
        LeaseRegistry._db_path = str(tmp_path / "leases.db")
        LeaseRegistry.reset()
        with patch.object(LeaseRegistry, "_start_model"), \
             patch.object(LeaseRegistry, "_stop_model") as stop:
            LeaseRegistry.acquire("42", "alias-a")
            LeaseRegistry.reset()
            assert LeaseRegistry.release("42", "alias-a", stop_model=False) is False
            stop.assert_not_called()
            assert LeaseRegistry.lease_count("alias-a") == 0, \
                "the lease row itself must be gone"
    finally:
        LeaseRegistry._db_path = old_db
        LeaseRegistry.reset()


# ---------------------------------------------------------------------------
# auto_prepend_xml_sections
# ---------------------------------------------------------------------------

POLLUTING_TEMPLATE = """<handoff_id>{handoff_id}</handoff_id>

<source_role>{source_role}</source_role>

<deliverable_input>
  {bridge_dir}/{flow_key}/results/{handoff_id}-result.md
</deliverable_input>

<deliverable_output>
  technical_review: {bridge_dir}/{flow_key}/reviews/{handoff_id}-review01.md
</deliverable_output>

<dispatch_command>
  escalation: python3 dispatch.py --db-flow {flow_key} --signal-escalation --from-role {next_role} --to-role archi01
</dispatch_command>
<chain_advancement>
Run this exact command:
    timeout 60 python3 dispatch.py --db-flow {flow_key} \\
      --signal-complete --from-role {next_role} --id {flow_run_id}
</chain_advancement>"""


def _conventions_db(tmp_path):
    db = str(tmp_path / "conv.db")
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE bridge_convention_rules (
            rule_key TEXT PRIMARY KEY, step_type TEXT NOT NULL,
            dir_template TEXT NOT NULL, pattern_template TEXT NOT NULL,
            error_template TEXT, prompt_template TEXT DEFAULT '',
            content_template TEXT, validation_schema TEXT,
            rule_type TEXT DEFAULT 'generic'
        )
    """)
    schema = json.dumps(["<handoff_id>", "<source_role>",
                         "<deliverable_input>", "<deliverable_output>"])
    conn.execute(
        "INSERT INTO bridge_convention_rules "
        "(rule_key, step_type, dir_template, pattern_template, "
        " content_template, validation_schema) VALUES (?,?,?,?,?,?)",
        ("technical_review", "review", "reviews", "{ID}-review01.md",
         POLLUTING_TEMPLATE, schema),
    )
    conn.commit()
    conn.close()
    return db


def test_auto_prepend_never_copies_prompt_material(tmp_path):
    """The deliverable header must not contain dispatch instructions."""
    db = _conventions_db(tmp_path)
    f = tmp_path / "42-result.md"
    f.write_text("## My review\nAll good.\n", encoding="utf-8")

    result = auto_prepend_xml_sections(
        str(f), "technical_review", "42", "imple01",
        "strict_review", str(tmp_path), db_path=db,
    )
    content = f.read_text(encoding="utf-8")

    assert result["prepended"] is True
    assert "<chain_advancement>" not in content
    assert "<dispatch_command>" not in content
    assert "--signal-complete" not in content
    assert "{" not in content.split("## My review")[0], \
        "no unresolved placeholders in the prepended header"


def test_auto_prepend_uses_correct_values_and_paths(tmp_path):
    db = _conventions_db(tmp_path)
    f = tmp_path / "42-result.md"
    f.write_text("## My review\n", encoding="utf-8")

    auto_prepend_xml_sections(
        str(f), "technical_review", "42", "imple01",
        "strict_review", str(tmp_path), db_path=db,
        input_path="/bridge/handoffs/42-handoff.md",
        output_path=str(f),
    )
    content = f.read_text(encoding="utf-8")

    assert "<handoff_id>42</handoff_id>" in content
    assert "<source_role>imple01</source_role>" in content
    assert "/bridge/handoffs/42-handoff.md" in content
    assert str(f) in content
    assert content.rstrip().endswith("## My review"), "original body preserved"


def test_auto_prepend_only_adds_missing_tags(tmp_path):
    db = _conventions_db(tmp_path)
    f = tmp_path / "42-result.md"
    f.write_text("<handoff_id>42</handoff_id>\n## My review\n", encoding="utf-8")

    auto_prepend_xml_sections(
        str(f), "technical_review", "42", "imple01",
        "strict_review", str(tmp_path), db_path=db,
    )
    content = f.read_text(encoding="utf-8")

    assert content.count("<handoff_id>") == 1, "existing tag must not be duplicated"
    assert "<source_role>imple01</source_role>" in content


# ---------------------------------------------------------------------------
# The idempotency guard is unbounded in time (preferred_cloud runs 004-005)
#
# The guard's own docstring said a transition happens at most once per handoff
# id — and then bounded it to ten minutes, which contradicts that rule. Four
# re-run signals landed at ~12.4 minutes, cleared the window, re-validated the
# handoff as a fresh deliverable, wrote an auto-prepended <deliverable> tag
# into it and injected it into a role already working on it. A fifth arrived
# nineteen minutes after its run had closed, aimed at a reviewer that would
# have overwritten an approved verdict.
# ---------------------------------------------------------------------------

def test_delivery_outside_the_old_window_is_still_a_duplicate(tmp_path):
    """12.4 minutes cleared the old 10-minute bound four times in one day."""
    base = tmp_path / "bridge"
    _trace_line(base, "Pre-super-cl", "Pre-imple-cl", "007", "dispatched",
                age_minutes=12.4)
    assert transition_recently_delivered(
        str(base), "Pre-super-cl", "Pre-imple-cl", "007") is True


def test_a_closed_runs_delivery_is_still_a_duplicate(tmp_path):
    """A stale signal for a closed run must not re-enter the chain."""
    base = tmp_path / "bridge"
    _trace_line(base, "Pre-imple-cl", "Pre-review-cl", "006", "signal_complete",
                age_minutes=17 * 60)
    assert transition_recently_delivered(
        str(base), "Pre-imple-cl", "Pre-review-cl", "006") is True


def test_a_gate_rejected_role_may_still_signal_again(tmp_path):
    """The rework path must survive the stricter guard.

    A rejection logs `gate_rejected`, not a delivery, so the implementer that
    rewrites its report can signal the same id again.
    """
    base = tmp_path / "bridge"
    _trace_line(base, "Pre-imple-cl", "Pre-review-cl", "005", "gate_rejected",
                age_minutes=30)
    assert transition_recently_delivered(
        str(base), "Pre-imple-cl", "Pre-review-cl", "005") is False


def test_an_explicit_window_is_still_honoured(tmp_path):
    """Callers that want a bound keep one; only the default changed."""
    base = tmp_path / "bridge"
    _trace_line(base, "review01", "review02", "42", "signal_complete",
                age_minutes=30)
    assert transition_recently_delivered(
        str(base), "review01", "review02", "42", within_minutes=10) is False
    assert transition_recently_delivered(
        str(base), "review01", "review02", "42") is True


def test_the_guard_still_distinguishes_roles_and_ids(tmp_path):
    """Field comparison, not substring — ids repeat across flows and eras."""
    base = tmp_path / "bridge"
    _trace_line(base, "Pre-super-cl", "Pre-imple-cl", "007", "dispatched",
                age_minutes=60)
    assert transition_recently_delivered(
        str(base), "Pre-imple-cl", "Pre-review-cl", "007") is False
    assert transition_recently_delivered(
        str(base), "Pre-super-cl", "Pre-imple-cl", "070") is False
