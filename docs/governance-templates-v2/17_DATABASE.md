# 17 — DATABASE RUNTIME STATE

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines what lives in the database versus governance files. Clarifies the
boundary between runtime state and governance configuration. Prevents
confusion about where data should be stored and how schema changes are managed.

## When to Use

- **Architect:** Design data models within the defined architecture.
- **Implementor:** Understand where to store new data.
- **Review:** Detect unauthorized schema changes.

---

## Database vs Governance Files

| Lives In | What |
|----------|------|
| **Database (SQLite)** | UI text slots, slot-label bindings, labels, translations, user preferences, panel group visibility, panel subgroups, prompt templates, prompt runs, workflow runs, template_model_hitrates, git sync status, validation rules/runs, platform info, Claude sessions, domain-specific data |
| **Governance files** | Project identity ([[10_PROJECT]]), scope ([[11_SCOPE]]), coding standards ([[12_CODING_STANDARD]]), validation rules ([[13_VALIDATION]]), architecture ([[14_ARCHITECTURE]]), git policy ([[15_GIT_POLICY]]), decisions ([[25_DECISIONS]]), changelog ([[26_CHANGELOG]]), session state ([[27_NEXT_CONTEXT]]) |
| **Git** | All code, all governance files, migration scripts, seed data |

## Schema Change Policy

1. **Schema changes require Human approval** — trigger Human Approval Gate.
2. **Use `CREATE TABLE IF NOT EXISTS`** for new tables — idempotent.
3. **No `ALTER TABLE` without explicit Human approval and phase authorization.**
4. **Migration scripts** are stored in `scripts/` and tracked in git.
5. **Seed data** is managed in `scripts/init_db.py` — idempotent via `INSERT OR IGNORE`.

## Committing The Database — Checkpoint First

`databases/dpmtf.db` is committed alongside its migrations, as the exception
in `.gitignore` says, because it is the recovery point after a database loss.

**The database runs in WAL mode, and git tracks only the main file.** Recent
writes live in `databases/dpmtf.db-wal`, which is untracked. Committing the
main file alone therefore captures a database missing everything the WAL
still holds — and `git status` reports the file unchanged, because the file
genuinely has not changed. Nothing about the omission is visible.

Before `git add databases/dpmtf.db`, always:

```bash
sqlite3 databases/dpmtf.db "PRAGMA wal_checkpoint(TRUNCATE);"   # expect 0|0|0
```

Then verify the main file *alone* — not the live database, which reads the
WAL — has what you are claiming to commit:

```bash
cp databases/dpmtf.db /tmp/check.db
sqlite3 /tmp/check.db "SELECT MAX(id), (SELECT filename FROM schema_migrations
                                        ORDER BY id DESC LIMIT 1)
                       FROM schema_migrations;"
```

Found on 2026-08-13: the committed database was three migrations behind the
live one, and the commit that introduced the gap asserted in its message that
those migrations were present. The convention dates to migration 034 and
never checkpointed, so earlier database commits are likely stale by whatever
their WAL held. A recovery point that silently lags is worse than one that is
obviously missing, because it will be restored and believed.

## UI Text Slot Architecture

The UI text system uses a 4-layer registry:

```
ui_text_slots         — slot_key, domain
ui_text_slot_labels   — slot_key → label_key mapping
ui_labels             — label_key, default_text
ui_label_translations — label_key, locale, translated_text
```

**Rules:**
- Slots are stable position identifiers — not semantic labels.
- Multiple slots CAN map to the same label via `ui_text_slot_labels`.
- API returns `{slot_key: text}` by traversing all 4 layers.
- Frontend uses `data-slot` attributes and `lbl(slot_key, fallback)` calls.

## Panel Groups and Subgroups

```
user_panel_groups     — group_name, pattern_key, is_visible
panel_subgroups       — subgroup_key, group_name, is_visible
panel_subgroup_mappings — subgroup_key, subpattern_key, is_visible
```

**Rules:**
- Panel groups are fixed: Daily, Journals, Reports, Periodic, Setup.
- Subgroups are database-driven — no HTML changes needed for new subgroups.
- If no subgroups defined: implicit "All" subgroup, flat display.
- `is_visible = 0` hides the element via CSS class `dpmtf-hidden`.
- For implementation guide, see [[30_FRONTEND_GOVERNANCE]].

## Machine Profile

Machine Profiles are stored as JSON files in `profiles/`.

They are not stored in the database in Phase 1.

Reasons:
- Machine Profile must be readable before database-dependent runtime logic
- Machine Profile is machine-specific
- Local profiles must be git-ignorable
- Secrets must not be stored in Machine Profile

The active profile is selected via `.env`:

```
DPMTF_MACHINE_PROFILE=machine.ai-pc.json
```

In Phase 1, Machine Profile may only be used for read-only healthcheck and System Setup display.

---
