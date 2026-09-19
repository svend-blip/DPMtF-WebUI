"""The run position reaches a simple-harness role launched by BridgeV002.

simple-harness fills ``run_id`` / ``handoff_id`` / ``flow_key`` on MCP calls
from ``SIMPLE_HARNESS_RUN_ID`` / ``_HANDOFF_ID`` / ``_FLOW_KEY``, so that a
knowledge retrieval can be attributed to the run that made it. FlowRunner sets
the three; BridgeV002 set none, and every retrieval made from one of its panes
was logged without a run. The terminal invokes the harness once per delivered
prompt, so the position is set per invocation — a pane outlives its handoffs.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import harness_terminal as _ht  # noqa: E402

HANDOFF_PROMPT = """The architect has prepared a handoff. Read and execute the referenced file.

## Previous Deliverable
Handoff ID: 097
Source Role: 1020-planner
"""

CALLBACK_PROMPT = """<handoff_id>104</handoff_id>

<source_role>1020-implementer</source_role>
"""


def _position(monkeypatch, task, run="041", flow="1020-02-ELOOP", harness="simple-harness"):
    monkeypatch.setattr(_ht, "_executing_run", lambda flow_key: run)
    for name in _ht.POSITION_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    return _ht.position_env(harness, flow, task)


def test_the_handoff_field_is_read_in_both_template_forms(monkeypatch):
    assert _position(monkeypatch, HANDOFF_PROMPT) == {
        "SIMPLE_HARNESS_RUN_ID": "041",
        "SIMPLE_HARNESS_HANDOFF_ID": "097",
        "SIMPLE_HARNESS_FLOW_KEY": "1020-02-ELOOP",
    }
    assert _position(monkeypatch, CALLBACK_PROMPT)["SIMPLE_HARNESS_HANDOFF_ID"] == "104"


def test_a_field_is_matched_not_a_substring(monkeypatch):
    # Prose that mentions a handoff is not the field, and a prompt naming
    # two different ids names none: a wrong attribution is worse than none.
    prose = "Continue from where handoff 009 stopped; see Handoff ID: 097 in the ledger for context."
    assert "SIMPLE_HARNESS_HANDOFF_ID" not in _position(monkeypatch, prose)
    both = HANDOFF_PROMPT + "\n<handoff_id>104</handoff_id>\n"
    assert "SIMPLE_HARNESS_HANDOFF_ID" not in _position(monkeypatch, both)
    same = HANDOFF_PROMPT + "\n<handoff_id>097</handoff_id>\n"
    assert _position(monkeypatch, same)["SIMPLE_HARNESS_HANDOFF_ID"] == "097"


def test_what_is_not_known_is_not_set(monkeypatch):
    # A flow without runs (strict_review) has a flow key and a handoff.
    got = _position(monkeypatch, HANDOFF_PROMPT, run=None, flow="strict_review")
    assert got == {"SIMPLE_HARNESS_HANDOFF_ID": "097", "SIMPLE_HARNESS_FLOW_KEY": "strict_review"}
    assert _position(monkeypatch, "just a question", run=None, flow="") == {}
    # Another harness reads none of these.
    assert _position(monkeypatch, HANDOFF_PROMPT, harness="codex") == {}


def test_a_value_the_operator_set_wins(monkeypatch):
    monkeypatch.setattr(_ht, "_executing_run", lambda flow_key: "041")
    for name in _ht.POSITION_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SIMPLE_HARNESS_RUN_ID", "pinned")
    got = _ht.position_env("simple-harness", "1020-02-ELOOP", HANDOFF_PROMPT)
    assert "SIMPLE_HARNESS_RUN_ID" not in got
    assert got["SIMPLE_HARNESS_HANDOFF_ID"] == "097"


def test_the_runner_sets_the_position_for_one_invocation_only(monkeypatch):
    seen = {}

    def fake_execute(**kwargs):
        seen.update({name: os.environ.get(name) for name in _ht.POSITION_ENV_NAMES})
        return {"status": "ok"}

    monkeypatch.setattr(_ht, "_standalone_pkg", lambda: SimpleNamespace(execute=fake_execute))
    monkeypatch.setattr(_ht, "_executing_run", lambda flow_key: "041")
    monkeypatch.setattr(_ht, "_TERMINAL_FLOW", "1020-02-ELOOP")
    for name in _ht.POSITION_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    result = _ht._standalone_runner(
        role="1020-implementer", harness="simple-harness", model_target="m", cwd=".",
        task=HANDOFF_PROMPT, request_id="r1", heartbeat_interval=1.0, timeout=5, on_event=None)
    assert result == {"status": "ok"}
    assert seen == {"SIMPLE_HARNESS_RUN_ID": "041", "SIMPLE_HARNESS_HANDOFF_ID": "097",
                    "SIMPLE_HARNESS_FLOW_KEY": "1020-02-ELOOP"}
    # The pane outlives the handoff: nothing of it stays in the environment.
    assert all(os.environ.get(name) is None for name in _ht.POSITION_ENV_NAMES)


def test_the_executing_run_lookup_never_breaks_a_delivery(monkeypatch):
    def boom(flow_key):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(_ht, "_executing_run", boom)
    for name in _ht.POSITION_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    got = _ht.position_env("simple-harness", "1020-02-ELOOP", HANDOFF_PROMPT)
    assert got == {"SIMPLE_HARNESS_HANDOFF_ID": "097", "SIMPLE_HARNESS_FLOW_KEY": "1020-02-ELOOP"}


def test_the_real_lookup_finds_the_executing_run(monkeypatch, tmp_path):
    # Not stubbed: supervisor_state.executing_run against a run directory on
    # disk, reached through config.get_bridge_dir — the path a live pane takes.
    import bridge_lib
    import config
    monkeypatch.setattr(config, "get_bridge_dir", lambda: str(tmp_path))
    monkeypatch.setattr(bridge_lib, "get_effective_artifact_root", lambda flow_key, db_path=None: "1020")
    closed, working = tmp_path / "1020" / "runs" / "040", tmp_path / "1020" / "runs" / "041"
    for run in (closed, working):
        run.mkdir(parents=True)
        (run / "GOAL.md").write_text("goal\n", encoding="utf-8")
        (run / "RUN-LEDGER.md").write_text("## 2026-09-19 — Run opened (kickoff)\n", encoding="utf-8")
    (closed / "END-REPORT.md").write_text("done\n", encoding="utf-8")
    for name in _ht.POSITION_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    got = _ht.position_env("simple-harness", "1020-02-ELOOP", HANDOFF_PROMPT)
    assert got["SIMPLE_HARNESS_RUN_ID"] == "041"
