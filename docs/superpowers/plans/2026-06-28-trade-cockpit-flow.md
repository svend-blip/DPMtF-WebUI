# Trade Cockpit DPMtF Flows — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two new BridgeV002 flows (`trade_cockpit_simulation_v001` and `trade_cockpit_scoring_v001`) that generate structured JSON output files for the Trade Cockpit WebUI.

**Architecture:** 8 agent roles + 1 human role across two flows. A new `json_output` convention type replaces markdown handoffs with JSON files written directly to trade-ui's inbox. Flow 1 runs daily via cronjob; Flow 2 runs periodically for scoring.

**Tech Stack:** Python/FastAPI (app.py), SQLite (dpmtf.db), BridgeV002 dispatch system, Ollama + Cloud Anthropic models, Tavily web search

**Spec:** `docs/superpowers/specs/2026-06-28-trade-cockpit-flow-design.md`

## Global Constraints

- en-US mandatory for all code, comments, commit messages, governance files
- `python3 -m py_compile app.py` MUST pass before signaling completion
- Parameterized SQL only — `?` placeholders, never f-strings in SQL
- No hardcoded `/home/svend/...` paths — use `config.py` getters
- Only Human may commit — all changes remain unstaged
- `bash -n <file>` for any shell scripts
- No new dependencies without Human approval
- All user-facing text uses `lbl()` — no hardcoded English strings in DOM

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `app.py` | Modify | Add POST `/api/bridge-v2/conventions` endpoint |
| `databases/dpmtf.db` | Modify | Runtime via API: convention, roles, flows, steps |
| `docs/governance-templates-v2/431_TRADE_TREND01.md` | Create | trend01_trade governance |
| `docs/governance-templates-v2/432_TRADE_MARKET01.md` | Create | market01_trade governance |
| `docs/governance-templates-v2/433_TRADE_ANALYST01.md` | Create | analyst01_trade governance |
| `docs/governance-templates-v2/434_TRADE_RISK01.md` | Create | risk01_trade governance |
| `docs/governance-templates-v2/435_TRADE_REVIEW01.md` | Create | review01_trade governance |
| `docs/governance-templates-v2/436_TRADE_SIM01.md` | Create | sim01_trade governance |
| `docs/governance-templates-v2/437_TRADE_SCORE01.md` | Create | score01_trade governance |
| `docs/governance-templates-v2/438_TRADE_LEARN01.md` | Create | learn01_trade governance |
| `docs/governance-templates-v2/439_TRADE_HUMAN.md` | Create | humantrade governance |

---

### Task 1: Add POST endpoint for conventions

**Files:**
- Modify: `app.py` (insert before the PATCH endpoint at line ~4483)

**Interfaces:**
- Consumes: `bridge_convention_rules` table schema
- Produces: `POST /api/bridge-v2/conventions` — accepts JSON body, inserts convention row, returns `{"status": "created", "rule_key": "..."}`

**Why:** No POST endpoint exists for conventions. The PATCH endpoint only updates existing rows. We need to create the `json_output` convention programmatically.

- [ ] **Step 1: Add the POST endpoint in app.py**

Insert this code immediately before the existing `@app.patch("/api/bridge-v2/conventions/{rule_key}")` block (before line 4483):

```python
@app.post("/api/bridge-v2/conventions")
async def bridge_v2_create_convention(request: Request):
    """Create a new BridgeV002 convention rule."""
    data = await request.json()
    required = ["rule_key", "step_type", "dir_template", "pattern_template"]
    for f in required:
        if f not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {f}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    existing = cursor.execute(
        "SELECT rule_key FROM bridge_convention_rules WHERE rule_key = ?",
        (data["rule_key"],)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail=f"Convention '{data['rule_key']}' already exists")

    cursor.execute("""
        INSERT INTO bridge_convention_rules
        (rule_key, step_type, dir_template, pattern_template, error_template,
         prompt_template, content_template, validation_schema, rule_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["rule_key"],
        data["step_type"],
        data["dir_template"],
        data["pattern_template"],
        data.get("error_template", ""),
        data.get("prompt_template", ""),
        data.get("content_template", ""),
        data.get("validation_schema", ""),
        data.get("rule_type", "generic"),
    ))
    conn.commit()
    conn.close()
    return {"status": "created", "rule_key": data["rule_key"]}
```

- [ ] **Step 2: Validate backend syntax**

Run: `python3 -m py_compile app.py`
Expected: No output (clean compile)

- [ ] **Step 3: Restart DPMtF to pick up the new endpoint**

Run: `lsof -ti:9130 | xargs kill 2>/dev/null; sleep 1 && cd /home/svend/DPMtF-WebUI && nohup /home/svend/.local/bin/uvicorn app:app --host 0.0.0.0 --port 9130 --reload > /tmp/dpmtf-9130.log 2>&1 &`
Wait 2 seconds, then: `curl -s http://127.0.0.1:9130/api/health`
Expected: `{"status":"healthy","app":"DPMtF WebUI",...}`

- [ ] **Step 4: Verify the new endpoint exists**

Run: `curl -s -X POST http://127.0.0.1:9130/api/bridge-v2/conventions -H "Content-Type: application/json" -d '{"rule_key":"test_temp","step_type":"Test","dir_template":"test","pattern_template":"test.json"}'`
Expected: `{"status":"created","rule_key":"test_temp"}`

- [ ] **Step 5: Clean up test data**

Run: `curl -s -X DELETE http://127.0.0.1:9130/api/bridge-v2/conventions/test_temp` (if DELETE exists, otherwise use sqlite3 to remove the test row)

---

### Task 2: Create json_output convention

**Files:**
- Modify: `databases/dpmtf.db` (via API)

**Interfaces:**
- Consumes: `POST /api/bridge-v2/conventions` (created in Task 1)
- Produces: `json_output` convention row in `bridge_convention_rules`

- [ ] **Step 1: Create the convention via API**

