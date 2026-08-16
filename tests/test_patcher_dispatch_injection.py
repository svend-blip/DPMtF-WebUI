"""Tests for the prompt-composition wiring of the Deterministic Patcher.

B1 (handoff 048, APPROVED) delivered the resolver
`scripts/bridgeV002/patch_mode.py:resolve_implementation_mode` and the
storage columns behind it. B2 (handoff 049, this file) wires the
resolver into dispatch: the function
`scripts/bridgeV002/patch_mode.py:apply_mode_block` appends the §26
instruction block to a composed prompt when the resolved mode is
'deterministic_patch', and returns the prompt byte-identical when it
isn't.

Spec §5 demands backward compatibility. The tests below prove it three
ways that the spec actually allows:

- exact string equality on a fixture with odd trailing whitespace,
  with the *identity* of the returned object also pinned so a future
  refactor cannot satisfy the equality test by normalizing the
  string;
- the production database, opened READ-ONLY with nothing opted in,
  still produces byte-identical passthrough for every role in
  preferred_cloud;
- a scratch DB built without migration 052 — i.e. the schema a
  pre-B1 production DB would have — produces byte-identical
  passthrough with no exception, covering spec §5's pre-migration
  clause.

The wiring test parses `scripts/bridgeV002/dispatch.py` with the
stdlib `ast` module and asserts both `run_flow_step_db` and
`signal_complete` contain a call to `apply_mode_block`. This pins the
bounded edit structurally: any future refactor that breaks the
wiring fails this test before a single prompt is injected.
"""

from __future__ import annotations

import ast
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

from patch_mode import (  # noqa: E402
    PATCH_MODE_BLOCK,
    apply_mode_block,
)


_REPO_ROOT = PROJECT_ROOT
_MIGRATION_PATH = _REPO_ROOT / "scripts" / "db" / "052_implementation_mode.sql"
_PRODUCTION_DB = _REPO_ROOT / "databases" / "dpmtf.db"
_DISPATCH_PATH = _REPO_ROOT / "scripts" / "bridgeV002" / "dispatch.py"


_BASE_SCHEMA = """
CREATE TABLE bridge_flows (
    flow_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    step_order TEXT,
    is_default INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    auto_complete_enabled INTEGER DEFAULT 0,
    use_machine_profile INTEGER DEFAULT 0,
    target_project_path TEXT DEFAULT NULL
);
CREATE TABLE bridge_flow_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_key TEXT NOT NULL,
    step_key TEXT NOT NULL,
    from_role TEXT NOT NULL,
    to_role TEXT NOT NULL,
    deliverable_dir TEXT,
    deliverable_pattern TEXT,
    pre_dispatch_script TEXT,
    post_dispatch_script TEXT,
    error_msg TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    rule_key TEXT,
    auto_chain_to_next INTEGER DEFAULT 0,
    validation_required INTEGER DEFAULT 0,
    model_source TEXT,
    model_alias TEXT,
    UNIQUE(flow_key, step_key)
);
CREATE TABLE bridge_roles (
    role_key TEXT PRIMARY KEY,
    tmux_session TEXT NOT NULL,
    setup_script TEXT,
    teardown_script TEXT,
    deliver_error_msg TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    restart_policy TEXT DEFAULT 'none',
    governance_file TEXT,
    role_type TEXT DEFAULT 'agent',
    enter_command TEXT DEFAULT 'default',
    config_dir TEXT,
    primary_output_type TEXT,
    default_model_source TEXT,
    default_model_alias TEXT,
    trade_mcp_push_mode TEXT,
    max_output_tokens INTEGER,
    allocator_client TEXT DEFAULT 'opencode',
    fresh_session_command TEXT,
    workdir_mode TEXT NOT NULL DEFAULT 'target_project',
    execution_target TEXT
);
"""


def _build_scratch_db(tmp_path: Path, *, with_migration: bool) -> Path:
    """Build a minimal bridge schema, optionally with migration 052 applied."""
    db = tmp_path / "scratch.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(_BASE_SCHEMA)
        conn.commit()
        if with_migration:
            sql = _MIGRATION_PATH.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.commit()
    finally:
        conn.close()
    return db


