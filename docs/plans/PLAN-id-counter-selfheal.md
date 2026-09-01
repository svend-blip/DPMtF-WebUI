# Self-Healing bridge_id_counters Implementation Plan

> **For agentic workers:** Execute tasks in order. Steps use checkbox (`- [ ]`) syntax for tracking. Do not skip verification steps.

**Goal:** Make `bridge_id_counters` self-healing so `next_id` can never lag behind the ids actually used on disk (cloud_pay is stuck at 53 while real handoffs reached 72 — forcing manual `--id` on every dispatch).

**Architecture:** A new `bridge_lib.reconcile_id_counter(flow_key, db_path=None) -> dict` computes the maximum observed id for a flow from durable evidence — every active step's deliverable directory (patterns from `bridge_flow_steps.deliverable_dir` / `deliverable_pattern`, including `processed/`/`rejected/` siblings for inbox-style dirs) plus the cycle-state JSON files' `last_handoff` — and raises `next_id` to `max+1` when the counter is behind (never lowers it). `get_next_id_for_flow` calls it before every allocation (cheap self-heal), and the allocation itself is hardened to a single `BEGIN IMMEDIATE` transaction. A new `dispatch.py --reconcile-counters [--db-flow X]` CLI prints per-flow before/after for manual audits.

**Tech Stack:** Python 3.12 stdlib (`sqlite3`, `re`, `os`, `json`), SQLite, pytest.

## Cold-Start Context

- Project: **DPMtF-WebUI** ("Father"), FastAPI app on port **9130**, SQLite DB at `databases/dpmtf.db` (committed).
- Start app: `uvicorn app:app --host 0.0.0.0 --port 9130 --reload` from `/home/svend/DPMtF-WebUI`.
- Run tests: `python3 -m pytest -q`. Fixtures: `tests/conftest.py`. Real schema comes from `scripts/migrate.py` + `scripts/db/00X_*.sql` (001–004 exist today; **this plan needs NO new migration** — no schema change, only code + data healing).
- Key files: `scripts/bridgeV002/bridge_lib.py` (`get_next_id_for_flow` at line ~262 — reads `bridge_id_counters.next_id`, returns it, then increments), `scripts/bridgeV002/dispatch.py` (`main()` at ~2033 auto-allocates via `get_next_id_for_flow` when `--id` is omitted; explicit `--id` is normalized by stripping non-leading digits).
- Bridge layout: `$DPMTF_BRIDGE_DIR` (this machine: `/home/svend/flows`, set in `.env`, loaded by `config.py` at import). Flow evidence on disk, per `bridge_flow_steps` (live rows verified):
  - `strict_review` / `cloud_llm`: ABSOLUTE `deliverable_dir` (e.g. `/home/svend/flows/strict_review/handoffs`), patterns `{ID}-handoff.md`, `{ID}-result.md`, `{ID}-review01.md`, `{ID}-verdict.md`.
  - `cloud_pay`: RELATIVE `deliverable_dir` (`cloud_pay/handoffs`, …) joined against the bridge dir.
  - trade flows: ABSOLUTE inbox `…/trade-ui/inbox/pending`, pattern `{ID}_{role_key}.json`; the import pipeline MOVES files to sibling `processed/` and `rejected/` dirs.
- Cycle-state JSON evidence: `scripts/docs/bridgeV002/current-cycle.json` (written by `dispatch._update_cycle_state`; fields `flow`, `last_handoff`) and per-flow `docs/bridgeV002/current-cycle-<flow-with-hyphens>.json` (e.g. `current-cycle-cloud-pay.json` has `"last_handoff": 72`).
- Live counter state (verified 2026-07-12): `strict_review=228` (files max 227 — healthy), `cloud_llm=3`, `cloud_pay=53` (files max 72 — **behind by 19**), `trade_cockpit_simulation_v001=73` (files max 072 — healthy), `trade_cockpit_scoring_v001=2`.

## Global Constraints

- `python3 -m py_compile <file>` MUST pass on every touched `.py` file.
- Parameterized SQL only (`?` placeholders).
- No hardcoded `/home/svend/...` paths — bridge dir via `$DPMTF_BRIDGE_DIR` / `config.get_bridge_base_path()`, project root via `bridge_lib._find_project_root()`.
- Schema changes ONLY via new `scripts/db/00X_*.sql` + `python3 scripts/migrate.py` — this plan makes NONE (data-only UPDATE of counter rows at runtime).
- No new pip dependencies.
- Frontend rules — not applicable; no frontend files touched.
- Tests must NOT touch `databases/dpmtf.db` or real bridge dirs — `tmp_path` + explicit `db_path`/`bridge_dir`/`project_root` parameters everywhere.
- `curl -s http://localhost:9130/api/health` returns `{"status":"healthy"}` after changes (app.py imports bridge_lib + dispatch).
- Git: **Only the Human may commit.** Stage and STOP.