Run:
```bash
curl -s -X POST http://127.0.0.1:9130/api/bridge-v2/conventions \
  -H "Content-Type: application/json" \
  -d '{
    "rule_key": "json_output",
    "step_type": "JsonOutput",
    "rule_type": "json_output_content",
    "dir_template": "/home/svend/trade-ui/inbox/pending",
    "pattern_template": "{ID}_{role_key}.json",
    "error_template": "Failed to deliver JSON output to trade-ui inbox.",
    "content_template": "<json_output>\n<role>{next_role}</role>\n<flow_run_id>{handoff_id}</flow_run_id>\n<flow_key>{flow_key}</flow_key>\n<output_type>{output_type}</output_type>\n\n<task>\nYou are {next_role} in the Trade Cockpit simulation flow.\n\nRead the previous role's JSON output from the inbox:\n  {previous_deliverable_path}\n\nProduce your JSON output according to your role specification in\ndocs/dpmtf/20_GATES.md and docs/dpmtf/11_SCOPE.md.\n\nWrite the output to: {deliverable_dir}/{deliverable_file}\n\nRequired wrapper fields:\n  flow_run_id: \"{handoff_id}\"\n  flow_key: \"{flow_key}\"\n  role_key: \"{next_role}\"\n  model_name: \"{model_name}\"\n  created_at: (ISO-8601 with timezone, e.g. 2026-06-28T08:57:00+02:00)\n  output_type: \"{output_type}\"\n  status: \"completed\"\n  payload: (role-specific, see GATES.md for required fields)\n</task>\n\n<constraint>\n- SIMULATION_ONLY = TRUE — no real orders, no broker execution\n- Follow role-specific gates from GATES.md\n- If required prior output is missing, output status \"needs_more_data\"\n- Write valid JSON only — the import script will reject malformed files\n- Allowed decisions only — see GATES.md for your role's allowed decisions\n</constraint>\n\n<notification>\nYour JSON output will be imported into Trade Cockpit and used by the next role.\n</notification>\n</json_output>",
    "validation_schema": "[\"<role>\", \"<flow_run_id>\", \"<flow_key>\", \"<output_type>\", \"<task>\", \"<constraint>\"]"
  }'
```
Expected: `{"status":"created","rule_key":"json_output"}`

- [ ] **Step 2: Verify the convention was created**

Run: `curl -s http://127.0.0.1:9130/api/bridge-v2/conventions | python3 -c "import sys,json; [print(c['rule_key'], c['step_type']) for c in json.load(sys.stdin)['conventions'] if c['rule_key']=='json_output']"`
Expected: `json_output JsonOutput`

---

### Task 3: Create 9 roles (8 agent + 1 human)

**Files:**
- Modify: `databases/dpmtf.db` (via API)

**Interfaces:**
- Consumes: `POST /api/bridge-v2/roles`
- Produces: 9 rows in `bridge_roles`

- [ ] **Step 1: Create humantrade (human role)**

Run:
```bash
curl -s -X POST http://127.0.0.1:9130/api/bridge-v2/roles \
  -H "Content-Type: application/json" \
  -d '{"role_key":"humantrade","tmux_session":"humantrade","role_type":"human","governance_file":"439_TRADE_HUMAN.md","model_type":"ollama","ollama_model":"","cloud_model":""}'
```
Expected: `{"status":"created","role_key":"humantrade"}`

- [ ] **Step 2: Create trend01_trade**

Run:
```bash
curl -s -X POST http://127.0.0.1:9130/api/bridge-v2/roles \
  -H "Content-Type: application/json" \
  -d '{"role_key":"trend01_trade","tmux_session":"trend01_trade","role_type":"agent","governance_file":"431_TRADE_TREND01.md","model_type":"ollama","ollama_model":"qwen3.6:35b-a3b-64k","cloud_model":"","enter_command":"default","start_cmd_suffix":"&& CLAUDE_CODE_MAX_OUTPUT_TOKENS=16384 ANTHROPIC_BASE_URL=http://127.0.0.1:11434 ANTHROPIC_AUTH_TOKEN=ollama claude --model qwen3.6:35b-a3b-64k"}'
```
Expected: `{"status":"created","role_key":"trend01_trade"}`

- [ ] **Step 3: Create market01_trade**

Run:
```bash
curl -s -X POST http://127.0.0.1:9130/api/bridge-v2/roles \
  -H "Content-Type: application/json" \
  -d '{"role_key":"market01_trade","tmux_session":"market01_trade","role_type":"agent","governance_file":"432_TRADE_MARKET01.md","model_type":"ollama","ollama_model":"qwen3.6:27b-q4_K_M","cloud_model":"","enter_command":"default","start_cmd_suffix":"&& CLAUDE_CODE_MAX_OUTPUT_TOKENS=16384 ANTHROPIC_BASE_URL=http://127.0.0.1:11434 ANTHROPIC_AUTH_TOKEN=ollama claude --model qwen3.6:27b-q4_K_M"}'
```
Expected: `{"status":"created","role_key":"market01_trade"}`

- [ ] **Step 4: Create analyst01_trade (Cloud Anthropic)**

Run:
```bash
curl -s -X POST http://127.0.0.1:9130/api/bridge-v2/roles \
  -H "Content-Type: application/json" \
  -d '{"role_key":"analyst01_trade","tmux_session":"analyst01_trade","role_type":"agent","governance_file":"433_TRADE_ANALYST01.md","model_type":"cloud","ollama_model":"","cloud_model":"Anthropic","enter_command":"c-m","start_cmd_suffix":"&& OPENCODE_CONFIG_DIR=\"$HOME/.config/opencode-roles/analyst01_trade\" OPENCODE_CONFIG=\"$HOME/.config/opencode-roles/analyst01_trade/opencode.json\" /home/svend/.opencode/bin/opencode --model anthropic/claude-sonnet-4-6"}'
```
Expected: `{"status":"created","role_key":"analyst01_trade"}`

- [ ] **Step 5: Create risk01_trade**

Run:
```bash
curl -s -X POST http://127.0.0.1:9130/api/bridge-v2/roles \
  -H "Content-Type: application/json" \
  -d '{"role_key":"risk01_trade","tmux_session":"risk01_trade","role_type":"agent","governance_file":"434_TRADE_RISK01.md","model_type":"ollama","ollama_model":"qwen3.6:35b-a3b-64k","cloud_model":"","enter_command":"default","start_cmd_suffix":"&& CLAUDE_CODE_MAX_OUTPUT_TOKENS=16384 ANTHROPIC_BASE_URL=http://127.0.0.1:11434 ANTHROPIC_AUTH_TOKEN=ollama claude --model qwen3.6:35b-a3b-64k"}'
```
Expected: `{"status":"created","role_key":"risk01_trade"}`

- [ ] **Step 6: Create review01_trade (Cloud Anthropic)**

Run:
```bash
curl -s -X POST http://127.0.0.1:9130/api/bridge-v2/roles \
  -H "Content-Type: application/json" \
  -d '{"role_key":"review01_trade","tmux_session":"review01_trade","role_type":"agent","governance_file":"435_TRADE_REVIEW01.md","model_type":"cloud","ollama_model":"","cloud_model":"Anthropic","enter_command":"c-m","start_cmd_suffix":"&& OPENCODE_CONFIG_DIR=\"$HOME/.config/opencode-roles/review01_trade\" OPENCODE_CONFIG=\"$HOME/.config/opencode-roles/review01_trade/opencode.json\" /home/svend/.opencode/bin/opencode --model anthropic/claude-sonnet-4-6"}'
```
Expected: `{"status":"created","role_key":"review01_trade"}`