def _seed_row(db: Path, table: str, columns: list[str], values: list) -> None:
    placeholders = ", ".join(["?"] * len(values))
    column_list = ", ".join(columns)
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
    finally:
        conn.close()


_ODD_PROMPT = (
    "Read and execute /tmp/flows/preferred_cloud/handoffs/048-handoff.md \n"
    "\n"
    "  trailing whitespace line above  \t \n"
    "\n"
    "## Final line with CRLF-style content."
)


class TestPassthroughByteIdentical:
    """With nothing opted in, the function must return the prompt
    unchanged — same string object, no normalization."""

    def test_empty_prompt_with_no_rows_is_passthrough(self, tmp_path):
        db = _build_scratch_db(tmp_path, with_migration=True)
        prompt = ""
        result = apply_mode_block(prompt, db, "preferred_cloud")
        assert result is prompt
        assert result == prompt

    def test_odd_whitespace_prompt_with_no_rows_is_passthrough(self, tmp_path):
        db = _build_scratch_db(tmp_path, with_migration=True)
        result = apply_mode_block(_ODD_PROMPT, db, "preferred_cloud")
        assert result is _ODD_PROMPT
        assert result == _ODD_PROMPT
        assert result == _ODD_PROMPT

    def test_direct_at_flow_level_is_passthrough(self, tmp_path):
        db = _build_scratch_db(tmp_path, with_migration=True)
        _seed_row(
            db, "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "direct"],
        )
        result = apply_mode_block(_ODD_PROMPT, db, "preferred_cloud")
        assert result is _ODD_PROMPT
        assert result == _ODD_PROMPT

    def test_direct_at_step_level_is_passthrough(self, tmp_path):
        db = _build_scratch_db(tmp_path, with_migration=True)
        _seed_row(
            db, "bridge_flow_steps",
            ["flow_key", "step_key", "from_role", "to_role", "implementation_mode"],
            ["preferred_cloud", "step_a", "Pre-super-cl", "Pre-imple-cl", "direct"],
        )
        result = apply_mode_block(
            _ODD_PROMPT, db, "preferred_cloud",
            step_key="step_a", role_key="Pre-imple-cl",
        )
        assert result is _ODD_PROMPT
        assert result == _ODD_PROMPT

    def test_direct_at_role_level_is_passthrough(self, tmp_path):
        db = _build_scratch_db(tmp_path, with_migration=True)
        _seed_row(
            db, "bridge_roles",
            ["role_key", "tmux_session", "implementation_mode"],
            ["Pre-imple-cl", "pre_imple_cl_session", "direct"],
        )
        result = apply_mode_block(
            _ODD_PROMPT, db, "preferred_cloud",
            step_key="step_a", role_key="Pre-imple-cl",
        )
        assert result is _ODD_PROMPT
        assert result == _ODD_PROMPT

    def test_direct_at_all_three_levels_is_passthrough(self, tmp_path):
        db = _build_scratch_db(tmp_path, with_migration=True)
        _seed_row(
            db, "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "direct"],
        )
        _seed_row(
            db, "bridge_flow_steps",
            ["flow_key", "step_key", "from_role", "to_role", "implementation_mode"],
            ["preferred_cloud", "step_a", "Pre-super-cl", "Pre-imple-cl", "direct"],
        )
        _seed_row(
            db, "bridge_roles",
            ["role_key", "tmux_session", "implementation_mode"],
            ["Pre-imple-cl", "pre_imple_cl_session", "direct"],
        )
        result = apply_mode_block(
            _ODD_PROMPT, db, "preferred_cloud",
            step_key="step_a", role_key="Pre-imple-cl",
        )
        assert result is _ODD_PROMPT
        assert result == _ODD_PROMPT