## Edge Cases a Weaker Model Would Miss

1. **`next_id` stores the NEXT id to hand out, not the last used.** `get_next_id_for_flow` returns the CURRENT value then increments. So with files up to 72, the healed value is `next_id = 73` — `max_observed + 1`, not `max_observed`. Off-by-one here re-collides the very next dispatch.
2. **Only ever RAISE the counter, never lower it.** A flow whose directories are empty (archived, wiped, or a fresh machine) must not reset a healthy counter — `strict_review` at 228 with files up to 227 must stay 228. Guard: update only when `next_id < max_observed + 1`, and skip entirely when `max_observed == 0`.
3. **Zero-padded vs bare filename ids.** `cloud_pay` handoffs are bare (`72-handoff.md`), trade outputs are zero-padded (`072_trend01_trade.json`). Parse with `int(...)` from a `(\d+)` capture so `"072"` and `"72"` compare as the same number.
4. **Ids live in MULTIPLE directories** — a flow's max may be in `verdicts/` while `handoffs/` lags (or in `rejected/` only, for a gate-rejected trade run). Take the max across every step's dir AND the `processed/`/`rejected/` siblings of any dir named `pending`.
5. **`last_handoff` values carry suffixes and mixed types.** Observed: `"072"` (str), `72` (int), and the flow-064 pollution shape `"064_humantrade"`. Parse with `re.match(r"^(\d+)", str(value))` — leading digits only; no match → ignore that source.
6. **Missing directories must not crash** (fresh checkouts, moved inboxes) — skip with a log line to stderr, keep scanning the rest. Same for missing/corrupt cycle JSON files.
7. **The per-flow cycle file only counts if it belongs to this flow.** `scripts/docs/bridgeV002/current-cycle.json` has a `flow` field — compare it against `flow_key` before using `last_handoff`. The `docs/bridgeV002/current-cycle-<flow>.json` filename encodes the flow with HYPHENS (`cloud_pay` → `current-cycle-cloud-pay.json`) — translate with `flow_key.replace("_", "-")`.
8. **Concurrency: read-and-update must be one transaction.** Two dispatches allocating simultaneously on Python's default autocommit-ish isolation can both read the same `next_id`. Use `conn.isolation_level = None` + explicit `BEGIN IMMEDIATE` (acquires the write lock up front) in BOTH `reconcile_id_counter` and the hardened `get_next_id_for_flow`. Directory scanning happens BEFORE the transaction opens — never hold the write lock during filesystem walks.
9. **Pattern-to-regex conversion must escape everything else.** `{ID}-handoff.md` contains `.` — build the regex from `re.escape(pattern)` then substitute the escaped `\{ID\}` / `\{role_key\}` tokens; anchor with `^...$` so `72-handoff.md.bak` and `current.md` never match.
10. **`get_next_id_for_flow` must keep its "missing table → return 1" behavior** (bridge_lib.py:322–324) — `trade-cronjob.sh` and `scoring-cronjob.sh` call it inline at 09:00 cron and "must never die here". The reconcile hook is wrapped so ANY exception degrades to a stderr warning, not a crash.
11. **`dispatch.py main()` requires `--db-flow` for everything else** (exits 1 without it). The new `--reconcile-counters` mode must be handled BEFORE that check, since it can meaningfully run for ALL flows (`--db-flow` optional as a filter).
12. **`tests/test_migrate.py` currently hardcodes the migration list and already fails** with 003/004 present. This plan adds no migration, so it changes nothing there — but do not be confused by those 2 pre-existing failures when running the suite (PLAN-bridgev002-test-suite.md Task 6 fixes them).

---

### Task 1: TDD — tests for `_ids_from_directory` and `reconcile_id_counter`

**Files:**
- Create: `/home/svend/DPMtF-WebUI/tests/test_id_counter_selfheal.py`

- [ ] Step 1: Create `tests/test_id_counter_selfheal.py`:

