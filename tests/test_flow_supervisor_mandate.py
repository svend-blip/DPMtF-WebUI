"""Migration 096: per-flow supervisor mandate, database-driven and UI-managed.

A resident planning supervisor may open a Run on the execution chain only
under a mandate the Human has given. 096 pins that mandate, the commit
cadence and the (pre-existing, migration 061) supervisor role to the FLOW
row, seeds the seven UI labels in all four mandatory locales, and exposes
the three fields on the flow PUT/GET endpoints.

These tests run the full migration chain against an empty database, the
way a new installation does, and pin:

- the two new columns exist with fail-closed defaults (NULL mandate =
  planning only; 'none' cadence = the Human commits);
- the seven labels exist with en-US, da-DK, de-DE and es-ES translations
  and their ui_text_slots / ui_text_slot_labels rows;
- the rollback names both columns and the schema_migrations delete;
- bridge_lib.get_flow_supervisor_mandate returns the default shape on a
  database predating 096 rather than raising;
- the router accepts the three fields, normalizes blanks to NULL and
  rejects an unknown commit_cadence with 400 (pattern:
  tests/test_flow_implementation_mode_api.py, schema guard pattern:
  tests/test_artifact_root_ui_roundtrip.py — conftest's temp-DB schema
  predates 061/096 and is out of fence, so each router test ALTERs it).
"""

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import migrate  # noqa: E402
import bridge_lib  # noqa: E402

MIGRATION_096 = PROJECT_ROOT / "scripts" / "db" / "096_flow_supervisor_mandate.sql"
ROLLBACK_096 = (
    PROJECT_ROOT / "scripts" / "db" / "rollbacks"
    / "096_flow_supervisor_mandate_rollback.sql"
)
LOCALES = {"en-US", "da-DK", "de-DE", "es-ES"}
LABELS = {
    "LBL-1000534": "lbl_bridge_flow_supervisor_mandate",
    "LBL-1000535": "lbl_bridge_flow_supervisor_mandate_placeholder",
    "LBL-1000536": "lbl_bridge_flow_commit_cadence",
    "LBL-1000537": "lbl_bridge_flow_commit_cadence_none",
    "LBL-1000538": "lbl_bridge_flow_commit_cadence_per_run",
    "LBL-1000539": "lbl_bridge_flow_commit_cadence_per_handoff",
    "LBL-1000540": "lbl_bridge_flow_supervisor_role",
}
DEFAULT_SHAPE = {
    "supervisor_mandate": "",
    "commit_cadence": "none",
    "supervisor_role": "",
}


@pytest.fixture(scope="module")
def fresh_db(tmp_path_factory):
    """A database built the way a new installation builds one."""
    db_path = str(tmp_path_factory.mktemp("mandate_seed") / "fresh.db")
    migrate.run_migrations(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn, db_path
    conn.close()


def test_migration_096_is_recorded(fresh_db):
    conn, _ = fresh_db
    row = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE filename = ?",
        (MIGRATION_096.name,),
    ).fetchone()
    assert row is not None


def test_columns_exist_with_fail_closed_defaults(fresh_db):
    conn, _ = fresh_db
    cols = {
        r["name"]: r
        for r in conn.execute("PRAGMA table_info(bridge_flows)").fetchall()
    }
    assert "supervisor_mandate" in cols
    assert "commit_cadence" in cols
    assert "supervisor_role" in cols  # migration 061, untouched by 096
    assert cols["commit_cadence"]["notnull"] == 1
    assert cols["commit_cadence"]["dflt_value"] == "'none'"
    assert cols["supervisor_mandate"]["dflt_value"] in (None, "NULL")

    # A row inserted without the fields lands on the fail-closed defaults.
    conn.execute(
        "INSERT INTO bridge_flows (flow_key, name) VALUES (?, ?)",
        ("mandate-test-flow", "Mandate test"),
    )
    conn.commit()
    row = conn.execute(
        "SELECT supervisor_mandate, commit_cadence FROM bridge_flows"
        " WHERE flow_key = 'mandate-test-flow'"
    ).fetchone()
    assert row["supervisor_mandate"] is None
    assert row["commit_cadence"] == "none"


