"""Tests for the harness-field write/read round-trip — Run 038 / D1.

The DPMtF /api/bridge-v2/{roles,steps} endpoints already GET the harness
columns (default_harness_source / default_harness_profile on bridge_roles;
harness_source / harness_profile on bridge_flow_steps), and the resolver
already reads them with the same step → role → system precedence as
model_source / model_alias. What was missing — and what D1a / D1b fix in
routers/bridge.py — is that PUT /roles/{role_key} and PUT /steps/{flow_key}/{step_id}
did not include those column names in their updatable list / field_map,
so a written value would silently be ignored.

The first two tests prove a written value survives a read-back through the
HTTP layer (PUT then GET). The two tests at the bottom of this file add the
omitted-field case (a PUT that OMITS the harness fields must leave the stored
values untouched), completing TG1's full "what" (Run 038 / D4).

CRITICAL TRAP: tests/conftest.py's temp-DB schema does NOT carry the four
harness columns (the conftest is OUT OF FENCE — fixing it there would
break the "tests are read-only" rule of every other test file). Each
test's setup ALTERs the temp DB to add the four columns. Setup is
idempotent via a PRAGMA table_info guard so re-running in one pytest
session does not error on the second run.
"""

import sqlite3
from typing import Tuple

import pytest
from fastapi.testclient import TestClient


