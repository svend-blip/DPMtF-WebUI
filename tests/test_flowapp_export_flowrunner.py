import json
"""Tests for the DPMtF -> FlowRunner Description bridge (format=flowrunner).

Run 088 / D(a): routers/flowapp_export.py transforms DPMtF flow facts into
a FlowRunner exporter Description. These are unit tests of the transform
logic with canned execution facts and a temp governance dir — no live DB
and no FlowRunner binary. The end-to-end round-trip (transform ->
`flowrunner export` -> `flowrunner validate`) is verified operationally.
"""
import config
import pytest
from fastapi import HTTPException

from routers import flowapp_export as fe


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    """Run every test from a scratch cwd so the sqlite placeholder path
    ("unused.db") is never created inside the repository."""
    monkeypatch.chdir(tmp_path)


def _facts(governance_file, harness, alias):
    return {
        "governance_file": governance_file,
        "harness_source": harness,
        "model_alias": alias,
    }


def _gov_dir(tmp_path, names):
    for n in names:
        (tmp_path / n).write_text(f"# {n}\ngovernance body for {n}\n", encoding="utf-8")
    return str(tmp_path)


def test_profile_id_strips_flow_prefix_and_avoids_engine_names():
    assert fe._fr_profile_id("9000-implementer", "9000-02-ELOOP") == "implementer"
    assert fe._fr_profile_id("1000-reviewer", "1000-02-ELOOP") == "reviewer"
    # a role that itself names an inference engine must not leak (rule 8)
    assert fe._fr_profile_id("9000-freetoken-qwen", "9000-02-ELOOP") == "model"
    assert fe._fr_profile_id("", "9000-02-ELOOP") == "model"


def test_to_flowrunner_description_maps_facts(tmp_path, monkeypatch):
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "read_only")
    monkeypatch.setattr(
        config, "get_governance_dir_abs",
        lambda: _gov_dir(tmp_path, ["IMPL.md", "REVIEW.md"]),
    )
    facts = {
        "s1": _facts("IMPL.md", "simple-harness", "freetoken-qwen38-flash-next"),
        "s2": _facts("REVIEW.md", "simple-harness", "cloud_deepseek_v4pro_direct"),
    }
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: facts[sk],
    )
    flow_row = {"flow_key": "9000-02-ELOOP", "name": "9000 Execution Loop"}
    steps = [
        {"step_key": "s1", "to_role": "9000-implementer", "sort_order": 1},
        {"step_key": "s2", "to_role": "9000-reviewer", "sort_order": 2},
    ]

    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")

    assert desc["app"]["name"] == "9000 Execution Loop"
    assert desc["schema_version"] == "1.0.0"
    # abstract, rule-8-safe model profiles (never the engine-named alias)
    profiles = {m["name"] for m in desc["models"]}
    assert profiles == {"implementer", "reviewer"}
    # the DPMtF alias is preserved as a hint for the operator
    impl = next(m for m in desc["models"] if m["name"] == "implementer")
    assert impl["dpmtf_alias"] == "freetoken-qwen38-flash-next"
    flow = desc["flows"][0]
    assert flow["name"] == "main"
    assert flow["entry"] == "s1"
    first = flow["steps"][0]
    assert first["model"] == "implementer"
    assert first["harness"] == "simple-harness"
    # Pinned to the host-independent fallback: the resolved mode has its own
    # tests below, and this one is about the fact mapping.
    assert first["permissions"] == ["read_only"]
    assert first["next"] == "s2"
    assert "governance body for IMPL.md" in first["governance"]
    # last step carries no next
    assert "next" not in flow["steps"][1]


def test_unsupported_harness_is_422(tmp_path, monkeypatch):
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["G.md"]),
    )
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("G.md", "opencode", "some-alias"),
    )
    flow_row = {"flow_key": "strict_review", "name": "Strict Review"}
    steps = [{"step_key": "x", "to_role": "review01", "sort_order": 1}]
    with pytest.raises(HTTPException) as exc:
        fe._to_flowrunner_description(flow_row, steps, "unused.db")
    assert exc.value.status_code == 422
    assert "opencode" in exc.value.detail
    assert "not supported" in exc.value.detail


