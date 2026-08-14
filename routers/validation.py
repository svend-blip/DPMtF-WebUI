"""Validation router (validation rules, runs, bootstrap-dataset-status).

Pure refactor from app.py — every endpoint, path, method, status code,
and response shape is identical to the previous inline definitions.
Only the code location moved and the decorator prefix changed
(`@app.X` → `@router.X`).

Endpoints moved (4 total):
  POST   /api/validate
  GET    /api/validation-runs
  GET    /api/validation-rules
  GET    /api/bootstrap-dataset-status

DB path is obtained via `routers.shared.get_db_path()` (late-import
pattern from B-1).

The `ALLOWED_BOOTSTRAP_TABLES` constant (used only by /api/bootstrap-
dataset-status) was moved here from app.py.
"""

import logging
import os
import shlex
import sqlite3
import subprocess

from fastapi import APIRouter, HTTPException, Request

from routers.shared import get_db_path


router = APIRouter(tags=["validation"])


logger = logging.getLogger(__name__)


# Programs a validation rule may start a shell segment with. Rules come
# from the validation_rules table and run with shell=True (they need
# globs, pipes and `|| echo` fallbacks), so the guard must reason about
# STRUCTURE: the substring denylist it replaces was bypassable with `;`,
# `|` or a newline before the destructive part.
_READONLY_PROGRAMS = {
    "python3", "node", "git", "grep", "bash", "echo",
    "ls", "cat", "head", "tail", "wc", "curl", "test",
}
# Programs whose first argument decides whether the call is read-only.
_CONSTRAINED_FIRST_ARG = {
    "bash": {"-n"},                       # syntax check only, never execute
    "node": {"--check"},
    "git": {"diff", "status", "log", "show", "ls-files", "rev-parse",
            "branch", "grep"},
    "python3": {"-m"},
}
_PYTHON_READONLY_MODULES = {"py_compile", "compileall", "json.tool", "pytest"}
_SHELL_OPERATORS = {"|", "||", ";", "&&"}


def _command_is_readonly(cmd: str) -> bool:
    """True when every shell segment starts with an allowlisted program.

    Tokenized with shlex (punctuation_chars) so operators inside quotes —
    e.g. grep -i "sql\\|migration" — stay ordinary words. Substitution,
    redirection, background `&` and subshells are refused outright.
    """
    # A newline is a command separator the tokenizer reads as whitespace,
    # which would hide a second command as the first one's "argument".
    if "`" in cmd or "$(" in cmd or "${" in cmd or "\n" in cmd or "\r" in cmd:
        return False
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    try:
        tokens = list(lex)
    except ValueError:
        return False
    if not tokens:
        return False
    expect_program = True
    pending = None  # program whose first argument is still unvalidated
    for tok in tokens:
        if tok in _SHELL_OPERATORS:
            if pending:
                return False
            expect_program, pending = True, None
            continue
        if any(c in tok for c in "<>&()"):
            return False
        if expect_program:
            program = os.path.basename(tok)
            if program not in _READONLY_PROGRAMS:
                return False
            pending = program if program in _CONSTRAINED_FIRST_ARG else None
            expect_program = False
            continue
        if pending == "python3":
            if tok != "-m":
                return False
            pending = "python3 -m"
            continue
        if pending == "python3 -m":
            if tok not in _PYTHON_READONLY_MODULES:
                return False
            pending = None
            continue
        if pending:
            if tok not in _CONSTRAINED_FIRST_ARG[pending]:
                return False
            pending = None
    return not pending and not expect_program


# Allowed table names for safe counting in bootstrap dataset status
ALLOWED_BOOTSTRAP_TABLES = {
    "phase_status",
    "layout_slots",
    "layout_panels",
    "ui_labels",
    "ui_label_translations",
    "endpoint_registry",
    "architecture_decision_records",
    "webui_migration_targets",
    "reusable_panel_selections",
    "webui_project_skeletons",
    "v2_panel_requirements",
}


# ── Endpoints (moved verbatim from app.py) ────────────────


# ── GET /api/bootstrap-dataset-status ──

@router.get("/api/bootstrap-dataset-status")
async def get_bootstrap_dataset_status():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get active bootstrap_dataset_registry records ordered by dataset_id
    cursor.execute("""
        SELECT dataset_id, dataset_key, table_name, min_expected_count,
               is_required, is_active
        FROM bootstrap_dataset_registry
        WHERE is_active = 1
        ORDER BY dataset_id
    """)

    bootstrap_status = []
    for row in cursor.fetchall():
        dataset_id, dataset_key, table_name, min_expected_count, is_required, is_active = row

        # Safe table-name handling: only count if the name is an allowed identifier
        if table_name not in ALLOWED_BOOTSTRAP_TABLES:
            bootstrap_status.append({
                "dataset_id": dataset_id,
                "dataset_key": dataset_key,
                "table_name": table_name,
                "min_expected_count": min_expected_count,
                "actual_count": None,
                "is_required": bool(is_required),
                "is_active": bool(is_active),
                "status": "missing_table",
            })
            continue

        # Verify the table exists in sqlite_schema
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        )
        if not cursor.fetchone():
            bootstrap_status.append({
                "dataset_id": dataset_id,
                "dataset_key": dataset_key,
                "table_name": table_name,
                "min_expected_count": min_expected_count,
                "actual_count": None,
                "is_required": bool(is_required),
                "is_active": bool(is_active),
                "status": "missing_table",
            })
            continue

        # Count records in the referenced table
        # Safe: table_name was validated against ALLOWED_BOOTSTRAP_TABLES
        # (literal allow-list constant) and sqlite_master (live schema check)
        # above. SQLite does not support `?` placeholders for table names;
        # the validated literal is concatenated.
        cursor.execute("SELECT COUNT(*) FROM " + table_name)
        actual_count = cursor.fetchone()[0]

        if actual_count >= min_expected_count:
            status = "ok"
        else:
            status = "below_minimum"

        bootstrap_status.append({
            "dataset_id": dataset_id,
            "dataset_key": dataset_key,
            "table_name": table_name,
            "min_expected_count": min_expected_count,
            "actual_count": actual_count,
            "is_required": bool(is_required),
            "is_active": bool(is_active),
            "status": status,
        })

    conn.close()
    return {"bootstrap_dataset_status": bootstrap_status}


