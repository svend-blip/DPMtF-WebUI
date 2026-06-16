# 16 — FILE ACCESS POLICY

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines which files each role may read, write, or delete. Prevents unauthorized
modifications and ensures all changes are traceable and reversible.

## When to Use

- **Implementor:** Read before making any code changes.
- **Review:** Verify that no forbidden paths were touched.
- **Architect:** Define file scope in implementation prompts.
- **After `/clear`:** Reconstruct access boundaries.

---

## Role-Specific Access

| Role | Read | Write | Delete |
|------|------|-------|--------|
| **Human** | All files in all projects. | Governance documents, scope, decisions. | Only with explicit intent. |
| **Architect** | All governance docs + codebase reference. | Governance docs, bridge handoff files. | None. |
| **Implementor** | Scoped files per handoff `<scope>` + governance references. | Files within defined `<scope>` only. | Only when explicitly scoped and specified in `<task>`. |
| **Review** | All changed files + diff output + governance docs. | Governance docs, bridge handoff files, validation reports, NEXT_CONTEXT. | None. |

## Read-Only (Append-Only) Files

These files MUST NOT be modified — only new entries may be added at the bottom:

- [[25_DECISIONS]] — decision log.
- [[26_CHANGELOG]] — change history.

## Restricted Write

These files require Human approval before modification:

- `app.py` — backend entry point.
- `config.py` — configuration.
- Database migration scripts — schema changes.
- Role definition files (01-04) — governance-critical.

## Free Write (Within Scope)

Files safe to modify within the current scope:

- Template files in `templates/`.
- Static assets in `static/` (JS, CSS, images).
- Documentation in `docs/`.

## Forbidden Paths (All Roles)

- `.git/` internals — managed by git commands only.
- `__pycache__/`, `.pytest_cache/` — generated artifacts.
- `.env` files, credentials, API keys.
- System configuration outside the project root.
- Other projects' directories (ENO, v3) unless explicitly authorized.

## Generated Artifacts, Logs, Backups

| Category | Policy |
|----------|--------|
| **Generated artifacts** (`__pycache__`, build outputs) | Do not commit. Do not edit manually. |
| **Logs** | Write-only for diagnostics. Never modify existing entries. |
| **Backups** (`*.bak`, `*_backup.*`) | Created automatically before restricted-write operations. Deleted after successful verification. |

## Local Git Rules

- All changes must be trackable via `git diff`.
- If offline, commit locally and mark push as pending per [[19_OFFLINE_MODE]].
- Do not amend or rebase commits without Human approval per [[15_GIT_POLICY]].

## Project Root Resolution

All project paths are resolved via `config.py`:

| Path | Getter | Example Value |
|------|--------|---------------|
| Project root | `config.get_project_root()` | `/home/svend/DPMtF-WebUI` |
| Bridge directory | `config.get_bridge_dir()` | `/home/svend/claude-bridge` |
| Governance docs | `config.get_governance_dir_abs()` | `/home/svend/DPMtF-WebUI/docs/governance-templates-v2` |

When writing handoff prompts, validation scripts, or scope definitions,
use config getters instead of hardcoding `/home/svend/...`.

**Example (correct — in a handoff prompt):**
```
<project>{config.get_project_root()}</project>
<governance>
- {config.get_project_root()}/{config.get_governance_dir()}/12_CODING_STANDARD.md
</governance>
```

**Example (WRONG — auto-fail in review):**
```
<project>/home/svend/DPMtF-WebUI</project>
<governance>
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md
</governance>
```

---
