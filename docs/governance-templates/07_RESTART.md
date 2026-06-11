# Restart / Runbook

## Purpose

This governance document defines how to restart the application, recover from failures, and — critically — how to handle `/clear` transitions in the role-based prompt loop. After `/clear`, all context is lost from the chat window; this document ensures the next session can reconstruct state from governance documents alone.

## When to Use

- **Application restart**: The server crashed or was stopped.
- **After `/clear`**: A new session needs to understand project state, current role, and what to do next.
- **Recovery**: Something went wrong and the application is in an unknown state.

## Required Inputs

| Input | Description |
|-------|-------------|
| Application state | Is it running, crashed, or in an undefined state? |
| Governance documents | `docs/governance-templates/` — the source of truth after `/clear`. |
| `NEXT_CONTEXT.md` | Session handoff notes from the previous role transition. |

## Required Outputs

- Application running and healthy (`/api/health` responds).
- Next session correctly oriented to current phase, role, and remaining work.

---

## `/clear` Rules

### When to Use `/clear`

- Between every role transition in the prompt loop (e.g., after Analyst finishes, before Solution Architect starts).
- Before starting a new phase.
- After completing a validation cycle.

### What Happens After `/clear`

1. Chat memory is cleared — no conversation history is available.
2. **Governance documents are the source of truth**, not chat memory.
3. The next session MUST reconstruct context by reading (in order):
 - `00_PROJECT.md` — project identity.
 - `01_ROLES.md` — role flow and current position.
 - `11_NEXT_CONTEXT.md` — handoff notes from the previous session.
 - `02_SCOPE.md` — what is allowed in this phase.
 - `05_CODING_STANDARD.md` — coding rules.
4. Do NOT assume anything was decided in a previous chat session that isn't recorded in governance documents.

### Reconstruction Checklist

After `/clear`, the new session must:

1. Read `NEXT_CONTEXT.md` to identify the current role and remaining work.
2. Read `00_PROJECT.md` to confirm project identity.
3. Read `02_SCOPE.md` to confirm what is in/out of scope.
4. Read the previous role's output (analysis document, design, generated prompts, or implementation report).
5. Proceed with the next role's work using governance documents as the only authorized reference.

---

## How to Start the Application

```bash
cd /path/to/project
python3 app.py
# or with uvicorn directly:
uvicorn app:app --host 0.0.0.0 --port 9130
```

## How to Verify It Is Running

- Open `http://localhost:9130` in a browser.
- Check `/api/health` returns `{"status": "healthy"}`.
- Verify all panels load without console errors.

## Common Failure Modes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Database not found | Missing `databases/dpmtf.db` | Verify path exists; restore from backup if needed. |
| Port already in use | Previous instance still running | Kill old process (`lsof -i :9130`) or change port. |
| Static files 404 | Wrong working directory | Run from project root where `app.py` lives. |
| Import error | Missing Python dependency | Verify installation: `pip install fastapi uvicorn`. |

## Recovery Steps

1. Check that `databases/dpmtf.db` exists and is readable.
2. Verify Python dependencies: `pip install fastapi uvicorn`.
3. Run syntax checks: `python3 -m py_compile app.py`.
4. Restart the server and check `/api/health`.
5. If still failing, review `NEXT_CONTEXT.md` for recent changes that may have caused the issue.

---
