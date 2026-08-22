"""Prompt Compiler router (Phase 2F/2I-v2 + UI labels).

Pure refactor from app.py — every endpoint, path, method, status code,
and response shape is identical to the previous inline definitions.
Only the code location moved and the decorator prefix changed
(`@app.X` -> `@router.X`).

Endpoints moved:
  GET    /api/ui-labels/{label_domain}
  POST   /api/prompt-compiler/compile
  POST   /api/prompt-compiler/assign-handoff-id
  POST   /api/prompt-compiler/dispatch

The prompt_compiler endpoints use module-level helpers that lived in
app.py at lines 81 (_resolve_ui_label_text), 159 (get_ui_labels_for_domain),
and 2421 (_load_knowledge_fragment). These helpers were used ONLY by
prompt_compiler endpoints (verified via grep — no other usage in app.py)
and have been moved here.
DB path is obtained via `routers.shared.get_db_path()` (late-import
pattern from B-1) — this preserves the test fixture's monkeypatch
of `app.DB_PATH` and avoids circular imports at module top-level.

A few compile/assign-handoff-id/dispatch endpoints depend on the
BridgeV002 DB helpers (load_flow_from_db, load_role_from_db,
get_next_id_for_flow, build_step_payload) — these are imported via
the same sys.path insert + bridge_lib import pattern as in app.py.
"""

import json
import logging
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

# Ensure scripts/bridgeV002/ is on sys.path so the bridge_lib imports
# below resolve. Mirrors app.py.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "scripts" / "bridgeV002"))

from bridge_lib import (  # noqa: E402
    get_next_id_for_flow,
    load_flow_from_db,
    load_role_from_db,
)
from dispatch import build_step_payload  # noqa: E402

import config  # noqa: E402
from routers.shared import get_db_path  # noqa: E402


router = APIRouter(tags=["prompt_compiler"])


logger = logging.getLogger(__name__)


# ── Module-level helpers (moved verbatim from app.py) ────────────────


def _resolve_ui_label_text(label_row, locale):
    """Resolve translated text for a single ui_label row with fallback chain."""
    label_key = label_row["label_key"]
    default_text = label_row["default_text"]
    translations = label_row.get("translations") or {}
    if locale in translations:
        return translations[locale]
    if "en-US" in translations:
        return translations["en-US"]
    if default_text:
        return default_text
    return label_key


def get_ui_labels_for_domain(label_domain: str, locale: str = "en-US") -> dict:
    """Resolve labels for a domain via the full 4-layer i18n architecture."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.slot_key, l.label_key, l.default_text,
               COALESCE(t_en.translated_text, l.default_text, l.label_key) AS text_en,
               COALESCE(t_req.translated_text, t_en.translated_text, l.default_text, l.label_key) AS text_req
        FROM ui_text_slots s
        JOIN ui_text_slot_labels sl ON s.slot_key = sl.slot_key
        JOIN ui_labels l ON sl.label_key = l.label_key
        LEFT JOIN ui_label_translations t_en ON l.label_id = t_en.label_id AND t_en.locale = 'en-US'
        LEFT JOIN ui_label_translations t_req ON l.label_id = t_req.label_id AND t_req.locale = ?
        WHERE l.label_domain = ?
    """, (locale, label_domain))

    labels = {}
    for row in cursor.fetchall():
        r = dict(row)
        labels[r["slot_key"]] = r["text_req"] if r["text_req"] else r["text_en"]

    conn.close()
    return labels


def _load_knowledge_fragment(filename):
    """Load a knowledge fragment file and return cleaned content."""
    frag_dir = os.path.join(
        config.get_project_root(),
        config.get_governance_dir(),
        "knowledge-fragments"
    )
    filepath = os.path.join(frag_dir, filename)
    if not os.path.exists(filepath):
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    lines = raw.split("\n")
    cleaned = [line for line in lines if not line.startswith("> **")]
    result = "\n".join(cleaned)
    result = result.lstrip("\n")

    lines = result.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# ") and not line.startswith("## "):
            lines.pop(i)
            if i < len(lines) and lines[i].strip() == "":
                lines.pop(i)
            break

    result = "\n".join(lines)
    result = result.replace("{{project_root}}", config.get_project_root())
    return result


# ── Endpoints (moved verbatim from app.py) ────────────────


