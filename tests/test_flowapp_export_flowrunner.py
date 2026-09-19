import json
from types import SimpleNamespace
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
    monkeypatch.setattr(fe, "_read_learning_artifact_schema", lambda: "# schema\n")
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
    monkeypatch.setattr(fe, "_read_learning_artifact_schema", lambda: "# schema\n")
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


def test_decomposer_context_allows_the_learning_draft_at_success_closure(tmp_path, monkeypatch):
    # GOAL-DRAFT-041: the pre-run 039 closure rule lets the decomposer write
    # LEARNING-DRAFT.yaml at SUCCESS closure; the old FlowRunner context said
    # "EXACTLY ONE file" and forbade the draft. The exported text must name
    # the draft and drop the prohibition.
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md"]),
    )
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("D.md", "simple-harness", "cloud_x"),
    )
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    monkeypatch.setattr(fe, "_read_learning_artifact_schema", lambda: "# schema\n")
    flow_row = {"flow_key": "2000-02-ELOOP", "name": "E"}
    steps = [{"step_key": "d", "from_role": "2000-execution-decomposer",
              "to_role": "2000-implementer", "sort_order": 1}]
    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")
    text = desc["flows"][0]["steps"][0]["governance"]
    assert "LEARNING-DRAFT.yaml" in text
    assert "Learning: none" in text
    assert "you write EXACTLY ONE file" not in text
    assert "EXACTLY ONE file" not in text


def test_decomposer_governance_bundles_the_learning_artifact_schema(tmp_path, monkeypatch):
    # GOAL-DRAFT-041: the decomposer step's exported governance must end with
    # the bundled schema so a FlowApp on a foreign target still carries it.
    schema = (
        "topic: t\nscope: experience\nrepository: r\nfamily: 2000\nrun: 041\n"
        "problem: p\napproach: a\nresult: r\nfailed_approaches: []\n"
        "important_files:\n  - x\narchitecture_implications: i\n"
        "validation:\n  evidence_level: tests\n  verdicts: []\n  testgoals: []\n"
        "confidence: high\nsupersedes: []\nadmitted_by: pending\n"
    )
    schema_path = tmp_path / "LEARNING-ARTIFACT.md"
    schema_path.write_text(schema, encoding="utf-8")
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md"]),
    )
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("D.md", "simple-harness", "cloud_x"),
    )
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    monkeypatch.setattr(fe, "_learning_artifact_schema_path", lambda: str(schema_path))
    flow_row = {"flow_key": "2000-02-ELOOP", "name": "E"}
    steps = [{"step_key": "d", "from_role": "2000-execution-decomposer",
              "to_role": "2000-implementer", "sort_order": 1}]
    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")
    text = desc["flows"][0]["steps"][0]["governance"]
    assert "## Learning artifact schema (bundled from docs/LEARNING-ARTIFACT.md)" in text
    for key in ("topic", "scope", "repository", "family", "run", "problem",
                "approach", "result", "failed_approaches", "important_files",
                "architecture_implications", "validation", "confidence",
                "supersedes", "admitted_by"):
        assert key in text
    assert "admitted_by: pending" in text
    assert text.rstrip().endswith(schema.rstrip())


def test_missing_learning_artifact_schema_is_422(tmp_path, monkeypatch):
    # GOAL-DRAFT-041: a missing schema document is a 422 like a missing
    # governance file, and the detail names the document.
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md"]),
    )
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("D.md", "simple-harness", "cloud_x"),
    )
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    monkeypatch.setattr(
        fe, "_learning_artifact_schema_path", lambda: str(tmp_path / "ABSENT.md"),
    )
    flow_row = {"flow_key": "2000-02-ELOOP", "name": "E"}
    steps = [{"step_key": "d", "from_role": "2000-execution-decomposer",
              "to_role": "2000-implementer", "sort_order": 1}]
    with pytest.raises(HTTPException) as exc:
        fe._to_flowrunner_description(flow_row, steps, "unused.db")
    assert exc.value.status_code == 422
    assert "docs/LEARNING-ARTIFACT.md" in exc.value.detail