def test_seven_labels_seeded_in_four_locales_with_slots(fresh_db):
    conn, _ = fresh_db
    for label_id, label_key in LABELS.items():
        label = conn.execute(
            "SELECT label_key, is_active FROM ui_labels WHERE label_id = ?",
            (label_id,),
        ).fetchone()
        assert label is not None, label_id
        assert label["label_key"] == label_key
        assert label["is_active"] == 1

        locales = {
            r["locale"]
            for r in conn.execute(
                "SELECT locale FROM ui_label_translations"
                " WHERE label_id = ? AND is_active = 1",
                (label_id,),
            )
        }
        assert LOCALES <= locales, f"{label_key}: missing {LOCALES - locales}"

        slot = conn.execute(
            "SELECT 1 FROM ui_text_slots WHERE slot_key = ?", (label_key,)
        ).fetchone()
        assert slot is not None, f"{label_key}: no ui_text_slots row"
        slot_label = conn.execute(
            "SELECT label_key FROM ui_text_slot_labels WHERE slot_key = ?",
            (label_key,),
        ).fetchone()
        assert slot_label is not None, f"{label_key}: no ui_text_slot_labels row"
        assert slot_label["label_key"] == label_key


def test_rollback_names_both_columns_and_the_ledger_delete():
    text = ROLLBACK_096.read_text(encoding="utf-8")
    assert "ALTER TABLE bridge_flows DROP COLUMN supervisor_mandate" in text
    assert "ALTER TABLE bridge_flows DROP COLUMN commit_cadence" in text
    assert (
        "DELETE FROM schema_migrations WHERE filename = '096_flow_supervisor_mandate.sql'"
        in text
    )
    for label_id in LABELS:
        assert label_id in text, label_id
    # supervisor_role predates 096 and must survive the rollback.
    assert "DROP COLUMN supervisor_role" not in text


def test_seed_sql_carries_no_machine_paths():
    for path in (MIGRATION_096, ROLLBACK_096):
        assert "/home/svend" not in path.read_text(encoding="utf-8"), path.name


class TestGetFlowSupervisorMandate:
    def test_pre_096_database_returns_defaults_without_raising(self, tmp_path):
        db_path = str(tmp_path / "pre096.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE bridge_flows (flow_key TEXT PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO bridge_flows VALUES ('old_flow', 'Old')")
        conn.commit()
        conn.close()
        assert bridge_lib.get_flow_supervisor_mandate("old_flow", db_path=db_path) == DEFAULT_SHAPE

    def test_database_without_bridge_flows_returns_defaults(self, tmp_path):
        db_path = str(tmp_path / "empty.db")
        sqlite3.connect(db_path).close()
        assert bridge_lib.get_flow_supervisor_mandate("any", db_path=db_path) == DEFAULT_SHAPE

    def test_unknown_flow_returns_defaults(self, fresh_db):
        _, db_path = fresh_db
        assert bridge_lib.get_flow_supervisor_mandate("no-such-flow", db_path=db_path) == DEFAULT_SHAPE

    def test_unset_flow_returns_defaults(self, fresh_db):
        conn, db_path = fresh_db
        conn.execute(
            "INSERT OR IGNORE INTO bridge_flows (flow_key, name) VALUES (?, ?)",
            ("mandate-unset-flow", "Unset"),
        )
        conn.commit()
        assert bridge_lib.get_flow_supervisor_mandate("mandate-unset-flow", db_path=db_path) == DEFAULT_SHAPE

    def test_set_values_are_returned_stripped(self, fresh_db):
        conn, db_path = fresh_db
        conn.execute(
            "INSERT OR IGNORE INTO bridge_flows (flow_key, name) VALUES (?, ?)",
            ("mandate-set-flow", "Set"),
        )
        conn.execute(
            "UPDATE bridge_flows SET supervisor_mandate = ?, commit_cadence = ?,"
            " supervisor_role = ? WHERE flow_key = 'mandate-set-flow'",
            ("  open Runs for approved backlog items  ", "per_run", " planner "),
        )
        conn.commit()
        assert bridge_lib.get_flow_supervisor_mandate("mandate-set-flow", db_path=db_path) == {
            "supervisor_mandate": "open Runs for approved backlog items",
            "commit_cadence": "per_run",
            "supervisor_role": "planner",
        }


# ── Router round-trip ─────────────────────────────────────────────────

