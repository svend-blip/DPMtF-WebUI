# 15 — GIT POLICY

> **en-US is the standard language for all governance-templates-v2 files.**
> All commit messages MUST be in English (en-US).

## Purpose

Defines git conventions, branching strategy, commit rules, and the
Human-gated push policy. Local git is the source of truth; remote push
is an optional sync operation controlled exclusively by the Human.

## When to Use

- **Human:** Authorize commits and pushes.
- **Review:** Prepare staged changes and commit messages for Human approval.
- **Implementor:** Know that commit is forbidden — all changes remain unstaged.
- **After `/clear`:** Reconstruct git conventions and sync status.

---

## Core Principle

**Local git is the source of truth.** Remote push is an optional synchronization
step. All work is valid and preserved via local commits regardless of network
connectivity. Only the Human may commit or push. One recorded
exception: in a two-flow family (PLOOP / ELOOP), the planning
supervisor acting under a recorded mandate (`bridge_flows.commit_cadence`,
`SUPERVISOR_PLANNING.md` §Commit and Push Cadence) commits and pushes the
target repository's baseline between Runs (or per approved handoff);
chain roles never commit.

## Branch Strategy

- `master` is the default and primary branch.
- Use **worktrees** for experimental changes or parallel phase work.
- Do not push directly to `master` without Human approval.
- Worktree branches are cleaned up after merging or abandoned if experimental.

## Commit Conventions

1. **One logical change per commit** — do not mix unrelated fixes.
2. **Commit messages describe what changed and why** — include phase key:
   `[3A] Add panel subgroup expand/collapse`.
3. **No Co-Authored-By trailers** — commit messages describe the change, not the tool.
4. **Do not commit hidden files or generated artifacts** (`__pycache__/`, `.env`, secrets).
5. **Stage related changes together** — use `git add` selectively, not `git add -A`.
6. **All commit messages MUST be in English (en-US).**

## Phase-Start Git Baseline Checks

Every phase MUST begin with actual git baseline checks:

1. `git status --short` — check for uncommitted or unstaged changes.
2. `git log --oneline -8` — review recent commit history.
3. `git branch --show-current` — confirm active branch.
4. `git remote -v` — verify remote configuration.

### Baseline Rules

- **Use actual HEAD as the latest committed baseline.**
- **Do not assume commit/push state from chat history or old NEXT_CONTEXT.**
- **If git state conflicts with NEXT_CONTEXT, escalate to Human.**
- **Record the phase-start baseline** in [[28_IMPLEMENTATION_REPORT]].

## Before Committing (Review's Checklist)

1. Run syntax checks per [[13_VALIDATION]]:
   - `python3 -m py_compile app.py` (if Python changed).
   - `node --check static/js/*.js` (if JavaScript changed).
   - `bash -n <file>` (if shell scripts changed).
2. Review `git diff --stat` for scope alignment with [[11_SCOPE]].
3. Verify the application still loads: check `/api/health`.
4. Ensure no secrets, credentials, or API keys are in the diff.
5. Confirm file access policy compliance per [[16_FILE_ACCESS]].

## Commit and Push Authorization

| Scenario | Action |
|----------|--------|
| Human authorizes commit | `git add <files>` + `git commit -m "..."` executed by Human or by Review after explicit Human approval. |
| Human authorizes push | `git push origin master` executed by Human or by Review after explicit Human approval. |
| Offline + checks pass | Commit locally only. Mark push as pending. See [[19_OFFLINE_MODE]]. |
| Checks fail | Do not commit. Return to Implementor. |
| Experimental worktree | Do not push until merged, tested, and verified on master. |

## Sync Recovery (After Offline Period)

1. Check for unpushed commits: `git log origin/master..master --oneline`.
2. Review unpushed commit messages for scope alignment.
3. If Human approves: `git push origin master`.
4. Update [[27_NEXT_CONTEXT]] to reflect sync completion.

## Forbidden Git Operations

- Do NOT amend published commits without Human approval.
- Do NOT rebase shared history.
- Do NOT force-push to `master`.
- Do NOT commit files from forbidden paths per [[16_FILE_ACCESS]].

## Role-Specific Git Permissions

| Role | Stage | Commit | Push |
|------|-------|--------|------|
| **Human** | Yes | Yes (authority) | Yes (authority) |
| **Architect** | No | No | No |
| **Implementor** | No | No | No |
| **Review** | Yes (prepare) | Only with Human approval | Only with Human approval |
| **Planning Supervisor (mandated)** | Yes (in-fence, verdict-approved) | Yes, per cadence | Yes, per cadence, never force |

---
