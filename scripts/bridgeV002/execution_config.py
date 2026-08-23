#!/usr/bin/env python3
"""Unified resolver for the step-key execution schema.

Spec sections 1-8, 15, 17 define the unified precedence
STEP -> ROLE DEFAULT -> SYSTEM/LEGACY for governance, model, and harness,
identically. Migration 062 (scripts/db/062_step_execution_config.sql)
adds the bound storage; this module is the single place the precedence
walk lives. Per GOAL.md section 2(b), implementation_mode is NOT
re-implemented here -- the existing patch_mode.resolve_implementation_mode
keeps its own precedence (role > step > flow > 'direct') and is delegated
to verbatim. Duplicating precedence logic would break TG10.

Public surface (GOAL.md section 2):

    resolve_execution_config(flow_key, step_key, db_path=None) -> dict
    resolve_for_receiver(flow_key, receiver_role, db_path=None) -> dict

Both functions open the DB read-only via sqlite3 and read the new
columns with dict(row).get(name) so a database predating migration 062
degrades to NULL/system rather than crashing (GOAL.md section 2(d)).
Pre-existing columns are read directly; their absence in a test fixture
is the test author's responsibility, not the resolver's.

The resolver returns exactly 13 keys (GOAL.md section 2), in any order:

    flow_key, step_key, from_role, to_role,
    governance_file, governance_source_level,
    model_source, model_alias, model_source_level,
    harness_source, harness_profile, harness_source_level,
    implementation_mode
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Mirror scripts/bridgeV002/bridge_lib.py lines 1-15: insert the project
# root onto sys.path so `import config` resolves. bridge_lib does this at
# module top-level so all submodules of bridgeV002 see the same config
# resolution path; we copy the pattern verbatim rather than importing
# bridge_lib (which would create a circular dependency between bridge_lib
# and the resolver for no benefit -- the resolver is meant to be the
# single precedence owner).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import config  # noqa: E402  (project-root import, see comment above)
from patch_mode import resolve_implementation_mode  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_set(value):
    """Return True when a stored value counts as set.

    "Set" means: not None AND the stripped string is non-empty. This
    mirrors patch_mode._is_set (the precedence walk for implementation_mode)
    and the bridge-wide convention that the UI persists empty fields for
    "unset", so the resolver must not silently promote an empty string
    to a real value. Treating blank strings as NULL keeps the migration
    062 contract: every existing row is NULL after the migration, so
    the new precedence walk behaves identically to the legacy direct
    column reads for every existing flow (zero behavior change, TG10).

    For model_source and harness_source, the literal "inherit_from_role"
    is also treated as unset (mirror bridge_lib.get_effective_model_source
    rule #15). Pass ``inherit_from_role`` here as ``value`` only when the
    caller wants that special treatment; governance_file has no such
    exception.
    """
    if value is None:
        return False
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if stripped == "":
        return False
    if stripped == "inherit_from_role":
        return False
    return True


def _step_row(conn, flow_key, step_key):
    """Load the bridge_flow_steps row for (flow_key, step_key).

    Returns a dict-like sqlite3.Row or None. The caller is responsible
    for raising when None -- a nonexistent step_key is a programmer
    error, not a silent default (GOAL.md section 2, spec section 16).
    """
    return conn.execute(
        "SELECT * FROM bridge_flow_steps WHERE flow_key = ? AND step_key = ?",
        (flow_key, step_key),
    ).fetchone()


def _role_row(conn, role_key):
    """Load the bridge_roles row for role_key. None when absent.

    A missing role row is NOT an error: the caller degrades to all-None
    role defaults, which means the precedence walk falls straight through
    to SYSTEM/LEGACY. This matches the legacy behavior: today a missing
    role row is a degraded read, not a crash.
    """
    return conn.execute(
        "SELECT * FROM bridge_roles WHERE role_key = ?",
        (role_key,),
    ).fetchone()


def _row_dict(row):
    """Convert a sqlite3.Row to a plain dict so .get() degrades cleanly.

    New columns added by migration 062 are read with dict(row).get(name)
    so a database predating migration 062 returns None for them and the
    resolver falls through to SYSTEM rather than raising KeyError
    (GOAL.md section 2(d)).
    """
    return dict(row) if row is not None else {}


# ---------------------------------------------------------------------------
# Precedence walks
# ---------------------------------------------------------------------------


def _resolve_governance(step, role):
    """Resolve governance_file with precedence STEP -> ROLE -> SYSTEM.

    Per GOAL.md section 1 D1 and section 2(a):
        if step.governance_file is set -> (value, "step")
        elif role.governance_file is set -> (value, "role")
        else -> (None, "system")
    """
    step_gov = step.get("governance_file")
    if _is_set(step_gov):
        return step_gov, "step"
    role_gov = role.get("governance_file")
    if _is_set(role_gov):
        return role_gov, "role"
    return None, "system"


def _resolve_model(step, role):
    """Resolve (model_source, model_alias) as a source-driven PAIR.

    Per GOAL.md section 2(c) and the bridge_lib.get_effective_model_source
    precedent: model overrides travel as a (source, alias) pair. When the
    step's source wins, the step's alias comes with it. A step that sets
    only model_alias (without model_source) FALLS THROUGH to the role
    pair -- the resolver never mixes step alias with role source, because
    "the alias is the format the source expects" and a step changing the
    format without changing the source would be incoherent.

    model_source='harness' and model_source='harness_provider' BOTH pass
    through UNCHANGED (harness-backed sources, GOAL.md Run 021 §1 D1 +
    section 1 D2). The literal "inherit_from_role" is treated as unset
    (already handled by _is_set for both source and alias keys).

    Returns (model_source, model_alias, source_level).
    """
    step_source = step.get("model_source")
    step_alias = step.get("model_alias")
    if _is_set(step_source):
        return step_source, step_alias, "step"

    role_source = role.get("default_model_source")
    role_alias = role.get("default_model_alias")
    if _is_set(role_source):
        return role_source, role_alias, "role"

    return None, None, "system"


def _resolve_harness(step, role):
    """Resolve (harness_source, harness_profile) with role COALESCE.

    Per GOAL.md section 1 D2 and section 2(c):
        if step.harness_source is set -> (step.harness_source,
                                          step.harness_profile, "step")
        else:
            role_default = role.default_harness_source if set else None
            role_source  = role_default if role_default is not None \
                           else (role.allocator_client if set else None)
            if role_source is not None -> (role_source,
                                           role.default_harness_profile,
                                           "role")
            else -> (None, None, "system")

    The role-level COALESCE keeps the legacy allocator_client column
    working as the role default until Phase 4 migrates it
    (GOAL.md section 1 D2). The literal "inherit_from_role" is treated
    as unset via _is_set.

    Returns (harness_source, harness_profile, source_level).
    """
    step_source = step.get("harness_source")
    step_profile = step.get("harness_profile")
    if _is_set(step_source):
        return step_source, step_profile, "step"

    role_default_source = role.get("default_harness_source")
    role_source = None
    if _is_set(role_default_source):
        role_source = role_default_source
    else:
        # COALESCE fallback: until Phase 4, the legacy allocator_client
        # column keeps working as the role default. allocator_client
        # defaults to 'opencode' in production rows, but we treat
        # "opencode" as a real value when explicitly stored -- only the
        # absence of a stored value (None or "") falls through. The
        # GOAL.md spec calls this out as COALESCE semantics, not as
        # "use allocator_client only when NULL".
        allocator = role.get("allocator_client")
        if _is_set(allocator):
            role_source = allocator

    if role_source is not None:
        role_profile = role.get("default_harness_profile")
        return role_source, role_profile, "role"

    return None, None, "system"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_execution_config(flow_key, step_key, db_path=None):
    """Return the unified execution config dict for (flow_key, step_key).

    The dict carries, per dimension, the resolved value AND its
    ``*_source_level`` (``step`` / ``role`` / ``system``). With all five
    new columns NULL (the post-migration state for every existing row),
    this resolver returns exactly the same governance_file /
    model_source / harness_source as the legacy direct column reads
    -- zero behavior change, mechanically guarded by TG10 in a later
    handoff.

    Args:
        flow_key: The flow the step belongs to.
        step_key: The step to resolve.
        db_path: Optional SQLite path. Defaults to config.get_db_path().

    Returns:
        A dict with exactly these 13 keys (GOAL.md section 2):

            flow_key, step_key, from_role, to_role,
            governance_file, governance_source_level,
            model_source, model_alias, model_source_level,
            harness_source, harness_profile, harness_source_level,
            implementation_mode

    Raises:
        ValueError: ``step_key`` does not exist for ``flow_key``. The
            message names both flow_key and step_key so the configurator
            can fix the offending call without re-reading the resolver.
            A missing role row is NOT an error: it degrades to all-None
            role defaults.
    """
    if db_path is None:
        db_path = config.get_db_path()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        step_row = _step_row(conn, flow_key, step_key)
        if step_row is None:
            raise ValueError(
                f"step_key {step_key!r} not found for flow_key {flow_key!r}; "
                "no silent default -- check bridge_flow_steps for this flow"
            )
        step = _row_dict(step_row)
        from_role = step.get("from_role")
        to_role = step.get("to_role")

        # Missing role row is a soft degradation, not an error: every
        # precedence walk falls through to SYSTEM/LEGACY, matching the
        # legacy behavior (no role = no role defaults = system default).
        role_row = _role_row(conn, from_role)
        role = _row_dict(role_row)

        governance_file, governance_source_level = _resolve_governance(step, role)
        model_source, model_alias, model_source_level = _resolve_model(step, role)
        harness_source, harness_profile, harness_source_level = _resolve_harness(step, role)
    finally:
        conn.close()

    # implementation_mode is delegated to patch_mode.resolve_implementation_mode.
    # That function owns its own precedence (role > step > flow > 'direct')
    # per migration 052, which differs deliberately from the STEP -> ROLE ->
    # SYSTEM walk used above. Re-implementing it here would duplicate
    # precedence logic and break TG10's invariant that nothing changes for
    # any existing step (GOAL.md section 2(b)).
    implementation_mode = resolve_implementation_mode(
        db_path, flow_key, step_key=step_key, role_key=from_role,
    )

    return {
        "flow_key": flow_key,
        "step_key": step_key,
        "from_role": from_role,
        "to_role": to_role,
        "governance_file": governance_file,
        "governance_source_level": governance_source_level,
        "model_source": model_source,
        "model_alias": model_alias,
        "model_source_level": model_source_level,
        "harness_source": harness_source,
        "harness_profile": harness_profile,
        "harness_source_level": harness_source_level,
        "implementation_mode": implementation_mode,
    }


def resolve_for_receiver(flow_key, receiver_role, db_path=None):
    """Resolve the execution config for the step the receiver is about to execute.

    Per GOAL.md section 2(a) (binding semantics, spec section 15):
    step configuration describes the actor (from_role). When dispatch
    composes a prompt FOR a receiver, it must resolve the step whose
    from_role IS the receiver -- the step the receiver is about to
    execute, not the transition step being signaled. This helper makes
    that selection explicit and keeps precedence + selection in one
    module (GOAL.md section 2(a)).

    Args:
        flow_key: The flow the receiver belongs to.
        receiver_role: The role the dispatch is being composed for. Must
            match exactly one active step's from_role in the flow.
        db_path: Optional SQLite path. Defaults to config.get_db_path().

    Returns:
        The dict returned by resolve_execution_config for that step.

    Raises:
        ValueError: Zero or more than one matching active step. The
            message names flow_key and receiver_role (plus the
            conflicting step_keys on ambiguity). A silent pick would
            hide a config bug; spec section 16 (branching) is a
            separate future concern and is intentionally not handled
            here.
    """
    if db_path is None:
        db_path = config.get_db_path()

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT step_key FROM bridge_flow_steps "
            "WHERE flow_key = ? AND from_role = ? AND is_active = 1 "
            "ORDER BY sort_order",
            (flow_key, receiver_role),
        ).fetchall()
    finally:
        conn.close()

    step_keys = [r[0] for r in rows]
    if len(step_keys) == 0:
        raise ValueError(
            f"no active step found in flow_key {flow_key!r} for receiver_role "
            f"{receiver_role!r}; expected exactly one step whose from_role "
            "matches the receiver"
        )
    if len(step_keys) > 1:
        raise ValueError(
            f"ambiguous receiver_step selection for flow_key {flow_key!r} and "
            f"receiver_role {receiver_role!r}: {len(step_keys)} active steps "
            f"have from_role == receiver (step_keys={step_keys!r}); resolve "
            "the ambiguity in bridge_flow_steps before dispatch"
        )

    return resolve_execution_config(flow_key, step_keys[0], db_path)


# ---------------------------------------------------------------------------
# Runtime context block (D3a — handoff 032)
# ---------------------------------------------------------------------------


def runtime_context_block(resolved):
    """Render the deterministic RUNTIME CONTEXT block from a resolved dict.

    The block is what dispatch injects ahead of the governance reference at
    each of the three sites in dispatch.py. It carries EXACTLY the five
    fields listed below (per handoff 032 / GOAL.md section 1 D3):

        flow_key, step_key, from_role, to_role, governance_file

    Contract (handoff 032 step 1):
        * Deterministic: same input dict yields a byte-identical string on
          repeated calls. Fixed field order, fixed separators, fixed line
          count.
        * No templating engine, no {{var}} substitution (spec section 4
          and section 23 verbatim: "prefer simple deterministic injection,
          no templating engine").
        * Every field is ALWAYS present. A field whose resolved value is
          None renders as the stable literal ``None`` (never omitted, never
          a trailing blank, never an empty line standing in for a missing
          field). This makes the block deterministic and Phase-3-ready:
          a Phase-3 governance file can rely on the literal "None" being
          there when governance has not been bound yet.

    Args:
        resolved: The dict returned by ``resolve_execution_config`` (the
            13-key shape defined in GOAL.md section 2). The block reads
            only ``flow_key``, ``step_key``, ``from_role``, ``to_role``,
            and ``governance_file`` from it.

    Returns:
        str: A plain-text block ending in ``\\n\\n`` so that when dispatch
        prepends ``build_target_project_block(...)`` + the block + the
        governance reference line + the rest of the prompt, the seams are
        single newlines at the section boundaries and double newlines
        between sections. The function returns bytes-equivalent text on
        every call given the same input.
    """
    flow_key = resolved["flow_key"]
    step_key = resolved["step_key"]
    from_role = resolved["from_role"]
    to_role = resolved["to_role"]
    governance_file = resolved["governance_file"]

    # Render None as the stable literal "None". str(None) == "None" so
    # this is also deterministic. We never substitute "" for None, never
    # omit the line, never leave the trailing colon dangling.
    def _r(value):
        if value is None:
            return "None"
        return str(value)

    return (
        f"## Runtime Context\n"
        f"- flow_key: {_r(flow_key)}\n"
        f"- step_key: {_r(step_key)}\n"
        f"- from_role: {_r(from_role)}\n"
        f"- to_role: {_r(to_role)}\n"
        f"- governance_file: {_r(governance_file)}\n\n"
    )
