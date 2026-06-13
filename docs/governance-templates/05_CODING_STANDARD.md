# Coding Standard

## Purpose

This governance document defines the coding standards for all roles in the DPMtF prompt loop. These rules enforce consistency, safety, and maintainability across AI-assisted and human-authored changes. Every Implementer must follow these standards; every Validator must check compliance.

## When to Use

- **Implementer step**: Read before writing any code to ensure compliance.
- **Validator step**: Check produced changes against these rules.
- **After `/clear`**: Reconstruct coding expectations without relying on chat memory.

## Required Inputs

| Input | Description |
|-------|-------------|
| Language being modified | Python, JavaScript, CSS, Markdown, or Shell. |
| Existing code style | The surrounding code's conventions. |

## Required Outputs

- Code that matches existing style (indentation, naming, comment density).
- Syntax-checked files before commit.
- No broad refactor — only targeted edits within scope.

---

## General Rules

1. **No new dependencies** unless explicitly authorized by Human Approval Gate.
2. **Temporary hiding is a migration tactic only** — when migrating an existing project, temporarily hiding old code or UI panels (CSS class, conditional guard, feature flag) is allowed if cleanup/removal is explicitly postponed and documented. Hidden code must be clearly marked as temporary with a planned cleanup date or phase. New projects and AI PC Resource WebUI v3 must implement cleanly and should not create irrelevant hidden panels or code by default.
3. **Deletion is valid when scoped** — removing code, panels, or functionality is allowed when the phase scope explicitly authorizes it, all references are verified, validation passes, Human Approval Gate approves (if user-visible behavior is removed), and the change is documented in `CHANGELOG.md` and `DECISIONS.md`.
4. **Match existing style** — indentation, naming conventions, comment density. Do not reformat unrelated code.
5. **One logical change per task** — do not mix unrelated fixes.
6. **Stop after verification** — do not expand scope mid-task.
7. **Targeted edits only** — edit the specific lines that need to change. Do not rewrite entire files.

## Prohibited Patterns (Learned from Project History)

The following patterns are forbidden unless explicitly approved:

- **No heredocs for multi-line writes** — avoid `cat << 'EOF' > file` for writing code files. Use targeted edits instead.
- **No broad shell writes** — do not use shell commands to overwrite entire files when only a few lines need to change.
- **No extra parameters "just in case"** — functions and scripts take only the arguments they need now. Do not add speculative parameters.
- **No guessing operational targets** — if the backend resolves a target (port, path, model), the script must accept it as an explicit argument, not hardcode or guess.
- **No repeated patching on structural mismatch** — if the code structure doesn't match expectations after two attempts, stop and escalate to Solution Architect for redesign.

## Python

1. Run `python3 -m py_compile <file>` to verify syntax before committing.
2. Follow PEP 8 for formatting where practical.
3. Document functions with docstrings matching existing conventions in the file.
4. Database queries must use parameterized statements (no string interpolation for SQL).
5. Import ordering: standard library → third-party → local imports, separated by blank lines.

## JavaScript / Frontend DOM Safety

1. Run `node --check <file>` to verify syntax before committing.
2. Use `camelCase` for variables and functions; match existing naming patterns.
3. No global state mutation without an explicit comment explaining why.
4. DOM manipulation should be localized — avoid side effects on unrelated elements.
5. Event handlers must be properly removed when panels are hidden or destroyed.

### Frontend DOM Safety (XSS Prevention)

The following rules prevent XSS and DOM-injection vulnerabilities:

1. **Do not use `innerHTML`** for rendering dynamic content. Using `innerHTML` with user-supplied or dynamically generated data is an auto-fail in validation unless explicitly approved at the phase level.
2. **Use safe DOM APIs** — construct elements using `document.createElement()`, set text via `textContent`, and attach nodes with `appendChild()` or `replaceChildren()`.
3. **Clearing containers** — to empty a container, use `element.replaceChildren()` rather than `element.innerHTML = ""`.
4. **Approved exceptions** — if `innerHTML` must be used (e.g., rendering pre-authenticated static markup), it requires explicit phase-level approval AND a short security justification documented in the implementation report. Any exception is recorded as `approved_innerHTML_exception` in the validation report.

