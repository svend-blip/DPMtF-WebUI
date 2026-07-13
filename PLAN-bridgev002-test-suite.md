# BridgeV002 Dispatch-Engine Test Suite Implementation Plan

> **For agentic workers:** Execute tasks in order. Steps use checkbox (`- [ ]`) syntax for tracking. Do not skip verification steps.

**Goal:** Create the first real test suite for the BridgeV002 dispatch engine (currently ZERO tests; `pytest.ini` even omits `scripts/bridgeV002/*` from coverage), testing the pure seams that need no tmux and no ollama.

**Architecture:** Tests import `dispatch.py`, `bridge_lib.py`, and `chain_watchdog.py` directly (import-safety verified below), feed them `tmp_path` filesystems and a temp SQLite DB created by the REAL migrations (`scripts/migrate.py` + `scripts/db/00X_*.sql`) so the schema stays honest, and monkeypatch the two runtime path sources (`config.get_trade_inbox_dir`, `$DPMTF_BRIDGE_DIR`). No production file is modified except `tests/conftest.py` (sys.path + fixture), `pytest.ini` (coverage scope), and the brittle assertions in `tests/test_migrate.py`.

**Tech Stack:** pytest, sqlite3, Python 3.12 stdlib.

## Cold-Start Context

- Project: **DPMtF-WebUI** ("Father"), FastAPI app on port **9130**, SQLite DB at `databases/dpmtf.db` (committed to the repo).
- Start app: `uvicorn app:app --host 0.0.0.0 --port 9130 --reload` from `/home/svend/DPMtF-WebUI`.
- Run tests: `python3 -m pytest -q`. Existing tests: `tests/test_health.py`, `tests/test_bridge_endpoints.py`, `tests/test_allocator_config_endpoints.py`, `tests/test_migrate.py`; fixtures in `tests/conftest.py` (temp-DB + `TestClient`).
- **Known baseline failure:** `tests/test_migrate.py` currently FAILS 2 tests (`test_migrate_idempotent`, `test_schema_migrations_tracks_baseline`) because they hardcode the migration list as `["001_baseline.sql", "002_drop_dead_tables.sql"]` while `scripts/db/` now also contains `003_model_allocator_fields.sql` and `004_role_runtime_config.sql`. Task 6 fixes this.
- Dispatch engine: `scripts/bridgeV002/{dispatch.py,bridge_lib.py,chain_watchdog.py,command_builder.py,start_coding.py}`. There is **no `__init__.py`** in `scripts/bridgeV002/` — imports need a `sys.path` insert.
- Governance: `docs/governance-templates-v2/`.

### Import-safety audit (performed against current source — this is the chosen approach)

- `dispatch.py`: module level only sets `PROJECT_ROOT`, inserts its own dir on `sys.path`, imports `bridge_lib`, and defines constants/functions; `main()` is guarded by `if __name__ == "__main__":`. **Import-safe — `app.py` already does `from dispatch import build_step_payload` in production.** → Tests import it directly.
- `bridge_lib.py`: module level inserts the project root on `sys.path` and does `import config`. `config.py` runs `_load_env()` at import, which loads `.env` into `os.environ` (notably `DPMTF_BRIDGE_DIR=/home/svend/flows` on this machine). **Consequence: any test touching bridge-dir-derived paths MUST `monkeypatch.setenv("DPMTF_BRIDGE_DIR", ...)`** — never rely on the ambient value. All DB functions under test accept an explicit `db_path=` override (verified: `get_next_id_for_flow`, `resolve_content_template_from_db`, `get_effective_model_source`, `load_role_from_db`, `resolve_convention_from_db`). → Import directly.
- `chain_watchdog.py`: module level executes `CHAIN = load_chain()` (a read-only `SELECT` against `PROJECT_ROOT/databases/dpmtf.db`; wrapped in `try/except Exception → CHAIN_FALLBACK`) and `_WD = _watchdog_profile()` (reads `profiles/machine.local.json`). NOTE: `sqlite3.connect` would create an empty DB file if `databases/dpmtf.db` were absent — it is committed to this repo, so import performs no write on a normal checkout. The functions under test (`inbox_dirs`, `find_output`, `latest_run_id`, `recent_signal_delivered`) resolve ALL paths at call time via `config.get_trade_inbox_dir()` / `$DPMTF_BRIDGE_DIR`, so per-test monkeypatching fully isolates them. → Import directly, monkeypatch per test; the import itself is additionally asserted side-effect-bounded in a subprocess test (Task 1).