# ── Test-only harness columns ─────────────────────────────────────────
# The four harness columns D1a / D1b / D1c introduce. Role columns carry
# the ``default_`` prefix (matching model_source / model_alias); step
# columns carry NO prefix (matching model_source / model_alias). DO NOT
# swap them — the production schema in init_db.py / migration 062 uses
# these exact names.
_ROLE_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("default_harness_source", "TEXT"),
    ("default_harness_profile", "TEXT"),
)
_STEP_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("harness_source", "TEXT"),
    ("harness_profile", "TEXT"),
)


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, decl: str
) -> None:
    """ALTER TABLE ADD COLUMN guarded by PRAGMA table_info — idempotent
    across repeated invocations in one pytest session."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _seed_harness_columns(seed_db: str) -> None:
    """Add the four harness columns to the temp DB schema. Idempotent."""
    conn = sqlite3.connect(seed_db)
    try:
        for col, decl in _ROLE_COLUMNS:
            _add_column_if_missing(conn, "bridge_roles", col, decl)
        for col, decl in _STEP_COLUMNS:
            _add_column_if_missing(conn, "bridge_flow_steps", col, decl)
        conn.commit()
    finally:
        conn.close()


def _seed_one_step(seed_db: str, flow_key: str, step_key: str) -> int:
    """Insert a single step row for the seeded flow and return its id.

    conftest.py's seeded_db_path fixture seeds test_role + test_flow but
    NO step row, so the step round-trip needs one to exist before PUT.
    Returns the new id (the only column callers need to build the PUT URL).
    """
    conn = sqlite3.connect(seed_db)
    try:
        cursor = conn.execute(
            """
            INSERT INTO bridge_flow_steps
                (flow_key, step_key, from_role, to_role,
                 sort_order, is_active)
            VALUES (?, ?, ?, ?, 0, 1)
            """,
            (flow_key, step_key, "test_role", "test_role"),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


@pytest.fixture()
def harness_schema_ready(seed_db: str):
    """Make sure the temp DB has the four harness columns. Runs once per
    test (function-scoped) so it stays correct even if a different test
    in the session mutated the schema. Yields the seed_db path so tests
    can use it for the step-row seed."""
    _seed_harness_columns(seed_db)
    return seed_db


# ── TG3 — the role endpoint writes the harness fields and they persist ──


def test_role_harness_fields_persist(
    client: TestClient, harness_schema_ready: str
) -> None:
    """PUT /api/bridge-v2/roles/test_role with default_harness_source /
    default_harness_profile persists them; GET back returns the same
    sentinels. Distinct sentinels so a swapped source↔profile assertion
    would fail."""
    sent_source = "sentinel-role-source"
    sent_profile = "sentinel-role-profile-X"

    put_resp = client.put(
        "/api/bridge-v2/roles/test_role",
        json={
            "default_harness_source": sent_source,
            "default_harness_profile": sent_profile,
        },
    )
    assert put_resp.status_code == 200, (
        f"PUT roles/test_role returned {put_resp.status_code}: {put_resp.text}"
    )

    get_resp = client.get("/api/bridge-v2/roles/test_role")
    assert get_resp.status_code == 200
    role = get_resp.json()["role"]

    assert role["default_harness_source"] == sent_source, (
        f"default_harness_source round-tripped as {role['default_harness_source']!r}, "
        f"expected {sent_source!r}"
    )
    assert role["default_harness_profile"] == sent_profile, (
        f"default_harness_profile round-tripped as {role['default_harness_profile']!r}, "
        f"expected {sent_profile!r}"
    )


# ── TG4 — the step endpoint writes the harness fields and they persist ──


def test_step_harness_fields_persist(
    client: TestClient, harness_schema_ready: str
) -> None:
    """PUT /api/bridge-v2/steps/test_flow/{step_id} with harness_source /
    harness_profile persists them; GET back from /steps/test_flow returns
    the same sentinels on the matching step. Distinct sentinels so a
    swapped source↔profile assertion would fail."""
    sent_source = "sentinel-step-source"
    sent_profile = "sentinel-step-profile-Y"

    step_id = _seed_one_step(harness_schema_ready, "test_flow", "step-harness-rt")

    put_resp = client.put(
        f"/api/bridge-v2/steps/test_flow/{step_id}",
        json={
            "harness_source": sent_source,
            "harness_profile": sent_profile,
        },
    )
    assert put_resp.status_code == 200, (
        f"PUT steps/test_flow/{step_id} returned {put_resp.status_code}: {put_resp.text}"
    )

    get_resp = client.get("/api/bridge-v2/steps/test_flow")
    assert get_resp.status_code == 200
    steps = get_resp.json()["steps"]
    matching = [s for s in steps if s["id"] == step_id]
    assert matching, (
        f"GET /steps/test_flow returned no step with id {step_id}; got ids "
        f"{[s['id'] for s in steps]!r}"
    )
    step = matching[0]

    assert step["harness_source"] == sent_source, (
        f"harness_source round-tripped as {step['harness_source']!r}, "
        f"expected {sent_source!r}"
    )
    assert step["harness_profile"] == sent_profile, (
        f"harness_profile round-tripped as {step['harness_profile']!r}, "
        f"expected {sent_profile!r}"
    )

# ── TG1 (omitted-field) — a PUT that omits the harness fields must not clear them ──


def test_role_harness_fields_survive_omitted_put(
    client: TestClient, harness_schema_ready: str
) -> None:
    """Persist the harness fields, then PUT a body that omits them; the
    omitted fields must be left untouched (NOT cleared to NULL)."""
    sent_source = "sentinel-role-source-omit"
    sent_profile = "sentinel-role-profile-omit"

    put1 = client.put(
        "/api/bridge-v2/roles/test_role",
        json={
            "default_harness_source": sent_source,
            "default_harness_profile": sent_profile,
        },
    )
    assert put1.status_code == 200, (
        f"PUT roles/test_role returned {put1.status_code}: {put1.text}"
    )

    # A second PUT that touches a DIFFERENT field (is_active) and omits both
    # harness fields. The endpoint must leave the harness columns alone.
    put2 = client.put(
        "/api/bridge-v2/roles/test_role",
        json={"is_active": True},
    )
    assert put2.status_code == 200, (
        f"PUT roles/test_role returned {put2.status_code}: {put2.text}"
    )

    role = client.get("/api/bridge-v2/roles/test_role").json()["role"]
    assert role["default_harness_source"] == sent_source, (
        f"default_harness_source was cleared to {role['default_harness_source']!r}, "
        f"expected {sent_source!r}"
    )
    assert role["default_harness_profile"] == sent_profile, (
        f"default_harness_profile was cleared to {role['default_harness_profile']!r}, "
        f"expected {sent_profile!r}"
    )


def test_step_harness_fields_survive_omitted_put(
    client: TestClient, harness_schema_ready: str
) -> None:
    """Persist the harness fields, then PUT a body that omits them; the
    omitted fields must be left untouched (NOT cleared to NULL)."""
    sent_source = "sentinel-step-source-omit"
    sent_profile = "sentinel-step-profile-omit"

    # Distinct step_key from the persist test — UNIQUE(flow_key, step_key).
    step_id = _seed_one_step(harness_schema_ready, "test_flow", "step-harness-rt-omitted")

    put1 = client.put(
        f"/api/bridge-v2/steps/test_flow/{step_id}",
        json={
            "harness_source": sent_source,
            "harness_profile": sent_profile,
        },
    )
    assert put1.status_code == 200, (
        f"PUT steps/test_flow/{step_id} returned {put1.status_code}: {put1.text}"
    )

    # A second PUT that touches a DIFFERENT field (sort_order) and omits both
    # harness fields. The endpoint must leave the harness columns alone.
    put2 = client.put(
        f"/api/bridge-v2/steps/test_flow/{step_id}",
        json={"sort_order": 1},
    )
    assert put2.status_code == 200, (
        f"PUT steps/test_flow/{step_id} returned {put2.status_code}: {put2.text}"
    )

    steps = client.get("/api/bridge-v2/steps/test_flow").json()["steps"]
    matching = [s for s in steps if s["id"] == step_id]
    assert matching, f"GET /steps/test_flow returned no step with id {step_id}"
    step = matching[0]
    assert step["harness_source"] == sent_source, (
        f"harness_source was cleared to {step['harness_source']!r}, expected {sent_source!r}"
    )
    assert step["harness_profile"] == sent_profile, (
        f"harness_profile was cleared to {step['harness_profile']!r}, expected {sent_profile!r}"
    )

# ── TG1 (create-path) — POST must persist the harness fields, not silently drop them ──


def test_role_harness_fields_persist_on_create(
    client: TestClient, harness_schema_ready: str
) -> None:
    """POST /api/bridge-v2/roles with default_harness_source /
    default_harness_profile persists them on the INSERT path. The
    existing PUT tests cover the UPDATE path; the CREATE path is the
    defect found at landing — the INSERT column list omitted the
    harness fields, so a brand-new role created with a harness override
    silently lost it.

    Uses a role_key DISTINCT from the seeded "test_role" so the INSERT
    path runs, not the reactivate branch.
    """
    rk = "test_role_create_rt"
    sent_source = "sentinel-role-create-src"
    sent_profile = "sentinel-role-create-prof"

    post = client.post(
        "/api/bridge-v2/roles",
        json={
            "role_key": rk,
            "tmux_session": "test_create_tmux",
            "default_harness_source": sent_source,
            "default_harness_profile": sent_profile,
        },
    )
    assert post.status_code == 200, (
        f"POST /api/bridge-v2/roles returned {post.status_code}: {post.text}"
    )

    # POST /roles returns {"status": "created", "role_key": ...} — not the
    # full role — so GET-back is required to prove DB persistence.
    get_resp = client.get(f"/api/bridge-v2/roles/{rk}")
    assert get_resp.status_code == 200, (
        f"GET /api/bridge-v2/roles/{rk} returned {get_resp.status_code}: {get_resp.text}"
    )
    role = get_resp.json()["role"]
    assert role["default_harness_source"] == sent_source, (
        f"default_harness_source was not persisted; got {role['default_harness_source']!r}, "
        f"expected {sent_source!r}"
    )
    assert role["default_harness_profile"] == sent_profile, (
        f"default_harness_profile was not persisted; got {role['default_harness_profile']!r}, "
        f"expected {sent_profile!r}"
    )


def test_step_harness_fields_persist_on_create(
    client: TestClient, harness_schema_ready: str
) -> None:
    """POST /api/bridge-v2/steps/test_flow with harness_source /
    harness_profile persists them on the INSERT path. Mirrors the role
    create-path test for steps.

    Uses a step_key DISTINCT from the seeded step_keys so the INSERT
    path runs (the endpoint returns 409 if the step_key already exists).
    """
    sk = "step-harness-create-rt"
    sent_source = "sentinel-step-create-src"
    sent_profile = "sentinel-step-create-prof"

    post = client.post(
        "/api/bridge-v2/steps/test_flow",
        json={
            "step_key": sk,
            "from_role": "test_role",
            "to_role": "test_role",
            "harness_source": sent_source,
            "harness_profile": sent_profile,
        },
    )
    assert post.status_code == 200, (
        f"POST /api/bridge-v2/steps/test_flow returned {post.status_code}: {post.text}"
    )

    # POST /steps returns {"step": {...}, "created": True} — the response
    # includes the created step, but we also GET-back to prove DB
    # persistence is not just a response echo.
    step_in_resp = post.json()["step"]
    assert step_in_resp["harness_source"] == sent_source, (
        f"POST response harness_source was not echoed; got {step_in_resp['harness_source']!r}, "
        f"expected {sent_source!r}"
    )
    assert step_in_resp["harness_profile"] == sent_profile, (
        f"POST response harness_profile was not echoed; got {step_in_resp['harness_profile']!r}, "
        f"expected {sent_profile!r}"
    )

    # GET-back through the steps list endpoint — proves DB persistence,
    # not just the immediate POST echo.
    list_resp = client.get("/api/bridge-v2/steps/test_flow")
    assert list_resp.status_code == 200
    steps = list_resp.json()["steps"]
    matching = [s for s in steps if s.get("step_key") == sk]
    assert matching, (
        f"GET /api/bridge-v2/steps/test_flow returned no step with step_key={sk!r}; "
        f"got step_keys {[s.get('step_key') for s in steps]!r}"
    )
    step = matching[0]
    assert step["harness_source"] == sent_source, (
        f"DB-persisted harness_source was not the sentinel; got {step['harness_source']!r}, "
        f"expected {sent_source!r}"
    )
    assert step["harness_profile"] == sent_profile, (
        f"DB-persisted harness_profile was not the sentinel; got {step['harness_profile']!r}, "
        f"expected {sent_profile!r}"
    )