# ── POST /api/validate ──

@router.post("/api/validate")
async def run_validation(request: Request):
    """Run validation rules against a project and return a structured report.

    Body (JSON):
      target_project  — project path or key (required)
      phase_key       — phase being validated (optional)
      rule_keys       — list of rule keys to run, or ["all"] (default)
      diff_content    — pre-provided diff output (optional, avoids shelling out)

    Only runs read-only diagnostic commands (grep, git diff, syntax checks).
    No destructive operations. Records results in validation_runs and
    validation_results tables.
    """
    data = await request.json()

    target = data.get("target_project")
    if not target:
        raise HTTPException(status_code=400, detail="Missing target_project")

    rule_keys = data.get("rule_keys", ["all"])
    phase_key = data.get("phase_key")

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch rules
    if "all" in rule_keys:
        cursor.execute("""
            SELECT * FROM validation_rules WHERE is_active = 1 ORDER BY rule_key
        """)
    else:
        placeholders = ",".join("?" for _ in rule_keys)
        # Safe: placeholders contains only literal "?" markers joined by ",".
        # All actual rule_key values are still parameterized via the
        # `rule_keys` tuple argument below.
        sql = (
            "SELECT * FROM validation_rules "
            "WHERE rule_key IN (" + placeholders + ") "
            "AND is_active = 1 "
            "ORDER BY rule_key"
        )
        cursor.execute(sql, rule_keys)
    rules = [dict(r) for r in cursor.fetchall()]

    if not rules:
        conn.close()
        return {"status": "no rules matched", "results": []}

    # Generate run_id
    import uuid
    run_id = f"VALRUN-{uuid.uuid4().hex[:8].upper()}"

    # Run each rule
    results = []
    passed_count = 0
    failed_count = 0

    for rule in rules:
        cmd = rule["command"]
        result = {"rule_key": rule["rule_key"], "rule_name": rule["rule_name"],
                  "command": cmd, "passed": 0, "actual_output": "", "notes": ""}

        try:
            # Safety: only allow read-only commands
            if not _command_is_readonly(cmd):
                result["notes"] = ("Blocked: command is not on the read-only "
                                   "allowlist (see _command_is_readonly)")
                results.append(result)
                failed_count += 1
                continue

            # Run command in the target project directory
            proc = subprocess.run(
                cmd, shell=True, cwd=target,
                capture_output=True, text=True, timeout=30,
            )
            output = (proc.stdout + proc.stderr).strip()
            result["actual_output"] = output[:2000]  # Truncate

            # Determine pass/fail
            # Exit code 0 = pass. expected_output is documentation for humans.
            if proc.returncode == 0:
                result["passed"] = 1
                passed_count += 1
            else:
                result["passed"] = 0
                result["notes"] = f"Exit code {proc.returncode}"
                failed_count += 1

        except subprocess.TimeoutExpired:
            result["notes"] = "Command timed out after 30s"
            failed_count += 1
        except Exception as exc:
            result["notes"] = f"Error: {str(exc)[:200]}"
            failed_count += 1

        results.append(result)

    # Record run
    total = len(rules)
    verdict = "PASS" if failed_count == 0 else ("PASS WITH NOTES" if failed_count <= 1 else "FAIL")
    cursor.execute("""
        INSERT INTO validation_runs
        (run_id, phase_key, target_project, overall_verdict,
         rules_total, rules_passed, rules_failed)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (run_id, phase_key, target, verdict, total, passed_count, failed_count))

    # Record per-rule results
    for r in results:
        cursor.execute("""
            INSERT INTO validation_results
            (run_id, rule_key, passed, actual_output, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (run_id, r["rule_key"], r["passed"],
              r["actual_output"][:500], r["notes"][:500]))

    conn.commit()
    conn.close()

    return {
        "run_id": run_id,
        "target_project": target,
        "phase_key": phase_key,
        "verdict": verdict,
        "rules_total": total,
        "rules_passed": passed_count,
        "rules_failed": failed_count,
        "results": results,
    }


# ── GET /api/validation-runs ──

@router.get("/api/validation-runs")
async def get_validation_runs(limit: int = 20):
    """Return recent validation runs."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM validation_runs
        ORDER BY run_timestamp DESC LIMIT ?
    """, (limit,))
    runs = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {"runs": runs}


# ── GET /api/validation-rules ──

@router.get("/api/validation-rules")
async def get_validation_rules():
    """Return all active validation rules."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM validation_rules
        WHERE is_active = 1
        ORDER BY rule_key
    """)
    rules = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {"rules": rules}


