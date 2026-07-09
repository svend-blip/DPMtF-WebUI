# Model Allocator config-dashboard — Design

**Date:** 2026-07-10
**Status:** Approved (brainstorm)
**Repos:** `model-allocator` (CLI write layer) + `DPMtF-WebUI` / Father (WebUI page)

## 1. Problem & goal

The Model Allocator's configuration — model aliases (`models.yaml`), role→alias
mappings (`roles.yaml`), and runtime profiles (`runtime_profiles.yaml`) — is
today edited **by hand as YAML**. The Father WebUI can only *assign* an existing
alias to a bridge role/step (V3A) and *drive* its runtime (V3B); it cannot
create or edit the aliases/roles themselves.

**Goal:** a dedicated **Model Allocator** page in the Father WebUI that both
edits the allocator's own configuration (aliases + roles) and shows/controls
runtime status — replacing hand-editing of two of the three YAML files.

## 2. Scope

**In scope**
- CRUD on **aliases** (`models.yaml`) and **roles** (`roles.yaml`) from the WebUI.
- Runtime profiles shown **read-only** (feed the profile dropdown + a reference panel).
- Runtime status/lifecycle reusing the existing validate/status/start/stop endpoints.
- New write commands in the allocator CLI to persist changes.

**Out of scope (stays hand-edited YAML for now)**
- Editing `runtime_profiles.yaml` (infrastructure; sensitive; changes rarely).
- A standalone allocator HTTP service (persistence stays CLI-shell-out).
- New Python dependencies (PyYAML 6.0 already covers read+write).

## 3. Architecture

Three-layer separation is preserved:

```
Father WebUI  →  new "Model Allocator" page (3-column dashboard)
     │  shells out (subprocess), same pattern as existing list/validate/status
     ▼
model-allocator CLI  →  new `config` subcommands (read JSON + write YAML)
     ▼
models.yaml / roles.yaml  (runtime_profiles.yaml read-only, never written by us)
```

