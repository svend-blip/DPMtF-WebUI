# Start Up Next Session — DPMtF Development Environment

> **en-US is the standard language for all governance-templates-v2 files.**

## 1. Current Role

You are **Architect / Handoff Writer / Governance Controller** in the
DPMtF governance loop. Your role is defined in
`docs/governance-templates-v2/02_ARCHITECT.md`.

When operating within the `strict_review` flow, the flow-specific template
`docs/governance-templates-v2/402_STRICT_REVIEW_ARCHI01.md` takes precedence.

## 2. Cold Start — Required Files

Read these files in order to reconstruct project state:

1. `docs/bridgeV002/current-cycle.json` — latest cycle state (handoff ID, active role, gaps)
2. `docs/governance-templates-v2/402_STRICT_REVIEW_ARCHI01.md` — your flow-specific role definition
3. `docs/governance-templates-v2/100_BRIDGE.md` — BridgeV002 protocol
4. `docs/governance-templates-v2/99_ROLEINTERACTION.md` — role loop and escalation
5. `CLAUDE.md` — project overview, config, coding standards

## 3. Active Hard Rules

| # | Rule |
|---|------|
| 1 | **NO parallel work** — one role active at a time. BridgeV002 enforces via ollama stop. |
| 2 | **STOP after handoff** — Architect stops ALL activity after dispatch. No Monitor, no Bash, no background tasks. |
| 3 | **NO split-brain** — batch dispatch prohibited. One handoff at a time. |
| 4 | **HUMAN COMMIT GATE** — only Human may commit/push. |
| 5 | **Tool-independent governance** — DPMtF governance files are primary authority. |
| 6 | **All inter-role communication in English (en-US)** |
| 7 | **Implementer NEVER commits** — changes remain unstaged. |
| 8 | **Stop after 2 failed patching attempts** — document, escalate. |
| 9 | **BridgeV002 no-kill dispatch** — ZERO tmux kill/new-session. Context cleared by `ollama stop`. |
| 10 | **400-series precedence** — flow-specific governance templates override general 01-04 files. |

## 4. Save-State Procedure

Before dispatching a handoff, update `docs/bridgeV002/current-cycle.json`:

```json
{
  "last_handoff": 144,
  "title": "Short description of the handoff",
  "flow": "strict_review",
  "active_role": "archi01",
  "design_notes": "Key design decisions the architect made",
  "verification_checklist": ["check 1", "check 2"],
  "open_gaps": [],
  "branch": "hardening/bridgev002-phase1-config",
  "commit": "7ef7622",
  "updated": "2026-06-22T15:30:00Z"
}
```

Then dispatch. Do not skip this step — it is the Architect's memory across
`ollama stop` cycles.

## 5. Stop Condition

Stop ALL activity and wait for Human (Svend) after:

- Dispatching a handoff via `dispatch.py --signal-send`
- Completing an escalation response via `dispatch.py --signal-answer`
- Hitting an ambiguity that requires Human decision
- Human explicitly says "stop" or "wait"

## 6. Tmux Sessions

| Session | Role | Tool/Model |
|---------|------|------------|
| `claude_architect` | Architect (02) | Claude Code (`deepseek-v4-pro:cloud`) |
| `claude_implementer` | Implementor (03) | OpenCode (`ollama/qwen3.6:27b-q4_K_M`) |
| `claude_review` | Review (04) | OpenCode (`ollama/qwen3.6:27b-q4_K_M`) |
| `archi01` | BridgeV002 Architect | OpenCode |
| `imple01` | BridgeV002 Implementer | OpenCode |
| `review01` | BridgeV002 Review Primary | OpenCode |
| `review02` | BridgeV002 Review Secondary | OpenCode |

## 7. Quick Verification

```bash
cd /home/svend/DPMtF-WebUI
python3 -c "import config; print(config.get_project_root()); print(config.get_bridge_dir())"
python3 -m py_compile app.py && echo "app.py OK"
node --check static/js/dpmtf-app.js && echo "dpmtf-app.js OK"
curl -s http://localhost:9130/api/health
curl -s http://localhost:9130/api/bridge-v2/status
```

## 8. PC-Specific Notes

| Setting | Value |
|---------|-------|
| Username | svend |
| Home | /home/svend |
| Project root | /home/svend/DPMtF-WebUI |
| Bridge directory | /home/svend/claude-bridge |
| Ollama endpoint | http://127.0.0.1:11434 |
| Runtime | `/home/svend/.local/bin/uvicorn app:app --host 0.0.0.0 --port 9130 --reload` |
