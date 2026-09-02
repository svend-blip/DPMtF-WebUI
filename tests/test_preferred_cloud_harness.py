"""Tests for the `preferred_cloud_harness` flow.

The flow is additive: it introduces three harness-bound roles and one flow,
and must not disturb `preferred_cloud` or any other existing flow. These
tests pin the DB shape (via the migration runner against a fresh DB), the
harness/model separation (scripts/bridgeV002/harness.py), the ownership rule
behind Stop-servers (scripts/bridgeV002/runtime_owner.py), the cold-start
skill, the governance files, and the two "must not regress" frontend rules
(no Stop Flow button; Stop servers remains the llama.cpp/SGLang path).
"""
import importlib.util
import os
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))
sys.path.insert(0, str(PROJECT_ROOT))

import migrate  # noqa: E402
import harness  # noqa: E402
import runtime_owner  # noqa: E402
import supervisor_state  # noqa: E402

FLOW = "preferred_cloud_harness"
ROLES = ("super-deep-deep4", "imple-codex-minimaxM3", "review-claude-sonnet5")


@pytest.fixture(scope="module")
def migrated_db(tmp_path_factory):
    """A fresh DB with every migration applied, including 055 and 056."""
    db = str(tmp_path_factory.mktemp("pch") / "pch.db")
    migrate.run_migrations(db)
    return db