```python
"""Tests for the self-healing bridge_id_counters (reconcile + allocation).

Everything runs against tmp_path dirs and a temp DB built by the REAL
migrations — never against databases/dpmtf.db or real bridge dirs.
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _p in (PROJECT_ROOT, PROJECT_ROOT / "scripts",
           PROJECT_ROOT / "scripts" / "bridgeV002"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bridge_lib  # noqa: E402
import migrate  # noqa: E402


@pytest.fixture()
def bridge_db(tmp_path):
    """Temp DB with the real schema (001_baseline + later migrations)."""
    db_path = str(tmp_path / "selfheal_test.db")
    migrate.run_migrations(db_path)
    return db_path


def _exec(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _counter(db_path, flow_key):
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT next_id FROM bridge_id_counters WHERE flow_key = ?",
            (flow_key,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _seed_flow(db_path, flow_key, steps):
    """steps: list of (step_key, deliverable_dir, deliverable_pattern)."""
    _exec(db_path,
          "INSERT INTO bridge_flows (flow_key, name, is_active) "
          "VALUES (?, ?, 1)", (flow_key, flow_key))
    for i, (step_key, ddir, patt) in enumerate(steps, start=1):
        _exec(db_path,
              "INSERT INTO bridge_flow_steps (flow_key, step_key, "
              "from_role, to_role, deliverable_dir, deliverable_pattern, "
              "sort_order, is_active) VALUES (?, ?, 'a', 'b', ?, ?, ?, 1)",
              (flow_key, step_key, ddir, patt, i))


# ── _ids_from_directory ──────────────────────────────────────────────

def test_ids_from_directory_bare_and_padded(tmp_path):
    d = tmp_path / "handoffs"
    d.mkdir()
    for name in ("6-handoff.md", "72-handoff.md", "072-handoff.md",
                 "current.md", "72-handoff.md.bak", "notes.txt"):
        (d / name).write_text("x", encoding="utf-8")
    ids = bridge_lib._ids_from_directory(str(d), "{ID}-handoff.md")
    assert sorted(ids) == [6, 72, 72]  # padded and bare both parse as 72


def test_ids_from_directory_role_key_pattern(tmp_path):
    d = tmp_path / "pending"
    d.mkdir()
    (d / "072_trend01_trade.json").write_text("{}", encoding="utf-8")
    (d / "071_humantrade.json").write_text("{}", encoding="utf-8")
    ids = bridge_lib._ids_from_directory(str(d), "{ID}_{role_key}.json")
    assert sorted(ids) == [71, 72]


def test_ids_from_directory_missing_dir(tmp_path):
    assert bridge_lib._ids_from_directory(
        str(tmp_path / "nope"), "{ID}-handoff.md") == []


def test_ids_from_directory_pattern_without_id_token(tmp_path):
    (tmp_path / "x.md").write_text("x", encoding="utf-8")
    assert bridge_lib._ids_from_directory(str(tmp_path), "static-name.md") == []


# ── reconcile_id_counter ─────────────────────────────────────────────

def test_reconcile_raises_lagging_counter(bridge_db, tmp_path):
    bdir = tmp_path / "bridge"
    (bdir / "pay/handoffs").mkdir(parents=True)
    (bdir / "pay/verdicts").mkdir(parents=True)
    (bdir / "pay/handoffs" / "72-handoff.md").write_text("x")
    (bdir / "pay/verdicts" / "70-verdict.md").write_text("x")
    _seed_flow(bridge_db, "payflow",
               [("s1", "pay/handoffs", "{ID}-handoff.md"),
                ("s2", "pay/verdicts", "{ID}-verdict.md")])
    _exec(bridge_db, "INSERT INTO bridge_id_counters (flow_key, next_id) "
                     "VALUES ('payflow', 53)")

    result = bridge_lib.reconcile_id_counter(
        "payflow", db_path=bridge_db, bridge_dir=str(bdir),
        project_root=str(tmp_path / "noproj"))

    assert result["max_observed"] == 72
    assert result["counter_before"] == 53
    assert result["counter_after"] == 73
    assert result["changed"] is True
    assert _counter(bridge_db, "payflow") == 73


def test_reconcile_never_lowers_healthy_counter(bridge_db, tmp_path):
    bdir = tmp_path / "bridge"
    (bdir / "sr/handoffs").mkdir(parents=True)
    (bdir / "sr/handoffs" / "227-handoff.md").write_text("x")
    _seed_flow(bridge_db, "sr", [("s1", "sr/handoffs", "{ID}-handoff.md")])
    _exec(bridge_db, "INSERT INTO bridge_id_counters (flow_key, next_id) "
                     "VALUES ('sr', 228)")
    result = bridge_lib.reconcile_id_counter(
        "sr", db_path=bridge_db, bridge_dir=str(bdir),
        project_root=str(tmp_path / "noproj"))
    assert result["changed"] is False
    assert _counter(bridge_db, "sr") == 228


def test_reconcile_no_files_no_downward_reset(bridge_db, tmp_path):
    _seed_flow(bridge_db, "emptyflow",
               [("s1", "e/handoffs", "{ID}-handoff.md")])
    _exec(bridge_db, "INSERT INTO bridge_id_counters (flow_key, next_id) "
                     "VALUES ('emptyflow', 41)")
    result = bridge_lib.reconcile_id_counter(
        "emptyflow", db_path=bridge_db, bridge_dir=str(tmp_path),
        project_root=str(tmp_path / "noproj"))
    assert result["max_observed"] == 0
    assert result["changed"] is False
    assert _counter(bridge_db, "emptyflow") == 41
    assert result["skipped_dirs"]  # missing dir was skipped, not fatal


def test_reconcile_scans_processed_and_rejected_siblings(bridge_db,
                                                         tmp_path):
    inbox = tmp_path / "trade-inbox"
    for sub in ("pending", "processed", "rejected"):
        (inbox / sub).mkdir(parents=True)
    (inbox / "rejected" / "070_risk01_trade.json").write_text("{}")
    (inbox / "processed" / "072_sim01_trade.json").write_text("{}")
    _seed_flow(bridge_db, "tradeflow",
               [("s1", str(inbox / "pending"), "{ID}_{role_key}.json")])
    result = bridge_lib.reconcile_id_counter(
        "tradeflow", db_path=bridge_db, bridge_dir=str(tmp_path),
        project_root=str(tmp_path / "noproj"))
    assert result["max_observed"] == 72
    assert _counter(bridge_db, "tradeflow") == 73  # row auto-created


def test_reconcile_uses_cycle_json_with_suffix(bridge_db, tmp_path):
    proj = tmp_path / "proj"
    (proj / "scripts/docs/bridgeV002").mkdir(parents=True)
    (proj / "docs/bridgeV002").mkdir(parents=True)
    (proj / "scripts/docs/bridgeV002/current-cycle.json").write_text(
        json.dumps({"flow": "cycleflow", "last_handoff": "064_humantrade"}))
    (proj / "docs/bridgeV002/current-cycle-cycleflow.json").write_text(
        json.dumps({"flow": "cycleflow", "last_handoff": 72}))
    _seed_flow(bridge_db, "cycleflow",
               [("s1", "cf/handoffs", "{ID}-handoff.md")])
    result = bridge_lib.reconcile_id_counter(
        "cycleflow", db_path=bridge_db, bridge_dir=str(tmp_path),
        project_root=str(proj))
    # "064_humantrade" -> 64; int 72 -> 72; max = 72
    assert result["max_observed"] == 72
    assert _counter(bridge_db, "cycleflow") == 73


def test_reconcile_ignores_other_flows_cycle_json(bridge_db, tmp_path):
    proj = tmp_path / "proj"
    (proj / "scripts/docs/bridgeV002").mkdir(parents=True)
    (proj / "scripts/docs/bridgeV002/current-cycle.json").write_text(
        json.dumps({"flow": "someone_else", "last_handoff": "999"}))
    _seed_flow(bridge_db, "mine", [("s1", "m/handoffs", "{ID}-handoff.md")])
    result = bridge_lib.reconcile_id_counter(
        "mine", db_path=bridge_db, bridge_dir=str(tmp_path),
        project_root=str(proj))
    assert result["max_observed"] == 0
    assert result["changed"] is False


def test_reconcile_missing_tables_degrades(tmp_path):
    empty_db = str(tmp_path / "empty.db")
    sqlite3.connect(empty_db).close()
    result = bridge_lib.reconcile_id_counter(
        "x", db_path=empty_db, bridge_dir=str(tmp_path),
        project_root=str(tmp_path))
    assert result["changed"] is False
    assert result["counter_after"] is None


# ── get_next_id_for_flow integration (self-heal on allocation) ───────

def test_allocation_self_heals_before_allocating(bridge_db, tmp_path,
                                                 monkeypatch):
    bdir = tmp_path / "bridge"
    (bdir / "pay/handoffs").mkdir(parents=True)
    (bdir / "pay/handoffs" / "72-handoff.md").write_text("x")
    _seed_flow(bridge_db, "payflow",
               [("s1", "pay/handoffs", "{ID}-handoff.md")])
    _exec(bridge_db, "INSERT INTO bridge_id_counters (flow_key, next_id) "
                     "VALUES ('payflow', 53)")
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", str(bdir))

    got = bridge_lib.get_next_id_for_flow("payflow", db_path=bridge_db)
    assert got == 73          # healed 53 -> 73, then handed out
    assert _counter(bridge_db, "payflow") == 74  # and incremented


def test_allocation_sequence_still_monotonic(bridge_db, tmp_path,
                                             monkeypatch):
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", str(tmp_path))
    _seed_flow(bridge_db, "fresh", [("s1", "f/handoffs", "{ID}-handoff.md")])
    assert bridge_lib.get_next_id_for_flow("fresh", db_path=bridge_db) == 1
    assert bridge_lib.get_next_id_for_flow("fresh", db_path=bridge_db) == 2


def test_allocation_missing_table_still_returns_1(tmp_path, monkeypatch):
    monkeypatch.setenv("DPMTF_BRIDGE_DIR", str(tmp_path))
    empty_db = str(tmp_path / "empty.db")
    sqlite3.connect(empty_db).close()
    assert bridge_lib.get_next_id_for_flow("x", db_path=empty_db) == 1
```

