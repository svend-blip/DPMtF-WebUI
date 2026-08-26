"""Tests for the artifact_root field's UI round-trip — Run 040 / D1 + D4.

The DPMtF bridge flow PATCH/PUT endpoint (/api/bridge-v2/flows/{flow_key})
already GETs the artifact_root column from bridge_flows (the resolver
`bridge_lib.get_effective_artifact_root` consumes it), but the
`bridge_v2_update_flow` route did not include `artifact_root` in its
`updatable` whitelist. D1 adds the column to the whitelist AND adds a
normalisation step: empty/whitespace -> NULL (the resolver's "the flow key
is the root" fallback). NO directory-existence check — an artifact root may
name a workspace the first run will create.

These four tests prove the full chain — PUT writes, GET returns, the
resolver sees it — including the two cases that get forgotten:

  - the UNSET case (empty string -> NULL, requirement (a))
  - the OMITTED case (PUT without the field leaves the stored value alone)
  - the RESOLVER case (requirement (b) — get_effective_artifact_root
    returns the new value after the PUT, proving the UI edit reaches the
    machinery that actually decides where artifacts land)

CRITICAL TRAP: tests/conftest.py's temp-DB `bridge_flows` schema does NOT
carry the `artifact_root` column (the conftest is OUT OF FENCE — fixing it
there would break the "tests are read-only" rule of every other test file).
Each test's setup ALTERs the temp DB to add the column. Setup is idempotent
via a PRAGMA table_info guard so re-running in one pytest session does not
error on the second run.

The resolver reads config.get_db_path() by default — which in tests is the
LIVE DB, not the temp DB. ALWAYS pass db_path=seed_db explicitly to
get_effective_artifact_root.
"""

import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ── bridge_lib resolver import (mirror test_artifact_root.py) ──────────
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts" / "bridgeV002"))

import bridge_lib  # noqa: E402


# ── Per-test schema setup ──────────────────────────────────────────────

def _ensure_artifact_root_column(seed_db: str) -> None:
    """ALTER TABLE ADD COLUMN guarded by PRAGMA table_info — idempotent
    across repeated invocations in one pytest session. conftest.py's
    seeded_db_path fixture does not include artifact_root (it predates
    migration 073); this guard adds the column without touching conftest."""
    conn = sqlite3.connect(seed_db)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(bridge_flows)").fetchall()}
        if "artifact_root" not in cols:
            conn.execute("ALTER TABLE bridge_flows ADD COLUMN artifact_root TEXT")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def artifact_root_schema_ready(seed_db: str):
    """Make sure the temp DB has the artifact_root column. Runs once per
    test (function-scoped) so it stays correct even if a different test
    in the session mutated the schema. Yields the seed_db path so tests
    can pass it to bridge_lib.get_effective_artifact_root."""
    _ensure_artifact_root_column(seed_db)
    return seed_db


# ── Test sentinels (distinct per test; absolute paths the resolver accepts) ──

SENTINEL_PERSIST = "/tmp/dpmtf-artifact-root-sentinel-040-persist"
SENTINEL_RESOLVER = "/tmp/dpmtf-artifact-root-sentinel-040-resolver"


# ── TG4 / D4 — round-trip suite ─────────────────────────────────────────


def test_artifact_root_persist_and_readback(
    client: TestClient, artifact_root_schema_ready: str
) -> None:
    """PUT /api/bridge-v2/flows/test_flow with artifact_root persists it;
    GET /api/bridge-v2/flows/test_flow returns the same sentinel."""
    put = client.put(
        "/api/bridge-v2/flows/test_flow",
        json={"artifact_root": SENTINEL_PERSIST},
    )
    assert put.status_code == 200, (
        f"PUT flows/test_flow returned {put.status_code}: {put.text}"
    )

    get = client.get("/api/bridge-v2/flows/test_flow")
    assert get.status_code == 200
    flow = get.json()["flow"]
    assert flow["artifact_root"] == SENTINEL_PERSIST, (
        f"artifact_root round-tripped as {flow['artifact_root']!r}, "
        f"expected {SENTINEL_PERSIST!r}"
    )


