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


def _run_advance(sched, job, base, monkeypatch, pane_active=False):
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", str(base))
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("bridge_lib.load_flow_from_db",
               return_value={"steps": _steps(base)}), \
         patch("bridge_lib.load_role_from_db",
               return_value={"tmux_session": "review01"}), \
         patch.object(Scheduler, "_pane_active", return_value=pane_active), \
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
