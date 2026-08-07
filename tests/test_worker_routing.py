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

    def test_every_role_in_the_live_database_runs_here(self):
        """The guarantee this change rests on, asserted against real data."""
        import sqlite3
        import config
        conn = sqlite3.connect(config.get_db_path())
        rows = conn.execute(
            "SELECT role_key, execution_target FROM bridge_roles").fetchall()
        conn.close()
        routed = [r[0] for r in rows if worker_target({"execution_target": r[1]})]
        assert not routed, f"roles would now route off-box: {routed}"


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