## Global Constraints

- `python3 -m py_compile <file>` MUST pass on every touched `.py` file.
- Parameterized SQL only (`?` placeholders) — including in test seed helpers.
- No hardcoded `/home/svend/...` paths — tests derive paths from `Path(__file__)` and `tmp_path`.
- Schema changes ONLY via new `scripts/db/00X_*.sql` + `python3 scripts/migrate.py` (this plan creates NO schema change; tests CONSUME the real migrations).
- No new pip dependencies (pytest already in the venv).
- Frontend rules — not applicable, no frontend files touched.
- Tests must NEVER touch `databases/dpmtf.db` or the real trace log (`$DPMTF_BRIDGE_DIR/trace.log`) — everything goes through `tmp_path` + `monkeypatch`.
- `curl -s http://localhost:9130/api/health` returns `{"status":"healthy"}` after changes (only test/config files change, so this is a formality).
- Git: **Only the Human may commit.** Stage and STOP.

## Edge Cases a Weaker Model Would Miss

1. **`.env` is loaded at `import config` time and SETS `DPMTF_BRIDGE_DIR` globally.** A test of `recent_signal_delivered` that forgets `monkeypatch.setenv("DPMTF_BRIDGE_DIR", str(tmp_path))` silently reads the REAL `/home/svend/flows/trace.log` and becomes machine-dependent (and a production-data leak into tests). Every bridge-dir test sets the env var explicitly.
2. **No `__init__.py` in `scripts/bridgeV002/`** — `import dispatch` only works after `sys.path.insert`. Do it ONCE in `tests/conftest.py` at module level so all test files can import uniformly; ad-hoc inserts in individual files cause double-import of the same module under two names.
3. **In-memory SQLite (`:memory:`) cannot be shared across connections** — `bridge_lib` functions open their OWN `sqlite3.connect(db_path)` per call. The "in-memory DB fixture" pattern from `tests/conftest.py` actually uses a temp FILE, and so must the new fixture. Use `tmp_path`-backed files, never `":memory:"`.
4. **`sqlite3.Row` vs dict:** `load_role_from_db` sets `conn.row_factory = sqlite3.Row` and returns `dict(row)` — callers use `.get()`. A test asserting attribute access (`row.role_key`) would pass against `sqlite3.Row` but the contract is dict; assert with `["..."]`/`.get()` on the returned dict.
5. **`find_output` requires valid JSON WITH a `status` field** (chain_watchdog.py:109–127) — mere file existence is NOT completion (flow 067: 817-byte partial file). Tests must cover: partial/invalid JSON → `None`, JSON without `status` → `None`, and the `{run_id}_humantrade_{role}.json` alternate filename.
6. **`inbox_dirs` includes `rejected/` ON PURPOSE** (flow 070: a rejected file still means the chain advanced). A "cleanup-minded" test that expects only `pending/` would enshrine a regression. Also: `inbox_dirs` derives the base as `inbox.parent if inbox.name == "pending" else inbox` — test both shapes.
7. **`recent_signal_delivered` treats an UNPARSEABLE timestamp as "recent" (returns True)** — deliberate fail-safe (chain_watchdog.py:228: `return True  # unparseable timestamp: assume recent, stay safe`). Assert True for garbage timestamps; do not "fix" it in the test's image.
8. **`get_next_id_for_flow` returns the CURRENT counter value and then increments** — first call on a fresh flow returns 1 (auto-creating the row), second returns 2. On a DB where `bridge_id_counters` does not exist at all it returns 1 without raising (OperationalError fallback). Cover all three.
9. **`get_effective_model_source` fallback chain:** step override → role default → `(None, None)`; step value `"inherit_from_role"` (or NULL) falls through to the role; role value `"inherit_from_role"` is INVALID at role level and treated as None. The alias falls together with its source — a step override with source but NULL alias must return `(step_source, None)`, not mix in the role alias.
10. **`resolve_convention_from_db` raises `ValueError` for a missing rule but returns `{}` when the TABLE is missing**, while `resolve_content_template_from_db` returns `""` in both cases — asymmetric by design; test the actual behavior.
11. **Coverage config:** `pytest.ini` `[coverage:run]` has `source = app` and `omit = ... scripts/bridgeV002/* ...`. Just deleting the omit line is not enough to MEASURE the engine — `source` must include the package path too (Task 7 scopes it properly).
12. **`test_migrate.py` hardcodes the migration list** — every future `00X_*.sql` breaks it again. Fix by deriving expectations from `migrate._discover_migrations()` (Task 6) so migration plans (e.g. PLAN-id-counter-selfheal.md) stop tripping over it.

