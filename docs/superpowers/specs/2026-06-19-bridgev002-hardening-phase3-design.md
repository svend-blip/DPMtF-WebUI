---
name: bridgev002-hardening-phase3-convention-rules
date: 2026-06-19
handoff: 104
status: approved
---

# BridgeV002 Hardening — Fase 3: Convention Rules

## Problem Statement

`bridge_flow_steps` stores raw strings for `deliverable_dir`, `deliverable_pattern`, and `error_msg`. These are hardcoded per step, duplicating logic that should be templates. A convention rules table provides parameterized templates so steps reference conventions rather than inline values — the foundation for Fase 4's auto-fill UX.

## Scope

| File | Change | Lines (est.) |
|------|--------|-------------|
| `scripts/init_db.py` | Add `bridge_convention_rules` table + seed data + ALTER to add FK column on `bridge_flow_steps` + UPDATE existing rows | ~50 |
| `app.py` | Add GET endpoint for convention rules | ~12 |
| Total | ~62 lines across 2 files |

## Schema Design

```sql
CREATE TABLE IF NOT EXISTS bridge_convention_rules (
    rule_key TEXT PRIMARY KEY,
    step_type TEXT NOT NULL,
    dir_template TEXT NOT NULL,
    pattern_template TEXT NOT NULL,
    error_template TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

| Column | Type | Purpose |
|--------|------|---------|
| `rule_key` | TEXT PK | Unique identifier: `"handoff"`, `"callback"`, `"verdict"` |
| `step_type` | TEXT NOT NULL | Display label for dropdowns: "Handoff", "Callback" |
| `dir_template` | TEXT NOT NULL | Deliverable directory template with `{ID}` placeholder support |
| `pattern_template` | TEXT NOT NULL | Filename pattern (e.g. `{ID}-handoff.md`) |
| `error_template` | TEXT | Error message template: `"Failed to deliver {step_type} to {to_role}."` |

### Why this schema?

Templates live at the convention level, not per-step. When a step references a `rule_key`, the runtime (Fase 5) can resolve `{ID}`, `{step_type}`, and `{to_role}` from context. This eliminates duplicate directory names and patterns across all steps.

## Seed Data

Three conventions cover the existing flow steps:

```python
[
    ("handoff", "Handoff",
     "reviewtoimplementor", "{ID}-handoff.md",
     "Failed to deliver handoff to {to_role}."),
    ("callback", "Callback",
     "implementertoreview", "{ID}-callback.md",
     "Failed to deliver callback to {to_role}."),
    ("verdict", "Verdict",
     "implementertoreview", "{ID}-review-verdict.md",
     "Failed to deliver verdict. Present to Human manually."),
]
```

### Mapping existing steps to conventions

| Existing step | dir + pattern | Maps to rule_key |
|--------------|---------------|-----------------|
| `*_to_implementer` (handoff) | reviewtoimplementor / `{ID}-handoff.md` | `"handoff"` |
| `*_callback`, `*_response` | various dirs / `{ID}-callback.md` | `"callback"` |
| `*_to_human` (verdict) | implementertoreview / `{ID}-review-verdict.md` | `"verdict"` |

**Exception:** Steps that use non-standard directories (e.g., `architecttoreview`, `reviewtoarchitect`) still map to closest convention (`callback`), but may need custom overrides. For Fase 3, we keep it simple — the 3 conventions cover the pattern, and future phases can add more rules or step-level overrides.

## ALTER + UPDATE Strategy

To avoid breaking existing steps, we add a `rule_key` column to `bridge_flow_steps`:

```sql
ALTER TABLE bridge_flow_steps ADD COLUMN rule_key TEXT REFERENCES bridge_convention_rules(rule_key)
```

Then update existing rows to reference the correct convention:

```python
updates = [
    ("handoff", "architect_to_implementer", "heavy"),
    ("handoff", "architect_to_implementer", "simplified"),
    ("callback", "implementer_to_review_heavy1", "heavy"),
    ("callback", "review_heavy1_to_heavy2", "heavy"),
    ("verdict", "review_heavy2_to_human", "heavy"),
    ("callback", "review_to_architect_escalation", "heavy"),
    ("handoff", "architect_to_implementer", "simplified"),
    ("callback", "implementer_to_reviewer_lite", "simplified"),
    ("verdict", "reviewer_lite_to_human", "simplified"),
    ("handoff", "review_to_architect", "escalation"),
    ("callback", "architect_to_review_response", "escalation"),
]
```

## API Endpoint

GET endpoint following existing pattern:

```python
@app.get("/api/bridge-v2/conventions")
async def bridge_v2_list_conventions():
    """Return all convention rules from database."""
```

Response format:
```json
{
    "count": 3,
    "conventions": [
        {
            "rule_key": "handoff",
            "step_type": "Handoff",
            "dir_template": "reviewtoimplementor",
            "pattern_template": "{ID}-handoff.md",
            "error_template": "Failed to deliver handoff to {to_role}."
        }
    ]
}
```

### Why GET-only?

Same rationale as Fase 2 — conventions are seed-data. POST/PUT/DELETE can be added when we build the full CRUD in Fase 4.

## Out of Scope
- Step-level auto-fill from conventions (Fase 4 frontend task)
- Parameterized template resolution at runtime (Fase 5 dispatch task)
- Adding more convention rules beyond the initial 3 (deferred)