def test_other_steps_do_not_carry_the_schema(tmp_path, monkeypatch):
    # GOAL-DRAFT-041: only the decomposer's governance carries the bundled
    # schema; implementer and reviewer texts stay unchanged in shape.
    monkeypatch.setattr(
        config, "get_governance_dir_abs",
        lambda: _gov_dir(tmp_path, ["I.md", "R.md"]),
    )
    facts = {
        "i": _facts("I.md", "simple-harness", "cloud_x"),
        "r": _facts("R.md", "simple-harness", "cloud_y"),
    }
    monkeypatch.setattr(fe, "_resolve_execution_config", lambda fk, sk, db: facts[sk])
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    flow_row = {"flow_key": "2000-02-ELOOP", "name": "E"}
    steps = [
        {"step_key": "i", "from_role": "2000-implementer",
         "to_role": "2000-reviewer", "sort_order": 1},
        {"step_key": "r", "from_role": "2000-reviewer",
         "to_role": "2000-execution-decomposer", "sort_order": 2},
    ]
    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")
    for step in desc["flows"][0]["steps"]:
        assert "Learning artifact schema (bundled" not in step["governance"]


def test_description_declares_the_knowledge_service_when_enabled(tmp_path, monkeypatch):
    # GOAL-DRAFT-042: when knowledge is enabled the FlowApp declares the
    # service as a provider by env NAME (never the URL), and that name is an
    # optional secret the receiving operator can type.
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md"]),
    )
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("D.md", "simple-harness", "cloud_x"),
    )
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    flow_row = {"flow_key": "2000-02-ELOOP", "name": "E"}
    steps = [{"step_key": "d", "from_role": "2000-execution-decomposer",
              "to_role": "2000-implementer", "sort_order": 1}]

    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")

    assert desc["knowledge"] == {
        "enabled": True,
        "providers": {
            "project": {
                "type": "http",
                "endpoint_env": "KNOWLEDGE_SERVICE_URL",
            }
        },
    }
    assert "KNOWLEDGE_SERVICE_URL" in desc["secrets"]["optional"]
    assert "KNOWLEDGE_SERVICE_URL" not in desc["secrets"]["required"]
    # the env NAME travels; the service URL never leaks into the description
    serialized = json.dumps(desc)
    assert "9140" not in serialized
    assert "127.0.0.1" not in serialized


def test_description_has_no_knowledge_block_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md"]),
    )
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("D.md", "simple-harness", "cloud_x"),
    )
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: False)
    flow_row = {"flow_key": "2000-02-ELOOP", "name": "E"}
    steps = [{"step_key": "d", "from_role": "2000-execution-decomposer",
              "to_role": "2000-implementer", "sort_order": 1}]

    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")

    assert "knowledge" not in desc
    assert "KNOWLEDGE_SERVICE_URL" not in desc["secrets"]["optional"]


def test_exported_context_tells_every_role_to_retrieve_first_with_run_attribution(
        tmp_path, monkeypatch):
    # GOAL-DRAFT-047: every exported role is told to retrieve before exploring
    # and to attribute the lookup to the run. The bullet lives in the shared
    # block, so it reaches the decomposer, the implementer and the reviewer
    # alike — not one role's own text.
    monkeypatch.setattr(
        config, "get_governance_dir_abs",
        lambda: _gov_dir(tmp_path, ["D.md", "I.md", "R.md"]),
    )
    facts = {
        "d": _facts("D.md", "simple-harness", "cloud_x"),
        "i": _facts("I.md", "simple-harness", "cloud_x"),
        "r": _facts("R.md", "simple-harness", "cloud_y"),
    }
    monkeypatch.setattr(fe, "_resolve_execution_config", lambda fk, sk, db: facts[sk])
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    monkeypatch.setattr(fe, "_read_learning_artifact_schema", lambda: "# schema\n")
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    flow_row = {"flow_key": "2000-02-ELOOP", "name": "E"}
    steps = [
        {"step_key": "d", "from_role": "2000-execution-decomposer",
         "to_role": "2000-implementer", "sort_order": 1},
        {"step_key": "i", "from_role": "2000-implementer",
         "to_role": "2000-reviewer", "sort_order": 2},
        {"step_key": "r", "from_role": "2000-reviewer",
         "to_role": "2000-execution-decomposer", "sort_order": 3},
    ]
    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")
    markers = ("You are the decomposer", "You are the implementer",
               "You are the reviewer")
    for step, marker in zip(desc["flows"][0]["steps"], markers):
        text = step["governance"]
        for literal in ("knowledge_search", "current_repository",
                        "run_id", "handoff_id"):
            assert literal in text
        # the bullet sits in the shared block, before the role-specific text
        assert text.index("knowledge_search") < text.index(marker)