# ── ui_labels_by_domain ──

@router.get("/api/ui-labels/{label_domain}")
async def get_ui_labels_by_domain(label_domain: str, locale: str = "en-US"):
    """Return resolved labels for a domain via the full 4-layer i18n architecture.

    Traverses ui_text_slots → ui_text_slot_labels → ui_labels → ui_label_translations.
    Returns {slot_key: resolved_text} so frontend data-slot attributes and lbl() calls
    resolve correctly through the slot→label mapping table.

    Fallback chain: requested locale → en-US → default_text → label_key.
    """
    labels = get_ui_labels_for_domain(label_domain, locale)
    return {
        "label_domain": label_domain,
        "locale": locale,
        "labels": labels
    }

# ── prompt_compiler_compile ──

@router.post("/api/prompt-compiler/compile")
async def compile_prompt(request: Request):
    """Compile a simplified prompt (Spor G).

    Accepts 8 fields. Auto-generates governance, constraint, validation
    from target_session role mapping. Returns governance-v2 XML handoff format.

    If flow_key + step_key are provided, resolves deliverable path and
    BridgeV002 signal instruction from DB (replaces legacy bridge.py).
    """
    data = await request.json()

    # ── Validate required fields ─────
    errors = []
    deployment_strategy = data.get("deployment_strategy", "standard")
    flow_key = data.get("flow_key", "")

    # Standard + flow: only target_project and goal are required
    # (phase_key, target_session, allowed_files, forbidden_files auto-resolved)
    if deployment_strategy == "standard" and flow_key:
        required_fields = ["target_project", "goal"]
    else:
        required_fields = ["target_project", "phase_key", "goal"]

    for field_key in required_fields:
        value = data.get(field_key, "")
        if not value or value == "":
            errors.append({
                "error": f"Field '{field_key}' must be filled in",
                "field_key": field_key,
            })

    # scope_gate_confirmed must be checked
    if not data.get("scope_gate_confirmed", False):
        errors.append({
            "error": "Du skal bekræfte at du har taget stilling til scope og gate scope",
            "field_key": "scope_gate_confirmed",
        })

    if errors:
        return JSONResponse(
            status_code=400, content={"errors": errors, "status": "incomplete"}
        )

    # ── Resolve BridgeV002 step data (if flow_key + step_key provided) ─────
    flow_key = data.get("flow_key", "")
    step_key = data.get("step_key", "")
    bridge_step_data = None  # payload dict from build_step_payload, or None

    if flow_key and step_key:
        try:
            flow_data = load_flow_from_db(flow_key, db_path=get_db_path())
        except ValueError:
            flow_data = None

        if flow_data:
            steps = flow_data["steps"]
            target_step = None
            for s in steps:
                if s.get("step_key") == step_key:
                    target_step = s
                    break

            if target_step:
                # Use placeholder "???" for ID — will be replaced at assign-handoff-id time
                bridge_step_data = build_step_payload(
                    target_step, flow_key, "???", config.get_bridge_dir()
                )

    # ── Generate prompt ─────
    handoff_id = data.get("handoff_id", "???")
    target_project = data.get("target_project", "")
    phase_key = data.get("phase_key", "")
    goal = data.get("goal", "")
    deployment_strategy = data.get("deployment_strategy", "standard")
    allowed_files = data.get("allowed_files", "")
    forbidden_files = data.get("forbidden_files", "")

    # ── Standard + BridgeV002: auto-resolve from governance ─────
    if deployment_strategy == "standard" and bridge_step_data:
        from_role_key = bridge_step_data.get("from_role", "")
        to_role_key = bridge_step_data.get("to_role", "")

        # Load to_role from DB → get governance_file, tmux_session
        # (to_role is the one who executes the prompt)
        try:
            to_role_data = load_role_from_db(to_role_key, db_path=get_db_path())
        except ValueError:
            to_role_data = None

        # Auto-resolve target_session from to_role's tmux_session
        if to_role_data:
            target_session = to_role_data.get("tmux_session", "")
            governance_file = to_role_data.get("governance_file", "")
        else:
            target_session = "claude_implementer"
            governance_file = "IMPLEMENTOR.md"

        # Read governance file content from disk
        gov_path = os.path.join(
            config.get_project_root(),
            config.get_governance_dir(),
            governance_file,
        )
        gov_content = ""
        if os.path.isfile(gov_path):
            with open(gov_path, "r", encoding="utf-8") as gf:
                gov_content = gf.read()

        # Extract role name from governance file (first # heading)
        role_name = to_role_key
        if gov_content:
            for line in gov_content.split("\n"):
                if line.startswith("# ") and "STRICT_REVIEW" in line:
                    role_name = line.replace("# ", "").strip()
                    break

        # ── Build deliverable path and signal command from DB ─────
        deliverable_dir_val = bridge_step_data.get("deliverable_dir", "")

        # Result path: use step's deliverable_dir (absolute path to results/)
        # For step archi01→imple01, deliverable_dir is .../handoffs, but result goes to .../results
        if deliverable_dir_val:
            result_dir = os.path.join(os.path.dirname(deliverable_dir_val), "results")
        else:
            result_dir = os.path.join(config.get_bridge_dir(), "results")
        result_path = f"{result_dir}/{{ID}}-result.md"

        signal_cmd_template = (
            f"python3 {config.get_project_root()}/scripts/bridgeV002/dispatch.py "
            f"--db-flow {flow_key} --signal-complete --from-role {to_role_key}"
        )

        # ── Assemble prompt from governance + DB ─────
        lines = []
        # <role> — from governance file reference
        lines.append(f"<role>You are {to_role_key} in the DPMtF strict_review flow.")
        lines.append(f"Your role is defined in {gov_path}.")
        lines.append("Read it now before proceeding.</role>")
        lines.append("")
        lines.append(f"<handoff_id>{handoff_id}</handoff_id>")
        lines.append("")
        lines.append(f"<project>{target_project}</project>")
        lines.append("")
        lines.append("<context>")
        lines.append(f"Human has approved scope for phase {phase_key}.")
        lines.append(f"Scope is defined in {target_project}/docs/dpmtf/11_SCOPE.md.")
        lines.append(f"Father project: {config.get_father_project()}.")
        lines.append(f"Flow: {flow_key}, Step: {step_key} ({from_role_key} → {to_role_key}).")
        lines.append("</context>")
        lines.append("")
        # <governance> — reference the flow-specific file only
        lines.append("<governance>")
        lines.append("Read and apply your role definition BEFORE starting:")
        lines.append(f"- {gov_path}")
        lines.append("")
        lines.append("Key rules from your governance file apply in full.")
        lines.append("</governance>")
        lines.append("")
        # <task> — goal + auto-generated bridge signal
        lines.append("<task>")
        lines.append(goal)
        lines.append("")
        lines.append("When ALL steps are complete, execute the bridge signal:")
        lines.append("")
        lines.append(f"1. Write result file to {result_path.replace('{ID}', handoff_id)}")
        lines.append(f"2. SIGNAL completion: {signal_cmd_template.replace('{ID}', handoff_id)}")
        lines.append("</task>")
        lines.append("")
        # <scope> — from user input + Father project protection
        lines.append("<scope>")
        lines.append("Files you MAY modify:")
        if allowed_files:
            for f in allowed_files.strip().split("\n"):
                f = f.strip()
                if f:
                    lines.append(f"- {f}")
        else:
            lines.append("- (per governance file — Review will verify)")
        lines.append("")
        lines.append("Files you MUST NOT touch:")
        if forbidden_files:
            for f in forbidden_files.strip().split("\n"):
                f = f.strip()
                if f:
                    lines.append(f"- {f}")
        lines.append(f"- {config.get_project_root()}/ (Father project)")
        lines.append("</scope>")
        lines.append("")
        # <validation> — reference governance file
        lines.append("<validation>")
        lines.append(f"Run all validation checks defined in your governance file: {gov_path}")
        lines.append("Key checks include: py_compile, node --check, innerHTML, diff scope, i18n.")
        lines.append("</validation>")
        lines.append("")
        # <constraint> — from governance
        lines.append("<constraint>")
        lines.append("DO NOT COMMIT. Leave all changes unstaged.")
        lines.append(f"Target session: {target_session} (role: {from_role_key}).")
        lines.append("Execute ALL steps in <task> — especially the signal completion command.")
        lines.append("Stop after 2 failed patching attempts — document, do not guess.")
        lines.append("</constraint>")

        prompt = "\n".join(lines)

        result_response = {
            "prompt": prompt,
            "params_used": list(data.keys()),
            "format": "governance-v2-xml",
            "target_session": target_session,
            "target_role": to_role_key,
            "bridge_flow_key": flow_key,
            "bridge_step_key": step_key,
            "deliverable_dir": deliverable_dir_val,
            "governance_file": governance_file,
            "auto_resolved": True,
        }
        return result_response

    # ── Legacy / accelerated / no-flow: existing behavior ─────
    target_session = data.get("target_session", "claude_implementer")

    # Map session to governance role
    if "implementer" in target_session.lower():
        governance_role_file = "IMPLEMENTOR.md"
        role_name = "Implementor"
    elif "architect" in target_session.lower():
        governance_role_file = "ARCHITECT.md"
        role_name = "Architect"
    elif "review" in target_session.lower():
        governance_role_file = "REVIEW.md"
        role_name = "Review"
    else:
        governance_role_file = "IMPLEMENTOR.md"
        role_name = "Implementor"

    # ── Determine deliverable path and signal command ─────
    if bridge_step_data:
        deliverable_dir_val = bridge_step_data.get("deliverable_dir", "implementertoreview")
        result_path = f"{config.get_bridge_dir()}/{deliverable_dir_val}/{{ID}}-result.md"
        to_role_key = bridge_step_data.get("to_role", "")
        signal_cmd_template = (
            f"python3 {config.get_project_root()}/scripts/bridgeV002/dispatch.py "
            f"--db-flow {flow_key} --signal-complete --from-role {to_role_key}"
        )
    else:
        deliverable_dir_val = "implementertoreview"
        result_path = f"{config.get_bridge_dir()}/implementertoreview/{{ID}}-result.md"
        signal_cmd_template = f"python3 {config.get_bridge_dir()}/bridge.py complete {{ID}}"

    lines = []
    lines.append(f"<role>You are {role_name} in the DPMtF governance loop. Your role is defined")
    lines.append(f"in {config.get_project_root()}/{config.get_governance_dir()}/{governance_role_file}.")
    lines.append("Read it now before proceeding.</role>")
    lines.append("")
    lines.append(f"<handoff_id>{handoff_id}</handoff_id>")
    lines.append("")
    lines.append(f"<project>{target_project}</project>")
    lines.append("")
    lines.append("<context>")
    lines.append(f"Human has approved scope for phase {phase_key}.")
    lines.append(f"Scope is defined in {target_project}/docs/dpmtf/11_SCOPE.md.")
    lines.append(f"Father project: {config.get_father_project()}.")
    if deployment_strategy:
        lines.append(f"Deployment strategy: {deployment_strategy}.")
    lines.append("</context>")
    lines.append("")
    lines.append("<governance>")
    lines.append("Read and apply these governance files BEFORE starting:")
    lines.append(f"- {config.get_project_root()}/{config.get_governance_dir()}/12_CODING_STANDARD.md")
    lines.append(f"- {config.get_project_root()}/{config.get_governance_dir()}/16_FILE_ACCESS.md")
    lines.append(f"- {config.get_project_root()}/{config.get_governance_dir()}/{governance_role_file}")
    lines.append("")
    lines.append("Key rules extracted:")
    lines.append("- NO innerHTML for dynamic content — use createElement()/textContent.")
    lines.append("- ALL user-facing text MUST use lbl(key, fallback).")
    lines.append("- Python: py_compile before signaling completion, parameterized SQL.")
    lines.append("- DO NOT COMMIT.")
    lines.append("</governance>")
    lines.append("")
    lines.append("<task>")
    lines.append(goal)
    lines.append("")
    lines.append("When ALL steps are complete, execute the bridge signal:")
    lines.append("")
    lines.append(f"1. Write result file to {result_path.replace('{ID}', handoff_id)}")
    lines.append(f"2. SIGNAL completion: {signal_cmd_template.replace('{ID}', handoff_id)}")
    lines.append("</task>")
    lines.append("")
    lines.append("<scope>")
    lines.append("Files you MAY modify:")
    if allowed_files:
        for f in allowed_files.strip().split("\n"):
            f = f.strip()
            if f:
                lines.append(f"- {f}")
    else:
        lines.append("- (none specified — Review should verify)")
    lines.append("")
    lines.append("Files you MUST NOT touch:")
    if forbidden_files:
        for f in forbidden_files.strip().split("\n"):
            f = f.strip()
            if f:
                lines.append(f"- {f}")
    lines.append(f"- {config.get_project_root()}/ (Father project)")
    lines.append("</scope>")
    lines.append("")
    lines.append("<validation>")
    lines.append("1. python3 -m py_compile <modified files> — must pass")
    lines.append("2. node --check static/js/*.js — must pass for each modified file")
    lines.append("3. grep -RIn 'innerHTML' static/ templates/ — must be empty")
    lines.append("4. git diff --stat — verify only allowed files changed")
    lines.append("</validation>")
    lines.append("")
    lines.append("<constraint>")
    lines.append("DO NOT COMMIT. Leave all changes unstaged.")
    lines.append(f"Target session: {target_session} (role: {role_name}).")
    lines.append(f"Execute ALL steps in <task> — especially the signal completion command.")
    lines.append("</constraint>")

    prompt = "\n".join(lines)

    result_response = {
        "prompt": prompt,
        "params_used": list(data.keys()),
        "format": "governance-v2-xml",
        "target_session": target_session,
        "target_role": role_name,
    }

    if bridge_step_data:
        result_response["bridge_flow_key"] = flow_key
        result_response["bridge_step_key"] = step_key
        result_response["deliverable_dir"] = bridge_step_data.get("deliverable_dir", "")

    return result_response