---

### Task 1: conftest additions + import-safety tests

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/tests/conftest.py`
- Create: `/home/svend/DPMtF-WebUI/tests/test_bridgev002_imports.py`

- [ ] Step 1: In `tests/conftest.py`, directly after the existing imports (line ~24, after `from fastapi.testclient import TestClient`), add:

```python
# ── sys.path for the BridgeV002 engine (scripts/bridgeV002 has no
#    __init__.py) and the scripts dir (migrate.py) ────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _extra in (_PROJECT_ROOT,
               _PROJECT_ROOT / "scripts",
               _PROJECT_ROOT / "scripts" / "bridgeV002"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))
```

- [ ] Step 2: At the END of `tests/conftest.py`, add the migrated-DB fixture (function-scoped: engine tests mutate counters):

```python
@pytest.fixture()
def migrated_db(tmp_path) -> str:
    """Fresh temp SQLite DB with the REAL schema applied via scripts/migrate.py
    (001_baseline + all later migrations) — keeps test schema honest.

    Function-scoped: BridgeV002 engine tests mutate counters/rows.
    """
    import migrate  # scripts/migrate.py (sys.path set above)

    db_path = str(tmp_path / "bridge_engine_test.db")
    migrate.run_migrations(db_path)
    return db_path
```

- [ ] Step 3: Create `tests/test_bridgev002_imports.py`:

```python
"""Import-safety tests for the BridgeV002 engine modules.

These are scripts, not a package: verify that importing them executes no
dispatch logic. Run in a subprocess so this test cannot be masked by
modules already cached in the pytest process.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_dispatch_and_bridge_lib_import_cleanly():
    code = (
        "import sys; "
        "sys.path.insert(0, 'scripts/bridgeV002'); "
        "import dispatch, bridge_lib; "
        "assert callable(dispatch.main); "
        "assert callable(bridge_lib.get_next_id_for_flow); "
        "print('IMPORT_OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "IMPORT_OK" in result.stdout
    # main() must NOT have run: it would print the --db-flow usage error.
    assert "--db-flow is required" not in result.stdout


def test_chain_watchdog_import_is_bounded():
    """chain_watchdog builds CHAIN at import (read-only SELECT against the
    committed repo DB, exception-guarded). Importing must succeed and yield
    a usable chain, and must not write anything to the repo."""
    code = (
        "import sys; "
        "sys.path.insert(0, 'scripts/bridgeV002'); "
        "import chain_watchdog as cw; "
        "assert isinstance(cw.CHAIN, list) and len(cw.CHAIN) >= 2; "
        "assert cw.MAX_NUDGES_PER_STEP >= 1; "
        "print('WATCHDOG_IMPORT_OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "WATCHDOG_IMPORT_OK" in result.stdout
```

- [ ] Step 4: Run `python3 -m pytest tests/test_bridgev002_imports.py -q` — expected: `2 passed`.
- [ ] Step 5: `python3 -m py_compile tests/conftest.py tests/test_bridgev002_imports.py` — exit 0. Also confirm the existing suite still collects: `python3 -m pytest -q --collect-only | tail -3`.

---

### Task 2: `bridge_lib` ID counter + lookup tests

**Files:**
- Create: `/home/svend/DPMtF-WebUI/tests/test_bridge_lib.py`

**Interfaces consumed (verified signatures):**
- `get_next_id_for_flow(flow_key, db_path=None) -> int` (bridge_lib.py:262)
- `resolve_content_template_from_db(rule_key, db_path=None) -> str` (bridge_lib.py:665)
- `resolve_convention_from_db(rule_key, db_path=None) -> dict` (bridge_lib.py:631)
- `get_effective_model_source(role_key, step_key=None, flow_key=None, db_path=None) -> tuple` (bridge_lib.py:420)
- `load_role_from_db(role_name, db_path=None) -> dict` (bridge_lib.py:364)

- [ ] Step 1: Create `tests/test_bridge_lib.py`:

```python
"""Unit tests for bridge_lib DB seams — real migrated schema, temp DB file."""

import sqlite3

import bridge_lib


def _exec(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


# ── get_next_id_for_flow ─────────────────────────────────────────────

def test_next_id_auto_creates_and_increments(migrated_db):
    assert bridge_lib.get_next_id_for_flow("t_flow", db_path=migrated_db) == 1
    assert bridge_lib.get_next_id_for_flow("t_flow", db_path=migrated_db) == 2
    assert bridge_lib.get_next_id_for_flow("t_flow", db_path=migrated_db) == 3


def test_next_id_flows_are_isolated(migrated_db):
    assert bridge_lib.get_next_id_for_flow("flow_a", db_path=migrated_db) == 1
    assert bridge_lib.get_next_id_for_flow("flow_b", db_path=migrated_db) == 1
    assert bridge_lib.get_next_id_for_flow("flow_a", db_path=migrated_db) == 2


def test_next_id_respects_existing_counter(migrated_db):
    _exec(migrated_db,
          "INSERT INTO bridge_id_counters (flow_key, next_id) VALUES (?, ?)",
          ("preset", 42))
    assert bridge_lib.get_next_id_for_flow("preset", db_path=migrated_db) == 42
    assert bridge_lib.get_next_id_for_flow("preset", db_path=migrated_db) == 43


def test_next_id_missing_table_returns_1(tmp_path):
    empty_db = str(tmp_path / "empty.db")
    sqlite3.connect(empty_db).close()  # file exists, zero tables
    assert bridge_lib.get_next_id_for_flow("x", db_path=empty_db) == 1


# ── resolve_content_template_from_db ─────────────────────────────────

def _seed_convention(db_path, rule_key, content_template=None):
    _exec(db_path,
          "INSERT INTO bridge_convention_rules "
          "(rule_key, step_type, dir_template, pattern_template, "
          " content_template) VALUES (?, ?, ?, ?, ?)",
          (rule_key, "handoff", "{flow_key}/handoffs",
           "{ID}-handoff.md", content_template))


def test_content_template_roundtrip(migrated_db):
    _seed_convention(migrated_db, "t_rule",
                     "Hello {next_role}, run {flow_run_id}")
    out = bridge_lib.resolve_content_template_from_db(
        "t_rule", db_path=migrated_db)
    assert out == "Hello {next_role}, run {flow_run_id}"


def test_content_template_missing_rule_is_empty(migrated_db):
    assert bridge_lib.resolve_content_template_from_db(
        "nope", db_path=migrated_db) == ""


def test_content_template_null_column_is_empty(migrated_db):
    _seed_convention(migrated_db, "no_tmpl", content_template=None)
    assert bridge_lib.resolve_content_template_from_db(
        "no_tmpl", db_path=migrated_db) == ""


def test_resolve_convention_missing_rule_raises(migrated_db):
    import pytest
    with pytest.raises(ValueError):
        bridge_lib.resolve_convention_from_db("nope", db_path=migrated_db)


# ── get_effective_model_source (step -> role -> default) ─────────────

def _seed_role(db_path, role_key, source=None, alias=None):
    _exec(db_path,
          "INSERT INTO bridge_roles (role_key, tmux_session, model_type, "
          "ollama_model, default_model_source, default_model_alias, "
          "is_active) VALUES (?, ?, 'ollama', 'qwen-test:7b', ?, ?, 1)",
          (role_key, role_key, source, alias))


def _seed_flow_step(db_path, flow_key, step_key, from_role, to_role,
                    model_source=None, model_alias=None):
    _exec(db_path,
          "INSERT INTO bridge_flows (flow_key, name, is_active) "
          "VALUES (?, ?, 1)", (flow_key, flow_key))
    _exec(db_path,
          "INSERT INTO bridge_flow_steps (flow_key, step_key, from_role, "
          "to_role, model_source, model_alias, is_active) "
          "VALUES (?, ?, ?, ?, ?, ?, 1)",
          (flow_key, step_key, from_role, to_role,
           model_source, model_alias))


def test_model_source_role_default(migrated_db):
    _seed_role(migrated_db, "r1", source="model_allocator", alias="r1-local")
    assert bridge_lib.get_effective_model_source(
        "r1", db_path=migrated_db) == ("model_allocator", "r1-local")


def test_model_source_step_override_wins(migrated_db):
    _seed_role(migrated_db, "r2", source="direct_ollama", alias=None)
    _seed_flow_step(migrated_db, "f2", "s2", "r2", "other",
                    model_source="model_allocator", model_alias="step-alias")
    assert bridge_lib.get_effective_model_source(
        "r2", step_key="s2", flow_key="f2",
        db_path=migrated_db) == ("model_allocator", "step-alias")


def test_model_source_step_inherit_falls_to_role(migrated_db):
    _seed_role(migrated_db, "r3", source="direct_ollama", alias="role-alias")
    _seed_flow_step(migrated_db, "f3", "s3", "r3", "other",
                    model_source="inherit_from_role", model_alias=None)
    assert bridge_lib.get_effective_model_source(
        "r3", step_key="s3", flow_key="f3",
        db_path=migrated_db) == ("direct_ollama", "role-alias")


def test_model_source_role_inherit_is_invalid_means_none(migrated_db):
    _seed_role(migrated_db, "r4", source="inherit_from_role", alias="x")
    assert bridge_lib.get_effective_model_source(
        "r4", db_path=migrated_db) == (None, None)


def test_model_source_unknown_role_is_none(migrated_db):
    assert bridge_lib.get_effective_model_source(
        "ghost", db_path=migrated_db) == (None, None)


# ── load_role_from_db (dict contract, sqlite3.Row internally) ────────

def test_load_role_returns_plain_dict(migrated_db):
    _seed_role(migrated_db, "r5")
    role = bridge_lib.load_role_from_db("r5", db_path=migrated_db)
    assert isinstance(role, dict)
    assert role["role_key"] == "r5"
    assert role["tmux_session"] == "r5"
    assert role.get("model_type") == "ollama"


def test_load_role_inactive_or_missing_raises(migrated_db):
    import pytest
    with pytest.raises(ValueError):
        bridge_lib.load_role_from_db("missing", db_path=migrated_db)
```

- [ ] Step 2: Run `python3 -m pytest tests/test_bridge_lib.py -q` — expected: all pass (`15 passed`). If `test_resolve_convention_missing_rule_raises` fails because `{}` is returned instead of a raise, re-read `resolve_convention_from_db` in the CURRENT source: the `raise ValueError` sits inside the `try:` whose `except sqlite3.OperationalError` returns `{}` — a `ValueError` is NOT caught there, so it propagates; if behavior differs, adjust the test to the actual source and note it.

---

### Task 3: `chain_watchdog` pure-seam tests

**Files:**
- Create: `/home/svend/DPMtF-WebUI/tests/test_chain_watchdog.py`

- [ ] Step 1: Create `tests/test_chain_watchdog.py`:

```python
"""Unit tests for chain_watchdog's pure seams — tmp inbox + tmp trace.log.

