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
| 11 | **mcp-light context-first** — query mcp-light (`http://127.0.0.1:9135/mcp`) before grep'ing the repo when the task touches governance, frontend layout, panels, bridge roles/flow, or review verdicts. See the 400-series role files' "Context-First Rule (mcp-light)" section for required calls by task type. If unavailable, proceed from repo files and report it. |

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
| `portfolio01_trade` | Portfolio Allocator | qwen3.6:27b (Ollama) | 440_TRADE_PORTFOLIO01.md |

### Starting a Trade Cycle

```bash
cd /home/svend/DPMtF-WebUI

# 1. Create tmux sessions
for s in trend01_trade market01_trade analyst01_trade risk01_trade review01_trade sim01_trade portfolio01_trade; do
  tmux new-session -d -s "$s"
done

# 2. Start coding frontends (includes sim01_trade + portfolio01_trade — start_coding.py fixed)
python3 scripts/bridgeV002/start_coding.py trade_cockpit_simulation_v001

# 3. Create trigger file (ID from database counter)
echo '<role>You are trend01_trade in the trade_cockpit_simulation_v001 flow.</role>
<task>Execute your role according to the governance file. Produce JSON output to the inbox.</task>
<constraint>SIMULATION_ONLY = TRUE. Follow GATES.md. Valid JSON only.</constraint>' > /home/svend/trade-ui/inbox/pending/{ID}_humantrade.json

# 4. Dispatch — auto-chain runs all 7 steps (trend→market→analyst→risk→review→sim01→portfolio01)
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

### Portfolio Allocation/Rebalancing Loop — Status & Next Step

The portfolio allocation/rebalancing loop (spec
`docs/superpowers/specs/2026-07-02-portfolio-allocation-rebalancing-design.md`)
is **FULLY BUILT AND OPERATIONAL END-TO-END** as of 2026-07-03. All build
phases are committed:

- 6.1 read-only scoring → 6.2 allocation_plan JSON → 6.3 swap proposals →
  6.4 bridge executor → 6.5 WebUI approval UI → 6.6 learning loop →
  6.7 `portfolio_allocator.py` CLI → 6.8 close-endpoint fix →
  6.9 DEMO Execute path with human-only approval gate.
- `portfolio01_trade` role activated (governance `440_TRADE_PORTFOLIO01.md`,
  live DB role + flow step 7, tmux session, CLI entrypoint).
- Close-endpoint **verified live** against the real eToro demo API:
  `POST /api/v1/trading/execution/demo/market-close-orders/positions/{id}`
  with body `{"InstrumentID": <int>, "UnitsToDeduct": null}` →
  200 + `{"orderForClose":{"orderID":...}}` (async close).
- `AUTO_EXECUTION_DISABLED` gate resolved: `execute_close_then_open` takes a
  `human_approval` param — autonomous calls blocked (`AUTONOMOUS_EXECUTION_BLOCKED`),
  Human-triggered calls allowed, still subject to `human_review_status='approved'`
  (step 1) + the 14 hard stops + idempotency + DEMO-only invariants.
- Safety invariants (`ETORO_DEMO_ONLY`/`ETORO_LIVE_DISABLED`/`AUTO_EXECUTION_DISABLED`)
  remain `True` (sacred, `etoro_bridge.py` untouched). 168 tests pass.

Commits: trade-ui `bbbc188` (6.1-6.9), Father `d40ae9a` (governance 437/438/440 +
seed). No remaining build blockers.

**NEXT STEP — live end-to-end validation run (not a build step):**

Validate the full chain live on the DEMO account. Either run a full
`trade_cockpit_simulation_v001` cycle (needs the upstream trend→…→sim01 chain +
a stored portfolio snapshot from a prior `sync-positions`), or reuse an existing
`allocation_plan` with a `close_then_open` item:

1. Open the trade-ui WebUI (port 9130, eToro panel → "Portfolio Allocation
   Plan" section).
2. Approve a `close_then_open` plan item (per-item Approve button → sets
   `human_review_status='approved'`).
3. Click the now-enabled **Execute** button → confirm dialog →
   `POST /api/allocation/plans/{plan_id}/items/{plan_item_id}/execute`
   (`human_approval=True`) → `execute_close_then_open` →
   `close_demo_position` (verified market-close-orders endpoint) +
   `place_demo_order` → real DEMO close-then-open.
4. Observe the `execution_status` (succeeded / partial_sequence_failed / blocked)
   and the close `orderID` / order result in the UI.

Notes:
- The close is **asynchronous** — the close order is accepted immediately
  (200 + `orderForClose`); the position closes when the market processes it.
  If the instrument's market is closed (e.g. TSM outside Asian session), the
  order stays pending in `ordersForClose` and the position remains open until
  market open. A portfolio refresh may be needed to confirm actual closure.
- This is DEMO only — never live/real money (sacred invariants enforce).
- The probe script used for the close-endpoint verification is at
  `/tmp/close_probe.py` (not committed).

## 8. Quick Verification

```bash
cd /home/svend/DPMtF-WebUI
python3 -c "import config; print(config.get_project_root()); print(config.get_bridge_dir())"
python3 -m py_compile app.py && echo "app.py OK"
node --check static/js/dpmtf-app.js && echo "dpmtf-app.js OK"
curl -s http://localhost:9130/api/health
curl -s http://localhost:9130/api/bridge-v2/status
systemctl is-active mcp-light   # MCP context server (read-only, 18 tools)
ss -ltnp | grep 9135            # mcp-light MCP HTTP endpoint on 127.0.0.1
```

## 8.1. init_db.py — Keep Slim (Architectural Note)

`scripts/init_db.py` should contain **only schema and canonical defaults** —
not user-configured data. The file is currently oversized (5500+ lines) because
role/flow/step definitions and model-provider choices were incrementally baked
in by handoffs. This is a known debt — cleanup is planned but not started.

**Principle:** Configuration must be visible & configurable (.env /
`machine.json` / frontend) or deleted — never hardcoded as invisible seed
data that overwrites user choices on restore.

**init_db.py should contain:**
- Schema: `CREATE TABLE`, `ALTER TABLE` — canonical structure.
- Canonical defaults: i18n labels, convention rules, governance-file mappings
  for standard roles.
- Minimal seed: `INSERT OR IGNORE` for rows a fresh DB needs to boot.

**init_db.py should NOT contain:**
- User-configured role models/providers (e.g. `imple01pay` →
  `moonshotai/kimi-k2.7-code`) — these belong in the DB (managed via frontend
  + `machine.local.json`), not in init_db.py.
- Flow/step definitions that are actively maintained via the UI.

**When adding/changing a role config:** update the DB (via frontend or
`sqlite3`) + commit `databases/dpmtf.db` to git (rollback safety). Only add to
`init_db.py` if the value is a canonical default needed on a fresh DB — and
use `INSERT OR IGNORE` / `WHERE field IS NULL` so it never overwrites
user-configured values.

**Refactor status (2026-07-05):** `seed_bridge.py` is created (337 lines,
idempotent — `INSERT OR IGNORE` / `WHERE IS NULL`). Bridge seed data
(roles, flows, steps, Machine Profile, governance, config_dir,
enter_command, counters) is extracted from `init_db.py` (5557→5271 lines).
Run order: `init_db.py` (schema) → `seed_bridge.py` (bridge seed, fresh DB
only). After seeding, all changes via frontend or DB edits + git commit.

**Remaining init_db.py debt:** the file is still 5271 lines (schema + i18n +
conventions + ALTER TABLE migrations). A versioned SQL-migration system
(`scripts/db/*.sql` + `schema_migrations` + `migrate.py`) is recommended as
the next refactor — see `~/Dokumenter/Optimeringer.md` §4.2 (Fase E).

## 8.2. Optimization Status + Recommendations

The Optimization Roadmap (Fase Ø/A/B/C) + post-roadmap cleanup is
**complete**. See `~/Dokumenter/Optimeringer.md` for full status.

**Completed (committed to master):**
- app.py 5473→145 lines, 10 routers (Fase B)
- Logging both apps, hardcoded paths removed, SQL f-string fixed (Fase Ø)
- pytest: Father 7 tests, trade-ui 168 tests (Fase A)
- i18n: 15 th-headers→lbl(), i18n SQL-bug fixed (Fase C + post)
- Dead config: start_cmd/start_cmd_suffix columns DROPPED, dispatch gate
  fixed to `if default_runtime:` (post)
- DB-safety rule #7 in `12_CODING_STANDARD.md`, Father DB in git

**Remaining (all low priority — system is operational):**
- Fase D: Central model/interface-schema (model_providers/models/interfaces
  tables + cascading UI) — Machine Profile covers the need today.
- Fase E: Versionerede SQL-migrationer — recommended next (largest
  maintenance risk as init_db.py grows).
- Fase F: Legacy-tabel-oprydning (data-migration of overlapping tables).
- Fase G: Cascading model-selector UI panel.
- Fase H: trade-ui label/version cleanup (v01_→ domain prefix).

**When starting a new optimization:** read `~/Dokumenter/Optimeringer.md`
first for current status + remaining recommendations.

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
| ONYX (optional) | ONYX Lite via docker compose — API `http://127.0.0.1:9162`, web UI `:9163`, onyx-mcp tools `:9164/mcp` (on-demand: `model-allocator mcp-serve`). OPTIONAL runtime: only `backend: onyx` aliases touch it; `docker compose down` removes it without affecting anything. Setup/credentials: `~/model-allocator/deploy/onyx/README.md` |
| mcp-light endpoint | http://127.0.0.1:9135/mcp — MCP streamable-http, read-only context server (18 tools). systemd `mcp-light.service` runs `/home/svend/mcp-light/venv/bin/python server.py`. Repo: `/home/svend/mcp-light` (separate). Configs: `~/.config/opencode-roles/*/opencode.json` `mcp.mcp-light` block. |
| Runtime | `/home/svend/.local/bin/uvicorn app:app --host 0.0.0.0 --port 9130 --reload` |
