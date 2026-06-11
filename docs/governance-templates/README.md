# Governance Templates — Index

This directory contains the governance documents that control the DPMtF WebUI role-based prompt loop. These files are the authoritative source of truth for process, roles, scope, architecture, validation, and operational rules. They are read during role handoffs, especially after `/clear` when chat memory is unavailable.

## Template Overview

| File | Name | Purpose |
|------|------|---------|
| [`00_PROJECT.md`](00_PROJECT.md) | Project Overview | Target project identity, ownership, status, and related projects. |
| [`01_ROLES.md`](01_ROLES.md) | Roles | Role definitions, role flow (Analyst → Architect → Engineer → Implementer → Validator → Human Approval Gate → Release Operator → Handoff Writer), and handoff rules. |
| [`02_SCOPE.md`](02_SCOPE.md) | Scope | What is in/out of scope for the current phase, constraints, success criteria, and scope change process. |
| [`03_FILE_ACCESS_POLICY.md`](03_FILE_ACCESS_POLICY.md) | File Access Policy | Which files each role may read, write, or delete; forbidden paths; local git rules. |
| [`04_ARCHITECTURE.md`](04_ARCHITECTURE.md) | Architecture | High-level architecture, components, data flow, directory structure, and the UI Text Slot / i18n four-layer architecture (slots → bindings → labels → translations). |
| [`05_CODING_STANDARD.md`](05_CODING_STANDARD.md) | Coding Standard | Coding rules for Python, JavaScript, CSS, Shell, and Markdown; prohibited patterns learned from project history. |
| [`06_VALIDATION.md`](06_VALIDATION.md) | Validation | Pre-commit checks, functional validation, regression checks, prohibited changes, and visual change rules. |
| [`07_RESTART.md`](07_RESTART.md) | Restart / Runbook | How to restart the application, recover from failures, `/clear` rules, and reconstruction checklist. |
| [`08_TESTPLAN.md`](08_TESTPLAN.md) | Test Plan | Test cases, manual verification steps, automated commands, and pass/fail criteria for the current phase. |
| [`09_DECISIONS.md`](09_DECISIONS.md) | Decision Log | Append-only record of all significant project decisions with context and rationale. |
| [`10_CHANGELOG.md`](10_CHANGELOG.md) | Changelog | Append-only history of all notable changes organized by date and phase. |
| [`11_NEXT_CONTEXT.md`](11_NEXT_CONTEXT.md) | Next Context / Handoff | Session handoff artifact updated before every `/clear`; reconstruction rules for post-`/clear` sessions. |
| [`12_IMPLEMENTATION_REPORT.md`](12_IMPLEMENTATION_REPORT.md) | Implementation Report | Template for documenting what was implemented in a prompt-run session. |
| [`13_VALIDATION_REPORT.md`](13_VALIDATION_REPORT.md) | Validation Report | Template for recording validation results and verdict (pass / fail). |
| [`14_OFFLINE_MODE.md`](14_OFFLINE_MODE.md) | Offline Mode | How the project operates without internet; local git as source of truth; offline workflow. |
| [`15_GIT_POLICY.md`](15_GIT_POLICY.md) | Git Policy | Branch strategy, commit conventions, push policy, temporary hiding for migration and scoped deletion rules. |
| [`16_DATABASE_RUNTIME_STATE.md`](16_DATABASE_RUNTIME_STATE.md) | Database Runtime State | What lives in the database vs governance files; UI text slots, bindings, labels, and translations as separate registry layers; schema change policy. |
| [`17_PERMISSION_MODE_POLICY.md`](17_PERMISSION_MODE_POLICY.md) | Permission Mode Policy | When Claude Code may run in Auto mode, when it must stop and ask Svend, phase modes, and stop-and-ask rules. |

## How to Use These Templates

### Project Initializer (script)

Templates are copied into a target project as `<target>/docs/dpmtf/` using the
governance initializer script:

```bash
python3 scripts/initialize_target_project_governance.py <target-path> [--dry-run] [--overwrite]
```

This ensures every target project starts with the same governance baseline.
See [`docs/project-initializer.md`](../project-initializer.md) for full usage details, path validation rules, and backup behavior.

### Day-to-day

1. **Before a new phase or target project**: Run the initializer script above, then fill in placeholder sections (`[...]`).
2. **During a session**: Each role reads the relevant governance documents before acting (see `01_ROLES.md` for handoff rules).
3. **After `/clear`**: Read in order: `11_NEXT_CONTEXT.md` → `00_PROJECT.md` → `01_ROLES.md` → `02_SCOPE.md`.
4. **Between phases**: Update scope, reset reports, and update the decision log.

## Cross-References

Governance documents reference each other using `[[filename]]` notation:

- `[[06_VALIDATION]]` references the validation rules in `06_VALIDATION.md`.
- `[[14_OFFLINE_MODE]]` references offline operation rules in `14_OFFLINE_MODE.md`.
- `[[03_FILE_ACCESS_POLICY]]` references file access rules in `03_FILE_ACCESS_POLICY.md`.

## Prompt-Run Templates

Related templates for individual prompt-run sessions are located in [`docs/prompt-runs/templates/`](../prompt-runs/templates/):

- `prompt_template.md` — Reusable implementation prompt template.
- `review_prompt_template.md` — Reusable review prompt template.
- `implementation_report_template.md` — Report template per prompt-run.
- `review_report_template.md` — Review report template per prompt-run.
- `metadata_template.json` — Structured metadata per prompt-run.

---