ALWAYS monkeypatch config.get_trade_inbox_dir and DPMTF_BRIDGE_DIR:
importing config loaded .env, which points both at real machine paths.
"""

import json
import time
from datetime import datetime, timezone, timedelta

import pytest

import chain_watchdog as cw


@pytest.fixture()
def inbox(tmp_path, monkeypatch):
    """Isolated pending/processed/rejected inbox; returns the base dir."""
    base = tmp_path / "inbox"
    for sub in ("pending", "processed", "rejected"):
        (base / sub).mkdir(parents=True)
    monkeypatch.setattr(cw.config, "get_trade_inbox_dir",
                        lambda: str(base / "pending"))
    return base


def _write_output(path, status="completed"):
    path.write_text(json.dumps({"status": status, "payload": {}}),
                    encoding="utf-8")


# ── inbox_dirs ───────────────────────────────────────────────────────

def test_inbox_dirs_includes_rejected(inbox):
    dirs = cw.inbox_dirs()
    names = [d.name for d in dirs]
    assert names == ["pending", "processed", "rejected"]
    assert all(str(d).startswith(str(inbox)) for d in dirs)


def test_inbox_dirs_handles_non_pending_configured_dir(tmp_path, monkeypatch):
    """When the configured inbox is NOT named 'pending', it is the base."""
    base = tmp_path / "flatbox"
    base.mkdir()
    monkeypatch.setattr(cw.config, "get_trade_inbox_dir", lambda: str(base))
    dirs = cw.inbox_dirs()
    assert dirs[0] == base / "pending"
    assert dirs[2] == base / "rejected"


# ── find_output ──────────────────────────────────────────────────────

def test_find_output_valid_json_with_status(inbox):
    _write_output(inbox / "pending" / "072_trend01_trade.json")
    p = cw.find_output("trend01_trade", "072")
    assert p is not None and p.name == "072_trend01_trade.json"


def test_find_output_rejected_still_counts(inbox):
    """A rejected deliverable HAS advanced the chain (flow 070)."""
    _write_output(inbox / "rejected" / "072_risk01_trade.json")
    assert cw.find_output("risk01_trade", "072") is not None


def test_find_output_partial_json_is_ignored(inbox):
    (inbox / "pending" / "072_market01_trade.json").write_text(
        '{"status": "compl', encoding="utf-8")  # truncated mid-write
    assert cw.find_output("market01_trade", "072") is None


def test_find_output_json_without_status_is_ignored(inbox):
    (inbox / "pending" / "072_sim01_trade.json").write_text(
        json.dumps({"payload": {}}), encoding="utf-8")
    assert cw.find_output("sim01_trade", "072") is None


def test_find_output_humantrade_variant_name(inbox):
    _write_output(inbox / "pending" / "072_humantrade_trend01_trade.json")
    assert cw.find_output("trend01_trade", "072") is not None


def test_find_output_missing_returns_none(inbox):
    assert cw.find_output("trend01_trade", "999") is None


# ── latest_run_id ────────────────────────────────────────────────────

def test_latest_run_id_zero_pads(inbox):
    _write_output(inbox / "pending" / "71_trend01_trade.json")
    _write_output(inbox / "processed" / "072_sim01_trade.json")
    assert cw.latest_run_id() == "072"


def test_latest_run_id_empty_inbox(inbox):
    assert cw.latest_run_id() is None


# ── recent_signal_delivered ──────────────────────────────────────────

def _trace_line(ts_text, role, next_role, run_id,
                status="signal_complete"):
    return (f"{ts_text} | {role}->{next_role} | {run_id} | {status} | "
            f"manual | Callback dispatched (test)\n")


def _write_trace(tmp_path, monkeypatch, lines):
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", str(tmp_path))
    (tmp_path / "trace.log").write_text("".join(lines), encoding="utf-8")


def test_recent_signal_true_for_fresh_line(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_trace(tmp_path, monkeypatch,
                 [_trace_line(now, "a", "b", "072")])
    assert cw.recent_signal_delivered("a", "b", "072", 30) is True


def test_recent_signal_false_for_old_line(tmp_path, monkeypatch):
    old = (datetime.now(timezone.utc) - timedelta(hours=5)
           ).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_trace(tmp_path, monkeypatch,
                 [_trace_line(old, "a", "b", "072")])
    assert cw.recent_signal_delivered("a", "b", "072", 30) is False


def test_recent_signal_unparseable_timestamp_assumes_recent(tmp_path,
                                                            monkeypatch):
    """Deliberate fail-safe: garbage timestamp -> True (stay safe)."""
    _write_trace(tmp_path, monkeypatch,
                 [_trace_line("NOT-A-TIMESTAMP", "a", "b", "072")])
    assert cw.recent_signal_delivered("a", "b", "072", 30) is True


def test_recent_signal_wrong_status_does_not_match(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_trace(tmp_path, monkeypatch,
                 [_trace_line(now, "a", "b", "072",
                              status="signal_complete_failed")])
    assert cw.recent_signal_delivered("a", "b", "072", 30) is False


def test_recent_signal_missing_trace_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", str(tmp_path / "nowhere"))
    assert cw.recent_signal_delivered("a", "b", "072", 30) is False
```

- [ ] Step 2: Run `python3 -m pytest tests/test_chain_watchdog.py -q` — all pass (`15 passed`).

---

### Task 4: `dispatch` pure-helper tests

**Files:**
- Create: `/home/svend/DPMtF-WebUI/tests/test_dispatch_helpers.py`

Helpers under test (all verified import-safe, no tmux/DB when given complete inputs): `_resolve_existing_target` (~578), `build_step_payload` (~671 — skips ALL DB lookups when the step dict provides `deliverable_dir`, `deliverable_pattern`, `error_msg` and has no `rule_key`), `step_to_cli_args` (~756), `_extract_watch_symbols` (~112), `_extract_candidate_proposals` (~66).

- [ ] Step 1: Create `tests/test_dispatch_helpers.py`:

```python
"""Unit tests for dispatch.py's pure decision helpers (no tmux, no DB)."""

