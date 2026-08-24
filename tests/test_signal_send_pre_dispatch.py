"""Tests for the signal_send pre-dispatch wiring (Run 030 D2).

Run 029 parked on a defect: dispatch.py signal_send() (the path the
supervisor's broker-seam dispatch actually takes) NEVER ran the step's
pre_dispatch_script. Run 030 D1 fixes that by inserting the same
4-line `_run_pre_dispatch_scripts(...)` pattern the two existing call
sites (run_flow_step_db and signal_complete) use, into signal_send(),
placed AFTER the handoff/XML validation block and BEFORE the model-
resolution job-record work.

This suite pins the four binding rules the reviewer measures:
  (T1) signal_send INVOKES the pre-dispatch helper with the step's
       resolved pre_dispatch_script key — the "IS invoked" case.
  (T2) A FAILING pre-dispatch script aborts the send: signal_send
       returns False, inject_prompt is NOT called, no "dispatched"
       log event.
       NAME contains "abort" so `-k "abort"` selects it (TG3).
  (T3) A step with NO pre_dispatch_script is an unchanged no-op:
       inject_prompt is called exactly once, the empty path is
       byte-identical to today's no-script path.
  (T4) The helper is called BEFORE inject_prompt (release fires
       before the prompt lands, never after).

HERMETIC by construction. Every outbound seam is stubbed via
monkeypatch; the isolated DB is in-memory; no live trace.log, no
live queues, no live tmux, no live databases/dpmtf.db.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts" / "bridgeV002"))
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "scripts" / "job_queue"))

import dispatch  # noqa: E402


# ---------------------------------------------------------------------------
# Seams — recording stubs. Every patched seam appends to a shared list so
# the test can assert order (T4) and which side-effects happened (T1/T2).
# ---------------------------------------------------------------------------
class _Seams:
    """One bag of recorders, reused across tests for hermetic isolation."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    # Pre-dispatch seam (the one the wiring exercises).
    def run_pre_dispatch_scripts(self, pre_script_value, payload, bridge_dir=None):
        self.calls.append(("pre_dispatch", pre_script_value, payload, bridge_dir))
        # Mirror dispatch._run_pre_dispatch_scripts: a failing script
        # returns (False, True); a successful one (or empty input)
        # returns (True, False).
        if pre_script_value and "FAIL" in str(pre_script_value).upper():
            return (False, True)
        return (True, False)

    # inject_prompt seam — must NOT be called when pre_dispatch fails (T2);
    # called exactly once in the no-op (T3) and successful paths.
    def inject_prompt(self, session_name, text, **kwargs):
        self.calls.append(("inject_prompt", session_name))
        return None

    # log seam — captures every trace event so T2 can assert NO
    # "dispatched" event was recorded on abort.
    def log(self, direction, handoff_id, status, message, source="manual"):
        self.calls.append(("log", direction, handoff_id, status, message))