class TestBlockPresent:
    """With 'deterministic_patch' set at any level that wins, the §26
    block must be appended and the original prompt must remain the
    prefix unchanged."""

    def test_flow_level_appends_block(self, tmp_path):
        db = _build_scratch_db(tmp_path, with_migration=True)
        _seed_row(
            db, "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "deterministic_patch"],
        )
        result = apply_mode_block(_ODD_PROMPT, db, "preferred_cloud")
        assert result.startswith(_ODD_PROMPT)
        assert PATCH_MODE_BLOCK in result
        assert result.endswith(PATCH_MODE_BLOCK)

    def test_step_level_appends_block(self, tmp_path):
        db = _build_scratch_db(tmp_path, with_migration=True)
        _seed_row(
            db, "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "direct"],
        )
        _seed_row(
            db, "bridge_flow_steps",
            ["flow_key", "step_key", "from_role", "to_role", "implementation_mode"],
            [
                "preferred_cloud", "step_a", "Pre-super-cl", "Pre-imple-cl",
                "deterministic_patch",
            ],
        )
        result = apply_mode_block(
            _ODD_PROMPT, db, "preferred_cloud",
            step_key="step_a", role_key="Pre-imple-cl",
        )
        assert result.startswith(_ODD_PROMPT)
        assert PATCH_MODE_BLOCK in result

    def test_role_level_appends_block(self, tmp_path):
        db = _build_scratch_db(tmp_path, with_migration=True)
        _seed_row(
            db, "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "direct"],
        )
        _seed_row(
            db, "bridge_flow_steps",
            ["flow_key", "step_key", "from_role", "to_role", "implementation_mode"],
            ["preferred_cloud", "step_a", "Pre-super-cl", "Pre-imple-cl", "direct"],
        )
        _seed_row(
            db, "bridge_roles",
            ["role_key", "tmux_session", "implementation_mode"],
            ["Pre-imple-cl", "pre_imple_cl_session", "deterministic_patch"],
        )
        result = apply_mode_block(
            _ODD_PROMPT, db, "preferred_cloud",
            step_key="step_a", role_key="Pre-imple-cl",
        )
        assert result.startswith(_ODD_PROMPT)
        assert PATCH_MODE_BLOCK in result

    def test_block_marker_present_in_block(self):
        """The block must open with the explicit marker the spec uses
        to detect that the mode is on."""
        assert PATCH_MODE_BLOCK.startswith(
            "<implementation_mode>deterministic_patch</implementation_mode>"
        )


class TestPrecedenceThroughBlock:
    """Precedence (role > step > flow) must still hold through the
    block path. A 'direct' role over a 'deterministic_patch' step
    must yield byte-identical passthrough."""

    def test_role_direct_overrides_step_deterministic_patch(self, tmp_path):
        db = _build_scratch_db(tmp_path, with_migration=True)
        _seed_row(
            db, "bridge_flow_steps",
            ["flow_key", "step_key", "from_role", "to_role", "implementation_mode"],
            [
                "preferred_cloud", "step_a", "Pre-super-cl", "Pre-imple-cl",
                "deterministic_patch",
            ],
        )
        _seed_row(
            db, "bridge_roles",
            ["role_key", "tmux_session", "implementation_mode"],
            ["Pre-imple-cl", "pre_imple_cl_session", "direct"],
        )
        result = apply_mode_block(
            _ODD_PROMPT, db, "preferred_cloud",
            step_key="step_a", role_key="Pre-imple-cl",
        )
        assert result is _ODD_PROMPT
        assert result == _ODD_PROMPT