- [ ] **Step 7: Create sim01_trade**

Run:
```bash
curl -s -X POST http://127.0.0.1:9130/api/bridge-v2/roles \
  -H "Content-Type: application/json" \
  -d '{"role_key":"sim01_trade","tmux_session":"sim01_trade","role_type":"agent","governance_file":"436_TRADE_SIM01.md","model_type":"ollama","ollama_model":"qwen3.6:27b-q4_K_M","cloud_model":"","enter_command":"default","start_cmd_suffix":"&& CLAUDE_CODE_MAX_OUTPUT_TOKENS=16384 ANTHROPIC_BASE_URL=http://127.0.0.1:11434 ANTHROPIC_AUTH_TOKEN=ollama claude --model qwen3.6:27b-q4_K_M"}'
```
Expected: `{"status":"created","role_key":"sim01_trade"}`

- [ ] **Step 8: Create score01_trade**

Run:
```bash
curl -s -X POST http://127.0.0.1:9130/api/bridge-v2/roles \
  -H "Content-Type: application/json" \
  -d '{"role_key":"score01_trade","tmux_session":"score01_trade","role_type":"agent","governance_file":"437_TRADE_SCORE01.md","model_type":"ollama","ollama_model":"qwen3.6:27b-q4_K_M","cloud_model":"","enter_command":"default","start_cmd_suffix":"&& CLAUDE_CODE_MAX_OUTPUT_TOKENS=16384 ANTHROPIC_BASE_URL=http://127.0.0.1:11434 ANTHROPIC_AUTH_TOKEN=ollama claude --model qwen3.6:27b-q4_K_M"}'
```
Expected: `{"status":"created","role_key":"score01_trade"}`

- [ ] **Step 9: Create learn01_trade**

Run:
```bash
curl -s -X POST http://127.0.0.1:9130/api/bridge-v2/roles \
  -H "Content-Type: application/json" \
  -d '{"role_key":"learn01_trade","tmux_session":"learn01_trade","role_type":"agent","governance_file":"438_TRADE_LEARN01.md","model_type":"ollama","ollama_model":"qwen3.6:27b-q4_K_M","cloud_model":"","enter_command":"default","start_cmd_suffix":"&& CLAUDE_CODE_MAX_OUTPUT_TOKENS=16384 ANTHROPIC_BASE_URL=http://127.0.0.1:11434 ANTHROPIC_AUTH_TOKEN=ollama claude --model qwen3.6:27b-q4_K_M"}'
```
Expected: `{"status":"created","role_key":"learn01_trade"}`

- [ ] **Step 10: Verify all 9 roles exist**

Run: `curl -s http://127.0.0.1:9130/api/bridge-v2/roles | python3 -c "import sys,json; roles=[r['role_key'] for r in json.load(sys.stdin)['roles'] if r['role_key'].endswith('trade') or r['role_key']=='humantrade']; print(f'{len(roles)} trade roles:', sorted(roles))"`
Expected: `9 trade roles: ['analyst01_trade', 'humantrade', 'learn01_trade', 'market01_trade', 'review01_trade', 'risk01_trade', 'score01_trade', 'sim01_trade', 'trend01_trade']`

---

### Task 4: Create Flow 1 — trade_cockpit_simulation_v001

**Files:**
- Modify: `databases/dpmtf.db` (via API)

**Interfaces:**
- Consumes: `POST /api/bridge-v2/flows` (with inline steps)
- Produces: Flow + 6 steps in `bridge_flows` / `bridge_flow_steps`

- [ ] **Step 1: Create the flow with all 6 steps inline**

Run:
```bash
curl -s -X POST http://127.0.0.1:9130/api/bridge-v2/flows \
  -H "Content-Type: application/json" \
  -d '{
    "flow_key": "trade_cockpit_simulation_v001",
    "name": "Trade Cockpit Simulation",
    "description": "Daily research-to-simulation chain: trend01→market01→analyst01→risk01→review01→sim01",
    "steps": [
      {
        "step_key": "human-trend01",
        "from_role": "humantrade",
        "to_role": "trend01_trade",
        "rule_key": "json_output",
        "post_dispatch_script": "post-dispatch-common",
        "error_msg": "Failed to deliver JSON output to trade-ui inbox."
      },
      {
        "step_key": "trend01-market01",
        "from_role": "trend01_trade",
        "to_role": "market01_trade",
        "rule_key": "json_output",
        "post_dispatch_script": "post-dispatch-common",
        "error_msg": "Failed to deliver JSON output to trade-ui inbox."
      },
      {
        "step_key": "market01-analyst01",
        "from_role": "market01_trade",
        "to_role": "analyst01_trade",
        "rule_key": "json_output",
        "post_dispatch_script": "post-dispatch-common",
        "error_msg": "Failed to deliver JSON output to trade-ui inbox."
      },
      {
        "step_key": "analyst01-risk01",
        "from_role": "analyst01_trade",
        "to_role": "risk01_trade",
        "rule_key": "json_output",
        "post_dispatch_script": "post-dispatch-common",
        "error_msg": "Failed to deliver JSON output to trade-ui inbox."
      },
      {
        "step_key": "risk01-review01",
        "from_role": "risk01_trade",
        "to_role": "review01_trade",
        "rule_key": "json_output",
        "post_dispatch_script": "post-dispatch-common",
        "error_msg": "Failed to deliver JSON output to trade-ui inbox."
      },
      {
        "step_key": "review01-sim01",
        "from_role": "review01_trade",
        "to_role": "sim01_trade",
        "rule_key": "json_output",
        "post_dispatch_script": "post-dispatch-common",
        "error_msg": "Failed to deliver JSON output to trade-ui inbox."
      }
    ]
  }'
```
Expected: `{"status":"created","flow_key":"trade_cockpit_simulation_v001","steps_added":6}`

- [ ] **Step 2: Verify the flow and steps**

Run: `curl -s http://127.0.0.1:9130/api/bridge-v2/steps/trade_cockpit_simulation_v001 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Flow: {d[\"flow_key\"]}, Steps: {d[\"count\"]}'); [print(f'  {s[\"sort_order\"]}. {s[\"step_key\"]}: {s[\"from_role\"]}→{s[\"to_role\"]} [{s[\"rule_key\"]}]') for s in d['steps']]"`
Expected:
```
Flow: trade_cockpit_simulation_v001, Steps: 6
  1. human-trend01: humantrade→trend01_trade [json_output]
  2. trend01-market01: trend01_trade→market01_trade [json_output]
  3. market01-analyst01: market01_trade→analyst01_trade [json_output]
  4. analyst01-risk01: analyst01_trade→risk01_trade [json_output]
  5. risk01-review01: risk01_trade→review01_trade [json_output]
  6. review01-sim01: review01_trade→sim01_trade [json_output]
```

