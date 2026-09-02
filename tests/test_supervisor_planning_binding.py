"""Migration 097: the planning supervisors are bound to SUPERVISOR_PLANNING.md.

The planning supervisor of a PLOOP/ELOOP family is a resident session,
not the conversational `supervisor` role that 500_SUPERVISOR.md
describes. Migration 097 rebinds it (role level and the planning-human
step), names it as the stall wake-up target on BOTH rows of its family
(103_FLOW_STARTUP Binding Rule 6), and clears the '/clear'
fresh_session_command that a machine wake-up would otherwise send into
the resident session. These tests run the full migration chain on a
temporary database, the way test_example_flows_seed.py does; the live
database at databases/dpmtf.db is never touched.

The 1010 family exists only in the live database (created through the
WebUI, never migrated — migration 090's header says so), so on a fresh
database its rows are absent. The family assertions therefore cover
every family present and pin that 1000, 9000 and 9010 are; the 1010
predicates are pinned at the migration-text level instead.
"""

import re
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import migrate  # noqa: E402
from execution_config import resolve_execution_config  # noqa: E402

MIGRATION_097 = PROJECT_ROOT / "scripts" / "db" / "097_supervisor_planning_rebind.sql"
ROLLBACK_097 = (
    PROJECT_ROOT / "scripts" / "db" / "rollbacks"
    / "097_supervisor_planning_rebind_rollback.sql"
)

PLANNING_GOVERNANCE = "SUPERVISOR_PLANNING.md"
CONVERSATIONAL_GOVERNANCE = "500_SUPERVISOR.md"

FAMILIES = ("1000", "1010", "9000", "9010")
# Families that ship by migration and must be present on a fresh database.
SEEDED_FAMILIES = ("1000", "9000", "9010")
# The planning supervisors on the claude-code client, whose '/clear'
# fresh_session_command 097 removes.
CLAUDE_CODE_PLANNING_SUPERVISORS = tuple(
    f"{family}-planning-supervisor" for family in FAMILIES
)
# Flows whose supervisor IS the conversational one 500_SUPERVISOR.md
# describes: the `supervisor` flow and its shipped one-flow example.
CONVERSATIONAL_SUPERVISOR_FLOWS = ("supervisor", "example-cloud")