class TestPreMigrationDb:
    """A database without migration 052 has no implementation_mode
    columns; the resolver must not crash, and dispatch must produce
    byte-identical passthrough."""

    def test_pre_052_db_passes_through_unchanged(self, tmp_path):
        db = _build_scratch_db(tmp_path, with_migration=False)
        result = apply_mode_block(
            _ODD_PROMPT, db, "preferred_cloud",
            step_key="step_a", role_key="Pre-imple-cl",
        )
        assert result is _ODD_PROMPT
        assert result == _ODD_PROMPT

    def test_pre_052_db_with_rows_passes_through_unchanged(self, tmp_path):
        """Even with a row that LOOKS like it could opt in (but
        cannot be read without the column), passthrough holds."""
        db = _build_scratch_db(tmp_path, with_migration=False)
        _seed_row(
            db, "bridge_flows",
            ["flow_key", "name"],
            ["preferred_cloud", "Preferred Cloud"],
        )
        _seed_row(
            db, "bridge_flow_steps",
            ["flow_key", "step_key", "from_role", "to_role"],
            ["preferred_cloud", "step_a", "Pre-super-cl", "Pre-imple-cl"],
        )
        _seed_row(
            db, "bridge_roles",
            ["role_key", "tmux_session"],
            ["Pre-imple-cl", "pre_imple_cl_session"],
        )
        result = apply_mode_block(
            _ODD_PROMPT, db, "preferred_cloud",
            step_key="step_a", role_key="Pre-imple-cl",
        )
        assert result is _ODD_PROMPT
        assert result == _ODD_PROMPT


class TestInvalidValueRaises:
    """A configured-but-wrong value must surface — never silently
    fall through to today's behavior."""

    def test_invalid_at_flow_level_raises_through_apply_mode_block(self, tmp_path):
        db = _build_scratch_db(tmp_path, with_migration=True)
        _seed_row(
            db, "bridge_flows",
            ["flow_key", "name", "implementation_mode"],
            ["preferred_cloud", "Preferred Cloud", "patcher_v3"],
        )
        with pytest.raises(ValueError) as exc:
            apply_mode_block(_ODD_PROMPT, db, "preferred_cloud")
        assert "patcher_v3" in str(exc.value)
        assert "preferred_cloud" in str(exc.value)

    def test_invalid_at_role_level_raises_through_apply_mode_block(self, tmp_path):
        db = _build_scratch_db(tmp_path, with_migration=True)
        _seed_row(
            db, "bridge_roles",
            ["role_key", "tmux_session", "implementation_mode"],
            ["Pre-imple-cl", "pre_imple_cl_session", "manual_edit"],
        )
        with pytest.raises(ValueError) as exc:
            apply_mode_block(
                _ODD_PROMPT, db, "preferred_cloud",
                step_key="step_a", role_key="Pre-imple-cl",
            )
        assert "manual_edit" in str(exc.value)