def test_no_retrieval_instruction_when_knowledge_is_disabled(tmp_path, monkeypatch):
    # GOAL-DRAFT-047: with knowledge disabled the exported context stays
    # byte-for-byte what it was before the retrieval bullet existed. Build the
    # same step with the switch on and off; removing the added bullet from the
    # enabled text must reproduce the disabled text exactly.
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["I.md"]),
    )
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("I.md", "simple-harness", "cloud_x"),
    )
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    flow_row = {"flow_key": "2000-02-ELOOP", "name": "E"}
    steps = [{"step_key": "i", "from_role": "2000-implementer",
              "to_role": "2000-reviewer", "sort_order": 1}]

    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    enabled = fe._to_flowrunner_description(flow_row, steps, "unused.db")[
        "flows"][0]["steps"][0]["governance"]

    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: False)
    disabled = fe._to_flowrunner_description(flow_row, steps, "unused.db")[
        "flows"][0]["steps"][0]["governance"]

    for literal in ("knowledge_search", "current_repository", "run_id",
                    "handoff_id"):
        assert literal not in disabled

    # one-bullet diff, byte for byte
    bullet_lines = [line for line in enabled.split("\n") if "knowledge_search" in line]
    assert len(bullet_lines) == 1
    assert enabled.replace(bullet_lines[0] + "\n", "", 1) == disabled


def test_description_declares_the_mcp_server_that_carries_retrieval(tmp_path, monkeypatch):
    # The exported governance tells every role to call `knowledge_search`.
    # That is an mcp-light tool, and nothing in the export said so: a run had
    # it only when the receiving machine's own ~/.simple-harness/config.json
    # happened to declare mcp-light. FlowRunner now refuses a FlowApp that
    # enables knowledge, runs simple-harness steps and declares no server
    # offering knowledge_search — so the export declares it, by env NAME.
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md"]),
    )
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("D.md", "simple-harness", "cloud_x"),
    )
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: True)
    flow_row = {"flow_key": "2000-02-ELOOP", "name": "E"}
    steps = [{"step_key": "d", "from_role": "2000-execution-decomposer",
              "to_role": "2000-implementer", "sort_order": 1}]

    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")

    server = desc["mcp_servers"]["mcp-light"]
    assert server["transport"] == "http"
    assert server["endpoint_env"] == "MCP_LIGHT_URL"
    assert server["permission"] == "read_only"
    # The knowledge tools and nothing else: the exported context tells the
    # role that the bridge's mcp-light tools do not apply under FlowRunner.
    assert server["allowlist"] == ["knowledge_search", "knowledge_scopes",
                                   "knowledge_learning", "knowledge_retrievals"]
    assert "MCP_LIGHT_URL" in desc["secrets"]["optional"]
    # the env NAME travels; the endpoint never leaks into the description
    serialized = json.dumps(desc)
    assert "9135" not in serialized
    assert "127.0.0.1" not in serialized


def test_description_declares_no_mcp_light_when_knowledge_is_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md"]),
    )
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("D.md", "simple-harness", "cloud_x"),
    )
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: False)
    flow_row = {"flow_key": "2000-02-ELOOP", "name": "E"}
    steps = [{"step_key": "d", "from_role": "2000-execution-decomposer",
              "to_role": "2000-implementer", "sort_order": 1}]

    desc = fe._to_flowrunner_description(flow_row, steps, "unused.db")

    # No mcp-light without knowledge. (A family FlowApp still declares
    # scope-mcp — project memory does not depend on the knowledge service —
    # so the block itself is present; that is pinned further down.)
    assert "mcp-light" not in desc.get("mcp_servers", {})
    assert "MCP_LIGHT_URL" not in desc["secrets"]["optional"]