- [ ] Step 2: Run `python3 -m pytest tests/test_id_counter_selfheal.py -q` — expected: failures/`AttributeError` (functions do not exist yet). This is the red state.

---

### Task 2: Implement `_ids_from_directory` + `reconcile_id_counter` in `bridge_lib.py`

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/bridgeV002/bridge_lib.py` — insert both functions directly ABOVE `get_next_id_for_flow` (line ~262). `os`, `re`, `json`, `sys`, `sqlite3`, `config` are already imported at module level.

- [ ] Step 1: Add:

```python
def _ids_from_directory(dir_path, pattern_template):
    """Extract integer run/handoff ids from filenames in one directory.

    pattern_template is a bridge deliverable pattern ('{ID}-handoff.md',
    '{ID}_{role_key}.json'). Everything except the tokens is regex-escaped
    and the match is anchored, so 'current.md' and '72-handoff.md.bak'
    never match. int() parsing makes '072' and '72' the same id.
    Missing/unreadable directory -> [] (caller logs the skip).
    """
    if not pattern_template or "{ID}" not in pattern_template:
        return []
    regex_src = re.escape(pattern_template)
    regex_src = regex_src.replace(re.escape("{ID}"), r"(\d+)")
    regex_src = regex_src.replace(re.escape("{role_key}"), r"[A-Za-z0-9_]+")
    file_re = re.compile("^" + regex_src + "$")
    try:
        names = os.listdir(dir_path)
    except OSError:
        return []
    ids = []
    for name in names:
        m = file_re.match(name)
        if m:
            ids.append(int(m.group(1)))
    return ids