import json

import dispatch


# ── _resolve_existing_target (zero-pad symlink healing) ──────────────

def test_resolve_existing_target_prefers_original(tmp_path):
    sub = tmp_path / "pending"
    sub.mkdir()
    (sub / "42_trend01_trade.json").write_text("{}", encoding="utf-8")
    out = dispatch._resolve_existing_target(str(tmp_path), "pending",
                                            "42_trend01_trade.json")
    assert out == "42_trend01_trade.json"


def test_resolve_existing_target_falls_back_to_zero_padded(tmp_path):
    sub = tmp_path / "pending"
    sub.mkdir()
    (sub / "042_trend01_trade.json").write_text("{}", encoding="utf-8")
    out = dispatch._resolve_existing_target(str(tmp_path), "pending",
                                            "42_trend01_trade.json")
    assert out == "042_trend01_trade.json"


def test_resolve_existing_target_neither_exists_returns_input(tmp_path):
    (tmp_path / "pending").mkdir()
    out = dispatch._resolve_existing_target(str(tmp_path), "pending",
                                            "42_trend01_trade.json")
    assert out == "42_trend01_trade.json"


# ── build_step_payload (fully-specified step: no DB access) ──────────

_STEP = {
    "step_key": "trend01-market01",
    "from_role": "trend01_trade",
    "to_role": "market01_trade",
    "deliverable_dir": "trade/inbox/pending",
    "deliverable_pattern": "{ID}_{role_key}.json",
    "error_msg": "delivery failed",
    "rule_key": None,
}


