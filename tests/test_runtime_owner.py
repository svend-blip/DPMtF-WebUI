"""Tests for D3 + D2 (run 007, handoff 028).

D3 — anchor precision (`_harness_child_pid` points at the harness child, never
the pane shell) and kill verification (`_default_kill` returns False when a
process survives SIGTERM past the bound).

D2 — coverage gap closure (stop_tmuxflow releases the flow's owned runtime
resources; `record()` upserts by primary key so re-running start_coding
refreshes the recorded pid, not duplicates it).

ALL tests use `db_path` overrides to a tmp SQLite — production DB is never
touched. Any real process spawned is killed in a `finally` block.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import signal
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import runtime_owner  # noqa: E402
import start_coding  # noqa: E402
from bridge_lib import _find_project_root  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _load(name, path):
    """Load a sibling module as if it were on sys.path."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_stop_tmuxflow():
    return _load(
        "stop_tmuxflow",
        PROJECT_ROOT / "scripts" / "bridgeV002" / "stop_tmuxflow.py",
    )


def _load_start_tmuxflow():
    return _load(
        "start_tmuxflow",
        PROJECT_ROOT / "scripts" / "bridgeV002" / "start_tmuxflow.py",
    )


def _load_start_coding():
    return start_coding  # already imported


@pytest.fixture
def tmp_db(tmp_path):
    """Isolated tmp DB — runtime_owner uses `flow_runtime_resources`."""
    db = str(tmp_path / "ro.db")
    conn = sqlite3.connect(db)
    conn.executescript(runtime_owner._TABLE_DDL)
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def tmux_available():
    """True iff tmux is reachable from this session (new-session succeeds)."""
    try:
        r = subprocess.run(
            ["tmux", "new-session", "-d", "-s", "ro_probe_" + uuid.uuid4().hex[:6],
             "-x", "120", "-y", "30"],
            capture_output=True, text=True, timeout=5,
        )
        # The probe session may have been created — clean up either way.
        subprocess.run(["tmux", "kill-session", "-t", "=ro_probe_empty"],
                       capture_output=True, timeout=2)
        # Find and kill the actual probe session by listing.
        ls = subprocess.run(
            ["tmux", "ls", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=5,
        )
        for line in (ls.stdout or "").splitlines():
            if line.startswith("ro_probe_"):
                subprocess.run(
                    ["tmux", "kill-session", "-t", "=" + line],
                    capture_output=True, timeout=2,
                )
        return r.returncode == 0
    except Exception:
        return False


def _scratch_session_name():
    """Unique tmux session name for a test."""
    return "ro_test_" + uuid.uuid4().hex[:8]


def _tmux_kill(session):
    """Best-effort cleanup. Never raises."""
    subprocess.run(["tmux", "kill-session", "-t", "=" + session],
                   capture_output=True, timeout=5)


# ===========================================================================
# D3 — anchor precision + kill verification
# ===========================================================================

class TestHarnessChildPidAnchor:
    """`start_coding._harness_child_pid` resolves the harness CHILD pid,
    not the pane shell pid (D3 step 1). The pane shell pid is the
    interactive bash of the tmux pane — TERM-immune — and recording it
    would defeat every Stop-servers attempt to actually stop the harness.

    All tests in this class scratch-create their own tmux session and
    tear it down in `finally`.
    """

    def test_child_pid_points_at_real_child_not_pane_shell(self, tmux_available):
        if not tmux_available:
            pytest.skip("tmux not reachable from this session")

        session = _scratch_session_name()
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session, "-x", "120", "-y", "30"],
            check=True, capture_output=True, timeout=5,
        )
        try:
            # Inject a dummy long-lived child via send-keys.
            dummy = (
                "python3 -c 'import time,sys;"
                "sys.stdout.write(\"ready\\n\");sys.stdout.flush();"
                "time.sleep(120)'"
            )
            subprocess.run(
                ["tmux", "send-keys", "-t", f"={session}:0", "-l", dummy],
                check=True, capture_output=True, timeout=5,
            )
            subprocess.run(
                ["tmux", "send-keys", "-t", f"={session}:0", "Enter"],
                check=True, capture_output=True, timeout=5,
            )

            child_pid = None
            for _ in range(40):  # up to ~4 s (40 * 0.1)
                child_pid = start_coding._harness_child_pid(session)
                if child_pid is not None:
                    break
                time.sleep(0.1)

            assert child_pid is not None, (
                f"dummy harness child did not appear under pane {session}; "
                f"_harness_child_pid timed out"
            )
            pane_pid = start_coding._pane_pid(session)
            assert pane_pid is not None
            # The anchor must NOT be the pane shell (the bug the live
            # incident surfaced — codex recorded 1510133 `-bash` while
            # the real child was 1511263).
            assert child_pid != pane_pid, (
                "anchor must point at the harness child, not the pane shell"
            )
        finally:
            _tmux_kill(session)

    def test_child_pid_returns_none_for_unknown_session(self):
        assert start_coding._harness_child_pid("definitely_not_a_real_session_zz") is None

    def test_record_harness_ownership_records_child_pid_when_available(
        self, tmux_available, tmp_path, monkeypatch,
    ):
        """The recorded pid is the child pid, never the pane shell pid."""
        if not tmux_available:
            pytest.skip("tmux not reachable from this session")

        session = _scratch_session_name()
        # Patch runtime_owner.record to write to the tmp DB.
        import runtime_owner as ro
        _orig_record = ro.record
        def _patched_record(*a, **k):
            k.pop("db_path", None)  # the test owns this — caller cannot override
            return _orig_record(*a, db_path=str(tmp_path / "ro.db"), **k)
        monkeypatch.setattr(ro, "record", _patched_record)

        # Patch _harness_child_pid to return a known child pid; _pane_pid
        # returns a different (pane-shell) pid. This is a test-mode
        # contract — the resolver itself is exercised by the previous
        # test.
        monkeypatch.setattr(start_coding, "_harness_child_pid", lambda _s, **_: 4242)
        monkeypatch.setattr(start_coding, "_pane_pid", lambda _s: 1111)

        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session, "-x", "120", "-y", "30"],
            check=True, capture_output=True, timeout=5,
        )
        try:
            start_coding._record_harness_ownership("scratch_flow", session)
            rows = ro.list_for_flow("scratch_flow", resource_type="harness_process",
                                    db_path=str(tmp_path / "ro.db"))
            assert len(rows) == 1
            assert rows[0]["pid"] == 4242
            assert rows[0]["pid"] != 1111  # never the pane shell pid
        finally:
            _tmux_kill(session)

    def test_record_harness_ownership_falls_back_to_pid_none_on_resolution_failure(
        self, tmp_path, monkeypatch,
    ):
        """When the resolver returns None, ownership is recorded with pid=None."""
        import runtime_owner as ro
        _orig_record2 = ro.record
        def _patched_record(*a, **k):
            k.pop("db_path", None)
            return _orig_record2(*a, db_path=str(tmp_path / "ro.db"), **k)
        monkeypatch.setattr(ro, "record", _patched_record)
        monkeypatch.setattr(start_coding, "_harness_child_pid", lambda _s, **_: None)

        # Must not raise even though the child cannot be resolved.
        start_coding._record_harness_ownership("scratch_flow", "no_such_session")
        rows = ro.list_for_flow("scratch_flow", resource_type="harness_process",
                                db_path=str(tmp_path / "ro.db"))
        assert len(rows) == 1
        assert rows[0]["pid"] is None


