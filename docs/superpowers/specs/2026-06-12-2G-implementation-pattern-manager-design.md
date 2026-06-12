# 2G: Implementation Pattern Manager — Design Spec

**Date:** 2026-06-12
**Phase:** 2G
**Status:** Design approved — awaiting implementation plan

---

## Purpose

Enable DPMtF-WebUI to recognize which prompt structures historically work by capturing reusable implementation patterns from completed phases. A pattern is defined by the combination of **file-change signature** (which files were modified) and **constraint set** (which rules applied). Each pattern tracks its own hitrate aggregate, best-performing model, and average execution metrics.

Simultaneously, enhance `prompt_runs` with model metadata (local vs cloud, token counts, token costs, idle time) so individual runs carry the full execution context needed for pattern analysis.

---

## Database Changes

### prompt_runs — 7 new columns (ALTER TABLE ADD COLUMN)

| Column | Type | Description |
|---|---|---|
| `model_type` | TEXT | `'local'` or `'cloud'`. Derived from `model_used` if not explicit (`:cloud` suffix → cloud). NULL = unknown. |
| `idle_seconds` | INTEGER | Wait time before model started processing. NULL = not traceable. |
| `token_count_input` | INTEGER | Input tokens consumed. NULL for local models. |
| `token_count_output` | INTEGER | Output tokens generated. NULL for local models. |
| `token_cost_eur` | REAL | Estimated cost in EUR at time of run. NULL for local models. |
| `token_cost_dkk` | REAL | Estimated cost in DKK at time of run. NULL for local models. |
| `pattern_id` | TEXT | FK to `implementation_patterns.pattern_id`. NULL = not yet classified. |

All added via `ALTER TABLE ADD COLUMN` with try/except for idempotent re-runs.

### implementation_patterns — new table (CREATE TABLE IF NOT EXISTS)

| Column | Type | Description |
|---|---|---|
| `pattern_id` | TEXT UNIQUE PK | e.g. `PAT-0001`, auto-generated. |
| `file_signature` | TEXT NOT NULL | Comma-separated list of file paths changed, e.g. `scripts/seed_database.py,static/js/app.js,docs/*`. |
| `constraint_set` | TEXT NOT NULL | Comma-separated list of constraints, e.g. `read-only,no-schema,no-innerHTML,no-POST/PUT/DELETE`. |
| `phase_key` | TEXT | First phase that used this pattern. |
| `total_runs` | INTEGER DEFAULT 0 | Total executions of this pattern. |
| `successful_runs` | INTEGER DEFAULT 0 | Successful executions. |
| `rolling_success_rate` | REAL DEFAULT 0.0 | `successful_runs / total_runs`. |
| `best_model` | TEXT | Model with highest success rate for this pattern. |
| `avg_duration_seconds` | INTEGER | Mean execution time across all runs. |
| `avg_idle_seconds` | INTEGER | Mean wait time across all runs. |
| `last_used_at` | TIMESTAMP | Most recent run timestamp. |
| `created_at` | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | |
| `updated_at` | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | |

**Unique constraint:** `UNIQUE(file_signature, constraint_set)` — two patterns with the same signature and constraints are the same pattern.

---

## API Changes

### POST /api/prompt-runs — extended

**New optional body fields:**

```json
{
  "model_type": "cloud",
  "idle_seconds": 12,
  "token_count_input": 1200,
  "token_count_output": 3400,
  "token_cost_eur": 0.12,
  "token_cost_dkk": 0.89,
  "file_signature": "scripts/seed_database.py,static/js/app.js,docs/*",
  "constraint_set": "read-only,no-schema,no-innerHTML"
}
```

**Pattern-matching logic on POST:**

1. If `file_signature` + `constraint_set` are provided:
   a. Query `implementation_patterns` for existing row with same signature + constraints.
   b. If found: UPDATE pattern's `total_runs`, `successful_runs`, `rolling_success_rate`, `best_model` (re-evaluated), `avg_duration_seconds`, `avg_idle_seconds`, `last_used_at`. SET `pattern_id` on the new prompt_run.
   c. If not found: INSERT new pattern with auto-generated `pattern_id` (`PAT-<next_sequential>`), seed with this run's data. SET `pattern_id` on the new prompt_run.
2. If not provided: `pattern_id` remains NULL on the run. Pattern classification can happen later.

**model_type derivation:** If `model_type` is not provided but `model_used` contains `:cloud` → set `model_type = 'cloud'`, else `model_type = 'local'`.

### GET /api/implementation-patterns — new

Query params: `?constraint_set=read-only` (optional filter).

Returns all patterns sorted by `rolling_success_rate ASC` (worst first, same convention as prompt-hirates).

Response:
```json
{
  "patterns": [
    {
      "pattern_id": "PAT-0001",
      "file_signature": "scripts/seed_database.py,static/js/app.js,docs/*",
      "constraint_set": "read-only,no-schema,no-innerHTML",
      "phase_key": "3C-14",
      "total_runs": 5,
      "successful_runs": 5,
      "rolling_success_rate": 1.0,
      "best_model": "claude-fable-5",
      "avg_duration_seconds": 180,
      "avg_idle_seconds": 12,
      "last_used_at": "2026-06-12T10:30:00"
    }
  ]
}
```

### GET /api/implementation-patterns/{pattern_id}/runs — new

