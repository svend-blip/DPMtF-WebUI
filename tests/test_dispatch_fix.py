"""Regression tests for cyclic-flow final-step prompt composition (H324/H325).

In cyclic flows (supervised_review: supervisor_auto -> imple01 -> review01
-> review02 -> supervisor_auto) dispatch.py resolved "the target role's next
step" by scanning ALL steps for from_role == target role. When the FINAL
step completed, that scan matched step 1 again, so the woken supervisor was
told to (1) write its result to the ORIGINAL handoffs/{ID}-handoff.md and
(2) run signal-complete with the SAME id — re-dispatching step 1 in an
infinite loop (observed in supervisor run smoke-001, 2026-07-28).

The lookup must be position-aware: only steps strictly AFTER the current
step in sort order qualify as "next". On the last step nothing follows, so
no "Your Deliverable" / "Signal Completion" block may be appended — the
agent_delivery content template alone defines the wake-up behavior.

These tests call dispatch.py's REAL signal_complete()/signal_send() against
a temp copy of the production DB extended with a synthetic cyclic flow
('cyclic_test', relative deliverable dirs under a temp bridge dir). The
tmux injection seam is monkeypatched to capture the composed prompt and
abort before any post-dispatch side effects (checkpoints, job DB, symlinks).
"""
import importlib
import shutil
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "job_queue"))
sys.path.insert(0, str(PROJECT_ROOT))

import dispatch

REAL_DB = PROJECT_ROOT / "databases" / "dpmtf.db"
FLOW = "cyclic_test"
HID = "77"
SUBDIRS = {1: "handoffs", 2: "results", 3: "reviews", 4: "verdicts"}


class _InjectionCaptured(Exception):
    """Raised by the patched injection seam to stop after prompt build."""


def _xml_header(source_role, input_path):
    return (
        f"<handoff_id>{HID}</handoff_id>\n"
        f"<source_role>{source_role}</source_role>\n"
        f"<deliverable_input>\n  {input_path}\n</deliverable_input>\n"
        f"<deliverable_output>\n  result: (test)\n</deliverable_output>\n"
        # signal_send validates these sections for non-json_output rules:
        f"<role>test role</role>\n<task>test task</task>\n"
        f"<constraint>test constraint</constraint>\n"
    )


@pytest.fixture
def cyclic_env(tmp_path, monkeypatch):
    """Temp DB (copy of prod + synthetic cyclic flow) and patched seams."""
    db = tmp_path / "test.db"
    shutil.copy(REAL_DB, db)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    flow_row = dict(conn.execute(
        "SELECT * FROM bridge_flows WHERE flow_key = ?",
        ("supervised_review",)).fetchone())
    flow_row["flow_key"] = FLOW
    cols = ", ".join(flow_row)
    ph = ", ".join("?" * len(flow_row))
    conn.execute(f"INSERT INTO bridge_flows ({cols}) VALUES ({ph})",
                 list(flow_row.values()))
    for row in conn.execute(
            "SELECT * FROM bridge_flow_steps WHERE flow_key = ? "
            "ORDER BY sort_order", ("supervised_review",)).fetchall():
        step = dict(row)
        step.pop("id")
        step["flow_key"] = FLOW
        step["deliverable_dir"] = SUBDIRS[step["sort_order"]]
        cols = ", ".join(step)
        ph = ", ".join("?" * len(step))
        conn.execute(f"INSERT INTO bridge_flow_steps ({cols}) VALUES ({ph})",
                     list(step.values()))
    conn.execute(
        "INSERT OR REPLACE INTO bridge_id_counters (flow_key, next_id) "
        "VALUES (?, 1000)", (FLOW,))
    conn.commit()
    conn.close()

    bridge = tmp_path / "bridge"
    for sub in SUBDIRS.values():
        (bridge / sub).mkdir(parents=True)
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", str(bridge))

    captured = {}

    def _capture(session_name, text, **kwargs):
        captured["session"] = session_name
        captured["prompt"] = text
        raise _InjectionCaptured()

    monkeypatch.setattr(dispatch, "_db_path", lambda: str(db))
    monkeypatch.setattr(dispatch, "session_alive", lambda s: True)
    monkeypatch.setattr(dispatch, "inject_prompt", _capture)
    monkeypatch.setattr(dispatch, "log", lambda *a, **k: None)
    monkeypatch.setattr(dispatch, "get_effective_model_source",
                        lambda *a, **k: ("", ""))
    monkeypatch.setattr(dispatch, "_run_allocator_start", lambda *a, **k: True)
    monkeypatch.setattr(dispatch, "_run_allocator_stop", lambda *a, **k: True)
    monkeypatch.setattr(dispatch, "_release_from_model_first",
                        lambda *a, **k: False)
    monkeypatch.setattr(dispatch, "append_trade_mcp_context",
                        lambda prompt, *a, **k: prompt)

    # Job records must never touch the real job DB from tests.
    models_mod = importlib.import_module("models")

    class _NoJobRepo:
        def __init__(self, *a, **k):
            raise RuntimeError("job DB blocked in tests")

    monkeypatch.setattr(models_mod, "JobRepository", _NoJobRepo)

    return SimpleNamespace(db=db, bridge=bridge, captured=captured)


