"""BridgeV002 HTTP API router (Spor I + J — database integration + CRUD).

Pure refactor from app.py — every endpoint, path, method, status code,
and response shape is identical to the previous inline definitions in
app.py. Only the code location moved.

The router registers under /api/bridge-v2 (the prefix matches the
previous inline `@app.X("/api/bridge-v2/...")` paths exactly).

Dependencies:
- `config` (for `get_db_path`, `get_governance_dir_abs`,
  `get_project_root`, `get_father_project`).
- `scripts.bridgeV002.bridge_lib` (for bridge_lib functions and the
  inline-imported `list_scripts_from_db`, `list_conventions_from_db`,
  `resolve_convention_from_db`).

To avoid circular imports (app.py imports this router; this router
must not import app.py), DB_PATH is NOT imported from app. Each
endpoint calls `config.get_db_path()` directly — this honors the same
`TRADE_UI_DB_PATH` env override that app.py used via the module-level
`DB_PATH` constant.
"""