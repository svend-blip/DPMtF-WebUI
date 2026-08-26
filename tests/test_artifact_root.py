"""The shared artifact root: one resolver, byte-compat, and the security property.

Two-flow specification §1/§2 (TWO-FLOW-PLOOP-ELOOP.md): two orchestration
flows may share one durable artifact structure via
`bridge_flows.artifact_root`, resolved by exactly one canonical helper. Three
contracts are pinned here:

- `byte_compat`: a flow with NULL root derives byte-for-byte the paths it
  derived before the column existed. Expected paths are HARDCODED LITERALS,
  never computed by the code under test — an oracle computed by the same
  code it checks only proves the code agrees with itself.
- `shared_root`: two flows with the same artifact_root resolve broker Run
  destinations under the same root.
- `caller_supplied`: no broker Run-artifact destination is caller-supplied.
  The destination remains a pure function of registered identity.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts" / "bridgeV002"))

import bridge_broker  # noqa: E402
import bridge_lib  # noqa: E402


def _make_db(rows):
    """A minimal bridge_flows table with the given (flow_key, artifact_root)."""
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE bridge_flows (flow_key TEXT PRIMARY KEY, artifact_root TEXT NULL)"
    )
    conn.executemany("INSERT INTO bridge_flows VALUES (?, ?)", rows)
    conn.commit()
    conn.close()
    return path


class TestResolver(unittest.TestCase):
    def test_null_root_resolves_to_the_flow_key(self):
        db = _make_db([("alpha", None)])
        self.assertEqual(
            bridge_lib.get_effective_artifact_root("alpha", db_path=db), "alpha")

    def test_set_root_wins(self):
        db = _make_db([("1000-01-PLOOP", "1000"), ("1000-02-ELOOP", "1000")])
        self.assertEqual(
            bridge_lib.get_effective_artifact_root("1000-01-PLOOP", db_path=db),
            "1000")
        self.assertEqual(
            bridge_lib.get_effective_artifact_root("1000-02-ELOOP", db_path=db),
            "1000")

    def test_empty_and_whitespace_roots_mean_unset(self):
        db = _make_db([("a", ""), ("b", "   ")])
        self.assertEqual(bridge_lib.get_effective_artifact_root("a", db_path=db), "a")
        self.assertEqual(bridge_lib.get_effective_artifact_root("b", db_path=db), "b")

    def test_unknown_flow_degrades_to_identity_not_a_crash(self):
        """A read-only status probe must not crash on a lookup failure."""
        db = _make_db([])
        self.assertEqual(
            bridge_lib.get_effective_artifact_root("ghost", db_path=db), "ghost")

    def test_unreadable_db_degrades_to_identity(self):
        self.assertEqual(
            bridge_lib.get_effective_artifact_root(
                "x", db_path="/nonexistent/nowhere.db"), "x")


class TestByteCompat(unittest.TestCase):
    """NULL-root flows derive EXACTLY the pre-column paths.

    The expected strings below are literals transcribed from the broker's
    f-strings as they stood before this change (commit 0fda552's tree), not
    computed. If a literal here ever needs "updating to match the code",
    stop: that is the incompatibility this test exists to catch.
    """

    def setUp(self):
        self.db = _make_db([("preferred_cloud_harness", None)])
        self._orig = bridge_lib.get_effective_artifact_root
        # Route the broker's resolver call at our fixture DB, changing ONLY
        # the db it reads — the resolution logic under test stays live.
        bridge_lib.get_effective_artifact_root = (
            lambda fk, db_path=None, _o=self._orig, _db=self.db: _o(fk, db_path=_db))

    def tearDown(self):
        bridge_lib.get_effective_artifact_root = self._orig

    def _dest(self, **kwargs):
        return bridge_broker._canonical_destination(**kwargs)

    def test_byte_compat_backlog(self):
        got = self._dest(flow_key="preferred_cloud_harness", run_id=37,
                         handoff_id=None, artifact_type="backlog")
        want = f"{bridge_broker._get_bridge_dir()}/preferred_cloud_harness/runs/037/BACKLOG.md"
        self.assertEqual(got, want)

    def test_byte_compat_run_ledger(self):
        got = self._dest(flow_key="preferred_cloud_harness", run_id=37,
                         handoff_id=None, artifact_type="run-ledger")
        want = f"{bridge_broker._get_bridge_dir()}/preferred_cloud_harness/runs/037/RUN-LEDGER.md"
        self.assertEqual(got, want)

    def test_byte_compat_end_report(self):
        got = self._dest(flow_key="preferred_cloud_harness", run_id=37,
                         handoff_id=None, artifact_type="end-report")
        want = f"{bridge_broker._get_bridge_dir()}/preferred_cloud_harness/runs/037/END-REPORT.md"
        self.assertEqual(got, want)

    def test_byte_compat_handoff(self):
        got = self._dest(flow_key="preferred_cloud_harness", run_id=None,
                         handoff_id=138, artifact_type="handoff")
        want = f"{bridge_broker._get_bridge_dir()}/preferred_cloud_harness/handoffs/138-handoff.md"
        self.assertEqual(got, want)

    def test_byte_compat_escalation_response_is_flow_independent(self):
        """Never flow-keyed before, must not become so now."""
        got = self._dest(flow_key="preferred_cloud_harness", run_id=None,
                         handoff_id=140, artifact_type="escalation-response",
                         role_key="archi01")
        want = f"{bridge_broker._get_bridge_dir()}/escalations/140-archi01-response.md"
        self.assertEqual(got, want)


class TestSharedRoot(unittest.TestCase):
    def setUp(self):
        self.db = _make_db([("1000-01-PLOOP", "1000"), ("1000-02-ELOOP", "1000")])
        self._orig = bridge_lib.get_effective_artifact_root
        bridge_lib.get_effective_artifact_root = (
            lambda fk, db_path=None, _o=self._orig, _db=self.db: _o(fk, db_path=_db))

    def tearDown(self):
        bridge_lib.get_effective_artifact_root = self._orig

    def test_shared_root_run_artifacts_converge(self):
        """Both flows' broker Run state lands under the SAME 1000/ paths."""
        a = bridge_broker._canonical_destination(
            flow_key="1000-01-PLOOP", run_id=1, handoff_id=None,
            artifact_type="run-ledger")
        b = bridge_broker._canonical_destination(
            flow_key="1000-02-ELOOP", run_id=1, handoff_id=None,
            artifact_type="run-ledger")
        self.assertEqual(a, b)
        self.assertEqual(
            a, f"{bridge_broker._get_bridge_dir()}/1000/runs/001/RUN-LEDGER.md")

    def test_shared_root_handoffs_converge(self):
        a = bridge_broker._canonical_destination(
            flow_key="1000-02-ELOOP", run_id=None, handoff_id=5,
            artifact_type="handoff")
        self.assertEqual(
            a, f"{bridge_broker._get_bridge_dir()}/1000/handoffs/005-handoff.md")


class TestCallerSupplied(unittest.TestCase):
    """The security property: destinations are computed, never accepted."""

    def test_caller_supplied_destination_parameter_does_not_exist(self):
        import inspect
        params = inspect.signature(
            bridge_broker._canonical_destination).parameters
        forbidden = {"path", "dest", "destination", "output", "target_path"}
        self.assertFalse(forbidden & set(params),
                         "_canonical_destination must accept no path input")

    def test_caller_supplied_path_absent_from_the_materialize_cli(self):
        """The CLI surface offers no way to name a filesystem destination."""
        import argparse
        captured = []
        # _ActionsContainer, not ArgumentParser: add_argument lives on the
        # container base class, and subparser/group calls resolve there. A
        # spy on ArgumentParser alone captures nothing from subcommands —
        # measured: the m2 mutation (a --dest argument injected into the
        # materialize subparser) left the first version of this test green.
        orig = argparse._ActionsContainer.add_argument

        def spy(self, *names, **kw):
            captured.extend(n for n in names if isinstance(n, str))
            return orig(self, *names, **kw)

        argparse._ActionsContainer.add_argument = spy
        try:
            bridge_broker._build_parser()
        finally:
            argparse._ActionsContainer.add_argument = orig
        forbidden = {"--path", "--dest", "--destination", "--output", "--out"}
        self.assertFalse(forbidden & set(captured),
                         f"materialize CLI grew a path argument: "
                         f"{forbidden & set(captured)}")

    def test_caller_supplied_root_is_read_from_the_flow_row_only(self):
        """The resolver consults the registered row, not its arguments."""
        import inspect
        params = set(inspect.signature(
            bridge_lib.get_effective_artifact_root).parameters)
        self.assertEqual(params, {"flow_key", "db_path"},
                         "the resolver takes identity, never a root value")


if __name__ == "__main__":
    unittest.main()
