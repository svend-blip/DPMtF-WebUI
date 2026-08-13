"""Tests for routers/bridge.py: GET /api/bridge-v2/flows/{flow_key}/trace.

The real trace log at ``$DPMTF_BRIDGE_DIR/trace.log`` belongs to the
LIVE chain driving this very handoff. Every test in this file MUST
redirect the route to a tmp_path fixture via ``monkeypatch.setenv``
— the route calls ``config.get_bridge_dir()`` at request time so the
env var is honoured by the request handler. A test that forgets the
monkeypatch silently reads the live chain's log and becomes a
production-data leak.

The trace log is flow-wide and append-only: it carries every flow's
and every era's rows mixed together, including same-``handoff_id``
rows from other flows. The route filters by field-splitting and a
DB-backed role set — substring matching is an auto-fail.

The conftest's ``seeded_db_path`` ships with the bridge_flows and
bridge_flow_steps tables and a single test_flow / test_role seed.
This file installs its own preferred_cloud + step rows via
INSERT OR IGNORE so the route's flow-existence and role-set paths
exercise real SQL.
"""

from __future__ import annotations

import os
import sqlite3

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _seed_trace_rows(seeded_db_path: str) -> None:
    """Insert the preferred_cloud flow + three active bridge_flow_steps rows.

    Idempotent (INSERT OR IGNORE) so a re-run does not collide with
    an existing seed. The seed yields the same role set the live
    database has: {Pre-super-cl, Pre-imple-cl, Pre-review-cl}.
    """
    conn = sqlite3.connect(seeded_db_path)
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO bridge_flows
                (flow_key, name, description, step_order,
                 is_default, is_active)
            VALUES (?, ?, ?, ?, 0, 1)
            """,
            (
                "preferred_cloud",
                "preferred_cloud (seeded for trace tests)",
                "Minimal flow used by tests/test_bridge_trace.py.",
                "Pre-super-cl,Pre-imple-cl,Pre-review-cl",
            ),
        )
        steps = [
            ("s-impl-review", "Pre-imple-cl", "Pre-review-cl"),
            ("s-review-super", "Pre-review-cl", "Pre-super-cl"),
            ("s-super-impl", "Pre-super-cl", "Pre-imple-cl"),
        ]
        for step_key, from_role, to_role in steps:
            conn.execute(
                """
                INSERT OR IGNORE INTO bridge_flow_steps
                    (flow_key, step_key, from_role, to_role,
                     is_active, sort_order)
                VALUES (?, ?, ?, ?, 1, 0)
                """,
                ("preferred_cloud", step_key, from_role, to_role),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def trace_db(seeded_db_path: str) -> str:
    """Temp DB with preferred_cloud + the three Pre-* role step rows seeded."""
    _seed_trace_rows(seeded_db_path)
    return seeded_db_path


@pytest.fixture()
def trace_log_dir(monkeypatch, tmp_path):
    """Redirect the route to a tmp_path bridge dir; yield the path.

    The monkeypatched env var is what the route sees at request time
    because the handler calls ``config.get_bridge_dir()`` on every
    invocation (not at import time). Writing trace.log under the
    yielded path is the test's responsibility.
    """
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir()
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", str(bridge_dir))
    return bridge_dir


def _write_log(path, lines: list[str]) -> None:
    """Write a fixture trace.log verbatim — no header, no trailing newline manipulation."""
    with open(path, "w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line)
            handle.write("\n")


# ---------------------------------------------------------------------------
# Testgoals pin the names; the bodies pin the semantics.
# ---------------------------------------------------------------------------


def test_unknown_flow_returns_404(
    trace_db: str, trace_log_dir, client: TestClient
) -> None:
    """An unknown flow_key returns 404; the detail names the offending key."""
    response = client.get("/api/bridge-v2/flows/no-such-flow/trace")
    assert response.status_code == 404, response.text
    detail = response.json().get("detail", "")
    assert "no-such-flow" in detail, (
        f"detail must name the offending flow; got {detail!r}"
    )


def test_trace_returns_field_parsed_entries(
    trace_db: str, trace_log_dir, client: TestClient
) -> None:
    """Modern preferred_cloud lines are returned with exactly the six keys and the exact field values.

    Pins the field-splitting contract. Every entry is checked
    byte-equal against the fixture (no normalization, no
    re-encoding) so an accidental transformation would fail.
    """
    log_path = trace_log_dir / "trace.log"
    _write_log(log_path, [
        "2026-08-08T10:44:59Z | Pre-super-cl->Pre-imple-cl | 023 | dispatched | manual | Handoff 023-handoff.md dispatched to Pre-imple-cl",
        "2026-08-08T10:50:12Z | Pre-imple-cl->Pre-review-cl | 023 | signal_complete | manual | Callback dispatched to Pre-review-cl",
        "2026-08-08T10:55:00Z | Pre-review-cl->Pre-super-cl | 023 | signal_complete | manual | Verdict delivered to Pre-super-cl",
    ])

    response = client.get("/api/bridge-v2/flows/preferred_cloud/trace")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["flow_key"] == "preferred_cloud"
    entries = body["entries"]
    assert len(entries) == 3, entries
    expected = [
        {
            "timestamp": "2026-08-08T10:44:59Z",
            "from_role": "Pre-super-cl",
            "to_role": "Pre-imple-cl",
            "handoff_id": "023",
            "event": "dispatched",
            "message": "Handoff 023-handoff.md dispatched to Pre-imple-cl",
        },
        {
            "timestamp": "2026-08-08T10:50:12Z",
            "from_role": "Pre-imple-cl",
            "to_role": "Pre-review-cl",
            "handoff_id": "023",
            "event": "signal_complete",
            "message": "Callback dispatched to Pre-review-cl",
        },
        {
            "timestamp": "2026-08-08T10:55:00Z",
            "from_role": "Pre-review-cl",
            "to_role": "Pre-super-cl",
            "handoff_id": "023",
            "event": "signal_complete",
            "message": "Verdict delivered to Pre-super-cl",
        },
    ]
    for actual, want in zip(entries, expected):
        assert set(actual.keys()) == set(want.keys()), (
            f"entry keys must be exactly the six contract keys; got {sorted(actual.keys())!r}"
        )
        for key, value in want.items():
            assert actual[key] == value, (
                f"entry[{key!r}] must equal fixture value byte-equal; "
                f"got {actual[key]!r} != {value!r}"
            )


def test_same_id_other_flow_entry_excluded(
    trace_db: str, trace_log_dir, client: TestClient
) -> None:
    """A same-``handoff_id`` line from another flow is excluded; the preferred_cloud line is included.

    Pins the role-set filter: handoff_id plays no part in the
    filter. The classic "review01SG in imple01SG->review01SG" trap
    is exactly what this test guards against.
    """
    log_path = trace_log_dir / "trace.log"
    _write_log(log_path, [
        # Other-flow line: same handoff_id, roles not in preferred_cloud.
        "2026-08-08T09:00:00Z | imple01SG->review01SG | 023 | dispatched | manual | strict_review chain step",
        # preferred_cloud line: same handoff_id, roles in the flow's role set.
        "2026-08-08T10:44:59Z | Pre-super-cl->Pre-imple-cl | 023 | dispatched | manual | Handoff 023-handoff.md dispatched to Pre-imple-cl",
    ])

    response = client.get("/api/bridge-v2/flows/preferred_cloud/trace")
    assert response.status_code == 200, response.text
    entries = response.json()["entries"]
    assert len(entries) == 1, (
        f"the other-flow line must be excluded; got entries={entries!r}"
    )
    only = entries[0]
    assert only["from_role"] == "Pre-super-cl"
    assert only["to_role"] == "Pre-imple-cl"
    assert only["handoff_id"] == "023"
    assert "strict_review" not in only["message"]


def test_malformed_lines_skipped(
    trace_db: str, trace_log_dir, client: TestClient
) -> None:
    """Comments, empty lines, 5-field old-era lines, and unicode-arrow lines are skipped; valid lines pass through.

    Pins the parse contract:
      - lines starting with "#" → skip
      - empty line → skip
      - 5-field pre-2025 era ("TIMESTAMP | INIT | bridge | created | msg")
        → skipped by the len(parts) < 6 guard
      - unicode-arrow era ("TIMESTAMP | L→C | 001 | completed | msg") →
        skipped by the 2-name guard (splitting "L→C" on "->" yields 1 name)
      - 6-field modern line with a " | " inside the message → kept
        intact because of maxsplit=5
    No 500; only the valid entries are returned.
    """
    log_path = trace_log_dir / "trace.log"
    _write_log(log_path, [
        "# Bridge Trace Log — Append-only",
        "# Format: TIMESTAMP | DIRECTION | HANDOFF_ID | STATUS | SUMMARY",
        "",
        "2026-06-14T09:37:00Z | INIT | bridge | created | Tovejs-bridge infrastruktur oprettet: reviewtoimplementor/ + implementertoreview/",
        "2026-06-14T07:43:28Z | L\u2192C | 001 | completed | Bridge test read-only OK",
        "2026-08-08T10:44:59Z | Pre-super-cl->Pre-imple-cl | 023 | dispatched | manual | Handoff 023-handoff.md dispatched to Pre-imple-cl",
        "2026-08-08T10:50:12Z | Pre-imple-cl->Pre-review-cl | 023 | signal_complete | manual | Callback dispatched to Pre-review-cl with note: a | b | c",
    ])

    response = client.get("/api/bridge-v2/flows/preferred_cloud/trace")
    assert response.status_code == 200, response.text
    entries = response.json()["entries"]
    assert len(entries) == 2, (
        f"only the two valid 6-field lines must be returned; got entries={entries!r}"
    )
    # The message with embedded " | " separators stays intact because
    # the parser uses maxsplit=5.
    assert entries[1]["message"] == (
        "Callback dispatched to Pre-review-cl with note: a | b | c"
    ), f"maxsplit=5 must keep embedded ' | ' intact; got message={entries[1]['message']!r}"


def test_limit_returns_last_n_entries(
    trace_db: str, trace_log_dir, client: TestClient
) -> None:
    """5 matching lines + limit=2 → exactly the last 2, in file order (oldest first within the slice)."""
    log_path = trace_log_dir / "trace.log"
    _write_log(log_path, [
        "2026-08-08T10:00:00Z | Pre-super-cl->Pre-imple-cl | 001 | dispatched | manual | line one",
        "2026-08-08T10:01:00Z | Pre-super-cl->Pre-imple-cl | 002 | dispatched | manual | line two",
        "2026-08-08T10:02:00Z | Pre-super-cl->Pre-imple-cl | 003 | dispatched | manual | line three",
        "2026-08-08T10:03:00Z | Pre-super-cl->Pre-imple-cl | 004 | dispatched | manual | line four",
        "2026-08-08T10:04:00Z | Pre-super-cl->Pre-imple-cl | 005 | dispatched | manual | line five",
    ])

    response = client.get(
        "/api/bridge-v2/flows/preferred_cloud/trace?limit=2"
    )
    assert response.status_code == 200, response.text
    entries = response.json()["entries"]
    assert [e["message"] for e in entries] == ["line four", "line five"], (
        f"limit=2 must return the last 2 matches in file order; got {[e['message'] for e in entries]!r}"
    )

    # Default limit=50 covers the 5-line fixture.
    response_default = client.get("/api/bridge-v2/flows/preferred_cloud/trace")
    assert response_default.status_code == 200
    assert len(response_default.json()["entries"]) == 5


def test_trace_log_missing_returns_empty_entries(
    trace_db: str, trace_log_dir, client: TestClient
) -> None:
    """A bridge dir with no trace.log yields HTTP 200 and an empty entries list."""
    # No log written under trace_log_dir.
    response = client.get("/api/bridge-v2/flows/preferred_cloud/trace")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["flow_key"] == "preferred_cloud"
    assert body["entries"] == [], (
        f"a missing trace.log must yield an empty feed; got {body!r}"
    )


def test_out_of_range_limit_is_fastapi_422(
    trace_db: str, trace_log_dir, client: TestClient
) -> None:
    """Out-of-range limit (0 or 501) is FastAPI's own 422 (Query ge=1, le=500)."""
    for bad in ("0", "501"):
        response = client.get(
            f"/api/bridge-v2/flows/preferred_cloud/trace?limit={bad}"
        )
        assert response.status_code == 422, (
            f"limit={bad} must be FastAPI 422; got {response.status_code} {response.text!r}"
        )
