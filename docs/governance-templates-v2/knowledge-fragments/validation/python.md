# Validation: Python Tasks

> **Fragment ID:** python
> **Target section:** `<validation>`
> **Trigger:** `language` = python

## Standard Python Validation Commands

Run these BEFORE signaling completion. All must pass.

1. **Syntax check:**
   ```bash
   python3 -m py_compile {project_root}/app.py
   ```
   Must pass without errors.

2. **No hardcoded paths:**
   ```bash
   grep -n '"/home/svend' {project_root}/app.py
   ```
   Must return NO results. Use `config.py` getters for all paths.

3. **Config getter usage:**
   ```bash
   grep -c "config.get" {project_root}/app.py
   ```
   Must show config getters are used for all configurable values.

4. **Parameterized SQL (if database changes):**
   ```bash
   grep -E 'execute\(.*f".*\{|execute\(.*\+|execute\(.*%' {project_root}/app.py
   ```
   Must return NO results. Use `?` placeholders.

5. **Diff scope:**
   ```bash
   git -C {project_root} diff --stat
   ```
   Verify only the files listed in `<scope>` are modified.

6. **Database idempotency (if init_db.py changed):**
   ```bash
   python3 {project_root}/scripts/init_db.py
   ```
   Must run without errors (CREATE TABLE IF NOT EXISTS / INSERT OR IGNORE).

## If the task also touches JavaScript

Add these checks:
```bash
node --check {project_root}/static/js/*.js
grep -RIn "innerHTML" {project_root}/static/ {project_root}/templates/
```