class TestDispatchWiring:
    """The bounded edit must structurally call apply_mode_block in
    both composition functions. Parsed with stdlib ast so the wiring
    is asserted without executing dispatch.py against the live flow."""

    @staticmethod
    def _function_bodies() -> dict[str, ast.AST]:
        source = _DISPATCH_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(_DISPATCH_PATH))
        bodies: dict[str, ast.AST] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                bodies[node.name] = node
        return bodies

    @staticmethod
    def _find_apply_mode_block_call(fn: ast.AST) -> ast.Call:
        """Return the apply_mode_block Call node inside fn.

        Raises AssertionError if no such call exists — the bounded
        edit is gone.
        """
        for sub in ast.walk(fn):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Name)
                and sub.func.id == "apply_mode_block"
            ):
                return sub
        raise AssertionError(
            "apply_mode_block is not called inside this function — "
            "the B2 wiring is gone. Re-add the bounded edit."
        )

    @staticmethod
    def _resolve_arg(call: ast.Call, *, positional_index: int, keyword: str):
        """Return the AST node for the requested argument, or None.

        Checks the keyword form first (call.kwarg where .arg == keyword),
        then falls back to the positional slot at positional_index.
        """
        for kw in call.keywords:
            if kw.arg == keyword:
                return kw.value
        if positional_index < len(call.args):
            return call.args[positional_index]
        return None

    @staticmethod
    def _assert_payload_subscript(
        arg_node, expected_key: str, *, site: str, argument_name: str
    ) -> None:
        """Assert arg_node is the AST shape `payload[<expected_key>]`.

        Fails on ast.Name (the original defect at signal_complete), on
        ast.Constant (a hardcoded None or string), on a different
        subscript target, or anything else — exactly the contrast the
        verdict on 049 called out.
        """
        assert isinstance(arg_node, ast.Subscript), (
            f"{site}: {argument_name} must be payload[{expected_key!r}] "
            f"(ast.Subscript); got {type(arg_node).__name__}. "
            "The original defect bound a bare function parameter here, "
            "which silently resolves mode with step_key=None under the "
            "governance-mandated --signal-complete invocation."
        )
        assert isinstance(arg_node.value, ast.Name), (
            f"{site}: {argument_name} subscript value must be the name "
            f"'payload'; got {type(arg_node.value).__name__}"
        )
        assert arg_node.value.id == "payload", (
            f"{site}: {argument_name} subscript value must be 'payload'; "
            f"got {arg_node.value.id!r}"
        )
        slice_node = arg_node.slice
        assert isinstance(slice_node, ast.Constant), (
            f"{site}: {argument_name} subscript slice must be a constant "
            f"string; got {type(slice_node).__name__}"
        )
        assert slice_node.value == expected_key, (
            f"{site}: {argument_name} subscript slice must be "
            f"{expected_key!r}; got {slice_node.value!r}"
        )

    def test_both_target_functions_are_present(self):
        bodies = self._function_bodies()
        assert "run_flow_step_db" in bodies
        assert "signal_complete" in bodies

    def test_run_flow_step_db_calls_apply_mode_block(self):
        bodies = self._function_bodies()
        fn = bodies["run_flow_step_db"]

        called = False
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Name) and func.id == "apply_mode_block":
                    called = True
                    break
        assert called, (
            "run_flow_step_db no longer calls apply_mode_block — the "
            "B2 wiring is gone. Re-add the bounded edit."
        )

    def test_signal_complete_calls_apply_mode_block(self):
        bodies = self._function_bodies()
        fn = bodies["signal_complete"]

        called = False
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Name) and func.id == "apply_mode_block":
                    called = True
                    break
        assert called, (
            "signal_complete no longer calls apply_mode_block — the "
            "B2 wiring is gone. Re-add the bounded edit."
        )

    def test_run_flow_step_db_binds_payload_step_key_and_to_role(self):
        """The step_key argument (4th positional OR keyword) must be
        payload["step_key"], and the role_key argument (5th positional
        OR keyword) must be payload["to_role"]. Any other shape —
        ast.Name (the old defect), ast.Constant (a hardcoded None),
        a different subscript — fails this test.
        """
        bodies = self._function_bodies()
        call = self._find_apply_mode_block_call(bodies["run_flow_step_db"])

        step_arg = self._resolve_arg(
            call, positional_index=3, keyword="step_key"
        )
        assert step_arg is not None, (
            "run_flow_step_db: apply_mode_block call is missing its "
            "step_key argument (4th positional or keyword)."
        )
        self._assert_payload_subscript(
            step_arg, "step_key",
            site="run_flow_step_db", argument_name="step_key",
        )

        role_arg = self._resolve_arg(
            call, positional_index=4, keyword="role_key"
        )
        assert role_arg is not None, (
            "run_flow_step_db: apply_mode_block call is missing its "
            "role_key argument (5th positional or keyword)."
        )
        self._assert_payload_subscript(
            role_arg, "to_role",
            site="run_flow_step_db", argument_name="role_key",
        )

    def test_signal_complete_binds_payload_step_key_and_to_role(self):
        """The same binding check at signal_complete. On 049 this was
        the defect: the bare `step_key` function parameter was passed
        instead of payload["step_key"]. Under the governance-mandated
        --signal-complete invocation (no --step-key), that bare
        parameter is None, so step-level implementation_mode rows were
        silently unreachable through the callback path.
        """
        bodies = self._function_bodies()
        call = self._find_apply_mode_block_call(bodies["signal_complete"])

        step_arg = self._resolve_arg(
            call, positional_index=3, keyword="step_key"
        )
        assert step_arg is not None, (
            "signal_complete: apply_mode_block call is missing its "
            "step_key argument (4th positional or keyword)."
        )
        self._assert_payload_subscript(
            step_arg, "step_key",
            site="signal_complete", argument_name="step_key",
        )

        role_arg = self._resolve_arg(
            call, positional_index=4, keyword="role_key"
        )
        assert role_arg is not None, (
            "signal_complete: apply_mode_block call is missing its "
            "role_key argument (5th positional or keyword)."
        )
        self._assert_payload_subscript(
            role_arg, "to_role",
            site="signal_complete", argument_name="role_key",
        )

    def test_signal_send_calls_apply_mode_block(self):
        """The third composition site, found LIVE on 2026-08-16.

        Run 018's B2 bound run_flow_step_db and signal_complete, but
        --signal-send composes and injects its own prompt in
        signal_send() — and that is the path an Architect's or the
        Human's handoff dispatch actually takes (preferred_cloud and
        pi_test both dispatch with --signal-send). The very first live
        opted-in dispatch (pi_test handoff 005) reached the implementer
        WITHOUT the section-26 block, and the implementer honestly
        reported it ABSENT. This test pins the site so the gap cannot
        reopen.
        """
        bodies = self._function_bodies()
        fn = bodies["signal_send"]

        called = False
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Name) and func.id == "apply_mode_block":
                    called = True
                    break
        assert called, (
            "signal_send no longer calls apply_mode_block — the third "
            "composition site is unwired. An opted-in flow's handoff "
            "dispatches would silently lose the section-26 block, which "
            "is exactly what pi_test handoff 005 demonstrated live."
        )

    def test_signal_send_binds_payload_step_key_and_to_role(self):
        """The same binding check at signal_send as at the other two
        sites: payload["step_key"] and payload["to_role"], never a bare
        function parameter or a constant.
        """
        bodies = self._function_bodies()
        call = self._find_apply_mode_block_call(bodies["signal_send"])

        step_arg = self._resolve_arg(
            call, positional_index=3, keyword="step_key"
        )
        assert step_arg is not None, (
            "signal_send: apply_mode_block call is missing its "
            "step_key argument (4th positional or keyword)."
        )
        self._assert_payload_subscript(
            step_arg, "step_key",
            site="signal_send", argument_name="step_key",
        )

        role_arg = self._resolve_arg(
            call, positional_index=4, keyword="role_key"
        )
        assert role_arg is not None, (
            "signal_send: apply_mode_block call is missing its "
            "role_key argument (5th positional or keyword)."
        )
        self._assert_payload_subscript(
            role_arg, "to_role",
            site="signal_send", argument_name="role_key",
        )