def test_artifact_root_empty_string_stores_null(
    client: TestClient, artifact_root_schema_ready: str
) -> None:
    """PUT with empty string MUST store NULL (UNSET case, requirement (a)).
    An empty string stored as-is would defeat the resolver's "the flow key
    is the root" fallback (the resolver's `or flow_key` only fires on
    NULL, not on "")."""
    put = client.put(
        "/api/bridge-v2/flows/test_flow",
        json={"artifact_root": ""},
    )
    assert put.status_code == 200, (
        f"PUT flows/test_flow returned {put.status_code}: {put.text}"
    )

    get = client.get("/api/bridge-v2/flows/test_flow")
    assert get.status_code == 200
    flow = get.json()["flow"]
    assert flow["artifact_root"] is None, (
        f"empty string was not normalised to NULL; got {flow['artifact_root']!r}, "
        f"expected None"
    )


def test_artifact_root_omitted_field_left_untouched(
    client: TestClient, artifact_root_schema_ready: str
) -> None:
    """First PUT sets artifact_root; second PUT touches a DIFFERENT field
    (name) and omits artifact_root. The endpoint must leave the stored
    artifact_root untouched (NOT cleared to NULL)."""
    put1 = client.put(
        "/api/bridge-v2/flows/test_flow",
        json={"artifact_root": SENTINEL_PERSIST},
    )
    assert put1.status_code == 200, (
        f"PUT flows/test_flow (set) returned {put1.status_code}: {put1.text}"
    )

    # Second PUT touches ONLY `name` — no `artifact_root` key at all.
    put2 = client.put(
        "/api/bridge-v2/flows/test_flow",
        json={"name": "Test Flow Renamed"},
    )
    assert put2.status_code == 200, (
        f"PUT flows/test_flow (rename) returned {put2.status_code}: {put2.text}"
    )

    get = client.get("/api/bridge-v2/flows/test_flow")
    assert get.status_code == 200
    flow = get.json()["flow"]
    assert flow["artifact_root"] == SENTINEL_PERSIST, (
        f"omitted artifact_root was cleared to {flow['artifact_root']!r}, "
        f"expected {SENTINEL_PERSIST!r}"
    )
    assert flow["name"] == "Test Flow Renamed", (
        f"rename did not persist; got {flow['name']!r}, "
        f"expected 'Test Flow Renamed'"
    )


def test_artifact_root_reaches_the_resolver(
    client: TestClient, artifact_root_schema_ready: str
) -> None:
    """The decisive assertion (requirement (b)): after PUT, the resolver
    `bridge_lib.get_effective_artifact_root` MUST return the new value.
    Without this, PUT-then-GET agreeing would be hollow — the resolver is
    the consumer that actually decides where artifacts land.

    Two halves:
      - PUT with a sentinel -> resolver returns the sentinel.
      - PUT with empty string -> resolver returns the flow_key (the
        "the flow key is the root" fallback that fires on NULL).
    """
    # Half 1: SET
    put1 = client.put(
        "/api/bridge-v2/flows/test_flow",
        json={"artifact_root": SENTINEL_RESOLVER},
    )
    assert put1.status_code == 200, (
        f"PUT flows/test_flow (set) returned {put1.status_code}: {put1.text}"
    )
    resolved = bridge_lib.get_effective_artifact_root(
        "test_flow", db_path=artifact_root_schema_ready
    )
    assert resolved == SENTINEL_RESOLVER, (
        f"resolver did not see the SET value; got {resolved!r}, "
        f"expected {SENTINEL_RESOLVER!r}"
    )

    # Half 2: UNSET
    put2 = client.put(
        "/api/bridge-v2/flows/test_flow",
        json={"artifact_root": ""},
    )
    assert put2.status_code == 200, (
        f"PUT flows/test_flow (unset) returned {put2.status_code}: {put2.text}"
    )
    resolved = bridge_lib.get_effective_artifact_root(
        "test_flow", db_path=artifact_root_schema_ready
    )
    assert resolved == "test_flow", (
        f"resolver did not fall back to flow_key after UNSET; got {resolved!r}, "
        f"expected 'test_flow' (the resolver's fallback for NULL/empty)"
    )