Returns all `prompt_runs` linked to the given pattern, sorted by `run_timestamp DESC`. Same response shape as `GET /api/prompt-runs` but filtered by pattern_id.

---

## Frontend Changes

### Hitrate panel extension (templates/index.html)

New table **"Implementation Patterns"** below the existing hitrate tables, inside the same `.hitrate-section` div:

| Column | Source |
|---|---|
| Pattern ID | `pattern_id` (clickable — expands detail view) |
| Files | `file_signature` (truncated to 60 chars with ellipsis) |
| Constraints | `constraint_set` |
| Success Rate | `rolling_success_rate` as percentage, color-coded (green ≥80%, orange ≥50%, red <50%) |
| Best Model | `best_model` |
| Avg Duration | `avg_duration_seconds` formatted as `180s` |
| Runs | `successful_runs / total_runs` |

**Expandable detail view:** Clicking a pattern row fetches `/api/implementation-patterns/{pattern_id}/runs` and renders a sub-table with the same columns as "Recent Prompt Runs" plus token cost columns for cloud runs.

### Recent Prompt Runs table extension

Three new columns added to the existing runs table:

| Column | Content |
|---|---|
| Model Type | `local` or `cloud` badge (CSS: blue for local, purple for cloud) |
| Tokens | `1.2K in / 3.4K out` for cloud, `-` for local |
| Cost | `€0.12 / 0.89 DKK` for cloud, `-` for local |

### JavaScript (static/js/dpmtf-app.js)

- `loadPatterns()` — fetches `/api/implementation-patterns`, renders pattern table
- `expandPattern(patternId)` — fetches pattern runs, toggles detail sub-table
- `loadPromptRuns()` — extended to render the 3 new columns
- `formatTokens(n)` — helper: formats large integers as `1.2K`, `3.4K`
- All new code uses `createElement`/`textContent`/`replaceChildren` (no innerHTML)

### CSS (static/css/dpmtf-theme.css)

- `.model-badge-local` — blue background, white text, small rounded pill
- `.model-badge-cloud` — purple background, white text, small rounded pill
- `.pattern-row` — cursor pointer on hover
- `.pattern-detail-row` — slightly indented, lighter background
- Reuse existing `.hitrate-good`, `.hitrate-ok`, `.hitrate-low` for success rates

---

## Seed Data

### Backfill PRUN-2E-0001

The existing 2E run is updated with pattern metadata:

```sql
UPDATE prompt_runs SET
  model_type = 'cloud',
  file_signature = 'docs/governance-templates/*,scripts/init_db.py,docs/project-report.md',
  constraint_set = 'read-only,no-schema,no-POST/PUT/DELETE,no-service-control',
  pattern_id = 'PAT-0001'
WHERE run_id = 'PRUN-2E-0001';
```

### Seed PAT-0001

```sql
INSERT OR IGNORE INTO implementation_patterns
  (pattern_id, file_signature, constraint_set, phase_key,
   total_runs, successful_runs, rolling_success_rate,
   best_model, avg_duration_seconds, last_used_at)
VALUES
  ('PAT-0001',
   'docs/governance-templates/*,scripts/init_db.py,docs/project-report.md',
   'read-only,no-schema,no-POST/PUT/DELETE,no-service-control',
   '2E', 1, 1, 1.0,
   'claude-fable-5', 240,
   CURRENT_TIMESTAMP);
```

### Endpoint registry

```
ENDP-4000016: GET /api/implementation-patterns
ENDP-4000017: GET /api/implementation-patterns/{pattern_id}/runs
```

### Bootstrap dataset registry

```
BDS-5000014: implementation_patterns
```

---

## Validation Checklist

| # | Check | Command |
|---|-------|---------|
| 1 | Python syntax (app.py) | `python3 -m py_compile app.py` |
| 2 | Python syntax (init_db.py) | `python3 -m py_compile scripts/init_db.py` |
| 3 | Seed idempotent | `python3 scripts/init_db.py` (run twice) |
| 4 | JavaScript syntax | `node --check static/js/dpmtf-app.js` |
| 5 | No new innerHTML | `git diff -- static/js/dpmtf-app.js \| grep innerHTML` |
| 6 | Diff scope | `git diff --stat` |
| 7 | ALTER TABLE safe | Verify try/except guards in init_db.py |

---

## Allowed Files

- `scripts/init_db.py`
- `app.py`
- `templates/index.html`
- `static/js/dpmtf-app.js`
- `static/css/dpmtf-theme.css`
- `docs/governance-templates/10_CHANGELOG.md`
- `docs/governance-templates/11_NEXT_CONTEXT.md`
- `docs/governance-templates/12_IMPLEMENTATION_REPORT.md`

---

## Out of Scope (deferred to 2H+)

- `model_pricing` table (dynamic token cost lookup)
- Pattern recommendation engine (`GET /api/patterns/recommend`)
- Automatic pattern extraction from git diffs
- Pattern-to-template linking (needs Prompt Template Manager from 2H)

---

## Success Criteria

1. `prompt_runs` accepts and stores all 6 new model metadata fields
2. POST /api/prompt-runs automatically classifies runs into patterns when `file_signature` + `constraint_set` are provided
3. GET /api/implementation-patterns returns aggregated pattern statistics
4. Frontend displays patterns with color-coded success rates and expandable run history
5. PRUN-2E-0001 is backfilled with pattern data and PAT-0001 exists
6. All validation checks pass
7. Seed script is idempotent
