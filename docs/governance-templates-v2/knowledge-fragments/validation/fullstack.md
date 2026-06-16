# Validation: Fullstack Tasks (Python + JavaScript)

> **Fragment ID:** fullstack
> **Target section:** `<validation>`
> **Trigger:** `language` = fullstack

## Standard Fullstack Validation Commands

Run these BEFORE signaling completion. All must pass.

### Python Checks

1. **Syntax check:**
   ```bash
   python3 -m py_compile {project_root}/app.py
   python3 -m py_compile {project_root}/scripts/init_db.py
   ```
   Both must pass without errors.

2. **No hardcoded paths:**
   ```bash
   grep -n '"/home/svend' {project_root}/app.py {project_root}/scripts/init_db.py
   ```
   Must return NO results. Use `config.py` getters.

3. **Config getter usage:**
   ```bash
   grep -c "config.get" {project_root}/app.py
   ```
   Must show config getters are used for all configurable values.

4. **Parameterized SQL:**
   ```bash
   grep -E 'execute\(.*f".*\{|execute\(.*\+|execute\(.*%' {project_root}/app.py {project_root}/scripts/init_db.py
   ```
   Must return NO results. Use `?` placeholders.

5. **Database idempotency:**
   ```bash
   python3 {project_root}/scripts/init_db.py
   ```
   Must run without errors.

### JavaScript Checks

6. **Syntax check:**
   ```bash
   node --check {project_root}/static/js/*.js
   ```
   Must pass for every modified JS file.

7. **No innerHTML:**
   ```bash
   grep -RIn "innerHTML" {project_root}/static/ {project_root}/templates/
   ```
   Must return NO results. Use `createElement()` / `textContent` / `appendChild()`.

8. **lbl() usage:**
   ```bash
   grep -c "lbl(" {project_root}/static/js/*.js
   ```
   All user-facing text must use `lbl(slot_key, fallback)`.

9. **No hardcoded English strings in DOM:**
   ```bash
   grep -Pn "(?<!lbl\()['\"][A-Z][a-z]{2,}.*['\"]" {project_root}/static/js/*.js
   ```
   Text strings in JS should go through `lbl()`, not be hardcoded.

### Diff Scope

10. **Verify only expected files changed:**
    ```bash
    git -C {project_root} diff --stat
    ```
    Must match the files listed in `<scope>`.

### Visual Check (if frontend changed)

11. **Screenshot comparison:**
    If `<validation>` requires `screenshot_required`, take before/after
    screenshots and verify no unintended visual changes.