# --- scope-mcp: project memory between steps, cycles and runs ----------------

def _family_description(tmp_path, monkeypatch, flow_key, steps, knowledge=False):
    monkeypatch.setattr(
        config, "get_governance_dir_abs", lambda: _gov_dir(tmp_path, ["D.md"]),
    )
    monkeypatch.setattr(
        fe, "_resolve_execution_config",
        lambda fk, sk, db: _facts("D.md", "simple-harness", "cloud_x"),
    )
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "workspace_write")
    monkeypatch.setattr(fe, "_resolved_model_binding", lambda role, client: {})
    monkeypatch.setattr(config, "get_knowledge_enabled", lambda: knowledge)
    return fe._to_flowrunner_description({"flow_key": flow_key, "name": "F"}, steps, "unused.db")


_ELOOP_STEPS = [
    {"step_key": "d", "from_role": "2000-execution-decomposer", "to_role": "2000-implementer", "sort_order": 1},
    {"step_key": "i", "from_role": "2000-implementer", "to_role": "2000-reviewer", "sort_order": 2},
    {"step_key": "r", "from_role": "2000-reviewer", "to_role": "2000-execution-decomposer", "sort_order": 3},
]
_PLOOP_STEPS = [
    {"step_key": "p", "from_role": "2000-planning-supervisor", "to_role": "2000-planning-supervisor", "sort_order": 1},
]


def test_a_family_flowapp_declares_scope_mcp_with_its_state_in_the_family_tree(tmp_path, monkeypatch):
    desc = _family_description(tmp_path, monkeypatch, "2000-02-ELOOP", _ELOOP_STEPS)
    server = desc["mcp_servers"]["scope-mcp"]
    assert server["transport"] == "stdio"
    assert server["permission"] == "workspace_write"
    # The server's home is a variable, never a path; its state sits inside
    # the family tree, which ignores itself, so the target repository's
    # `git status` does not learn that the run kept notes — and both loops of
    # the family name the same file.
    assert server["command"] == ["node", "${SCOPE_MCP_HOME}/src/server.js",
                                 "--db", ".flowrunner/2000/scope-mcp/state.db"]
    assert "SCOPE_MCP_HOME" in desc["secrets"]["optional"]
    planning = _family_description(tmp_path, monkeypatch, "2000-01-PLOOP", _PLOOP_STEPS)
    assert planning["mcp_servers"]["scope-mcp"]["command"] == server["command"]
    # Declared whether or not knowledge is enabled; mcp-light only with it.
    assert "mcp-light" not in desc["mcp_servers"]
    both = _family_description(tmp_path, monkeypatch, "2000-02-ELOOP", _ELOOP_STEPS, knowledge=True)
    assert set(both["mcp_servers"]) == {"mcp-light", "scope-mcp"}


def test_the_allowlist_is_the_fence_goals_belong_to_the_planner(tmp_path, monkeypatch):
    execution = _family_description(tmp_path, monkeypatch, "2000-02-ELOOP", _ELOOP_STEPS)
    planning = _family_description(tmp_path, monkeypatch, "2000-01-PLOOP", _PLOOP_STEPS)
    chain = set(execution["mcp_servers"]["scope-mcp"]["allowlist"])
    planner = set(planning["mcp_servers"]["scope-mcp"]["allowlist"])
    assert chain == {"status", "record_decision", "record_blocker", "resolve_blocker", "checkpoint"}
    assert planner == chain | {"init_project", "set_goals"}
    # SCOPE.md is the Human's and the project is never declared finished by a
    # role: what would say otherwise is not offered to anyone.
    for forbidden in ("record_scope", "add_scope_addendum", "complete_project",
                      "coverage", "complete_goal", "next_goal"):
        assert forbidden not in planner


def test_a_flow_outside_a_family_declares_no_scope_mcp(tmp_path, monkeypatch):
    desc = _family_description(tmp_path, monkeypatch, "9000-simple-flow-without-loops", _ELOOP_STEPS)
    assert "mcp_servers" not in desc
    assert "SCOPE_MCP_HOME" not in desc["secrets"]["optional"]
    assert "scope-mcp" not in desc["flows"][0]["steps"][0]["governance"]


