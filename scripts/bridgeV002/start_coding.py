#!/usr/bin/env python3
"""start_coding.py — Start coding frontends for each role in a flow.

Usage:
    python3 scripts/bridgeV002/start_coding.py <flow_key>

Iterates through all active steps in the given flow, looks up each step's
TO-ROLE, resolves the model via Model Allocator, and starts the coding
frontend (opencode/claude-code/freebuff) in the role's tmux session.

**Assumes sessions are already created** (use start_tmuxflow.py first).
Roles without a model_allocator alias are skipped with a warning.

Example:
    python3 scripts/bridgeV002/start_coding.py strict_review
"""

import argparse
import json
import os
import shlex
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from bridge_lib import (  # noqa: E402
    ensure_opencode_model_field,
    get_effective_model_source,
    get_flow_target_project,
    resolve_placeholders,
)
import harness  # noqa: E402
import runtime_owner  # noqa: E402

# All roles use model_allocator — direct command_builder path removed.


def get_flow_roles(db_path, flow_key):
    """Fetch all role data for active steps in a flow (both from_role and to_role).

    Returns a list of dicts sorted by sort_order:
        [{role_key, tmux_session, default_model_source, default_model_alias,
          max_output_tokens, config_dir}, ...]
    Duplicate roles are deduplicated (first occurrence wins).

    Includes the last step's to_role so the final role in the chain
    also gets its coding frontend started.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Fetch from_role entries. Human roles never run a coding frontend.
    from_rows = conn.execute(
        """
        SELECT r.role_key, r.tmux_session,
               r.default_model_source, r.default_model_alias,
               r.max_output_tokens,
               r.config_dir,
               r.allocator_client,  # deprecated: fallback mirror of default_harness_source
               r.default_harness_source,
               r.workdir_mode,
               s.sort_order
        FROM bridge_flow_steps s
        JOIN bridge_roles r ON s.from_role = r.role_key
        WHERE s.flow_key = ? AND s.is_active = 1 AND r.is_active = 1
          AND r.role_type != 'human'
          -- A role with an execution_target runs elsewhere; its coding
          -- interface is the worker's own daemon, not a pane on this host.
          AND (r.execution_target IS NULL OR TRIM(r.execution_target) = '')
        """,
        (flow_key,),
    ).fetchall()

    # Fetch the last step's to_role (final role in chain, never a from_role)
    to_rows = conn.execute(
        """
        SELECT r.role_key, r.tmux_session,
               r.default_model_source, r.default_model_alias,
               r.max_output_tokens,
               r.config_dir,
               r.allocator_client,  # deprecated: fallback mirror of default_harness_source
               r.default_harness_source,
               r.workdir_mode,
               s.sort_order + 0.5 AS sort_order
        FROM bridge_flow_steps s
        JOIN bridge_roles r ON s.to_role = r.role_key
        WHERE s.flow_key = ? AND s.is_active = 1 AND r.is_active = 1
          AND r.role_type != 'human'
          -- A role with an execution_target runs elsewhere; its coding
          -- interface is the worker's own daemon, not a pane on this host.
          AND (r.execution_target IS NULL OR TRIM(r.execution_target) = '')
        ORDER BY s.sort_order DESC
        LIMIT 1
        """,
        (flow_key,),
    ).fetchall()

    # Combine and deduplicate by role_key (first occurrence wins)
    all_rows = list(from_rows) + list(to_rows)
    all_rows.sort(key=lambda r: r["sort_order"])

    seen = set()
    result = []
    for row in all_rows:
        rk = row["role_key"]
        if rk not in seen:
            seen.add(rk)
            result.append({
                "role_key": row["role_key"],
                "tmux_session": row["tmux_session"],
                "default_model_source": row["default_model_source"],
                "default_model_alias": row["default_model_alias"],
                "max_output_tokens": row["max_output_tokens"],
                "config_dir": row["config_dir"],
                "harness_source": (row["default_harness_source"] or row["allocator_client"] or "opencode"),  # allocator_client kept as fallback mirror
                "workdir_mode": row["workdir_mode"] or "target_project",
            })

    conn.close()
    return result


def ensure_session_exists(session_name):
    """Check if a tmux session exists. Returns True if it does."""
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", "=" + session_name],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def run_cmd_in_session(session_name, cmd_str, bridge_dir, project_root):
    """Send the start command string to an existing tmux session via send-keys.

    The cmd_str is a fully-formed shell command from `model-allocator run`.
    Returns True on success, False on failure.
    """
    if not cmd_str:
        print(f"  ERROR: No command string to send")
        return False

    resolved = resolve_placeholders(
        cmd_str, bridge_dir=bridge_dir, project_root=project_root
    )
    print(f"  Command: {resolved}")
    # Literal text and the Enter KEY as two calls. Without -l, send-keys
    # parses the string as key names, and a long allocator command with
    # quotes can land mangled -- observed 2026-08-07: review01LW's launch
    # arrived with a broken quote and the shell sat at a `>` continuation
    # prompt while the chain believed a client was starting. Same family as
    # tmux_session._submit's "Enter typed as five letters", fixed the same
    # way.
    target = "=" + session_name + ":0"
    first = subprocess.run(
        ["tmux", "send-keys", "-t", target, "-l", resolved],
        capture_output=True, text=True)
    second = subprocess.run(
        ["tmux", "send-keys", "-t", target, "Enter"],
        capture_output=True, text=True)
    return first.returncode == 0 and second.returncode == 0


def _pane_pid(session_name):
    """The pane shell pid of a tmux session, or None when unavailable.

    This is the pane's INTERACTIVE BASH — TERM-immune (start_coding always
    sees it, even across harness restarts). Recording IT as the
    harness_process anchor reports a stop while stopping nothing, so
    ownership recording must go one level deeper; this helper now only
    exists as a stepping stone for `_harness_child_pid`. Never record the
    pane-shell pid as the harness anchor (D3, 2026-08-21 incident).
    """
    result = subprocess.run(
        ["tmux", "display-message", "-p", "-t", "=" + session_name + ":0",
         "#{pane_pid}"],
        capture_output=True, text=True,
    )
    pid_text = (result.stdout or "").strip()
    return int(pid_text) if pid_text.isdigit() else None


def _harness_child_pid(session_name, max_wait_s=2.0):
    """Resolve the harness CHILD pid in a tmux pane, or None.

    Walks one level down from the pane's interactive bash (`# {pane_pid}`)
    to the direct child process — the harness DPMtF just launched via
    send-keys (e.g. `python3 harness_terminal.py ...`). The pane shell
    pid is TERM-immune and must never be recorded as the anchor; this
    helper returns its youngest direct child instead.

    Deterministic and testable against any process tree (NOT codex-
    specific). Uses portable `ps --ppid <pane_pid> -o pid=` semantics.
    Bounded poll (`max_wait_s`, default 2 s) for the child to appear
    after send-keys — start_coding's own `time.sleep(0.5)` between
    send-keys and `_record_harness_ownership` is normally enough, but
    the bound is there for slower hosts.

    Returns None when the pane shell cannot be resolved OR no direct
    child appears within the bound — the caller falls back to
    recording pid=None (the existing degrade path), never to the
    pane-shell pid.
    """
    pane = _pane_pid(session_name)
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
            # The earliest direct child (smallest pid) is the harness
            # that the start command forked first; subsequent children
            # are grandchildren or follow-on helpers, not the anchor.
            return min(pids)
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.1)


def _record_harness_ownership(flow_key, session_name):
    """Record that DPMtF launched (and therefore owns) this flow's harness.

    The recorded pid is the harness CHILD pid (the actual resident
    harness process launched inside the pane), not the pane shell pid —
    the pane shell is TERM-immune, so recording it as the anchor reports
    a stop while stopping nothing (2026-08-21: codex pane pid 1510133
    while the real harness child was 1511263). On resolution failure
    (child not yet visible, or pane gone) the helper falls back to
    recording pid=None — the existing degrade path. The pane-shell pid
    is NEVER recorded as the anchor.
    """
    try:
        child_pid = _harness_child_pid(session_name)
        runtime_owner.record(
            flow_key, "harness_process", session_name, pid=child_pid
        )
    except Exception:
        # Ownership recording must never fail the start itself.
        runtime_owner.record(flow_key, "harness_process", session_name, pid=None)


def _apply_fresh_context_policy(flow_key, harness_key, policy):
    """Apply a requested Codex fresh-context policy for a new work unit.

    The reset boundary lives here, at ``start_coding.py`` startup, rather
    than in dispatch, injection, or the persistent Harness Terminal. A
    correction in the same governed work unit therefore reuses the resident
    Codex session unless a new work unit explicitly requests ``work_unit``.
    Only flow-owned harness processes are stopped; externally started
    harnesses are never addressed by name. DSH is intentionally untouched.
    """
    if harness_key != "codex" or policy != "work_unit":
        return []

    stopped = runtime_owner.stop_owned_harness_processes(flow_key)
    if stopped:
        print(
            "    Fresh context requested; stopped "
            f"{len(stopped)} flow-owned Codex process(es): "
            + ", ".join(stopped)
        )
    else:
        print("    Fresh context requested; no flow-owned Codex process was running.")
    return stopped


def _compose_initial_supervisor_prompt(role, flow_key, project_root):
    """Cold-start context for a headless harness role's first wakeup.

    A resident client (Claude Code / OpenCode) receives this by the Human
    typing its cold-start skill command into the TUI. A headless one-shot
    harness has no interactive session, so DPMtF composes the same content —
    role definition, cold-start state command, target project — as one prompt.
    The governance path is built from project_root, never hardcoded.
    """
    gov_file = (role.get("governance_file") or "").strip()
    parts = [f"You are {role['role_key']}, a role in the {flow_key} flow."]
    if gov_file:
        gov_path = os.path.join(
            project_root, "docs", "governance-templates-v2", gov_file
        )
        parts.append(f"Read your role definition at {gov_path} before proceeding.")
    parts.append(
        "Reconstruct your context with the cold-start procedure: run "
        f"`python3 scripts/bridgeV002/supervisor_state.py --flow {flow_key}` "
        f"and follow the {flow_key} cold-start skill and your governance file."
    )
    parts.append(f"Target project: {project_root}.")
    return " ".join(parts)


def _harness_terminal_command(role, harness_key, flow_key, cwd, project_root):
    """The shell command that launches the persistent Harness Terminal.

    The terminal (scripts/bridgeV002/harness_terminal.py) owns the persistent
    interactive surface; the one-shot harness is invoked from inside it, so the
    tmux pane shows a real client rather than an idle shell.
    """
    script = os.path.join(project_root, "scripts", "bridgeV002", "harness_terminal.py")
    return (
        f"python3 {shlex.quote(script)} "
        f"--role {shlex.quote(role['role_key'])} "
        f"--harness {shlex.quote(harness_key)} "
        f"--model {shlex.quote(role.get('default_model_alias') or '')} "
        f"--flow {shlex.quote(flow_key)} "
        f"--cwd {shlex.quote(cwd)}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Start coding frontends for all roles in a BridgeV002 flow."
    )
    parser.add_argument("flow_key", help="Flow key (e.g. strict_review)")
    args = parser.parse_args()

    # Resolve paths — config.py lives TWO levels up from this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_derived = os.path.dirname(os.path.dirname(script_dir))

    # Directly import config from absolute path to avoid sys.path conflicts
    spec = __import__("importlib.util").util.spec_from_file_location(
        "config", os.path.join(project_root_derived, "config.py")
    )
    config_mod = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(config_mod)

    db_path = config_mod.get_db_path()
    project_root = config_mod.get_project_root()
    bridge_dir = config_mod.get_bridge_base_path()

    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}")
        sys.exit(1)

    # 1. Get all roles for this flow (deduplicated, sorted by step order)
    roles = get_flow_roles(db_path, args.flow_key)
    if not roles:
        print(f"No active steps found for flow '{args.flow_key}'. Nothing to do.")
        return

    # Resolve the flow's target project ONCE, before any session is touched.
    # get_flow_target_project falls back to Father when the flow sets no
    # target, and raises loudly on a configured-but-missing directory — so a
    # broken target fails here rather than leaving half the chain started.
    # Which directory each role actually starts in is per-role data
    # (bridge_roles.workdir_mode, migration 023): chain workers follow the
    # flow's target, Father-procedure roles (supervisors, architects) stay
    # in Father. Prompts are cwd-independent either way — dispatch injects
    # absolute governance paths and the Target Project block.
    target_cwd = get_flow_target_project(args.flow_key, db_path=db_path)

    # 2. Process each role — start coding frontend via Model Allocator
    started = []
    skipped = []
    errors = []
    for i, role in enumerate(roles):
        session_name = role["tmux_session"]

        if not role.get("default_model_source"):
            print(f"  {role['role_key']:15s} → '{session_name}'  (skipped — no model_source)")
            skipped.append(role["role_key"])
            continue

        # Verify session exists before trying to run
        if not ensure_session_exists(session_name):
            msg = f"ERROR: tmux session '{session_name}' does not exist. Run start_tmuxflow.py first."
            print(f"  {role['role_key']:15s} → '{session_name}'")
            print(f"    {msg}", file=sys.stderr)
            errors.append(role["role_key"])
            continue

        # Harness source per role from the database. PRIMARY read is
        # default_harness_source (single authoritative role-level source);
        # allocator_client is the deprecated fallback mirror (kept for
        # backwards compatibility with rows that have not yet been backfilled).
        harness_source = role.get("default_harness_source") or role.get("allocator_client") or "opencode"

        # V1B pilot: use Model Allocator when role opts in.
        model_source, model_alias = get_effective_model_source(
            role["role_key"], db_path=db_path
        )
        if model_source == "model_allocator":
            model_allocator_path = os.path.join(
                config_mod.get_project_path("model-allocator"),
                "scripts",
                "model-allocator",
            )

            # V2.2: regenerate role-specific opencode.json so the OpenCode TUI
            # uses the allocator-selected model. This is only needed/correct for
            # the opencode client; other clients follow the existing path.
            if harness_source == "opencode":
                config_dir = role.get("config_dir") or role["role_key"]
                opencode_json_path = os.path.expanduser(
                    f"~/.config/opencode-roles/{config_dir}/opencode.json"
                )
                try:
                    subprocess.run(
                        [
                            model_allocator_path,
                            "render-config",
                            "--role", role["role_key"],
                            "--client", "opencode",
                            "--output", opencode_json_path,
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=60,
                    )
                    print(f"    Regenerated opencode.json at {opencode_json_path}")
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                    print(f"    WARNING: render-config failed; continuing with start command")
                    if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
                        print(f"      stderr: {exc.stderr.strip()}")

            try:
                run_cmd = [
                    model_allocator_path,
                    "run",
                    "--role", role["role_key"],
                    "--client", harness_source,
                ]
                # Pass per-role max_output_tokens from DB
                if role.get("max_output_tokens"):
                    run_cmd += ["--max-output-tokens", str(role["max_output_tokens"])]
                # Only the first role in the chain auto-starts its server.
                # Other roles get their server started by pre_dispatch_script
                # when the flow advances to them (avoids VRAM conflicts).
                if i > 0:
                    run_cmd.append("--no-auto-start")
                result = subprocess.run(
                    run_cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=300,
                )
                shell_str = result.stdout.strip()
                cwd = project_root if role["workdir_mode"] == "father" else target_cwd
                cmd_str = f"cd {cwd} && {shell_str}"
                print(f"  {role['role_key']:15s} → '{session_name}'  (model_allocator) ...")
                ok = run_cmd_in_session(
                    session_name,
                    cmd_str,
                    bridge_dir,
                    project_root,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                print(f"  {role['role_key']:15s} → '{session_name}'")
                print(f"  ERROR calling model-allocator: {exc}")
                if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
                    print(f"    stderr: {exc.stderr.strip()}")
                errors.append(role["role_key"])
                continue

            if ok:
                started.append(session_name)
                print(f"    Command sent to session.")
            else:
                print(f"    ERROR running command in '{session_name}'.", file=sys.stderr)
                errors.append(role["role_key"])
            continue

        # Native harness (dsh, codex) — DPMtF builds the launch command itself,
        # because the model allocator has no client adapter for these harnesses.
        if model_source == "harness":
            harness_key = harness_source
            missing = harness.missing_env(harness_key)
            if missing:
                print(f"  {role['role_key']:15s} → '{session_name}'")
                print(f"  ERROR: {harness.describe_missing(harness_key, missing)}",
                      file=sys.stderr)
                errors.append(role["role_key"])
                continue
            cwd = project_root if role["workdir_mode"] == "father" else target_cwd

            # dsh headless is a ONE-SHOT invocation, not a resident process:
            # there is no dsh TUI in the installed release. The tmux session
            # hosts the persistent shell that is the role's environment, and
            # dsh is invoked fresh per wakeup (see the cold-start skill). Do
            # NOT register the (absent) dsh process as a persistent
            # harness_process — a completed one-shot requires no later Stop
            # servers shutdown, and the tmux session stays Stop tmux's job.
            if harness_key == "dsh":
                print(f"  {role['role_key']:15s} → '{session_name}'"
                      f"  (harness=dsh, Harness Terminal)")
                # Launch the persistent Harness Terminal inside the role
                # session. It prints the identity banner and waits for requests;
                # each wakeup (manual or dispatched) is a fresh one-shot harness
                # invocation, so dsh itself stays non-persistent while the
                # terminal stays alive. Do NOT record it as a harness_process:
                # it is owned by the tmux session and dies with Stop tmux.
                terminal_cmd = _harness_terminal_command(
                    role, harness_key, args.flow_key, cwd, project_root
                )
                cmd_str = f"cd {cwd} && {terminal_cmd}"
                if not run_cmd_in_session(session_name, cmd_str,
                                          bridge_dir, project_root):
                    print(f"    ERROR launching Harness Terminal in '{session_name}'.",
                          file=sys.stderr)
                    errors.append(role["role_key"])
                    continue
                started.append(session_name)
                print(f"    Harness Terminal launched.")
                # Initial supervisor wakeup: send the cold-start task to the
                # terminal; the terminal wraps it into the one-shot dsh
                # invocation itself. The terminal stays READY after dsh exits.
                initial_task = _compose_initial_supervisor_prompt(
                    role, args.flow_key, project_root
                )
                time.sleep(0.5)
                if run_cmd_in_session(session_name, initial_task,
                                      bridge_dir, project_root):
                    print(f"    Initial supervisor wakeup sent to Harness Terminal.")
                else:
                    print(f"    ERROR sending initial supervisor wakeup.",
                          file=sys.stderr)
                    errors.append(role["role_key"])
                continue

            # codex is a resident TUI: launch it and record ownership, so Stop
            # servers can tear down exactly what DPMtF started.
            policy = harness.get_codex_fresh_context_policy()
            _apply_fresh_context_policy(args.flow_key, harness_key, policy)
            try:
                shell_str = harness.build_launch_command(harness_key, role)
            except ValueError as exc:
                print(f"  {role['role_key']:15s} → '{session_name}'")
                print(f"  ERROR: {exc}", file=sys.stderr)
                errors.append(role["role_key"])
                continue
            cmd_str = f"cd {cwd} && {shell_str}"
            print(f"  {role['role_key']:15s} → '{session_name}'  (harness={harness_key}) ...")
            ok = run_cmd_in_session(session_name, cmd_str, bridge_dir, project_root)
            if ok:
                started.append(session_name)
                print(f"    Command sent to session.")
                _record_harness_ownership(args.flow_key, session_name)
            else:
                print(f"    ERROR running command in '{session_name}'.", file=sys.stderr)
                errors.append(role["role_key"])
            continue

        # If a role reaches here, it has an unknown model_source.
        print(f"  {role['role_key']:15s} → '{session_name}'")
        print(f"  ERROR: role has model_source='{model_source}' — "
              f"expected 'model_allocator' or 'harness'")
        errors.append(role["role_key"])

    # Summary
    parts = []
    if started:
        parts.append(f"{len(started)} start command(s) executed")
    if skipped:
        parts.append(f"{len(skipped)} role(s) skipped (no model_source)")
    if errors:
        parts.append(f"{len(errors)} error(s)")
    if not parts:
        print(f"\nDone: no roles with model_source in flow '{args.flow_key}'.")
    else:
        print(f"\nDone: {'; '.join(parts)}.")


if __name__ == "__main__":
    main()