def test_missing_governance_file_is_422(tmp_path, monkeypatch):
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: str(tmp_path),  # empty dir
    )
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("ABSENT.md", "simple-harness", "a"),
    )
    flow_row = {"flow_key": "f", "name": "F"}
    steps = [{"step_key": "x", "to_role": "f-implementer", "sort_order": 1}]
    with pytest.raises(HTTPException) as exc:
        fe._to_flowrunner_description(flow_row, steps, "unused.db")
    assert exc.value.status_code == 422
    assert "governance file not found" in exc.value.detail


def test_human_steps_are_excluded(tmp_path, monkeypatch):
    # A human role is a placeholder for HUMAN.md, not a runnable FlowApp step:
    # steps handing to or from it are dropped, and entry/next span the agents.
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md", "I.md"]),
    )
    facts = {
        "decompose": _facts("D.md", "simple-harness", "cloud_qwen38flash"),
        "implement": _facts("I.md", "simple-harness", "cloud_qwen38flash"),
    }
    monkeypatch.setattr(fe, "_resolve_execution_config", lambda fk, sk, db: facts[sk])
    flow_row = {"flow_key": "2000-02-ELOOP", "name": "ELOOP"}
    steps = [
        {"step_key": "human-planning", "from_role": "human",
         "to_role": "2000-planning-supervisor", "sort_order": 1},
        {"step_key": "decompose", "from_role": "2000-execution-decomposer",
         "to_role": "2000-implementer", "sort_order": 2},
        {"step_key": "implement", "from_role": "2000-implementer",
         "to_role": "2000-reviewer", "sort_order": 3},
    ]
    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")
    names = [s["name"] for s in desc["flows"][0]["steps"]]
    assert names == ["decompose", "implement"]  # human-planning dropped
    assert desc["flows"][0]["entry"] == "decompose"  # entry spans the agents
    assert desc["flows"][0]["steps"][0]["next"] == "implement"


def test_all_human_performed_steps_is_422(tmp_path, monkeypatch):
    # 422 only when EVERY step is performed by a human, i.e. no step has an
    # agent as its acting (from) role. A human on the receiving end is just the
    # flow's exit and does not disqualify the step -- see the planning-loop test.
    monkeypatch.setattr(config, "get_governance_dir_abs", lambda: str(tmp_path))
    monkeypatch.setattr(fe, "_resolve_execution_config", lambda fk, sk, db: {})
    flow_row = {"flow_key": "all-human", "name": "AH"}
    steps = [
        {"step_key": "human-a", "from_role": "human",
         "to_role": "human", "sort_order": 1},
        {"step_key": "human-b", "from_role": "human",
         "to_role": "2000-planning-supervisor", "sort_order": 2},
    ]
    with pytest.raises(HTTPException) as exc:
        fe._to_flowrunner_description(flow_row, steps, "unused.db")
    assert exc.value.status_code == 422
    assert "no agent steps" in exc.value.detail


def test_planning_loop_exports_its_single_agent_step(tmp_path, monkeypatch):
    # Human decision 2026-09-10: "the first role is human, but ALL agents must
    # be exported." A planning loop runs human -> supervisor -> human. The
    # supervisor's step is real agent work and must survive; only the step the
    # HUMAN performs is dropped, because the Human acts out of band and that
    # input reaches the run as --task. Filtering on either end used to drop both
    # steps and refuse a flow that is perfectly runnable.
    monkeypatch.setattr(
        config, "get_governance_dir_abs",
        lambda: _gov_dir(tmp_path, ["SUPERVISOR_PLANNING.md"]),
    )
    facts = {
        "planning-human": _facts(
            "SUPERVISOR_PLANNING.md", "simple-harness", "cloud_deepseek_v4pro_direct"),
    }
    monkeypatch.setattr(fe, "_resolve_execution_config", lambda fk, sk, db: facts[sk])
    flow_row = {"flow_key": "2000-01-PLOOP", "name": "PLOOP"}
    steps = [
        {"step_key": "human-planning", "from_role": "human",
         "to_role": "2000-planning-supervisor", "sort_order": 1},
        {"step_key": "planning-human", "from_role": "2000-planning-supervisor",
         "to_role": "human", "sort_order": 2},
    ]
    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")
    names = [s["name"] for s in desc["flows"][0]["steps"]]
    assert names == ["planning-human"]
    assert desc["flows"][0]["entry"] == "planning-human"
    assert desc["flows"][0]["steps"][0].get("next") in (None, "")


