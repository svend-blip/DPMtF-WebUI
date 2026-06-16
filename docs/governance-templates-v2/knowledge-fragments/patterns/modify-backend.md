# Pattern: Modify Backend (app.py)

> **Fragment ID:** modify-backend
> **Target section:** `<task>`
> **Trigger:** `task_type` = modify_backend

## Standard Pattern for Backend Changes

### Files You Will Typically Touch

- `app.py` — primary target (route handlers, business logic, helpers)
- `scripts/init_db.py` — if new endpoints need endpoint_registry entries
- `config.py` — DO NOT TOUCH unless adding a new config getter (rare)

### Step Pattern

1. **Locate the target area in app.py.**
   - Routes are defined with `@app.get(...)`, `@app.post(...)` decorators.
   - Helper functions are above the route that uses them.
   - Database operations use `sqlite3.connect(config.get_db_path())`.

2. **Make the change.**
   - New route: add `@app.get("/api/...")` or `@app.post("/api/...")` decorator
     followed by an `async def` handler.
   - Modified logic: find the existing function and edit its body.
   - New helper: add before the route that calls it.

3. **Update seed data if needed.**
   - If adding a permanent endpoint, add it to `endpoint_registry` in
     `scripts/init_db.py` (INSERT OR IGNORE pattern).
   - If adding i18n labels, add to `ui_labels` + `ui_label_translations` seed data.

4. **Run validation.**
   - `python3 -m py_compile app.py` — must pass.
   - `grep -n '"/home/svend' app.py` — must return NO results (use config getters).
   - If init_db.py was changed: `python3 scripts/init_db.py` — must run without errors.

### Common Pitfalls

- **Hardcoded paths:** Use `config.get_db_path()`, `config.get_bridge_dir()`,
  `config.get_project_root()` — never `/home/svend/...`.
- **String concatenation in SQL:** Use parameterized queries (`?` placeholders).
- **Missing imports:** FastAPI imports are at the top of app.py (lines 1-11).
  `import config` is at line 11. Add new imports only if needed.
- **Forgetting init_db.py:** New permanent endpoints MUST be registered in
  `endpoint_registry` seed data.

### Example: Adding a Simple GET Endpoint

```python
# In app.py, add after existing routes:
@app.get("/api/example")
async def example_endpoint():
    conn = sqlite3.connect(config.get_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ui_labels")
    count = cursor.fetchone()[0]
    conn.close()
    return {"status": "ok", "label_count": count}
```

### Verification Commands

```bash
# After changes:
python3 -m py_compile app.py
grep -n '"/home/svend' app.py  # Must return NO results
git diff --stat                 # Verify only expected files changed
```