class TestBlockSurvivesXmlStripping:
    """The block must survive the OpenCode/Pi injection path readable.

    inject_prompt deliberately runs _strip_xml_tags on every prompt
    bound for an opencode or pi session — qwen-class models see XML
    tags and hallucinate XML-style function calls. The function
    converts KNOWN tags to plain-text headers and deletes the rest.
    <implementation_mode> was not known, so the first live opted-in
    dispatches (pi_test 005/006) delivered the block with its tag line
    reduced to a bare 'deterministic_patch' — the four rules and the
    governance path survived, the mode framing did not. The implementer
    reported it honestly, both times.

    These tests pin the survival contract: after stripping, the mode
    line is still a readable statement, and nothing of the block's
    substance is lost.
    """

    @staticmethod
    def _stripped_block():
        import dispatch
        return dispatch._strip_xml_tags(PATCH_MODE_BLOCK)

    def test_mode_line_survives_as_readable_header(self):
        stripped = self._stripped_block()
        assert "Implementation Mode: deterministic_patch" in stripped, (
            "the <implementation_mode> tag line must strip to "
            "'Implementation Mode: deterministic_patch', not vanish — "
            "a bare 'deterministic_patch' header is what pi_test 005/006 "
            "received and reported as an absent block"
        )

    def test_no_orphaned_bare_mode_header_remains(self):
        import re
        stripped = self._stripped_block()
        assert not re.search(r"^deterministic_patch$", stripped, re.M), (
            "an orphaned bare 'deterministic_patch' line means the tag "
            "was deleted instead of converted"
        )

    def test_block_substance_survives_stripping(self):
        stripped = self._stripped_block()
        for needle in (
            "Deterministic Patcher mode",
            "structural_python",
            "unified_diff",
            "Never manually repair a rejected patch",
            "docs/governance-templates-v2/102_DETERMINISTIC_PATCH_MODE.md",
        ):
            assert needle in stripped, (
                f"block content {needle!r} lost in the injection strip"
            )


