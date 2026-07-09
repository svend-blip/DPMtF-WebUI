# Optimization Roadmap — DPMtF-WebUI & trade-ui

> **For agentic workers:** This is a multi-phase roadmap, NOT a single handoff. Each
> phase contains independent handoffs dispatched via BridgeV002. Phases are gated —
> do NOT start a later phase before its gate is met. Steps use checkbox (`- [ ]`)
> syntax for tracking within each handoff. **Do not begin implementation of any
> handoff until the Human explicitly dispatches it.**

**Goal:** Address the optimizations from `/home/svend/Dokumenter/Optimeringer.md`
(DPMtF-WebUI & trade-ui review, 2026-07-04) in a dependency-correct, risk-ordered
sequence — with corrections to the source document's errors and overstatements.

**Source doc status:** Faktisk meget præcis (verificeret mod filestate 2026-07-04),
men indeholder 3 fejl/overdrivelser der rettes her (se "Source doc corrections").

**Architecture:**
- **DPMtF-WebUI changes** → `strict_review` flow (handoffs to `imple01`).
- **trade-ui changes** → `cloud_pay` flow (handoffs to `imple01pay`).
- Each handoff is independently testable and independently reviewed.
- app.py modular split is **test-gated**: Fase A (tests) MUST land before Fase B
  (split). No big-bang refactor of a 5473-line monolith under active development.

**Tech Stack:** Python (FastAPI), SQLite, JavaScript (vanilla), pytest/httpx.

**Flow mapping rationale:** `cloud_pay` targets trade-ui (the eToro/pay project);
`strict_review` is the Father project's own development flow. Handoffs respect the
relevant flow's role definitions and the Human commit gate (changes stay unstaged
until Human approval).

## Global Constraints

- NO innerHTML for dynamic content — use textContent, createElement(), etc.
- ALL user-facing text MUST use lbl(key, fallback) — no hardcoded strings in DOM.
- Parameterized SQL only — `?` placeholders, never f-strings/concatenation in SQL
  (Fase Ø-5 explicitly removes the existing f-string execute anti-pattern).
