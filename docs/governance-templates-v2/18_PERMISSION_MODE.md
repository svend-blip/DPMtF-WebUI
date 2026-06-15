# 18 — PERMISSION MODE

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines when roles may proceed without per-action Human confirmation and when
they MUST stop and ask. This replaces the legacy "Permission Mode Policy"
(17_PERMISSION_MODE_POLICY.md) from governance-templates v1.

## When to Use

- **All roles:** Determine whether an action requires Human approval.
- **Architect:** Know what constraints to include in prompts.
- **Review:** Know when to escalate to Human.
- **After `/clear`:** Reconstruct permission expectations.

---

## Phase Modes

| Mode | Description | Auto-Execute Allowed |
|------|-------------|---------------------|
| `design` | Architect analyzes scope and designs technical approach. | Yes, within scope. |
| `implementation` | Implementor executes prompts and produces code changes. | Yes, within handoff scope. |
| `validation` | Review validates implementation results. | Yes, within governance rules. |
| `commit_release` | Staging, committing, or pushing changes to git. | **No** — Human approval required. |
| `bridge_dispatch` | Sending prompts via bridge.py. | Yes, within governance rules. |

## Stop-and-Ask Rules (All Roles)

Every role MUST stop and ask the Human before:

1. **Commit or push** — any `git commit`, `git push`, or equivalent.
2. **Destructive commands** — `rm -rf`, mass deletion, database truncation, dropping tables.
3. **Service control** — starting, stopping, or restarting services (Flask, Ollama, GPU).
4. **Credential or auth changes** — modifying API keys, passwords, tokens, OAuth config.
5. **Broad filesystem operations** — recursive search-and-replace outside scope, mass renaming.
6. **Unclear scope** — when requested work is ambiguous or exceeds [[11_SCOPE]].
7. **Exceeding policy boundaries** — any action not explicitly covered by governance rules.

## Auto-Execute Conditions

A role may proceed without per-action Human confirmation when ALL of the
following are explicit:

1. **Role is defined** — the role's governance file (01-04) is loaded.
2. **Phase mode is defined** — from the table above.
3. **Scope is explicit** — [[11_SCOPE]] defines what is allowed.
4. **Files are explicit** — [[16_FILE_ACCESS]] defines allowed/forbidden files.
5. **Commands are explicit** — the handoff `<task>` or governance defines allowed commands.
6. **Stop-before-commit is active** — all roles know commit requires Human approval.

## Role-Specific Auto-Execute Boundaries

| Role | Auto-Execute Scope |
|------|-------------------|
| **Human** | Full control — all actions require self-authorization. |
| **Architect** | Read governance + codebase. Write governance docs + bridge handoff files. Bridge dispatch (`bridge.py send`, `bridge.py answer-review`). |
| **Implementor** | Read scoped files + governance references. Write files within handoff `<scope>`. Bridge signal (`bridge.py complete`). |
| **Review** | Read all changed files + governance docs. Write governance docs + bridge handoff files. Bridge dispatch (`bridge.py send`, `bridge.py ask-architect`). Git staging (NOT commit). |

## Escalation for Permission Boundaries

If a role encounters an action that exceeds its auto-execute boundaries:

1. **Architect/Review:** Escalate to Human with specific description of what is needed and why.
2. **Implementor:** Document in result file and signal completion — do NOT guess or exceed scope.
3. **Human:** Decide and authorize or deny.

---