def reconcile_id_counter(flow_key, db_path=None, bridge_dir=None,
                         project_root=None):
    """Self-heal bridge_id_counters for one flow from durable evidence.

    Evidence sources:
      1. Every active step's deliverable directory (bridge_flow_steps
         deliverable_dir + deliverable_pattern). Relative dirs resolve
         against the bridge dir; a dir named 'pending' also contributes
         its 'processed' and 'rejected' siblings (the trade import
         pipeline moves files there).
      2. Cycle-state JSON: <project_root>/scripts/docs/bridgeV002/
         current-cycle.json (only when its 'flow' matches) and
         <project_root>/docs/bridgeV002/current-cycle-<flow-hyphens>.json.
         last_handoff values like '064_humantrade' contribute their
         leading digits.

    The counter is only ever RAISED (next_id = max_observed + 1 when
    behind) — an empty flow never resets a healthy counter downward.
    Read-and-update runs in one BEGIN IMMEDIATE transaction; filesystem
    scanning happens before the transaction opens.

    Returns:
        dict with keys: flow_key, max_observed, counter_before,
        counter_after, changed, scanned_dirs, skipped_dirs.
    """
    if db_path is None:
        db_path = config.get_db_path()
    if bridge_dir is None:
        bridge_dir = (os.environ.get("DPMTF_BRIDGE_DIR")
                      or config.get_bridge_base_path())
    if project_root is None:
        project_root = _find_project_root()

    result = {"flow_key": flow_key, "max_observed": 0,
              "counter_before": None, "counter_after": None,
              "changed": False, "scanned_dirs": [], "skipped_dirs": []}

    # ── Phase 1: filesystem evidence (no DB lock held) ────────────────
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        steps = conn.execute(
            "SELECT deliverable_dir, deliverable_pattern "
            "FROM bridge_flow_steps WHERE flow_key = ? AND is_active = 1",
            (flow_key,),
        ).fetchall()
        conn.close()
    except sqlite3.OperationalError:
        return result  # tables absent (fresh DB) — nothing to heal

    seen = set()
    for step in steps:
        raw_dir = step["deliverable_dir"] or ""
        pattern = step["deliverable_pattern"] or ""
        if not raw_dir or not pattern:
            continue
        base = (raw_dir if os.path.isabs(raw_dir)
                else os.path.join(bridge_dir, raw_dir))
        candidates = [base]
        if os.path.basename(base.rstrip("/")) == "pending":
            parent = os.path.dirname(base.rstrip("/"))
            candidates.append(os.path.join(parent, "processed"))
            candidates.append(os.path.join(parent, "rejected"))
        for d in candidates:
            key = (d, pattern)
            if key in seen:
                continue
            seen.add(key)
            if not os.path.isdir(d):
                result["skipped_dirs"].append(d)
                print(f"  reconcile[{flow_key}]: dir missing, skipped: {d}",
                      file=sys.stderr)
                continue
            ids = _ids_from_directory(d, pattern)
            result["scanned_dirs"].append(d)
            if ids:
                result["max_observed"] = max(result["max_observed"],
                                             max(ids))

    # ── Phase 2: cycle-state JSON evidence ────────────────────────────
    cycle_candidates = (
        os.path.join(project_root, "scripts", "docs", "bridgeV002",
                     "current-cycle.json"),
        os.path.join(project_root, "docs", "bridgeV002",
                     f"current-cycle-{flow_key.replace('_', '-')}.json"),
    )
    for cycle_path in cycle_candidates:
        try:
            with open(cycle_path, encoding="utf-8") as fh:
                cycle = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if cycle.get("flow") != flow_key:
            continue
        m = re.match(r"^(\d+)", str(cycle.get("last_handoff", "")))
        if m:
            result["max_observed"] = max(result["max_observed"],
                                         int(m.group(1)))

    # ── Phase 3: conditional raise in ONE immediate transaction ──────
    try:
        conn = sqlite3.connect(db_path)
        conn.isolation_level = None  # explicit transaction control
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        row = cur.execute(
            "SELECT next_id FROM bridge_id_counters WHERE flow_key = ?",
            (flow_key,)).fetchone()
        result["counter_before"] = row[0] if row else None
        result["counter_after"] = result["counter_before"]
        if result["max_observed"] > 0:
            target = result["max_observed"] + 1
            if row is None:
                cur.execute(
                    "INSERT INTO bridge_id_counters (flow_key, next_id) "
                    "VALUES (?, ?)", (flow_key, target))
                result["counter_after"] = target
                result["changed"] = True
            elif (row[0] or 0) < target:
                cur.execute(
                    "UPDATE bridge_id_counters SET next_id = ? "
                    "WHERE flow_key = ?", (target, flow_key))
                result["counter_after"] = target
                result["changed"] = True
        cur.execute("COMMIT")
        conn.close()
    except sqlite3.OperationalError:
        try:
            conn.close()
        except Exception:
            pass
    return result
