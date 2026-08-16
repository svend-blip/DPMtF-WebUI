"""signal_complete must refuse manual-dispatch-only steps (migration 054).

pi_test's fan-out defect, measured live on 2026-08-16 (handoffs
008/009/010): every oc_imple01 completion was followed seconds later by
a second, improvised `--signal-complete --from-role human`. On the
cyclic pi_test flow that resolves the FIRST step whose from_role is
'human' (human-pi_imple01) and re-injects the same handoff id into the
parallel implementer — a duplicate execution of a possibly
repository-mutating task, with both roles writing the same
{ID}-result.md.

Migration 054 adds bridge_flow_steps.auto_dispatch (NULL/1 = chain
delivery allowed, 0 = Human-initiated only) and opts pi_test's two
handoff steps out. The guard must fire BEFORE any session or
deliverable check — the refusal is the point, not a side effect of a
missing session.
"""

from __future__ import annotations

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


class _InjectionCaptured(Exception):
    """Raised by the patched injection seam to prove an injection fired."""


@pytest.fixture
def pi_test_env(tmp_path, monkeypatch):
    """Copy of the prod DB (which carries pi_test + migration 054) with
    every outbound seam patched. The bridge dir is a tmp_path."""
    db = tmp_path / "test.db"
    # sqlite backup, NOT shutil.copy: the prod DB runs WAL, and a raw
    # file copy misses everything still living in dpmtf.db-wal (this
    # bit twice on 2026-08-16 — a "pre-migration" copy that wasn't).
    src = sqlite3.connect(str(REAL_DB))
    dst = sqlite3.connect(str(db))
    src.backup(dst)
    dst.close()
    src.close()

    bridge = tmp_path / "bridge"
    (bridge / "pi_test" / "handoffs").mkdir(parents=True)
    (bridge / "pi_test" / "results").mkdir(parents=True)
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", str(bridge))

    captured = {}

    def _capture(session_name, text, **kwargs):
        captured["session"] = session_name
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

    models_mod = importlib.import_module("models")

    class _NoJobRepo:
        def __init__(self, *a, **k):
            raise RuntimeError("job DB blocked in tests")

    monkeypatch.setattr(models_mod, "JobRepository", _NoJobRepo)

    return SimpleNamespace(db=db, bridge=bridge, captured=captured)


def _step_flag(db, step_key):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            "SELECT auto_dispatch FROM bridge_flow_steps "
            "WHERE flow_key = 'pi_test' AND step_key = ?", (step_key,)
        ).fetchone()[0]
    finally:
        conn.close()


def test_migration_054_opted_the_pi_test_handoff_steps_out(pi_test_env):
    assert _step_flag(pi_test_env.db, "human-oc_imple01") == 0
    assert _step_flag(pi_test_env.db, "human-pi_imple01") == 0


def test_from_role_human_is_refused_before_any_injection(pi_test_env):
    """The exact improvised command shape from handoffs 008-010: a
    signal_complete carrying --from-role human resolves the
    human-pi_imple01 step, which is manual-dispatch only. The call must
    refuse (return False) and the injection seam must never fire — even
    though the deliverable exists and the session reads alive.
    """
    (pi_test_env.bridge / "pi_test" / "handoffs" / "999-handoff.md"
     ).write_text("<role>x</role>\n", encoding="utf-8")

    ok = dispatch.signal_complete(
        "pi_test", None, "human", "999",
        bridge_dir=str(pi_test_env.bridge))

    assert ok is False, (
        "signal_complete must refuse a manual-dispatch-only step"
    )
    assert "session" not in pi_test_env.captured, (
        "the handoff was injected into the parallel implementer — the "
        "fan-out the flag exists to stop"
    )


def test_default_steps_still_deliver(pi_test_env):
    """Control: oc_imple01's own completion step (auto_dispatch NULL)
    must behave exactly as before — the to-human delivery succeeds."""
    (pi_test_env.bridge / "pi_test" / "results" / "999-result.md"
     ).write_text("result\n", encoding="utf-8")

    ok = dispatch.signal_complete(
        "pi_test", None, "oc_imple01", "999",
        bridge_dir=str(pi_test_env.bridge))

    assert ok is True, (
        "a NULL auto_dispatch step must keep today's behavior"
    )
