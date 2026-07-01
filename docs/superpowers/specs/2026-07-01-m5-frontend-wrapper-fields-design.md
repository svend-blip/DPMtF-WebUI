# Design Spec: M5 — Frontend Wrapper-Field Surfacing

> **Status:** Draft — awaiting approval
> **Date:** 2026-07-01
> **Scope:** Surface the net-new `trade_output_v001` wrapper fields in the
> trade-ui frontend (Daily cards + Journal audit view) in a single pass.
> Final phase of the JSON-standard migration.

## 1. Purpose

The `trade_output_v001` migration (M1–M4, M6) made 15 wrapper fields available
on every role output, persisted to `role_outputs` columns. The frontend still
renders only the original 8-field subset. M5 surfaces the net-new fields so the
frontend is optimized relative to the migration in one pass — rather than
returning to add fields piecemeal.

This fulfills two use cases equally:
- **Daily decision-support** — quality/simulation_id visible at a glance on cards.
- **Audit/debuggability** — lineage (input_refs, evaluates_simulation_ids)
  drill-down in the Journal.

## 2. Net-New Fields (already in `role_outputs` columns)

The frontend already shows: `flow_run_id`, `role_key`, `output_type`,
`created_at`, `status`, `model_name`. Net-new fields to surface:

| Field | Where surfaced | Form |
|-------|----------------|------|
| `quality` (data_quality + confidence) | Daily cards + Journal | badge (color + number) |
| `simulation_id` | sim/score/learn cards + Journal | monospace label (omit if null) |
| `role_stage` | Daily cards + Journal | small label |
| `input_refs` | Journal expandable row | list of upstream refs |
| `evaluates_simulation_ids` | Journal expandable row | list of SIM ids |

Not surfaced: `flow_type` (already structural via Daily/Periodic panel
placement), `schema_version` (internal).

No DB changes — the columns already exist:
- On `role_outputs` (L2 migration): `simulation_id`, `evaluates_simulation_ids_json`,
  `quality_json`, `input_refs_json`, `role_stage`, `flow_type`, `schema_version`.
- On `simulated_trades` (M3): `simulation_id`.
- On `score_results` (M3): `evaluates_simulation_ids_json`.

The dashboard's simulated_trades / score_results sections SELECT from those
tables; the candidate/review sections and the Journal SELECT from `role_outputs`.

## 3. Architecture

Presentation-layer change only. Two API endpoints extend their SELECT to
return the new columns (parsing the `_json` TEXT columns); frontend renderers
display them as badges/labels + an expandable Journal row.

```
role_outputs columns → API SELECT + JSON-parse → response → app.js → DOM
                                                           (createElement/textContent, no innerHTML)
```

## 4. Components

### 4.1 Backend — `/api/dashboard/daily` (`app.py:326`)
Add to the SELECT for `latest_candidates` and `latest_reviews`:
`simulation_id, role_stage, flow_type, quality_json`. Parse `quality_json` →
`quality` object in each returned row. Add `simulation_id` to the
simulated_trades / score_results sections where those are returned.

### 4.2 Backend — `/api/journals/role-outputs`
Add to the SELECT: `simulation_id, role_stage, flow_type, quality_json,
input_refs_json, evaluates_simulation_ids_json`. Parse the three `_json`
columns into objects in the response (defensive try/except per row).

### 4.3 Frontend — Daily cards (`static/js/app.js`)
- `quality` badge: `data_quality` color (high=green, medium=yellow, low=red,
  unknown=gray) + confidence number (e.g. `0.68`), omitted when null.
- `simulation_id`: monospace label on sim/score/learn cards only; omitted if null.
- `role_stage`: small label.

### 4.4 Frontend — Journal role-outputs table (`app.js`)
- New columns: `simulation_id`, `data_quality`.
- Expandable rows: click a row → toggle a sub-row rendering `input_refs` (list
  of `{flow_run_id, role_key, output_type}`), `evaluates_simulation_ids`
  (list of SIM ids), and the full `quality` block (confidence, data_quality,
  warnings, missing_fields).

### 4.5 CSS + i18n
- Reuse `dpmtf-badge` classes; add `data_quality` color variants
  (success/warning/danger/muted).
- All new user-facing text via `lbl(key, fallback)` + 4-layer seed data
  (da-DK, en-US, de-DE, sv-SE): column headers ("Simulation ID", "Data
  Quality"), expandable labels ("Lineage", "Built on", "Evaluates",
  "Warnings", "Missing fields"), badge fallbacks.

## 5. Data Flow

`role_outputs` columns → API SELECT → `json.loads()` on `quality_json` /
`input_refs_json` / `evaluates_simulation_ids_json` → response JSON →
`app.js` render functions → DOM via `createElement` / `textContent`
(no `innerHTML` for dynamic content).

## 6. Error Handling

- `simulation_id` null → omit the label.
- `quality_json` null or unparseable → "unknown" gray badge, no crash.
- `input_refs` empty → "No upstream refs" muted text.
- `confidence` null → omit the number, keep the data_quality badge.
- All JSON parsing wrapped in try/except → silent degradation (degraded badge
  / empty list), never a 500 or a broken render.

## 7. Testing

### Automated
- Extend `test_v10_gates.py` (or `test_v01_gates.py` test 10) to assert
  `/api/dashboard/daily` returns `quality` and `simulation_id` keys on
  candidate/review objects.
- Add an assertion that `/api/journals/role-outputs` response rows include
  `simulation_id`, `quality`, `input_refs`, `evaluates_simulation_ids`.
- 62/62 regression must still pass.

### Manual
- MV-03 update: Daily panel renders `quality` badges + `simulation_id` on
  sim/score/learn cards.
- New MV: Journal role-outputs row expands to show lineage (input_refs,
  evaluates_simulation_ids, full quality block).

### Checklist (per CLAUDE.md §6)
- `python3 -m py_compile app.py`
- `node --check static/js/app.js`
- `grep -RIn "innerHTML" static/ templates/` — empty
- All new user-facing text uses `lbl()` — no hardcoded English
- `curl -s http://localhost:9140/api/health` → healthy

## 8. Out of Scope

- Filtering Daily cards by `data_quality` (YAGNI until scoring cycle runs).
- `simulation_id` cross-linking between sim/score/learn cards (YAGNI).
- A dedicated lineage graph/tree panel (rejected in brainstorming — expandable
  Journal row suffices).
- Surfacing `flow_type` (already structural) or `schema_version` (internal).

## 9. Sequencing

M5 is the final migration phase. After it, the migration is complete (M1–M6
all done). Unblocks nothing downstream — it is polish that makes the migrated
data visible. eToro V1.1 (separate) consumes `simulation_id` and `quality`
from the DB, not from this frontend.
