"""Tests for delivery-truthfulness (preferred_cloud_harness Run 032 D1).

On 2026-08-24 a handoff prompt was typed into a live bash login shell
because dispatch injected into a tmux pane whose HARNESS process had
died. ``dispatch.session_alive`` only checks the tmux container — not
its contents. Run 032 D1 binds a new ``dispatch.harness_alive``
predicate that verifies the receiver's harness is still alive and
makes BOTH the injection path AND the verify_injection_submitted Enter
fallback REFUSE when it is not.

This file pins D1's behaviour. It is hermetic: no live database, no
live tmux session, no live trace.log, no live subprocess — every
external probe is routed through a seam the test installs.

Testgoals:
- TG1 (``dispatch.harness_alive`` exists) is covered by the module
  attribute smoke test.
- TG3 (injection refuses when no harness is alive) is covered by the
  ``-k "no_harness"`` selection — the named tests assert that
  ``signal_send`` / ``run_flow_step_db`` and the Enter fallback all
  refuse when harness_alive returns False, and that no send-keys /
  paste-buffer happens.

Required cases (handoff 107 §4):
  (a) harness_alive is True when the anchor pid is live;
  (b) harness_alive is False when the anchor pid is NULL or dead
      (the "no_harness" case);
  (c) harness_alive is True when no anchor row exists (non-harness
      role);
  (d) injection REFUSES (no send-keys/paste-buffer; a
      failed/send_failed result) when harness_alive is False;
  (e) the Enter fallback does NOT send Enter when harness_alive is
      False.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Make the bridgeV002 package importable.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts" / "bridgeV002"))

import dispatch as _dispatch  # noqa: E402


# ── Helpers ─────────────────────────────────────────────────────


class _FakeTmuxRun:
    """Mock for dispatch.subprocess.run that simulates a tmux session.

    Records every tmux call so tests can assert which side-effects
    happened. The pane tail (returned by `tmux capture-pane`) is
    configurable per test via `set_pane_tail`. tmux has-session
    returns 0 by default; override ``session_alive_rc`` to force
    the session_alive check to fail.
    """

    def __init__(self) -> None:
        self.pane_tail = ""
        self.calls: list[list[str]] = []
        self.session_alive_rc = 0  # 0 == session alive
        self.has_session_stdout = ""

    def set_pane_tail(self, tail: str) -> None:
        self.pane_tail = tail

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        # `tmux has-session` -> session_alive check.
        if cmd and cmd[0] == "tmux" and "has-session" in cmd:
            return subprocess.CompletedProcess(
                cmd, self.session_alive_rc,
                stdout=self.has_session_stdout, stderr="",
            )
        # `tmux capture-pane` returns the configured tail.
        if cmd and cmd[0] == "tmux" and "capture-pane" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=self.pane_tail, stderr="",
            )
        # `tmux list-panes` returns "unknown" (no special tool).
        if cmd and cmd[0] == "tmux" and "list-panes" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="unknown", stderr="",
            )
        # Everything else (send-keys, load-buffer, paste-buffer) is a
        # successful no-op.
        return subprocess.CompletedProcess(
            cmd, 0, stdout="", stderr="",
        )


def _send_keys_calls(fake: _FakeTmuxRun) -> list[list[str]]:
    return [c for c in fake.calls if c and c[0] == "tmux"
            and "send-keys" in c]


def _paste_buffer_calls(fake: _FakeTmuxRun) -> list[list[str]]:
    return [c for c in fake.calls if c and c[0] == "tmux"
            and ("paste-buffer" in c or "load-buffer" in c)]


def _load_buffer_calls(fake: _FakeTmuxRun) -> list[list[str]]:
    return [c for c in fake.calls if c and c[0] == "tmux"
            and "load-buffer" in c]


def _build_minimal_bridge_db(db_path: str) -> None:
    """Create the minimum bridge schema for signal_send / run_flow_step_db."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS bridge_roles (
                role_key TEXT PRIMARY KEY,
                tmux_session TEXT NOT NULL,
                start_cmd TEXT,
                setup_script TEXT,
                teardown_script TEXT,
                deliver_error_msg TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                restart_policy TEXT,
                governance_file TEXT,
                role_type TEXT DEFAULT 'agent',
                enter_command TEXT DEFAULT 'default',
                config_dir TEXT,
                primary_output_type TEXT,
                default_model_source TEXT,
                default_model_alias TEXT,
                trade_mcp_push_mode TEXT,
                max_output_tokens INTEGER
            );
            CREATE TABLE IF NOT EXISTS bridge_flows (
                flow_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                step_order TEXT,
                is_default INTEGER DEFAULT 0,
                use_machine_profile INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                auto_complete_enabled INTEGER DEFAULT 0,
                target_project_path TEXT DEFAULT NULL,
                implementation_mode TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS bridge_flow_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_key TEXT NOT NULL,
                step_key TEXT NOT NULL,
                from_role TEXT NOT NULL,
                to_role TEXT NOT NULL,
                deliverable_dir TEXT,
                deliverable_pattern TEXT,
                pre_dispatch_script TEXT,
                post_dispatch_script TEXT,
                error_msg TEXT,
                sort_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                rule_key TEXT,
                auto_chain_to_next INTEGER DEFAULT 0,
                validation_required INTEGER DEFAULT 0,
                model_source TEXT,
                model_alias TEXT,
                auto_dispatch INTEGER DEFAULT NULL,
                FOREIGN KEY (flow_key) REFERENCES bridge_flows(flow_key),
                UNIQUE(flow_key, step_key)
            );
            CREATE TABLE IF NOT EXISTS flow_runtime_resources (
                flow_key TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                pid INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (flow_key, resource_type, resource_id)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


# ── TG1: harness_alive exists at the module level ──────────────


def test_harness_alive_module_attribute_present() -> None:
    """TG1 (GOAL.md §4): dispatch exposes a harness-liveness predicate.

    Reads the resolved module attribute so the bound name is enforced.
    """
    assert hasattr(_dispatch, "harness_alive")
    assert callable(_dispatch.harness_alive)


# ── (a) harness_alive True when anchor pid is live ──────────────


def test_harness_alive_returns_true_when_anchor_pid_is_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case (a): an anchor row exists with a live pid → True.

    The pid probe is the monkeypatched seam; this test does not spawn
    any process. ``os.kill(pid, 0)`` semantics are pinned in the
    _default_pid_alive helper.
    """
    pid_seen: list[int] = []

    def fake_pid_alive(pid):
        pid_seen.append(pid)
        return True

    def fake_load_role(role_name, db_path=None):
        return {"role_key": role_name,
                "tmux_session": "review-claude-sonnet5-session"}

    def fake_list_anchors(flow_key, db_path=None):
        return [{"flow_key": flow_key,
                 "resource_type": "harness_process",
                 "resource_id": "review-claude-sonnet5-session",
                 "pid": 12345}]

    monkeypatch.setattr(_dispatch, "_default_pid_alive", fake_pid_alive)
    monkeypatch.setattr(_dispatch, "_default_load_role", fake_load_role)
    monkeypatch.setattr(_dispatch,
                        "_default_list_harness_anchors", fake_list_anchors)

    assert _dispatch.harness_alive("preferred_cloud_harness",
                                   "review-claude-sonnet5") is True
    assert pid_seen == [12345]


# ── (b) harness_alive False when anchor pid is dead or NULL ─────


def test_harness_alive_returns_false_when_anchor_pid_is_dead_no_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case (b) — the "no_harness" case (TG3 selection): a dead anchor
    pid must read False so the injection path refuses to paste into
    the pane (the 2026-08-24 failure mode)."""

    def fake_pid_alive(pid):
        return False  # os.kill would have raised ProcessLookupError

    monkeypatch.setattr(_dispatch, "_default_pid_alive", fake_pid_alive)
    monkeypatch.setattr(_dispatch, "_default_load_role",
                        lambda role_name, db_path=None: {
                            "role_key": role_name,
                            "tmux_session": "review-claude-sonnet5-session",
                        })
    monkeypatch.setattr(_dispatch,
                        "_default_list_harness_anchors",
                        lambda flow_key, db_path=None: [{
                            "flow_key": flow_key,
                            "resource_type": "harness_process",
                            "resource_id": "review-claude-sonnet5-session",
                            "pid": 99999,
                        }])

    assert _dispatch.harness_alive("preferred_cloud_harness",
                                   "review-claude-sonnet5") is False


def test_harness_alive_returns_false_when_anchor_pid_is_null_no_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case (b) — NULL anchor pid variant: an anchor row whose pid
    column is NULL also fails the liveness check (a recorded claim
    with no live process to back it)."""

    def fail_if_called(pid):
        raise AssertionError(
            "_pid_alive must NOT be called when the anchor pid is NULL "
            "(the NULL value already means 'no live process')")

    monkeypatch.setattr(_dispatch, "_default_pid_alive", fail_if_called)
    monkeypatch.setattr(_dispatch, "_default_load_role",
                        lambda role_name, db_path=None: {
                            "role_key": role_name,
                            "tmux_session": "review-claude-sonnet5-session",
                        })
    monkeypatch.setattr(_dispatch,
                        "_default_list_harness_anchors",
                        lambda flow_key, db_path=None: [{
                            "flow_key": flow_key,
                            "resource_type": "harness_process",
                            "resource_id": "review-claude-sonnet5-session",
                            "pid": None,
                        }])

    assert _dispatch.harness_alive("preferred_cloud_harness",
                                   "review-claude-sonnet5") is False


def test_harness_alive_returns_false_when_role_row_missing_no_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown role key (the role row cannot be loaded) returns
    False — a misconfigured flow must not auto-inject."""

    def fake_load_role(role_name, db_path=None):
        raise ValueError(f"Active role '{role_name}' not found in bridge_roles")

    list_calls: list[str] = []

    def fake_list_anchors(flow_key, db_path=None):
        list_calls.append(flow_key)
        return []

    monkeypatch.setattr(_dispatch, "_default_load_role", fake_load_role)
    monkeypatch.setattr(_dispatch,
                        "_default_list_harness_anchors", fake_list_anchors)

    assert _dispatch.harness_alive("preferred_cloud_harness",
                                   "ghost-role") is False
    # The anchor reader must NOT be consulted when the role is unknown.
    assert list_calls == []


# ── (c) harness_alive True when no anchor row exists ───────────


def test_harness_alive_returns_true_when_no_anchor_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case (c): no harness_process anchor row exists → True.

    This is REQUIRED so the shared dispatch.py does not break the
    parallel preferred_cloud flow and the model_allocator / opencode
    roles that have no harness_process anchor (Run 032 GOAL.md §1 D1).
    """
    pid_calls: list[int] = []

    def fake_pid_alive(pid):
        pid_calls.append(pid)
        return True

    monkeypatch.setattr(_dispatch, "_default_pid_alive", fake_pid_alive)
    monkeypatch.setattr(_dispatch, "_default_load_role",
                        lambda role_name, db_path=None: {
                            "role_key": role_name,
                            "tmux_session": "some-session",
                        })
    # No anchor rows at all — simulates a non-harness role / a
    # parallel flow that does not write to flow_runtime_resources.
    monkeypatch.setattr(_dispatch,
                        "_default_list_harness_anchors",
                        lambda flow_key, db_path=None: [])

    assert _dispatch.harness_alive("preferred_cloud",
                                   "non-harness-role") is True
    # The proc probe is NOT called when no anchor row exists.
    assert pid_calls == []


# ── (d) injection REFUSES when harness_alive is False ───────────


def test_signal_send_no_harness_refuses_injection_no_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case (d) — the "no_harness" case: signal_send returns False and
    does NOT send-keys / paste-buffer / load-buffer when the receiver's
    harness is dead. A ``send_failed`` log entry is written.

    Uses a fully-populated temp DB and patches every external seam:
    no live tmux, no live DB, no live trace.log, no live model allocator.
    """
    db_path = str(tmp_path / "truth.db")
    _build_minimal_bridge_db(db_path)

    # Seed the role + flow + step rows signal_send needs.
    flow_key = "preferred_cloud_harness"
    from_role = "supervisor_super"
    to_role = "imple-codex-minimaxM3"
    deliverable_dir = "handoffs"
    handoff_file = "999-handoff.md"
    flow_dir = tmp_path / flow_key
    handoff_subdir = flow_dir / deliverable_dir
    handoff_subdir.mkdir(parents=True)
    handoff_path = handoff_subdir / handoff_file
    handoff_path.write_text(
        "<role>Implementer</role>\n"
        "<task>Do the thing.</task>\n"
        "<constraint>Follow governance.</constraint>\n",
        encoding="utf-8",
    )

    # bridge_dir points under tmp_path so trace.log and similar are
    # hermetic. signal_send resolves bridge_dir via env / config.
    bridge_dir = str(flow_dir)
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", bridge_dir)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO bridge_roles
                (role_key, tmux_session, is_active, role_type,
                 enter_command, default_model_source, default_model_alias)
            VALUES (?, ?, 1, 'agent', 'default', 'model_allocator', 'a')
            """,
            (from_role, f"{from_role}-session"),
        )
        conn.execute(
            """
            INSERT INTO bridge_roles
                (role_key, tmux_session, is_active, role_type,
                 enter_command, default_model_source, default_model_alias)
            VALUES (?, ?, 1, 'agent', 'default', 'model_allocator', 'b')
            """,
            (to_role, f"{to_role}-session"),
        )
        conn.execute(
            """
            INSERT INTO bridge_flows (flow_key, name, is_active)
            VALUES (?, ?, 1)
            """,
            (flow_key, "preferred_cloud_harness"),
        )
        conn.execute(
            """
            INSERT INTO bridge_flow_steps
                (flow_key, step_key, from_role, to_role,
                 deliverable_dir, deliverable_pattern,
                 rule_key, sort_order, is_active, validation_required)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 0)
            """,
            (flow_key, "imple01", from_role, to_role,
             str(Path(bridge_dir) / flow_key / deliverable_dir),
             "{ID}-handoff.md", "json_output"),
        )
        conn.commit()
    finally:
        conn.close()

    # Pin _db_path() to the temp DB.
    monkeypatch.setattr(_dispatch, "_db_path", lambda: db_path)

    # Pin session_alive to True (so we reach the harness_alive check).
    monkeypatch.setattr(_dispatch, "session_alive", lambda s: True)

    # Pin harness_alive to False — the dead-harness scenario.
    monkeypatch.setattr(_dispatch, "harness_alive",
                        lambda flow, role, db_path=None: False)

    # Install FakeTmuxRun so any accidental send-keys / paste-buffer
    # would be visible AND the function never reaches a real tmux.
    fake = _FakeTmuxRun()
    monkeypatch.setattr(_dispatch, "subprocess", mock.MagicMock(run=fake))

    # Block all the heavy pre/post work signal_send does before
    # inject_prompt. We're testing the INJECTION refusal; everything
    # before it must pass so the code actually reaches the harness_alive
    # check.
    monkeypatch.setattr(_dispatch, "_sweep_orphaned_leases", lambda: None)
    monkeypatch.setattr(_dispatch, "bump_id_counter_past",
                        lambda flow, hid, db_path=None: None)
    monkeypatch.setattr(_dispatch, "ensure_subdir", lambda *a, **kw: None)
    monkeypatch.setattr(_dispatch, "_run_pre_dispatch_scripts",
                        lambda *a, **kw: (True, None))
    monkeypatch.setattr(_dispatch, "get_effective_model_source",
                        lambda *a, **kw: ("model_allocator", ""))
    monkeypatch.setattr(_dispatch, "worker_target", lambda *a, **kw: None)
    monkeypatch.setattr(_dispatch, "_stop_other_local_models",
                        lambda *a, **kw: None)
    monkeypatch.setattr(_dispatch, "_run_allocator_stop",
                        lambda *a, **kw: None)
    monkeypatch.setattr(_dispatch, "_run_allocator_start",
                        lambda *a, **kw: None)
    monkeypatch.setattr(_dispatch, "_release_from_model_first",
                        lambda *a, **kw: None)
    monkeypatch.setattr(_dispatch, "_backend_is_down", lambda *a, **kw: False)
    monkeypatch.setattr(_dispatch, "_resolve_receiver_execution_config",
                        lambda *a, **kw: {"governance_file": "",
                                          "model_source": "harness_provider",
                                          "model_alias": "",
                                          "harness_source": "codex",
                                          "harness_profile": "gpu",
                                          "implementation_mode": "direct"})
    monkeypatch.setattr(_dispatch, "resolve_content_template_from_db",
                        lambda *a, **kw: "")
    monkeypatch.setattr(_dispatch, "get_flow_target_project",
                        lambda *a, **kw: str(tmp_path))
    monkeypatch.setattr(_dispatch, "apply_mode_block",
                        lambda t, *a, **kw: t)
    monkeypatch.setattr(_dispatch, "build_target_project_block",
                        lambda flow_key: "")
    monkeypatch.setattr(_dispatch, "build_runtime_context",
                        lambda resolved: "")
    monkeypatch.setattr(_dispatch, "escalation_role", lambda flow: "human")
    monkeypatch.setattr(_dispatch, "append_trade_mcp_context",
                        lambda t, *a, **kw: t)
    # _update_cycle_state writes to a state file under bridge_dir.
    monkeypatch.setattr(_dispatch, "_update_cycle_state",
                        lambda *a, **kw: None)

    rc = _dispatch.signal_send(flow_key, from_role, to_role, "999",
                                bridge_dir=bridge_dir)

    assert rc is False, (
        f"signal_send must return False when harness_alive is False, "
        f"got {rc}"
    )
    # No send-keys / paste-buffer / load-buffer — the refused dispatch
    # NEVER reached the injection path.
    assert _send_keys_calls(fake) == [], (
        f"signal_send must NOT call send-keys when harness_alive is False; "
        f"got {_send_keys_calls(fake)}"
    )
    assert _paste_buffer_calls(fake) == [], (
        f"signal_send must NOT call paste-buffer when harness_alive is "
        f"False; got {_paste_buffer_calls(fake)}"
    )

    # A loud refusal was logged to trace.log.
    trace = Path(bridge_dir) / "trace.log"
    assert trace.exists(), "signal_send must write a trace.log entry"
    trace_text = trace.read_text(encoding="utf-8")
    # The D1 status is send_failed (signal_send's standard refusal log).
    assert "send_failed" in trace_text, (
        f"expected a send_failed trace entry, got:\n{trace_text}"
    )
    # The error message names the dead harness (the refusal is LOUD).
    assert "is not alive" in trace_text or "(D1)" in trace_text, (
        f"refusal log must name the dead-harness reason, got:\n{trace_text}"
    )


def test_run_flow_step_db_no_harness_refuses_injection_no_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case (d) — the second injection path: run_flow_step_db returns
    False and never injects when harness_alive is False."""
    db_path = str(tmp_path / "truth.db")
    _build_minimal_bridge_db(db_path)

    flow_key = "preferred_cloud_harness"
    from_role = "supervisor_super"
    to_role = "imple-codex-minimaxM3"
    flow_dir = tmp_path / flow_key
    deliverable_dir = str(flow_dir / "handoffs")
    (flow_dir / "handoffs").mkdir(parents=True)
    handoff_path = flow_dir / "handoffs" / "999-handoff.md"
    handoff_path.write_text(
        "<role>Implementer</role>\n"
        "<task>Do the thing.</task>\n"
        "<constraint>Follow governance.</constraint>\n",
        encoding="utf-8",
    )

    bridge_dir = str(flow_dir)
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", bridge_dir)
    monkeypatch.setattr(_dispatch, "_db_path", lambda: db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO bridge_roles
                (role_key, tmux_session, is_active, role_type,
                 enter_command, default_model_source, default_model_alias)
            VALUES (?, ?, 1, 'agent', 'default', 'model_allocator', 'a')
            """,
            (from_role, f"{from_role}-session"),
        )
        conn.execute(
            """
            INSERT INTO bridge_roles
                (role_key, tmux_session, is_active, role_type,
                 enter_command, default_model_source, default_model_alias)
            VALUES (?, ?, 1, 'agent', 'default', 'model_allocator', 'b')
            """,
            (to_role, f"{to_role}-session"),
        )
        conn.execute(
            """
            INSERT INTO bridge_flows (flow_key, name, is_active)
            VALUES (?, ?, 1)
            """,
            (flow_key, "preferred_cloud_harness"),
        )
        conn.execute(
            """
            INSERT INTO bridge_flow_steps
                (flow_key, step_key, from_role, to_role,
                 deliverable_dir, deliverable_pattern,
                 rule_key, sort_order, is_active, validation_required)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 0)
            """,
            (flow_key, "imple01", from_role, to_role,
             str(flow_dir / "handoffs"),
             "{ID}-handoff.md", "json_output"),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(_dispatch, "session_alive", lambda s: True)
    monkeypatch.setattr(_dispatch, "harness_alive",
                        lambda flow, role, db_path=None: False)
    monkeypatch.setattr(_dispatch, "get_flow_target_project",
                        lambda *a, **kw: str(tmp_path))

    fake = _FakeTmuxRun()
    monkeypatch.setattr(_dispatch, "subprocess", mock.MagicMock(run=fake))

    rc = _dispatch.run_flow_step_db(flow_key, "imple01", "999",
                                     bridge_dir=bridge_dir)
    assert rc is False, (
        f"run_flow_step_db must return False when harness_alive is False, "
        f"got {rc}"
    )
    # Never injected.
    assert _send_keys_calls(fake) == []
    assert _paste_buffer_calls(fake) == []

    trace = Path(bridge_dir) / "trace.log"
    assert trace.exists()
    trace_text = trace.read_text(encoding="utf-8")
    assert "failed" in trace_text, (
        f"expected a failed trace entry, got:\n{trace_text}"
    )
    assert "is not alive" in trace_text or "(D1)" in trace_text


# ── (e) Enter fallback REFUSES when harness_alive is False ──────


def test_verify_injection_no_harness_does_not_send_enter_no_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case (e) — the "no_harness" case: verify_injection_submitted
    does NOT press Enter into a pane whose harness is dead. The
    stuck-paste remedy is gated by D1 just like the no-activity
    remedy."""
    fake = _FakeTmuxRun()
    # The pane shows no activity, no menu — the no-activity branch
    # would normally send Enter. With a dead harness, it MUST NOT.
    fake.set_pane_tail("... idle footer, no markers, no menu ...\n")
    monkeypatch.setattr(_dispatch, "subprocess", mock.MagicMock(run=fake))
    monkeypatch.setattr(_dispatch, "session_alive", lambda s: True)
    monkeypatch.setattr(_dispatch, "harness_alive",
                        lambda flow, role, db_path=None: False)
    monkeypatch.setattr(_dispatch, "_pane_tail", lambda s, lines=25: fake.pane_tail)
    monkeypatch.setattr(_dispatch, "_pane_target", lambda s: "=s:0")
    monkeypatch.setattr(_dispatch, "_pane_has_menu_or_selector",
                        lambda tail: False)
    monkeypatch.setattr(_dispatch, "_PASTE_STUCK_MARKER", "paste again to expand")
    monkeypatch.setattr(_dispatch, "activity_markers",
                        lambda s: ("esc to interrupt",))

    confirmed = _dispatch.verify_injection_submitted(
        "review-claude-sonnet5", attempts=2, settle_seconds=0,
        flow_key="preferred_cloud_harness", to_role="review-claude-sonnet5",
    )
    assert confirmed is False
    # The crucial assertion: NO Enter was sent.
    enter_calls = [c for c in _send_keys_calls(fake) if "Enter" in c]
    assert enter_calls == [], (
        f"verify_injection_submitted must NOT send Enter when the harness "
        f"is dead; got {enter_calls}"
    )