def _ensure_096_columns(seed_db: str) -> None:
    """conftest's temp-DB bridge_flows predates migrations 061 and 096 and
    is out of fence; add the columns here, idempotently."""
    conn = sqlite3.connect(seed_db)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(bridge_flows)").fetchall()}
        if "supervisor_role" not in cols:
            conn.execute("ALTER TABLE bridge_flows ADD COLUMN supervisor_role TEXT DEFAULT NULL")
        if "supervisor_mandate" not in cols:
            conn.execute("ALTER TABLE bridge_flows ADD COLUMN supervisor_mandate TEXT DEFAULT NULL")
        if "commit_cadence" not in cols:
            conn.execute(
                "ALTER TABLE bridge_flows ADD COLUMN commit_cadence TEXT NOT NULL DEFAULT 'none'"
            )
        conn.commit()
    finally:
        conn.close()


def _mandate_in_db(db_path: str, flow_key: str):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT supervisor_mandate, commit_cadence, supervisor_role"
            " FROM bridge_flows WHERE flow_key = ?",
            (flow_key,),
        ).fetchone()
    finally:
        conn.close()


@pytest.fixture()
def mandate_schema_ready(seed_db):
    _ensure_096_columns(seed_db)
    yield seed_db
    conn = sqlite3.connect(seed_db)
    try:
        conn.execute(
            "UPDATE bridge_flows SET supervisor_mandate = NULL, commit_cadence = 'none',"
            " supervisor_role = NULL WHERE flow_key = 'test_flow'"
        )
        conn.commit()
    finally:
        conn.close()


class TestPutSupervisorMandate:
    def test_all_three_fields_are_stored(self, client, mandate_schema_ready):
        res = client.put(
            "/api/bridge-v2/flows/test_flow",
            json={
                "supervisor_mandate": "open Runs for approved backlog items",
                "commit_cadence": "per_handoff",
                "supervisor_role": "test_role",
            },
        )
        assert res.status_code == 200, res.text
        assert _mandate_in_db(mandate_schema_ready, "test_flow") == (
            "open Runs for approved backlog items", "per_handoff", "test_role",
        )

    def test_blank_mandate_and_role_clear_to_null(self, client, mandate_schema_ready):
        client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"supervisor_mandate": "x", "supervisor_role": "test_role"},
        )
        res = client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"supervisor_mandate": "   ", "supervisor_role": ""},
        )
        assert res.status_code == 200, res.text
        mandate, _, role = _mandate_in_db(mandate_schema_ready, "test_flow")
        assert mandate is None
        assert role is None

    def test_invalid_commit_cadence_is_rejected_with_400(self, client, mandate_schema_ready):
        res = client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"commit_cadence": "hourly"},
        )
        assert res.status_code == 400, res.text
        assert "hourly" in res.json()["detail"]
        assert _mandate_in_db(mandate_schema_ready, "test_flow")[1] == "none"

    def test_blank_commit_cadence_is_rejected_with_400(self, client, mandate_schema_ready):
        res = client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"commit_cadence": ""},
        )
        assert res.status_code == 400, res.text

    def test_omitting_the_fields_leaves_them_alone(self, client, mandate_schema_ready):
        client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"supervisor_mandate": "keep", "commit_cadence": "per_run"},
        )
        res = client.put(
            "/api/bridge-v2/flows/test_flow",
            json={"description": "unrelated edit"},
        )
        assert res.status_code == 200, res.text
        assert _mandate_in_db(mandate_schema_ready, "test_flow")[:2] == ("keep", "per_run")


class TestGetExposesSupervisorMandate:
    def test_list_and_get_carry_the_fields(self, client, mandate_schema_ready):
        client.put(
            "/api/bridge-v2/flows/test_flow",
            json={
                "supervisor_mandate": "visible",
                "commit_cadence": "per_run",
                "supervisor_role": "test_role",
            },
        )
        res = client.get("/api/bridge-v2/flows")
        assert res.status_code == 200, res.text
        flows = {f["flow_key"]: f for f in res.json()["flows"]}
        assert flows["test_flow"]["supervisor_mandate"] == "visible"
        assert flows["test_flow"]["commit_cadence"] == "per_run"
        assert flows["test_flow"]["supervisor_role"] == "test_role"

        res = client.get("/api/bridge-v2/flows/test_flow")
        assert res.status_code == 200, res.text
        flow = res.json()["flow"]
        assert flow["supervisor_mandate"] == "visible"
        assert flow["commit_cadence"] == "per_run"
        assert flow["supervisor_role"] == "test_role"