# ---------------------------------------------------------------------------
# Fixtures — patched seams + a fake payload/target_step.
# ---------------------------------------------------------------------------
@pytest.fixture
def seams(tmp_path, monkeypatch: pytest.MonkeyPatch) -> _Seams:
    """Patch every outbound seam of signal_send. Returns the recorder."""
    s = _Seams()

    # Use a real temp dir as the bridge root so signal_send's handoff
    # file existence check passes. Create the handoff file the test
    # expects to find (signal_send validates it BEFORE the
    # pre-dispatch wiring fires).
    bridge_dir = tmp_path / "bridge"
    handoff_subdir = bridge_dir / "preferred_cloud_harness" / "handoffs"
    handoff_subdir.mkdir(parents=True)
    handoff_path = handoff_subdir / "099-result.md"
    handoff_path.write_text(
        "<role>review-claude-sonnet5</role>\n"
        "<task>dispatch</task>\n"
        "<constraint>none</constraint>\n"
    )
    bridge_dir_str = str(bridge_dir)

    # Minimal role / flow stubs — signal_send needs from_role and to_role
    # to be loadable, and a step with a pre_dispatch_script field.
    fake_from = {
        "role_key": "review-claude-sonnet5",
        "tmux_session": "review-claude-sonnet5",
        "role_type": "agent",
    }
    fake_to = {
        "role_key": "imple-codex-minimaxM3",
        "tmux_session": "imple-codex-minimaxM3",
        "role_type": "agent",
    }

    def _load_role(role_key, db_path=None):
        if role_key == "review-claude-sonnet5":
            return dict(fake_from)
        if role_key == "imple-codex-minimaxM3":
            return dict(fake_to)
        raise ValueError(f"unknown role {role_key!r}")

    def _build_payload(step, flow_key, handoff_id, bridge_dir):
        return {
            "step_key": step.get("step_key", "review-to-imple"),
            "from_role": "review-claude-sonnet5",
            "to_role": "imple-codex-minimaxM3",
            "flow_key": flow_key,
            "handoff_id": handoff_id,
            "deliverable_dir": f"{flow_key}/handoffs",
            "deliverable_file": "099-result.md",
            "deliverable_pattern": "*",
            "bridge_dir": bridge_dir,
            "rule_key": step.get("rule_key"),
            "prompt_template": "",
        }

    monkeypatch.setattr(dispatch, "_db_path", lambda: "/tmp/_unused_test.db")
    monkeypatch.setattr(dispatch, "load_role_from_db", _load_role)
    monkeypatch.setattr(dispatch, "_sweep_orphaned_leases", lambda: None)
    monkeypatch.setattr(dispatch, "worker_target", lambda role_data: None)
    monkeypatch.setattr(dispatch, "get_flow_target_project", lambda fk: "/tmp")
    monkeypatch.setattr(dispatch, "session_alive", lambda session_name: True)
    monkeypatch.setattr(dispatch, "_run_pre_dispatch_scripts",
                        s.run_pre_dispatch_scripts)
    monkeypatch.setattr(dispatch, "build_step_payload", _build_payload)
    monkeypatch.setattr(dispatch, "bump_id_counter_past",
                        lambda *a, **k: None)
    monkeypatch.setattr(dispatch, "ensure_subdir", lambda *a, **k: None)
    monkeypatch.setattr(dispatch, "log", s.log)
    monkeypatch.setattr(dispatch, "inject_prompt", s.inject_prompt)
    # The post-pre-dispatch chain (job record, model resolve, content
    # template, prompt assembly, symlink) is no-op-stubbed; only T3
    # needs the "inject_prompt is reached" branch to fire.
    monkeypatch.setattr(dispatch, "get_effective_model_source",
                        lambda *a, **k: ("", ""))
    monkeypatch.setattr(dispatch, "resolve_content_template_from_db",
                        lambda *a, **k: "")
    monkeypatch.setattr(dispatch, "apply_mode_block",
                        lambda p, *a, **k: p)
    monkeypatch.setattr(dispatch, "build_target_project_block",
                        lambda fk: "")
    monkeypatch.setattr(dispatch, "build_runtime_context",
                        lambda *a, **k: "")
    monkeypatch.setattr(dispatch, "append_trade_mcp_context",
                        lambda p, *a, **k: p)
    monkeypatch.setattr(dispatch, "_update_cycle_state", lambda *a, **k: None)
    monkeypatch.setattr(dispatch, "_resolve_receiver_execution_config",
                        lambda *a, **k: {"governance_file": ""})

    # Block the JobRepository side-effect (would touch the live job DB).
    import importlib
    models_mod = importlib.import_module("models")

    class _NoJobRepo:
        def __init__(self, *a, **k):
            raise RuntimeError("job DB blocked in tests")

    monkeypatch.setattr(models_mod, "JobRepository", _NoJobRepo)

    # flow_data.load — return a step with the requested pre_dispatch_script.
    def _make_load_flow(pre_dispatch_script):
        def _load_flow(flow_key, **kwargs):
            return {
                "flow_key": flow_key,
                "steps": [{
                    "step_key": "review-to-imple",
                    "from_role": "review-claude-sonnet5",
                    "to_role": "imple-codex-minimaxM3",
                    "rule_key": "json_output",
                    "pre_dispatch_script": pre_dispatch_script,
                    "validation_required": 0,
                }],
            }
        return _load_flow

    return SimpleNamespace(
        recorder=s,
        make_load_flow=_make_load_flow,
        bridge_dir_str=bridge_dir_str,
    )