@pytest.fixture(scope="module")
def fresh_db(tmp_path_factory):
    """A database built the way a new installation builds one."""
    db_path = str(tmp_path_factory.mktemp("planning_binding") / "fresh.db")
    migrate.run_migrations(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def _family_rows(conn, family):
    return {
        r["flow_key"]: r
        for r in conn.execute(
            "SELECT flow_key, supervisor_role, cold_start_skill FROM bridge_flows"
            " WHERE flow_key IN (?, ?)",
            (f"{family}-01-PLOOP", f"{family}-02-ELOOP"),
        )
    }


def test_planning_supervisor_roles_bound_to_planning_governance(fresh_db):
    rows = fresh_db.execute(
        "SELECT role_key, governance_file FROM bridge_roles"
        " WHERE role_key LIKE '%-planning-supervisor'"
    ).fetchall()
    assert {r["role_key"] for r in rows} >= {
        f"{family}-planning-supervisor" for family in SEEDED_FAMILIES
    } | {"example-planning-supervisor"}
    for row in rows:
        assert row["governance_file"] == PLANNING_GOVERNANCE, row["role_key"]


def test_planning_human_steps_bound_to_planning_governance(fresh_db):
    rows = fresh_db.execute(
        "SELECT flow_key, governance_file FROM bridge_flow_steps"
        " WHERE step_key = 'planning-human'"
    ).fetchall()
    assert {r["flow_key"] for r in rows} >= {
        f"{family}-01-PLOOP" for family in SEEDED_FAMILIES
    } | {"example-01-PLOOP"}
    for row in rows:
        assert row["governance_file"] == PLANNING_GOVERNANCE, row["flow_key"]


def test_conversational_governance_only_in_conversational_flows(fresh_db):
    """500_SUPERVISOR.md stays with the flows it describes and nowhere else."""
    placeholders = ",".join("?" * len(CONVERSATIONAL_SUPERVISOR_FLOWS))
    conversational_roles = {"human"}
    for row in fresh_db.execute(
        f"SELECT from_role, to_role FROM bridge_flow_steps"
        f" WHERE flow_key IN ({placeholders})",
        CONVERSATIONAL_SUPERVISOR_FLOWS,
    ):
        conversational_roles.update((row["from_role"], row["to_role"]))
    # The exemption must be real: both conversational flows ship.
    assert "supervisor" in conversational_roles
    assert "ex-super-cl" in conversational_roles

    stray_roles = [
        r["role_key"]
        for r in fresh_db.execute(
            "SELECT role_key FROM bridge_roles"
            " WHERE is_active = 1 AND governance_file = ?",
            (CONVERSATIONAL_GOVERNANCE,),
        )
        if r["role_key"] not in conversational_roles
    ]
    assert stray_roles == [], stray_roles

    stray_steps = [
        f"{r['flow_key']}/{r['step_key']}"
        for r in fresh_db.execute(
            "SELECT flow_key, step_key FROM bridge_flow_steps"
            " WHERE is_active = 1 AND governance_file = ?",
            (CONVERSATIONAL_GOVERNANCE,),
        )
        if r["flow_key"] not in CONVERSATIONAL_SUPERVISOR_FLOWS
    ]
    assert stray_steps == [], stray_steps


def test_both_family_rows_wake_the_resident_planning_supervisor(fresh_db):
    present = []
    for family in FAMILIES:
        rows = _family_rows(fresh_db, family)
        if not rows:
            continue
        present.append(family)
        assert set(rows) == {f"{family}-01-PLOOP", f"{family}-02-ELOOP"}, family
        for flow_key, row in rows.items():
            assert row["supervisor_role"] == f"{family}-planning-supervisor", (
                flow_key
            )
    assert set(present) >= set(SEEDED_FAMILIES), present


def test_example_family_supervisor_roles_untouched(fresh_db):
    rows = _family_rows(fresh_db, "example")
    assert rows["example-01-PLOOP"]["supervisor_role"] == "example-planning-supervisor"
    assert rows["example-02-ELOOP"]["supervisor_role"] == "example-escalation-supervisor"


def test_claude_code_planning_supervisors_keep_their_session(fresh_db):
    rows = {
        r["role_key"]: r
        for r in fresh_db.execute(
            "SELECT role_key, allocator_client, fresh_session_command"
            " FROM bridge_roles WHERE role_key IN ({})".format(
                ",".join("?" * len(CLAUDE_CODE_PLANNING_SUPERVISORS))
            ),
            CLAUDE_CODE_PLANNING_SUPERVISORS,
        )
    }
    assert set(rows) >= {f"{family}-planning-supervisor" for family in SEEDED_FAMILIES}
    for key, row in rows.items():
        assert row["allocator_client"] == "claude-code", key
        assert row["fresh_session_command"] is None, key


def test_9000_ploop_carries_cold_start_skill(fresh_db):
    row = fresh_db.execute(
        "SELECT cold_start_skill FROM bridge_flows WHERE flow_key = '9000-01-PLOOP'"
    ).fetchone()
    assert row is not None
    assert row["cold_start_skill"] == "9000"


def test_resolver_hands_planning_supervisor_its_governance(fresh_db, tmp_path_factory):
    # Resolve against the same fresh database the fixture built.
    db_path = fresh_db.execute("PRAGMA database_list").fetchone()["file"]
    resolved = resolve_execution_config("9000-01-PLOOP", "planning-human", db_path=db_path)
    assert resolved["governance_file"] == PLANNING_GOVERNANCE
    assert resolved["from_role"] == "9000-planning-supervisor"


def test_migration_text_covers_every_family():
    text = MIGRATION_097.read_text(encoding="utf-8")
    for family in FAMILIES:
        assert f"'{family}-planning-supervisor'" in text, family
        assert f"'{family}-02-ELOOP'" in text, family
    for family in ("1000", "1010", "9000"):
        assert f"'{family}-01-PLOOP'" in text, family
    assert "cold_start_skill = '9000'" in text
    assert "/home/svend" not in text


def test_rollback_is_the_exact_inverse():
    assert ROLLBACK_097.is_file()
    text = ROLLBACK_097.read_text(encoding="utf-8")
    assert re.search(
        r"governance_file\s*=\s*'500_SUPERVISOR\.md'.*?governance_file\s*=\s*"
        r"'SUPERVISOR_PLANNING\.md'",
        text, re.S,
    ), "governance_file is not returned to 500_SUPERVISOR.md on the moved rows"
    assert re.search(r"supervisor_role\s*=\s*NULL", text)
    assert re.search(r"supervisor_role\s*=\s*'9010-escalation-supervisor'", text)
    assert re.search(r"fresh_session_command\s*=\s*'/clear'", text)
    assert re.search(r"cold_start_skill\s*=\s*NULL", text)
    assert re.search(
        r"DELETE\s+FROM\s+schema_migrations\s+WHERE\s+filename\s*=\s*"
        r"'097_supervisor_planning_rebind\.sql'",
        text,
    )
    for family in FAMILIES:
        assert f"'{family}-planning-supervisor'" in text, family


def test_rollback_round_trip_restores_pre_097_state(tmp_path):
    """Forward, rollback, forward on a scratch DB: rollback undoes 097 exactly."""
    db_path = str(tmp_path / "roundtrip.db")
    migrate.run_migrations(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        def snapshot():
            return (
                conn.execute(
                    "SELECT role_key, governance_file, fresh_session_command"
                    " FROM bridge_roles ORDER BY role_key"
                ).fetchall(),
                conn.execute(
                    "SELECT flow_key, step_key, governance_file"
                    " FROM bridge_flow_steps ORDER BY flow_key, step_key"
                ).fetchall(),
                conn.execute(
                    "SELECT flow_key, supervisor_role, cold_start_skill"
                    " FROM bridge_flows ORDER BY flow_key"
                ).fetchall(),
            )

        after_forward = snapshot()
        conn.executescript(ROLLBACK_097.read_text(encoding="utf-8"))
        conn.commit()
        assert conn.execute(
            "SELECT 1 FROM schema_migrations WHERE filename = ?",
            (MIGRATION_097.name,),
        ).fetchone() is None
        roles = dict(
            conn.execute(
                "SELECT role_key, governance_file FROM bridge_roles"
                " WHERE role_key LIKE '%-planning-supervisor'"
            ).fetchall()
        )
        assert set(roles.values()) == {CONVERSATIONAL_GOVERNANCE}
        assert conn.execute(
            "SELECT supervisor_role FROM bridge_flows WHERE flow_key = '9010-02-ELOOP'"
        ).fetchone()[0] == "9010-escalation-supervisor"
        assert conn.execute(
            "SELECT supervisor_role FROM bridge_flows WHERE flow_key = '9000-02-ELOOP'"
        ).fetchone()[0] is None
        assert conn.execute(
            "SELECT fresh_session_command FROM bridge_roles"
            " WHERE role_key = '9000-planning-supervisor'"
        ).fetchone()[0] == "/clear"

        # The runner re-applies only 097 and lands on the same state.
        conn.close()
        migrate.run_migrations(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        assert [tuple(r) for t in snapshot() for r in t] == [
            tuple(r) for t in after_forward for r in t
        ]
    finally:
        conn.close()