---

### Task 5: Create Flow 2 — trade_cockpit_scoring_v001

**Files:**
- Modify: `databases/dpmtf.db` (via API)

**Interfaces:**
- Consumes: `POST /api/bridge-v2/flows`
- Produces: Flow + 2 steps

- [ ] **Step 1: Create the flow with 2 steps inline**

Run:
```bash
curl -s -X POST http://127.0.0.1:9130/api/bridge-v2/flows \
  -H "Content-Type: application/json" \
  -d '{
    "flow_key": "trade_cockpit_scoring_v001",
    "name": "Trade Cockpit Scoring",
    "description": "Periodic scoring and learning: score01→learn01",
    "steps": [
      {
        "step_key": "human-score01",
        "from_role": "humantrade",
        "to_role": "score01_trade",
        "rule_key": "json_output",
        "post_dispatch_script": "post-dispatch-common",
        "error_msg": "Failed to deliver JSON output to trade-ui inbox."
      },
      {
        "step_key": "score01-learn01",
        "from_role": "score01_trade",
        "to_role": "learn01_trade",
        "rule_key": "json_output",
        "post_dispatch_script": "post-dispatch-common",
        "error_msg": "Failed to deliver JSON output to trade-ui inbox."
      }
    ]
  }'
```
Expected: `{"status":"created","flow_key":"trade_cockpit_scoring_v001","steps_added":2}`

- [ ] **Step 2: Verify the flow and steps**

Run: `curl -s http://127.0.0.1:9130/api/bridge-v2/steps/trade_cockpit_scoring_v001 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Flow: {d[\"flow_key\"]}, Steps: {d[\"count\"]}'); [print(f'  {s[\"sort_order\"]}. {s[\"step_key\"]}: {s[\"from_role\"]}→{s[\"to_role\"]} [{s[\"rule_key\"]}]') for s in d['steps']]"`
Expected:
```
Flow: trade_cockpit_scoring_v001, Steps: 2
  1. human-score01: humantrade→score01_trade [json_output]
  2. score01-learn01: score01_trade→learn01_trade [json_output]
```

- [ ] **Step 3: Verify all 4 flows exist in DPMtF**

Run: `curl -s http://127.0.0.1:9130/api/bridge-v2/flows | python3 -c "import sys,json; [print(f['flow_key']) for f in json.load(sys.stdin)['flows']]"`
Expected:
```
cloud_llm
cloud_pay
strict_review
trade_cockpit_simulation_v001
trade_cockpit_scoring_v001
```

---

### Task 6: Create 9 governance files

**Files:**
- Create: `docs/governance-templates-v2/431_TRADE_TREND01.md`
- Create: `docs/governance-templates-v2/432_TRADE_MARKET01.md`
- Create: `docs/governance-templates-v2/433_TRADE_ANALYST01.md`
- Create: `docs/governance-templates-v2/434_TRADE_RISK01.md`
- Create: `docs/governance-templates-v2/435_TRADE_REVIEW01.md`
- Create: `docs/governance-templates-v2/436_TRADE_SIM01.md`
- Create: `docs/governance-templates-v2/437_TRADE_SCORE01.md`
- Create: `docs/governance-templates-v2/438_TRADE_LEARN01.md`
- Create: `docs/governance-templates-v2/439_TRADE_HUMAN.md`

**Interfaces:**
- Consumes: Spec §7, trade-ui SCOPE.md §9, trade-ui GATES.md
- Produces: 9 governance files following the 422_CLOUD_PAY_ARCHI01PAY.md template pattern

**Pattern:** Each file follows the same structure as existing 400-series files:
1. Role identity header
2. When active section
3. Role-specific boundaries/constraints
4. Output contract (JSON wrapper fields)
5. Allowed decisions
6. Forbidden actions
7. Model configuration
8. Escalation rules

- [ ] **Step 1: Create 431_TRADE_TREND01.md**

Write file `docs/governance-templates-v2/431_TRADE_TREND01.md`:

```markdown
# 431 — TRADE_TREND01

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **trend01_trade** (Trend Synthesizer) in the DPMtF `trade_cockpit_simulation_v001` flow.
You turn source observations and web research into structured trend themes.

## When You Are Active

- At the start of a `trade_cockpit_simulation_v001` cycle: Human or cronjob initiates the flow,
  and you are the first agent role. You receive a prompt template with the day's research scope.
- You run once per cycle — your output feeds market01_trade and analyst01_trade.

## Model Configuration

| Field | Value |
|-------|-------|
| model_type | ollama |
| ollama_model | qwen3.6:35b-a3b-64k |
| Tools | Tavily web search |

## Output Contract

You produce a JSON file written to `/home/svend/trade-ui/inbox/pending/`.

Required wrapper:
```json
{
  "flow_run_id": "<generated>",
  "flow_key": "trade_cockpit_simulation_v001",
  "role_key": "trend01_trade",
  "model_name": "qwen3.6:35b-a3b-64k",
  "created_at": "<ISO-8601 with timezone>",
  "output_type": "trend_note",
  "status": "completed",
  "payload": { ... }
}
```

Payload fields:
- `symbols`: array of relevant symbols/ tickers identified
- `themes`: array of trend themes with descriptions
- `sentiment`: overall market sentiment (bullish/bearish/neutral)
- `sources`: references used (Tavily search results, manual notes)
- `summary`: concise trend summary

## Allowed Actions

- Use Tavily to search for current market trends, news, and sector movements
- Identify symbols and themes from web research
- Produce descriptive trend notes — no trading decisions

## Forbidden Actions

- Do NOT produce buy/sell recommendations
- Do NOT create simulated trades
- Do NOT output broker orders
- Do NOT use paywall scraping
- Do NOT output `simulated_trade`, `risk_verdict`, `broker_order`, `real_trade`

## Constraints

- SIMULATION_ONLY = TRUE
- REAL_ORDERS_DISABLED = TRUE
- If Tavily search fails, note the failure in payload and set status "needs_more_data"
- All output must be valid JSON — the trade-ui import script will reject malformed files

## Escalation

If you cannot complete your task (e.g. Tavily unavailable, no useful results), output
`status: "needs_more_data"` with an explanation in the payload. The next role will see this
and act accordingly.
```

