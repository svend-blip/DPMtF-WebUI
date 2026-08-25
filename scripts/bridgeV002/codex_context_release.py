#!/usr/bin/env python3
"""Codex-context-release pre-dispatch script (Spec #13).

Run 018 D1 deliverable. Invoked as a pre-dispatch script on a step whose
receiver is a codex role when the allocator's `CODEX_FRESH_CONTEXT_POLICY`
env is set to ``work_unit`` (run 018 leaves the policy at its default
``off``; the live path is exercised only in the controlled live-path proof
handoff, with a scratch tmux session and a detached dummy process — never
against the live chain's resident codex).

The script's job is to free context for the receiving codex role by
VERIFIED STOP + RELAUNCH + RE-ANCHOR of the flow-owned harness process:

1. Resolve the receiving role's harness. PRIMARY read is the role's own
   ``default_harness_source`` column (the start_coding primary-read rule,
   bridge_roles role-level pointer); FALLBACK is ``harness.resolve_harness``
   (the legacy-keys reader). Reading resolve_harness alone would misresolve
   a backfilled-only role into ``"opencode"`` and silently no-op the
   release.
2. No-op gate. If the harness is not ``codex``, OR if
   ``harness.get_codex_fresh_context_policy()`` is not ``"work_unit"``,
   print a clear pass-through line and exit 0. The chain must be
   unaffected with the policy at its default ``off``.
3. Verified stop. Find the role's harness_process anchor in
   flow_runtime_resources (resource_id = the role's tmux_session).
   Stop it through runtime_owner's verified-kill path (SIGTERM +
   bounded wait + death confirmed). NEVER kill anything not recorded
   as DPMtF-owned.
     - Stale anchor (recorded pid already dead at send time): treat as
       satisfied (the SIGTERM / ProcessLookupError satisfied the claim).
     - TUI visibly alive (pane runs a codex TUI) BUT no live anchor:
       REFUSE — print a clear message and exit nonzero. Guessing a pid
       is forbidden.
     - BOUND reference finding: do NOT call ``runtime_owner.release()``
       for the anchor. release() deletes by (flow_key, resource_id)
       ACROSS resource types, and the tmux_session ownership row SHARES
       its resource_id with the harness_process anchor — releasing the
       anchor silently drops the session-stop claim. Stop via the
       verified-kill path and leave the row in place; the relaunch
       OVERWRITES the anchor in place via ``record()`` (INSERT OR
       REPLACE, same PK). On relaunch failure the old row remains as
       a tolerated stale anchor.
4. Relaunch + re-anchor. Relaunch codex in the role's tmux session via
   ``harness.build_launch_command("codex", role)`` (sent through
   ``tmux send-keys -l + Enter``, the start_coding idiom). Wait bounded
   for the TUI to be ready (a codex process child is visible one level
   below the pane bash). Re-record the harness_process anchor with the
   REAL child pid (the #10 rule — never the pane bash) via
   ``runtime_owner.record()``. On relaunch failure the old anchor
   remains as a tolerated stale anchor and the script exits nonzero —
   dispatch must abort rather than inject into a dead or half-started
   pane.
5. Exit 0 only on a clean no-op OR a clean verified stop + relaunch +
   re-anchor. Anything else exits nonzero.

Importable as a module: ``if __name__ == "__main__":`` guards the CLI.
The D4 tests import ``stop_anchor``, ``relaunch_in_session``,
``re_anchor``, ``resolve_receiving_harness`` and ``should_no_op``
directly so they can exercise the stop/refusal/stale-anchor paths
without spawning the script as a subprocess.

CLI contract (BOUND reference finding): accepts BOTH ``--flow`` and
``--flow-key`` (aliases), plus ``--to-role`` (the receiving role). The
other flags dispatch.py's ``step_to_cli_args`` passes are tolerated and
ignored (``--step-key``, ``--from-role``, ``--handoff-id``,
``--bridge-dir``, ``--deliverable-dir``, ``--deliverable-pattern``,
``--deliverable-file``, ``--prompt-template``).
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

# Mirror scripts/bridgeV002/runtime_owner.py lines 31-35: insert the project
# root onto sys.path so `import config` and `import harness` resolve. The
# seams this script reuses live in scripts/bridgeV002/ and at the project
# root (config.py).
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import config  # noqa: E402
import bridge_lib  # noqa: E402
import harness  # noqa: E402
import runtime_owner  # noqa: E402

#: Bounded wait after send-keys for the codex child to appear one level
#: below the pane bash (the verified-anchor pid). Matches start_coding's
#: own wait budget — the bound is the failure mode for "TUI never came
#: up", not a tuning knob.
_RELAUNCH_CHILD_WAIT_S = 4.0
_RELAUNCH_CHILD_POLL_S = 0.1


# ---------------------------------------------------------------------------
# D2 (Run 032 GOAL.md sec 1 D2): survive-or-refuse probe.
#
# On 2026-08-24 codex_context_release.py's re_anchor resolved a child
# pid (2469038) and recorded it IMMEDIATELY, returning (True,
# "re-anchored pid=2469038"). The codex had already hit an interactive
# update prompt and died; the anchor pointed at a corpse and dispatch
# reported success. D2 confirms the resolved child is still alive
# BEFORE the record() call, and returns (False, ...) when it is not.
#
# _default_pid_alive mirrors dispatch._default_pid_alive
# (os.kill(pid, 0); ProcessLookupError -> False; PermissionError /
# other OSError -> True; else True) so the two liveness predicates
# share one idiom. _pid_alive is the seam the D2 tests monkeypatch.
# ---------------------------------------------------------------------------
def _default_pid_alive(pid):
    """True iff ``pid`` is verifiably a live process right now.

    ProcessLookupError means the pid is gone (False). PermissionError
    or any other OSError means something else owns the pid but it
    exists (True -- same shape as runtime_owner._default_kill).
    """
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True


# ---------------------------------------------------------------------------
# Pure helpers (no I/O beyond the seam calls) — imported by tests.
# ---------------------------------------------------------------------------
def resolve_receiving_harness(flow_key, to_role, db_path=None):
    """Return the harness key for ``to_role`` (the receiving role).

    PRIMARY read: ``bridge_roles.default_harness_source`` (the
    start_coding primary-read rule, role-level pointer). FALLBACK:
    ``harness.resolve_harness(role_config)`` (legacy keys reader that
    would misresolve a backfilled-only role into ``opencode`` if used
    alone). Stripped and lower-cased to compare against the seam
    contract.

    Returns the harness key string, never None — ``harness.resolve_harness``
    applies the explicit fallback to ``"opencode"`` when the role carries
    no harness key, so this function inherits that behavior on the
    fallback path.
    """
    if db_path is None:
        db_path = config.get_db_path()
    role_config = bridge_lib.load_role_from_db(to_role, db_path=db_path)
    primary = (role_config.get("default_harness_source") or "").strip().lower()
    if primary:
        return primary
    # Fallback to the seam; resolve_harness falls through to "opencode"
    # when no harness key is set anywhere on the role.
    return (harness.resolve_harness(role_config) or "").strip().lower() or "opencode"


def should_no_op(harness_key):
    """True when the script should pass through without touching any process.

    The chain MUST be unaffected with the policy at its default ``off``.
    Two ways to no-op:
      * The receiving role's harness is not ``codex`` (e.g. ``dsh``,
        ``opencode``, ``claude-code``). Stopping and relaunching a
        different harness would corrupt the chain.
      * The fresh-context policy is not ``work_unit`` (the default
        ``off``, or any future policy name). Only ``work_unit``
        authorizes a context release at the work-unit boundary.

    Returns (no_op, reason) so the caller can log a useful pass-through
    line; the reason string is informational, not contract.
    """
    if harness_key != "codex":
        return True, f"harness={harness_key!r} (only 'codex' triggers release)"
    policy = (harness.get_codex_fresh_context_policy() or "").strip().lower()
    if policy != "work_unit":
        return True, f"fresh-context policy={policy!r} (only 'work_unit' triggers release)"
    return False, ""


def stop_anchor(flow_key, resource_id, db_path=None, _kill=None):
    """Stop the recorded harness_process anchor via the verified-kill path.

    Bounds: the anchor must exist (resource_id is recorded for this
    flow); a stale anchor (pid already dead at send time) is treated
    as satisfied. A MISSING anchor is a refusal, not a fallback — the
    script NEVER guesses a pid.

    Returns ``(ok, message)``:
      * (True, "stale-anchor")              — anchor recorded, pid gone
      * (True, "stopped")                   — SIGTERM sent, death confirmed
      * (False, "no-anchor: <resource_id>") — no anchor row at all
      * (False, "survivor: <pid>")          — SIGTERM sent, process survived

    The anchor row is LEFT IN PLACE. Releasing it would silently drop
    the tmux_session ownership claim (release deletes by resource_id
    across resource types; tmux_session and harness_process share the
    resource_id for the role). The relaunch step OVERWRITES the row
    in place via runtime_owner.record() (INSERT OR REPLACE, same PK).
    On relaunch failure the old row remains as a tolerated stale
    anchor.

    ``_kill`` is injectable for tests (default: runtime_owner._default_kill).
    """
    if db_path is None:
        db_path = config.get_db_path()
    kill = _kill or runtime_owner._default_kill
    rows = [
        r for r in runtime_owner.list_for_flow(
            flow_key, resource_type="harness_process", db_path=db_path,
        )
        if r.get("resource_id") == resource_id
    ]
    if not rows:
        return False, f"no-anchor: {resource_id}"
    row = rows[0]
    pid = row.get("pid")
    if not pid:
        # Recorded-but-unkillable-by-pid: the existing degrade path.
        # Treat as satisfied (no pid, nothing to stop). The anchor stays.
        return True, "stale-anchor"
    if kill(pid):
        return True, "stopped"
    return False, f"survivor: {pid}"


def relaunch_in_session(session_name, role_config, db_path=None,
                        _send_keys=None, _build_launch=None):
    """Send ``codex ...`` to ``session_name`` via ``tmux send-keys -l + Enter``.

    The launch command is built by the harness seam
    (``harness.build_launch_command("codex", role_config)``). Sending
    uses the same idiom as start_coding.run_cmd_in_session: literal
    text first (send-keys -l) so a long command with quotes is not
    mangled into key names, then a separate Enter keystroke.

    Returns (ok, message):
      * (True, "launched") — both send-keys calls returned 0.
      * (False, "no-session") — the tmux session does not exist.
      * (False, "send-keys returned <rc>") — tmux rejected the input.

    ``_send_keys`` and ``_build_launch`` are injectable for tests
    (default: subprocess tmux send-keys, harness.build_launch_command).
    """
    if db_path is None:
        db_path = config.get_db_path()
    build_launch = _build_launch or harness.build_launch_command
    send_keys = _send_keys or _default_send_keys
    # Verify the session exists before sending — sending to a missing
    # session would print an error to tmux's stderr and a subsequent
    # ready-wait would loop forever.
    has_session = subprocess.run(
        ["tmux", "has-session", "-t", "=" + session_name],
        capture_output=True, text=True,
    )
    if has_session.returncode != 0:
        return False, "no-session"
    # Run 024 / D2 path B: export CODEX_PROFILE from the resolved
    # harness_profile BEFORE build_launch reads it. The harness seam
    # exports the env itself for the in-process path (start_coding's
    # native-launch codex branch already calls _apply_codex_profile_env
    # inside _codex_command), but relaunch goes through ``_build_launch``
    # which is injectable — the injection point bypasses the seam's
    # in-process env handling. Doing it here keeps the contract
    # uniform: env is set before the launch command is materialised,
    # regardless of which entry point materialises it.
    # Mirror harness._profile_from_role so both paths resolve the
    # role's profile identically. Empty / absent profile UNSETS the
    # env (no stale profile leaks into the new codex).
    profile_raw = ""
    if isinstance(role_config, dict):
        profile_raw = role_config.get("harness_profile")
        if profile_raw is None or profile_raw == "":
            profile_raw = role_config.get("default_harness_profile")
    profile = (profile_raw or "").strip()
    if profile:
        os.environ["CODEX_PROFILE"] = profile
    else:
        os.environ.pop("CODEX_PROFILE", None)
    cmd_str = build_launch("codex", role_config)
    return send_keys(session_name, cmd_str)


def re_anchor(flow_key, session_name, db_path=None,
              _child_pid=None, _pid_alive=None):
    """Re-record the harness_process anchor with the REAL child pid.

    Walks one level down from the pane bash (start_coding's
    ``_harness_child_pid`` idiom -- the #10 rule, never the pane bash).
    Bounded wait for the child to appear after send-keys. On
    resolution failure the anchor is recorded with pid=None (the
    existing degrade path) -- the relaunch is treated as a tolerated
    stale anchor and the function returns True (the relaunch
    succeeded; the recording failure is degraded, not fatal -- the
    latter launch attempt and the eventual stop will surface it).

    Returns (ok, message):
      * (True, "re-anchored pid=<n>")   -- child pid resolved, alive, recorded
      * (True, "re-anchored pid=None")  -- child pid never resolved, recorded None
      * (False, "child pid <n> did not survive")  -- D2: resolved but DEAD
      * (False, "recording failed: <e>")          -- record() raised

    D2 (Run 032 GOAL.md sec 1 D2): when a child pid WAS resolved, it
    is re-checked for liveness BEFORE the record() call. A dead
    resolved child is a refuse-to-record failure (the 2026-08-24
    bug class -- a codex hit an interactive update prompt and died
    between the ready-window walk and the record call; recording its
    corpse and returning success was the lie). A never-resolved
    child (None) is left to the existing degrade path (pid=None
    recorded, (True, "re-anchored pid=None")).

    ``_child_pid`` and ``_pid_alive`` are injectable for tests
    (defaults: a private bounded-poll ps --ppid walker and the
    shared os.kill(pid, 0) idiom).
    """
    if db_path is None:
        db_path = config.get_db_path()
    child_pid_resolver = _child_pid or _harness_child_pid
    child_pid = child_pid_resolver(session_name)
    # D2 (Run 032): refuse to record a corpse. When a child pid was
    # resolved, re-check liveness BEFORE the record() call. The
    # never-resolved case (child_pid is None) is left to the
    # existing degrade path below -- D2 only changes behaviour for
    # a child that WAS resolved and is now dead.
    if child_pid is not None:
        alive = (_pid_alive or _default_pid_alive)(child_pid)
        if not alive:
            # Loud refusal -- DO NOT record. run_release turns this
            # (False, ...) into "RE-ANCHOR FAILED ... aborting dispatch"
            # and exits 5.
            return False, f"child pid {child_pid} did not survive"
    try:
        runtime_owner.record(
            flow_key, "harness_process", session_name, pid=child_pid,
            db_path=db_path,
        )
    except Exception as exc:
        return False, f"recording failed: {exc}"
    if child_pid is None:
        return True, "re-anchored pid=None"
    return True, f"re-anchored pid={child_pid}"


# ---------------------------------------------------------------------------
# Internal helpers — TMUX + child-pid seams (NOT mocked by tests; tests
# inject their own when they want to skip the real subprocess).
# ---------------------------------------------------------------------------
def _default_send_keys(session_name, cmd_str):
    """send-keys -l + Enter into the role's tmux pane (start_coding idiom).

    Two subprocess calls: literal text first, then Enter as a key name.
    Returns (ok, message). Mirrors the start_coding.run_cmd_in_session
    ordering — without -l, send-keys parses the string as key names
    and a long allocator command with quotes lands mangled.
    """
    target = "=" + session_name + ":0"
    first = subprocess.run(
        ["tmux", "send-keys", "-t", target, "-l", cmd_str],
        capture_output=True, text=True,
    )
    if first.returncode != 0:
        return False, f"send-keys returned {first.returncode}"
    second = subprocess.run(
        ["tmux", "send-keys", "-t", target, "Enter"],
        capture_output=True, text=True,
    )
    if second.returncode != 0:
        return False, f"send-keys Enter returned {second.returncode}"
    return True, "launched"


def _harness_child_pid(session_name, max_wait_s=_RELAUNCH_CHILD_WAIT_S):
    """The harness CHILD pid in the pane (one level below the bash).

    Portable ``ps --ppid <pane_pid> -o pid=`` walker — same algorithm
    as start_coding._harness_child_pid but private here so the
    release script can be tested in isolation without importing
    start_coding's larger module (which also pulls in model_allocator
    config). Bounded poll.

    Returns the smallest direct child pid (the harness forked first),
    or None when the pane bash is gone or no direct child appears
    within the bound. NEVER returns the pane bash pid (the #10 rule).
    """
    pane = _pane_bash_pid(session_name)
    if pane is None:
        return None
    deadline = time.monotonic() + max_wait_s
    while True:
        try:
            result = subprocess.run(
                ["ps", "-o", "pid=", "--no-headers", "--ppid", str(pane)],
                capture_output=True, text=True, timeout=2,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None
        pids = []
        for line in (result.stdout or "").splitlines():
            tok = line.strip()
            if tok.isdigit():
                pids.append(int(tok))
        if pids:
            return min(pids)
        if time.monotonic() >= deadline:
            return None
        time.sleep(_RELAUNCH_CHILD_POLL_S)


def _pane_bash_pid(session_name):
    """The pane bash pid of a tmux session, or None.

    Same algorithm as start_coding._pane_pid — a private copy so the
    release script does not depend on start_coding's import surface.
    NEVER recorded as the anchor — see _harness_child_pid above.
    """
    result = subprocess.run(
        ["tmux", "display-message", "-p", "-t", "=" + session_name + ":0",
         "#{pane_pid}"],
        capture_output=True, text=True,
    )
    pid_text = (result.stdout or "").strip()
    return int(pid_text) if pid_text.isdigit() else None


# ---------------------------------------------------------------------------
# Top-level orchestration — the one place the seams above are wired
# together. Each branch exits with a clear, log-friendly line so the
# live-path landing handoff can grep dispatch's stdout for the no-op
# pass-through evidence.
# ---------------------------------------------------------------------------
def _load_role_or_exit(to_role, db_path):
    try:
        return bridge_lib.load_role_from_db(to_role, db_path=db_path)
    except Exception as exc:
        print(f"  ERROR: load_role_from_db({to_role!r}) failed: {exc}",
              file=sys.stderr)
        sys.exit(2)


def run_release(flow_key, to_role, db_path=None,
                _kill=None, _send_keys=None, _build_launch=None,
                _child_pid=None):
    """Orchestrate the verified-stop + relaunch + re-anchor path.

    Same arguments as the CLI's run, plus injectable seams for the D4
    tests. Returns the process exit code (0 = clean no-op OR clean
    stop + relaunch + re-anchor; nonzero = any failure).

    Importable so tests can drive the path without spawning a
    subprocess. Used by ``main`` and by tests.
    """
    if db_path is None:
        db_path = config.get_db_path()
    role_config = _load_role_or_exit(to_role, db_path)
    harness_key = resolve_receiving_harness(flow_key, to_role, db_path=db_path)
    no_op, reason = should_no_op(harness_key)
    if no_op:
        print(f"  codex-context-release: pass-through ({reason})")
        return 0
    session_name = role_config.get("tmux_session") or to_role
    ok, msg = stop_anchor(flow_key, session_name, db_path=db_path, _kill=_kill)
    if not ok:
        print(
            f"  codex-context-release: REFUSED stop ({msg}); "
            f"refusing to guess a pid. Aborting dispatch.",
            file=sys.stderr,
        )
        return 3
    if msg == "stale-anchor":
        print(
            f"  codex-context-release: stale anchor for {session_name!r}; "
            f"proceeding to relaunch."
        )
    else:
        print(f"  codex-context-release: verified stop of {session_name!r} ({msg}).")
    ok, msg = relaunch_in_session(
        session_name, role_config, db_path=db_path,
        _send_keys=_send_keys, _build_launch=_build_launch,
    )
    if not ok:
        print(
            f"  codex-context-release: RELAUNCH FAILED for "
            f"{session_name!r} ({msg}); old anchor tolerated as stale, "
            f"aborting dispatch.",
            file=sys.stderr,
        )
        return 4
    print(f"  codex-context-release: relaunched {session_name!r} ({msg}).")
    ok, msg = re_anchor(
        flow_key, session_name, db_path=db_path, _child_pid=_child_pid,
    )
    if not ok:
        print(
            f"  codex-context-release: RE-ANCHOR FAILED ({msg}); "
            f"aborting dispatch.",
            file=sys.stderr,
        )
        return 5
    print(f"  codex-context-release: {msg}.")
    return 0


def _build_argparser():
    """Build the CLI parser. Tolerated-but-ignored flags are listed so
    dispatch.py's step_to_cli_args output does not error the script.

    The D4 tests use a parser-level convenience to bypass this; the
    CLI is exercised by TG6 (no-op pass-through with policy off).
    """
    parser = argparse.ArgumentParser(
        description="Codex context-release pre-dispatch script (Spec #13).",
        add_help=True,
    )
    # Flow is accepted as both --flow and --flow-key (aliases).
    parser.add_argument("--flow", dest="flow", default=None,
                        help="(alias for --flow-key) The flow key, e.g. preferred_cloud_harness")
    parser.add_argument("--flow-key", dest="flow_key", default=None,
                        help="The flow key, e.g. preferred_cloud_harness")
    parser.add_argument("--to-role", dest="to_role", default=None,
                        help="The receiving role (the one whose context is released)")
    # Tolerated-and-ignored flags (dispatch.py step_to_cli_args produces
    # these for any pre/post-dispatch script). Keep them optional so the
    # script also works as a manual smoke-test invocation.
    for flag in ("--step-key", "--from-role", "--handoff-id",
                 "--bridge-dir", "--deliverable-dir",
                 "--deliverable-pattern", "--deliverable-file",
                 "--prompt-template"):
        parser.add_argument(flag, dest=flag.lstrip("-").replace("-", "_"),
                            default=None, help=argparse.SUPPRESS)
    return parser


def main(argv=None):
    parser = _build_argparser()
    args = parser.parse_args(argv)
    flow_key = args.flow_key or args.flow
    if not flow_key:
        print("  ERROR: --flow-key (or --flow) is required", file=sys.stderr)
        return 2
    if not args.to_role:
        print("  ERROR: --to-role is required", file=sys.stderr)
        return 2
    return run_release(flow_key, args.to_role)


if __name__ == "__main__":
    sys.exit(main())