def test_build_step_payload_resolves_deliverable_file():
    payload = dispatch.build_step_payload(_STEP, "test_flow", "072",
                                          "/tmp/bridge-x")
    assert payload["deliverable_file"] == "072_trend01_trade.json"
    assert payload["deliverable_dir"] == "trade/inbox/pending"
    assert payload["from_role"] == "trend01_trade"
    assert payload["to_role"] == "market01_trade"
    assert payload["handoff_id"] == "072"
    assert payload["bridge_dir"] == "/tmp/bridge-x"
    assert payload["error_msg"] == "delivery failed"
    assert payload["prompt_template"] == ""


def test_step_to_cli_args_round_trip():
    payload = dispatch.build_step_payload(_STEP, "test_flow", "072",
                                          "/tmp/bridge-x")
    args = dispatch.step_to_cli_args(payload)
    assert "--flow-key" in args and "test_flow" in args
    assert "--deliverable-file" in args
    assert args[args.index("--deliverable-file") + 1] == \
        "072_trend01_trade.json"
    assert "--handoff-id" in args
    assert args[args.index("--handoff-id") + 1] == "072"


# ── trade-mcp deliverable extractors ─────────────────────────────────

def _write_json(tmp_path, data):
    p = tmp_path / "deliverable.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_extract_watch_symbols_dedup_and_upper(tmp_path):
    path = _write_json(tmp_path, {"payload": {"symbols": [
        {"symbol": "nvda"}, "amd", {"symbol": "NVDA"}, {"noise": 1}]}})
    assert dispatch._extract_watch_symbols(path) == ["NVDA", "AMD"]


