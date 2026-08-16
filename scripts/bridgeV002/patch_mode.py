"""Deterministic Patcher: resolution helper for `implementation_mode`.

Spec sections 41-42 define the configuration principle for the
Deterministic Patcher: opt-in, global default 'direct', with a
precedence chain that allows gradual adoption. The chain is

    role > step > flow > global default 'direct'

The first non-NULL value in (role_row, step_row, flow_row) wins; if
all three are NULL or the rows are missing, the resolver returns the
global default 'direct'.

This module is the database-side reader. It owns no business logic
beyond the precedence walk; it does not import config, does not
hardcode paths, and emits the offending table and key when it
encounters a stored value it cannot accept.

Allowed stored values: 'direct', 'deterministic_patch'. NULL and an
empty string both mean "inherit from the next level" — the same
convention used elsewhere in the bridge schema for unset columns
(tests/test_flow_target_project.py is the precedent). Anything else
raises ValueError naming the table and the identifying key, so the
configurator can fix the row without ambiguity.

Spec section 26 defines the instruction block injected into an
implementation role's prompt when the resolved mode is
'deterministic_patch'. The block is a plain-text section that
constrains the role to use the patcher instead of editing files
directly. The block lives here (rather than in dispatch.py) so the
unit-test surface stays in one module, the wording cannot drift from
the resolver, and backward compatibility (spec §5) is a property of
this file rather than of the dispatcher that calls into it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


DEFAULT_MODE = "direct"
ALLOWED_MODES = frozenset({"direct", "deterministic_patch"})


PATCH_MODE_BLOCK = """\
<implementation_mode>deterministic_patch</implementation_mode>

You are operating under the Deterministic Patcher mode. Follow these
rules — they are part of your governance:

1. Do not directly modify repository files when the requested change
   can be performed through the Deterministic Patcher.
2. Prefer structural_python operations for supported Python
   transformations.
3. Use unified_diff when the change cannot be represented with
   available structural operations.
4. Never manually repair a rejected patch outside the normal DPMtF
   execution flow — return control through the flow.