# ── prompt_compiler_assign_handoff_id ──

@router.post("/api/prompt-compiler/assign-handoff-id")
async def assign_handoff_id(request: Request):
    """Assign a real handoff ID to a compiled prompt and write the handoff file.

    Replaces ??? placeholders with the next available BridgeV002 handoff ID,
    writes the finalized prompt to the correct deliverable directory resolved
    from DB, and returns a BridgeV002 dispatch command.

    Body (JSON):
      prompt_text     — the compiled prompt text (may contain ??? placeholders)
      target_project  — target project path (for logging context)
      flow_key        — BridgeV002 flow key (e.g. 'strict_review')
      step_key        — BridgeV002 step key within the flow (optional)
      deliverable_dir — pre-resolved from compile_prompt (if available)
    """
    data = await request.json()
    prompt_text: str = data.get("prompt_text", "")

    if not prompt_text:
        raise HTTPException(status_code=400, detail="Missing prompt_text")

    flow_key = data.get("flow_key", "strict_review")
    step_key = data.get("step_key", "")

    # Get next handoff ID from BridgeV002 DB (replaces bridge.py next-id subprocess)
    try:
        handoff_id_raw = get_next_id_for_flow(flow_key, db_path=get_db_path())
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get next ID for flow '{flow_key}': {e}",
        )

    handoff_id: str = str(handoff_id_raw)

    # Replace ??? placeholders with real ID
    finalized_prompt: str = prompt_text.replace("???", handoff_id)

    # Resolve deliverable directory and pattern from step
    # Priority: 1) DB step deliverable_dir (absolute path), 2) pre-resolved from compile, 3) default
    deliverable_dir_val = ""
    deliverable_pattern = "{ID}-handoff.md"  # default

    if flow_key and step_key:
        try:
            flow_data = load_flow_from_db(flow_key, db_path=get_db_path())
            for s in flow_data["steps"]:
                if s.get("step_key") == step_key:
                    deliverable_dir_val = s.get("deliverable_dir", "")
                    deliverable_pattern = s.get("deliverable_pattern", deliverable_pattern)
                    break
        except ValueError as exc:
            logger.warning("TBD: flow %s not found for assign-handoff-id deliverable lookup: %s", flow_key, exc)

    # Fall back to pre-resolved from compile if DB lookup didn't yield a dir
    if not deliverable_dir_val:
        deliverable_dir_val = data.get("deliverable_dir", "")

    if not deliverable_dir_val:
        # Last-resort fallback — use DPMTF_BRIDGE_DIR from environment
        bridge_base = os.environ.get("DPMTF_BRIDGE_DIR", os.path.expanduser("~/flows"))
        deliverable_dir_val = f"{bridge_base}/{flow_key}/handoffs"

    # Build deliverable filename from pattern
    deliverable_file = deliverable_pattern.replace("{ID}", handoff_id)

    # Build handoff path — handle absolute vs relative deliverable_dir
    if os.path.isabs(deliverable_dir_val):
        handoff_dir = deliverable_dir_val
    else:
        handoff_dir = os.path.join(config.get_bridge_dir(), deliverable_dir_val)
    handoff_path = os.path.join(handoff_dir, deliverable_file)
    os.makedirs(handoff_dir, exist_ok=True)
    try:
        with open(handoff_path, "w") as f:
            f.write(finalized_prompt)
    except IOError as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to write handoff file: {e}"
        )

    # Build BridgeV002 dispatch command from step (replaces legacy bridge.py send)
    from_role_for_send = "archi01"  # default sender
    to_role_for_send = "imple01"    # default target
    if flow_key and step_key:
        try:
            flow_data = load_flow_from_db(flow_key, db_path=get_db_path())
            for s in flow_data["steps"]:
                if s.get("step_key") == step_key:
                    from_role_for_send = s.get("from_role", from_role_for_send)
                    to_role_for_send = s.get("to_role", to_role_for_send)
                    break
        except ValueError as exc:
            logger.warning("TBD: flow %s not found for assign-handoff-id role lookup: %s", flow_key, exc)

    dispatch_command: str = (
        f"python3 {config.get_project_root()}/scripts/bridgeV002/dispatch.py "
        f"--db-flow {flow_key} --signal-send "
        f"--from-role {from_role_for_send} --to-role {to_role_for_send} "
        f"--id {handoff_id}"
    )

    return {
        "handoff_id": handoff_id,
        "handoff_path": handoff_path,
        "prompt": finalized_prompt,
        "dispatch_command": dispatch_command,
        "flow_key": flow_key,
        "from_role": from_role_for_send,
        "to_role": to_role_for_send,
        "deliverable_dir": deliverable_dir_val,
        "status": "ready_for_dispatch",
    }