```

- [ ] Step 2: `python3 -m py_compile scripts/bridgeV002/bridge_lib.py` — exit 0.
- [ ] Step 3: Run `python3 -m pytest tests/test_id_counter_selfheal.py -q` — the `_ids_from_directory` and `reconcile_id_counter` tests pass; the three `get_next_id_for_flow` integration tests still fail (Task 3 wires them).

---

### Task 3: Hook reconcile into `get_next_id_for_flow` + `BEGIN IMMEDIATE` allocation

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/bridgeV002/bridge_lib.py` — replace `get_next_id_for_flow` (lines ~262–326 pre-insert).

- [ ] Step 1: Replace the ENTIRE existing `get_next_id_for_flow` function with:

```python
def get_next_id_for_flow(flow_key, db_path=None):
    """Return the next handoff ID for a specific flow, auto-incrementing.

    Uses bridge_id_counters. Flow-isolated. SELF-HEALING: reconciles the
    counter against durable evidence (deliverable dirs + cycle JSON) on
    EVERY allocation, so a counter that fell behind manually-passed --id
    values (cloud_pay stuck at 53 vs handoff 72) recovers automatically.
    Allocation runs in a single BEGIN IMMEDIATE transaction.

    Args:
        flow_key: The flow key (e.g. 'strict_review', 'heavy').
        db_path: Optional path to SQLite database. Defaults to
                 config.get_db_path().

    Returns:
        int — the next ID, or 1 if the counter table does not exist yet
        (cron scripts call this inline and must never die here).
    """
    if db_path is None:
        db_path = config.get_db_path()

    # Self-heal first (cheap: one directory scan per step). NEVER let a
    # reconcile problem break allocation — 09:00 cron depends on this.
    try:
        reconcile_id_counter(flow_key, db_path=db_path)
    except Exception as exc:
        print(f"  WARNING: id-counter reconcile failed for "
              f"'{flow_key}': {exc}", file=sys.stderr)

    conn = sqlite3.connect(db_path)
    conn.isolation_level = None  # explicit transaction control
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "SELECT next_id FROM bridge_id_counters WHERE flow_key = ?",
            (flow_key,)
        )
        row = cursor.fetchone()
        if row and row[0]:
            new_id = row[0]
        else:
            new_id = 1
            cursor.execute(
                "INSERT OR IGNORE INTO bridge_id_counters "
                "(flow_key, next_id) VALUES (?, 1)",
                (flow_key,)
            )
        cursor.execute(
            "UPDATE bridge_id_counters "
            "SET next_id = COALESCE(next_id, 1) + 1 WHERE flow_key = ?",
            (flow_key,)
        )
        cursor.execute("COMMIT")
        return new_id
    except sqlite3.OperationalError:
        # Table doesn't exist yet — safe fallback
        try:
            cursor.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        return 1
    finally:
        conn.close()
```

