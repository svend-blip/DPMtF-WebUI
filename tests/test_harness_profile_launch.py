"""Tests for D2 (CODEX_PROFILE export on launch paths) + D2b (get_flow_roles SQL
crash fix) + D4 (harness_profile line in build_runtime_context).

Run 024 / handoff 092: the codex launch path threads a resolved
``harness_profile`` through ``CODEX_PROFILE`` (env) so the D1
harness-allocator adapter can render `--sandbox danger-full-access` for the
gpu profile. The profile-less path stays byte-identical to today. NULL
profile means CODEX_PROFILE is UNSET, not empty.

These tests are hermetic: isolated sqlite in tmp_path, monkeypatched env
capture, no real tmux/codex spawn. The harness-allocator package is
imported via the same seam tests/test_codex_context_release.py uses
(``HARNESS_ALLOCATOR_PATH`` env var setdefault).
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

os.environ.setdefault(
    "HARNESS_ALLOCATOR_PATH",
    str(PROJECT_ROOT.parent / "harness-allocator"),
)

# Pop CODEX_PROFILE if a previous test left it set — every test in this
# file asserts a specific env value and starts from a known baseline.
os.environ.pop("CODEX_PROFILE", None)

import config  # noqa: E402
import codex_context_release as ccr  # noqa: E402
import dispatch  # noqa: E402
import harness  # noqa: E402


# ── Test 1: LAUNCH-PATH ENV EXPORT (gpu profile) ───────────────────────


def test_build_launch_command_with_gpu_profile_sets_codex_profile_env(monkeypatch):
    """With ``harness_profile='gpu'`` in the role config, the launch path
    sets CODEX_PROFILE=gpu AND the resulting command contains
    `--sandbox danger-full-access`.

    The contract: the DPMtF-side ``harness.build_launch_command`` exports
    CODEX_PROFILE in the env when the role carries a non-empty profile,
    and the adapter then renders the gpu sandbox override.
    """
    monkeypatch.delenv("CODEX_PROFILE", raising=False)
    role = {
        "default_model_alias": "MiniMax-M3",
        "harness_profile": "gpu",
    }

    cmd = harness.build_launch_command("codex", role)

    # The env was exported.
    assert os.environ.get("CODEX_PROFILE") == "gpu", (
        f"CODEX_PROFILE must be exported as 'gpu'; got "
        f"{os.environ.get('CODEX_PROFILE')!r}"
    )

    # And the gpu sandbox override landed in the command.
    assert "--sandbox danger-full-access" in cmd, (
        f"gpu profile must render --sandbox danger-full-access; got "
        f"{cmd!r}"
    )


# ── Test 2: NULL PROFILE → UNSET (profile-less byte-identical) ────────


def test_build_launch_command_with_null_profile_keeps_byte_identical_argv(monkeypatch):
    """With absent/empty ``harness_profile``, CODEX_PROFILE is UNSET and the
    command is byte-identical to today's profile-less literal.

    The pinned profile-less literal (the DPMtF defaults are appended
    add-dirs — see config.get_codex_add_dirs):
        ``codex -m MiniMax-M3 --add-dir <...> --sandbox workspace-write
         --ask-for-approval never``
    with NO ``--sandbox danger-full-access``.
    """
    monkeypatch.delenv("CODEX_PROFILE", raising=False)

    # Call 1: no harness_profile key at all.
    role_no_profile = {"default_model_alias": "MiniMax-M3"}
    cmd_no = harness.build_launch_command("codex", role_no_profile)
    assert "--sandbox danger-full-access" not in cmd_no, (
        f"profile-less role must NOT render danger-full-access; got {cmd_no!r}"
    )
    assert "workspace-write" in cmd_no, (
        f"profile-less role must keep workspace-write; got {cmd_no!r}"
    )

    # Call 2: harness_profile is empty string.
    monkeypatch.delenv("CODEX_PROFILE", raising=False)
    role_empty = {"default_model_alias": "MiniMax-M3", "harness_profile": ""}
    cmd_empty = harness.build_launch_command("codex", role_empty)
    assert "--sandbox danger-full-access" not in cmd_empty, (
        f"empty harness_profile must NOT render danger-full-access; "
        f"got {cmd_empty!r}"
    )

    # CODEX_PROFILE must be unset (or absent) — NOT set to the empty string.
    assert os.environ.get("CODEX_PROFILE", "__UNSET__") == "__UNSET__", (
        f"empty profile must leave CODEX_PROFILE UNSET; got "
        f"{os.environ.get('CODEX_PROFILE')!r}"
    )

    # And the two profile-less commands must be byte-identical.
    assert cmd_no == cmd_empty, (
        f"profile-less commands must be byte-identical regardless of whether "
        f"the key is absent or empty; got {cmd_no!r} vs {cmd_empty!r}"
    )


# ── Test 3: RUNTIME CONTEXT RENDER (D4 dispatch line) ─────────────────


def test_build_runtime_context_renders_harness_profile_line():
    """``build_runtime_context`` renders ``- harness_profile: <value>``
    between ``harness_source`` and ``autonomous``, .get()-safe."""
    # All the keys runtime_context_block reads must be present (it
    # uses bracket indexing, not .get()).
    base_keys = {
        "flow_key": "preferred_cloud_harness",
        "step_key": "imple01-review01",
        "from_role": "imple-codex-minimaxM3",
        "to_role": "review-claude-sonnet5",
        "governance_file": "IMPLEMENTOR.md",
        "model_source": "harness",
        "harness_source": "codex",
    }

    # Case A: a dict with harness_profile="gpu".
    resolved = dict(base_keys, harness_profile="gpu")
    out = dispatch.build_runtime_context(resolved)
    assert "- harness_source: codex" in out
    assert "- harness_profile: gpu" in out
    assert "- autonomous: " in out
    # Order: harness_source < harness_profile < autonomous.
    src_idx = out.index("- harness_source:")
    prof_idx = out.index("- harness_profile:")
    auto_idx = out.index("- autonomous:")
    assert src_idx < prof_idx < auto_idx, (
        f"line order must be harness_source < harness_profile < autonomous; "
        f"got src={src_idx}, prof={prof_idx}, auto={auto_idx}"
    )

    # Case B: a dict WITHOUT the key (the .get()-safe contract).
    resolved_no_key = dict(base_keys)  # no harness_profile
    out_no_key = dispatch.build_runtime_context(resolved_no_key)
    assert "- harness_profile: None" in out_no_key, (
        f"missing harness_profile key must render as 'None'; "
        f"got {out_no_key!r}"
    )

    # Case C: None value renders as the stable literal "None".
    resolved_none = dict(base_keys, harness_profile=None)
    out_none = dispatch.build_runtime_context(resolved_none)
    assert "- harness_profile: None" in out_none


# ── Test 4: get_flow_roles NO-CRASH + PROFILE EXPOSURE (D2b) ──────────


def _build_isolated_flow_db(tmp_path):
    """Build a minimal bridge schema in tmp_path for get_flow_roles tests.

    Includes the columns get_flow_roles reads (including the new
    default_harness_profile column).
    """
    db = tmp_path / "isolated_flow.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(
            """
            CREATE TABLE bridge_flows (
                flow_key TEXT PRIMARY KEY,
                is_active INTEGER DEFAULT 1
            );
            CREATE TABLE bridge_flow_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_key TEXT NOT NULL,
                step_key TEXT NOT NULL,
                from_role TEXT NOT NULL,
                to_role TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            );
            CREATE TABLE bridge_roles (
                role_key TEXT PRIMARY KEY,
                tmux_session TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                role_type TEXT DEFAULT 'agent',
                default_model_source TEXT,
                default_model_alias TEXT,
                max_output_tokens INTEGER,
                config_dir TEXT,
                allocator_client TEXT DEFAULT 'opencode',
                workdir_mode TEXT NOT NULL DEFAULT 'target_project',
                execution_target TEXT,
                default_harness_source TEXT,
                default_harness_profile TEXT
                ,max_turns INTEGER
            );
            """
        )
        conn.execute(
            "INSERT INTO bridge_flows (flow_key, is_active) VALUES (?, 1)",
            ("preferred_cloud_harness",),
        )
        # A single active step + role to exercise the query path.
        conn.execute(
            "INSERT INTO bridge_flow_steps "
            "(flow_key, step_key, from_role, to_role, sort_order, is_active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            ("preferred_cloud_harness", "imple01-review01",
             "imple-codex-minimaxM3", "review-claude-sonnet5", 1),
        )
        conn.execute(
            "INSERT INTO bridge_roles "
            "(role_key, tmux_session, default_model_alias, "
            " default_harness_source, default_harness_profile, allocator_client) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("imple-codex-minimaxM3", "test-session", "MiniMax-M3",
             "codex", None, "codex"),
        )
        conn.commit()
    finally:
        conn.close()
    return db


def test_get_flow_roles_no_crash_and_exposes_harness_profile(tmp_path):
    """get_flow_roles no longer crashes on the ``#`` SQL-comment bug AND
    exposes a ``harness_profile`` field on each returned dict."""
    import start_coding  # local import — the import side-effect is what
                          # we're testing; isolated_db is hermetic

    db = _build_isolated_flow_db(tmp_path)

    # Pre-fix this call would raise sqlite3.OperationalError
    # "unrecognized token: '#'" (the start_coding SQL contains a literal
    # ``# deprecated: ...`` comment inside the triple-quoted SQL string).
    roles = start_coding.get_flow_roles(str(db), "preferred_cloud_harness")

    assert isinstance(roles, list)
    assert len(roles) >= 1, f"expected at least one role; got {roles!r}"

    # Every returned role carries a harness_profile field.
    for r in roles:
        assert "harness_profile" in r, (
            f"role {r.get('role_key')!r} must carry a harness_profile field; "
            f"got keys {list(r.keys())}"
        )

    # The seeded role's profile is empty (the SQL ``or ""`` COALESCE
    # mirrors the harness_source fallback pattern). Migration 071 has
    # not landed yet (handoff 3), so the column is NULL everywhere today.
    imple = next(r for r in roles if r["role_key"] == "imple-codex-minimaxM3")
    assert imple["harness_profile"] == "", (
        f"pre-migration-071 profile must COALESCE to empty string; "
        f"got {imple['harness_profile']!r}"
    )


# ── Test 5: relaunch path also exports the profile (D2 path B) ───────


def test_relaunch_in_session_exports_profile_via_build_launch(monkeypatch):
    """The codex_context_release relaunch path resolves
    ``harness_profile`` from ``role_config`` and threads it through to
    the launch command the same way the start_coding native-launch path
    does.

    Probed with monkeypatched ``_build_launch`` capturing the env at
    the moment of the call.
    """
    # Capture the env state at build_launch time.
    captured = {"env": {}, "called_with": None}

    def fake_build_launch(harness_arg, role_arg):
        captured["env"] = dict(os.environ)
        captured["called_with"] = role_arg
        return "codex -m MiniMax-M3 --sandbox danger-full-access"

    monkeypatch.delenv("CODEX_PROFILE", raising=False)

    # role_config with harness_profile=gpu (no live DB).
    role_config = {"tmux_session": "session-x", "harness_profile": "gpu"}

    # Mock the tmux has-session check.
    def fake_has_session(*args, **kwargs):
        r = type("R", (), {})()
        r.returncode = 0
        r.stdout = ""
        r.stderr = ""
        return r

    monkeypatch.setattr(ccr.subprocess, "run", fake_has_session)
    monkeypatch.setattr(ccr, "_default_send_keys", lambda name, cmd: (True, "launched"))

    ok, msg = ccr.relaunch_in_session(
        "session-x", role_config,
        _build_launch=fake_build_launch,
    )

    assert ok is True, f"relaunch must succeed; got ok={ok}, msg={msg}"
    # The build_launch was called with the role config.
    assert captured["called_with"] == role_config
    # CODEX_PROFILE was set to 'gpu' before build_launch ran.
    assert captured["env"].get("CODEX_PROFILE") == "gpu", (
        f"relaunch path must export CODEX_PROFILE=gpu before build_launch; "
        f"got env CODEX_PROFILE={captured['env'].get('CODEX_PROFILE')!r}"
    )