- [ ] **Step 2: Create 432_TRADE_MARKET01.md**

Write file `docs/governance-templates-v2/432_TRADE_MARKET01.md`:

```markdown
# 432 — TRADE_MARKET01

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **market01_trade** (Market Snapshot Builder) in the DPMtF `trade_cockpit_simulation_v001` flow.
You collect factual market data for symbols identified by trend01_trade.

## When You Are Active

- After trend01_trade has produced its `trend_note` JSON output.
- You read trend01_trade's output from the trade-ui inbox to know which symbols to analyze.

## Model Configuration

| Field | Value |
|-------|-------|
| model_type | ollama |
| ollama_model | qwen3.6:27b-q4_K_M |
| Tools | Tavily web search |

## Output Contract

You produce a JSON file written to `/home/svend/trade-ui/inbox/pending/`.

Required wrapper:
```json
{
  "flow_run_id": "<same as trend01>",
  "flow_key": "trade_cockpit_simulation_v001",
  "role_key": "market01_trade",
  "model_name": "qwen3.6:27b-q4_K_M",
  "created_at": "<ISO-8601 with timezone>",
  "output_type": "market_snapshot",
  "status": "completed",
  "payload": { ... }
}
```

Payload fields (per GATES.md §13.2):
- `symbol`: the symbol this snapshot is for
- `price`: current price (if available)
- `volume`: current volume (if available)
- `ma_20`, `ma_50`, `ma_200`: moving averages (if available)
- `rsi_14`: RSI value (if available)
- `volatility_20d`: 20-day volatility (if available)
- `trend_score`: composite trend score
- `snapshot_at`: ISO-8601 timestamp of the data

## Allowed Actions

- Use Tavily to find current market data for symbols
- Produce factual market snapshots — no opinions, no recommendations
- Note when data is unavailable rather than fabricating numbers

## Forbidden Actions

- Do NOT produce buy/sell recommendations
- Do NOT create candidate analyses
- Do NOT output simulated trades
- Do NOT fabricate market data — mark unavailable fields as null
- Do NOT output `candidate_analysis`, `risk_verdict`, `review_verdict`, `simulated_trade`, `broker_order`

## Constraints

- This role should be facts-only and opinion-light
- If trend01_trade output is missing or has status "needs_more_data", output `status: "needs_more_data"`
- If market data is unavailable for a symbol, set those fields to null — do not guess

## Escalation

If trend01_trade's output is missing or unusable, output `status: "needs_more_data"`.
If Tavily returns no useful market data, document this in the payload.
```

- [ ] **Step 3: Create 433_TRADE_ANALYST01.md**

Write file `docs/governance-templates-v2/433_TRADE_ANALYST01.md`:

```markdown
# 433 — TRADE_ANALYST01

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **analyst01_trade** (Candidate Analyst) in the DPMtF `trade_cockpit_simulation_v001` flow.
You combine trend and market data into candidate investment notes.

## When You Are Active

- After trend01_trade AND market01_trade have produced their outputs.
- You read both prior outputs from the trade-ui inbox.

## Model Configuration

| Field | Value |
|-------|-------|
| model_type | cloud |
| cloud_model | Anthropic |
| Tools | Tavily web search |

## Output Contract

You produce a JSON file written to `/home/svend/trade-ui/inbox/pending/`.

Required wrapper:
```json
{
  "flow_run_id": "<same as prior steps>",
  "flow_key": "trade_cockpit_simulation_v001",
  "role_key": "analyst01_trade",
  "model_name": "Anthropic",
  "created_at": "<ISO-8601 with timezone>",
  "output_type": "candidate_note",
  "status": "completed",
  "payload": { ... }
}
```

Payload fields (per GATES.md §8.1):
- `symbol`: the symbol being analyzed
- `decision`: one of the allowed decisions below
- `score`: 0-100 candidate score
- `summary`: concise analysis summary

## Allowed Decisions (GATES.md §5.5)

- `NO_TRADE` — no action recommended
- `WATCHLIST_ONLY` — interesting but not actionable now
- `SIMULATED_BUY_CANDIDATE` — potential simulated buy
- `SIMULATED_SELL_CANDIDATE` — potential simulated sell
- `NEEDS_MORE_DATA` — insufficient information

## Forbidden Actions

- Do NOT output `risk_verdict`, `review_verdict`, `simulated_trade`
- Do NOT output `broker_order`, `real_trade`
- Do NOT use real trading language (BUY, SELL without SIMULATED_ prefix)
- Do NOT set score outside 0-100 range

## Constraints

- SIMULATION_ONLY = TRUE
- If prior outputs are missing or have status "needs_more_data", output `status: "needs_more_data"`
- Score must be justified by the evidence in the summary
- Use Tavily to supplement research on specific candidates

## Escalation

If both trend01_trade and market01_trade outputs are missing or unusable,
output `status: "needs_more_data"` with explanation.
```

- [ ] **Step 4: Create 434_TRADE_RISK01.md**

Write file `docs/governance-templates-v2/434_TRADE_RISK01.md`:

```markdown
# 434 — TRADE_RISK01

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **risk01_trade** (Risk Gate / Veto Role) in the DPMtF `trade_cockpit_simulation_v001` flow.
You decide whether a candidate is safe enough for simulated trading.

## When You Are Active

- After analyst01_trade has produced its `candidate_note` output.
- You read analyst01_trade's output from the trade-ui inbox.

## Model Configuration

| Field | Value |
|-------|-------|
| model_type | ollama |
| ollama_model | qwen3.6:35b-a3b-64k |

## Output Contract

You produce a JSON file written to `/home/svend/trade-ui/inbox/pending/`.

Required wrapper:
```json
{
  "flow_run_id": "<same as prior steps>",
  "flow_key": "trade_cockpit_simulation_v001",
  "role_key": "risk01_trade",
  "model_name": "qwen3.6:35b-a3b-64k",
  "created_at": "<ISO-8601 with timezone>",
  "output_type": "risk_verdict",
  "status": "completed",
  "payload": { ... }
}
```

Payload fields (per GATES.md §9.1):
- `symbol`: the symbol being evaluated
- `risk_decision`: one of the allowed decisions below
- `risk_score`: 0-100 risk score
- `max_position_pct`: max position as % of virtual portfolio (required if APPROVE_SIMULATION)
- `max_loss_pct`: max acceptable loss % (required if APPROVE_SIMULATION)
- `risk_reward_ratio`: risk/reward ratio (required if APPROVE_SIMULATION, must be >= 1:2)
- `stop_loss_suggestion`: suggested stop loss (required if APPROVE_SIMULATION)
- `veto_reason`: explanation if vetoing

## Allowed Decisions (GATES.md §5.6)

- `APPROVE_SIMULATION` — safe for simulated trading
- `REJECT` — veto, do not proceed
- `WATCHLIST_ONLY` — not safe enough for simulation
- `NEEDS_MORE_DATA` — insufficient risk data

## Veto Authority (GATES.md §9.3)

If you output REJECT, WATCHLIST_ONLY, or NEEDS_MORE_DATA, sim01_trade MUST NOT create a simulated trade.

## Risk Thresholds (GATES.md §9.4)

- Max simulated loss per trade <= 1% of virtual portfolio
- Risk/reward >= 1:2 for simulated trade
- No simulated trade if stop_loss is missing
- No simulated trade if entry_price is missing
- No simulated trade if thesis is missing

## Forbidden Actions

- Do NOT output `candidate_analysis`, `review_verdict`, `simulated_trade`
- Do NOT output `broker_order`, `real_trade`
- Do NOT approve a candidate that lacks a thesis or invalidation condition

## Escalation

If analyst01_trade output is missing or has status "needs_more_data",
output `status: "needs_more_data"`.
```