- NO hardcoded `/home/svend/...` paths — use config.get_*() (Fase Ø-4 enforces).
- DO NOT COMMIT. Leave all changes unstaged until Human approval.
- All code and comments MUST be in English (en-US).
- Stop after 2 failed patching attempts — document, escalate (CLAUDE.md auto-fail #7).
- Sacred invariants untouched: `ETORO_DEMO_ONLY` / `ETORO_LIVE_DISABLED` /
  `AUTO_EXECUTION_DISABLED` stay `True` in trade-ui `etoro_bridge.py`.

---

## Source doc corrections (critical — do NOT follow these doc recommendations)

The source `Optimeringer.md` is accurate on facts but wrong/overstated on these
points. This plan corrects them:

1. **`new-webui-skeleton` removal — SKIP.** The skeleton is NOT dead code; it is
   **Spor C Accelerated WebUI Factory** (committed handoffs 039-041:
   `c55283a`/`0e1b1c9`/`1d5e1c6`). It contains `scripts/initialize_new_webui.py`
   and bootstraps new WebUI projects. Removing/moving it would break Spor C.
   **Action:** leave untouched.

2. **config.py "approved but not committed" — framing corrected.** Handoff 027
   committed fixes for **7** init_db paths, but config.py's 2 fallbacks
   (`config.py:56`, `config.py:128`) and init_db's **remaining 32** `/home/svend`
   occurrences were never touched. The work must be done from scratch
   (Fase Ø-4), not merely committed.

3. **eToro API key rotation — overstated severity, deferred.** `.env` IS in
   `.gitignore` (verified), so the keys are NOT in git. They are DEMO-account
   keys (not real-money). Rotation is reasonable hygiene but is a Human action,
   not a code handoff. **Action:** deferred to Human hygiene; not a phase here.

4. **Auth middleware — SKIP (disproportionate).** Both apps are localhost dev
   tools (ports 9130/9140). JWT/API-key auth is enterprise overkill for a local
   tool. **Action:** skip. CORS may be added later IF a real cross-origin need
   arises (deferred, not a phase).

5. **app.py split timing — corrected.** The source doc ranks split as #1 (first).
   This plan defers it to **Fase B, AFTER Fase A (tests)**. Refactoring a
   5473-line monolith without behavior tests violates the "stop after 2 failed
   patch attempts" auto-fail and risks uncontrolled churn while BridgeV002/Phase 6
   are still landing.

6. **SQL injection — re-graded.** The f-string execute (app.py:1538, 3491) has a
   whitelist check before it, so real risk is low (but non-zero). It is hygiene,
   not a "high security risk." Still fixed (Fase Ø-5) at low cost.

---

# PHASE OVERVIEW

```
Fase Ø (Foundation, parallel in both flows)   ~2-3 days   [no dependencies]
    ↓ GATE: Ø-1..Ø-5 approved + committed
Fase A (Test scaffolding, both)                ~1-2 days   [depends on Ø]
    ↓ GATE: green test suites in both projects
Fase B (app.py modular split, DPMtF only)      ~1 week     [depends on A]
    ↓ (can overlap with Fase C)
Fase C (Hygiene, both, low priority)           ~1-2 days   [independent]
```

**Hard rule:** Do NOT start Fase B before Fase A is green. Do NOT start any phase
before its gate is met.

---

# FASE Ø — Foundation (both projects, parallel)

Low-risk, high-value, no dependencies. Handoffs in both flows can run concurrently.
Each is a standalone handoff.

## Handoff Ø-1: Add logging to DPMtF app.py
**Flow:** strict_review  | **Project:** DPMtF-WebUI

### Affected Files
- **Modify:** `app.py` (add `import logging`, `logger = logging.getLogger(__name__)`,
  replace critical `print()` calls with `logger.info/warning/error`)
- **Modify:** `dpmtf.ini` (add `[logging]` section: `level=INFO`, `file=logs/app.log`)
- **Modify:** `config.py` (add `get_logging_level()` / `get_logging_file()` getters)

### Task
- [ ] Step 1: Read `app.py` and inventory all `print()` calls (categorize: info / warning / error).
- [ ] Step 2: Add `logging` module import + module-level `logger`.
- [ ] Step 3: Add `[logging]` config section to `dpmtf.ini` + `config.py` getters (no hardcoded paths — use `config.get_log_dir()`).
- [ ] Step 4: Replace critical `print()` with appropriate `logger.<level>()` calls. Console output may remain for startup banner only.
- [ ] Step 5: Verify: `python3 -m py_compile app.py`; app starts; logs written to configured file.

## Handoff Ø-2: Add logging to trade-ui app.py
**Flow:** cloud_pay  | **Project:** trade-ui

### Affected Files
- **Modify:** `app.py` (same pattern as Ø-1), `dpmtf.ini`, `config.py`

### Task
- [ ] Step 1-5: Mirror Ø-1 for trade-ui (1543 lines, 22 endpoints, 0 logging imports today).

## Handoff Ø-3: trade-ui .gitignore + requirements pins
**Flow:** cloud_pay  | **Project:** trade-ui

### Affected Files
- **Modify:** `.gitignore` (add `/trade-ui.db`, `/trade_cockpit.sqlite`, `*.sqlite`)
- **Modify:** `requirements.txt` (pin: `fastapi==0.110.0`, `uvicorn==0.29.0`, `python-dotenv==1.0.1` — match DPMtF versions where applicable)

### Task
- [ ] Step 1: Add root-level DB files + `*.sqlite` to `.gitignore`.
- [ ] Step 2: Pin `requirements.txt` (verify versions resolve in venv).
- [ ] Step 3: Verify `git status` no longer shows `trade-ui.db` / `trade_cockpit.sqlite` as untracked.

## Handoff Ø-4: Remove hardcoded /home/svend paths (config.py + init_db.py)
**Flow:** strict_review  | **Project:** DPMtF-WebUI  | **Governance auto-fail fix**

### Affected Files
- **Modify:** `config.py` (remove `fallback="/home/svend/flows"` at line 56 and
  `"/home/svend/trade-ui/inbox/pending"` at line 128 — use env var without
  hardcoded default, or a config-section default that is not a user path)
- **Modify:** `scripts/init_db.py` (replace 32 `/home/svend/` occurrences in seed
  data with env-gated / config-derived values)
- **Modify:** `dpmtf.ini` (remove hardcoded `project_root` / `bridge_dir` user paths)
- **Possibly add:** startup validation that raises `ConfigValidationError` if any
  resolved config value contains `/home/svend`

### Task
- [ ] Step 1: Audit all `/home/svend` in config.py + init_db.py + dpmtf.ini.
- [ ] Step 2: Replace each with `config.get_*()` or env var (no hardcoded user path defaults).
- [ ] Step 3: Add startup validation hook.
- [ ] Step 4: Verify: `grep -n '"/home/svend' app.py scripts/ config.py` returns nothing; `python3 scripts/init_db.py` runs idempotently; `curl /api/health` returns healthy.

## Handoff Ø-5: SQL f-string fix
**Flow:** strict_review  | **Project:** DPMtF-WebUI

### Affected Files
- **Modify:** `app.py` lines 1538 and 3491 (replace `cursor.execute(f"...[{table_name}]")` with `PRAGMA table_list` validation or explicit `ALLOWED_TABLES` whitelist + parameterized query)

### Task
- [ ] Step 1: Replace f-string table-name executes with whitelist-gated `PRAGMA table_list` lookup.
- [ ] Step 2: Verify the affected endpoints still return correct counts.
- [ ] Step 3: Verify: `grep -nE "cursor\.execute\(f" app.py` returns nothing.

---

# FASE A — Test scaffolding (both projects)

**This is the hard gate for Fase B.** Without behavior tests, the app.py split
cannot be done safely. DPMtF has 0 application tests today; trade-ui has 168
`verify_*.py` tests that need to be formalized under pytest.

## Handoff A-1: pytest scaffolding for DPMtF
**Flow:** strict_review  | **Project:** DPMtF-WebUI

### Affected Files
- **Modify:** `requirements.txt` (add `pytest`, `httpx`, `coverage` — pinned)
- **Add:** `pytest.ini`, `tests/conftest.py`, `tests/test_health.py`,
  `tests/test_bridge_endpoints.py` (2-3 critical endpoints: bridge status, flows)

### Task
- [ ] Step 1: Add pytest deps + `pytest.ini` (config: testpaths, coverage).
- [ ] Step 2: `tests/conftest.py` with FastAPI `TestClient` fixture + temp DB.
- [ ] Step 3: `tests/test_health.py` smoke test (`/api/health` → 200 healthy).
- [ ] Step 4: 2-3 critical-endpoint tests (bridge-v2 status, flows list).
- [ ] Step 5: Verify: `pytest` runs green.

## Handoff A-2: formalize trade-ui tests under pytest
**Flow:** cloud_pay  | **Project:** trade-ui

### Affected Files
- **Modify:** `requirements.txt` (add `pytest`, `coverage`)
- **Add:** `pytest.ini`, `tests/conftest.py`
- **Reference:** existing `scripts/verify_*.py` (168 tests) — collected under pytest

### Task
- [ ] Step 1: Add `pytest.ini` + `tests/conftest.py`.
- [ ] Step 2: Ensure existing `verify_*.py` scripts are collected by pytest (rename or add `tests/test_*` shims if needed — do NOT rewrite the 168 tests).
- [ ] Step 3: Add coverage config.
- [ ] Step 4: Verify: `pytest` runs green with all existing tests passing.

---

# FASE B — app.py modular split (DPMtF only, test-gated)

**Hard preconditions:** Fase A-1 green. app.py split is the highest-effort,
highest-risk phase. One router per handoff. After each extraction, A-1's tests
MUST pass — behavior unchanged. If tests go red, stop, document, escalate.

Uses FastAPI `APIRouter`. app.py becomes a ~200-line registration hub.

## Handoff B-1: Establish routers/ package + extract bridge router (PILOT)
**Flow:** strict_review  | **Project:** DPMtF-WebUI

### Affected Files
- **Add:** `routers/__init__.py`, `routers/bridge.py`
- **Modify:** `app.py` (register `bridge` router, remove bridge endpoint definitions)

### Task
- [ ] Step 1: Create `routers/` package + `APIRouter` pattern.
- [ ] Step 2: Extract the ~40 bridge endpoints (BridgeV002 flows/roles/steps/signaling) into `routers/bridge.py`.
- [ ] Step 3: Register router in `app.py`; remove old inline definitions.
- [ ] Step 4: Run A-1 tests — MUST stay green. Run `python3 -m py_compile app.py routers/bridge.py`.
- [ ] Step 5: Verify `curl /api/bridge-v2/status` + `/api/bridge-v2/flows` still work.

## Handoff B-2: Extract panels router
**Flow:** strict_review  | **Project:** DPMtF-WebUI
- [ ] Extract ~20 panel CRUD endpoints to `routers/panels.py`. Tests stay green.

## Handoff B-3: Extract prompt_compiler + governance routers
**Flow:** strict_review  | **Project:** DPMtF-WebUI
- [ ] Extract ~15 prompt-compiler endpoints to `routers/prompt_compiler.py`.
- [ ] Extract ~7 governance-template endpoints to `routers/governance.py`.
- [ ] Tests stay green.

## Handoff B-4: Extract system + trade routers; reduce app.py to hub
**Flow:** strict_review  | **Project:** DPMtF-WebUI
- [ ] Extract ~8 system endpoints (health, panels, preferences) to `routers/system.py`.
- [ ] Extract portfolio01_trade-related endpoints to `routers/trade.py`.
- [ ] app.py reduced to ~200 lines (router registration + startup logic).
- [ ] Final full test run + all endpoints smoke-tested.

---

# FASE C — Hygiene (both projects, low priority, can run between B-handoffs)

## Handoff C-1: i18n leakage fixes
**Flow:** strict_review (DPMtF `dpmtf-app.js`) + cloud_pay (trade-ui `app.js`)
- [ ] Map hardcoded th/h4/table-headers to `lbl()` with da-DK + en-US seed data.
- [ ] DPMtF: ~8 leaks (lines 176, 491, 493, 535, 558, 596, …).
- [ ] trade-ui: ~15 leaks (lines 462, 482, 503, 531, 720, 831, …).

## Handoff C-2: Replace bare `pass` statements (DPMtF)
**Flow:** strict_review  | **Project:** DPMtF-WebUI
- [ ] Replace 33 bare `pass` with `raise NotImplementedError(...)` or `logger.warning("TBD: ...")`.

## Handoff C-3: DB table audit (DPMtF)
**Flow:** strict_review  | **Project:** DPMtF-WebUI
- [ ] `SELECT COUNT(*)` per table; identify 0-row tables.
- [ ] Verify each 0-row table is not referenced by code before dropping.
- [ ] Add migration script to init_db.py for safe drops. **Do NOT drop tables with data.**

---

# Explicitly excluded (with rationale)

| Item | Reason |
|------|--------|
| Remove `new-webui-skeleton` | It is Spor C Accelerated WebUI Factory — an active feature, not dead code. |
| Auth middleware (JWT/API-key) | Localhost dev tool; disproportionate enterprise security. |
| CORS middleware | Defer until a real cross-origin access need arises. |
| eToro demo key rotation | `.env` is gitignored; keys are DEMO-only. Human hygiene action, not a code handoff. |

---

# Verification gates summary

| Gate | Condition | Blocks |
|------|-----------|--------|
| G1 | Fase Ø-1..Ø-5 approved + committed | Fase A |
| G2 | Fase A-1 + A-2 green test suites | Fase B |
| G3 | After each B-handoff: A-1 tests green + endpoints smoke-tested | Next B-handoff |
| G4 | `grep -RIn "innerHTML" static/ templates/` empty | Every frontend handoff |
| G5 | `grep -n '"/home/svend' app.py scripts/ config.py` empty | Ø-4 |
| G6 | `grep -nE "cursor\.execute\(f" app.py` empty | Ø-5 |

---

# Next action

This plan is written but **no handoff is dispatched**. The Human decides when to
start. Recommended first dispatch: **Handoff Ø-1 (logging, strict_review)** and
**Handoff Ø-2 (logging, cloud_pay)** in parallel — cheapest, zero regression risk,
unblocks debugging for everything else.

Do not begin implementation until the Human explicitly says to dispatch a handoff.