class TestStepLevelBindingContrast:
    """Behavioral contrast: with implementation_mode set at STEP level
    only, the same prompt + the same DB returns two different answers
    depending on whether step_key is None or the real step key.

    - step_key=None  → the step level is skipped entirely, the resolver
      falls through to (flow, default) and yields 'direct'. The block
      is NOT injected. This is exactly what the dispatch.py defect
      silently produced under the governance-mandated --signal-complete
      invocation.
    - step_key="step_a" → the step-level row is read, 'deterministic_patch'
      is resolved, and the §26 block is appended.

    Both assertions live in one test so the contrast is explicit.
    """

    def test_step_level_mode_passthrough_with_none_block_with_real_key(self, tmp_path):
        db = _build_scratch_db(tmp_path, with_migration=True)
        _seed_row(
            db, "bridge_flow_steps",
            ["flow_key", "step_key", "from_role", "to_role", "implementation_mode"],
            [
                "preferred_cloud", "step_a", "Pre-super-cl", "Pre-imple-cl",
                "deterministic_patch",
            ],
        )

        with_none = apply_mode_block(
            _ODD_PROMPT, db, "preferred_cloud",
            step_key=None, role_key="Pre-imple-cl",
        )
        with_key = apply_mode_block(
            _ODD_PROMPT, db, "preferred_cloud",
            step_key="step_a", role_key="Pre-imple-cl",
        )

        assert with_none is _ODD_PROMPT, (
            "step_key=None must skip step-level resolution and return "
            "the SAME string object — this is the defect's silent "
            "behavior under the governance-mandated --signal-complete "
            "invocation."
        )
        assert with_none == _ODD_PROMPT, (
            "step_key=None must produce byte-identical passthrough."
        )
        assert with_key.startswith(_ODD_PROMPT), (
            "with the real step key, the original prompt must remain "
            "the prefix of the result."
        )
        assert PATCH_MODE_BLOCK in with_key, (
            "with the real step key, the §26 block must be present in "
            "the result — this is the behavior the dispatch.py fix "
            "restores by binding payload['step_key']."
        )
        assert with_key.endswith(PATCH_MODE_BLOCK), (
            "with the real step key, the block must be the appended "
            "suffix (still preserving the original prompt as the prefix)."
        )


class TestProductionDbGuard:
    """Production DB read-only: nothing in preferred_cloud is opted
    in, so every role the flow dispatches to must produce
    byte-identical passthrough. If a future run opts in by accident,
    this test catches it before the dispatch prompt drifts."""

    def test_preferred_cloud_roles_produce_passthrough(self):
        if not _PRODUCTION_DB.exists():
            pytest.skip(
                f"production DB not present at {_PRODUCTION_DB} — skipping"
            )

        uri = f"file:{_PRODUCTION_DB}?mode=ro"
        try:
            conn = sqlite3.connect(uri, uri=True)
        except sqlite3.OperationalError as exc:
            pytest.skip(f"production DB not openable READ-ONLY ({exc})")

        try:
            for role_key in ("Pre-super-cl", "Pre-imple-cl", "Pre-review-cl"):
                cols = {
                    row[1]
                    for row in conn.execute(
                        "PRAGMA table_info(bridge_roles);"
                    ).fetchall()
                }
                if "implementation_mode" not in cols:
                    pytest.skip(
                        "bridge_roles has no implementation_mode column "
                        "yet — Step 5 not applied — skipping guard"
                    )
            for role_key in ("Pre-super-cl", "Pre-imple-cl", "Pre-review-cl"):
                result = apply_mode_block(
                    _ODD_PROMPT, _PRODUCTION_DB, "preferred_cloud",
                    step_key=None, role_key=role_key,
                )
                assert result is _ODD_PROMPT, (
                    f"production DB opted {role_key} into a mode — "
                    "dispatch will modify prompts until this is unset"
                )
                assert result == _ODD_PROMPT
        finally:
            conn.close()