### Frontend i18n (Internationalization) — 4-Layer Architecture

**ALL user-visible frontend text MUST use the full 4-layer i18n system.** This is not optional — it is a mandatory routine, same priority as the innerHTML rule.

The 4-layer architecture (aligned with ENO, documented 2026-06-13):

```
Lag 1: ui_text_slots        — stable frontend placement IDs (slot_key)
         ↓
Lag 2: ui_text_slot_labels  — mapping table: slot_key → label_key
         ↓                    (multiple slots CAN map to same label)
Lag 3: ui_labels            — semantic label with default_text fallback
         ↓
Lag 4: ui_label_translations — locale-specific translated_text
```

**API contract:** `/api/ui-labels/{domain}?locale=` MUST traverse all 4 layers and return `{slot_key: resolved_text}`. The frontend `lbl()` function and `data-slot` attributes use `slot_key` as the lookup key.

**Rules:**
1. **Use `lbl(slot_key, fallback)` for every user-visible string** — table headers, button labels, headings, status messages, placeholder text, badge labels. The first argument is a `slot_key` (unique position ID). The `fallback` is the English default shown when a translation is missing.
2. **Every `slot_key` must have a `ui_text_slots` row** — registered in the slots table with a description.
3. **Every `slot_key` must have a `ui_text_slot_labels` mapping** — binding it to a `label_key`.
4. **Every `label_key` must have a `ui_labels` row** — with `label_domain`, `default_text`, and `label_id`.
5. **Every label must have `da-DK` and `en-US` translations** — seeded in `ui_label_translations`. Danish is the primary language; English is the fallback.
6. **No hardcoded English strings in DOM construction** — `el("th", null, "Name")` is forbidden. Use `el("th", null, lbl("slot_col_name", "Name"))`.
7. **Validation check:** `grep -RIn '"[A-Z][a-z]' static/js/` should return ONLY `lbl()` fallback strings and CSS class names — no bare user-visible English.
8. **New phases must include complete 4-layer i18n seed data** — the phase's implementation report must list all new `slot_key`s, `label_key`s, and confirm all 4 layers are populated with both da-DK and en-US translations.

**Rationale:** The 4-layer architecture enables changing frontend text at the database level without touching HTML: (a) update a translation in layer 4 to change text for all slots using that label, (b) update a mapping in layer 2 to point a slot to a different label. This is the standard aligned with ENO and must be preserved in all future DPMtF-derived projects.

## CSS

1. Use class-based selectors; avoid inline styles unless dynamically generated by JS.
2. Group related rules together (e.g., all panel layout rules in one block).
3. When temporarily hiding panels during migration (existing projects only), use a named class (`dpmtf-hidden-phase-X`) and include an inline comment explaining the temporary nature and planned cleanup phase. New projects should implement cleanly — do not create hidden panels by default.

## Shell Scripts

1. Run `bash -n <file>` to verify syntax before committing.
2. Use explicit arguments — do not hardcode paths or port numbers.
3. Safe quoting: always quote variables (`"$VAR"`, not `$VAR`) unless word splitting is intentional.
4. Use `set -euo pipefail` at the top of scripts for safety.
5. Do not use heredocs to write code files — use them only for inline documentation or help text.

## Markdown / Governance Files

1. Use ATX headings (`#`, `##`, `###`).
2. Keep tables consistent with header separators (`|---|---|`).
3. **Append only** to `CHANGELOG.md` and `DECISIONS.md` — never edit existing entries.
4. Use consistent terminology across governance documents:
 - "governance documents" for Markdown files in `docs/governance-templates/`.
 - "target project" for the project being governed.
 - "role-based prompt loop" for the Analyst → Architect → Engineer → Implementer → Validator flow.

---
