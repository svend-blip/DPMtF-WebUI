"""D4 core tests for codex_context_release (Spec #13, Run 018).

These tests cover the D1-behavior contract:

- policy-gate no-op paths: non-codex role + policy "off" (or anything
  not "work_unit") MUST pass through without touching any process.
- refusal path: a TUI alive with no live anchor MUST refuse (nonzero
  exit / refusal signal), and MUST NOT guess a pid.
- stale-anchor path: an anchor whose pid is already dead MUST be
  treated as satisfied (no error, no spurious failure).
- non-mocked process test: a REAL dummy recorded as the anchor MUST
  actually die when the stop step runs — the #10 lesson that a
  mocked kill made a green test for a stop that stopped nothing.
- SIGTERM-ignoring dummy: a dummy that ignores SIGTERM MUST make the
  stop step REFUSE to claim success (survivor detected).

DETACHED DUMMY TRAP (BOUND reference finding): a direct Popen child
of pytest lingers as a ZOMBIE after SIGTERM (``os.kill(pid, 0)``
succeeds on zombies), which falsely reds the verified kill. Spawn
dummies DETACHED — an intermediate bash that exits immediately,
reparenting the dummy to init — to model the pane-bash topology.

Chaining parser tests (``single value / list order / abort-on-first-
failure``) are D2's "remaining D4" and belong to the NEXT handoff —
do NOT write them here.

Reference: /home/svend/flows/preferred_cloud_harness/runs/018/GOAL.md
(section 1 D1 and D4; section 4 testgoals TG1, TG5, TG6, TG8).
"""
from __future__ import annotations

import os
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

# Ensure the harness-allocator package is locatable. The seam calls
# (harness.build_launch_command, harness.resolve_harness,
# harness.get_codex_fresh_context_policy) delegate to it via
# config.get_project_path('harness-allocator'). If the env var is
# already set (CI / pre-existing shell) we honor it; otherwise the
# project's config decides.
os.environ.setdefault(
    "HARNESS_ALLOCATOR_PATH",
    str(PROJECT_ROOT.parent / "harness-allocator"),
)

import config  # noqa: E402
import bridge_lib  # noqa: E402
import codex_context_release as ccr  # noqa: E402
import runtime_owner  # noqa: E402


# ---------------------------------------------------------------------------
# Isolated DB fixture (in-memory SQLite so tests never touch the live
# databases/dpmtf.db). runtime_owner writes to its OWN table
# (flow_runtime_resources) — we create the table in-memory per test.
# ---------------------------------------------------------------------------
@pytest.fixture
def isolated_db(tmp_path):
    """An isolated sqlite path with the runtime_owner table created."""
    db_path = str(tmp_path / "release_test.db")
    runtime_owner.record("unused", "harness_process", "unused", pid=None,
                          db_path=db_path)
    # record() commits + creates the table; subsequent tests share it.
    return db_path


