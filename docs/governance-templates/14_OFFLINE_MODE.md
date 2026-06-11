# Offline Mode

## Purpose

This governance document defines how the project operates in offline mode — without internet access. DPMtF WebUI is designed to run fully locally. Local git is the source of truth; GitHub push is an optional sync operation, not a requirement for progress. This document ensures that offline operation never blocks local work.

## When to Use

- **Release Operator**: Follow these rules when committing and syncing changes.
- **Any role in offline environments**: Understand what can and cannot be done without internet.
- **After `/clear`**: Read to reconstruct operational constraints for the current environment.

## Required Inputs

| Input | Description |
|-------|-------------|
| Network status | Online or offline. Check with `ping -c 1 8.8.8.8` or equivalent. |
| Git state | Local commit status and any pending pushes. |

## Required Outputs

- Changes committed locally regardless of network status.
- Push status tracked (pushed, pending, or not applicable).
- If offline: clear marker that push is pending for later sync.

---

## Core Principle

**Local git is the source of truth.** GitHub push is an optional synchronization step. Offline operation must never block local progress.

## Requirements for Offline Operation

- Local Python runtime with FastAPI and Uvicorn installed.
- SQLite database file present at `databases/dpmtf.db`.
- Local LLM (e.g., Ollama) for agent-driven prompt execution (optional, role-local).
- Local git repository for version control — the authoritative record of all changes.

## What Does NOT Require Internet

- Application startup and API endpoints.
- Database reads and writes.
- Governance document reads and writes.
- Prompt generation and execution with local models.
- Git commit operations.
- All role-based prompt loop steps (Analyst through Handoff Writer).

## What MAY Require Internet

- Initial dependency installation (`pip install`).
- Model downloads (one-time setup for local LLM).
- Upstream package updates.
- GitHub push (optional sync, not required for progress).

## Offline Git Workflow

1. **Develop locally** — make changes as normal within scope.
2. **Commit locally** — `git add` and `git commit` regardless of network status.
3. **Check connectivity** before attempting push:
 ```bash
 ping -c 1 8.8.8.8 >/dev/null 2>&1 && echo "online" || echo "offline"
 ```
4. **If online**: push to GitHub as normal — `git push origin master`.
5. **If offline**: skip push, note that changes are committed locally with pending push status. Document in `NEXT_CONTEXT.md`:
 ```markdown
 ## Git Sync Status
 - Local commits: [N] unpushed commits.
 - Push status: PENDING — offline. Will sync when online.
 ```
6. **When back online**: review pending commits, then push: `git push origin master`.

## No Internet-Required Step Should Block Local Work

Unless a step explicitly requires internet (e.g., downloading a new model for the first time), no role or phase should be blocked by offline status. If a step requires internet and the environment is offline:

1. Document the blocking step in `NEXT_CONTEXT.md`.
2. Complete all other work that does NOT require internet.
3. Mark the blocking step as "deferred until online" with a clear description of what needs to happen.

## Offline Verification

1. Disconnect network (or verify offline status).
2. Start the application: `python3 app.py`.
3. Verify `/api/health` responds with healthy status.
4. Verify all UI panels load without errors.
5. Verify governance documents are readable from `docs/governance-templates/`.

---
