"""signal_send honours the idempotency guard: one delivery per (transition, id).

Measured 2026-09-01 on flow 9000-02-ELOOP, handoff 4: the implementer ran
its signal-send twice, the broker processed both, and the reviewer's pane
received the same result prompt twice — the second executing the whole
review again after the first finished. signal_complete has refused that
since preferred_cloud run 005; signal_send now does the same.
"""
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import dispatch  # noqa: E402


def _trace_line(base, from_role, to_role, hid, event, age_minutes=1):
    base.mkdir(parents=True, exist_ok=True)
    ts = (datetime.now(timezone.utc) - timedelta(minutes=age_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(base / "trace.log", "a", encoding="utf-8") as f:
        f.write(f"{ts} | {from_role}->{to_role} | {hid} | {event} | manual | x\n")


def _arm(monkeypatch, base):
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", str(base))
    monkeypatch.setattr(dispatch, "_bridge_dir", lambda: str(base))
    monkeypatch.setattr(dispatch, "load_role_from_db",
                        lambda key, db_path=None: {"role_key": key, "tmux_session": key,
                                                   "role_type": "agent"})

    def _never(*a, **k):
        raise AssertionError("delivery path must not be reached")
    monkeypatch.setattr(dispatch, "session_alive", _never)


def test_second_signal_send_for_a_delivered_handoff_is_suppressed(tmp_path, monkeypatch):
    base = tmp_path / "bridge"
    _trace_line(base, "9000-implementer", "9000-reviewer", "4", "dispatched")
    _arm(monkeypatch, base)
    assert dispatch.signal_send("9000-02-ELOOP", "9000-implementer", "9000-reviewer", "4",
                                bridge_dir=str(base)) is True
    lines = (base / "trace.log").read_text().splitlines()
    assert lines[-1].split(" | ")[3] == "send_skipped"
    assert "Duplicate delivery suppressed" in lines[-1]


def test_send_failed_does_not_block_a_retry(tmp_path, monkeypatch):
    base = tmp_path / "bridge"
    _trace_line(base, "9000-execution-decomposer", "9000-implementer", "4", "send_failed")
    _arm(monkeypatch, base)
    # The delivery path IS reached (session_alive is the first step of it),
    # which is the retry going through — the guard did not stop it.
    try:
        dispatch.signal_send("9000-02-ELOOP", "9000-execution-decomposer", "9000-implementer", "4",
                             bridge_dir=str(base))
    except AssertionError as exc:
        assert "delivery path must not be reached" in str(exc)
    else:
        raise AssertionError("expected the delivery path to be reached")


def test_force_bypasses_the_guard(tmp_path, monkeypatch):
    base = tmp_path / "bridge"
    _trace_line(base, "9000-implementer", "9000-reviewer", "4", "dispatched")
    _arm(monkeypatch, base)
    try:
        dispatch.signal_send("9000-02-ELOOP", "9000-implementer", "9000-reviewer", "4",
                             bridge_dir=str(base), force=True)
    except AssertionError as exc:
        assert "delivery path must not be reached" in str(exc)
    else:
        raise AssertionError("expected --force to reach the delivery path")