The governance that defines this mode and the boundary between the
LLM and the Patcher is at
docs/governance-templates-v2/102_DETERMINISTIC_PATCH_MODE.md
(referenced by path). If that path is not readable from your working
directory, or you need the PatchRequest format, fetch them through
mcp-light when your session has it configured:
get_governance_file("102_DETERMINISTIC_PATCH_MODE.md") and
get_patcher_usage().
"""


def _is_set(value: Optional[str]) -> bool:
    """A stored value counts as set when it is not None and not blank.

    Treating blank strings as NULL mirrors the existing bridge
    convention: the UI persists empty fields for "unset", and the
    resolver must not silently promote them to a real mode.
    """
    return value is not None and value.strip() != ""


def _validate(value: str, table: str, key: str) -> str:
    """Raise ValueError on anything outside ALLOWED_MODES; return value."""
    if value not in ALLOWED_MODES:
        raise ValueError(
            f"invalid implementation_mode {value!r} in {table} "
            f"(key={key!r}); allowed: {sorted(ALLOWED_MODES)}"
        )
    return value


def _read_role(
    conn: sqlite3.Connection, role_key: str
) -> Optional[str]:
    row = conn.execute(
        "SELECT implementation_mode FROM bridge_roles WHERE role_key = ?",
        (role_key,),
    ).fetchone()
    if row is None:
        return None
    value = row[0]
    if _is_set(value):
        return _validate(value, "bridge_roles", role_key)
    return None


def _read_step(
    conn: sqlite3.Connection, flow_key: str, step_key: str
) -> Optional[str]:
    row = conn.execute(
        """
        SELECT implementation_mode FROM bridge_flow_steps
        WHERE flow_key = ? AND step_key = ?
        """,
        (flow_key, step_key),
    ).fetchone()
    if row is None:
        return None
    value = row[0]
    if _is_set(value):
        return _validate(value, "bridge_flow_steps", f"{flow_key}/{step_key}")
    return None


def _read_flow(
    conn: sqlite3.Connection, flow_key: str
) -> Optional[str]:
    row = conn.execute(
        "SELECT implementation_mode FROM bridge_flows WHERE flow_key = ?",
        (flow_key,),
    ).fetchone()
    if row is None:
        return None
    value = row[0]
    if _is_set(value):
        return _validate(value, "bridge_flows", flow_key)
    return None


def resolve_implementation_mode(
    db_path: str | Path,
    flow_key: str,
    step_key: Optional[str] = None,
    role_key: Optional[str] = None,
) -> str:
    """Return the effective implementation_mode for the given chain.

    Walks role -> step -> flow, returning the first non-NULL value
    found. Falls back to the global default (DEFAULT_MODE = 'direct')
    when no level sets a value.

    Args:
        db_path: Path to the DPMtF SQLite database. Resolved via
            sqlite3.connect, so strings and Path objects are both
            accepted.
        flow_key: The flow to resolve against. Required.
        step_key: Optional step within the flow. When None, the step
            level is skipped entirely — first non-NULL is taken from
            (role, flow, default).
        role_key: Optional role. When None, the role level is skipped
            entirely. When supplied with no matching row, the level
            is treated as NULL and the chain falls through.

    Returns:
        One of 'direct' or 'deterministic_patch'.

    Raises:
        ValueError: A stored value is outside the allowed set. The
            message names the table and the key (role_key for
            bridge_roles, "flow_key/step_key" for bridge_flow_steps,
            flow_key for bridge_flows) so the operator can fix the
            offending row without reading the resolver.
    """
    with sqlite3.connect(str(db_path)) as conn:
        if role_key is not None:
            value = _read_role(conn, role_key)
            if value is not None:
                return value
        if step_key is not None:
            value = _read_step(conn, flow_key, step_key)
            if value is not None:
                return value
        value = _read_flow(conn, flow_key)
        if value is not None:
            return value
    return DEFAULT_MODE


def apply_mode_block(
    prompt_text: str,
    db_path: str | Path,
    flow_key: str,
    step_key: Optional[str] = None,
    role_key: Optional[str] = None,
) -> str:
    """Return the prompt with the §26 block appended when patch mode is on.

    Spec §5 demands backward compatibility: when no flow is opted in,
    or a flow is explicitly 'direct', the dispatched prompt must be
    byte-identical to today's behavior. To prove that, this function
    returns the *same* string object (no strip, no normalization, no
    trailing newline added) whenever the resolved mode is anything
    other than 'deterministic_patch'.

    Pre-migration 052 databases do not have the
    `implementation_mode` columns, so resolving the mode raises
    sqlite3.OperationalError. Spec §5 also covers that: a pre-052 DB
    must resolve to today's behavior, never crash dispatch. We catch
    the OperationalError specifically — anything else (e.g. a
    corrupt DB) keeps the original surfacing.

    A stored-but-invalid value still raises ValueError. An operator
    who configured the wrong row must see the error rather than
    have the dispatch silently fall through to today's behavior.

    Args:
        prompt_text: The already-composed prompt about to be injected
            into the target role's tmux session. Not modified unless
            the resolved mode is 'deterministic_patch'.
        db_path: Path to the DPMtF SQLite database.
        flow_key: The flow the dispatch belongs to.
        step_key: The step the dispatch targets (None skips step
            level).
        role_key: The receiving role's key (None skips role level).

    Returns:
        prompt_text with "\n\n" + PATCH_MODE_BLOCK appended when the
        resolved mode is 'deterministic_patch'. Otherwise prompt_text
        returned unchanged (same string object).
    """
    try:
        mode = resolve_implementation_mode(
            db_path, flow_key, step_key=step_key, role_key=role_key
        )
    except sqlite3.OperationalError as exc:
        if "implementation_mode" in str(exc):
            return prompt_text
        raise
    if mode == "deterministic_patch":
        return prompt_text + "\n\n" + PATCH_MODE_BLOCK
    return prompt_text
