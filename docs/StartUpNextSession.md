# Start Up Next Session — DPMtF Development Environment

> **en-US is the standard language for all governance-templates-v2 files.**

## 1. Current Role

You are **Architect / Handoff Writer / Governance Controller** in the
DPMtF governance loop. Your role is defined in
`docs/governance-templates-v2/02_ARCHITECT.md`.

When operating within the `strict_review` flow, the flow-specific template
`docs/governance-templates-v2/402_STRICT_REVIEW_ARCHI01.md` takes precedence.

When operating within the `cloud_llm` flow, the flow-specific template
`docs/governance-templates-v2/412_CLOUD_LLM_ARCHI01CLOUD.md` takes precedence.

## 2. Cold Start — Required Files

Read these files in order to reconstruct project state for `strict_review` flow:

1. `docs/bridgeV002/current-cycle-strict-review.json` — latest cycle state (handoff ID, active role, gaps)
2. `docs/governance-templates-v2/402_STRICT_REVIEW_ARCHI01.md` — your flow-specific role definition
3. `docs/governance-templates-v2/100_BRIDGE.md` — BridgeV002 protocol
4. `docs/governance-templates-v2/99_ROLEINTERACTION.md` — role loop and escalation
5. `CLAUDE.md` — project overview, config, coding standards

Read these files in order to reconstruct project state for `cloud_llm` flow:

1. `docs/bridgeV002/current-cycle-cloud-llm.json` — latest cycle state (handoff ID, active role, gaps)
2. `docs/governance-templates-v2/412_CLOUD_LLM_ARCHI01CLOUD.md` — your flow-specific role definition
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

Before dispatching a handoff, update `docs/bridgeV002/current-cycle-strict-review.json` for `strict_review` flow:

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
Before dispatching a handoff, update `docs/bridgeV002/current-cycle-cloud-llm.json` for `cloud_llm` flow:

```json
{
  "last_handoff": 144,
  "title": "Short description of the handoff",
  "flow": "cloud_llm",
  "active_role": "archi01cloud",
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

Stop ALL activity and wait for Human after:

- Dispatching a handoff via `dispatch.py --signal-send`
- Completing an escalation response via `dispatch.py --signal-answer`
- Hitting an ambiguity that requires Human decision
- Human explicitly says "stop" or "wait"

## 6. Tmux Sessions

Only these 4 sessions matter for the strict_review flow. Models and tools are
configured in the database (`bridge_roles.start_cmd`) — not hardcoded here.

| Session | Role | Governance |
|---------|------|------------|
| `archi01` | Architect | 402_STRICT_REVIEW_ARCHI01.md |
| `imple01` | Implementer | 403_STRICT_REVIEW_IMPLE01.md |
| `review01` | Technical Review | 404_STRICT_REVIEW_REVIEW01.md |
| `review02` | Governance Review | 405_STRICT_REVIEW_REVIEW02.md |

Start/stop/attach via BridgeV002 UI buttons.
View all 4: `tmux attach -t flow-strict_review` (after clicking Attach tmux).


Only these 4 sessions matter for the cloud_llm flow. Models and tools are
configured in the database (`bridge_roles.start_cmd`) — not hardcoded here.

| Session | Role | Governance |
|---------|------|------------|
| `archi01cloud` | Architect | 412_CLOUD_LLM_ARCHI01CLOUD.md |
| `imple01cloud` | Implementer | 413_CLOUD_LLM_IMPLE01CLOUD.md |
| `review01cloud` | Technical Review | 414_CLOUD_LLM_REVIEW01CLOUD.md |
| `review02cloud` | Governance Review | 415_CLOUD_LLM_REVIEW02CLOUD.md |

Start/stop/attach via BridgeV002 UI buttons.
View all 4: `tmux attach -t flow_cloud_llm` (after clicking Attach tmux).


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
| Bridge deliverable_dir | **BridgeV002 uses database-driven `deliverable_dir`** from `bridge_flow_steps.deliverable_dir` — *not* legacy `/home/svend/claude-bridge`. Current values: `/home/svend/flows/strict_review/{handoffs,results,reviews,verdicts}` |
| Bridge deliverable_dir | **BridgeV002 uses database-driven `deliverable_dir`** from `bridge_flow_steps.deliverable_dir` — *not* legacy `/home/svend/claude-bridge`. Current values: `/home/svend/flows/cloud_llm/{handoffs,results,reviews,verdicts}` |
| Ollama endpoint | http://127.0.0.1:11434 |
| Runtime | `/home/svend/.local/bin/uvicorn app:app --host 0.0.0.0 --port 9130 --reload` |