# ---------------------------------------------------------------------------
# T1 — pre_dispatch_script IS invoked with the step's resolved key
# ---------------------------------------------------------------------------
def test_signal_send_invokes_pre_dispatch_with_step_key(
    seams, monkeypatch: pytest.MonkeyPatch
) -> None:
    """signal_send calls _run_pre_dispatch_scripts with the step's
    pre_dispatch_script value and the same payload/bridge_dir."""
    recorder = seams.recorder
    make_load_flow = seams.make_load_flow
    bridge_dir_str = seams.bridge_dir_str
    monkeypatch.setattr(dispatch, "load_flow_from_db",
                        make_load_flow("codex_context_release"))

    rc = dispatch.signal_send(
        "preferred_cloud_harness",
        "review-claude-sonnet5",
        "imple-codex-minimaxM3",
        "099",
        bridge_dir=bridge_dir_str,
    )

    assert rc is True
    # Exactly one pre_dispatch call.
    pre_calls = [c for c in recorder.calls if c[0] == "pre_dispatch"]
    assert len(pre_calls) == 1
    key, payload, bridge_dir_seen = (pre_calls[0][1], pre_calls[0][2],
                                     pre_calls[0][3])
    assert key == "codex_context_release"
    assert payload["flow_key"] == "preferred_cloud_harness"
    assert payload["to_role"] == "imple-codex-minimaxM3"
    assert bridge_dir_seen == bridge_dir_str


# ---------------------------------------------------------------------------
# T2 — failing pre_dispatch_script aborts the send (NAME has "abort")
# ---------------------------------------------------------------------------
def test_abort_on_failing_pre_dispatch_script(
    seams, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A FAILING pre-dispatch script aborts the send: signal_send returns
    False, inject_prompt is NOT called, no "dispatched" log event.
    """
    recorder = seams.recorder
    make_load_flow = seams.make_load_flow
    bridge_dir_str = seams.bridge_dir_str
    # The seam treats any key containing "FAIL" as a failing script.
    monkeypatch.setattr(dispatch, "load_flow_from_db",
                        make_load_flow("WILL_FAIL"))

    rc = dispatch.signal_send(
        "preferred_cloud_harness",
        "review-claude-sonnet5",
        "imple-codex-minimaxM3",
        "099",
        bridge_dir=bridge_dir_str,
    )

    # signal_send returned False.
    assert rc is False
    # inject_prompt was NEVER reached.
    inject_calls = [c for c in recorder.calls if c[0] == "inject_prompt"]
    assert inject_calls == []
    # NO log event with status == "dispatched" was recorded.
    dispatched_logs = [
        c for c in recorder.calls
        if c[0] == "log" and c[3] == "dispatched"
    ]
    assert dispatched_logs == []


# ---------------------------------------------------------------------------
# T3 — NO pre_dispatch_script → unchanged no-op path
# ---------------------------------------------------------------------------
def test_no_pre_dispatch_script_is_unchanged_noop(
    seams, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A step with no pre_dispatch_script must exercise the empty-input
    path byte-identically to today: _run_pre_dispatch_scripts returns
    (True, False), signal_send proceeds, inject_prompt is called exactly
    once."""
    recorder = seams.recorder
    make_load_flow = seams.make_load_flow
    bridge_dir_str = seams.bridge_dir_str
    monkeypatch.setattr(dispatch, "load_flow_from_db",
                        make_load_flow(None))

    rc = dispatch.signal_send(
        "preferred_cloud_harness",
        "review-claude-sonnet5",
        "imple-codex-minimaxM3",
        "099",
        bridge_dir=bridge_dir_str,
    )

    assert rc is True
    # Helper WAS called (with the empty value).
    pre_calls = [c for c in recorder.calls if c[0] == "pre_dispatch"]
    assert len(pre_calls) == 1
    assert pre_calls[0][1] in (None, "")
    # inject_prompt fired exactly once.
    inject_calls = [c for c in recorder.calls if c[0] == "inject_prompt"]
    assert len(inject_calls) == 1


# ---------------------------------------------------------------------------
# T4 — ORDER: pre_dispatch BEFORE inject_prompt
# ---------------------------------------------------------------------------
def test_pre_dispatch_runs_before_inject_prompt(
    seams, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pre-dispatch call MUST precede the inject_prompt call.
    A release after the prompt lands is not a release."""
    recorder = seams.recorder
    make_load_flow = seams.make_load_flow
    bridge_dir_str = seams.bridge_dir_str
    monkeypatch.setattr(dispatch, "load_flow_from_db",
                        make_load_flow("codex_context_release"))

    rc = dispatch.signal_send(
        "preferred_cloud_harness",
        "review-claude-sonnet5",
        "imple-codex-minimaxM3",
        "099",
        bridge_dir=bridge_dir_str,
    )

    assert rc is True
    pre_idx = next(
        i for i, c in enumerate(recorder.calls) if c[0] == "pre_dispatch"
    )
    inject_idx = next(
        i for i, c in enumerate(recorder.calls) if c[0] == "inject_prompt"
    )
    assert pre_idx < inject_idx, (
        f"pre_dispatch at index {pre_idx} must precede "
        f"inject_prompt at index {inject_idx}"
    )