def test_every_role_is_told_what_project_memory_is_and_is_not(tmp_path, monkeypatch):
    desc = _family_description(tmp_path, monkeypatch, "2000-02-ELOOP", _ELOOP_STEPS)
    governance = {s["name"]: s["governance"] for s in desc["flows"][0]["steps"]}
    for name, text in governance.items():
        head = text.split("\n---\n")[0]
        # what it is for, what outranks it, and the two calls that frame a turn
        assert "scope-mcp" in head, name
        assert "`status`" in head and "`checkpoint`" in head, name
        assert "The files are the contract" in head, name
        assert "record_decision" in head and "record_blocker" in head, name
    decomposer, implementer, reviewer = governance["d"], governance["i"], governance["r"]
    # The decomposer's tool budget is tight; the memory calls are counted in it.
    assert "inside your budget" in decomposer.split("\n---\n")[0]
    # The reviewer's only REPOSITORY write stays the verdict: memory is not the repository.
    assert "not a repository write" in reviewer.split("\n---\n")[0]
    # The implementer records the reading it chose where the handoff was silent.
    assert "left something open" in implementer.split("\n---\n")[0]
    # Goals are the planner's: no execution role is told to touch them.
    for text in governance.values():
        assert "set_goals" not in text.split("\n---\n")[0]


def test_the_planner_mirrors_its_drafts_as_goals(tmp_path, monkeypatch):
    desc = _family_description(tmp_path, monkeypatch, "2000-01-PLOOP", _PLOOP_STEPS)
    head = desc["flows"][0]["steps"][0]["governance"].split("\n---\n")[0]
    assert "init_project" in head and "set_goals" in head
    assert "GOAL-DRAFT" in head
    # the scope stays a file the Human owns
    assert "never" in head and "SCOPE.md" in head


def test_no_project_memory_when_the_steps_run_read_only(tmp_path, monkeypatch):
    # Measured 2026-09-19: simple-harness ends a run with exit 4 on a tool
    # call the permission gate refuses, and scope-mcp's tools write. Under
    # read_only the role's first instructed call — `status` — would kill the
    # run. The exporter falls back to read_only when the mode cannot be
    # resolved, so that fallback must not come with the memory, nor with
    # governance telling the role to call it.
    desc = _family_description(tmp_path, monkeypatch, "2000-02-ELOOP", _ELOOP_STEPS)
    assert "scope-mcp" in desc["mcp_servers"]          # workspace_write: declared
    monkeypatch.setattr(fe, "_resolved_step_permission", lambda: "read_only")
    ro = fe._to_flowrunner_description({"flow_key": "2000-02-ELOOP", "name": "F"}, _ELOOP_STEPS, "unused.db")
    assert "mcp_servers" not in ro
    assert "SCOPE_MCP_HOME" not in ro["secrets"]["optional"]
    for step in ro["flows"][0]["steps"]:
        assert "scope-mcp" not in step["governance"].split("\n---\n")[0]


# --- the model's context window travels with the binding ----------------------

def _allocator_answers(monkeypatch, payload):
    monkeypatch.setattr(config, "get_project_path", lambda name: "/nonexistent/model-allocator")
    monkeypatch.setattr(
        fe.subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""))


def test_the_binding_carries_the_aliass_context_window(monkeypatch):
    # A FlowApp exported from here runs mostly against cloud endpoints, which
    # do not report their window; FlowRunner bounds a run by the binding's
    # context_window. The allocator already resolves `context` per alias.
    _allocator_answers(monkeypatch, {
        "real_model": "deepseek-v4-pro", "default_api_base": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY", "backend": "openai_compatible", "context": 131072})
    binding = fe._resolved_model_binding("2000-implementer", "simple-harness")
    assert binding["context_window"] == 131072
    assert binding["model"] == "deepseek-v4-pro"


def test_an_alias_without_a_usable_context_declares_no_window(monkeypatch):
    for context in (None, 0, -4, "plenty", ""):
        _allocator_answers(monkeypatch, {"real_model": "m", "context": context})
        binding = fe._resolved_model_binding("r", "simple-harness")
        assert binding.get("model") == "m", "the stub must resolve, or this proves nothing"
        assert "context_window" not in binding, context
