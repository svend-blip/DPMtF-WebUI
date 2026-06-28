# Design Spec: DPMtF Trade Cockpit Flows

> **Status:** Approved — awaiting implementation plan
> **Date:** 2026-06-28
> **Scope:** Two new BridgeV002 flows for trade-ui JSON output generation

## 1. Purpose

Build two new DPMtF BridgeV002 flows that generate structured JSON output files
for the Trade Cockpit WebUI (`/home/svend/trade-ui`, port 9140).

Trade Cockpit is a simulation-only learning environment for investment/trading
analysis. It receives JSON files in `inbox/pending/`, validates them via
`scripts/import_flow_output.py`, and stores them in SQLite for display and
scoring.

The existing DPMtF flows (`strict_review`, `cloud_llm`, `cloud_pay`) use
markdown-based handoff files. The trade flows are fundamentally different:
they produce **JSON output files** written directly to trade-ui's inbox.

## 2. Two-Flow Architecture

### Flow 1: `trade_cockpit_simulation_v001`

Daily research-to-simulation chain. Triggered by cronjob.

```
human → trend01_trade → market01_trade → analyst01_trade
      → risk01_trade → review01_trade → sim01_trade
```

6 agent roles, 6 steps. Cron: `57 8 * * 1-5` (weekdays 08:57).

### Flow 2: `trade_cockpit_scoring_v001`

Periodic scoring and learning. Triggered manually or via weekly cronjob.

```
human → score01_trade → learn01_trade
```

2 agent roles, 2 steps. Scores open simulated trades, extracts lessons.

## 3. Role Definitions

### 3.1 Flow 1 Roles (Simulation)

| Role Key | Model | Tools | Output Type | Governance |
|----------|-------|-------|-------------|------------|
| `trend01_trade` | Ollama `qwen3.6:35b-a3b-64k` | Tavily | `trend_note` | `431_TRADE_TREND01.md` |
| `market01_trade` | Ollama `qwen3.6:27b-q4_K_M` | Tavily | `market_snapshot` | `432_TRADE_MARKET01.md` |
| `analyst01_trade` | Cloud Anthropic | Tavily | `candidate_note` | `433_TRADE_ANALYST01.md` |
| `risk01_trade` | Ollama `qwen3.6:35b-a3b-64k` | — | `risk_verdict` | `434_TRADE_RISK01.md` |
| `review01_trade` | Cloud Anthropic | — | `review_verdict` | `435_TRADE_REVIEW01.md` |
| `sim01_trade` | Ollama `qwen3.6:27b-q4_K_M` | — | `simulated_trade` | `436_TRADE_SIM01.md` |

### 3.2 Flow 2 Roles (Scoring)

| Role Key | Model | Tools | Output Type | Governance |
|----------|-------|-------|-------------|------------|
| `score01_trade` | Ollama `qwen3.6:27b-q4_K_M` | — | `score_result` | `437_TRADE_SCORE01.md` |
| `learn01_trade` | Ollama `qwen3.6:27b-q4_K_M` | — | `learning_log_entry` | `438_TRADE_LEARN01.md` |

### 3.3 Human Role

| Role Key | Type | Governance |
|----------|------|------------|
| `humantrade` | human | `439_TRADE_HUMAN.md` |

Human role is the flow initiator. `role_type=human` means dispatch skips tmux
injection — the first agent role is started directly with the prompt template.

### 3.4 Role Naming Convention

All trade roles use the `_trade` suffix as required by SCOPE.md §4 and
GATES.md §3.4. Tmux session names match role keys.

## 4. Flow Steps

### 4.1 Flow 1 Steps

| # | Step Key | From | To | Convention | Post-Dispatch |
|---|----------|------|----|------------|---------------|
| 1 | `human-trend01` | humantrade | trend01_trade | `json_output` | post-dispatch-common |
| 2 | `trend01-market01` | trend01_trade | market01_trade | `json_output` | post-dispatch-common |
| 3 | `market01-analyst01` | market01_trade | analyst01_trade | `json_output` | post-dispatch-common |
| 4 | `analyst01-risk01` | analyst01_trade | risk01_trade | `json_output` | post-dispatch-common |
| 5 | `risk01-review01` | risk01_trade | review01_trade | `json_output` | post-dispatch-common |
| 6 | `review01-sim01` | review01_trade | sim01_trade | `json_output` | post-dispatch-common |

### 4.2 Flow 2 Steps

| # | Step Key | From | To | Convention | Post-Dispatch |
|---|----------|------|----|------------|---------------|
| 1 | `human-score01` | humantrade | score01_trade | `json_output` | post-dispatch-common |
| 2 | `score01-learn01` | score01_trade | learn01_trade | `json_output` | post-dispatch-common |

### 4.3 Deliverable Paths