class TestVerifiedKill:
    """`_default_kill(pid)` returns True only when the process is verifiably
    gone within the bound. A surviving process is NOT reported stopped.
    """

    def test_process_survives_sigterm_is_not_reported_stopped(self):
        """`survive` (bound literally by GOAL.md section 2; `-k survive`
        must select this name and not deselect on a similarly-named test).

        Spawn a real Python child that ignores SIGTERM, ask `_default_kill`
        to stop it, and assert the verifier returns False. The child is
        SIGKILL'd in `finally`.
        """
        # Spawn a process that ignores SIGTERM but accepts SIGKILL.
        child = subprocess.Popen(
            ["python3", "-c",
             "import signal, time\n"
             "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
             "time.sleep(120)\n"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            # Give the child a moment to install its SIGTERM handler.
            time.sleep(0.3)
            assert child.poll() is None, f"child died unexpectedly with rc={child.returncode}"

            # Re-bind the kill bound to a value short enough that this
            # test stays fast (default is 3.0s; we use 0.5s).
            original = runtime_owner._KILL_VERIFY_BOUND_SECONDS
            runtime_owner._KILL_VERIFY_BOUND_SECONDS = 0.5
            try:
                result = runtime_owner._default_kill(child.pid)
            finally:
                runtime_owner._KILL_VERIFY_BOUND_SECONDS = original

            assert result is False, (
                "_default_kill must return False when the process survives "
                "SIGTERM past the bound — a surviving process must NOT be "
                "reported stopped"
            )
            # The child is still alive.
            assert child.poll() is None
        finally:
            # SIGKILL to clean up the child regardless of the test outcome.
            try:
                child.kill()
            except Exception:
                pass
            try:
                child.wait(timeout=5)
            except Exception:
                pass

    def test_verified_kill_for_already_dead_pid_returns_true(self):
        """Already-dead pid: the SIGTERM send raises ProcessLookupError,
        which is treated as 'stale claim, satisfied by the send itself'.
        """
        # 999999_999 is overwhelmingly unlikely to be a live pid in CI;
        # if a fluke hits, the test becomes non-deterministic. Use a value
        # we know is gone (a pid from a child that just exited).
        child = subprocess.Popen(["true"], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        child.wait()
        assert runtime_owner._default_kill(child.pid) is True

    def test_stop_owned_harness_processes_returns_only_verified_gone(self, tmp_db):
        """A process that survives SIGTERM must NOT appear in the stopped list."""
        # Spawn the SIGTERM-ignoring child.
        child = subprocess.Popen(
            ["python3", "-c",
             "import signal, time\n"
             "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
             "time.sleep(120)\n"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(0.3)
            runtime_owner.record("f", "harness_process", "stubborn", pid=child.pid,
                                 db_path=tmp_db)
            original = runtime_owner._KILL_VERIFY_BOUND_SECONDS
            runtime_owner._KILL_VERIFY_BOUND_SECONDS = 0.5
            try:
                stopped = runtime_owner.stop_owned_harness_processes("f", db_path=tmp_db)
            finally:
                runtime_owner._KILL_VERIFY_BOUND_SECONDS = original

            assert stopped == [], (
                "surviving process must NOT be reported stopped"
            )
            # Ownership row was NOT released (still alive process still owns).
            rows = runtime_owner.list_for_flow("f", resource_type="harness_process",
                                               db_path=tmp_db)
            assert len(rows) == 1
            assert rows[0]["pid"] == child.pid
        finally:
            try:
                child.kill()
            except Exception:
                pass
            try:
                child.wait(timeout=5)
            except Exception:
                pass

    def test_stop_owned_releases_pid_none_rows_with_no_kill_attempt(self, tmp_db, monkeypatch):
        """A row with pid=None is degraded to "no-op"; release is skipped
        because there is no pid to kill. Confirms the existing degrade
        path through stop_owned_harness_processes remains intact.
        """
        killed = []

        def _kill(pid):
            killed.append(pid)
            return True

        runtime_owner.record("f", "harness_process", "pidless", pid=None,
                             db_path=tmp_db)
        stopped = runtime_owner.stop_owned_harness_processes("f", db_path=tmp_db,
                                                             _kill=_kill)
        assert stopped == []
        assert killed == [], "no kill attempt should fire for pid=None"
        # Row is still there — release skipped because there was no kill.
        rows = runtime_owner.list_for_flow("f", resource_type="harness_process",
                                           db_path=tmp_db)
        assert len(rows) == 1 and rows[0]["pid"] is None

    def test_permission_error_returns_false(self, monkeypatch):
        """PermissionError on the SIGTERM send returns False (stops short)."""

        def fake_kill(pid, sig):
            raise PermissionError(f"nope for {pid}")

        monkeypatch.setattr(runtime_owner.os, "kill", fake_kill)
        assert runtime_owner._default_kill(1234) is False


# ===========================================================================
# D2 — coverage gap closure
# ===========================================================================

class TestRecordUpsert:
    """`record(flow, type, resource_id, pid)` does INSERT OR REPLACE — a
    re-run of start_coding refreshes the recorded pid rather than
    leaving a stale one (D2 step 5).
    """

    def test_record_same_resource_twice_upserts_pid(self, tmp_db):
        runtime_owner.record("f", "harness_process", "s1", pid=100, db_path=tmp_db)
        runtime_owner.record("f", "harness_process", "s1", pid=200, db_path=tmp_db)
        rows = runtime_owner.list_for_flow("f", resource_type="harness_process",
                                           db_path=tmp_db)
        assert len(rows) == 1, "INSERT OR REPLACE must NOT duplicate the row"
        assert rows[0]["pid"] == 200, "second record() call must update the pid"

    def test_record_refreshes_when_pid_changes(self, tmp_db):
        """Refreshing the pid corresponds to start_coding re-running with
        a different child process (the recorded harness pid has changed).
        """
        # First start_coding run (recorded pid=1234).
        runtime_owner.record("f", "harness_process", "session_x",
                             pid=1234, db_path=tmp_db)
        # Second start_coding run (recording refreshed pid=5678).
        runtime_owner.record("f", "harness_process", "session_x",
                             pid=5678, db_path=tmp_db)
        rows = runtime_owner.list_for_flow("f", resource_type="harness_process",
                                           db_path=tmp_db)
        assert len(rows) == 1
        assert rows[0]["pid"] == 5678


class TestReleaseForFlow:
    """`release_for_flow(flow_key)` drops every `flow_runtime_resources`
    row for the flow (D2 step 4). Used by stop_tmuxflow after the tmux
    teardown so dead ownership claims do not accumulate.
    """

    def test_release_for_flow_drops_all_resource_types(self, tmp_db):
        runtime_owner.record("f", "tmux_session", "ts1", pid=None, db_path=tmp_db)
        runtime_owner.record("f", "harness_process", "hp1", pid=42, db_path=tmp_db)
        runtime_owner.record("f", "tmux_session", "ts2", pid=None, db_path=tmp_db)
        runtime_owner.record("other", "tmux_session", "ots", pid=None, db_path=tmp_db)

        released = runtime_owner.release_for_flow("f", db_path=tmp_db)
        assert sorted(released) == ["hp1", "ts1", "ts2"]
        # All f-rows are gone, other-row untouched (ownership rule).
        assert runtime_owner.list_for_flow("f", db_path=tmp_db) == []
        other_rows = runtime_owner.list_for_flow("other", db_path=tmp_db)
        assert len(other_rows) == 1 and other_rows[0]["resource_id"] == "ots"

    def test_release_for_flow_returns_empty_for_unknown_flow(self, tmp_db):
        assert runtime_owner.release_for_flow("nonexistent", db_path=tmp_db) == []


class TestStopTmuxflowRelease:
    """stop_tmuxflow.py main() calls `runtime_owner.release_for_flow(args.flow_key)`
    after the tmux teardown (D2 step 4). We verify this by intercepting
    `release_for_flow` at the module level, running stop_tmuxflow.main(),
    and asserting the call was made with the expected flow_key. Behavior
    of `release_for_flow` itself is covered in `TestReleaseForFlow` above.

    The DB is isolated to the production DB (which stop_tmuxflow loads
    via config). To respect "never touch the production DB", we assert
    on the intercepted CALL only and do not assert on the production
    runtime table.
    """

    def test_stop_tmuxflow_main_calls_release_for_flow(self, monkeypatch, tmp_path):
        st = _load_stop_tmuxflow()

        # Stub out the tmux-side and remote-side interactions so the
        # test does not depend on a real session.
        monkeypatch.setattr(st, "kill_tmux_sessions",
                            lambda sessions: list(sessions))
        monkeypatch.setattr(st, "get_remote_roles",
                            lambda *a, **k: [])
        monkeypatch.setattr(st, "kill_remote_sessions",
                            lambda *a, **k: [])

        # Intercept release_for_flow so we can assert it was called,
        # without touching production DB.
        called = []

        def _fake_release(flow_key, db_path=None):
            called.append((flow_key, db_path))
            return []  # nothing to release for this test

        # Patch the binding that stop_tmuxflow sees.
        monkeypatch.setattr(st.runtime_owner, "release_for_flow", _fake_release)

        monkeypatch.setattr("sys.argv", ["stop_tmuxflow", "f"])
        st.main()

        assert len(called) == 1, (
            "stop_tmuxflow.main() must call release_for_flow exactly once "
            "after the tmux teardown"
        )
        assert called[0][0] == "f", (
            f"release_for_flow must be called with args.flow_key 'f', got {called[0][0]!r}"
        )

    def test_stop_tmuxflow_preserves_existing_kill_behavior(self, monkeypatch):
        """The existing remote/local kill behavior is unchanged (regression)."""
        st = _load_stop_tmuxflow()

        killed_local = []

        def _fake_kill_local(sessions):
            killed_local.extend(sessions)
            return list(sessions)

        killed_remote = []
        remote_roles = [("r1", "host1")]

        monkeypatch.setattr(st, "kill_tmux_sessions", _fake_kill_local)
        monkeypatch.setattr(st, "get_remote_roles", lambda *a, **k: remote_roles)
        monkeypatch.setattr(st, "kill_remote_sessions",
                            lambda roles: killed_remote.extend(roles) or [])
        monkeypatch.setattr(st.runtime_owner, "release_for_flow",
                            lambda *a, **k: [])

        # Inject `sessions = {"sessA", "sessB"}` by also stubbing the
        # get_flow_tmux_sessions that main() calls before kill_tmux_sessions.
        monkeypatch.setattr(st, "get_flow_tmux_sessions", lambda *a, **k: {"sessA", "sessB"})
        monkeypatch.setattr("sys.argv", ["stop_tmuxflow", "f"])
        st.main()

        # Local sessions are still killed.
        assert sorted(killed_local) == ["flow-f", "sessA", "sessB"]
        # Remote roles are still listed for the ssh kill.
        assert killed_remote == remote_roles


# ===========================================================================
# D3 — fresh-context integration (TG7)
# ===========================================================================

class TestFreshContextStopsRealChild:
    """A test NAME containing `fresh_context` (bound by GOAL.md TG7) —
    must select via `-k fresh_context` and run FOR REAL (not skip) when
    tmux is reachable.

    Steps:
      1. Create a scratch tmux session.
      2. Inject a dummy long-lived harness child into the pane.
      3. Resolve the harness CHILD pid (the harness anchor, not the pane shell).
      4. Record ownership in an isolated tmp DB.
      5. Apply the `work_unit` fresh-context stop (calls
         `stop_owned_harness_processes`).
      6. Assert the dummy child is verifiably terminated.
      7. Tear down the scratch session.
    """

    def test_fresh_context_stops_real_dummy_harness_child(
        self, tmp_path, tmux_available,
    ):
        if not tmux_available:
            pytest.skip("tmux not reachable from this session")

        session = _scratch_session_name()
        db = tmp_path / "ro.db"
        conn = sqlite3.connect(db)
        conn.executescript(runtime_owner._TABLE_DDL)
        conn.commit()
        conn.close()
        db_path = str(db)

        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session, "-x", "120", "-y", "30"],
            check=True, capture_output=True, timeout=5,
        )
        child_pid = None
        try:
            # Inject a real long-lived harness child via send-keys.
            dummy = (
                "python3 -c 'import sys,time;"
                "sys.stdout.write(\"ready\\n\");sys.stdout.flush();"
                "time.sleep(120)'"
            )
            subprocess.run(
                ["tmux", "send-keys", "-t", f"={session}:0", "-l", dummy],
                check=True, capture_output=True, timeout=5,
            )
            subprocess.run(
                ["tmux", "send-keys", "-t", f"={session}:0", "Enter"],
                check=True, capture_output=True, timeout=5,
            )

            # Wait for the child to appear (the anchor).
            for _ in range(40):
                child_pid = start_coding._harness_child_pid(session)
                if child_pid is not None:
                    break
                time.sleep(0.1)
            assert child_pid is not None, (
                f"dummy harness child did not appear in scratch session {session}"
            )
            pane_pid = start_coding._pane_pid(session)
            assert child_pid != pane_pid

            # Record the anchor (the child pid) and apply the work_unit stop.
            runtime_owner.record("scratch_flow", "harness_process", session,
                                 pid=child_pid, db_path=db_path)
            # Bound the verify tightly so this stays fast.
            original = runtime_owner._KILL_VERIFY_BOUND_SECONDS
            runtime_owner._KILL_VERIFY_BOUND_SECONDS = 2.0
            try:
                stopped = runtime_owner.stop_owned_harness_processes(
                    "scratch_flow", db_path=db_path,
                )
            finally:
                runtime_owner._KILL_VERIFY_BOUND_SECONDS = original

            assert session in stopped, (
                "the work_unit fresh-context stop MUST release the recorded "
                "anchor (the dummy harness child) when it terminates"
            )

            # The dummy child is verifiably terminated (ProcessLookupError).
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                pass
            except PermissionError:
                # EPERM in this race is acceptable too — the process is no
                # longer ours.
                pass
            else:
                raise AssertionError(
                    f"dummy harness child pid {child_pid} should be "
                    f"verifiably gone after the fresh-context stop"
                )

            # Ownership row is released.
            assert runtime_owner.list_for_flow(
                "scratch_flow", db_path=db_path,
            ) == []
        finally:
            # Kill any surviving child (test must not leave dummy processes).
            if child_pid is not None:
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    pass
                else:
                    try:
                        os.kill(child_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    except Exception:
                        pass
            _tmux_kill(session)