- [ ] Step 2: `python3 -m py_compile scripts/bridgeV002/bridge_lib.py` — exit 0.
- [ ] Step 3: Run `python3 -m pytest tests/test_id_counter_selfheal.py -q` — ALL tests pass (`14 passed`).
- [ ] Step 4: Regression check of every existing caller path: `grep -rn "get_next_id_for_flow" app.py routers/ scripts/ | grep -v __pycache__` — confirm callers pass `(flow_key)` or `(flow_key, db_path=...)` only (verified callers today: `dispatch.py` main, `app.py` import, `routers/bridge.py`, `trade-cronjob.sh`/`scoring-cronjob.sh` inline python) — signature unchanged, nothing else to edit.

---

### Task 4: CLI — `dispatch.py --reconcile-counters [--db-flow X]`

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py` — import + `main()`.

- [ ] Step 1: Extend the `from bridge_lib import (...)` block at the top of dispatch.py (lines 23–34) with the new name:

```python
from bridge_lib import (
    load_role_from_db,
    load_flow_from_db,
    resolve_convention_from_db,
    resolve_content_template_from_db,
    validate_deliverable_against_schema,
    get_next_id_for_flow,
    reconcile_id_counter,
    ensure_subdir,
    resolve_placeholders,
    list_scripts_from_db,
    get_effective_model_source,
)
```

- [ ] Step 2: In `main()`, add the argparse flag after the `--signal-answer` argument:

```python
    parser.add_argument("--reconcile-counters", action="store_true",
                        help="Audit/self-heal bridge_id_counters from "
                             "durable evidence; --db-flow limits to one "
                             "flow. Prints per-flow before/after.")
```

- [ ] Step 3: Handle it BEFORE the `if not args.db_flow:` requirement check (it must work without `--db-flow`). Insert directly after `bridge_dir = _bridge_dir()`:

```python
    if args.reconcile_counters:
        if args.db_flow:
            flow_keys = [args.db_flow]
        else:
            conn = sqlite3.connect(_db_path())
            try:
                rows = conn.execute(
                    "SELECT flow_key FROM bridge_id_counters "
                    "UNION SELECT flow_key FROM bridge_flows"
                ).fetchall()
                flow_keys = sorted({r[0] for r in rows})
            except sqlite3.OperationalError:
                flow_keys = []
            finally:
                conn.close()
        if not flow_keys:
            print("No flows found to reconcile.")
            sys.exit(0)
        for fk in flow_keys:
            r = reconcile_id_counter(fk, db_path=_db_path(),
                                     bridge_dir=bridge_dir)
            print(f"{fk}: next_id {r['counter_before']} -> "
                  f"{r['counter_after']} "
                  f"(max observed {r['max_observed']}, "
                  f"{'RAISED' if r['changed'] else 'ok'}; "
                  f"scanned {len(r['scanned_dirs'])} dirs, "
                  f"skipped {len(r['skipped_dirs'])})")
        sys.exit(0)