All steps write to: `/home/svend/trade-ui/inbox/pending/`

File pattern: `{flow_run_id}_{role_key}.json`

Example: `trade_20260628_001_trend01_trade.json`

## 5. New Convention: `json_output`

A new convention type is required because the trade flow produces JSON files
for trade-ui's inbox, not markdown handoff files for tmux injection.

### 5.1 Convention Fields

| Field | Value |
|-------|-------|
| `rule_key` | `json_output` |
| `step_type` | `JsonOutput` |
| `rule_type` | `json_output_content` |
| `dir_template` | `/home/svend/trade-ui/inbox/pending` |
| `pattern_template` | `{flow_run_id}_{role_key}.json` |
| `error_template` | `Failed to deliver JSON output to trade-ui inbox.` |

### 5.2 Content Template

```xml
<json_output>
<role>{next_role}</role>
<flow_run_id>{handoff_id}</flow_run_id>
<flow_key>{flow_key}</flow_key>
<output_type>{output_type}</output_type>

<task>
You are {next_role} in the Trade Cockpit simulation flow.

Read the previous role's JSON output from the inbox:
  {previous_deliverable_path}

Produce your JSON output according to your role specification in
docs/dpmtf/20_GATES.md and docs/dpmtf/11_SCOPE.md.

Write the output to: {deliverable_dir}/{deliverable_file}

Required wrapper fields:
  flow_run_id: "{handoff_id}"
  flow_key: "{flow_key}"
  role_key: "{next_role}"
  model_name: "{model_name}"
  created_at: (ISO-8601 with timezone, e.g. 2026-06-28T08:57:00+02:00)
  output_type: "{output_type}"
  status: "completed"
  payload: (role-specific, see GATES.md for required fields)
</task>

<constraint>
- SIMULATION_ONLY = TRUE — no real orders, no broker execution
- Follow role-specific gates from GATES.md
- If required prior output is missing, output status "needs_more_data"
- Write valid JSON only — the import script will reject malformed files
- Allowed decisions only — see GATES.md for your role's allowed decisions
</constraint>

<notification>
Your JSON output will be imported into Trade Cockpit and used by the next role.
</notification>
</json_output>
```

### 5.3 Validation Schema

```json
["<role>", "<flow_run_id>", "<flow_key>", "<output_type>", "<task>", "<constraint>"]
```

### 5.4 Template Variables

| Variable | Source | Example |
|----------|--------|---------|
| `{next_role}` | Step's `to_role` | `trend01_trade` |
| `{handoff_id}` | Generated flow_run_id | `trade_20260628_001` |
| `{flow_key}` | Flow definition | `trade_cockpit_simulation_v001` |
| `{output_type}` | Looked up from role_key → output_type mapping table (§8). If role has multiple allowed types, the first/primary is used | `trend_note` |
| `{model_name}` | Role's `ollama_model` field. For cloud roles (model_type=cloud), uses `cloud_model` field instead | `qwen3.6:35b-a3b-64k` |
| `{deliverable_dir}` | Convention's `dir_template` | `/home/svend/trade-ui/inbox/pending` |
| `{deliverable_file}` | Convention's `pattern_template` resolved | `trade_20260628_001_trend01_trade.json` |
| `{previous_deliverable_path}` | Previous step's deliverable. For the first step (from_role=human), this variable is empty — the role starts fresh with only the prompt template as context | `/home/svend/trade-ui/inbox/pending/trade_20260628_001_trend01_trade.json` |

## 6. Cronjob Initiation

### 6.1 Flow 1 — Daily

```bash
# Weekdays at 08:57 — run the simulation flow
57 8 * * 1-5 cd /home/svend/DPMtF-WebUI && python3 scripts/bridgeV002/dispatch.py \
  --db-flow trade_cockpit_simulation_v001 \
  --signal-send \
  --from-role humantrade \
  --to-role trend01_trade
```

The `--from-role humantrade` (role_type=human) means dispatch skips tmux
injection and starts trend01_trade directly. The prompt template
`daily_trend_scan` is resolved from the database and injected.

### 6.2 Flow 2 — Weekly (optional)

```bash
# Sundays at 18:00 — score open trades and extract lessons
0 18 * * 0 cd /home/svend/DPMtF-WebUI && python3 scripts/bridgeV002/dispatch.py \
  --db-flow trade_cockpit_scoring_v001 \
  --signal-send \
  --from-role humantrade \
  --to-role score01_trade
```

### 6.3 Prompt Template

A prompt template `daily_trend_scan` is stored in the DPMtF database
(`prompt_templates` table). It contains the fixed instruction for the
daily scan — e.g. "Scan Nordic markets for trends using Tavily".
The same template runs every day, but Tavily provides fresh web search
results each time, ensuring new market research on every run.

