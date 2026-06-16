# Governance: Python Task Rules

> **Fragment ID:** python-task
> **Target section:** `<governance>` (Key rules extracted)
> **Trigger:** `language` = python

## Key Rules for Python Tasks

Extracted from 12_CODING_STANDARD.md and 16_FILE_ACCESS.md:

1. **Python: py_compile before signaling completion.**
   `python3 -m py_compile <file>` MUST pass for every modified Python file.

2. **NO hardcoded /home/svend/... paths.**
   Use `config.py` getters: `config.get_project_root()`, `config.get_bridge_dir()`,
   `config.get_db_path()`, `config.get_governance_dir()`. Hardcoded paths are
   an auto-fail in validation (12_CODING_STANDARD.md, Prohibited Pattern 2.5).

3. **Parameterized SQL.**
   All SQL queries MUST use `?` placeholders — never string concatenation,
   f-strings in SQL, or `%` formatting.

4. **DO NOT COMMIT.**
   Leave all changes unstaged. Only the Human (01_HUMAN) may authorize commits
   per 15_GIT_POLICY.md.

## Additional Rules (check if applicable)

- **Database schema changes:** Require `CREATE TABLE IF NOT EXISTS` —
  idempotent, rerunnable. No `DROP TABLE` or `ALTER TABLE` without Human approval.
- **New dependencies:** Require Human approval via GATE-DEPENDENCY.
  Add to `requirements.txt` only after approval.
- **Seed data:** Use `INSERT OR IGNORE` — idempotent, rerunnable.