**Persistence decision:** write capability lives in the allocator CLI, keeping
the allocator the owner of its own config and respecting the project boundary
(Father must not write into another repo's files directly). The WebUI never
touches the YAML files — it only calls CLI commands.

**Page layout:** single 3-column dashboard — `Aliases | Roles | Detail+Status`.

```
┌ Model Allocator ──────────────────────────────────────┐
│ ALIASES       │ ROLES         │ DETAIL / STATUS        │
│ imple-fast  ▸ │ imple01       │ Alias: imple-fast      │
│ imple01-local │ claude-test   │ profile [local_ollama▾]│
│ review-cloud  │ openrouter-t. │ model [qwen36-27b-q4km]│
│ llama-test    │ + New role    │ ctx[131072] ☑opencode  │
│ + New alias   │               │ ● Running pid4823:11434│
│               │               │ [Val][Start][Stop][Save]│
└───────────────┴───────────────┴────────────────────────┘
```

## 4. Layer 1 — Allocator CLI write commands (`model-allocator` repo)

New module `src/model_allocator/config_writer.py`; new `config` subcommand group
in `cli.py`.

| Command | Effect |
|---|---|
| `config show` | Print the full config as JSON: `{ "aliases": {...}, "roles": {...}, "profiles": {...} }`. One call populates the whole UI. |
| `config set-alias --name X --json '{...}'` | Upsert an alias into `models.yaml`. |
| `config delete-alias --name X` | Delete an alias. Refused (nonzero exit) if a role still references it. |
| `config set-role --name X --json '{...}'` | Upsert a role into `roles.yaml`. |
| `config delete-role --name X` | Delete a role. |

**Input format:** a JSON object payload via `--json` (handles nested `clients` /
`client_aliases` cleanly, avoids flag explosion). The `--name` flag is the key;
the JSON is the value body (without the name).

**Validation before write** (reuse the existing loader/resolver load path):
- `set-alias`: referenced `runtime_profile` must exist.
- `set-role`: `default_alias` and every value in `client_aliases` must reference
  an existing alias.
- Incoherent writes are rejected with a nonzero exit code and an error payload
  (JSON) on stdout/stderr.

**Safe write** (defensive, given prior DB-loss incident history):
1. Write `<file>.bak` (copy of current file) before overwriting.
2. Serialize with `yaml.safe_dump(..., sort_keys=False, allow_unicode=True)`.
3. Write to a temp file in the same dir, then `os.replace()` (atomic).

Comment/formatting loss on `models.yaml` / `roles.yaml` is acceptable (they carry
no meaningful comments). `runtime_profiles.yaml` is never written and keeps its
comments.

**Tests (pytest, existing suite):** upsert-then-load round-trip, delete,
validation rejection (missing profile / dangling alias reference), delete refused
when referenced, `.bak` creation + atomic replace, `config show` JSON shape.

## 5. Layer 2 — WebUI backend (`routers/bridge.py`)

New endpoints, mirroring the existing subprocess + timeout + `HTTPException`
pattern already used by the allocator endpoints:

| Method + path | CLI call |
|---|---|
| `GET /api/bridge-v2/allocator/config` | `config show` |
| `POST /api/bridge-v2/allocator/config/alias` (body `{name, definition}`) | `config set-alias` |
| `DELETE /api/bridge-v2/allocator/config/alias/{name}` | `config delete-alias` |
| `POST /api/bridge-v2/allocator/config/role` (body `{name, definition}`) | `config set-role` |
| `DELETE /api/bridge-v2/allocator/config/role/{name}` | `config delete-role` |

Reused unchanged: `/allocator/validate`, `/allocator/status`,
`/allocator/start`, `/allocator/stop`.

Error handling: CLI nonzero exit → HTTP 4xx (validation) or 502 (execution) with
the CLI's error message; 30s subprocess timeout as in the existing endpoints.
The allocator path comes from `config.get_project_path("model-allocator")` — no
hardcoded paths.

## 6. Layer 2 — WebUI frontend (new `static/js/allocator.js`)

A **new JS file** rather than growing `dpmtf-app.js` (already 3700+ lines),
matching the "focused files" principle.

- **Nav:** new top-level "Model Allocator" section/entry.
- **Data flow:** `GET config` → render Aliases + Roles lists → select an item →
  populate the detail form → Save → `POST upsert` → reload config → re-render.
  Validate/Start/Stop hit the runtime endpoints.
- **Alias detail form:** `name`, `runtime_profile` (dropdown from profiles),
  `real_model` / `model_path`, `context`, `lifecycle_policy` (dropdown),
  `clients` (opencode / claude-code checkboxes). Runtime-status subsection reuses
  validate/status/start/stop + the existing localStorage validate-cache. Save / Delete.
- **Role detail form:** `name`, `config_dir`, `default_alias` (dropdown from
  aliases), `client_aliases` (opencode → alias dropdown, claude-code → alias
  dropdown). Save / Delete.
- **Profiles:** read-only reference panel; also populate the alias profile dropdown.

**Compliance (CLAUDE.md §4):**
- All user-facing text via `lbl(key, fallback)`; new labels seeded in
  `init_db.py` across all locales (da-DK / en-US at minimum, matching existing
  allocator labels).
- **No `innerHTML`** — `createElement` / `textContent` / `appendChild` / `replaceChildren`.
- Event delegation on container elements; `const` by default, `let` only when reassigned.
- Class-based selectors, dark GitHub-dark theme; no inline layout styles.

## 7. Error handling

- CLI nonzero → endpoint error → UI error banner with the message.
- Delete and Stop are guarded by `confirm()`.
- `delete-alias` refused server-side when a role still references the alias; the
  UI surfaces the refusal.
- Validation errors (missing profile, dangling reference) shown inline in the form.

## 8. Testing & validation

**model-allocator (Phase 1):** pytest for `config_writer` per §4.

**WebUI (Phase 2):** the 8-point checklist —
`python3 -m py_compile app.py routers/bridge.py`, `node --check static/js/allocator.js`,
`grep -RIn innerHTML static/` (empty), i18n check (all text via `lbl()`),
diff scope, no new deps, schema review (init_db label seeds only) — plus a manual
walk-through of the page (create/edit/delete an alias and a role, validate,
start/stop).

## 9. Phasing & git boundary

- **Phase 1 — `model-allocator` repo:** `config_writer.py` + `config` CLI
  subcommands + pytest. Self-contained; its own commit.
- **Phase 2 — Father WebUI:** endpoints in `routers/bridge.py`, new
  `static/js/allocator.js`, nav entry, i18n label seeds in `init_db.py`. Its own
  commit.

**Governance:**
- Only the Human commits/pushes; changes stay unstaged until approval (CLAUDE.md §5).
- `init_db.py` edits (new labels) are approval-required per File Access rules (§10).
- No new dependencies (PyYAML already present) → no dependency approval needed.
- No hardcoded paths; allocator path via `config.get_project_path(...)`.

## 10. Open questions / deferred

- Editing `runtime_profiles.yaml` from the UI — deferred; hand-edited for now.
- Standalone allocator HTTP service — deferred; CLI-shell-out is sufficient.