## 7. Governance Files

Each role requires a 400-series governance file in
`docs/governance-templates-v2/`. These follow the same pattern as the
existing 401-425 files for strict_review, cloud_llm, and cloud_pay.

| # | File | Role | Flow |
|---|------|------|------|
| 431 | `431_TRADE_TREND01.md` | trend01_trade | simulation |
| 432 | `432_TRADE_MARKET01.md` | market01_trade | simulation |
| 433 | `433_TRADE_ANALYST01.md` | analyst01_trade | simulation |
| 434 | `434_TRADE_RISK01.md` | risk01_trade | simulation |
| 435 | `435_TRADE_REVIEW01.md` | review01_trade | simulation |
| 436 | `436_TRADE_SIM01.md` | sim01_trade | simulation |
| 437 | `437_TRADE_SCORE01.md` | score01_trade | scoring |
| 438 | `438_TRADE_LEARN01.md` | learn01_trade | scoring |
| 439 | `439_TRADE_HUMAN.md` | humantrade | both |

Each governance file defines: role identity, allowed actions, forbidden
actions, output contract, model configuration, and escalation rules.

## 8. Role → Output Type Mapping

Enforced by both the `json_output` convention and trade-ui's import script.

| Role | Output Type | Allowed Decisions |
|------|-------------|-------------------|
| trend01_trade | `trend_note` | (descriptive only) |
| market01_trade | `market_snapshot` | (factual data only) |
| analyst01_trade | `candidate_note` | NO_TRADE, WATCHLIST_ONLY, SIMULATED_BUY_CANDIDATE, SIMULATED_SELL_CANDIDATE, NEEDS_MORE_DATA |
| risk01_trade | `risk_verdict` | APPROVE_SIMULATION, REJECT, WATCHLIST_ONLY, NEEDS_MORE_DATA |
| review01_trade | `review_verdict` | APPROVED, APPROVED_FOR_SIMULATION, REJECTED, REJECTED_BY_REVIEW, NEEDS_REWORK, GOVERNANCE_FAIL |
| sim01_trade | `simulated_trade` | SIMULATED_BUY, SIMULATED_SELL, NO_SIMULATION_CREATED |
| score01_trade | `score_result` | (scoring only, no trade decisions) |
| learn01_trade | `learning_log_entry` | (lessons only, no rule activation) |

## 9. Gate Dependencies

Per GATES.md §7, each role must verify prior outputs exist before proceeding:

| Role | Requires Output From |
|------|---------------------|
| market01_trade | trend01_trade |
| analyst01_trade | trend01_trade + market01_trade |
| risk01_trade | analyst01_trade |
| review01_trade | analyst01_trade |
| sim01_trade | risk01_trade AND review01_trade (both must approve) |
| score01_trade | sim01_trade (existing simulated trades) |
| learn01_trade | score01_trade |

If a required prior output is missing or has status `failed`/`rejected`,
the role must output `status: "needs_more_data"` with an appropriate
message in the payload.

## 10. Safety Constraints

All roles operate under hard safety constraints from GATES.md §3.1:

- `SIMULATION_ONLY = TRUE`
- `REAL_ORDERS_DISABLED = TRUE`
- `ETORO_API_DISABLED = TRUE`
- `BROKER_KEYS_ALLOWED = FALSE`

Forbidden payload tokens (auto-reject by import script):
`BUY_REAL`, `SELL_REAL`, `OPEN_ORDER`, `CLOSE_ORDER`, `BROKER_ORDER`,
`ETORO_ORDER`, `CFD_ORDER`, `LEVERAGED_TRADE`, `real_orders_enabled`,
`broker_order`, `real_trade`, `etoro_order`, `broker_api_key`

## 11. What This Design Does NOT Cover

- **Anthropic API model selection** — deferred, configurable later per role
- **Tavily API key configuration** — assumed available as environment variable
- **Prompt template content** — `daily_trend_scan` template content is authored separately
- **trade-ui frontend changes** — trade-ui already supports all 9 output types
- **New database tables** — trade-ui already has all tables (market_snapshots, risk_verdicts, simulated_trades, score_results, learning_log)

## 12. Build Order

1. Create `json_output` convention in DPMtF database
2. Create 8 agent roles + 1 human role
3. Create Flow 1 (`trade_cockpit_simulation_v001`) with 6 steps
4. Create Flow 2 (`trade_cockpit_scoring_v001`) with 2 steps
5. Create 9 governance files (431-439)
6. Create `daily_trend_scan` prompt template
7. Test Flow 1 manually via BridgeV002 UI
8. Configure cronjob for Flow 1
9. Test Flow 2 manually
10. Verify end-to-end: DPMtF → JSON → trade-ui inbox → import → WebUI display