def test_extract_watch_symbols_top_level_fallback(tmp_path):
    path = _write_json(tmp_path, {"symbols": ["tsm"]})
    assert dispatch._extract_watch_symbols(path) == ["TSM"]


def test_extract_candidates_filters_watchlist_only(tmp_path):
    path = _write_json(tmp_path, {"payload": {"candidates": [
        {"symbol": "amd", "candidate_action": "WATCHLIST_ONLY"},
        {"symbol": "nvda", "candidate_action": "SIMULATED_BUY_CANDIDATE",
         "entry_price": 100.0, "stop_loss": 90.0},
    ]}})
    props = dispatch._extract_candidate_proposals(path)
    assert props == [{"symbol": "NVDA", "entry": 100.0, "stop": 90.0}]


def test_extract_candidates_legacy_single_shape(tmp_path):
    path = _write_json(tmp_path, {"payload": {
        "symbol": "tsm", "entry_price": 50.0, "stop_loss": 45.0}})
    props = dispatch._extract_candidate_proposals(path)
    assert props == [{"symbol": "TSM", "entry": 50.0, "stop": 45.0}]


def test_extract_candidates_empty_payload(tmp_path):
    path = _write_json(tmp_path, {"payload": {}})
    assert dispatch._extract_candidate_proposals(path) == []
```

- [ ] Step 2: Run `python3 -m pytest tests/test_dispatch_helpers.py -q` — all pass (`10 passed`).

---

### Task 5: Guard test — dispatch helpers never touch the real DB in these tests

- [ ] Step 1: Append to `tests/test_dispatch_helpers.py`:

```python
def test_build_step_payload_fully_specified_step_needs_no_db(monkeypatch):
    """When the step row carries dir/pattern/error and no rule_key,
    build_step_payload must not open ANY database."""
    def boom(*a, **k):
        raise AssertionError("DB access attempted")

    monkeypatch.setattr(dispatch, "resolve_convention_from_db", boom)
    monkeypatch.setattr(dispatch, "_db_path", boom)
    payload = dispatch.build_step_payload(_STEP, "f", "007", "/tmp/b")
    assert payload["deliverable_file"] == "007_trend01_trade.json"