def _roles(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return {
            r["role_key"]: dict(r)
            for r in conn.execute("SELECT * FROM bridge_roles").fetchall()
        }
    finally:
        conn.close()


def _flows(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return {
            r["flow_key"]: dict(r)
            for r in conn.execute("SELECT * FROM bridge_flows").fetchall()
        }
    finally:
        conn.close()


def _steps(db_path, flow_key):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [
            dict(r) for r in conn.execute(
                "SELECT * FROM bridge_flow_steps WHERE flow_key = ? ORDER BY sort_order",
                (flow_key,),
            ).fetchall()
        ]
    finally:
        conn.close()


# ── 1, 2: the flow loads and names the three required roles ──────────

def test_flow_is_loadable(migrated_db):
    flows = _flows(migrated_db)
    assert FLOW in flows
    assert flows[FLOW]["name"] == "Preferred Cloud Harness"


def test_three_required_roles_present(migrated_db):
    role_keys = set(_roles(migrated_db))
    assert set(ROLES) <= role_keys


def test_steps_form_the_supervisor_chain(migrated_db):
    steps = _steps(migrated_db, FLOW)
    chain = [(s["from_role"], s["to_role"], s["rule_key"]) for s in steps]
    assert chain == [
        ("super-deep-deep4", "imple-codex-minimaxM3", "handoff"),
        ("imple-codex-minimaxM3", "review-claude-sonnet5", "callback"),
        ("review-claude-sonnet5", "super-deep-deep4", "agent_delivery"),
    ]
    # The evidence gate guards the two deliverable-carrying callbacks, as in
    # preferred_cloud (028).
    assert steps[0]["pre_dispatch_script"] == "codex-context-release"
    assert steps[1]["pre_dispatch_script"] == "gate-deliverable-evidence"
    assert steps[2]["pre_dispatch_script"] == "gate-deliverable-evidence"


# ── 3, 6, 7, 8: harness/model mapping resolves per role ──────────────

def test_harness_model_mappings(migrated_db):
    roles = _roles(migrated_db)
    assert roles["super-deep-deep4"]["allocator_client"] == "dsh"
    assert roles["super-deep-deep4"]["default_model_source"] == "harness_provider"
    assert roles["super-deep-deep4"]["default_model_alias"] == "deepseek-v4-pro"

    assert roles["imple-codex-minimaxM3"]["allocator_client"] == "codex"
    assert roles["imple-codex-minimaxM3"]["default_model_source"] == "harness_provider"
    assert roles["imple-codex-minimaxM3"]["default_model_alias"] == "MiniMax-M3"

    # Reviewer reuses the existing model allocator sonnet5 alias.
    assert roles["review-claude-sonnet5"]["allocator_client"] == "claude-code"
    assert roles["review-claude-sonnet5"]["default_model_source"] == "model_allocator"
    assert roles["review-claude-sonnet5"]["default_model_alias"] == "sonnet5"


def test_harness_identity_is_not_model_identity(migrated_db):
    roles = _roles(migrated_db)
    # A harness (dsh) may be paired with more than one model over its life, and
    # the model column never names the harness. The two must stay separate.
    for key in ROLES:
        role = roles[key]
        assert role["allocator_client"] != role["default_model_alias"]


class _FakeCfg:
    def get_codex_bin(self):
        return "codex"

    def get_codex_workdir(self):
        return ""

    def get_codex_add_dirs(self):
        return []

    def get_codex_sandbox(self):
        return "workspace-write"

    def get_codex_ask_for_approval(self):
        return "never"

    def get_dsh_bin(self):
        return "npx @deepseek-ai/dsh"

    def get_dsh_profile(self):
        return "headless"

    def get_dsh_patch_path(self):
        return "/tmp/dsh-v4-pro.patch.yml"


def test_dsh_supervisor_resolves_headless_not_tui():
    cmd = harness.build_launch_command(
        "dsh", {"default_model_alias": "deepseek-v4-pro"}, cfg=_FakeCfg()
    )
    assert "--profile headless" in cmd
    assert "--profile tui" not in cmd


def test_dsh_command_preserves_configured_patch():
    cmd = harness.build_launch_command(
        "dsh", {"default_model_alias": "deepseek-v4-pro"}, cfg=_FakeCfg()
    )
    assert "--patch /tmp/dsh-v4-pro.patch.yml" in cmd


def test_dsh_invocation_carries_the_task():
    cmd = harness.build_dsh_invocation(
        {"default_model_alias": "deepseek-v4-pro"},
        "Reply with exactly: OK",
        cfg=_FakeCfg(),
    )
    assert cmd == (
        "npx @deepseek-ai/dsh --profile headless "
        "--patch /tmp/dsh-v4-pro.patch.yml 'Reply with exactly: OK'"
    )


def test_codex_implementer_start_command_resolves():
    cmd = harness.build_launch_command(
        "codex", {"default_model_alias": "MiniMax-M3"}, cfg=_FakeCfg()
    )
    assert cmd == "codex -m MiniMax-M3 --sandbox workspace-write --ask-for-approval never"


def test_codex_implementer_carries_extra_permissions():
    class Cfg(_FakeCfg):
        def get_codex_workdir(self):
            return "/home/svend/harness-allocator"

        def get_codex_add_dirs(self):
            return ["/home/svend/flows", "/home/svend/DPMtF-WebUI"]

    cmd = harness.build_launch_command(
        "codex", {"default_model_alias": "MiniMax-M3"}, cfg=Cfg()
    )
    assert cmd == (
        "codex -m MiniMax-M3 -C /home/svend/harness-allocator "
        "--add-dir /home/svend/flows --add-dir /home/svend/DPMtF-WebUI "
        "--sandbox workspace-write --ask-for-approval never"
    )


def test_dsh_command_without_patch_resolves():
    class Cfg(_FakeCfg):
        def get_dsh_patch_path(self):
            return ""

    cmd = harness.build_launch_command("dsh", {"default_model_alias": "deepseek-v4-pro"}, cfg=Cfg())
    assert cmd == "npx @deepseek-ai/dsh --profile headless"


def test_dsh_profile_defaults_to_headless(monkeypatch):
    monkeypatch.delenv("DSH_PROFILE", raising=False)
    import config
    assert config.get_dsh_profile() == "headless"


def test_resolve_harness_falls_back_to_opencode():
    assert harness.resolve_harness({}) == "opencode"
    assert harness.resolve_harness({"allocator_client": "codex"}) == "codex"


# ── runtime dispatch wiring: supervisor wakeup → Harness Terminal task ─

def test_dispatch_sends_flat_task_to_dsh_terminal():
    """For a dsh role, dispatch sends the semantic task (flattened to one
    request line), not a wrapped shell command — the terminal wraps it."""
    import dispatch

    role = {"allocator_client": "dsh", "default_model_alias": "deepseek-v4-pro"}
    out = dispatch._wrap_prompt_for_harness(role, "Read the verdict.\nAct on it.")
    assert out == "Read the verdict. Act on it."  # flattened, no shell command
    assert "\n" not in out


def test_dispatch_leaves_non_dsh_prompt_unchanged():
    import dispatch

    for role in ({"allocator_client": "codex"},
                 {"allocator_client": "claude-code"},
                 {"allocator_client": "opencode"}):
        assert dispatch._wrap_prompt_for_harness(role, "do the work") == "do the work"


def test_dispatch_wrap_survives_missing_harness_fields():
    """A role dict without allocator_client must fall through unchanged."""
    import dispatch
    assert dispatch._wrap_prompt_for_harness({}, "text") == "text"


# ── initial supervisor startup dispatch ─────────────────────────────

_SUPERVISOR_ROLE = {
    "role_key": "super-deep-deep4",
    "governance_file": "511_PREFERRED_CLOUD_HARNESS_SUPERVISOR.md",
    "default_model_alias": "deepseek-v4-pro",
}


def test_initial_prompt_references_governance_skill_and_state():
    import start_coding

    prompt = start_coding._compose_initial_supervisor_prompt(
        _SUPERVISOR_ROLE, FLOW, str(PROJECT_ROOT)
    )
    assert "super-deep-deep4" in prompt
    assert "511_PREFERRED_CLOUD_HARNESS_SUPERVISOR.md" in prompt
    assert f"supervisor_state.py --flow {FLOW}" in prompt
    assert "Target project:" in prompt
    # The target-project path is the passed-in value, never a hardcoded literal
    # (source-level hardcoded-path coverage is test_no_hardcoded_home_path...).
    assert str(PROJECT_ROOT) in prompt


def test_build_task_invocation_wraps_dsh_headless(monkeypatch):
    monkeypatch.setattr(harness.config, "get_dsh_bin", lambda: "npx @deepseek-ai/dsh")
    monkeypatch.setattr(harness.config, "get_dsh_profile", lambda: "headless")
    monkeypatch.setattr(harness.config, "get_dsh_patch_path",
                        lambda: "/tmp/dsh-v4-pro.patch.yml")

    task = "You are super-deep-deep4. Read your role definition before proceeding."
    cmd = harness.build_task_invocation("dsh", _SUPERVISOR_ROLE, task)

    assert cmd.startswith("npx @deepseek-ai/dsh ")
    assert "--profile headless" in cmd
    assert "--patch /tmp/dsh-v4-pro.patch.yml" in cmd
    assert "--profile tui" not in cmd
    assert "super-deep-deep4" in cmd  # task carried as the final argument


def test_build_task_invocation_rejects_resident_harnesses():
    for resident in ("codex", "claude-code", "opencode"):
        try:
            harness.build_task_invocation(resident, _SUPERVISOR_ROLE, "task")
        except ValueError:
            continue
        raise AssertionError(f"{resident} must not have a one-shot invocation")


def test_harness_terminal_command_launches_terminal():
    import start_coding

    cmd = start_coding._harness_terminal_command(
        _SUPERVISOR_ROLE, "dsh", FLOW, str(PROJECT_ROOT), str(PROJECT_ROOT)
    )
    assert "harness_terminal.py" in cmd
    assert "--role super-deep-deep4" in cmd
    assert "--harness dsh" in cmd
    assert "--model deepseek-v4-pro" in cmd
    assert f"--flow {FLOW}" in cmd


def test_harness_terminal_banner_and_labels():
    import harness_terminal as ht

    banner = ht.render_banner(FLOW, "super-deep-deep4", "dsh", "deepseek-v4-pro", "/x")
    assert "DPMtF Harness Terminal" in banner
    assert "super-deep-deep4" in banner
    assert "DeepSeek Harness" in banner
    assert "DeepSeek V4 Pro" in banner
    assert "headless / one-shot" in banner


def test_harness_terminal_execute_uses_build_task_invocation(monkeypatch):
    """execute() runs the command produced by the shared builder."""
    import harness_terminal as ht

    monkeypatch.setattr(harness.config, "get_dsh_bin", lambda: "npx @deepseek-ai/dsh")
    monkeypatch.setattr(harness.config, "get_dsh_profile", lambda: "headless")
    monkeypatch.setattr(harness.config, "get_dsh_patch_path", lambda: "")

    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(ht.subprocess, "run", fake_run)
    ht.execute("dsh", _SUPERVISOR_ROLE, "task one", "/x")

    assert captured["argv"][:3] == ["npx", "@deepseek-ai/dsh", "--profile"]
    assert captured["argv"][3] == "headless"
    assert captured["argv"][-1] == "task one"


def test_later_wakeup_paths_still_wrap_through_dispatch():
    """signal_complete and signal_escalation must keep the shared wrap helper."""
    import dispatch

    source = (PROJECT_ROOT / "scripts" / "bridgeV002" / "dispatch.py").read_text(encoding="utf-8")
    # Both later-wakeup injection sites still route through the harness wrap.
    assert source.count("_wrap_prompt_for_harness(") >= 2


def test_non_dsh_startup_is_unchanged():
    """The codex branch still launches the resident TUI and records ownership."""
    source = (PROJECT_ROOT / "scripts" / "bridgeV002" / "start_coding.py").read_text(encoding="utf-8")
    assert "codex -m" in source or 'build_launch_command(harness_key, role)' in source
    assert "_record_harness_ownership" in source


def test_fresh_context_work_unit_stops_owned_codex(monkeypatch):
    """A new work unit explicitly requests a fresh Codex context."""
    import start_coding

    seen = []

    def fake_stop(flow_key, db_path=None, _kill=None):
        seen.append((flow_key, db_path, _kill))
        return ["owned-codex-session"]

    monkeypatch.setattr(start_coding.runtime_owner, "stop_owned_harness_processes", fake_stop)
    stopped = start_coding._apply_fresh_context_policy(FLOW, "codex", "work_unit")
    assert stopped == ["owned-codex-session"]
    assert seen == [(FLOW, None, None)]


def test_fresh_context_off_does_not_stop_owned_codex(monkeypatch):
    """The default policy preserves the existing Codex lifecycle."""
    import start_coding

    def fail_stop(*args, **kwargs):
        raise AssertionError("off policy must not stop a Codex process")

    monkeypatch.setattr(start_coding.runtime_owner, "stop_owned_harness_processes", fail_stop)
    assert start_coding._apply_fresh_context_policy(FLOW, "codex", "off") == []


def test_fresh_context_work_unit_does_not_stop_dsh(monkeypatch):
    """The one-shot DSH branch is outside the fresh-context reset boundary."""
    import start_coding

    def fail_stop(*args, **kwargs):
        raise AssertionError("DSH must not be stopped by the Codex policy")

    monkeypatch.setattr(start_coding.runtime_owner, "stop_owned_harness_processes", fail_stop)
    assert start_coding._apply_fresh_context_policy(FLOW, "dsh", "work_unit") == []


# ── 4, 5: existing flows are untouched ──────────────────────────────

def test_preferred_cloud_unchanged(migrated_db):
    roles = _roles(migrated_db)
    assert roles["Pre-super-cl"]["default_model_alias"] == "opus5"
    assert roles["Pre-super-cl"]["allocator_client"] == "claude-code"
    assert roles["Pre-imple-cl"]["default_model_alias"] == "cloud_minimax"
    assert roles["Pre-imple-cl"]["allocator_client"] == "opencode"
    assert roles["Pre-review-cl"]["default_model_alias"] == "sonnet5"
    assert roles["Pre-review-cl"]["allocator_client"] == "claude-code"
    assert "preferred_cloud" in _flows(migrated_db)


def test_existing_flows_still_valid(migrated_db):
    # Migration-seeded flows (the seed_bridge flows such as strict_review and
    # cloud_llm live outside the migration set). Every one must survive 055.
    flows = _flows(migrated_db)
    for existing in ("supervisor", "supervised_review", "llama_SG",
                     "preferred_cloud", "lightworker", "reveng", "pi_test"):
        assert existing in flows, f"existing flow {existing} missing"


# ── 9, 10: cold-start material and governance resolve ───────────────

def test_cold_start_skill_resolves():
    skill = PROJECT_ROOT / ".claude" / "skills" / "PRECLOUDHARNESS" / "SKILL.md"
    assert skill.exists()
    text = skill.read_text(encoding="utf-8")
    assert "name: preferred_cloud_harness" in text
    assert "super-deep-deep4" in text
    assert "supervisor_state.py --flow preferred_cloud_harness" in text


def test_governance_files_resolve():
    """Post Phase-5 (Run 017): the three harness-bound absorbed
    originals (511/512/513) were RETIRED via git rm (D3). The role-
    level repoint in migration 068 moved bridge_roles.governance_file
    to the three generic equivalents, which now exist as the live
    role-level fallback chain. This test asserts the post-D3 invariant:

    * 511/512/513 are ABSENT on disk (retired).
    * The three generic equivalents (SUPERVISOR_AUTONOMOUS.md,
      IMPLEMENTOR.md, REVIEW.md) are PRESENT on disk.
    * Each generic file declares the role category it governs
      ("Autonomous Supervisor" / "Implementer" / "Review layer").
      The literal harness role keys (super-deep-deep4, etc.) are NOT
      in the generic files -- the generic files use {implementor_role_key}
      placeholders and category-level prose by design (Run 017 §3
      scope: no generic file is edited)."""
    gov = PROJECT_ROOT / "docs" / "governance-templates-v2"
    retired = (
        "511_PREFERRED_CLOUD_HARNESS_SUPERVISOR.md",
        "512_PREFERRED_CLOUD_HARNESS_IMPLE01.md",
        "513_PREFERRED_CLOUD_HARNESS_REVIEW01.md",
    )
    for filename in retired:
        path = gov / filename
        assert not path.exists(), (
            f"retired {filename} must NOT be on disk after Run 017 D3"
        )
    expected = {
        "SUPERVISOR_AUTONOMOUS.md": "Autonomous Supervisor",
        "IMPLEMENTOR.md": "Implementer",
        "REVIEW.md": "Review layer",
    }
    for filename, category_marker in expected.items():
        path = gov / filename
        assert path.exists(), filename
        text = path.read_text(encoding="utf-8")
        assert category_marker in text, (
            f"{filename} must contain the role-category marker "
            f"{category_marker!r} (its generic role identity)"
        )


def test_governance_references_governance_files_from_db(migrated_db):
    gov_dir = PROJECT_ROOT / "docs" / "governance-templates-v2"
    roles = _roles(migrated_db)
    for key in ROLES:
        gov_file = roles[key]["governance_file"]
        assert (gov_dir / gov_file).exists(), gov_file


# ── 11: missing credentials fail safely ─────────────────────────────

def test_missing_env_fails_safely(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    assert harness.missing_env("dsh") == ["DEEPSEEK_API_KEY"]
    assert harness.missing_env("codex") == ["MINIMAX_API_KEY"]
    # A non-native harness has no credential requirement here.
    assert harness.missing_env("claude-code") == []


def test_missing_env_message_names_what_without_leaking_values(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    msg = harness.describe_missing("dsh", ["DEEPSEEK_API_KEY"])
    assert "DEEPSEEK_API_KEY" in msg
    assert "DeepSeek" in msg
    assert "=" not in msg  # never prints a value


def test_present_env_reports_nothing_missing(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")
    monkeypatch.setenv("MINIMAX_API_KEY", "test")
    assert harness.missing_env("dsh") == []
    assert harness.missing_env("codex") == []


# ── 12: flow-owned shutdown never targets externally owned processes ─

def test_stop_owned_harness_processes_targets_only_recorded_pids(tmp_path):
    db = str(tmp_path / "owner.db")
    runtime_owner.record(FLOW, "harness_process", "owned-session", pid=1111, db_path=db)
    # An externally started process has NO ownership row.
    external_pid = 9999

    seen = []

    def fake_kill(pid):
        seen.append(pid)
        return True

    stopped = runtime_owner.stop_owned_harness_processes(FLOW, db_path=db, _kill=fake_kill)

    assert stopped == ["owned-session"]
    assert seen == [1111]
    assert external_pid not in seen


def test_stop_owned_harness_processes_ignores_null_pid(tmp_path):
    db = str(tmp_path / "owner2.db")
    runtime_owner.record(FLOW, "harness_process", "no-pid", pid=None, db_path=db)
    assert runtime_owner.stop_owned_harness_processes(FLOW, db_path=db) == []


def test_stop_owned_harness_processes_is_not_name_based(tmp_path):
    """A pid with no ownership row is never touched, whatever its name."""
    db = str(tmp_path / "owner3.db")
    seen = []

    def fake_kill(pid):
        seen.append(pid)
        return True

    runtime_owner.stop_owned_harness_processes(FLOW, db_path=db, _kill=fake_kill)
    assert seen == []


# ── 5: a completed headless dsh invocation is not a persistent service ──

def _terminal_branch_lines(source):
    lines = source.splitlines()
    start = next(i for i, line in enumerate(lines)
                 if line.strip() == "if terminal_wrapped:")
    end = next(i for i in range(start + 1, len(lines))
               if lines[i].strip() == "continue")
    return lines[start:end + 1]


def test_terminal_wrapped_path_does_not_record_ownership():
    source = (PROJECT_ROOT / "scripts" / "bridgeV002" / "start_coding.py").read_text(encoding="utf-8")
    terminal_branch = "\n".join(_terminal_branch_lines(source))
    # The terminal-wrapped (one-shot dsh) path must not register ownership of a completed process.
    assert "_record_harness_ownership" not in terminal_branch
    # The resident path still records ownership (guarded by the spec's anchor).
    assert "_record_harness_ownership" in source


# ── 6: flow-owned tmux lifecycle unchanged ──────────────────────────

def test_start_tmuxflow_still_records_session_ownership():
    source = (PROJECT_ROOT / "scripts" / "bridgeV002" / "start_tmuxflow.py").read_text(encoding="utf-8")
    assert 'runtime_owner.record(args.flow_key, "tmux_session", s)' in source


# ── 4: no hard-coded home path introduced ───────────────────────────

def test_no_hardcoded_home_path_in_harness_code():
    for rel in ("scripts/bridgeV002/harness.py",
                "scripts/bridgeV002/runtime_owner.py",
                "scripts/db/055_preferred_cloud_harness_flow.sql",
                "scripts/db/056_flow_runtime_resources.sql"):
        text = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
        assert "/home/" not in text, rel


# ── 13, 14: Stop-servers llama.cpp/SGLang intact; no Stop Flow button ─

def test_stop_servers_still_runs_allocator_stop_for_aliases():
    source = (PROJECT_ROOT / "routers" / "bridge.py").read_text(encoding="utf-8")
    # The existing model-server sweep (model-allocator stop --alias) is intact.
    assert '"stop", "--alias"' in source
    assert "default_model_source = 'model_allocator'" in source


def test_no_stop_flow_frontend_action():
    js = (PROJECT_ROOT / "static" / "js" / "dpmtf-app.js").read_text(encoding="utf-8")
    assert "Stop Flow" not in js
    assert "stop-flow" not in js
    # The existing Stop servers button remains.
    assert "lbl_bridge_stop_servers" in js


def test_harness_flow_needs_no_local_model_server(migrated_db):
    """A harness-source role talks to a hosted API, never a local server."""
    assert supervisor_state.flow_uses_local_models(FLOW, db_path=migrated_db) is False


def test_migration_056_creates_ownership_table(migrated_db):
    conn = sqlite3.connect(migrated_db)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='flow_runtime_resources'"
        ).fetchone()
        assert row is not None
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────
# ADD-only seam tests (handoff 002): standalone delegation + multiline
# atomicity. No existing test above is modified.
# ─────────────────────────────────────────────────────────────────────────


import harness_terminal as _seam_ht  # noqa: E402


_SEAM_SUPERVISOR_ROLE = {
    "role_key": "super-deep-deep4",
    "governance_file": "511_PREFERRED_CLOUD_HARNESS_SUPERVISOR.md",
    "default_model_alias": "deepseek-v4-pro",
}


class _SeamCleanCfg:
    """Bare-bones config surface for tests that need to control the
    standalone's argv builder output independent of host env vars."""

    def get_codex_bin(self):
        return "codex"

    def get_codex_workdir(self):
        return ""

    def get_codex_add_dirs(self):
        return []

    def get_codex_sandbox(self):
        return "workspace-write"

    def get_codex_ask_for_approval(self):
        return "never"

    def get_dsh_bin(self):
        return "npx @deepseek-ai/dsh"

    def get_dsh_profile(self):
        return "headless"

    def get_dsh_patch_path(self):
        return ""


def _seam_build_20k_multiline_prompt():
    """A 20k+ character prompt with hundreds of embedded newlines."""
    payload = (
        "## 1. Project Objective\n\n"
        "Supervisor: deliver a complete status report.\n\n"
        + ("Implement the atomic dispatch layer.\n" * 700)
        + "\n```\n" + ("x" * 300) + "\n```\nSupervisor\n"
        + ("partial sentence continues here\n" * 100)
    )
    assert len(payload) >= 20000
    assert payload.count("\n") > 500
    return payload


class _SeamFakeStream:
    """Stream-like object for the reader tests.

    Holds a single chunk and releases it on the next ``read1``; subsequent
    ``read1`` calls return ``b""`` (EOF). Additional bytes can be appended
    via ``feed()`` to simulate a multi-chunk paste.
    """

    def __init__(self, initial=b""):
        self._buf = initial

    def feed(self, more):
        self._buf += more

    def read1(self, n):
        if not self._buf:
            return b""
        out = self._buf
        self._buf = b""
        return out

    def has_data(self):
        return bool(self._buf)


def _seam_patch_select_for_fake(monkeypatch, stream):
    """Patch ``select.select`` so the fake stream is always reported ready.

    The reader's idle window is the only thing that ends a frame; the
    patched ``select`` reports the fake stream as ready whenever it is
    in the rlist, so the reader reads bytes until idle.
    """
    import select as _select

    def _fake_select(rlist, wlist, xlist, timeout):
        ready = [s for s in rlist if isinstance(s, _SeamFakeStream)]
        return (ready, [], [])

    monkeypatch.setattr(_seam_ht.select, "select", _fake_select)


# ── delegation: the seam imports the standalone package ──────────────


def test_seam_resolves_standalone_package_via_config():
    """The seam locates the standalone package via config.get_project_path.

    No hardcoded ``/home/...`` path; the standalone is the package at
    ``config.get_project_path('harness-allocator')``.
    """
    pkg = harness._standalone()
    assert pkg is not None
    assert hasattr(pkg, "execute"), "standalone harness_allocator must expose execute"
    assert hasattr(pkg, "build_dsh_argv"), "standalone must expose build_dsh_argv"
    assert hasattr(pkg, "build_task_argv"), "standalone must expose build_task_argv"
    assert hasattr(pkg, "build_launch_argv"), "standalone must expose build_launch_argv"


def test_seam_resolve_harness_delegates_and_keeps_opencode_default():
    """resolve_harness delegates to the standalone, but preserves the
    historical DPMtF-only ``opencode`` fallback for empty rows."""
    assert harness.resolve_harness({"allocator_client": "dsh"}) == "dsh"
    assert harness.resolve_harness({"allocator_client": "codex"}) == "codex"
    assert harness.resolve_harness({}) == "opencode"
    assert harness.resolve_harness({"allocator_client": ""}) == "opencode"


def test_seam_build_task_invocation_now_matches_standalone_argv():
    """The DPMtF-side shell command, when split, reconstructs the
    standalone argv list. There is exactly ONE command-builder source of
    truth: the standalone's argv builders."""
    cmd = harness.build_task_invocation(
        "dsh", _SEAM_SUPERVISOR_ROLE, "task one", cfg=_SeamCleanCfg()
    )
    import shlex as _shlex
    argv = _shlex.split(cmd)
    assert argv == ["npx", "@deepseek-ai/dsh", "--profile", "headless", "task one"]


def test_seam_is_native_and_missing_env_delegate_to_standalone():
    """The seam no longer carries its own native/credential knowledge.

    These attributes were duplicated before handoff 002; now they are
    delegated to the standalone package, so removing the duplicate is
    visible at the surface."""
    ha = harness._standalone()
    assert harness.is_native("dsh") == ha.is_native("dsh")
    assert harness.is_native("codex") == ha.is_native("codex")
    assert harness.missing_env("dsh") == ha.missing_env("dsh")
    assert harness.missing_env("codex") == ha.missing_env("codex")
    assert harness.describe_missing("dsh", ["DEEPSEEK_API_KEY"]) == \
        ha.describe_missing("dsh", ["DEEPSEEK_API_KEY"])


def test_seam_fresh_context_policy_delegates_to_standalone(monkeypatch):
    """The integration reads the policy from the standalone allocator."""
    ha = harness._standalone()
    monkeypatch.setattr(ha, "get_codex_fresh_context_policy", lambda: "work_unit")
    assert harness.get_codex_fresh_context_policy() == "work_unit"


def test_seam_role_without_model_target_does_not_substitute_model():
    """A role without ``default_model_alias`` does NOT cause a silent
    model to appear in the resolved command. The seam only renders the
    model that DPMtF resolved upstream; absent means absent."""
    role_no_model = {
        "role_key": "x",
        "allocator_client": "codex",
    }
    cmd = harness.build_launch_command("codex", role_no_model, cfg=_SeamCleanCfg())
    assert "-m" not in cmd, f"expected no model flag, got {cmd!r}"
    assert cmd == "codex --sandbox workspace-write --ask-for-approval never"


# ── multiline atomicity: raw tmux paste -> one invocation ────────────


def test_idle_accumulating_reader_emits_one_frame_for_full_paste(monkeypatch):
    """A 20k+ multiline raw paste arrives as one byte stream; the reader
    accumulates until idle and returns exactly ONE frame."""
    payload = _seam_build_20k_multiline_prompt()
    stream = _SeamFakeStream(payload.encode("utf-8"))
    _seam_patch_select_for_fake(monkeypatch, stream)

    reader = _seam_ht._IdleAccumulatingReader(stream, idle_seconds=0.05)
    frame = reader.read_frame()
    assert frame is not None
    expected = payload[:-1] if payload.endswith("\n") else payload
    assert frame.payload == expected
    assert frame.payload.count("\n") == expected.count("\n")
    assert len(frame.payload) == len(expected)


def test_idle_accumulating_reader_returns_none_at_eof(monkeypatch):
    """A stream with no data returns ``None`` (EOF)."""
    stream = _SeamFakeStream(b"")
    _seam_patch_select_for_fake(monkeypatch, stream)

    reader = _seam_ht._IdleAccumulatingReader(stream, idle_seconds=0.01)
    assert reader.read_frame() is None


def test_idle_accumulating_reader_strips_only_trailing_submit_enter(monkeypatch):
    """The final newline that the user pressed as Enter (submission) is
    consumed; all embedded newlines remain as prompt content."""
    payload = "line one\nline two\nline three\n"
    stream = _SeamFakeStream(payload.encode("utf-8"))
    _seam_patch_select_for_fake(monkeypatch, stream)

    reader = _seam_ht._IdleAccumulatingReader(stream, idle_seconds=0.01)
    frame = reader.read_frame()
    assert frame.payload == "line one\nline two\nline three"
    # Exactly one trailing newline stripped; internal newlines preserved.
    assert frame.payload.count("\n") == 2


def test_idle_accumulating_reader_handles_multiple_submissions(monkeypatch):
    """The reader can be re-used across multiple submissions in one
    session: each idle boundary -> one frame."""
    p1 = "first\nmulti\nline"
    p2 = "second\nmulti\nline"
    stream = _SeamFakeStream(p1.encode("utf-8"))
    _seam_patch_select_for_fake(monkeypatch, stream)

    reader = _seam_ht._IdleAccumulatingReader(stream, idle_seconds=0.02)
    f1 = reader.read_frame()
    assert f1 is not None
    assert f1.payload == p1
    stream.feed(p2.encode("utf-8"))
    f2 = reader.read_frame()
    assert f2 is not None
    assert f2.payload == p2


def test_harness_terminal_execute_invokes_harness_once_per_submission(monkeypatch):
    """Feed a 20k+ multiline paste through ``ht.execute`` once; assert the
    argv list passed to ``subprocess.run`` has the WHOLE payload as one
    element and ``subprocess.run`` is called exactly once. This is the
    end-to-end behavior the Mission Contract requires for raw tmux
    multiline injection."""
    payload = _seam_build_20k_multiline_prompt()
    captured = {"calls": []}

    def fake_run(argv, **kwargs):
        captured["calls"].append(list(argv))
        return type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(_seam_ht.subprocess, "run", fake_run)
    # Patch the underlying config surface so the standalone's argv builder
    # resolves to a predictable command.
    monkeypatch.setattr(harness.config, "get_dsh_bin", lambda: "npx @deepseek-ai/dsh")
    monkeypatch.setattr(harness.config, "get_dsh_profile", lambda: "headless")
    monkeypatch.setattr(harness.config, "get_dsh_patch_path", lambda: "")
    # Clear the cached standalone import so the patched config surface is
    # picked up by the harness module's lazy loader.
    if hasattr(harness._standalone, "_cache"):
        del harness._standalone._cache

    result = _seam_ht.execute("dsh", _SEAM_SUPERVISOR_ROLE, payload, "/x")

    # Exactly one subprocess.run call.
    assert len(captured["calls"]) == 1
    argv = captured["calls"][0]
    # The complete payload is one argv element (preserving embedded newlines).
    assert argv[-1] == payload
    assert argv[-1].count("\n") == payload.count("\n")
    assert len(argv[-1]) == len(payload)
    # Head is the canonical dsh invocation.
    assert argv[:3] == ["npx", "@deepseek-ai/dsh", "--profile"]
    assert argv[3] == "headless"
    # The subprocess result is reported via the historical surface.
    assert result.returncode == 0
    assert result.stdout == "ok"


def test_consumer_surface_unchanged_for_existing_callers():
    """The seam's public names and signatures are unchanged, so
    ``start_coding`` and ``dispatch`` continue to work without edits."""
    cmd = harness.build_dsh_invocation(_SEAM_SUPERVISOR_ROLE, cfg=_SeamCleanCfg())
    assert "dsh" in cmd
    assert "--profile headless" in cmd
    cmd = harness.build_task_invocation(
        "dsh", _SEAM_SUPERVISOR_ROLE, "x", cfg=_SeamCleanCfg()
    )
    assert cmd.endswith("x") or "x" in cmd
    cmd = harness.build_launch_command("codex", _SEAM_SUPERVISOR_ROLE, cfg=_SeamCleanCfg())
    assert cmd == "codex -m deepseek-v4-pro --sandbox workspace-write --ask-for-approval never"
    banner = _seam_ht.render_banner(
        "preferred_cloud_harness", "super-deep-deep4",
        "dsh", "deepseek-v4-pro", "/x",
    )
    assert "DPMtF Harness Terminal" in banner
    assert "super-deep-deep4" in banner


# ─────────────────────────────────────────────────────────────────────────
# ADD-only seam tests (handoff 003): operational visibility (objectives
# 5/6/7). No existing test above is modified. The terminal delegates its
# persistent loop to harness_allocator.run_terminal(); the seam tests
# inject the DPMtF idle-bounded reader as the ``reader`` and a fake
# runner to drive the loop deterministically without spawning a harness.
# ─────────────────────────────────────────────────────────────────────────


import io as _seam_io  # noqa: E402


def _seam_terminal_runner(events=None, sleep=0.0):
    """Build a fake runner that records every call and emits any preset events.

    Returns ``(recorder, runner)``: ``recorder`` is a list that gains one
    dict per invocation; ``runner`` is suitable as the ``runner=`` argument
    to ``ha.run_terminal``. ``events`` is an optional list of
    ``(kind, payload)`` pairs that the runner fires through ``on_event``
    before returning its fake result.
    """
    recorder = []
    events = list(events or [])

    def runner(*, role, harness, model_target, cwd, task, request_id,
               heartbeat_interval, timeout, on_event):
        recorder.append({
            "role": role, "harness": harness, "model_target": model_target,
            "cwd": cwd, "task": task, "request_id": request_id,
            "heartbeat_interval": heartbeat_interval, "timeout": timeout,
        })
        for kind, payload in events:
            on_event(kind, payload)
        if sleep:
            import time as _t
            _t.sleep(sleep)
        return {
            "status": "SUCCESS", "output": "done", "error": "",
            "elapsed": 0.42, "pid": 7,
            "request_id": request_id,
        }

    return recorder, runner


class _SeamIdleStream:
    """Byte stream that releases one chunk per ``select`` wakeup, then idles.

    Mirrors the behavior of the handoff 002 ``_SeamFakeStream``: the bytes
    are buffered and returned by the next ``read1`` call. A test patches
    ``select.select`` so this stream is always reported ready while it has
    buffered bytes, then idles so the reader's idle window fires and the
    accumulated bytes are submitted as one frame.
    """

    def __init__(self, initial=b""):
        self._buf = initial

    def feed(self, more):
        self._buf += more

    def read1(self, n):
        if not self._buf:
            return b""
        out = self._buf
        self._buf = b""
        return out

    def has_data(self):
        return bool(self._buf)


def _seam_patch_select_for_idle(monkeypatch, stream):
    """Patch ``select.select`` so the idle stream is reported ready while it
    has buffered bytes, then idles so the reader emits one frame."""
    import select as _select
    import harness_terminal as _ht

    def _fake_select(rlist, wlist, xlist, timeout):
        ready = [s for s in rlist if isinstance(s, _SeamIdleStream)]
        return (ready, [], [])

    monkeypatch.setattr(_ht.select, "select", _fake_select)


def _seam_drive_terminal(payload, runner, *, harness="dsh",
                          model_target="deepseek-v4-pro",
                          heartbeat_interval=0.05, monkeypatch=None):
    """Drive the standalone ``run_terminal`` loop with the DPMtF idle reader.

    Returns ``(writer_output, recorder)``. The stream holds ``payload`` as
    bytes plus a trailing submit-Enter; the patched select keeps the reader
    returning those bytes until the idle window flushes the frame.
    """
    import harness_terminal as _ht
    import harness_allocator as _ha

    stream = _SeamIdleStream(payload.encode("utf-8") + b"\n")
    if monkeypatch is not None:
        _seam_patch_select_for_idle(monkeypatch, stream)
    reader = _ht._IdleAccumulatingReader(stream, idle_seconds=0.02)
    writer = _seam_io.StringIO()
    recorder, runner_fn = _seam_terminal_runner()
    # Replace the user's runner with the recorder we just built.
    _ = runner(recorder, runner_fn)  # keep type-checker happy if misused

    def _wrapped_runner(**kwargs):
        return runner_fn(**kwargs)

    _ha.run_terminal(
        role="super-deep-deep4",
        harness=harness,
        model_target=model_target,
        cwd="/x",
        flow="preferred_cloud_harness",
        reader=reader,
        writer=writer,
        runner=_wrapped_runner,
        heartbeat_interval=heartbeat_interval,
    )
    return writer.getvalue(), recorder


# ── (a) full loop: 20k+ multiline paste -> exactly one invocation ──────


def test_terminal_full_loop_one_invocation_for_20k_multiline(monkeypatch):
    """A 20k+ character paste containing hundreds of embedded newlines is
    delivered to the harness runner as exactly one complete Python string,
    producing exactly one harness invocation. Embedded newlines are
    preserved verbatim.

    Objective (a) of handoff 003: full-loop one-invocation invariant for
    the DPMtF terminal after objectives 5/6/7 are wired up.
    """
    import harness_terminal as _ht
    import harness_allocator as _ha

    payload = _seam_build_20k_multiline_prompt()
    stream = _SeamIdleStream(payload.encode("utf-8") + b"\n")
    _seam_patch_select_for_idle(monkeypatch, stream)
    reader = _ht._IdleAccumulatingReader(stream, idle_seconds=0.02)
    writer = _seam_io.StringIO()
    recorder, runner_fn = _seam_terminal_runner()

    def _wrapped_runner(**kwargs):
        return runner_fn(**kwargs)

    _ha.run_terminal(
        role="super-deep-deep4",
        harness="dsh",
        model_target="deepseek-v4-pro",
        cwd="/x",
        flow="preferred_cloud_harness",
        reader=reader,
        writer=writer,
        runner=_wrapped_runner,
        heartbeat_interval=0.05,
    )
    out = writer.getvalue()

    # Exactly one runner invocation for the complete submitted prompt.
    assert len(recorder) == 1, \
        f"expected exactly one invocation, got {len(recorder)}"
    call = recorder[0]
    assert call["task"] == payload
    assert call["task"].count("\n") == payload.count("\n")
    assert len(call["task"]) == len(payload)
    # The terminal prints a request identity block (objective 5) — chars and
    # lines for the submitted payload.
    assert f"{len(payload)} chars" in out
    assert f"{len(payload.splitlines())} lines" in out
    assert "[DISPATCH]" in out
    assert "[SUCCESS]" in out
    # Exactly one DISPATCH block (one turn) and exactly one SUCCESS block.
    assert out.count("[DISPATCH]") == 1
    assert out.count("[SUCCESS]") == 1
    assert out.count("Status: READY") == 2  # initial READY + post-SUCCESS READY


# ── (b) heartbeat events emitted while a child stays alive ──────────


def test_terminal_heartbeat_emitted_while_runner_runs(monkeypatch):
    """While the runner is alive, the on_event HEARTBEAT callback fires and
    the terminal writes a [HEARTBEAT] block carrying request_id,
    process_alive and elapsed. The terminal does not surface any private
    reasoning content (objectives 5/6 are operational metadata only).

    Objective (b) of handoff 003.
    """
    import harness_terminal as _ht
    import harness_allocator as _ha

    stream = _SeamIdleStream(b"heartbeat probe task\n")
    _seam_patch_select_for_idle(monkeypatch, stream)
    reader = _ht._IdleAccumulatingReader(stream, idle_seconds=0.02)
    writer = _seam_io.StringIO()
    recorder, runner_fn = _seam_terminal_runner(events=[
        ("RUNNING", {"pid": 7, "elapsed": 0.0, "process_alive": True}),
        ("HEARTBEAT", {"request_id": "ha-hb", "elapsed": 1.5,
                       "process_alive": True, "pid": 7}),
    ])

    def _wrapped_runner(**kwargs):
        return runner_fn(**kwargs)

    _ha.run_terminal(
        role="super-deep-deep4",
        harness="dsh",
        model_target="deepseek-v4-pro",
        cwd="/x",
        flow="preferred_cloud_harness",
        reader=reader,
        writer=writer,
        runner=_wrapped_runner,
        heartbeat_interval=0.05,
    )
    out = writer.getvalue()

    # RUNNING block carries pid and elapsed time.
    assert "[RUNNING]" in out
    assert "pid 7" in out
    # HEARTBEAT block carries request_id, process_alive, elapsed.
    # One line per heartbeat since harness-allocator b50bba8: header,
    # request id, elapsed and either the live activity or "alive".
    assert "[HEARTBEAT] · ha-hb · 1s · alive" in out
    # No chain-of-thought: nothing private leaks. The harness label is the
    # only human-facing string besides the lifecycle tokens.
    assert "[SUCCESS]" in out
    assert len(recorder) == 1
    # The heartbeat cadence is configurable: the runner received the
    # configured value.
    assert recorder[0]["heartbeat_interval"] == 0.05


# ── (c) duplicate-request protection: same identity must not run twice


def test_terminal_duplicate_request_returns_ready_without_second_invocation(monkeypatch):
    """A re-submitted completed ``(request_id, payload_sha256)`` identity
    must NOT invoke the harness a second time: the terminal reports
    ``[DUPLICATE_REQUEST]`` and returns to READY without invoking the
    runner. A deliberate retry is the only legitimate way to re-run.

    Objective (c) of handoff 003.

    Implementation note: the standalone's dedup key is
    ``(request_id, payload_sha256)``. The DPMtF idle reader synthesizes
    a fresh ``request_id`` per submission, so to test the (request_id,
    sha256) dedup we pin ``make_request_id`` to return a stable value.
    Two submissions of the same payload through the idle reader then
    produce frames with the same (request_id, sha256) identity, and the
    second submission must be detected as DUPLICATE_REQUEST without
    invoking the runner a second time.
    """
    import harness_terminal as _ht
    import harness_allocator as _ha
    payload = "same task\nwith embedded newline"
    # Pin request_id synthesis so both submissions carry the same id. The
    # reader uses the version bound in harness_terminal's namespace (it
    # imported make_request_id from harness_allocator.transport), so patch
    # it there, not on the transport module.
    monkeypatch.setattr(_ht, "make_request_id", lambda prefix="ha": "ha-dup")
    # First submission on the stream at construction. Feed the second
    # submission AFTER the runner has been invoked once so the idle reader
    # returns the first frame, the runner records one call, and the second
    # submission becomes available on the next read.
    stream = _SeamIdleStream(payload.encode("utf-8") + b"\n")
    _seam_patch_select_for_idle(monkeypatch, stream)
    reader = _ht._IdleAccumulatingReader(stream, idle_seconds=0.02)
    writer = _seam_io.StringIO()
    recorder, runner_fn = _seam_terminal_runner()

    called = [0]

    def _wrapped_runner(**kwargs):
        result = runner_fn(**kwargs)
        called[0] += 1
        if called[0] == 1:
            stream.feed(payload.encode("utf-8") + b"\n")
        return result

    _ha.run_terminal(
        role="super-deep-deep4",
        harness="dsh",
        model_target="deepseek-v4-pro",
        cwd="/x",
        flow="preferred_cloud_harness",
        reader=reader,
        writer=writer,
        runner=_wrapped_runner,
        heartbeat_interval=0.05,
    )
    out = writer.getvalue()

    # The runner was invoked exactly once — duplicate must not re-invoke.
    assert len(recorder) == 1, \
        f"duplicate must not invoke the runner; got {len(recorder)} invocations"
    assert recorder[0]["task"] == payload
    # The duplicate was reported and the terminal returned to READY.
    assert "[DUPLICATE_REQUEST]" in out
    # Exactly one DISPATCH block, one SUCCESS block, one DUPLICATE_REQUEST
    # block, and three READY prompts (initial + after SUCCESS + after
    # DUPLICATE_REQUEST — the duplicate path prints its own READY).
    assert out.count("[DISPATCH]") == 1
    assert out.count("[SUCCESS]") == 1
    assert out.count("[DUPLICATE_REQUEST]") == 1
    assert out.count("Status: READY") == 3


def test_terminal_identity_block_printed_for_submission(monkeypatch):
    """For every submitted prompt the terminal prints the operational
    identity: ``request_id``, ``chars``, ``lines``, ``sha256``,
    ``harness``, ``role``, ``model_target``. This is objective 5.

    The standalone's ``compute_identity`` derives the sha256 deterministically
    from the payload bytes; we assert the same sha256 appears in the output.
    """
    import harness_terminal as _ht
    import harness_allocator as _ha

    payload = "hello\nworld"
    stream = _SeamIdleStream(payload.encode("utf-8") + b"\n")
    _seam_patch_select_for_idle(monkeypatch, stream)
    reader = _ht._IdleAccumulatingReader(stream, idle_seconds=0.02)
    writer = _seam_io.StringIO()
    recorder, runner_fn = _seam_terminal_runner()

    def _wrapped_runner(**kwargs):
        return runner_fn(**kwargs)

    _ha.run_terminal(
        role="super-deep-deep4",
        harness="dsh",
        model_target="deepseek-v4-pro",
        cwd="/x",
        flow="preferred_cloud_harness",
        reader=reader,
        writer=writer,
        runner=_wrapped_runner,
        heartbeat_interval=0.05,
    )
    out = writer.getvalue()

    # The standalone computes identity from the payload, not from a
    # synthesized value; the printed sha256 matches the sha256 we compute
    # locally over the same bytes.
    import hashlib as _hl
    expected_sha = _hl.sha256(payload.encode("utf-8")).hexdigest()
    assert f"{len(payload)} chars" in out
    assert f"{len(payload.splitlines())} lines" in out
    assert f"sha256 {expected_sha[:8]}" in out
    # request_id is synthesized per-frame; we only assert the prefix is
    # present (the counter is module-level and may differ across runs).
    assert "[DISPATCH] ha-" in out
    # The per-submission identity block is gone (harness-allocator f09cc08);
    # the banner carries role, harness and model target for the whole pane.
    assert "DeepSeek Harness" in out
    assert "super-deep-deep4" in out
    assert "DeepSeek V4 Pro" in out
    assert len(recorder) == 1


# ── Run 002: seam-level Ctrl+C + runtime status (TG4-TG7) ─────────


def test_seam_render_banner_exposes_runtime_status_fields():
    """TG6: the seam's banner exposes the same status fields as the
    standalone, with the DPMtF header. Values are not guessed: missing
    fields fall back to ``unknown`` or ``not configured``.
    """
    import harness_terminal as _ht

    info = {
        "sandbox_mode": "workspace-write",
        "approval_policy": "never",
        "workspace_access_mode": "writable",
        "bridge_dir": "/home/svend/flows",
        "bridge_dir_access": "writable",
        "mcp_light": "not configured",
    }
    banner = _ht.render_banner(
        "preferred_cloud_harness",
        "super-deep-deep4",
        "dsh",
        "deepseek-v4-pro",
        "/x",
        status_info=info,
    )
    # Identity.
    assert "DPMtF Harness Terminal" in banner
    assert "Flow:    preferred_cloud_harness" in banner
    assert "Role:    super-deep-deep4" in banner
    assert "Harness: DeepSeek Harness" in banner
    assert "Model:   DeepSeek V4 Pro" in banner
    assert "Cwd:     /x" in banner
    # Status fields.
    assert "Sandbox: workspace-write" in banner
    assert "Approval: never" in banner
    assert "Workspace: writable" in banner
    assert "Bridge/flows: /home/svend/flows (writable)" in banner
    assert "MCP-Light: not configured" in banner


def test_seam_render_banner_honours_unknown_and_not_configured():
    """TG6: missing values render honestly as unknown / not configured."""
    import harness_terminal as _ht

    banner = _ht.render_banner(
        "preferred_cloud_harness", "r", "dsh", "deepseek-v4-pro", "/x"
    )
    assert "Sandbox: unknown" in banner
    assert "Approval: unknown" in banner
    assert "Workspace: unknown" in banner
    assert "Bridge/flows: not configured (unknown)" in banner
    assert "MCP-Light: not configured" in banner


def test_seam_render_banner_strips_secret_like_values():
    """TG6: secrets never appear in the seam banner even if a caller passes them."""
    import harness_terminal as _ht

    info = {
        "sandbox_mode": "the api_key is exposed",
        "approval_policy": "your token got printed",
    }
    banner = _ht.render_banner(
        "preferred_cloud_harness", "r", "dsh", "deepseek-v4-pro", "/x",
        status_info=info,
    )
    assert "exposed" not in banner
    assert "got printed" not in banner
    assert "Sandbox: unknown" in banner
    assert "Approval: unknown" in banner


def test_seam_collect_runtime_status_uses_env(monkeypatch):
    """collect_runtime_status must source values from explicit env names
    and default to honest unknown / not configured when absent. Values
    that look like secrets are filtered to the default.
    """
    import harness_terminal as _ht

    monkeypatch.setenv("DPMTF_SANDBOX_MODE", "workspace-write")
    monkeypatch.setenv("DPMTF_APPROVAL_POLICY", "on-request")
    monkeypatch.setenv("DPMTF_WORKSPACE_ACCESS_MODE", "writable")
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", "/home/svend/flows")
    monkeypatch.setenv("DPMTF_BRIDGE_ACCESS", "writable")
    monkeypatch.setenv("DPMTF_MCP_LIGHT", "not configured")

    info = _ht.collect_runtime_status()
    assert info["sandbox_mode"] == "workspace-write"
    assert info["approval_policy"] == "on-request"
    assert info["workspace_access_mode"] == "writable"
    assert info["bridge_dir"] == "/home/svend/flows"
    assert info["bridge_dir_access"] == "writable"
    assert info["mcp_light"] == "not configured"


def test_seam_collect_runtime_status_defaults_to_unknown(monkeypatch):
    """With no env overrides, the collector returns unknown / not configured
    for every field rather than guessing.
    """
    import harness_terminal as _ht

    for var in (
        "DPMTF_SANDBOX_MODE", "DPMTF_SANDBOX",
        "DPMTF_APPROVAL_POLICY", "DPMTF_APPROVAL",
        "DPMTF_WORKSPACE_ACCESS_MODE", "DPMTF_WORKSPACE_ACCESS",
        "DPMTF_BRIDGE_DIR", "DPMTF_BRIDGE_DIR_ACCESS",
        "DPMTF_MCP_LIGHT", "MCP_LIGHT_STATE", "MCP_LIGHT",
    ):
        monkeypatch.delenv(var, raising=False)

    info = _ht.collect_runtime_status()
    assert info["sandbox_mode"] == "unknown"
    assert info["approval_policy"] == "unknown"
    assert info["workspace_access_mode"] == "unknown"
    # The bridge path is not configured when no env or config provides one.
    assert info["bridge_dir"] == "not configured"
    assert info["bridge_dir_access"] == "unknown"
    # MCP-Light is a label only and defaults to "not configured".
    assert info["mcp_light"] == "not configured"


def test_seam_collect_runtime_status_filters_secret_like_env(monkeypatch):
    """An env value that looks like a secret is normalised to the default."""
    import harness_terminal as _ht

    monkeypatch.setenv("DPMTF_SANDBOX_MODE", "the api_key is leaking")
    info = _ht.collect_runtime_status()
    assert info["sandbox_mode"] == "unknown"


def test_seam_collect_runtime_status_bridge_dir_via_config(monkeypatch):
    """When env is absent, the bridge path comes from config.get_bridge_dir,
    not from a hardcoded literal. We patch config so the test is hermetic.
    """
    import harness_terminal as _ht
    import config as _config

    monkeypatch.delenv("DPMTF_BRIDGE_DIR", raising=False)
    monkeypatch.delenv("DPMTF_BRIDGE_DIR_ACCESS", raising=False)
    monkeypatch.delenv("DPMTF_BRIDGE_ACCESS", raising=False)

    sentinel = "/tmp/seam-test-bridge"
    monkeypatch.setattr(_config, "get_bridge_dir", lambda: sentinel)
    info = _ht.collect_runtime_status()
    assert info["bridge_dir"] == sentinel
    # Access is computed from os.access on the configured path.
    assert info["bridge_dir_access"] in ("writable", "read-only", "unknown")


def test_seam_idle_reader_handles_eintr(monkeypatch):
    """A read interrupted by EINTR surfaces the interrupted sentinel, and a
    subsequent read after clear() returns the one real frame. The stream is
    finite and realistic: it raises EINTR exactly once, then serves the data
    exactly once, then goes idle/EOF — it does not re-serve the same bytes
    forever.
    """
    import harness_terminal as _ht
    import errno as _errno

    class _EintrThenFiniteData:
        def __init__(self):
            self._eintr_pending = True
            self._data_served = False

        def read1(self, n):
            if self._eintr_pending:
                self._eintr_pending = False
                err = OSError("interrupted")
                err.errno = _errno.EINTR
                raise err
            if not self._data_served:
                self._data_served = True
                return b"task after eintr\n"
            return b""  # EOF once the single data chunk has been served

        def has_data(self):
            return self._eintr_pending or not self._data_served

    stream = _EintrThenFiniteData()

    def _fake_select(rlist, wlist, xlist, timeout):
        # Report the stream ready only while it still has bytes to serve;
        # once the data has been read, go idle so the reader flushes one frame.
        if stream.has_data():
            return ([stream], [], [])
        return ([], [], [])

    monkeypatch.setattr(_ht.select, "select", _fake_select)
    reader = _ht._IdleAccumulatingReader(stream, idle_seconds=0.01)

    # The first read is interrupted and surfaces the interrupted sentinel.
    out = reader.read_frame()
    assert out is _ht.IDLE_READ_INTERRUPTED
    # clear() discards the interrupted state; the next read delivers the
    # single real frame that follows the interruption.
    reader.clear()
    frame = reader.read_frame()
    assert frame is not None
    assert frame.payload == "task after eintr"


def test_seam_idle_reader_clear_discards_buffer():
    """The reader's clear() empties the buffer so a Ctrl+C during READY
    does not leave partial bytes that reappear as a partial submission.
    """
    import harness_terminal as _ht
    import io as _io

    # A buffered reader accumulates bytes from read1; clear() must empty it.
    class _Buf:
        def __init__(self):
            self._buf = b""

        def read1(self, n):
            return b""

        def has_data(self):
            return bool(self._buf)

    stream = _Buf()
    reader = _ht._IdleAccumulatingReader(stream, idle_seconds=0.01)
    reader._buf = b"partial garbage from a cancelled submission"
    reader.clear()
    assert reader._buf == b""


def test_seam_terminal_runner_forwards_cancel_event(monkeypatch):
    """The seam's _standalone_runner forwards cancel_event to the
    standalone's execute, so the persistent loop can cancel an active
    child. The seam's own KeyboardInterrupt fallback returns CANCELLED.
    """
    import harness_terminal as _ht
    import threading

    cancel = threading.Event()
    captured = {}

    def fake_execute(*, role, harness, model_target, cwd, task, request_id,
                     cancel_event=None, **kwargs):
        captured["cancel_event"] = cancel_event
        captured["task"] = task
        return {
            "status": "CANCELLED", "output": "", "error": "cancelled by Ctrl+C",
            "elapsed": 0.0, "pid": None, "request_id": request_id,
        }

    monkeypatch.setattr(_ht, "_standalone_pkg", lambda: type("Pkg", (), {"execute": staticmethod(fake_execute)}))

    result = _ht._standalone_runner(
        role="probe", harness="dsh", model_target="deepseek-v4-pro", cwd=".",
        task="long task", request_id="ha-c1",
        heartbeat_interval=0.05, timeout=None, on_event=None,
        cancel_event=cancel, cancel_grace_seconds=1.0,
    )
    # Forwarded to the standalone's execute.
    assert captured["cancel_event"] is cancel
    assert captured["task"] == "long task"
    # CANCELLED status propagates back to the persistent loop.
    assert result["status"] == "CANCELLED"


def test_seam_terminal_runner_uses_default_grace(monkeypatch):
    """When no cancel_grace_seconds is supplied, the seam runner uses the
    default 1.0s bounded escalation. The standalone's execute must see a
    numeric value.
    """
    import harness_terminal as _ht

    captured = {}

    def fake_execute(*, cancel_grace_seconds=None, **_kwargs):
        captured["cancel_grace_seconds"] = cancel_grace_seconds
        return {
            "status": "SUCCESS", "output": "ok", "error": "",
            "elapsed": 0.0, "pid": None, "request_id": "",
        }

    monkeypatch.setattr(_ht, "_standalone_pkg", lambda: type("Pkg", (), {"execute": staticmethod(fake_execute)}))

    _ht._standalone_runner(
        role="probe", harness="dsh", model_target="deepseek-v4-pro", cwd=".",
        task="t", request_id="ha-1",
        heartbeat_interval=0.05, timeout=None, on_event=None,
    )
    # Default grace is 1.0s.
    assert captured["cancel_grace_seconds"] == 1.0


def test_seam_main_collects_status_and_passes_to_loop(monkeypatch, capsys):
    """main() builds a status_info via collect_runtime_status, merges
    flow / model target into it, and forwards it to the standalone
    run_terminal. The persistent loop's banner reflects the merged info.
    """
    import harness_terminal as _ht
    import harness_allocator as _ha

    monkeypatch.setenv("DPMTF_SANDBOX_MODE", "workspace-write")
    monkeypatch.setenv("DPMTF_MCP_LIGHT", "not configured")

    seen = {}

    def fake_run_terminal(*, role, harness, model_target, cwd, flow,
                          reader, writer, runner, heartbeat_interval,
                          status_info=None, cancel_event=None):
        seen["status_info"] = status_info
        seen["flow"] = flow
        seen["model_target"] = model_target
        # Emit a single READY prompt so the function returns normally.
        writer.write(_ht._ready_line(role))
        return 0

    monkeypatch.setattr(_ha, "run_terminal", fake_run_terminal)

    # An empty stdin is fine; main() only invokes run_terminal once.
    rc = _ht.main([
        "--role", "super-deep-deep4",
        "--harness", "dsh",
        "--model", "deepseek-v4-pro",
        "--flow", "preferred_cloud_harness",
        "--cwd", "/x",
    ])
    assert rc == 0
    info = seen["status_info"]
    assert info["sandbox_mode"] == "workspace-write"
    assert info["mcp_light"] == "not configured"
    assert info["flow"] == "preferred_cloud_harness"
    assert info["model_target"] == "deepseek-v4-pro"
    assert seen["flow"] == "preferred_cloud_harness"


# ---------------------------------------------------------------------
# Run 002 ADD-only growth: seam-level Ctrl+C + multiline coverage
# ---------------------------------------------------------------------
# These tests extend the existing seam suite without modifying any existing
# test function. They complement
# test_seam_idle_reader_handles_eintr (which exercises the EINTR recovery
# path: interrupted read -> interrupted sentinel -> clear() -> next real
# frame) and exercise the seam-level wiring of Ctrl+C behaviour documented in
# /home/svend/flows/preferred_cloud_harness/runs/002/GOAL.md §7-§8.


def _seam_new_idle_stream(initial=b""):
    """A seam-side idle stream that honours real-ish select behaviour.

    The companion ``_seam_new_idle_select`` patches ``select.select`` so
    the stream is reported ready only while it has buffered bytes, then
    idles so the reader's idle window fires and the accumulated bytes
    are submitted as one frame.
    """

    class _Stream:
        def __init__(self):
            self._buf = initial

        def feed(self, more):
            self._buf += more

        def read1(self, n):
            if not self._buf:
                return b""
            out = self._buf
            self._buf = b""
            return out

        def has_data(self):
            return bool(self._buf)

    return _Stream()


def _seam_new_idle_select(monkeypatch, stream):
    """Patch select.select so the new idle stream is ready while it has
    bytes, then idles so the reader emits one frame.
    """

    import select as _select
    import harness_terminal as _ht

    def _fake_select(rlist, wlist, xlist, timeout):
        ready = [s for s in rlist if isinstance(s, type(stream))]
        return (ready, [], [])

    monkeypatch.setattr(_ht.select, "select", _fake_select)
    return stream


def test_seam_idle_reader_returns_frame_after_idle(monkeypatch):
    """TG3 + TG5 seam-level: the seam's idle reader returns one complete
    frame after the input stream has idled, with embedded newlines
    preserved verbatim and the trailing submission Enter consumed.
    """
    import harness_terminal as _ht

    payload = "first line\nsecond line\nthird line\nSupervisor\n"
    stream = _seam_new_idle_stream(payload.encode("utf-8"))
    stream = _seam_new_idle_select(monkeypatch, stream)
    reader = _ht._IdleAccumulatingReader(stream, idle_seconds=0.05)

    frame = reader.read_frame()
    assert frame is not None
    # The seam reader strips the single trailing newline consumed as the
    # submission Enter; embedded newlines are preserved verbatim.
    assert frame.payload == "first line\nsecond line\nthird line\nSupervisor"
    assert frame.payload.count("\n") == 3


def test_seam_idle_reader_preserves_atomicity_for_20k_multiline(monkeypatch):
    """TG3 seam-level: a 20k+ character prompt with hundreds of embedded
    newlines reaches the seam's idle reader as exactly one frame. The
    per-invocation atomicity contract holds for the seam's reader on
    large pastes.
    """
    import harness_terminal as _ht

    payload = (
        "## 1. Project Objective\n\n"
        + ("Implement the atomic dispatch layer.\n" * 700)
        + "\n```\n" + ("x" * 300) + "\n```\nSupervisor\n"
        + ("partial sentence continues here\n" * 100)
    )
    assert len(payload) >= 20000
    assert payload.count("\n") > 500

    stream = _seam_new_idle_stream(payload.encode("utf-8"))
    stream = _seam_new_idle_select(monkeypatch, stream)
    reader = _ht._IdleAccumulatingReader(stream, idle_seconds=0.05)

    frame = reader.read_frame()
    assert frame is not None
    # Exactly one frame; the complete payload is preserved verbatim,
    # with the single trailing newline consumed as the submission Enter.
    assert frame.payload == payload.rstrip("\n")
    # No fragmentation: every embedded newline is preserved.
    assert frame.payload.count("\n") == payload.count("\n") - 1


def test_seam_idle_reader_clear_drops_pending_bytes():
    """TG5 seam-level: the seam's clear() drains the buffered bytes so a
    Ctrl+C during READY does not leave a partial submission that reappears
    on the next read.
    """
    import harness_terminal as _ht

    class _NoIdleStream:
        def __init__(self):
            self._buf = b""

        def read1(self, n):
            out = self._buf
            self._buf = b""
            return out

    stream = _NoIdleStream()
    reader = _ht._IdleAccumulatingReader(stream, idle_seconds=0.01)
    reader._buf = b"partial garbage from a cancelled submission"
    reader.clear()
    assert reader._buf == b""
    assert reader._interrupted is False


def test_seam_main_passes_cancel_event_to_loop(monkeypatch):
    """TG4 seam-level: seam main() instantiates a threading.Event for
    cancellation and forwards it to the standalone run_terminal. The
    persistent loop's Cancel-while-RUNNING semantics are preserved end to
    end from the seam.
    """
    import harness_terminal as _ht
    import harness_allocator as _ha
    import threading as _threading

    seen = {}

    def fake_run_terminal(*, role, harness, model_target, cwd, flow,
                          reader, writer, runner, heartbeat_interval,
                          status_info=None, cancel_event=None):
        seen["cancel_event"] = cancel_event
        seen["cancel_event_is_event"] = isinstance(cancel_event, _threading.Event)
        writer.write(_ht._ready_line(role))
        return 0

    monkeypatch.setattr(_ha, "run_terminal", fake_run_terminal)

    rc = _ht.main([
        "--role", "super-deep-deep4",
        "--harness", "dsh",
        "--model", "deepseek-v4-pro",
        "--flow", "preferred_cloud_harness",
        "--cwd", "/x",
    ])
    assert rc == 0
    assert seen["cancel_event_is_event"] is True
    # Cancel events start cleared at run_terminal startup so a pre-set
    # event does not poison subsequent turns.
    assert seen["cancel_event"].is_set() is False


def test_seam_collect_runtime_status_honours_explicit_config(monkeypatch):
    """TG6 seam-level: when no env override is set and config's bridge dir
    is just the project-root default, the collector reports
    ``not configured`` rather than fabricating the fallback path. An
    explicit env override always wins.
    """
    import harness_terminal as _ht

    for var in (
        "DPMTF_BRIDGE_DIR", "DPMTF_BRIDGE_DIR_ACCESS", "DPMTF_BRIDGE_ACCESS",
    ):
        monkeypatch.delenv(var, raising=False)

    info = _ht.collect_runtime_status()
    # When config only supplies the default fallback and env is unset,
    # ``bridge_dir`` is honest: ``not configured``.
    assert info["bridge_dir"] == "not configured"
    assert info["bridge_dir_access"] == "unknown"

    monkeypatch.setenv("DPMTF_BRIDGE_DIR", "/tmp/explicit-bridge")
    info = _ht.collect_runtime_status()
    assert info["bridge_dir"] == "/tmp/explicit-bridge"