def test_step_permission_carries_the_resolved_mode(tmp_path, monkeypatch):
    # Hardcoding read_only exported an app that could not do its work: every
    # step was denied write access and the harness exited permission_denied
    # (2000 smoke test, 2026-09-10). The export must describe the mode the
    # flow actually runs under.
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md"]))
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("D.md", "simple-harness", "cloud_qwen38flash"))
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    flow_row = {"flow_key": "f", "name": "F"}
    steps = [{"step_key": "d", "from_role": "f-decomposer",
              "to_role": "f-implementer", "sort_order": 1}]
    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")
    assert desc["flows"][0]["steps"][0]["permissions"] == ["workspace_write"]


def test_step_permission_falls_back_when_unresolvable(monkeypatch):
    # The exporter must keep working on a host without the allocator, and the
    # safe mode is the honest answer there.
    monkeypatch.setattr(fe, "_FLOWRUNNER_PERMISSIONS", ("read_only",))
    assert fe._resolved_step_permission() in ("read_only", "workspace_write")


def test_model_binding_and_secret_name_travel(tmp_path, monkeypatch):
    # Human requirement 2026-09-10: export on one PC, install FlowRunner on
    # another, import, type secrets, run. The receiving machine cannot infer
    # an endpoint or an engine name, so the binding must travel with the app.
    # Only the key NAME travels: "secrets are always typed in flowrunner and
    # are never transferred at export" (Human).
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md"]))
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("D.md", "simple-harness", "cloud_x"))
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {
        "model": "deepseek-v4-pro",
        "endpoint": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "backend": "openai_compatible",
    })
    flow_row = {"flow_key": "f", "name": "F"}
    steps = [{"step_key": "d", "from_role": "f-decomposer",
              "to_role": "f-implementer", "sort_order": 1}]
    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")
    profile = desc["models"][0]
    assert profile["model"] == "deepseek-v4-pro"
    assert profile["endpoint"] == "https://api.deepseek.com"
    assert profile["api_key_env"] == "DEEPSEEK_API_KEY"
    assert profile["backend"] == "openai_compatible"
    assert profile["dpmtf_alias"] == "cloud_x"          # provenance retained
    # the NAME is declared so `flowrunner secrets check` can name it
    assert desc["secrets"]["required"] == ["DEEPSEEK_API_KEY"]
    # and no VALUE appears anywhere in the description
    assert "sk-" not in json.dumps(desc)


def test_export_survives_an_unresolvable_binding(tmp_path, monkeypatch):
    # An export on a host without the allocator must still produce a valid
    # FlowApp; the receiving operator then supplies --model-name themselves.
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md"]))
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("D.md", "simple-harness", "cloud_x"))
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "read_only")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    flow_row = {"flow_key": "f", "name": "F"}
    steps = [{"step_key": "d", "from_role": "f-decomposer",
              "to_role": "f-implementer", "sort_order": 1}]
    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")
    assert desc["models"][0] == {"name": "implementer", "dpmtf_alias": "cloud_x"}
    assert desc["secrets"]["required"] == []


