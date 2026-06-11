# File Access Policy

## Purpose

This governance document defines which files each role in the prompt loop may read, write, or delete. It prevents unauthorized modifications to critical project files and ensures that all changes are traceable and reversible.

## When to Use

- **Implementer step**: Read before making any code changes to know what can be modified.
- **Validator step**: Verify that no forbidden paths were touched by the Implementer.
- **After `/clear`**: Reconstruct access boundaries without relying on chat memory.

## Required Inputs

| Input | Description |
|-------|-------------|
| Current role | Determines which access rules apply. |
| Target files | The files proposed for modification. |
| Phase scope | Defined in `02_SCOPE.md`. |

## Required Outputs

- All file operations comply with the policy defined here.
- Any violations flagged to Human Approval Gate.

---

## Role-Specific Access

| Role | Read | Write | Delete |
|------|------|-------|--------|
| **Analyst** | All governance docs, scope, architecture. Governance docs only. None. |
| **Solution Architect** | Governance docs + codebase reference read. Governance docs (design notes). None. |
| **Prompt Engineer** | Governance docs + scoped files from architect design. Generated prompts only (`docs/prompt-runs/`). None. |
| **Implementer** | Scoped files per phase. Free-write zone + restricted-write files with approval. Delete only when scoped and validated; temporary hiding allowed for migration (see [[05_CODING_STANDARD]]). |
| **Validator** | All changed files + diff output. Validation reports only. None. |
| **Human Approval Gate** | Diff, validation report, screenshots. Decision log (`DECISIONS.md`). None. |
| **Release Operator** | All governance docs + changed files. Changelog, commit messages. Deletes committed only after validation and approval (see [[06_VALIDATION]]). |
| **Handoff Writer** | All governance docs. `NEXT_CONTEXT.md`, implementation report. None. |

---

## Read-Only Files

These files must not be modified without explicit Human Approval Gate approval:

- `16_DATABASE_RUNTIME_STATE.md` — database schema reference for the target project.
- `09_DECISIONS.md` — append-only decision log. Only new entries may be added at the bottom.
- `10_CHANGELOG.md` — append-only change history. Only new entries may be added at the bottom.

## Restricted Write

These files require human approval before modification:

- `app.py` — backend entry point; changes must pass validation first.
- Database migration scripts — schema changes require explicit approval per phase scope.
- `01_ROLES.md` — role definitions are governance-critical; changes affect the entire pipeline.

## Free Write

Files safe to modify within the current scope:

- Template files in `templates/`.
- Static assets in `static/` (JS, CSS, images).
- Documentation in `docs/`.
- Generated artifacts in `docs/prompt-runs/`.

## Forbidden Paths

These paths must not be modified by any role without explicit Human Approval Gate authorization:

- `.git/` internals — managed by git commands only.
- `__pycache__/`, `.pytest_cache/` — generated artifacts; delete and regenerate instead of editing.
- `.env` files, credentials, API keys — never write secrets to governance files or commits.
- System configuration outside the project root.

## Generated Artifacts, Logs, Backups

| Category | Policy |
|----------|--------|
| **Generated artifacts** (`__pycache__`, build outputs) | Do not commit. Do not edit manually. Regenerate if stale. |
| **Logs** (application logs, CI logs) | Write-only for diagnostics. Never modify existing log entries. |
| **Backups** (`*.bak`, `*_backup.*`) | Created automatically before restricted-write operations. Deleted after successful verification. |

## Local Git Rules

- All changes must be trackable via `git diff`.
- If offline, commit locally and mark push as pending. See [[14_OFFLINE_MODE]].
- Do not amend or rebase commits without Human Approval Gate approval.
- Worktrees for experimental changes; do not push worktree branches without merging and testing first.

---