def test_verify_injection_no_harness_refuses_stuck_paste_enter_no_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case (e) — stuck-paste path: even when the pane shows the
    paste-expand hint, the Enter remedy is GATED on liveness. The
    2026-08-24 failure had a *stuck* prompt — the very case where the
    Enter fallback fires — so this branch MUST also refuse."""
    fake = _FakeTmuxRun()
    fake.set_pane_tail(
        "... your message is in the buffer — paste again to expand ...\n"
    )
    monkeypatch.setattr(_dispatch, "subprocess", mock.MagicMock(run=fake))
    monkeypatch.setattr(_dispatch, "session_alive", lambda s: True)
    monkeypatch.setattr(_dispatch, "harness_alive",
                        lambda flow, role, db_path=None: False)
    monkeypatch.setattr(_dispatch, "_pane_tail", lambda s, lines=25: fake.pane_tail)
    monkeypatch.setattr(_dispatch, "_pane_target", lambda s: "=s:0")
    monkeypatch.setattr(_dispatch, "_pane_has_menu_or_selector",
                        lambda tail: False)
    monkeypatch.setattr(_dispatch, "_PASTE_STUCK_MARKER", "paste again to expand")
    monkeypatch.setattr(_dispatch, "activity_markers",
                        lambda s: ("esc to interrupt",))

    confirmed = _dispatch.verify_injection_submitted(
        "review-claude-sonnet5", attempts=2, settle_seconds=0,
        flow_key="preferred_cloud_harness", to_role="review-claude-sonnet5",
    )
    assert confirmed is False
    # The stuck-paste Enter must NOT have been sent.
    enter_calls = [c for c in _send_keys_calls(fake) if "Enter" in c]
    assert enter_calls == [], (
        f"stuck-paste Enter must be gated on harness_alive; got {enter_calls}"
    )


# ── Negative tests: verify the gated paths still WORK when alive ──


def test_verify_injection_alive_harness_still_resends_stuck_paste_enter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With a LIVE harness, the existing stuck-paste remedy MUST still
    work — D1 is additive, not a replacement. (Replaces the parallel
    preferred_cloud flow's stuck-paste path.)"""
    fake = _FakeTmuxRun()
    fake.set_pane_tail(
        "... your message is in the buffer — paste again to expand ...\n"
    )
    monkeypatch.setattr(_dispatch, "subprocess", mock.MagicMock(run=fake))
    monkeypatch.setattr(_dispatch, "session_alive", lambda s: True)
    monkeypatch.setattr(_dispatch, "harness_alive",
                        lambda flow, role, db_path=None: True)
    monkeypatch.setattr(_dispatch, "_pane_tail", lambda s, lines=25: fake.pane_tail)
    monkeypatch.setattr(_dispatch, "_pane_target", lambda s: "=s:0")
    monkeypatch.setattr(_dispatch, "_pane_has_menu_or_selector",
                        lambda tail: False)
    monkeypatch.setattr(_dispatch, "_PASTE_STUCK_MARKER", "paste again to expand")
    monkeypatch.setattr(_dispatch, "activity_markers",
                        lambda s: ("esc to interrupt",))

    _dispatch.verify_injection_submitted(
        "review-claude-sonnet5", attempts=1, settle_seconds=0,
        flow_key="preferred_cloud_harness", to_role="review-claude-sonnet5",
    )
    # The stuck-paste Enter MUST be sent (the alive branch keeps the
    # existing remedy intact).
    enter_calls = [c for c in _send_keys_calls(fake) if "Enter" in c]
    assert len(enter_calls) >= 1, (
        f"with a live harness, the stuck-paste Enter MUST be sent; got "
        f"{enter_calls}"
    )


