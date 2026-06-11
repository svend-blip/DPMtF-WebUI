# Permission Mode Policy

## Purpose

This governance document defines when Claude Code may proceed automatically in **Auto mode** and when it must stop and ask Svend for explicit approval. Auto mode is a default operating state, not a blanket permission to bypass governance rules or policy boundaries.

## When to Use

- **Every session start**: Perform phase-start git baseline checks per [[15_GIT_POLICY]] before determining mode. Determine whether the current work falls within Auto-mode boundaries.
- **Before any action outside scope**: Stop and ask if the requested work exceeds policy boundaries.
- **After `/clear`**: Reconstruct permission expectations without relying on chat memory.

## Required Inputs

| Input | Description |
|-------|-------------|
| Phase key and title | From `00_PROJECT.md`. |
| Phase mode | Current phase mode (see section below). |
| Scope document | Defined in `02_SCOPE.md`. |
| Allowed / forbidden files | Defined in `03_FILE_ACCESS_POLICY.md` or explicit prompt instructions. |
| Allowed / forbidden commands | Explicit prompt instructions. |
| Stop-before-commit flag | Whether the phase requires stopping before any git commit or push. |

## Required Outputs

- Permission policy result for each action: **allowed** / **blocked** / **ask_human**.
- Actual Claude Code mode assumed: **Auto mode**.
- If blocked: specific reason and what must be clarified with Svend.

---

## Auto Mode

Claude Code normally runs in **Auto mode**. This means Claude may proceed with actions without per-action confirmation, provided all of the following are explicit:

1. `phase_mode` — current phase mode is defined.
2. `allowed_files` — which files may be read, written, or deleted.
3. `forbidden_files` — which files must not be touched.
4. `allowed_commands` — which shell commands may be run.
5. `forbidden_commands` — which commands must not be run.
6. `stop_before_commit` — whether Claude must stop before committing or pushing.

**Auto mode is not permission to bypass governance.** All phase-specific rules, coding standards, validation checks, and scope boundaries still apply. If any of the six items above is missing or unclear, Claude must stop and ask Svend.

## Phase Modes

The following phase modes are recognized:

| Mode | Description | Auto-mode allowed |
|------|-------------|-------------------|
| `prompt_generation` | Generating prompts for a future implementation phase. | Yes, within scope. |
| `implementation` | Implementing code changes as defined by the prompt. | Yes, if all six policy items are explicit. |
| `validation` | Running validation checks on produced changes. | Yes, within scope. |
| `commit_release` | Committing and/or pushing changes to git. | **No** — always requires human approval. |
| `service_control` | Starting, stopping, or restarting services (Flask, GPU, Ollama). | **No** — always requires human approval. |

## Stop-and-Ask Rules

Claude must stop and ask Svend before performing any of the following:

1. **Commit or push** — any `git commit`, `git push`, or equivalent operation.
2. **Destructive commands** — `rm -rf`, mass deletion, truncation of databases, dropping tables.
3. **Service control** — starting, stopping, or restarting Flask, GPU services, Ollama, or any daemon process.
4. **Credential or auth changes** — modifying API keys, passwords, tokens, OAuth configurations, or authentication logic.
5. **Broad filesystem operations** — recursive search-and-replace outside scope, mass renaming, bulk file moves.
6. **Unclear scope** — when the requested work is ambiguous, exceeds `02_SCOPE.md`, or conflicts with governance rules.
7. **Exceeding policy boundaries** — any action not explicitly covered by the six Auto-mode items above.

## Permission Policy Results

For every substantive action, Claude must determine and (if asked to report) document one of:

| Result | Meaning |
|--------|---------|
| **allowed** | All six Auto-mode items are explicit; action is within scope and phase mode permits it. |
| **blocked** | Action violates a governance rule, forbidden file, or stop-and-ask rule. Must not proceed. |
| **ask_human** | Ambiguous situation, unclear scope, or missing one of the six Auto-mode items. Must ask Svend. |

## Reporting

When producing an implementation report (`12_IMPLEMENTATION_REPORT.md`) or validation report (`13_VALIDATION_REPORT.md`), include:

- Permission policy result: allowed / blocked / ask_human.
- Actual Claude Code mode assumed: Auto mode.
- Whether Claude stopped before commit (yes / no — should always be yes unless explicitly told otherwise).

---