```

- [ ] Step 2: Run `python3 -m pytest tests/test_dispatch_helpers.py -q` — all pass (`11 passed`).

---

### Task 6: Fix the brittle `test_migrate.py` assertions (currently failing)

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/tests/test_migrate.py`

- [ ] Step 1: Replace `test_migrate_idempotent` (lines 39–46) with:

```python
def test_migrate_idempotent(temp_db_path):
    expected = [p.name for p in migrate._discover_migrations()]
    assert expected, "no migrations discovered — scripts/db/ missing?"
    assert expected[0] == "001_baseline.sql"

    first = migrate.run_migrations(temp_db_path)
    assert first["applied"] == expected
    assert first["skipped"] == 0

    second = migrate.run_migrations(temp_db_path)
    assert second["applied"] == []
    assert second["skipped"] == len(expected)
```

- [ ] Step 2: Replace `test_schema_migrations_tracks_baseline` (lines 97–110) with:

```python
def test_schema_migrations_tracks_baseline(temp_db_path):
    expected = {p.name for p in migrate._discover_migrations()}
    migrate.run_migrations(temp_db_path)
    conn = sqlite3.connect(temp_db_path)
    try:
        rows = conn.execute(
            "SELECT filename, applied_at FROM schema_migrations"
        ).fetchall()
        assert {row[0] for row in rows} == expected
        for _, applied_at in rows:
            assert applied_at is not None and len(applied_at) > 0
    finally:
        conn.close()
```

- [ ] Step 3: Run `python3 -m pytest tests/test_migrate.py -q` — expected: `6 passed` (the 2 previous failures are gone; future `00X_*.sql` files no longer break these tests).

---

### Task 7: Scope coverage properly in `pytest.ini`

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/pytest.ini`

- [ ] Step 1: Replace the `[coverage:run]` section (currently `source = app` plus an `omit` list including `scripts/bridgeV002/*`) with:

```ini
[coverage:run]
source =
    app
    routers
    scripts/bridgeV002
omit =
    tests/*
    venv/*
    __pycache__/*
```

The `scripts/bridgeV002/*` omit line is REMOVED — the engine is now measured whenever coverage runs (e.g. `python3 -m pytest --cov --cov-config=pytest.ini`, if `pytest-cov` is available in the venv; plain `python3 -m pytest` is unaffected by this section).
- [ ] Step 2: Verify pytest still runs with the edited ini: `python3 -m pytest -q` — full suite passes (all new tests + fixed migrate tests; expected: `59 passed` or similar, ZERO failures).

---

### Task 8: Stage and stop

- [ ] Step 1: `git diff --stat` — expected: `tests/conftest.py`, `tests/test_migrate.py`, `pytest.ini` modified; `tests/test_bridgev002_imports.py`, `tests/test_bridge_lib.py`, `tests/test_chain_watchdog.py`, `tests/test_dispatch_helpers.py` new. NO change under `scripts/`.
- [ ] Step 2: Stage with `git add tests/conftest.py tests/test_migrate.py pytest.ini tests/test_bridgev002_imports.py tests/test_bridge_lib.py tests/test_chain_watchdog.py tests/test_dispatch_helpers.py` and STOP — await Human commit approval. Suggested commit message: `[hardening] first BridgeV002 engine test suite (43 tests) + coverage scope + migrate-test fix`.

## Acceptance Criteria

1. `python3 -m pytest -q` — entire suite passes with ZERO failures (the 2 pre-existing `test_migrate.py` failures are fixed by Task 6).
2. `python3 -m pytest tests/test_bridgev002_imports.py tests/test_bridge_lib.py tests/test_chain_watchdog.py tests/test_dispatch_helpers.py -q` — `43 passed`.
3. `grep -n "scripts/bridgeV002" pytest.ini` — the ONLY hit is under `source =` (none under `omit`).
4. Isolation proof: `python3 -m pytest -q` leaves `databases/dpmtf.db` untouched — `git status --porcelain databases/dpmtf.db` prints nothing new after a test run, and the real trace log's mtime is unchanged: `stat -c %y "$(python3 -c 'import config,os;print(os.path.join(os.environ.get("DPMTF_BRIDGE_DIR","~/.bridge"),"trace.log"))")"` before/after.
5. `python3 -m py_compile tests/conftest.py tests/test_migrate.py` — exit 0.
6. `curl -s http://localhost:9130/api/health` returns `{"status":"healthy"}`.