# ── prompt_compiler_dispatch ──

@router.post("/api/prompt-compiler/dispatch")
async def dispatch_handoff(request: Request):
    """Run the BridgeV002 dispatcher to deliver a handoff to its target role.

    Frontend wrapper around dispatch.py signal-send. Called from the UI after
    assign-handoff-id has produced a ready dispatch command, eliminating the
    need to copy/paste the command into a terminal.

    Body (JSON):
      flow_key   — BridgeV002 flow key (e.g. 'strict_review')
      from_role  — source role key (e.g. 'archi01')
      to_role    — target role key (e.g. 'imple01')
      handoff_id — assigned handoff ID (e.g. '178')
    """
    data = await request.json()

    required_fields = ["flow_key", "from_role", "to_role", "handoff_id"]
    for field in required_fields:
        if field not in data or not str(data[field]).strip():
            raise HTTPException(
                status_code=400, detail=f"Missing required field: {field}"
            )

    flow_key = str(data["flow_key"]).strip()
    from_role = str(data["from_role"]).strip()
    to_role = str(data["to_role"]).strip()
    handoff_id = str(data["handoff_id"]).strip()

    script_path = (
        Path(config.get_project_root())
        / "scripts"
        / "bridgeV002"
        / "dispatch.py"
    )
    if not script_path.exists():
        raise HTTPException(
            status_code=500, detail=f"dispatch.py not found at {script_path}"
        )

    cmd = [
        "python3",
        str(script_path),
        "--db-flow", flow_key,
        "--signal-send",
        "--from-role", from_role,
        "--to-role", to_role,
        "--id", handoff_id,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=config.get_project_root(),
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return JSONResponse(
            status_code=504,
            content={
                "success": False,
                "error": "dispatch.py timed out after 120 seconds",
                "handoff_id": handoff_id,
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Failed to execute dispatch.py: {e}",
                "handoff_id": handoff_id,
            },
        )

    output = (result.stdout or "") + (result.stderr or "")
    success = (
        result.returncode == 0
        and "ERROR" not in output
        and "send_failed" not in output
        and "✅" in output
    )

    return {
        "success": success,
        "returncode": result.returncode,
        "output": output,
        "handoff_id": handoff_id,
        "from_role": from_role,
        "to_role": to_role,
        "flow_key": flow_key,
    }

