# Restart / Runbook

## Purpose

This governance document defines how to restart the AI PC Resource WebUI v3 application, recover from failures, and — critically — how to handle `/clear` transitions in the role-based prompt loop. After `/clear`, all context is lost from the chat window; this document ensures the next session can reconstruct state from governance documents alone.

## When to Use

- **Application restart**: The server crashed or was stopped.
- **After `/clear`**: A new session needs to understand project state, current role, and what to do next.
- **Recovery**: Something went wrong and the application is in an unknown state.

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

1. Read `11_NEXT_CONTEXT.md` to identify the current role and remaining work.
2. Read `00_PROJECT.md` to confirm project identity.
3. Read `02_SCOPE.md` to confirm what is in/out of scope.
4. Read the previous role's output (analysis document, design, generated prompts, or implementation report).
5. Proceed with the next role's work using governance documents as the only authorized reference.

---

## How to Restart AI PC Resource WebUI v3

### Stop Existing Process on Port 9123

```bash
lsof -ti:9123 | xargs -r kill
```

### Start with .venv Uvicorn

```bash
cd /home/svend/ai-pc-resource-webui-v3
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 9123 --log-level info 2>&1 | tee /tmp/ai_pc_resource_webui_v3_9123.log
```

### Verify Root Returns 200

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:9123/
```

Expected output: `200`

### Verify Health Endpoint

```bash
curl -s http://localhost:9123/api/health
```

Expected output: `{"status": "healthy"}` or similar healthy response.

### Suggested Log Path

```
/tmp/ai_pc_resource_webui_v3_9123.log
```

## Common Failure Modes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Port already in use | Previous instance still running on 9123 | Kill old process: `lsof -ti:9123 \| xargs -r kill` |
| ModuleNotFoundError | Missing Python dependency in .venv | Install: `.venv/bin/pip install fastapi uvicorn` |
| Static files 404 | Wrong working directory | Run from project root where `app.py` lives |
| Import error | Missing dependency or broken import in skeleton | Verify with: `python3 -m py_compile app.py` |

## Recovery Steps

1. Verify Python dependencies: `.venv/bin/pip install -r requirements.txt`.
2. Run syntax checks: `python3 -m py_compile app.py`.
3. Restart the server using the commands above.
4. Check `/api/health` returns a healthy response.
5. If still failing, review `11_NEXT_CONTEXT.md` for recent changes that may have caused the issue.

---