def test_verify_injection_without_flow_key_keeps_existing_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backwards compat: callers that did NOT thread flow_key/to_role
    (internal tests) get the prior behaviour — the Enter fallback fires
    on the stuck-paste hint without consulting harness_alive."""
    fake = _FakeTmuxRun()
    fake.set_pane_tail(
        "... your message is in the buffer — paste again to expand ...\n"
    )
    monkeypatch.setattr(_dispatch, "subprocess", mock.MagicMock(run=fake))
    monkeypatch.setattr(_dispatch, "_pane_tail", lambda s, lines=25: fake.pane_tail)
    monkeypatch.setattr(_dispatch, "_pane_target", lambda s: "=s:0")
    monkeypatch.setattr(_dispatch, "_pane_has_menu_or_selector",
                        lambda tail: False)
    monkeypatch.setattr(_dispatch, "_PASTE_STUCK_MARKER", "paste again to expand")
    monkeypatch.setattr(_dispatch, "activity_markers",
                        lambda s: ("esc to interrupt",))

    # No flow_key / no to_role passed -> D1 check is skipped.
    _dispatch.verify_injection_submitted(
        "review-claude-sonnet5", attempts=1, settle_seconds=0,
    )
    enter_calls = [c for c in _send_keys_calls(fake) if "Enter" in c]
    assert len(enter_calls) >= 1, (
        "without flow_key/to_role, the prior stuck-paste behaviour MUST "
        f"fire; got {enter_calls}"
    )


# ── Read-only invariant ────────────────────────────────────────


def test_harness_alive_does_not_write_to_flow_runtime_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """harness_alive is READ-ONLY (Run 032 GOAL.md §2). It must NEVER
    insert, update, or delete flow_runtime_resources rows even when
    the answer is False (the run-031 'deliverable written but no
    change observed' class of bugs)."""
    # Sentinel: if anything writes here, the seam will see it.
    write_calls: list[tuple] = []

    class _Sentinel:
        def record(self, *a, **kw):
            write_calls.append(("record", a, kw))

        def release(self, *a, **kw):
            write_calls.append(("release", a, kw))

        def list_for_flow(self, flow_key, resource_type=None, db_path=None):
            # Simulate an anchor that exists with a dead pid — the
            # path most likely to tempt a code change that writes back.
            return [{
                "flow_key": flow_key,
                "resource_type": "harness_process",
                "resource_id": "review-claude-sonnet5-session",
                "pid": None,
            }]

    sentinel = _Sentinel()
    monkeypatch.setattr(_dispatch, "_default_load_role",
                        lambda role_name, db_path=None: {
                            "role_key": role_name,
                            "tmux_session": "review-claude-sonnet5-session",
                        })

    import sys as _sys
    _sys.modules["runtime_owner"] = type(sys)("runtime_owner")
    _sys.modules["runtime_owner"].list_for_flow = sentinel.list_for_flow
    _sys.modules["runtime_owner"].record = sentinel.record
    _sys.modules["runtime_owner"].release = sentinel.release
    monkeypatch.setattr(_dispatch, "_default_list_harness_anchors",
                        lambda flow_key, db_path=None:
                        _sys.modules["runtime_owner"].list_for_flow(
                            flow_key, resource_type="harness_process",
                            db_path=db_path))

    rc = _dispatch.harness_alive("preferred_cloud_harness",
                                 "review-claude-sonnet5")
    assert rc is False
    assert write_calls == [], (
        f"harness_alive must NOT write to flow_runtime_resources; got "
        f"{write_calls}"
    )


# ════════════════════════════════════════════════════════════════════
# D2 (Run 032 GOAL.md §1 D2) -- the release's survival check before
# re-anchor. Selected by `pytest -k "survive"` (TG4).
# ════════════════════════════════════════════════════════════════════


# Import the module under test. It is a sibling of dispatch and shares
# the same `_PROJECT_ROOT` sys.path insert.
sys.path.insert(0, str(_REPO / "scripts" / "bridgeV002"))
import codex_context_release as _ccr  # noqa: E402


class _RecordingSpy:
    """Spy for codex_context_release.runtime_owner.record().

    Records every invocation so tests can assert that the refusal
    path does NOT call record() (the 2026-08-24 bug class) and the
    alive path DOES call record() with the resolved pid.

    D2 keeps the release path READ-ONLY against flow_runtime_resources
    for the refusing branch: a dead resolved child MUST NOT leave any
    anchor row recorded. The spy enforces that.
    """

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __call__(self, flow_key, resource_type, resource_id,
                 pid=None, db_path=None):
        self.calls.append({
            "flow_key": flow_key,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "pid": pid,
            "db_path": db_path,
        })
        return None


@pytest.fixture()
def ccr_runtime_owner_spy(monkeypatch: pytest.MonkeyPatch):
    """Replace runtime_owner.* inside codex_context_release so the
    hermetic test never reaches the live DB."""
    spy = _RecordingSpy()

    # Patch every entry point the release path uses so the spy is the
    # sole writer (and so the live DB is NEVER touched).
    monkeypatch.setattr(_ccr.runtime_owner, "list_for_flow",
                        lambda flow_key, resource_type=None, db_path=None: [])
    monkeypatch.setattr(_ccr.runtime_owner, "record", spy)
    monkeypatch.setattr(_ccr.runtime_owner, "release",
                        lambda flow_key, resource_id, db_path=None: None)
    monkeypatch.setattr(_ccr.runtime_owner, "_default_kill",
                        lambda pid: True)
    monkeypatch.setattr(_ccr.config, "get_db_path", lambda: "/tmp/nonexistent.db")
    return spy


# ── (a) Dead child → refuse + NO record ─────────────────────────


def test_re_anchor_refuses_dead_resolved_child_does_not_survive(
    ccr_runtime_owner_spy: _RecordingSpy,
) -> None:
    """Case (a): the resolved child is dead — re_anchor MUST return
    (False, "child pid <n> did not survive") AND MUST NOT call
    runtime_owner.record(). This is the 2026-08-24 bug class pinned
    at the refusal site."""
    def fake_child_pid(session_name):
        return 4242  # the resolved pid

    def fake_pid_alive(pid):
        assert pid == 4242
        return False  # os.kill(4242, 0) raised ProcessLookupError

    ok, msg = _ccr.re_anchor(
        "preferred_cloud_harness", "review-claude-sonnet5-session",
        _child_pid=fake_child_pid, _pid_alive=fake_pid_alive,
    )
    assert ok is False, (
        f"re_anchor must return False when the resolved child is dead; "
        f"got ({ok!r}, {msg!r})"
    )
    assert msg == "child pid 4242 did not survive", (
        f"refusal message must name the dead pid; got {msg!r}"
    )
    # The crucial assertion: NO record() was called. A recorded corpse
    # is exactly the failure mode D2 closes.
    assert ccr_runtime_owner_spy.calls == [], (
        f"re_anchor MUST NOT call runtime_owner.record when the "
        f"resolved child is dead; got {ccr_runtime_owner_spy.calls}"
    )


# ── (b) Alive child → record + (True, "re-anchored pid=<n>") ─────


def test_re_anchor_records_live_resolved_child_survive(
    ccr_runtime_owner_spy: _RecordingSpy,
) -> None:
    """Case (b): the resolved child is alive — re_anchor records it
    and returns (True, "re-anchored pid=<n>"). Same shape as the
    pre-D2 success path; D2 is purely additive."""
    def fake_child_pid(session_name):
        return 9001

    def fake_pid_alive(pid):
        assert pid == 9001
        return True

    ok, msg = _ccr.re_anchor(
        "preferred_cloud_harness", "review-claude-sonnet5-session",
        _child_pid=fake_child_pid, _pid_alive=fake_pid_alive,
    )
    assert ok is True
    assert msg == "re-anchored pid=9001"
    # Exactly ONE record() call with the resolved pid.
    assert len(ccr_runtime_owner_spy.calls) == 1
    call = ccr_runtime_owner_spy.calls[0]
    assert call["pid"] == 9001
    assert call["resource_id"] == "review-claude-sonnet5-session"
    assert call["resource_type"] == "harness_process"


# ── Negative test: the never-resolved degrade path is UNCHANGED ───


def test_re_anchor_unchanged_when_child_never_resolved_does_not_survive(
    ccr_runtime_owner_spy: _RecordingSpy,
) -> None:
    """The never-resolved case (child_pid is None after the ready
    window) keeps its existing degrade: pid=None recorded, return
    (True, "re-anchored pid=None"). D2 is only about a child that
    WAS resolved and is now dead."""
    def fake_child_pid(session_name):
        return None  # never appeared

    def fake_pid_alive(pid):
        raise AssertionError(
            "_pid_alive must NOT be called when child_pid is None "
            "(D2 only checks resolved pids)"
        )

    ok, msg = _ccr.re_anchor(
        "preferred_cloud_harness", "review-claude-sonnet5-session",
        _child_pid=fake_child_pid, _pid_alive=fake_pid_alive,
    )
    assert ok is True
    assert msg == "re-anchored pid=None"
    # The existing degrade records pid=None and returns success.
    assert len(ccr_runtime_owner_spy.calls) == 1
    assert ccr_runtime_owner_spy.calls[0]["pid"] is None


# ── Negative test: the seam defaults to the shared idiom ──────────


def test_default_pid_alive_uses_os_kill_zero_survive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default _default_pid_alive is the shared os.kill(pid, 0)
    idiom (ProcessLookupError -> False; PermissionError / other
    OSError -> True). Same shape as dispatch._default_pid_alive."""
    seen: list[int] = []

    def fake_kill(pid, sig):
        seen.append(pid)
        if pid == 1:
            raise ProcessLookupError(pid)
        if pid == 2:
            raise PermissionError(pid)
        return None  # alive

    monkeypatch.setattr(_ccr.os, "kill", fake_kill)
    assert _ccr._default_pid_alive(1) is False   # ProcessLookupError
    assert _ccr._default_pid_alive(2) is True    # PermissionError
    assert _ccr._default_pid_alive(3) is True    # alive
    assert _ccr._default_pid_alive(None) is False
    assert seen == [1, 2, 3]


# ── (c) run_release aborts (exit 5) when the child does not survive


def test_run_release_aborts_when_child_did_not_survive(
    ccr_runtime_owner_spy: _RecordingSpy,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Case (c): end-to-end — when the child does not survive,
    run_release returns exit 5 ("RE-ANCHOR FAILED ... aborting
    dispatch") and does NOT call record(). The loud-failure wiring
    is preserved."""
    # Stub the role row load so run_release gets a valid role_config.
    monkeypatch.setattr(_ccr, "_load_role_or_exit",
                        lambda to_role, db_path: {
                            "role_key": to_role,
                            "tmux_session": "review-claude-sonnet5-session",
                            "default_harness_source": "codex",
                        })
    # No-op the no-op gate (harness is codex, policy is work_unit).
    monkeypatch.setattr(_ccr, "resolve_receiving_harness",
                        lambda flow_key, to_role, db_path=None: "codex")
    monkeypatch.setattr(_ccr, "should_no_op",
                        lambda harness_key: (False, "codex armed"))

    # stop_anchor returns (True, "stale-anchor") so run_release proceeds
    # to relaunch + re_anchor.
    monkeypatch.setattr(_ccr, "stop_anchor",
                        lambda flow_key, resource_id, db_path=None,
                        _kill=None: (True, "stale-anchor"))
    # relaunch_in_session returns (True, "relaunched") so run_release
    # proceeds to re_anchor.
    monkeypatch.setattr(_ccr, "relaunch_in_session",
                        lambda session_name, role_config, db_path=None,
                        _send_keys=None, _build_launch=None:
                        (True, "relaunched"))

    # re_anchor returns the D2 failure shape.
    monkeypatch.setattr(_ccr, "re_anchor",
                        lambda flow_key, session_name, db_path=None,
                        _child_pid=None, _pid_alive=None:
                        (False, "child pid 4242 did not survive"))

    rc = _ccr.run_release("preferred_cloud_harness",
                          "review-claude-sonnet5")

    assert rc == 5, (
        f"run_release must exit 5 (RE-ANCHOR FAILED ... aborting "
        f"dispatch) when re_anchor returns False; got {rc}"
    )
    # record() must NOT have been called end-to-end.
    assert ccr_runtime_owner_spy.calls == [], (
        f"run_release MUST NOT call record() when re_anchor refused; "
        f"got {ccr_runtime_owner_spy.calls}"
    )
    # Loud failure surfaced to stderr.
    captured = capsys.readouterr()
    assert "RE-ANCHOR FAILED" in captured.err, (
        f"the failure must print 'RE-ANCHOR FAILED ... aborting "
        f"dispatch' to stderr; got stderr={captured.err!r}"
    )
    assert "aborting dispatch" in captured.err
    assert "did not survive" in captured.err


# ════════════════════════════════════════════════════════════════════
# D3 (Run 032 GOAL.md §1 D3) -- truthful queue status for an aborted
# send. Selected by `pytest -k "aborted_send"` (TG5).
# ════════════════════════════════════════════════════════════════════


# Import the broker so we can drive _run_dispatch / _process_one
# hermetically without spawning a real dispatch.py.
import bridge_broker as _broker  # noqa: E402


# ── Helpers ─────────────────────────────────────────────────────


def _write_fake_dispatch_py(path: Path, *, stderr_reason: str,
                            stdout_lines: tuple = (),
                            rc: int = 1) -> None:
    """Write a tiny Python script that simulates a failed dispatch.

    The fake reads its argv, prints the supplied stdout_lines, prints
    an ERROR: line to stderr naming the reason, and exits with the
    supplied rc. dispatch.py's _dispatch_main_run wrapper does exactly
    the same in production (ERROR to stderr + sys.exit(1)); the fake
    here makes that contract executable from a temp file.

    Pass stderr_reason="" to make the fake exit silently with rc=1 --
    used by tests that check the row is failed even when no error text
    is captured (a worst-case, "what if dispatch.py crashes without a
    message" guard).
    """
    lines_block = (
        "for line in [\n"
        + "".join(f"    {line!r},\n" for line in stdout_lines)
        + "]:\n"
        "    print(line)\n"
    )
    stderr_block = (
        f"print({('ERROR: ' + stderr_reason)!r}, file=sys.stderr, flush=True)\n"
        if stderr_reason else ""
    )
    code = (
        "import sys\n"
        + lines_block
        + stderr_block
        + f"sys.exit({rc})\n"
    )
    path.write_text(code, encoding="utf-8")


@pytest.fixture()
def aborted_send_env(tmp_path: Path,
                      monkeypatch: pytest.MonkeyPatch):
    """Hermetic setup for D3 tests.

    Builds a fresh SQLite bridge_dispatch_queue table, writes a fake
    dispatch.py to a temp file, and monkeypatches the broker's DB
    path / dispatch.py path / retry sleep / bridge_dir / config helpers
    so EVERY call inside _process_one uses the temp fixtures. No live
    database, no live trace.log, no live dispatch.py.
    """
    db_path = str(tmp_path / "truth.db")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE bridge_dispatch_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_key TEXT NOT NULL,
                from_role TEXT NOT NULL,
                to_role TEXT NOT NULL,
                handoff_id TEXT,
                action TEXT,
                handoff_path TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now')),
                claimed_at TEXT,
                processed_at TEXT,
                error_msg TEXT,
                broker_pid INTEGER
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    bridge_dir = str(tmp_path / "bridge")
    (Path(bridge_dir) / "preferred_cloud_harness").mkdir(parents=True)

    fake_dispatch = tmp_path / "fake_dispatch.py"

    # Pin the broker to the temp DB / temp bridge_dir / fake dispatch.py.
    monkeypatch.setattr(_broker, "_get_db_path", lambda: db_path)
    monkeypatch.setattr(_broker, "_get_bridge_dir", lambda: bridge_dir)
    monkeypatch.setattr(_broker, "_DISPATCH_PY", fake_dispatch)
    # Skip retry sleeps so the bound is observable in milliseconds.
    monkeypatch.setattr(_broker, "_RETRY_SLEEP", lambda _s: None)
    # Short-circuit the broker's pid attribution -- a fixed value keeps
    # the row-claim SELECT stable.
    monkeypatch.setattr(_broker.os, "getpid", lambda: 99999)

    return {
        "db_path": db_path,
        "bridge_dir": bridge_dir,
        "fake_dispatch": fake_dispatch,
    }


def _enqueue_pending(conn: sqlite3.Connection, *,
                     flow_key: str, from_role: str, to_role: str,
                     handoff_id: str, action: str = "signal-send",
                     handoff_path: str = "") -> int:
    """Insert one pending dispatch row; return its row id."""
    cur = conn.execute(
        """
        INSERT INTO bridge_dispatch_queue
            (flow_key, from_role, to_role, handoff_id, action,
             handoff_path, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """,
        (flow_key, from_role, to_role, handoff_id, action, handoff_path),
    )
    conn.commit()
    return cur.lastrowid


def _row_status(db_path: str, row_id: int) -> tuple:
    """Read the current (status, error_msg) for a queue row."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "SELECT status, error_msg FROM bridge_dispatch_queue WHERE id = ?",
            (row_id,),
        )
        return cur.fetchone()
    finally:
        conn.close()


# ── (a) pre-dispatch script failure → row failed ────────────────


def test_pre_dispatch_script_fail_marks_row_failed_aborted_send(
    aborted_send_env,
) -> None:
    """Case (a) -- the D1/D2/D3 headline: a send whose pre-dispatch
    script refuses MUST leave its queue row `failed` with an
    error_msg naming the reason. Today this row reads `completed`
    with empty error_msg -- the 2026-08-24 dispatch row 431 / run
    030 row 413 bug class.

    The fake dispatch.py prints an ERROR: line on stderr and exits
    1 -- exactly what dispatch.py's _dispatch_main_run wrapper does
    when signal_send returns False after a pre_dispatch_script
    refusal."""
    fake = aborted_send_env["fake_dispatch"]
    _write_fake_dispatch_py(
        fake,
        stderr_reason=(
            "signal_send returned False (dispatch aborted) "
            "-- pre-dispatch script refused"
        ),
    )

    db_path = aborted_send_env["db_path"]
    conn = sqlite3.connect(db_path)
    try:
        row_id = _enqueue_pending(
            conn,
            flow_key="preferred_cloud_harness",
            from_role="supervisor_super",
            to_role="imple-codex-minimaxM3",
            handoff_id="999",
        )
    finally:
        conn.close()

    # Drive one claim through the broker; this is the path the live
    # bridge-broker.service takes.
    _proc_conn = sqlite3.connect(db_path)
    _proc_conn.row_factory = sqlite3.Row
    processed = _broker._process_one(_proc_conn)
    assert processed is True, "_process_one must claim the pending row"

    status, err = _row_status(db_path, row_id)
    assert status == "failed", (
        f"a pre-dispatch-script failure must leave the row failed; "
        f"got status={status!r} err={err!r}"
    )
    assert err, (
        f"the failed row's error_msg MUST be set (naming the reason); "
        f"got {err!r}"
    )
    assert "pre-dispatch script" in err or "dispatch aborted" in err, (
        f"error_msg must name the refusal reason; got {err!r}"
    )


# ── (b) inject failure → row failed ─────────────────────────────


def test_inject_failure_marks_row_failed_aborted_send(
    aborted_send_env,
) -> None:
    """Case (b) -- a send that cannot inject MUST leave its queue
    row `failed` with an error naming the reason. The fake
    dispatch.py simulates an unhandled exception during injection
    (a tmux send-keys subprocess crash that propagates out of
    inject_prompt). _dispatch_main_run catches the exception,
    prints ERROR: to stderr, and exits 1."""
    fake = aborted_send_env["fake_dispatch"]
    _write_fake_dispatch_py(
        fake,
        stderr_reason=(
            "signal_send raised CalledProcessError: tmux send-keys "
            "exited 1 during injection"
        ),
    )

    db_path = aborted_send_env["db_path"]
    conn = sqlite3.connect(db_path)
    try:
        row_id = _enqueue_pending(
            conn,
            flow_key="preferred_cloud_harness",
            from_role="supervisor_super",
            to_role="imple-codex-minimaxM3",
            handoff_id="1000",
        )
    finally:
        conn.close()

    _proc_conn = sqlite3.connect(db_path)
    _proc_conn.row_factory = sqlite3.Row
    processed = _broker._process_one(_proc_conn)
    assert processed is True

    status, err = _row_status(db_path, row_id)
    assert status == "failed", (
        f"an injection failure must leave the row failed; got "
        f"status={status!r} err={err!r}"
    )
    assert err, (
        f"the failed row's error_msg MUST be set; got {err!r}"
    )
    assert "tmux send-keys" in err or "injection" in err, (
        f"error_msg must name the injection failure; got {err!r}"
    )


# ── Negative tests for the precedence ordering ──────────────────


def test_refused_injection_still_requeues_not_failed_aborted_send(
    aborted_send_env,
) -> None:
    """The Run 006 D6(b) requeue contract is preserved: a busy-pane
    refusal (REFUSED_INJECTION line) MUST requeue with backoff, NOT
    mark failed. D3 reordered the broker's precedence so REFUSED_
    INJECTION is checked BEFORE the rc != 0 check; this test pins
    the precedence against future drift."""
    fake = aborted_send_env["fake_dispatch"]
    # The fake simulates signal_send's busy-pane path: prints
    # REFUSED_INJECTION on stdout AND ERROR: on stderr, exits 1.
    _write_fake_dispatch_py(
        fake,
        stderr_reason="signal_send returned False (dispatch aborted)",
        stdout_lines=("REFUSED_INJECTION: pane busy",),
    )

    db_path = aborted_send_env["db_path"]
    conn = sqlite3.connect(db_path)
    try:
        row_id = _enqueue_pending(
            conn,
            flow_key="preferred_cloud_harness",
            from_role="supervisor_super",
            to_role="imple-codex-minimaxM3",
            handoff_id="1001",
        )
    finally:
        conn.close()

    _proc_conn = sqlite3.connect(db_path)
    _proc_conn.row_factory = sqlite3.Row
    processed = _broker._process_one(_proc_conn)
    assert processed is True

    status, err = _row_status(db_path, row_id)
    assert status == "pending", (
        f"a REFUSED_INJECTION must requeue (pending with backoff), "
        f"NOT mark failed; got status={status!r} err={err!r}"
    )
    assert err in (None, ""), (
        f"requeued rows have no error_msg; got {err!r}"
    )


def test_happy_dispatch_still_marks_row_completed_aborted_send(
    aborted_send_env,
) -> None:
    """Negative control -- the happy path (dispatch.py exits 0, no
    ERROR / REFUSED_INJECTION line) still marks the row `completed`
    with NULL error_msg. D3 must not regress the success path."""
    fake = aborted_send_env["fake_dispatch"]
    # Fake with NO error output and rc=0.
    code = (
        "import sys\n"
        "print('  Handoff dispatch prompt injected')\n"
        "sys.exit(0)\n"
    )
    fake.write_text(code, encoding="utf-8")

    db_path = aborted_send_env["db_path"]
    conn = sqlite3.connect(db_path)
    try:
        row_id = _enqueue_pending(
            conn,
            flow_key="preferred_cloud_harness",
            from_role="supervisor_super",
            to_role="imple-codex-minimaxM3",
            handoff_id="1002",
        )
    finally:
        conn.close()

    _proc_conn = sqlite3.connect(db_path)
    _proc_conn.row_factory = sqlite3.Row
    processed = _broker._process_one(_proc_conn)
    assert processed is True

    status, err = _row_status(db_path, row_id)
    assert status == "completed", (
        f"a successful dispatch must leave the row completed; got "
        f"status={status!r} err={err!r}"
    )
    assert err in (None, ""), (
        f"completed rows have no error_msg; got {err!r}"
    )


def test_silent_dispatch_crash_still_marks_row_failed_aborted_send(
    aborted_send_env,
) -> None:
    """Even when dispatch.py crashes WITHOUT an ERROR line (the
    "silent dispatch failure" worst case -- e.g. an uncaught
    exception that does not match the wrapper's catch), the broker
    must mark the row `failed` because dispatch.py exited nonzero.
    This is the D3 'aborted send leaves its row failed with a
    reason' contract under the worst-case scenario."""
    fake = aborted_send_env["fake_dispatch"]
    # Fake exits 1 with NO output at all (the silent-crash case).
    fake.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")

    db_path = aborted_send_env["db_path"]
    conn = sqlite3.connect(db_path)
    try:
        row_id = _enqueue_pending(
            conn,
            flow_key="preferred_cloud_harness",
            from_role="supervisor_super",
            to_role="imple-codex-minimaxM3",
            handoff_id="1003",
        )
    finally:
        conn.close()

    _proc_conn = sqlite3.connect(db_path)
    _proc_conn.row_factory = sqlite3.Row
    processed = _broker._process_one(_proc_conn)
    assert processed is True

    status, err = _row_status(db_path, row_id)
    assert status == "failed", (
        f"a silent dispatch crash must leave the row failed (not "
        f"completed); got status={status!r} err={err!r}"
    )
    # The error_msg is whatever the broker captures; the broker's
    # fallback when err is empty is `f'dispatch.py exited {rc}'` per
    # _process_one.
    assert err, f"the failed row's error_msg MUST be set; got {err!r}"
