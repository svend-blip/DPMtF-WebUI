---
name: bridgev002-hardening-phase4-steps-crud
date: 2026-06-19
handoff: 105
status: approved
---

# BridgeV002 Hardening — Fase 4: Steps CRUD (Backend + Frontend)

## Problem Statement

`bridge_flow_steps` is only visible through DB queries. There is no API to create, read, update, or delete steps independently, and no frontend UI for managing steps within a flow. This phase adds the missing backend endpoints and a "Manage Steps" panel with auto-fill from convention rules.

## Scope

| File | Change | Lines (est.) |
|------|--------|-------------|
| `app.py` | Steps CRUD endpoints (GET list, POST create, PUT update, DELETE soft-delete) | ~120 |
| `static/js/dpmtf-app.js` | Steps UI: render, create form with dropdowns + auto-fill, edit, delete | ~250 |
| `templates/index.html` | Steps section container in Bridge Setup panel | ~15 |
| `scripts/init_db.py` | i18n labels for steps UI (da-DK + en-US) | ~40 |
| Total | ~425 lines across 4 files |

## Backend Design

### API Endpoints

Four endpoints follow the existing BridgeV002 pattern (`/api/bridge-v2/` prefix, lazy import from bridge_lib):

#### GET `/api/bridge-v2/steps/{flow_key}`
```json
{
    "steps": [{"id": 1, "step_key": "architect_to_implementer", ...}],
    "count": 5,
    "flow_key": "heavy"
}
```

Returns all steps for a given flow, ordered by sort_order. Includes convention and script metadata for frontend dropdowns.

#### POST `/api/bridge-v2/steps/{flow_key}`
```json
{
    "step_key": "my_step",
    "from_role": "architect",
    "to_role": "implementer",
    "rule_key": "handoff",
    "pre_dispatch_script": "role_setup",
    "post_dispatch_script": "role_teardown",
    "sort_order": 1
}
```

Creates a new step. `deliverable_dir` and `deliverable_pattern` are auto-filled from the convention rule if `rule_key` is provided. Returns created step or HTTP 409 on duplicate (same flow_key + step_key).

#### PUT `/api/bridge-v2/steps/{flow_key}/{step_id}`
```json
{
    "rule_key": "callback",
    "from_role": "implementer",
    "to_role": "reviewer_lite",
    "sort_order": 2
}
```

Updates step fields. Supports partial updates — only provided fields are changed. If `rule_key` changes, auto-fill dir/pattern from new convention. Returns updated step or HTTP 404 if not found.

#### DELETE `/api/bridge-v2/steps/{flow_key}/{step_id}`
Soft-delete: sets `is_active = 0`. Does not actually delete the row. Returns deleted step data or HTTP 404.

### Convention auto-fill logic (in app.py)

When a POST or PUT provides a `rule_key`, resolve the convention and populate:
- `deliverable_dir` ← `dir_template` from convention
- `deliverable_pattern` ← `pattern_template` from convention
- `error_msg` ← `error_template` with `{step_type}` already filled from convention's `step_type`

This is the core of Fase 4 — users select a convention dropdown and get correct paths without typing.

### Helper data in GET response

The GET endpoint should also return:
- Available roles (for dropdown population) — from bridge_roles table
- Available conventions (for auto-fill dropdown) — from bridge_convention_rules table
- Available scripts (for pre/post dispatch dropdowns) — from bridge_scripts table

This avoids 3 separate API calls on page load. Response format:
```json
{
    "steps": [...],
    "count": 5,
    "flow_key": "heavy",
    "available_roles": ["architect", "implementer", ...],
    "available_conventions": [{"rule_key": "handoff", "step_type": "Handoff"}, ...],
    "available_scripts": [{"script_key": "role_setup", "name": "Role Setup", "stage": "pre"}, ...]
}
```

## Frontend Design

### Steps Panel Structure

Add a `<section id="bridge-steps-section">` after the Flows section in `templates/index.html`:

```html
<section id="bridge-steps-section">
    <h3 data-slot="lbl_bridge_steps_title">Steps</h3>
    <div class="bridge-btn-row">
        <select id="bridge-steps-flow-select" data-slot="lbl_bridge_select_flow">Select Flow</select>
        <button id="bridge-add-step-btn" type="button" data-slot="lbl_bridge_step_add">Add Step</button>
    </div>
    <div id="bridge-steps-list-container" class="dpmtf-card-grid"></div>
</section>
```

### Form with dropdowns (created via createElement, NOT innerHTML)

The step form has these fields:
1. `step_key` — text input
2. `from_role` — dropdown populated from available_roles
3. `to_role` — dropdown populated from available_roles
4. `rule_key` — dropdown populated from available_conventions (with auto-fill on change)
5. `deliverable_dir` — text input, auto-filled from convention
6. `deliverable_pattern` — text input, auto-filled from convention
7. `pre_dispatch_script` — dropdown populated from available_scripts (stage=pre or both)
8. `post_dispatch_script` — dropdown populated from available_scripts (stage=post or both)
9. `error_msg` — text input, auto-filled from convention
10. `sort_order` — number input

### Auto-fill logic

When user selects a `rule_key`:
- Fetch the convention data (already in memory from GET response)
- Populate `deliverable_dir`, `deliverable_pattern`, and `error_msg` automatically
- User can override these values after auto-fill

### JavaScript functions

Following the existing pattern (Spor J), add ~10 new functions to dpmtf-app.js:

| Function | Purpose |
|----------|---------|
| `loadBridgeStepsFlow()` | Render flow selector dropdown |
| `fetchBridgeSteps(flow_key)` | GET steps for selected flow |
| `renderBridgeStepsList(steps, metadata)` | Render step cards in grid |
| `showCreateStepForm()` | Show inline form for new step |
| `autoFillFromConvention(rule_key)` | Populate dir/pattern/error from convention |
| `submitBridgeStep(flow_key, formData)` | POST or PUT step |
| `editBridgeStep(stepId, flow_key)` | Pre-populate form with existing data |
| `deleteBridgeStep(stepId, flow_key)` | Soft-delete step |

### i18n labels

New labels for the Steps section:
- `lbl_bridge_steps_title` — "Steps"
- `lbl_bridge_select_flow` — "Select Flow"
- `lbl_bridge_step_form_title` — "Add/Edit Step"
- `lbl_bridge_rule_key` — "Convention Rule"
- `lbl_bridge_script_pre` — "Pre-Dispatch Script"
- `lbl_bridge_script_post` — "Post-Dispatch Script"
- `lbl_bridge_auto_filled` — "(auto-filled from convention)"

Both da-DK and en-US translations needed.

## Out of Scope
- Parameterized script execution (Fase 5)
- Database cleanup (Fase 6)
- Full Convention CRUD (GET-only for now, conventions are seed data)