- [ ] **Step 5: Create 435_TRADE_REVIEW01.md**

Write file `docs/governance-templates-v2/435_TRADE_REVIEW01.md`:

```markdown
# 435 — TRADE_REVIEW01

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **review01_trade** (Independent Reviewer) in the DPMtF `trade_cockpit_simulation_v001` flow.
You review all previous outputs for hallucination, missing data, weak evidence, and governance breaches.

## When You Are Active

- After risk01_trade has produced its `risk_verdict` output.
- You read analyst01_trade's AND risk01_trade's outputs from the trade-ui inbox.

## Model Configuration

| Field | Value |
|-------|-------|
| model_type | cloud |
| cloud_model | Anthropic |

## Output Contract

You produce a JSON file written to `/home/svend/trade-ui/inbox/pending/`.

Required wrapper:
```json
{
  "flow_run_id": "<same as prior steps>",
  "flow_key": "trade_cockpit_simulation_v001",
  "role_key": "review01_trade",
  "model_name": "Anthropic",
  "created_at": "<ISO-8601 with timezone>",
  "output_type": "review_verdict",
  "status": "completed",
  "payload": { ... }
}
```

Payload fields (per GATES.md §10.1):
- `review_decision`: one of the allowed decisions below
- `governance_pass`: true/false — did all outputs follow governance rules?
- `verdict_summary`: concise review summary
- `hallucination_risk`: 0-100 (optional but recommended)
- `missing_data`: array of missing data points (optional)
- `issues`: array of issues found (optional)

## Allowed Decisions (GATES.md §5.7)

- `APPROVED` — for non-trade notes
- `APPROVED_FOR_SIMULATION` — safe for simulated trading
- `REJECTED` — does not meet standards
- `REJECTED_BY_REVIEW` — review-specific rejection
- `NEEDS_REWORK` — needs changes before proceeding
- `GOVERNANCE_FAIL` — governance rules were violated

## Veto Authority (GATES.md §10.3)

If you output REJECTED, REJECTED_BY_REVIEW, NEEDS_REWORK, or GOVERNANCE_FAIL,
sim01_trade MUST NOT create a simulated trade.

## Governance Pass Gate (GATES.md §10.4)

If `governance_pass = false` or `review_decision = GOVERNANCE_FAIL`,
the flow must stop before simulation.

## Forbidden Actions

- Do NOT output `candidate_analysis`, `risk_verdict`, `simulated_trade`
- Do NOT output `broker_order`, `real_trade`
- Do NOT approve outputs that contain forbidden payload tokens

## Escalation

If prior outputs are missing or have status "needs_more_data",
output `status: "needs_more_data"`.
```

- [ ] **Step 6: Create 436_TRADE_SIM01.md**

Write file `docs/governance-templates-v2/436_TRADE_SIM01.md`:

```markdown
# 436 — TRADE_SIM01

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **sim01_trade** (Simulation Executor) in the DPMtF `trade_cockpit_simulation_v001` flow.
You create simulated trade records ONLY if risk01_trade AND review01_trade both approve.

## When You Are Active

- After risk01_trade AND review01_trade have both produced their outputs.
- You read both verdicts from the trade-ui inbox.

## Model Configuration

| Field | Value |
|-------|-------|
| model_type | ollama |
| ollama_model | qwen3.6:27b-q4_K_M |

## Output Contract

You produce a JSON file written to `/home/svend/trade-ui/inbox/pending/`.

Required wrapper:
```json
{
  "flow_run_id": "<same as prior steps>",
  "flow_key": "trade_cockpit_simulation_v001",
  "role_key": "sim01_trade",
  "model_name": "qwen3.6:27b-q4_K_M",
  "created_at": "<ISO-8601 with timezone>",
  "output_type": "simulated_trade",
  "status": "completed",
  "payload": { ... }
}
```

Payload fields (per GATES.md §11.2):
- `symbol`: the symbol
- `action`: SIMULATED_BUY, SIMULATED_SELL, or NO_SIMULATION_CREATED
- `entry_price`: entry price
- `simulated_size_usd`: position size in USD
- `stop_loss`: stop loss price
- `take_profit`: take profit price
- `thesis`: why this trade
- `invalidation_condition`: what would invalidate the thesis
- `status`: "open"
- `opened_at`: ISO-8601 timestamp

## Approval Gate (GATES.md §11.1)

You may create a simulated_trade ONLY if ALL of:
1. analyst01_trade produced SIMULATED_BUY_CANDIDATE or SIMULATED_SELL_CANDIDATE
2. risk01_trade produced APPROVE_SIMULATION
3. review01_trade produced APPROVED_FOR_SIMULATION
4. SIMULATION_ONLY = TRUE
5. REAL_ORDERS_DISABLED = TRUE

If ANY condition is not met, output `action: "NO_SIMULATION_CREATED"`.

## Allowed Actions (GATES.md §5.8)

- `SIMULATED_BUY`
- `SIMULATED_SELL`
- `NO_SIMULATION_CREATED`

## Forbidden Actions

- Do NOT output `real_trade`, `broker_order`, `etoro_order`
- Do NOT use leverage or CFD execution
- Do NOT create a trade without both risk and review approval
- Do NOT use real trading language without SIMULATED_ prefix

## Escalation

If risk01_trade or review01_trade outputs are missing, output `action: "NO_SIMULATION_CREATED"`
with explanation.
```

- [ ] **Step 7: Create 437_TRADE_SCORE01.md**

Write file `docs/governance-templates-v2/437_TRADE_SCORE01.md`:

