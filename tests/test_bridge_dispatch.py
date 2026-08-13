"""Tests for routers/bridge.py: POST /api/bridge-v2/flows/{flow_key}/dispatch.

The bridge chain is LIVE in tmux on this machine, so every test that
reaches the spawn step MUST monkeypatch ``routers.bridge.subprocess.run``
(or the equivalent module-level name) — a real ``dispatch.py`` fired
from the test suite would inject a prompt into a live role session.
The monkeypatched fake records every call and returns whatever the
test asks it to return (a fake CompletedProcess, a TimeoutExpired,
or a spawn-side exception). The validation-only tests also assert the
fake was never called.

The dispatch route validates the flow and the two roles against the
database BEFORE spawning the subprocess, so the validation tests do
not need a real subprocess. They do, however, need the temp DB to
carry the seed rows (preferred_cloud flow + Pre-super-cl + Pre-imple-cl
roles) — the conftest's ``seeded_db_path`` ships with test_flow /
test_role only, so the dispatch tests install their own seeds.
"""

from __future__ import annotations

import sqlite3
import subprocess
from typing import Any, List

import pytest
from fastapi.testclient import TestClient


# Sentinel return value for the "valid dispatch" test. The fake's
# returncode and stream values are picked so the test cannot pass by
# accident: anything other than the verbatim sentinels would fail the
# exit_code / stdout / stderr assertions.
_SENTINEL_STDOUT = "DISPATCH-SENTINEL-STDOUT-line\n"
_SENTINEL_STDERR = "DISPATCH-SENTINEL-STDERR-line\n"
_SENTINEL_EXIT = 3


