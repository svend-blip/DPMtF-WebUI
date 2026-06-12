# Git Policy

## Purpose

This governance document defines the git conventions, branching strategy, commit rules, and synchronization policy for AI PC Resource WebUI v3. Local git is the source of truth; GitHub push is an optional sync operation. This document ensures consistent version control across all sessions, especially after `/clear` when the new session needs to understand the repository's state.

## When to Use

- **Release Operator**: Follow these rules for committing and pushing changes.
- **Any role making file changes**: Know when to stage, what to commit, and how to write messages.
- **After `/clear`**: Read to reconstruct git conventions and current sync status.

---

## Repository Details

| Item | Value |
|------|-------|
| **Local path** | `/home/svend/ai-pc-resource-webui-v3` |
| **Remote** | `https://github.com/svend-blip/ai-pc-resource-webui-v3.git` |
| **Default branch** | `master` |
| **Current baseline commit** | Do not store a static baseline here. Use phase-start git baseline checks and actual HEAD. |

## Core Principle

**Local git is the source of truth.** GitHub push is an optional synchronization step. All work is valid and preserved via local commits regardless of network connectivity.

## Branch Strategy

- `master` is the default and primary branch.
- Use **worktrees** for experimental changes or parallel phase work.
- Do not push directly to `master` without local verification (syntax checks, health endpoint test).
- Worktree branches are cleaned up after merging or abandoned if experimental.

## Commit Conventions

1. **One logical change per commit** — do not mix unrelated fixes.
2. **Commit messages describe what changed and why** — include the phase key: `[3C-3] Initialize governance docs`.
3. **Include `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`** when AI-assisted.
4. **Do not commit hidden files or generated artifacts** (`__pycache__/`, `.env`, secrets).
5. **Stage related changes together** — use `git add` selectively, not `git add -A`.

## Phase-Start Git Baseline Checks

Every phase must begin with actual git baseline checks before any work begins. Claude must run these commands at the start of every session:

1. `git status --short` — check for uncommitted or unstaged changes.
2. `git log --oneline -8` — review recent commit history.
3. `git branch --show-current` — confirm active branch.
4. `git remote -v` — verify remote configuration.

### Baseline Rules

- **Use actual HEAD as the latest committed baseline.** The most recent commit in the local repository is the authoritative reference point for all subsequent work in this phase.
- **Do not assume commit/push state from chat history or old NEXT_CONTEXT text.** Previously recorded sync status may be stale; always verify with live git commands.
- **If git state conflicts with NEXT_CONTEXT,** stop and ask Svend before proceeding. Do not silently override governance records.
- **Record the phase-start baseline** in the implementation report (see [[12_IMPLEMENTATION_REPORT]]).

### Manual Git Operations

- Manual `git add`, `git commit`, and `git push` still require explicit human approval per [[17_PERMISSION_MODE_POLICY]]. This section only governs read-only baseline checks.

## Before Committing

1. Run syntax checks per `06_VALIDATION.md`:
 - `python3 -m py_compile app.py` (if Python changed).
 - `node --check static/js/*.js` (if JavaScript changed).
 - `bash -n <file>` (if shell scripts changed).
2. Review `git diff --stat` for scope alignment with `02_SCOPE.md`.
3. Verify the application still loads: check `/api/health`.
4. Ensure no secrets, credentials, or API keys are in the diff.
5. Confirm file access policy compliance (see `03_FILE_ACCESS_POLICY.md`).

## Temporary Hiding and Deletion Policy

### New Projects — Clean Implementation

AI PC Resource WebUI v3 is a clean implementation:

1. Implement cleanly — do not create hidden panels or unused code by default.
2. Build the intended structure from scratch without irrelevant legacy artifacts.
3. No migration from v2 — v2 is reference only, not source material.

### Scoped Deletion (All Projects)

1. Deleting code is allowed when: the phase scope explicitly authorizes it, all references are verified, validation passes, Human Approval Gate approves (if user-visible behavior changes), and the change is documented in `10_CHANGELOG.md`.
2. Do not delete governance documents, decision logs, or changelog entries — these are append-only per their own rules.

## Push Policy

| Scenario | Action |
|----------|--------|
| Online + all checks pass | Commit and push to `origin/master`. |
| Offline + all checks pass | Commit locally. Mark push as pending in `11_NEXT_CONTEXT.md`. |
| Online + checks fail | Do not commit. Return changes to Implementer. |
| Experimental worktree | Do not push until merged, tested, and verified on master. |

## Sync Recovery (After Offline Period)

1. Check for unpushed commits: `git log origin/master..master --oneline`.
2. Review the unpushed commit messages for scope alignment.
3. If satisfied: `git push origin master`.
4. Update `11_NEXT_CONTEXT.md` to reflect sync completion.

## Forbidden Git Operations

- Do not amend published commits without Human Approval Gate approval.
- Do not rebase shared history.
- Do not force-push to `master`.
- Do not commit files from forbidden paths (see `03_FILE_ACCESS_POLICY.md`).

## Phase 3C-3 Rule

**Stop before commit in this phase.** No commit is made during phase 3C-3 governance initialization. All changes remain unstaged and uncommitted until explicitly instructed to commit in a later phase.

---
