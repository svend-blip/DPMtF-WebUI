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

When operating within the `cloud_pay` flow, the flow-specific template
`docs/governance-templates-v2/422_CLOUD_PAY_ARCHI01PAY.md` takes precedence.

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

Read these files in order to reconstruct project state for `cloud_pay` flow:

1. `docs/bridgeV002/current-cycle-cloud-pay.json` — latest cycle state (handoff ID, active role, gaps)
2. `docs/governance-templates-v2/422_CLOUD_PAY_ARCHI01PAY.md` — your flow-specific role definition
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

Before dispatching a handoff, update `docs/bridgeV002/current-cycle-cloud-pay.json` for `cloud_pay` flow:

```json
{
  "last_handoff": 144,
  "title": "Short description of the handoff",
  "flow": "cloud_pay",
  "active_role": "archi01pay",
  "design_notes": "Key design decisions the architect made",
  "verification_checklist": ["check 1", "check 2"],
  "open_gaps": [],
  "branch": "master",
  "commit": "",
  "updated": "2026-06-25T15:00:00Z"
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


Only these 4 sessions matter for the cloud_pay flow. Models and tools are
configured in the database (`bridge_roles.start_cmd`) — not hardcoded here.

| Session | Role | Governance |
|---------|------|------------|
| `archi01pay` | Architect | 422_CLOUD_PAY_ARCHI01PAY.md |
| `imple01pay` | Implementer | 423_CLOUD_PAY_IMPLE01PAY.md |
| `review01pay` | Technical Review | 424_CLOUD_PAY_REVIEW01PAY.md |
| `review02pay` | Governance Review | 425_CLOUD_PAY_REVIEW02PAY.md |

Start/stop/attach via BridgeV002 UI buttons.
View all 4: `tmux attach -t flow_cloud_pay` (after clicking Attach tmux).


## 7. Trade Cockpit Flow

The `trade_cockpit_simulation_v001` flow is a Human/cronjob-driven daily research-to-simulation chain.
It is NOT an Architect flow — the Human or a cronjob triggers it directly.

### Roles

| Session | Role | Model | Governance |
|---------|------|-------|------------|
| `trend01_trade` | Trend Synthesizer | qwen3.6:35b (Ollama) | 431_TRADE_TREND01.md |
| `market01_trade` | Market Snapshot | deepseek-v4-pro:cloud (Ollama) | 432_TRADE_MARKET01.md |
| `analyst01_trade` | Candidate Analyst | MiniMax-M3 (OpenCode) | 433_TRADE_ANALYST01.md |
| `risk01_trade` | Risk Gate | qwen3.6:35b (Ollama) | 434_TRADE_RISK01.md |
| `review01_trade` | Independent Reviewer | GLM 5.2 (OpenRouter) | 435_TRADE_REVIEW01.md |
| `sim01_trade` | Simulation Executor | qwen3.6:27b (Ollama) | 436_TRADE_SIM01.md |

### Starting a Trade Cycle

```bash
cd /home/svend/DPMtF-WebUI

# 1. Create tmux sessions
for s in trend01_trade market01_trade analyst01_trade risk01_trade review01_trade sim01_trade; do
  tmux new-session -d -s "$s"
done

# 2. Start coding frontends (includes sim01_trade — start_coding.py fixed)
python3 scripts/bridgeV002/start_coding.py trade_cockpit_simulation_v001

# 3. Create trigger file (ID from database counter)
echo '<role>You are trend01_trade in the trade_cockpit_simulation_v001 flow.</role>
<task>Execute your role according to the governance file. Produce JSON output to the inbox.</task>
<constraint>SIMULATION_ONLY = TRUE. Follow GATES.md. Valid JSON only.</constraint>' > /home/svend/trade-ui/inbox/pending/{ID}_humantrade.json

# 4. Dispatch — auto-chain runs all 6 steps
python3 scripts/bridgeV002/dispatch.py \
  --db-flow trade_cockpit_simulation_v001 \
  --signal-send --from-role humantrade --to-role trend01_trade \
  --id {ID}
```

### Key Configuration

| Setting | File |
|---------|------|
| Permissions (Claude Code) | `.claude/settings.local.json` — `Bash`, `Write` for trade-ui, `Bash(tvly *)` |
| Permissions (OpenCode) | `~/.config/opencode-roles/imple01/opencode.json` — `~/trade-ui/**`, `~/DPMtF-WebUI/docs/**` |
| Permissions (OpenCode GLM) | `~/.config/opencode-roles/glm52trade/opencode.json` — `~/trade-ui/**` |
| Tavily CLI | `tvly` v0.1.4+ installed via `uv tool install tavily-cli`, API key in `~/.bashrc` |
| Content template | `json_output` convention in DB — includes `<search_method>` and `<final_instruction>` |

### Prerequisites

- `tvly` CLI installed and authenticated (`tvly --status`)
- `TAVILY_API_KEY` in `~/.bashrc`
- `OPENROUTER_API_KEY` in `~/.bashrc`
- `MINIMAX_API_KEY` in environment
- Ollama running with models: `qwen3.6:35b-a3b-64k`, `qwen3.6:27b-q4_K_M`, `deepseek-v4-pro:cloud`

## 8. Quick Verification

```bash
cd /home/svend/DPMtF-WebUI
python3 -c "import config; print(config.get_project_root()); print(config.get_bridge_dir())"
python3 -m py_compile app.py && echo "app.py OK"
node --check static/js/dpmtf-app.js && echo "dpmtf-app.js OK"
curl -s http://localhost:9130/api/health
curl -s http://localhost:9130/api/bridge-v2/status
```

## 9. PC-Specific Notes

| Setting | Value |
|---------|-------|
| Username | svend |
| Home | /home/svend |
| Project root | /home/svend/DPMtF-WebUI |
| Trade UI | /home/svend/trade-ui (separate project — inbox, scripts, schemas) |
| Bridge deliverable_dir | **BridgeV002 uses database-driven `deliverable_dir`** from `bridge_flow_steps.deliverable_dir` — *not* legacy `/home/svend/claude-bridge`. Current values: `/home/svend/flows/strict_review/{handoffs,results,reviews,verdicts}` |
| Bridge deliverable_dir | **BridgeV002 uses database-driven `deliverable_dir`** from `bridge_flow_steps.deliverable_dir` — *not* legacy `/home/svend/claude-bridge`. Current values: `/home/svend/flows/cloud_llm/{handoffs,results,reviews,verdicts}` |
| Bridge deliverable_dir | **BridgeV002 uses database-driven `deliverable_dir`** from `bridge_flow_steps.deliverable_dir` — *not* legacy `/home/svend/claude-bridge`. Current values: `/home/svend/flows/cloud_pay/{handoffs,results,reviews,verdicts}` |
| Trade deliverable_dir | `/home/svend/trade-ui/inbox/pending` (absolute path in bridge_flow_steps.deliverable_dir) |
| Ollama endpoint | http://127.0.0.1:11434 |
| Runtime | `/home/svend/.local/bin/uvicorn app:app --host 0.0.0.0 --port 9130 --reload` |