```

- [ ] Step 4: `python3 -m py_compile scripts/bridgeV002/dispatch.py` — exit 0.
- [ ] Step 5: Full suite: `python3 -m pytest -q` — no new failures (the 2 pre-existing `test_migrate.py` failures are unrelated; see edge case 12).

---

### Task 5: Live audit of the real counters (read → heal → verify)

Runs against the committed `databases/dpmtf.db` on this machine — this is the actual healing of the cloud_pay drift, and it is idempotent/raise-only, so it is safe to run.

- [ ] Step 1: Snapshot the current state: `sqlite3 databases/dpmtf.db "SELECT flow_key, next_id FROM bridge_id_counters ORDER BY flow_key;"` — expected (as of plan-writing): `cloud_llm|3`, `cloud_pay|53`, `strict_review|228`, `trade_cockpit_scoring_v001|2`, `trade_cockpit_simulation_v001|73`.
- [ ] Step 2: Run the audit for everything: `python3 scripts/bridgeV002/dispatch.py --reconcile-counters` — expected output includes:
  - `cloud_pay: next_id 53 -> 73 (max observed 72, RAISED; ...)` (files `72-handoff.md`/`72-verdict.md` + cycle JSON `last_handoff: 72`),
  - `strict_review: next_id 228 -> 228 (max observed 227, ok; ...)`,
  - `trade_cockpit_simulation_v001: next_id 73 -> 73 (max observed 72, ok; ...)`,
  - `cloud_llm` / `trade_cockpit_scoring_v001` lines with `RAISED` or `ok` depending on their on-disk evidence — NEVER a value lower than the Step 1 snapshot.
- [ ] Step 3: Re-run the same command — every line now reports `ok` (idempotent; nothing raised twice).
- [ ] Step 4: Verify the healed row: `sqlite3 databases/dpmtf.db "SELECT next_id FROM bridge_id_counters WHERE flow_key='cloud_pay';"` — prints `73` (or higher if newer handoffs exist).

---

### Task 6: Stage and stop

- [ ] Step 1: `git diff --stat` — expected: `scripts/bridgeV002/bridge_lib.py`, `scripts/bridgeV002/dispatch.py`, `databases/dpmtf.db` (counter rows healed in Task 5); new: `tests/test_id_counter_selfheal.py`.
- [ ] Step 2: `curl -s http://localhost:9130/api/health` → `{"status":"healthy"}`.
- [ ] Step 3: Stage with `git add scripts/bridgeV002/bridge_lib.py scripts/bridgeV002/dispatch.py tests/test_id_counter_selfheal.py databases/dpmtf.db` and STOP — await Human commit approval. Suggested commit message: `[hardening] self-healing bridge_id_counters (reconcile on allocation + --reconcile-counters CLI)`.

## Acceptance Criteria

1. `python3 -m pytest tests/test_id_counter_selfheal.py -q` — `14 passed`.
2. `python3 scripts/bridgeV002/dispatch.py --reconcile-counters --db-flow cloud_pay` — prints a `cloud_pay:` line whose `counter_after` ≥ 73 and never lower than `counter_before`; a second run prints `ok` (idempotent).
3. `sqlite3 databases/dpmtf.db "SELECT next_id >= 73 FROM bridge_id_counters WHERE flow_key='cloud_pay';"` — prints `1`.
4. Allocation self-heal proof (no DB row edit needed): `python3 -c "import sys; sys.path.insert(0,'scripts/bridgeV002'); from bridge_lib import get_next_id_for_flow; print(get_next_id_for_flow('cloud_pay'))"` — prints a value ≥ 73 that has never been used by an existing handoff file in `$DPMTF_BRIDGE_DIR/cloud_pay/handoffs/`. NOTE: this consumes one id from the live counter — acceptable (ids are cheap; gaps are harmless), run it at most once.
5. `python3 -m py_compile scripts/bridgeV002/bridge_lib.py scripts/bridgeV002/dispatch.py` — exit 0.
6. `python3 -m pytest -q` — no failures beyond the 2 pre-existing `test_migrate.py` ones (or zero, if PLAN-bridgev002-test-suite.md ran first).
7. `curl -s http://localhost:9130/api/health` returns `{"status":"healthy"}`.