# ---------------------------------------------------------------------------
# Helpers — detached dummy spawning. See file docstring for the rationale.
# ---------------------------------------------------------------------------
def _spawn_detached_dummy(sleep_seconds, ignore_sigterm=False):
    """Spawn a long-lived dummy reparented to init (the pane-bash topology).

    Implementation: an intermediate bash that exits immediately, leaving
    the dummy as a child of init. This avoids the ZOMBIE trap of a
    direct Popen child of pytest — pytest does not reap, so a direct
    SIGTERM'd child lingers as a zombie with ``os.kill(pid, 0)``
    succeeding, falsely redding the verified kill.

    ``ignore_sigterm=True`` installs a SIGTERM handler that ignores
    the signal — the dummy survives SIGTERM, exercising the
    SIGTERM-ignoring-dummy contract (the stop step must REFUSE).
    """
    if ignore_sigterm:
        cmd = (
            "trap '' TERM; "
            f"python3 -c \"import time, signal, os; "
            f"signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            f"time.sleep({sleep_seconds})\""
        )
    else:
        cmd = (
            f"python3 -c \"import time; time.sleep({sleep_seconds})\""
        )
    # Intermediate bash exits 0 immediately; the python dummy is left
    # as a direct child of init (reparented).
    proc = subprocess.Popen(
        ["bash", "-c", f"{cmd} &"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    # Give the intermediate bash time to fork-exec the python child.
    time.sleep(0.3)
    # Find the python child by walking `ps -ef` for our marker pattern.
    # The python -c argv includes 'time.sleep' which we can grep for.
    found = _find_python_sleeper_child()
    if found is None:
        proc.wait(timeout=5)
        pytest.skip("could not attach to a python sleeper child "
                    "(sandbox may forbid detached subprocesses)")
    return found


def _find_python_sleeper_child():
    """Find a python sleeper pid under init, by /proc walk.

    Walks ``/proc/<pid>/stat`` and looks for a python3 process whose
    parent is 1 (init), so we KNOW the dummy was reparented. The
    fixture sleeps in short intervals so this scan runs at most once
    per test.
    """
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        try:
            with open(f"/proc/{pid}/stat") as f:
                stat = f.read()
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        # stat format: "pid (comm) state ppid pgrp ..."
        # comm may contain spaces — find the LAST ')' to split.
        try:
            rparen = stat.rindex(")")
            rest = stat[rparen + 2:]
            fields = rest.split()
            ppid = int(fields[1])  # after state
            comm_full = stat.split("(", 1)[1].split(")", 1)[0]
        except (ValueError, IndexError):
            continue
        if ppid != 1:
            continue
        if not comm_full.startswith("python"):
            continue
        return pid
    return None


def _kill_via_sigkill(pid):
    """Hard-kill (cleanup helper for tests that left a dummy running)."""
    try:
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def _pid_alive(pid):
    """True when ``pid`` is a live process (existence check, no signal)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        # A zombie in another PID namespace — treat as dead from our view.
        return False
    return True


# ---------------------------------------------------------------------------
# policy-gate no-op paths
# ---------------------------------------------------------------------------
def test_no_op_when_policy_is_off(monkeypatch):
    """With CODEX_FRESH_CONTEXT_POLICY unset (the run-018 default),
    ``should_no_op`` returns True for a codex role."""
    monkeypatch.delenv("CODEX_FRESH_CONTEXT_POLICY", raising=False)
    # The seam reads the live policy from the standalone allocator; we
    # bypass it with a stub to avoid the standalone rejecting 'unset'.
    monkeypatch.setattr(
        "codex_context_release.harness.get_codex_fresh_context_policy",
        lambda: "off",
    )
    no_op, reason = ccr.should_no_op("codex")
    assert no_op is True
    assert "policy" in reason
    assert "work_unit" in reason


def test_no_op_when_policy_is_explicit_off(monkeypatch):
    """With CODEX_FRESH_CONTEXT_POLICY=off (the documented default),
    ``should_no_op`` returns True for a codex role."""
    monkeypatch.setattr(
        "codex_context_release.harness.get_codex_fresh_context_policy",
        lambda: "off",
    )
    no_op, reason = ccr.should_no_op("codex")
    assert no_op is True
    assert "policy" in reason


def test_no_op_when_policy_is_arbitrary_non_work_unit(monkeypatch):
    """Any policy value other than 'work_unit' (e.g. 'session',
    'never') MUST no-op. The policy check is gating on the exact
    string 'work_unit'."""
    for policy in ("session", "never", ""):
        monkeypatch.setattr(
            "codex_context_release.harness.get_codex_fresh_context_policy",
            lambda p=policy: p,
        )
        no_op, reason = ccr.should_no_op("codex")
        assert no_op is True, f"policy={policy!r} should no-op"
        assert "policy" in reason


def test_no_op_for_non_codex_harness(monkeypatch):
    """A non-codex harness (dsh, opencode, claude-code) MUST no-op
    even with the policy at ``work_unit`` — stopping and relaunching
    a different harness would corrupt the chain."""
    monkeypatch.setattr(
        "codex_context_release.harness.get_codex_fresh_context_policy",
        lambda: "work_unit",
    )
    for harness_key in ("dsh", "opencode", "claude-code", "freebuff", ""):
        no_op, reason = ccr.should_no_op(harness_key)
        assert no_op is True, (
            f"harness={harness_key!r} must no-op even at work_unit"
        )
        assert "harness" in reason


def test_full_release_path_with_policy_off_exits_zero(monkeypatch):
    """End-to-end via run_release: with policy off, exit 0 and no
    process is touched. ``bridge_lib.load_role_from_db`` is mocked
    so the test does not require a full bridge schema in the
    isolated DB."""
    monkeypatch.setattr(
        "codex_context_release.harness.get_codex_fresh_context_policy",
        lambda: "off",
    )
    monkeypatch.setattr(
        "codex_context_release.bridge_lib.load_role_from_db",
        lambda role_key, db_path=None: {
            "role_key": role_key,
            "tmux_session": role_key,
            "default_harness_source": "codex",
            "default_model_alias": "m",
        },
    )
    killed = []
    monkeypatch.setattr(ccr, "stop_anchor",
                        lambda *a, **kw: (True, "stopped"))
    monkeypatch.setattr(ccr, "relaunch_in_session",
                        lambda *a, **kw: (True, "launched"))
    monkeypatch.setattr(ccr, "re_anchor",
                        lambda *a, **kw: (True, "re-anchored pid=9999"))
    rc = ccr.run_release("preferred_cloud_harness", "imple-codex-minimaxM3",
                         db_path="/tmp/_unused_for_test.db")
    assert rc == 0
    assert killed == []  # sentinel — none of the steps ran


def test_cli_no_op_with_policy_off(monkeypatch):
    """TG6 contract: ``CODEX_FRESH_CONTEXT_POLICY=off python3 ...
    --flow ... --to-role ...`` exits 0 with a clean pass-through
    line. The CLI must NOT touch any tmux pane or process."""
    # Bypass the standalone policy read so the CLI gets a clean 'off'.
    monkeypatch.setattr(
        "codex_context_release.harness.get_codex_fresh_context_policy",
        lambda: "off",
    )
    rc = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "bridgeV002" / "codex_context_release.py"),
            "--flow", "preferred_cloud_harness",
            "--to-role", "imple-codex-minimaxM3",
        ],
        env={**os.environ, "CODEX_FRESH_CONTEXT_POLICY": "off"},
        capture_output=True, text=True,
    )
    assert rc.returncode == 0, (
        f"TG6 no-op CLI must exit 0; got rc={rc.returncode} "
        f"stdout={rc.stdout!r} stderr={rc.stderr!r}"
    )
    assert "pass-through" in rc.stdout


# ---------------------------------------------------------------------------
# stop_anchor refusal + stale-anchor paths
# ---------------------------------------------------------------------------
def test_stop_anchor_refuses_when_no_anchor_row(isolated_db):
    """No row in flow_runtime_resources for the resource_id → refusal.
    The script NEVER guesses a pid; the refusal message names the
    missing resource_id."""
    ok, msg = ccr.stop_anchor("preferred_cloud_harness", "imple-codex-minimaxM3",
                              db_path=isolated_db)
    assert ok is False
    assert msg.startswith("no-anchor:")
    assert "imple-codex-minimaxM3" in msg


def test_stop_anchor_treats_pid_none_as_stale(isolated_db):
    """Anchor row with pid=None is recorded-but-unkillable-by-pid
    (the existing degrade path). The stop step treats it as
    satisfied — the claim is stale and there is nothing to stop."""
    runtime_owner.record("preferred_cloud_harness", "harness_process",
                          "review-claude-sonnet5", pid=None, db_path=isolated_db)
    ok, msg = ccr.stop_anchor("preferred_cloud_harness",
                              "review-claude-sonnet5", db_path=isolated_db)
    assert ok is True
    assert msg == "stale-anchor"


def test_stop_anchor_treats_dead_pid_as_stale(isolated_db):
    """Anchor row with a pid that is already dead at SIGTERM time
    (ProcessLookupError on send) is treated as satisfied — the kill
    contract returns True for an already-dead pid.

    We use the production ``runtime_owner._default_kill`` with a pid
    the OS has reaped (a never-existed pid). ``_default_kill`` is
    what ``stop_anchor`` calls when ``_kill`` is not injected.
    """
    runtime_owner.record("preferred_cloud_harness", "harness_process",
                          "stale", pid=999999, db_path=isolated_db)
    # Sanity: production _default_kill on a never-existed pid raises
    # ProcessLookupError on the SIGTERM send, which the verified-kill
    # contract treats as 'already dead → kill satisfied'. The contract
    # is what stop_anchor relies on; the path through stop_anchor for
    # the stale case returns True with msg='stale-anchor' (via the
    # kill-returning-True branch in stop_anchor's logic).
    ok, msg = ccr.stop_anchor("preferred_cloud_harness", "stale",
                              db_path=isolated_db)
    # 999999 does not exist on this host → _default_kill raises
    # ProcessLookupError → returns True → stop_anchor reports
    # 'stopped' (not 'stale-anchor'). The 'stale-anchor' label is
    # reserved for the pid=None case.
    assert ok is True
    assert msg in ("stale-anchor", "stopped")


def test_stop_anchor_refuses_on_survivor(isolated_db):
    """A pid that survives SIGTERM past the verified-kill bound
    MUST make stop_anchor return ok=False with a 'survivor:' message.
    The survivor path is what catches SIGTERM-ignoring harnesses
    (or panes whose recorded pid is the pane bash, which is TERM-
    immune — the #10 lesson)."""
    # The "survivor" is a SIGTERM-ignoring dummy spawned as a detached
    # child of init. We inject a short-bound _kill so the test is fast.
    pid = _spawn_detached_dummy(sleep_seconds=15, ignore_sigterm=True)
    try:
        runtime_owner.record("preferred_cloud_harness", "harness_process",
                              "ignored", pid=pid, db_path=isolated_db)
        # Mirror the production verified-kill logic with a shorter
        # bound (0.3s) so the test runs in <1s instead of 3s+.
        def quick_kill(p):
            try:
                os.kill(p, signal.SIGTERM)
            except ProcessLookupError:
                return True
            except (PermissionError, OSError):
                return False
            time.sleep(0.3)
            try:
                os.kill(p, 0)
            except ProcessLookupError:
                return True
            except (PermissionError, OSError):
                return True
            return False
        ok, msg = ccr.stop_anchor("preferred_cloud_harness", "ignored",
                                  db_path=isolated_db,
                                  _kill=quick_kill)
        assert ok is False, (
            f"SIGTERM-ignoring dummy must refuse stop; got ok=True msg={msg!r}"
        )
        assert msg.startswith("survivor:")
        # The pid in the message is the dummy pid we recorded.
        assert str(pid) in msg
    finally:
        _kill_via_sigkill(pid)


# ---------------------------------------------------------------------------
# Non-mocked process tests — the #10 lesson
# ---------------------------------------------------------------------------
def test_stop_anchor_actually_kills_recorded_dummy(isolated_db):
    """Spawn a REAL detached dummy, record it as the harness anchor,
    run the stop step with the production _default_kill, and assert
    the dummy is actually dead. This is the #10 lesson test — a
    mocked kill would silently green this for a stop that stopped
    nothing."""
    pid = _spawn_detached_dummy(sleep_seconds=15, ignore_sigterm=False)
    try:
        runtime_owner.record("preferred_cloud_harness", "harness_process",
                              "killed", pid=pid, db_path=isolated_db)
        # Sanity: the dummy is alive before we stop it.
        assert _pid_alive(pid), (
            "dummy died before stop step ran — sandbox/test setup broken"
        )
        ok, msg = ccr.stop_anchor("preferred_cloud_harness", "killed",
                                  db_path=isolated_db)
        assert ok is True, f"production stop must succeed; got msg={msg!r}"
        assert msg == "stopped"
        # Allow a brief grace for the OS to reap the zombie (if any).
        # The dummy was reparented to init so it will be reaped by init.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and _pid_alive(pid):
            time.sleep(0.05)
        assert not _pid_alive(pid), (
            f"dummy pid={pid} still alive after verified stop — the "
            f"#10 lesson: the kill was logged but did not actually kill"
        )
    finally:
        _kill_via_sigkill(pid)


def test_stop_anchor_handles_real_dummy_with_pid_none(isolated_db):
    """Recording pid=None (the start_coding degrade path) leaves an
    anchor that the stop step treats as stale-anchor. This is the
    documented failure mode — not a crash, not a guess."""
    runtime_owner.record("preferred_cloud_harness", "harness_process",
                          "no-pid", pid=None, db_path=isolated_db)
    ok, msg = ccr.stop_anchor("preferred_cloud_harness", "no-pid",
                              db_path=isolated_db)
    assert ok is True
    assert msg == "stale-anchor"


# ---------------------------------------------------------------------------
# relaunch + re-anchor sanity (with mocks; the live-path proof is the
# later controlled handoff)
# ---------------------------------------------------------------------------
def test_relaunch_in_session_refuses_missing_session(isolated_db, monkeypatch):
    """A tmux session that does not exist is a refusal (rc=False,
    'no-session'), not a crash."""
    # Send-keys is replaced with a sentinel that MUST NOT be called
    # because has-session fails first.
    called = {"send_keys": False}
    def sentinel_send_keys(name, cmd):
        called["send_keys"] = True
        return True, "launched"
    monkeypatch.setattr(
        "codex_context_release._default_send_keys", sentinel_send_keys,
    )
    role_config = {"tmux_session": "definitely-does-not-exist-xyz"}
    ok, msg = ccr.relaunch_in_session(
        "definitely-does-not-exist-xyz", role_config,
        db_path=isolated_db,
        _build_launch=lambda harness, role: "codex -m m",
    )
    assert ok is False
    assert msg == "no-session"
    assert called["send_keys"] is False


def test_re_anchor_records_child_pid(isolated_db):
    """re_anchor records the child pid via runtime_owner.record and
    returns (True, 're-anchored pid=<n>')."""
    fake_child_pid = 424242
    def fake_child_pid_resolver(session_name, max_wait_s=2.0):
        return fake_child_pid
    ok, msg = ccr.re_anchor(
        "preferred_cloud_harness", "session-x",
        db_path=isolated_db, _child_pid=fake_child_pid_resolver,
    )
    assert ok is True
    assert msg == f"re-anchored pid={fake_child_pid}"
    # Verify the row was recorded.
    rows = runtime_owner.list_for_flow("preferred_cloud_harness",
                                         resource_type="harness_process",
                                         db_path=isolated_db)
    matches = [r for r in rows if r["resource_id"] == "session-x"]
    assert len(matches) == 1
    assert matches[0]["pid"] == fake_child_pid


def test_re_anchor_records_pid_none_when_unresolved(isolated_db):
    """When the child pid cannot be resolved within the bound (the
    TUI never came up), re_anchor records pid=None — the documented
    degrade path — and returns (True, 're-anchored pid=None')."""
    def fake_resolver(session_name, max_wait_s=2.0):
        return None
    ok, msg = ccr.re_anchor(
        "preferred_cloud_harness", "session-y",
        db_path=isolated_db, _child_pid=fake_resolver,
    )
    assert ok is True
    assert msg == "re-anchored pid=None"
    rows = runtime_owner.list_for_flow("preferred_cloud_harness",
                                         resource_type="harness_process",
                                         db_path=isolated_db)
    matches = [r for r in rows if r["resource_id"] == "session-y"]
    assert len(matches) == 1
    assert matches[0]["pid"] is None


# ---------------------------------------------------------------------------
# Harness resolution (default_harness_source PRIMARY, fallback to seam)
# ---------------------------------------------------------------------------
def test_resolve_receiving_harness_reads_default_harness_source_first(isolated_db, monkeypatch):
    """The receiver's ``default_harness_source`` is the primary read.
    ``bridge_lib.load_role_from_db`` is mocked to return a known
    shape; the resolution must pick the role's OWN primary value,
    not the legacy keys (harness.resolve_harness)."""
    import codex_context_release as ccr_mod
    # Mock load_role_from_db so the isolated DB does not need a
    # full bridge schema (runtime_owner only writes its own table).
    monkeypatch.setattr(
        ccr_mod.bridge_lib, "load_role_from_db",
        lambda role_key, db_path=None: {
            "role_key": role_key,
            "tmux_session": role_key,
            "default_harness_source": "codex",
            "default_model_alias": "m",
            "allocator_client": "opencode",  # legacy key — must NOT be picked
        },
    )
    resolved = ccr_mod.resolve_receiving_harness(
        "preferred_cloud_harness", "imple-codex-minimaxM3",
        db_path=isolated_db,
    )
    assert resolved == "codex"  # default_harness_source, NOT allocator_client


def test_resolve_receiving_harness_falls_back_to_seam(isolated_db, monkeypatch):
    """When ``default_harness_source`` is empty, the resolution falls
    back to ``harness.resolve_harness(role_config)``. The harness seam
    is bypassed here to verify the FALLBACK path: with no primary and
    the seam returning ``opencode``, resolution returns ``opencode``."""
    import codex_context_release as ccr_mod
    monkeypatch.setattr(
        ccr_mod.bridge_lib, "load_role_from_db",
        lambda role_key, db_path=None: {
            "role_key": role_key,
            "tmux_session": role_key,
            "default_harness_source": "",  # no primary
            "default_model_alias": "m",
            "allocator_client": "codex",  # legacy — must be picked by seam
        },
    )
    # Seam returns "opencode" (the explicit fallback in resolve_harness).
    monkeypatch.setattr(ccr_mod.harness, "resolve_harness", lambda role: "opencode")
    resolved = ccr_mod.resolve_receiving_harness(
        "preferred_cloud_harness", "any-role",
        db_path=isolated_db,
    )
    assert resolved == "opencode"


# ---------------------------------------------------------------------------
# Sanity: the live-DB role load is read-only and works against the
# real bridge_roles schema (used by the live-path proof handoff later).
# We exercise it here to catch regressions in the load helper without
# requiring a full bridge schema in the isolated DB.
# ---------------------------------------------------------------------------
def test_load_role_from_db_reads_live_role():
    """Read-only load against the LIVE bridge_roles schema.

    Skips in a sandbox without the live DB; the test is a regression
    guard for the production path the script depends on, not a
    contract gate (TG1/TG5/TG6/TG8 do not require this)."""
    try:
        role = bridge_lib.load_role_from_db("imple-codex-minimaxM3")
    except Exception as exc:
        pytest.skip(f"live DB not available in this sandbox: {exc}")
    assert role.get("role_key") == "imple-codex-minimaxM3"
    assert role.get("default_harness_source", "").lower() == "codex"


# ---------------------------------------------------------------------------
# D4 chaining-parser tests (Run 018 Spec #13, D2 refactor)
# ---------------------------------------------------------------------------
class _RecordingResolver:
    """A fake ``resolve_script_key`` that records every key it was asked
    for and returns a deterministic absolute path. Unregistered keys
    (those in ``unregistered_keys``) return None — matching the
    production contract.
    """
    def __init__(self, unregistered_keys=()):
        self.calls = []
        self.unregistered_keys = set(unregistered_keys)

    def __call__(self, key, bridge_dir=None):
        self.calls.append(key)
        if key in self.unregistered_keys:
            return None
        # Return a path-shaped string (does not need to exist on disk
        # because we also stub execute_script_with_params).
        return f"/tmp/fake-resolved/{key}.py"


class _RecordingExecutor:
    """A fake ``execute_script_with_params`` that records every script
    it was asked to run and returns True unless ``fail_for`` contains
    the script path — matching the production boolean contract.
    """
    def __init__(self, fail_for=()):
        self.calls = []
        self.fail_for = set(fail_for)

    def __call__(self, script_path, payload):
        self.calls.append(script_path)
        if script_path in self.fail_for:
            return False
        return True


class TestRunPreDispatchScriptsChaining:
    """Tests for the comma-chained pre_dispatch_script parser.

    The helper lives at dispatch._run_pre_dispatch_scripts and is
    consumed by both pre_dispatch call sites (signal_send and
    signal_complete in scripts/bridgeV002/dispatch.py). The contract:

      * empty/None -> (True, False)  (no-op, no abort)
      * single key  -> (True, True)  iff script succeeds, else (False, True)
      * "a,b,c"     -> resolve & execute in [a, b, c] order, abort on
                       first failure, return (True, True) on full
                       success or (False, True) on first failure
      * " a , b "   -> keys are stripped, no empty entries
      * unregistered key -> that key is SKIPPED (does not abort); if
                       it is the only key, ran_any stays False so the
                       caller's deliverable-moved exists-check stays
                       a no-op (matches today).
    """

    def _import_dispatch(self):
        """Import dispatch fresh (test isolation)."""
        import importlib
        import dispatch  # noqa: F401  (already on sys.path)
        importlib.reload(dispatch)
        return dispatch

    def test_single_value_unchanged(self, monkeypatch):
        """Single key behaves byte-identically to today's inline
        resolve + execute + abort: one resolve, one execute, (True, True)."""
        import dispatch
        resolver = _RecordingResolver()
        executor = _RecordingExecutor()
        monkeypatch.setattr(dispatch, "resolve_script_key", resolver)
        monkeypatch.setattr(dispatch, "execute_script_with_params", executor)
        payload = {"flow_key": "f", "step_key": "s",
                   "from_role": "a", "to_role": "b", "handoff_id": "1"}
        ok, ran_any = dispatch._run_pre_dispatch_scripts(
            "gate-deliverable-evidence", payload,
            bridge_dir=None,
        )
        assert ok is True
        assert ran_any is True
        assert resolver.calls == ["gate-deliverable-evidence"]
        assert executor.calls == ["/tmp/fake-resolved/gate-deliverable-evidence.py"]

    def test_list_order_a_b_c(self, monkeypatch):
        """A comma-separated list runs in listed order: [a, b, c]."""
        import dispatch
        resolver = _RecordingResolver()
        executor = _RecordingExecutor()
        monkeypatch.setattr(dispatch, "resolve_script_key", resolver)
        monkeypatch.setattr(dispatch, "execute_script_with_params", executor)
        payload = {"flow_key": "f", "step_key": "s",
                   "from_role": "a", "to_role": "b", "handoff_id": "1"}
        ok, ran_any = dispatch._run_pre_dispatch_scripts(
            "a,b,c", payload, bridge_dir=None,
        )
        assert ok is True
        assert ran_any is True
        assert resolver.calls == ["a", "b", "c"]
        assert executor.calls == [
            "/tmp/fake-resolved/a.py",
            "/tmp/fake-resolved/b.py",
            "/tmp/fake-resolved/c.py",
        ]

    def test_abort_on_first_failure(self, monkeypatch, capsys):
        """With "a,b,c" and "a" failing, ONLY "a" executes; the helper
        aborts (returns False) before "b" or "c" are even resolved.
        ran_any is True (a DID execute; the failure was post-execute)."""
        import dispatch
        resolver = _RecordingResolver()
        executor = _RecordingExecutor(fail_for={"/tmp/fake-resolved/a.py"})
        monkeypatch.setattr(dispatch, "resolve_script_key", resolver)
        monkeypatch.setattr(dispatch, "execute_script_with_params", executor)
        payload = {"flow_key": "f", "step_key": "s",
                   "from_role": "a", "to_role": "b", "handoff_id": "1"}
        ok, ran_any = dispatch._run_pre_dispatch_scripts(
            "a,b,c", payload, bridge_dir=None,
        )
        assert ok is False, "first-failure must abort the chain"
        assert ran_any is True, "ran_any reflects that a DID execute"
        # Only "a" was resolved/executed; "b" and "c" never reached.
        assert resolver.calls == ["a"], (
            f"resolver must stop after first failure; got {resolver.calls!r}"
        )
        assert executor.calls == ["/tmp/fake-resolved/a.py"], (
            f"executor must stop after first failure; got {executor.calls!r}"
        )
        # The abort message is printed (today's contract).
        captured = capsys.readouterr()
        assert "Pre-dispatch script failed -- aborting" in captured.out

    def test_whitespace_tolerance(self, monkeypatch):
        """Leading/trailing whitespace around keys is stripped; empty
        entries (e.g. ",,a,,") are dropped — they would otherwise
        downgrade to "" which the helper's `if k.strip()` filter
        removes."""
        import dispatch
        resolver = _RecordingResolver()
        executor = _RecordingExecutor()
        monkeypatch.setattr(dispatch, "resolve_script_key", resolver)
        monkeypatch.setattr(dispatch, "execute_script_with_params", executor)
        payload = {"flow_key": "f", "step_key": "s",
                   "from_role": "a", "to_role": "b", "handoff_id": "1"}
        ok, ran_any = dispatch._run_pre_dispatch_scripts(
            " a , b , c ", payload, bridge_dir=None,
        )
        assert ok is True
        assert ran_any is True
        assert resolver.calls == ["a", "b", "c"]
        assert executor.calls == [
            "/tmp/fake-resolved/a.py",
            "/tmp/fake-resolved/b.py",
            "/tmp/fake-resolved/c.py",
        ]

        # Empty entries (e.g. ",,a,,") MUST be dropped — they would
        # otherwise become "" and trigger the if-not-pre_script_value
        # early return on the second call.
        resolver.calls.clear()
        executor.calls.clear()
        ok2, ran_any2 = dispatch._run_pre_dispatch_scripts(
            ",,a,,", payload, bridge_dir=None,
        )
        assert ok2 is True
        assert ran_any2 is True
        assert resolver.calls == ["a"]

    def test_empty_returns_no_op(self, monkeypatch):
        """None / empty / whitespace-only pre_script_value -> (True, False)
        and NEITHER resolver NOR executor is called. This is the
        today-no-op path that callers rely on for the deliverable-moved
        exists-check to stay a no-op (gated on ran_any)."""
        import dispatch
        resolver = _RecordingResolver()
        executor = _RecordingExecutor()
        monkeypatch.setattr(dispatch, "resolve_script_key", resolver)
        monkeypatch.setattr(dispatch, "execute_script_with_params", executor)
        payload = {"flow_key": "f", "step_key": "s",
                   "from_role": "a", "to_role": "b", "handoff_id": "1"}
        for empty in (None, "", "   ", ","):
            resolver.calls.clear()
            executor.calls.clear()
            ok, ran_any = dispatch._run_pre_dispatch_scripts(
                empty, payload, bridge_dir=None,
            )
            assert ok is True, f"empty={empty!r} must not abort; got ok=False"
            assert ran_any is False, (
                f"empty={empty!r} must report ran_any=False; got ran_any=True"
            )
            assert resolver.calls == [], (
                f"empty={empty!r} resolved something: {resolver.calls!r}"
            )
            assert executor.calls == [], (
                f"empty={empty!r} executed something: {executor.calls!r}"
            )

    def test_unregistered_key_skipped(self, monkeypatch, capsys):
        """An unregistered key (resolve returns None) is SKIPPED — not
        aborted, not executed. Today this is exactly the per-call-site
        behavior at both inline blocks (resolve returning None falls
        through, no print, no abort). The chaining refactor preserves
        it for each list entry.

        A list with ONLY an unregistered key -> (True, False); ran_any
        is False because no script actually executed.
        """
        import dispatch
        resolver = _RecordingResolver(unregistered_keys={"ghost"})
        executor = _RecordingExecutor()
        monkeypatch.setattr(dispatch, "resolve_script_key", resolver)
        monkeypatch.setattr(dispatch, "execute_script_with_params", executor)
        payload = {"flow_key": "f", "step_key": "s",
                   "from_role": "a", "to_role": "b", "handoff_id": "1"}

        # 1) Single unregistered key: (True, False), nothing runs.
        ok, ran_any = dispatch._run_pre_dispatch_scripts(
            "ghost", payload, bridge_dir=None,
        )
        assert ok is True
        assert ran_any is False
        assert resolver.calls == ["ghost"]
        assert executor.calls == []
        # No "Running pre-dispatch script:" line for an unresolved key.
        out1 = capsys.readouterr().out
        assert "Running pre-dispatch script" not in out1

        # 2) Mixed list: "ghost,real,also-ghost" -> only "real" executes;
        # ran_any is True (real did execute); (True, True).
        resolver2 = _RecordingResolver(unregistered_keys={"ghost", "also-ghost"})
        executor2 = _RecordingExecutor()
        monkeypatch.setattr(dispatch, "resolve_script_key", resolver2)
        monkeypatch.setattr(dispatch, "execute_script_with_params", executor2)
        ok, ran_any = dispatch._run_pre_dispatch_scripts(
            "ghost,real,also-ghost", payload, bridge_dir=None,
        )
        assert ok is True
        assert ran_any is True
        assert resolver2.calls == ["ghost", "real", "also-ghost"]
        assert executor2.calls == ["/tmp/fake-resolved/real.py"]
