# 27 — NEXT CONTEXT / HANDOFF

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

The primary handoff artifact between sessions. Updated by the Review role
before every `/clear`. After `/clear`, the new session reads this file first
to reconstruct project state, current phase progress, and what needs to
happen next.

This file, combined with the governance documents in `docs/governance-templates-v2/`,
is the authoritative source of context — not chat memory.

## When to Use

- **Review:** Update before every `/clear` with current session state.
- **All roles:** Read first after `/clear` to reconstruct context.
- **Architect:** Read to understand remaining work.

---

## `/clear` Reconstruction Rules

1. **No-kill mode:** BridgeV002 uses `ollama stop` to clear context between
   role transitions — not `/clear`. Sessions are persistent.
2. **Governance documents are the source of truth.** Do not rely on chat history.
3. **Reconstruction order after restart:**
   - Read your flow-specific governance file (402-405 for strict_review).
   - Read [[10_PROJECT]] — confirm project identity.
   - Read [[11_SCOPE]] — confirm phase boundaries.
   - Check trace log and current.md symlinks for latest state.
   - Read previous role's output (handoff file, result file, or escalation response).
4. **If information is missing from governance documents, escalate to Human.**

---

## Phase-Start Git Baseline

| Check | Result |
|-------|--------|
| Branch | `{branch}` |
| Latest commit (HEAD) | `{hash}` ({description}) |
| Uncommitted changes | {list or "none"} |
| Remote | `origin → {url}` |

**Rule:** Always verify with live git commands. Do not assume commit/push state
from previous NEXT_CONTEXT. If git state conflicts with this file, escalate to Human.
See [[15_GIT_POLICY]].

## Current State

- **Project:** {PROJECT_NAME} — {SHORT_DESCRIPTION}
- **Current phase:** {PHASE_KEY} — {PHASE_TITLE}
- **Latest committed baseline:** {HEAD_HASH} ({description})
- **Active role:** {Human | Architect | Implementor | Review}

### Phase Progress

| Phase | Status | Description |
|-------|--------|-------------|
| {PHASE_KEY} | {completed | in_progress | pending} | {DESCRIPTION} |

## Completed Since Last Handoff

- {Bullet list of completed work since the last NEXT_CONTEXT update.}

## Remaining Work

- {Bullet list of work remaining in the current phase.}
- {Open questions that need resolution.}

## Important Notes for Next Session

- {Critical information the next session needs to know.}
- {Current bridge state, tmux session status.}
- {Cross-project alignment status.}
- {Pending pushes if offline.}

## Open Questions

- {Unresolved items that need Human or Architect attention.}

## Files Changed

| File | What Changed |
|------|-------------|
| {path} | {description} |

---