```markdown
# 437 — TRADE_SCORE01

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **score01_trade** (Outcome Scorer) in the DPMtF `trade_cockpit_scoring_v001` flow.
You evaluate open simulated trades after a time horizon has passed.

## When You Are Active

- Periodically (weekly or manually triggered) in the `trade_cockpit_scoring_v001` flow.
- You read existing simulated trades from the trade-ui database via the inbox.

## Model Configuration

| Field | Value |
|-------|-------|
| model_type | ollama |
| ollama_model | qwen3.6:27b-q4_K_M |

## Output Contract

You produce a JSON file written to `/home/svend/trade-ui/inbox/pending/`.

Required wrapper:
```json
{
  "flow_run_id": "<generated>",
  "flow_key": "trade_cockpit_scoring_v001",
  "role_key": "score01_trade",
  "model_name": "qwen3.6:27b-q4_K_M",
  "created_at": "<ISO-8601 with timezone>",
  "output_type": "score_result",
  "status": "completed",
  "payload": { ... }
}
```

Payload fields (per GATES.md §12.3):
- `simulated_trade_id`: ID of the trade being scored
- `scored_at`: ISO-8601 timestamp
- `horizon`: one of 1h, 1d, 3d, 1w, 1m
- `price_at_score`: current price
- `pnl_pct`: P/L percentage
- `max_drawdown_pct`: max drawdown since open
- `max_runup_pct`: max runup since open
- `stop_loss_hit`: true/false
- `take_profit_hit`: true/false
- `decision_quality_score`: 0-100 how good was the original decision?

## Allowed Scoring Horizons (GATES.md §12.2)

- `1h`, `1d`, `3d`, `1w`, `1m`

## Forbidden Actions

- Do NOT create new trade candidates
- Do NOT override risk or review decisions
- Do NOT output `broker_order`
- Score existing trades only — do not modify them

## Escalation

If no open simulated trades exist, output `status: "needs_more_data"` with explanation.
```

- [ ] **Step 8: Create 438_TRADE_LEARN01.md**

Write file `docs/governance-templates-v2/438_TRADE_LEARN01.md`:

```markdown
# 438 — TRADE_LEARN01

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **learn01_trade** (Learning Extractor) in the DPMtF `trade_cockpit_scoring_v001` flow.
You turn scored outcomes into reusable lessons and proposed rule changes.

## When You Are Active

- After score01_trade has produced its `score_result` output(s).
- You read score results from the trade-ui inbox.

## Model Configuration

| Field | Value |
|-------|-------|
| model_type | ollama |
| ollama_model | qwen3.6:27b-q4_K_M |

## Output Contract

You produce a JSON file written to `/home/svend/trade-ui/inbox/pending/`.

Required wrapper:
```json
{
  "flow_run_id": "<same as score01>",
  "flow_key": "trade_cockpit_scoring_v001",
  "role_key": "learn01_trade",
  "model_name": "qwen3.6:27b-q4_K_M",
  "created_at": "<ISO-8601 with timezone>",
  "output_type": "learning_log_entry",
  "status": "completed",
  "payload": { ... }
}
```

Payload fields (per GATES.md §13.1):
- `lesson_type`: category of lesson
- `lesson`: the lesson learned
- `severity`: low/medium/high/critical
- `suggested_rule_change`: proposed governance change (optional)
- `symbol`: related symbol (optional)
- `flow_run_id`: related flow run (optional)

## No Automatic Rule Change (GATES.md §13.2)

You may propose rule changes but MUST NOT activate them automatically.
Any rule change must be marked `accepted_by_user = 0` until the Human explicitly approves.

## Forbidden Actions

- Do NOT activate rule changes automatically
- Do NOT output `broker_order`, `real_trade`
- Do NOT override risk or review decisions
- Do NOT create new trades

## Escalation

If score01_trade output is missing, output `status: "needs_more_data"`.
```

- [ ] **Step 9: Create 439_TRADE_HUMAN.md**

Write file `docs/governance-templates-v2/439_TRADE_HUMAN.md`:

```markdown
# 439 — TRADE_HUMAN

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **humantrade** (Human) in the DPMtF trade flows. You are the flow initiator and
the endpoint for all trade cockpit outputs.

## When You Are Active

- **Flow initiation:** You (or a cronjob) start `trade_cockpit_simulation_v001` by dispatching
  from humantrade to trend01_trade. The dispatch system skips tmux injection for human roles
  and starts the first agent role directly.
- **Flow initiation:** You (or a cronjob) start `trade_cockpit_scoring_v001` by dispatching
  from humantrade to score01_trade.
- **Review:** You review trade outputs in the Trade Cockpit WebUI (port 9140).

## Scope Authority

- You approve or reject proposed rule changes from learn01_trade
- You configure cronjob schedules
- You set the prompt template for daily trend scans
- You decide when to run the scoring flow

## Flows

| Flow | Your Role |
|------|-----------|
| `trade_cockpit_simulation_v001` | Initiator (human → trend01_trade) |
| `trade_cockpit_scoring_v001` | Initiator (human → score01_trade) |

## Cronjob Initiation

```bash
# Daily simulation flow (weekdays 08:57)
57 8 * * 1-5 cd /home/svend/DPMtF-WebUI && python3 scripts/bridgeV002/dispatch.py \
  --db-flow trade_cockpit_simulation_v001 \
  --signal-send \
  --from-role humantrade \
  --to-role trend01_trade

# Weekly scoring flow (Sundays 18:00)
0 18 * * 0 cd /home/svend/DPMtF-WebUI && python3 scripts/bridgeV002/dispatch.py \
  --db-flow trade_cockpit_scoring_v001 \
  --signal-send \
  --from-role humantrade \
  --to-role score01_trade
```

## Constraints

- SIMULATION_ONLY = TRUE — never enable real trading without explicit approval
- All rule changes from learn01_trade require your explicit approval
- Review trade-ui dashboard regularly to monitor simulation results
```

- [ ] **Step 10: Verify all 9 governance files exist**

Run: `ls -la docs/governance-templates-v2/43[1-9]_TRADE_*.md`
Expected: 9 files listed

---

### Task 7: Validation and verification

**Files:**
- Verify: `app.py`, all governance files, database state

- [ ] **Step 1: Backend syntax check**

Run: `python3 -m py_compile app.py`
Expected: No output (clean compile)

- [ ] **Step 2: Verify all flows via API**

