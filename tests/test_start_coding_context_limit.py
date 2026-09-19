"""A BridgeV002 simple-harness role runs bounded by its model's context window.

simple-harness bounds a run (pruning, compaction) only when it knows the
model's window. It asks the runtime, and a local runtime usually answers; a
cloud API's /v1/models names the model and nothing else, so against one the
limit stays unknown and the lifecycle accounts without bounding. The allocator
already carries `context` for every alias; the launch never passed it on, so
the cloud roles — the ones whose tokens cost money — ran unbounded.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import start_coding  # noqa: E402

SRC = (PROJECT_ROOT / "scripts" / "bridgeV002" / "start_coding.py").read_text()
NAME = "SIMPLE_HARNESS_CONTEXT_MODEL_LIMIT"


def test_the_aliass_context_becomes_the_configured_limit():
    assert start_coding.context_limit_env({"context": 131072}) == {NAME: "131072"}
    # the allocator's JSON may carry it as a string
    assert start_coding.context_limit_env({"context": "65536"}) == {NAME: "65536"}


def test_what_the_alias_does_not_say_is_not_set():
    for resolved in ({}, {"context": None}, {"context": 0}, {"context": -1},
                     {"context": "plenty"}, {"context": ""}):
        assert start_coding.context_limit_env(resolved) == {}, resolved


def test_it_is_the_configured_limit_not_the_flag():
    # simple-harness reconciles a CONFIGURED limit with what the runtime
    # reports by taking the smaller; --context-limit skips that probe and
    # would override a local runtime serving the model with a smaller window
    # than the alias declares.
    assert "--context-limit" not in SRC


def test_the_launch_block_applies_it_from_the_resolved_alias():
    # beside the other per-alias harness settings, inside the same branch
    assert SRC.index("SIMPLE_HARNESS_MAX_OUTPUT_TOKENS") < SRC.index("child_env.update(context_limit_env(resolved")


# --- the per-role context budget (migration 115) ------------------------------

def test_the_smaller_of_window_and_budget_bounds_the_role():
    # A 1,000,000-token window bounds nothing a run will reach; the budget is
    # what the role MAY use.
    assert start_coding.context_limit_env({"context": 1000000}, 131072) == {NAME: "131072"}
    # A budget above the window cannot enlarge the window.
    assert start_coding.context_limit_env({"context": 65536}, 131072) == {NAME: "65536"}
    # A budget alone still bounds a role whose alias declares no window.
    assert start_coding.context_limit_env({}, 32768) == {NAME: "32768"}
    # No budget: the window, as before migration 115.
    assert start_coding.context_limit_env({"context": 131072}, None) == {NAME: "131072"}


def test_a_budget_that_is_not_a_positive_number_is_no_budget():
    for budget in (0, -1, "", "lots", None):
        assert start_coding.context_limit_env({"context": 131072}, budget) == {NAME: "131072"}, budget
    assert start_coding.context_limit_env({}, 0) == {}


def test_the_launch_block_passes_the_roles_budget():
    assert 'child_env.update(context_limit_env(resolved, role.get("context_budget")))' in SRC


def test_get_flow_roles_returns_the_budget(tmp_path):
    import sqlite3
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE bridge_flow_steps (flow_key TEXT, step_key TEXT, from_role TEXT, to_role TEXT,
                                        sort_order INTEGER, is_active INTEGER DEFAULT 1);
        CREATE TABLE bridge_roles (role_key TEXT PRIMARY KEY, tmux_session TEXT, is_active INTEGER DEFAULT 1,
            role_type TEXT DEFAULT 'agent', default_model_source TEXT, default_model_alias TEXT,
            max_output_tokens INTEGER, config_dir TEXT, allocator_client TEXT, workdir_mode TEXT,
            execution_target TEXT, default_harness_source TEXT, default_harness_profile TEXT,
            max_turns INTEGER, context_budget INTEGER);
        INSERT INTO bridge_flow_steps VALUES ('f', 's', 'with-budget', 'without', 1, 1);
        INSERT INTO bridge_roles (role_key, tmux_session, context_budget) VALUES ('with-budget', 's1', 131072);
        INSERT INTO bridge_roles (role_key, tmux_session) VALUES ('without', 's2');
    """)
    conn.commit()
    conn.close()
    roles = {r["role_key"]: r for r in start_coding.get_flow_roles(str(db), "f")}
    assert roles["with-budget"]["context_budget"] == 131072
    assert roles["without"]["context_budget"] is None
