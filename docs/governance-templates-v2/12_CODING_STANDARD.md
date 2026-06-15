# 12 — CODING STANDARD

> **en-US is the standard language for all governance-templates-v2 files.**
> All code, comments, documentation strings, and commit messages MUST be in
> English (en-US).

## Purpose

Defines coding rules for all languages used in DPMtF-governed projects. These
rules apply to all code produced by the Implementor role and are enforced by
the Review role during validation.

## When to Use

- **Implementor:** Apply these rules to every line of code produced.
- **Review:** Check all diffs against these rules.
- **Architect:** Reference these rules in implementation prompts.

---

## Python

| Rule | Description |
|------|-------------|
| **Syntax check** | `python3 -m py_compile <file>` MUST pass before signaling completion. |
| **PEP 8** | Follow PEP 8 style guide. |
| **Parameterized SQL** | All SQL queries MUST use parameterized statements — never string concatenation. |
| **No hardcoded paths** | Ports, paths, model names MUST come from explicit arguments or configuration. |
| **f-strings** | Prefer f-strings over `.format()` or `%` formatting. |
| **Type hints** | Use type hints for function signatures where practical. |

## JavaScript

| Rule | Description |
|------|-------------|
| **Syntax check** | `node --check static/js/*.js` MUST pass for each modified file. |
| **NO innerHTML** | `innerHTML` for dynamic content is an auto-fail. Use `createElement()` / `textContent` / `appendChild()` / `replaceChildren()`. |
| **lbl() helper** | ALL user-facing text MUST use `lbl(key, fallback)`. No hardcoded English strings in DOM construction. |
| **data-slot attributes** | Frontend elements reference `slot_key` via `data-slot` attributes, not `ui_labels` directly. |
| **Event delegation** | Use event delegation on container elements, not individual listeners per item. |
| **const/let** | Use `const` by default, `let` only when reassignment is needed. Never `var`. |

## CSS

| Rule | Description |
|------|-------------|
| **Class-based selectors** | Use class selectors, not ID selectors for styling. |
| **No inline styles** | No inline `style=""` attributes for layout. Use CSS classes. |
| **Dark theme** | All projects use dark theme (GitHub-dark palette). No light-theme colors. |
| **Temporary hiding** | Use `dpmtf-hidden` class for hiding elements. `is_visible = 0` in database controls visibility. |

## Shell

| Rule | Description |
|------|-------------|
| **Syntax check** | `bash -n <file>` MUST pass before signaling completion. |
| **set -euo pipefail** | Every script MUST start with `set -euo pipefail`. |
| **No heredocs for code** | Do not use heredocs to generate code files. |

## Markdown

| Rule | Description |
|------|-------------|
| **ATX headings** | Use `#` style headings, not underline style. |
| **Consistent tables** | Align table columns for readability. |
| **Append-only logs** | [[25_DECISIONS]] and [[26_CHANGELOG]] are append-only — add new entries at the bottom. |

## 4-Layer i18n Architecture (Mandatory)

The four-layer internationalization architecture is mandatory across all projects:

```
ui_text_slots (slot_key = unique position ID)
  → ui_text_slot_labels (slot → label mapping)
    → ui_labels (semantic label with default_text)
      → ui_label_translations (locale-specific text)
```

**Rules:**
- API MUST traverse all 4 layers and return `{slot_key: text}`.
- Multiple slots CAN map to the same label.
- Frontend `data-slot` attributes and `lbl()` calls use `slot_key` as the key.
- Each label MUST have seed data in both `da-DK` and `en-US` locales.
- New labels require `ui_labels` + `ui_label_translations` entries — this is
  routine, not optional.

## Prohibited Patterns

These patterns are prohibited based on project history:

1. **innerHTML for dynamic content** — auto-fail in validation.
2. **Hardcoded English strings in frontend** — auto-fail. Use `lbl()`.
3. **Guesswork on operational targets** — ports, paths, model names MUST be explicit.
4. **Silent failures** — catch blocks MUST log or report errors.
5. **New dependencies without Human approval** — auto-fail.
6. **More than 2 failed patching attempts** — stop, document, escalate.

---