def test_s1_final_step_callback_has_no_signal_block(cyclic_env):
    """S1: completing the LAST step must not tell the woken agent to write a
    chain deliverable or to signal-complete — that loops the chain."""
    verdict = cyclic_env.bridge / "verdicts" / f"{HID}-verdict.md"
    verdict.write_text(
        _xml_header("review02", "(review input)") + "\n## Verdict\nAPPROVED\n",
        encoding="utf-8")

    with pytest.raises(_InjectionCaptured):
        dispatch.signal_complete(FLOW, None, "review02", HID,
                                 bridge_dir=str(cyclic_env.bridge))

    prompt = cyclic_env.captured["prompt"]
    assert "Signal Completion" not in prompt
    assert "--signal-complete" not in prompt
    assert f"{HID}-handoff.md" not in prompt
    assert "Your Deliverable" not in prompt
    # The convention content template must still be delivered.
    assert f"handoff {HID}" in prompt


def test_s2_mid_chain_callback_keeps_deliverable_and_signal(cyclic_env):
    """S2 (regression guard): mid-chain steps keep today's behavior —
    deliverable path, XML header requirement, and the mandatory signal."""
    result = cyclic_env.bridge / "results" / f"{HID}-result.md"
    result.write_text(
        _xml_header("imple01", "(handoff input)") + "\n## Summary\ndone\n",
        encoding="utf-8")

    with pytest.raises(_InjectionCaptured):
        dispatch.signal_complete(FLOW, None, "imple01", HID,
                                 bridge_dir=str(cyclic_env.bridge))

    prompt = cyclic_env.captured["prompt"]
    assert "Your Deliverable" in prompt
    assert "Signal Completion" in prompt
    assert "--signal-complete" in prompt
    assert "--from-role review01" in prompt
    assert f"--id {HID}" in prompt
    # review01's own deliverable (next step's file), not the original handoff:
    assert f"{HID}-review01.md" in prompt
    assert f"<handoff_id>{HID}</handoff_id>" in prompt


def test_s3_signal_send_final_step_has_no_signal_block(cyclic_env):
    """S3: signal_send on the final step (the scheduler's stall wake-up
    shape) must not append a mandatory-signal block with the same id."""
    verdict = cyclic_env.bridge / "verdicts" / f"{HID}-verdict.md"
    verdict.write_text(
        _xml_header("review02", "(review input)") + "\n## Verdict\nAPPROVED\n",
        encoding="utf-8")

    with pytest.raises(_InjectionCaptured):
        dispatch.signal_send(FLOW, "review02", "supervisor_auto", HID,
                             bridge_dir=str(cyclic_env.bridge))

    prompt = cyclic_env.captured["prompt"]
    assert "Signal Completion" not in prompt
    assert "--signal-complete" not in prompt
    assert f"{HID}-handoff.md" not in prompt
    assert "Your Deliverable" not in prompt


def test_s2b_signal_send_mid_chain_keeps_signal_block(cyclic_env):
    """S2b (regression guard): signal_send on step 1 still gives the target
    its own deliverable path and mandatory signal command."""
    handoff = cyclic_env.bridge / "handoffs" / f"{HID}-handoff.md"
    handoff.write_text(
        _xml_header("supervisor_auto", "(goal)") + "\n## Task\ndo it\n",
        encoding="utf-8")

    with pytest.raises(_InjectionCaptured):
        dispatch.signal_send(FLOW, "supervisor_auto", "imple01", HID,
                             bridge_dir=str(cyclic_env.bridge))

    prompt = cyclic_env.captured["prompt"]
    assert "Your Deliverable" in prompt
    assert "Signal Completion" in prompt
    assert "--from-role imple01" in prompt
    assert f"{HID}-result.md" in prompt