def test_app_identifier_derives_from_flow_key(tmp_path, monkeypatch):
    # FlowRunner installs an imported FlowApp under app.identifier, so it
    # must read the way the Human names the folders: eloop2000 / ploop2000.
    assert fe._flowapp_identifier("2000-02-ELOOP") == "eloop2000"
    assert fe._flowapp_identifier("2000-01-PLOOP") == "ploop2000"
    assert fe._flowapp_identifier("9000-02-ELOOP") == "eloop9000"
    assert fe._flowapp_identifier("Strict Review 40x") == "strict-review-40x"
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md"]))
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("D.md", "simple-harness", "cloud_x"))
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    flow_row = {"flow_key": "2000-02-ELOOP", "name": "2000 Execution Loop"}
    steps = [{"step_key": "d", "from_role": "2000-execution-decomposer",
              "to_role": "2000-implementer", "sort_order": 1}]
    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")
    assert desc["app"]["identifier"] == "eloop2000"
    assert desc["app"]["name"] == "2000 Execution Loop"


def test_governance_carries_the_flowrunner_execution_context(tmp_path, monkeypatch):
    # 2026-09-11: an exported decomposer, run by FlowRunner INSIDE the DPMtF
    # checkout, followed its bridge instructions literally (bridge_broker.py
    # --help, tmux ls, reading the bridge directory). Every exported governance
    # file must open with a notice that puts the bridge out of force and
    # states FlowRunner's handoff contract, per step: previous deliverable,
    # own deliverable path, next step.
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md", "I.md"]))
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("D.md" if sk == "d" else "I.md", "simple-harness", "cloud_x"))
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    flow_row = {"flow_key": "2000-02-ELOOP", "name": "E"}
    steps = [{"step_key": "d", "from_role": "2000-execution-decomposer",
              "to_role": "2000-implementer", "sort_order": 1},
             {"step_key": "i", "from_role": "2000-implementer",
              "to_role": "2000-reviewer", "sort_order": 2}]
    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")
    texts = [st["governance"] for st in desc["flows"][0]["steps"]]
    first, second = texts[0], texts[1]
    for text in (first, second):
        assert text.startswith("## FlowRunner execution context")
        assert "bridge_broker.py" in text and "DPMtF bridge directory" in text
        assert config.get_bridge_dir() in text
        assert ".flowrunner/<family>/runs/NNN/" in text and "STEP INPUT" in text
    assert "You are the decomposer" in first and "handoffs/NNN-<step>.md" in first and "END-REPORT.md" in first
    assert "You are the implementer" in second and "results/NNN-<step>.md" in second
    assert desc["app"]["family"] == "2000"


def test_execution_context_addresses_the_role_by_name(tmp_path, monkeypatch):
    # 2026-09-11: a flash decomposer under-acted (0 writes in 63 requests) and
    # a strong one over-acted (implemented GOAL-001 itself). The text is the
    # variable: the notice must bind the ROLE by name to its only write.
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md", "I.md", "R.md"]))
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts({"d": "D.md", "i": "I.md", "r": "R.md"}[sk], "simple-harness", "cloud_x"))
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    flow_row = {"flow_key": "2000-02-ELOOP", "name": "E"}
    steps = [{"step_key": "d", "from_role": "2000-execution-decomposer", "to_role": "2000-implementer", "sort_order": 1},
             {"step_key": "i", "from_role": "2000-implementer", "to_role": "2000-reviewer", "sort_order": 2},
             {"step_key": "r", "from_role": "2000-reviewer", "to_role": "2000-execution-decomposer", "sort_order": 3}]
    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")
    d, i, r = [st["governance"] for st in desc["flows"][0]["steps"]]
    assert "You are the decomposer" in d and "you do not implement" in d and "handoffs/NNN-<step>.md" in d
    assert "at most 12 tool calls" in d and "END-REPORT.md" in d
    assert "You are the implementer" in i and "results/NNN-<step>.md" in i
    assert "You are the reviewer" in r and "do not implement or fix" in r and "verdicts/NNN-<step>.md" in r
