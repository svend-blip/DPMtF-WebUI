# Pattern: Add API Endpoint

> **Fragment ID:** add-endpoint
> **Target section:** `<task>`
> **Trigger:** `task_type` = add_endpoint

## Standard Pattern for Adding a New API Endpoint

### Files You Will Touch

- `app.py` — route decorator + async handler function
- `scripts/init_db.py` — endpoint_registry seed data (for permanent endpoints)

### Step Pattern

1. **Add the route decorator and handler in app.py.**
   Find a logical location among existing routes (grouped by domain).
   Add after the last route in that group.

   ```python
   @app.get("/api/{endpoint_name}")
   async def {endpoint_name}():
       """Brief docstring describing what this endpoint returns."""
       conn = sqlite3.connect(config.get_db_path())
       cursor = conn.cursor()
       # Parameterized query
       cursor.execute("SELECT ... FROM ... WHERE ...", (param,))
       result = cursor.fetchall()
       conn.close()
       return {"status": "ok", "data": result}
   ```

   For POST endpoints accepting JSON input:
   ```python
   @app.post("/api/{endpoint_name}")
   async def {endpoint_name}(request: Request):
       data = await request.json()
       # Validate required fields
       if not data.get("required_field"):
           raise HTTPException(status_code=400, detail="Missing required_field")
       # Process and return
   ```

2. **Register in endpoint_registry (init_db.py).**
   Find the `endpoint_registry_*` seed data section (search for `ENDP-`).
   Add a new entry following the existing pattern:

   ```python
   ("ENDP-{next_id}", "{endpoint_key}", "/api/{endpoint_name}", "GET",
    "{short_description}", "{response_format}", "{panel_name}"),
   ```

   Use the next available ENDP ID (check existing entries for the highest number).

3. **Run validation.**
   - `python3 -m py_compile app.py` — must pass.
   - `python3 scripts/init_db.py` — must run without errors (idempotent).
   - `curl -s http://localhost:9130/api/{endpoint_name}` — must return 200.

### Common Pitfalls

- **Forgetting init_db.py registration:** New permanent endpoints MUST be in
  endpoint_registry. Temporary/debug endpoints can skip this.
- **SQL string concatenation:** Use `?` placeholders, never f-strings in SQL.
- **Missing error handling:** Validate input, return HTTPException for bad requests.
- **Hardcoded paths:** Use `config.get_db_path()` for database connections.

### Verification Commands

```bash
python3 -m py_compile app.py
python3 scripts/init_db.py
curl -s http://localhost:9130/api/{endpoint_name}  # Must return JSON, not error
grep -n '"/home/svend' app.py                      # Must return NO results
```
