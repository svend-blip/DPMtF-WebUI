# 30 — FRONTEND GOVERNANCE

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines mandatory frontend rules for DPMtF-WebUI. Ensures frontend impact
is never forgotten in design, implementation, or review. All roles MUST
follow these rules when frontend is affected.

## When to Use

- **Architect:** Include Frontend Impact section in all designs.
- **Implementor:** Follow panel registration rules. Never skip Frontend Impact.
- **Review:** Fail any deliverable missing Frontend Impact.
- **Any role:** If UI changes, this file applies.

---

## Frontend Impact — Mandatory Output

Every design, implementation, and review MUST include one of:

### Frontend impact

```markdown
## Frontend Impact

- Frontend impact: <what changes in the UI>
- index.html impact: <yes/no, what changes>
- Panel group/subgroup: <which group, which subgroup>
- Existing panel reused: <yes/no, which>
- New panel needed: <yes/no, why>
- Frontend verification: <how to verify the change>
```

### No frontend impact

```markdown
## Frontend Impact

No frontend impact.

Reason: <why frontend is not affected>
```

---

## Panel System Rules

### Panel Groups (Fixed)

```
Daily → Journals → Reports → Periodic → Setup → Job Queue → Experimental
```

Panel groups are fixed. Never add new groups without Human approval.
Experimental was added by Human decision 2026-08-30 (see 25_DECISIONS.md):
it is always the LAST group and holds panels whose everyday value is
unproven. Empty groups (Journals, Reports, Periodic) are hidden via
`user_panel_groups.is_visible = 0` until they gain content.

### Subgroups (Database-Driven)

Subgroups are defined in `panel_subgroups` and mapped via
`panel_subgroup_mappings`. They control collapse/expand behavior.

**Rules:**
- Subgroups are database-driven — no HTML changes needed for new subgroups
- If no subgroups defined: implicit "All" subgroup, flat display
- `is_visible = 0` hides the element via CSS class `dpmtf-hidden`

### How to Add a New Panel

1. **Add HTML section** in `templates/index.html` with a `data-slot` attribute on the heading:
   ```html
   <section id="my-new-section">
     <h3 data-slot="my_new_title">My Title</h3>
     <div id="my-new-content"></div>
   </section>
   ```

2. **Register subgroup** in `scripts/init_db.py` — `panel_subgroups_seed`:
   ```python
   ("sg_setup_mynew", "setup", "Min Titel", "My Title", 8, 1),
   ```

3. **Register mapping** in `scripts/init_db.py` — `panel_subgroup_mappings_seed`:
   ```python
   ("my_new_title", "sg_setup_mynew"),
   ```

4. **Add i18n labels** in `scripts/init_db.py` for the title and any UI text.

5. **Add JavaScript** in `static/js/dpmtf-app.js` to populate the content div.

### Prohibited Patterns

- **Do NOT** add panels directly in HTML without subgroup registration
- **Do NOT** hardcode English strings — use `lbl(key, fallback)`
- **Do NOT** use `innerHTML` for dynamic content — use `createElement()`/`textContent`/`appendChild()`
- **Do NOT** create new panel groups — use existing groups
- **Do NOT** skip i18n — every user-facing string needs a label

---

## Coding Standards (Summary)

Full rules: [[12_CODING_STANDARD]]

- `const` by default, `let` only when reassignment needed. Never `var`.
- Event delegation on container elements, not individual listeners.
- Class-based selectors (not ID selectors for styling).
- No inline `style=""` attributes for layout.
- Dark theme (GitHub-dark palette). No light-theme colors.
- `dpmtf-hidden` class for hiding elements.

---

## Validation

Full rules: [[13_VALIDATION]]

- `node --check static/js/*.js` MUST pass
- `grep -RIn "innerHTML" static/ templates/` MUST be empty
- All user-facing text MUST use `lbl(key, fallback)`
- `python3 scripts/init_db.py` MUST run without errors (idempotent)

---

## Review Check

Review MUST verify:

- [ ] Frontend Impact section present
- [ ] "No frontend impact" has a reason (if claimed)
- [ ] UI changes specify panel group/subgroup
- [ ] New panels are registered in `panel_subgroups` + `panel_subgroup_mappings`
- [ ] i18n labels exist for all new UI text
- [ ] No `innerHTML` in new code
- [ ] `node --check` passes
- [ ] `init_db.py` runs idempotent

**Missing Frontend Impact = fail**

---

## Related Files

| File | Role |
|------|------|
| `templates/index.html` | Main HTML template (SPA) |
| `static/js/dpmtf-app.js` | Frontend JavaScript |
| `static/css/theme.css` | Dark theme CSS |
| `scripts/init_db.py` | Panel subgroups, mappings, i18n labels |
| [[12_CODING_STANDARD]] | Full coding rules |
| [[13_VALIDATION]] | Full validation rules |
| [[14_ARCHITECTURE]] | Panel group architecture |
| [[17_DATABASE]] | Panel subgroup schema |