Run:
```bash
echo "=== Flows ===" && curl -s http://127.0.0.1:9130/api/bridge-v2/flows | python3 -c "import sys,json; [print(f'  {f[\"flow_key\"]}: {f[\"name\"]}') for f in json.load(sys.stdin)['flows']]"
echo "=== Flow 1 Steps ===" && curl -s http://127.0.0.1:9130/api/bridge-v2/steps/trade_cockpit_simulation_v001 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  {d[\"count\"]} steps, flow_key={d[\"flow_key\"]}')"
echo "=== Flow 2 Steps ===" && curl -s http://127.0.0.1:9130/api/bridge-v2/steps/trade_cockpit_scoring_v001 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  {d[\"count\"]} steps, flow_key={d[\"flow_key\"]}')"
echo "=== Trade Roles ===" && curl -s http://127.0.0.1:9130/api/bridge-v2/roles | python3 -c "import sys,json; roles=[r for r in json.load(sys.stdin)['roles'] if 'trade' in r['role_key'] or r['role_key']=='humantrade']; print(f'  {len(roles)} roles'); [print(f'    {r[\"role_key\"]:20s} type={r[\"role_type\"]:6s} model={r[\"model_type\"]:6s} gov={r[\"governance_file\"]}') for r in sorted(roles, key=lambda x: x['role_key'])]"
echo "=== json_output convention ===" && curl -s http://127.0.0.1:9130/api/bridge-v2/conventions | python3 -c "import sys,json; c=next((c for c in json.load(sys.stdin)['conventions'] if c['rule_key']=='json_output'), None); print(f'  rule_key={c[\"rule_key\"]}, step_type={c[\"step_type\"]}, dir={c[\"dir_template\"]}') if c else print('  NOT FOUND')"
```
Expected: All checks pass with correct counts

- [ ] **Step 3: Verify trade-ui is ready to receive JSON**

Run: `curl -s http://127.0.0.1:9140/api/setup | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  pending dir: {d[\"import_paths\"][\"pending\"]}'); print(f'  allowed roles: {len(d[\"allowed_roles\"])}'); print(f'  allowed output_types: {len(d[\"allowed_output_types\"])}')"`
Expected:
```
  pending dir: /home/svend/trade-ui/inbox/pending
  allowed roles: 8
  allowed output_types: 9
```

- [ ] **Step 4: Verify governance file count**

Run: `ls docs/governance-templates-v2/43[1-9]_TRADE_*.md | wc -l`
Expected: `9`

- [ ] **Step 5: innerHTML check**

Run: `grep -RIn "innerHTML" static/ templates/`
Expected: No output (or only comments mentioning "no innerHTML")

- [ ] **Step 6: Hardcoded paths check**

Run: `grep -n '"/home/svend' app.py scripts/`
Expected: No output

---

### Task 8: Configure cronjob for Flow 1

**Files:**
- Modify: User's crontab

**Note:** This step requires Human approval before execution. The cronjob will start
dispatching the trade flow automatically on weekdays.

- [ ] **Step 1: Show the proposed crontab entry to Human**

The proposed entry:
```
57 8 * * 1-5 cd /home/svend/DPMtF-WebUI && python3 scripts/bridgeV002/dispatch.py --db-flow trade_cockpit_simulation_v001 --signal-send --from-role humantrade --to-role trend01_trade
```

- [ ] **Step 2: After Human approval, add to crontab**

Run: `(crontab -l 2>/dev/null; echo "57 8 * * 1-5 cd /home/svend/DPMtF-WebUI && python3 scripts/bridgeV002/dispatch.py --db-flow trade_cockpit_simulation_v001 --signal-send --from-role humantrade --to-role trend01_trade") | crontab -`

- [ ] **Step 3: Verify crontab entry**

Run: `crontab -l | grep trade_cockpit`
Expected: The cron line is present

---

### Task 9: Manual smoke test of Flow 1

**Files:**
- Test: `trade_cockpit_simulation_v001` flow via dispatch

**Note:** This is a manual test to verify the dispatch mechanism works end-to-end
for the first step (human → trend01_trade). Full chain testing requires all Ollama
models to be available.

- [ ] **Step 1: Verify trend01_trade Ollama model is available**

Run: `curl -s http://127.0.0.1:11434/api/tags | python3 -c "import sys,json; models=[m['name'] for m in json.load(sys.stdin)['models']]; print('qwen3.6:35b-a3b-64k available:', 'qwen3.6:35b-a3b-64k' in models)"`
Expected: `qwen3.6:35b-a3b-64k available: True`

- [ ] **Step 2: Run a test dispatch (dry-run or with Human supervision)**

Run:
```bash
python3 scripts/bridgeV002/dispatch.py \
  --db-flow trade_cockpit_simulation_v001 \
  --signal-send \
  --from-role humantrade \
  --to-role trend01_trade
```
Expected: Dispatch completes without errors. Check output for the generated flow_run_id.

- [ ] **Step 3: Verify the JSON output file was created**

Run: `ls -la /home/svend/trade-ui/inbox/pending/ | grep trend01_trade`
Expected: At least one `.json` file with `trend01_trade` in the name

- [ ] **Step 4: Run trade-ui import to process the file**

Run: `cd /home/svend/trade-ui && source .venv/bin/activate && python3 scripts/import_flow_output.py`
Expected: Import summary shows the file was imported (or skipped if duplicate)

- [ ] **Step 5: Verify the output appears in trade-ui**

Run: `curl -s "http://127.0.0.1:9140/api/journals/role-outputs?page=1&page_size=5" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Total: {d[\"total\"]}'); [print(f'  {i[\"role_key\"]}: {i[\"output_type\"]} ({i[\"status\"]})') for i in d['items'][:5]]"`
Expected: The new trend01_trade output appears in the list

---

### Task 10: Final diff review

**Files:**
- Review: `git diff --stat`

- [ ] **Step 1: Show all changes**

Run: `git diff --stat`
Expected: Only expected files changed:
```
app.py                                    (modified — POST /conventions endpoint)
docs/governance-templates-v2/431_TRADE_TREND01.md   (new)
docs/governance-templates-v2/432_TRADE_MARKET01.md  (new)
docs/governance-templates-v2/433_TRADE_ANALYST01.md (new)
docs/governance-templates-v2/434_TRADE_RISK01.md    (new)
docs/governance-templates-v2/435_TRADE_REVIEW01.md  (new)
docs/governance-templates-v2/436_TRADE_SIM01.md     (new)
docs/governance-templates-v2/437_TRADE_SCORE01.md   (new)
docs/governance-templates-v2/438_TRADE_LEARN01.md   (new)
docs/governance-templates-v2/439_TRADE_HUMAN.md     (new)
```

- [ ] **Step 2: Verify no unexpected files**

Run: `git diff --stat | grep -v "governance-templates-v2/43" | grep -v "app.py" | grep -v "docs/superpowers"`
Expected: No output (only the expected files)

---
