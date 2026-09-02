"""Shipped example flows (migration 091) work on a fresh database.

PLAN-example-flows.md: a fresh clone must carry a complete, cloud-only
flow catalogue — example-cloud (1-flow principle) and the
example-01-PLOOP / example-02-ELOOP pair (2-flow principle). These tests
run the full migration chain against an empty database, the way a new
installation does, and assert the seeded rows are self-contained: every
referenced governance file ships in the repo, every referenced gate
script is registered AND present on disk, and nothing points at a
machine-specific path.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import migrate

EXAMPLE_FLOWS = {"example-cloud", "example-01-PLOOP", "example-02-ELOOP"}
EXAMPLE_ROLES = {
    "ex-super-cl",
    "ex-imple-cl",
    "ex-review-cl",
    "example-planning-supervisor",
    "example-execution-decomposer",
    "example-implementer",
    "example-reviewer",
    "example-escalation-supervisor",
}
GOVERNANCE_DIR = PROJECT_ROOT / "docs" / "governance-templates-v2"
MIGRATION_091 = PROJECT_ROOT / "scripts" / "db" / "091_example_cloud_flows.sql"
MIGRATION_093 = PROJECT_ROOT / "scripts" / "db" / "093_9010_flows.sql"


@pytest.fixture(scope="module")
def fresh_db(tmp_path_factory):
    """A database built the way a new installation builds one."""
    db_path = str(tmp_path_factory.mktemp("example_seed") / "fresh.db")
    migrate.run_migrations(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def test_example_flows_seeded_standard_and_portable(fresh_db):
    rows = fresh_db.execute(
        "SELECT flow_key, ui_category, target_project_path, supervisor_role"
        " FROM bridge_flows WHERE flow_key IN (?, ?, ?)",
        sorted(EXAMPLE_FLOWS),
    ).fetchall()
    assert {r["flow_key"] for r in rows} == EXAMPLE_FLOWS
    for row in rows:
        assert row["ui_category"] == "standard", row["flow_key"]
        # NULL target_project_path is the portability contract: the
        # examples must not require any repo beyond this one.
        assert row["target_project_path"] is None, row["flow_key"]
        assert row["supervisor_role"] in EXAMPLE_ROLES, row["flow_key"]


def test_ploop_eloop_share_artifact_root(fresh_db):
    roots = dict(
        fresh_db.execute(
            "SELECT flow_key, artifact_root FROM bridge_flows"
            " WHERE flow_key IN ('example-01-PLOOP', 'example-02-ELOOP')"
        ).fetchall()
    )
    assert roots == {"example-01-PLOOP": "example", "example-02-ELOOP": "example"}


def test_example_roles_cloud_only_single_credential(fresh_db):
    rows = fresh_db.execute(
        "SELECT role_key, default_model_source, default_model_alias,"
        " default_harness_source, workdir_mode, governance_file"
        " FROM bridge_roles WHERE role_key IN ({})".format(
            ",".join("?" * len(EXAMPLE_ROLES))
        ),
        sorted(EXAMPLE_ROLES),
    ).fetchall()
    assert {r["role_key"] for r in rows} == EXAMPLE_ROLES
    for row in rows:
        # PLAN §6.2: one combo everywhere so one API key suffices.
        assert row["default_model_source"] == "model_allocator", row["role_key"]
        assert row["default_model_alias"] == "cloud_minimax", row["role_key"]
        assert row["default_harness_source"] == "opencode", row["role_key"]
        assert row["workdir_mode"] == "father", row["role_key"]
        governance = GOVERNANCE_DIR / row["governance_file"]
        assert governance.is_file(), (
            f"{row['role_key']} references {row['governance_file']},"
            f" which does not ship in docs/governance-templates-v2/"
        )


def test_example_steps_reference_shipped_governance_and_gates(fresh_db):
    steps = fresh_db.execute(
        "SELECT flow_key, step_key, from_role, to_role, governance_file,"
        " pre_dispatch_script, deliverable_dir FROM bridge_flow_steps"
        " WHERE flow_key IN (?, ?, ?)",
        sorted(EXAMPLE_FLOWS),
    ).fetchall()
    per_flow = {}
    for step in steps:
        per_flow.setdefault(step["flow_key"], []).append(step)
    assert {k: len(v) for k, v in per_flow.items()} == {
        "example-cloud": 3,
        "example-01-PLOOP": 2,
        "example-02-ELOOP": 3,
    }
    registered = {
        row["script_key"]
        for row in fresh_db.execute("SELECT script_key FROM bridge_scripts")
    }
    for step in steps:
        label = f"{step['flow_key']}/{step['step_key']}"
        assert (GOVERNANCE_DIR / step["governance_file"]).is_file(), label
        # Relative deliverable dirs only — resolved under the bridge dir.
        assert not step["deliverable_dir"].startswith("/"), label
        for role in (step["from_role"], step["to_role"]):
            assert role == "human" or role in EXAMPLE_ROLES, label
        gate = step["pre_dispatch_script"]
        if gate:
            assert gate in registered, (
                f"{label} references unregistered gate {gate!r}"
            )
            gate_path = fresh_db.execute(
                "SELECT path FROM bridge_scripts WHERE script_key = ?", (gate,)
            ).fetchone()["path"]
            assert (PROJECT_ROOT / gate_path).is_file(), (
                f"{label}: gate {gate!r} registered at {gate_path},"
                f" but the script does not ship in the repo"
            )


def test_gate_deliverable_evidence_registered_on_fresh_db(fresh_db):
    # The row was hand-registered in the live DB on 2026-08-05 and never
    # migrated; 091 fixes that. Guard it so fresh installs keep working.
    row = fresh_db.execute(
        "SELECT path FROM bridge_scripts WHERE script_key = 'gate-deliverable-evidence'"
    ).fetchone()
    assert row is not None
    assert (PROJECT_ROOT / row["path"]).is_file()


def test_seed_sql_carries_no_machine_paths():
    # The governance no-hardcoded-paths guard does not cover
    # scripts/db/*.sql; hold the shipped seeds (091 examples, 093 9010)
    # to it.
    for migration in (MIGRATION_091, MIGRATION_093):
        assert "/home/svend" not in migration.read_text(encoding="utf-8"), (
            migration.name
        )


def test_9010_flows_seeded_experimental_and_self_contained(fresh_db):
    """Migration 093: the 9010 DeepSeek/Codex pair ships on fresh DBs."""
    flows = {
        r["flow_key"]: r
        for r in fresh_db.execute(
            "SELECT flow_key, ui_category, artifact_root,"
            " target_project_path, supervisor_role FROM bridge_flows"
            " WHERE flow_key IN ('9010-01-PLOOP', '9010-02-ELOOP')"
        )
    }
    assert set(flows) == {"9010-01-PLOOP", "9010-02-ELOOP"}
    for row in flows.values():
        assert row["ui_category"] == "experimental", row["flow_key"]
        assert row["artifact_root"] == "9010", row["flow_key"]
        assert row["target_project_path"] is None, row["flow_key"]
    assert flows["9010-01-PLOOP"]["supervisor_role"] == "9010-planning-supervisor"
    # Migration 097: both rows of a family wake the resident planning supervisor.
    assert flows["9010-02-ELOOP"]["supervisor_role"] == "9010-planning-supervisor"

    roles = {
        r["role_key"]: r
        for r in fresh_db.execute(
            "SELECT role_key, default_model_source, default_model_alias,"
            " allocator_client, default_harness_source, workdir_mode,"
            " governance_file FROM bridge_roles WHERE role_key LIKE '9010-%'"
        )
    }
    assert set(roles) == {
        "9010-planning-supervisor",
        "9010-execution-decomposer",
        "9010-implementer",
        "9010-reviewer",
        "9010-escalation-supervisor",
    }
    planner = roles["9010-planning-supervisor"]
    # PLOOP: DeepSeek DIRECT over claude-code, resolved by model-allocator.
    assert planner["default_model_source"] == "model_allocator"
    assert planner["default_model_alias"] == "cloud_deepseek"
    assert planner["default_harness_source"] == "claude-code"
    for key, row in roles.items():
        if key == "9010-planning-supervisor":
            continue
        # ELOOP: MiniMax-M3 over the native Codex harness on every role —
        # codex has no model-allocator adapter, so harness_provider with
        # the literal model id is the proven shape.
        assert row["default_model_source"] == "harness_provider", key
        assert row["default_model_alias"] == "MiniMax-M3", key
        assert row["default_harness_source"] == "codex", key
    for row in roles.values():
        assert row["workdir_mode"] == "father", row["role_key"]
        assert (GOVERNANCE_DIR / row["governance_file"]).is_file(), (
            row["role_key"]
        )

    steps = fresh_db.execute(
        "SELECT flow_key, governance_file, pre_dispatch_script"
        " FROM bridge_flow_steps"
        " WHERE flow_key IN ('9010-01-PLOOP', '9010-02-ELOOP')"
    ).fetchall()
    assert len(steps) == 5
    registered = {
        r["script_key"]
        for r in fresh_db.execute("SELECT script_key FROM bridge_scripts")
    }
    for step in steps:
        assert (GOVERNANCE_DIR / step["governance_file"]).is_file()
        if step["pre_dispatch_script"]:
            assert step["pre_dispatch_script"] in registered


def test_id_counters_seeded(fresh_db):
    counters = dict(
        fresh_db.execute(
            "SELECT flow_key, next_id FROM bridge_id_counters"
            " WHERE flow_key IN (?, ?, ?)",
            sorted(EXAMPLE_FLOWS),
        ).fetchall()
    )
    assert counters == {flow: 1 for flow in EXAMPLE_FLOWS}
