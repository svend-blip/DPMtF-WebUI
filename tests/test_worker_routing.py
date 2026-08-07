"""Tests for routing a handoff to a remote LightWorker (GOAL.md §8, §20).

The property that matters most is the boring one: **this must change nothing
today.** No role has an `execution_target`, so every dispatch on this machine
must take the path it always has. A routing change that quietly activates
itself on merge leaves nobody a moment to look at it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))
sys.path.insert(0, str(PROJECT_ROOT))

from worker_routing import execution_id, offer_to_worker, worker_target  # noqa: E402


class TestItIsInertUntilARoleIsGivenATarget:

    def test_a_role_without_the_column_runs_here(self):
        assert worker_target({"role_key": "imple01"}) is None

    def test_null_runs_here(self):
        assert worker_target({"execution_target": None}) is None

    @pytest.mark.parametrize("value", ["", "   ", "\t"])
    def test_blank_is_not_a_worker(self, value):
        """A column defaulted to '' by some later migration must not route
        a live role off-box because the string was falsy-but-present."""
        assert worker_target({"execution_target": value}) is None

    def test_only_the_intended_roles_route_off_box(self):
        """Asserted against the live database, not against fixtures.

        This began as "no role routes off-box", which held until migration
        031 gave imple01LW a target on purpose. The protection is worth
        keeping, so it became a list: a role that acquires an
        execution_target without being named here still fails, and being
        named here means somebody decided it.
        """
        import sqlite3
        import config
        expected = {"imple01LW": "svend3060"}
        conn = sqlite3.connect(config.get_db_path())
        rows = conn.execute(
            "SELECT role_key, execution_target FROM bridge_roles").fetchall()
        conn.close()
        routed = {r[0]: worker_target({"execution_target": r[1]})
                  for r in rows if worker_target({"execution_target": r[1]})}
        assert routed == expected, (
            f"off-box routing changed: {routed} (expected {expected}). "
            "Add a role here only when its remote execution is intended.")


class TestWhenATargetIsSet:

    def test_a_target_is_returned(self):
        assert worker_target({"execution_target": "svend3060"}) == "svend3060"

    def test_surrounding_whitespace_is_not_part_of_the_name(self):
        assert worker_target({"execution_target": " svend3060 "}) == "svend3060"

    def test_execution_id_follows_the_specification(self):
        """§5.1 writes EXEC-123-IMPLE01; §16.4 nests ATTEMPT-1 inside it."""
        assert execution_id("123", "imple01") == "EXEC-123-IMPLE01"

    def test_the_offer_reaches_the_store_with_the_handoff_reference(self, tmp_path):
        from routers.lightworker_store import SqliteLightWorkerStore
        store = SqliteLightWorkerStore(str(tmp_path / "s.db"))
        eid = offer_to_worker(
            worker_id="svend3060", handoff_id="014", flow_key="preferred_cloud",
            to_role_key="imple01", handoff_path="/flows/x/handoffs/014-handoff.md",
            store=store,
        )
        assert eid == "EXEC-014-IMPLE01"
        offered = store.offer_next("svend3060")
        assert offered["execution_id"] == eid
        assert offered["handoff_id"] == "014"
        assert offered["target_role"] == "imple01"

    def test_the_offer_says_it_is_not_a_complete_envelope(self, tmp_path):
        """§13's envelope is not built. The offer must not pretend otherwise.

        A worker that claims this and finds no repository, base commit or
        result contract should be able to see why from the offer itself.
        """
        from routers.lightworker_store import SqliteLightWorkerStore
        store = SqliteLightWorkerStore(str(tmp_path / "s.db"))
        offer_to_worker(
            worker_id="svend3060", handoff_id="014", flow_key="preferred_cloud",
            to_role_key="imple01", handoff_path="/x.md", store=store,
        )
        assert store.offer_next("svend3060")["envelope_complete"] is False


def test_dispatch_checks_the_target_before_it_reaches_tmux():
    """The branch must sit ahead of session handling, not inside it.

    A role that runs elsewhere has no session on this host; reaching
    session_alive() at all would fail it for the wrong reason.
    """
    src = (PROJECT_ROOT / "scripts" / "bridgeV002" / "dispatch.py").read_text(
        encoding="utf-8")
    body = src.split("def signal_send(")[1]
    assert "worker_target(to_role_data)" in body, "dispatch never checks the target"
    assert body.index("worker_target(to_role_data)") < body.index("session_alive("), \
        "the worker branch sits after tmux session handling"


# ---------------------------------------------------------------------------
# The §13 envelope
#
# The worker's envelope_validator.py is the specification, and it is committed
# in the other repository. These tests build an envelope the way dispatch does
# and hand it to that validator: a green here means the two halves of the
# protocol agree, which no amount of reading either side proves on its own.
# ---------------------------------------------------------------------------

LIGHTWORKER_SRC = Path("/home/svend/DPMtF-LightWorker/src")
_has_worker = LIGHTWORKER_SRC.is_dir()
requires_worker = pytest.mark.skipif(
    not _has_worker, reason="DPMtF-LightWorker is not checked out beside this repo")


def _payload_and_role():
    import sqlite3
    import config
    conn = sqlite3.connect(config.get_db_path())
    conn.row_factory = sqlite3.Row
    role = dict(conn.execute(
        "SELECT * FROM bridge_roles WHERE role_key='Pre-imple-cl'").fetchone())
    step = dict(conn.execute(
        "SELECT * FROM bridge_flow_steps WHERE flow_key='preferred_cloud'"
        " AND to_role='Pre-imple-cl'").fetchone())
    conn.close()
    return {
        "flow_key": "preferred_cloud", "step_key": step["step_key"],
        "from_role": step["from_role"], "to_role": step["to_role"],
        "deliverable_dir": step["deliverable_dir"],
        "deliverable_file": "013-handoff.md",
    }, role


def _build(handoff_file: Path):
    from worker_routing import build_envelope
    payload, role = _payload_and_role()
    return build_envelope(
        worker_id="svend3060", handoff_id="013", payload=payload,
        to_role_data=role, target_project="/home/svend/DPMtF-LightWorker",
        handoff_path=str(handoff_file))


@requires_worker
def test_fathers_envelope_passes_the_workers_own_validator(tmp_path):
    sys.path.insert(0, str(LIGHTWORKER_SRC))
    from dpmtf_lightworker.envelope_validator import (  # noqa: E402
        ValidatorConfig, validate_envelope)

    handoff = tmp_path / "013-handoff.md"
    handoff.write_text("<task>do the thing</task>", encoding="utf-8")
    env = _build(handoff)

    validated = validate_envelope(env, config=ValidatorConfig(
        worker_id="svend3060",
        supported_schema_versions=frozenset({"1"}),
        supported_clients=frozenset({"opencode", "claude-code"}),
        repository_root=Path("/home/svend/lightworker/repos")))

    assert validated.execution_id == "EXEC-013-PRE-IMPLE-CL"
    assert validated.model_source == "model_allocator"
    assert len(validated.repository.base_commit) == 40


@requires_worker
def test_the_base_commit_is_the_target_projects_real_head(tmp_path):
    """§16.1: the exact commit, never a branch name or an inferred revision."""
    import subprocess
    handoff = tmp_path / "013-handoff.md"
    handoff.write_text("x", encoding="utf-8")
    head = subprocess.run(
        ["git", "-C", "/home/svend/DPMtF-LightWorker", "rev-parse", "HEAD"],
        capture_output=True, text=True).stdout.strip()
    assert _build(handoff)["repository"]["base_commit"] == head


def test_an_unbuildable_envelope_raises_rather_than_shipping_partial(tmp_path):
    """A worker learns of a missing base commit only after cloning and
    starting a model. Refuse at the point where it is cheap."""
    from worker_routing import EnvelopeIncomplete, build_envelope
    payload, role = _payload_and_role()
    handoff = tmp_path / "h.md"
    handoff.write_text("x", encoding="utf-8")
    not_a_repo = tmp_path / "empty"
    not_a_repo.mkdir()
    with pytest.raises(EnvelopeIncomplete, match="base commit"):
        build_envelope(worker_id="svend3060", handoff_id="013", payload=payload,
                       to_role_data=role, target_project=str(not_a_repo),
                       handoff_path=str(handoff))


def test_a_role_without_an_alias_is_refused(tmp_path):
    """§6.2 makes the alias Father's to choose; an empty one is not a choice."""
    from worker_routing import EnvelopeIncomplete, build_envelope
    payload, role = _payload_and_role()
    role["default_model_alias"] = ""
    handoff = tmp_path / "h.md"
    handoff.write_text("x", encoding="utf-8")
    with pytest.raises(EnvelopeIncomplete, match="alias"):
        build_envelope(worker_id="svend3060", handoff_id="013", payload=payload,
                       to_role_data=role,
                       target_project="/home/svend/DPMtF-LightWorker",
                       handoff_path=str(handoff))