def _seed_dispatch_rows(seeded_db_path: str) -> None:
    """Insert the preferred_cloud flow + Pre-super-cl/Pre-imple-cl roles.

    Idempotent: uses INSERT OR IGNORE so a re-run does not collide
    with an existing seed. The seeded rows carry the minimum columns
    the dispatch route queries (``flow_key`` / ``is_active`` and
    ``role_key`` / ``is_active``) — the route does not read any
    other column.
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
                "preferred_cloud (seeded for dispatch tests)",
                "Minimal flow used by tests/test_bridge_dispatch.py.",
                "Pre-super-cl,Pre-imple-cl",
            ),
        )
        for role_key in ("Pre-super-cl", "Pre-imple-cl"):
            conn.execute(
                """
                INSERT OR IGNORE INTO bridge_roles
                    (role_key, tmux_session, start_cmd,
                     default_model_source, default_model_alias, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (
                    role_key,
                    f"{role_key}-tmux",
                    f"echo {role_key}",
                    "model_allocator",
                    f"{role_key}-alias",
                ),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def dispatch_db(seeded_db_path: str) -> str:
    """Temp DB with preferred_cloud + the two Pre-* roles seeded.

    Builds on the conftest's ``seeded_db_path`` (which already has
    test_flow + test_role) so the rest of the suite can keep using
    its seeds unchanged.
    """
    _seed_dispatch_rows(seeded_db_path)
    return seeded_db_path


class _SpawnRecorder:
    """A drop-in for ``subprocess.run`` that records every call and returns a fixed result.

    Tests configure ``return_value`` for the happy path (a fake
    ``CompletedProcess``) or set ``raise_exc`` to surface a
    ``TimeoutExpired`` / spawn-side exception. The ``calls`` list
    carries the argv of every invocation, so the "no spawn" tests
    can assert the recorder was never called.
    """

    def __init__(
        self,
        return_value: subprocess.CompletedProcess | None = None,
        raise_exc: BaseException | None = None,
    ) -> None:
        self.return_value = return_value
        self.raise_exc = raise_exc
        self.calls: List[List[str]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
        if args:
            argv = list(args[0])
        else:
            argv = list(kwargs.get("args", []))
        self.calls.append(argv)
        if self.raise_exc is not None:
            raise self.raise_exc
        if self.return_value is not None:
            return self.return_value
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")


@pytest.fixture()
def spawn_recorder(monkeypatch):
    """Yield a ``_SpawnRecorder`` wired into ``routers.bridge.subprocess.run``.

    The recorder replaces ``subprocess.run`` at the module level so
    every call site in ``routers/bridge.py`` — the new dispatch route
    AND the existing flow-level endpoints — sees the same fake. The
    new route is the only one the dispatch tests exercise, so the
    recorder's call count is the test's source of truth.
    """
    import routers.bridge as bridge_module

    recorder = _SpawnRecorder()
    monkeypatch.setattr(bridge_module.subprocess, "run", recorder)
    return recorder


# ---------------------------------------------------------------------------
# Testgoals pin the names; the bodies pin the semantics.
# ---------------------------------------------------------------------------


def test_unknown_flow_returns_404_and_spawns_nothing(
    dispatch_db: str, client: TestClient, spawn_recorder: _SpawnRecorder
) -> None:
    """A flow_key that is not in bridge_flows returns 404 AND never spawns dispatch.py.

    Pin TG-level contract: a missing flow is a 404 (not 422) and the
    spawn recorder must remain empty. The body uses a real flow
    (preferred_cloud is now seeded into the temp DB) so the test
    flips the expectation: the 404 fires on the unknown flow name.
    """
    response = client.post(
        "/api/bridge-v2/flows/no-such-flow/dispatch",
        json={"from_role": "Pre-super-cl", "to_role": "Pre-imple-cl"},
    )
    assert response.status_code == 404, response.text
    assert "no-such-flow" in response.json().get("detail", "")
    assert spawn_recorder.calls == [], (
        f"validation failure must not spawn dispatch.py; got calls={spawn_recorder.calls!r}"
    )


def test_unknown_role_returns_422_and_spawns_nothing(
    dispatch_db: str, client: TestClient, spawn_recorder: _SpawnRecorder
) -> None:
    """A role that is not in bridge_roles returns 422 with the role name in the detail AND never spawns dispatch.py.

    Pins the role-validation contract. The flow is real; one role is
    real; the other is fabricated. The detail MUST name the
    offending role(s) so the UI can show it, and the recorder MUST
    remain empty.
    """
    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/dispatch",
        json={"from_role": "Pre-super-cl", "to_role": "also-absent"},
    )
    assert response.status_code == 422, response.text
    detail = response.json().get("detail", "")
    assert "also-absent" in detail, (
        f"detail must name the offending role; got {detail!r}"
    )
    assert spawn_recorder.calls == [], (
        f"validation failure must not spawn dispatch.py; got calls={spawn_recorder.calls!r}"
    )


def test_valid_dispatch_returns_real_exit_code_and_output(
    dispatch_db: str, client: TestClient, spawn_recorder: _SpawnRecorder
) -> None:
    """A valid dispatch returns 200 with status "dispatch_error", exit_code 3, and both sentinels verbatim.

    The fake returncode is non-zero on purpose: the route must
    surface a non-zero dispatch exit in the 200 body — never a
    silent success, never a swallowed stderr (handoff step 1d).
    The sentinels are unique strings; the assertions on stdout and
    stderr are byte-equal so an accidental re-encoding of the
    streams would fail.
    """
    spawn_recorder.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=_SENTINEL_EXIT,
        stdout=_SENTINEL_STDOUT,
        stderr=_SENTINEL_STDERR,
    )

    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/dispatch",
        json={
            "from_role": "Pre-super-cl",
            "to_role": "Pre-imple-cl",
            "id": "019",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "dispatch_error", body
    assert body["exit_code"] == _SENTINEL_EXIT, body
    assert body["stdout"] == _SENTINEL_STDOUT, body
    assert body["stderr"] == _SENTINEL_STDERR, body

    # The spawn was made with exactly the validated values plus
    # --id 019. The argv must NOT carry other verbs (no
    # --signal-complete / --signal-escalation / --signal-answer).
    assert len(spawn_recorder.calls) == 1, spawn_recorder.calls
    argv = spawn_recorder.calls[0]
    assert "--db-flow" in argv and argv[argv.index("--db-flow") + 1] == "preferred_cloud"
    assert "--signal-send" in argv
    assert "--from-role" in argv and argv[argv.index("--from-role") + 1] == "Pre-super-cl"
    assert "--to-role" in argv and argv[argv.index("--to-role") + 1] == "Pre-imple-cl"
    assert "--id" in argv and argv[argv.index("--id") + 1] == "019"
    for forbidden in ("--signal-complete", "--signal-escalation", "--signal-answer"):
        assert forbidden not in argv, (
            f"the dispatch route must not pass {forbidden!r}; argv={argv!r}"
        )


def test_dispatch_omits_id_when_not_provided(
    dispatch_db: str, client: TestClient, spawn_recorder: _SpawnRecorder
) -> None:
    """When the body has no ``id``, the spawned argv must not carry --id.

    Handoff step 1c: ``--id`` is included only when the field was
    provided. A missing ``id`` must NOT be invented (the dispatch
    script's own default id generator kicks in).
    """
    spawn_recorder.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr="",
    )

    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/dispatch",
        json={"from_role": "Pre-super-cl", "to_role": "Pre-imple-cl"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok", body
    assert body["exit_code"] == 0, body

    assert len(spawn_recorder.calls) == 1, spawn_recorder.calls
    argv = spawn_recorder.calls[0]
    assert "--id" not in argv, argv


def test_timeout_returns_500(
    dispatch_db: str, client: TestClient, spawn_recorder: _SpawnRecorder
) -> None:
    """A TimeoutExpired from the spawned subprocess is surfaced as HTTP 500.

    Handoff step 1e: timeout → 500 with the error text. The test
    asserts the route maps TimeoutExpired to 500, not 200, and the
    spawn recorder was actually called.
    """
    spawn_recorder.raise_exc = subprocess.TimeoutExpired(
        cmd=["python3", "dispatch.py"], timeout=300,
    )

    response = client.post(
        "/api/bridge-v2/flows/preferred_cloud/dispatch",
        json={"from_role": "Pre-super-cl", "to_role": "Pre-imple-cl"},
    )
    assert response.status_code == 500, response.text
    detail = response.json().get("detail", "")
    assert "timed out" in detail or "TimeoutExpired" in detail, detail
    assert len(spawn_recorder.calls) == 1, (
        f"timeout test must have called subprocess.run exactly once; "
        f"got {spawn_recorder.calls!r}"
    )
