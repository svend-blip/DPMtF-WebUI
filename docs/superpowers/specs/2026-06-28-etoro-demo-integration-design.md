# Design Spec: eToro Demo Account Integration

> **Status:** Approved v4 (2026-07-01)
> **Date:** 2026-06-28 (v1) · 2026-07-01 (v2, v3, v4, approved)
> **Scope:** Connect trade-ui to eToro demo API for simulated→demo trade execution

## 0. Changelog

### v4 — 2026-07-01 (review feedback integrated)

Safety, auditability, and scoring/learning refinements. Adds: unified gate-result
structure (§10), dedicated eligibility endpoint (§7.2), mandatory dry-run with
payload hash (§12), `request_payload_json` snapshot (§5.1), stronger instrument
verification (§5.3, §11), explicit idempotency (§14), scoring distinction
between `simulation_only` and `etoro_demo` (§16), `learn01` recommend-only
constraint (§16), expanded `execution_eligibility` enum (§9), concrete
confirmation text (§15), and the consolidated minimum-gates list (§11).
Renamed `raw_request_json → request_payload_json`; `execution_failed →
execution_error`.

### v3 — 2026-07-01 (optimizations integrated)

Added `execution_eligibility`, `etoro_order_events` audit table,
`etoro_instruments` cache, dry-run Phase 1A/1B split, `/live/` negative check,
expanded `etoro_orders`, WebUI button rules, final architecture rule.

### v2 — 2026-07-01 (amended against `trade_output_v001` JSON standard)

Realigned with the JSON standard: link by `simulation_id`, rename
`simulated_trade → simulation_order`, add Quality Gate, declare the eToro
bridge is NOT a BridgeV002 role, add JSON-standard-migration prerequisite.

### v1 — 2026-06-28 (original)

Initial draft: safety architecture, endpoints, config, build phases.

## 1. Purpose

Bridge the gap between DPMtF's fully simulated trade flow and eToro's demo
trading platform. When sim01_trade outputs `SIMULATED_BUY` or `SIMULATED_SELL`,
the system can optionally execute the corresponding trade on eToro's demo
account — using real market prices but virtual money.

This is NOT real trading. eToro demo accounts use virtual funds. The integration
is a learning tool to validate that DPMtF's trade decisions would execute
correctly in a live environment.

The core principle:

```text
DPMtF producerer beslutningsgrundlag.
trade-ui importerer og viser simulationen.
Mennesket godkender demo-eksekvering.
eToro Bridge udfører kun demo-handlingen.
score01/learn01 evaluerer bagefter.
```

## 1.1 Prerequisites — JSON-Standard Migration

> **Hard prerequisite.** Phase 2 (Execution Endpoint) cannot be built until
> this is satisfied.

The eToro bridge links to simulations via `simulation_id` (§4), a field from the
`trade_output_v001` JSON standard not yet produced by sim01_trade.

Before Phase 2:

1. The Trade Cockpit JSON Standard migration must land — see
   `docs/superpowers/specs/2026-07-01-trade-output-json-standard-migration-design.md`.
2. sim01_trade governance (`436_TRADE_SIM01.md`) must instruct generation of
   `simulation_id` using `SIM-{flow_run_id}-{SYMBOL}-{seq}`.
3. The `simulated_trades` table must carry a `simulation_id TEXT` column.

Phase 1A (Bridge Core Dry-run) and Phase 1B (Instrument Mapping) may proceed
in parallel with the migration tail.

## 2. Architecture — Main Design Retained

```text
trade_cockpit_simulation_v001:  trend01 → market01 → analyst01 → risk01 → review01 → sim01
trade_cockpit_scoring_v001:     score01 → learn01
```

The eToro Bridge is **not** inserted as an extra role step after `sim01`. It
lies outside the role flow:

```text
sim01_trade → simulation_order JSON → trade-ui inbox/import → simulated_trades DB row
  → Human approval → eToro Bridge → eToro Demo API → etoro_orders / etoro_order_events
  → scoring / learning
```

## 3. The eToro Bridge is NOT a BridgeV002 Role

The bridge is not `trend/market/analysis/risk/review/simulation/scoring/learning`
and is not a new `role_stage`. It is a human-triggered trade-ui service that:

- does **not** emit role-output JSON
- does **not** write to the trade-ui inbox
- does **not** participate in either flow chain
- writes execution state to SQLite tables only

## 4. `simulation_id` — Canonical Link, Hard Requirement

`simulation_id` links every layer:

```text
simulation_order JSON · simulated_trades · etoro_orders · etoro_order_events
score01_trade · learn01_trade · frontend audit view
```

Convention: `SIM-{flow_run_id}-{SYMBOL}-{seq}` (e.g. `SIM-030-TSM-001`).

**Hard rule:** no eToro dry-run or demo execution without `simulation_id`.
If missing → `execution_eligibility = blocked_by_missing_simulation_id`.

## 5. Database Schema

### 5.1 `etoro_orders`

```sql
CREATE TABLE IF NOT EXISTS etoro_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id TEXT NOT NULL,
    simulated_trade_id INTEGER NOT NULL,
    etoro_order_id TEXT,
    etoro_position_id TEXT,
    instrument_id INTEGER,
    action TEXT NOT NULL,
    amount_usd REAL NOT NULL,
    leverage INTEGER DEFAULT 1,
    stop_loss_rate REAL,
    take_profit_rate REAL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    executed_at TEXT,
    error_message TEXT,
    request_payload_json TEXT,   -- what we actually sent
    raw_response_json TEXT,      -- what eToro answered
    FOREIGN KEY(simulated_trade_id) REFERENCES simulated_trades(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_etoro_orders_simulation_id ON etoro_orders(simulation_id);
CREATE INDEX IF NOT EXISTS idx_etoro_orders_status ON etoro_orders(status);
```

`status`: `draft · dry_run_ready · pending_human_approval · submitted · executed
· rejected · open · closed · failed`.

> `request_payload_json` + `raw_response_json` together give "what did we send?"
> and "what did eToro answer?" — essential for audit/debugging.

### 5.2 `etoro_order_events` (audit timeline)

```sql
CREATE TABLE IF NOT EXISTS etoro_order_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id TEXT NOT NULL,
    etoro_order_id TEXT,
    etoro_position_id TEXT,
    event_type TEXT NOT NULL,
    event_time TEXT NOT NULL,
    message TEXT,
    raw_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_etoro_order_events_simulation_id
ON etoro_order_events(simulation_id);
CREATE INDEX IF NOT EXISTS idx_etoro_order_events_event_time
ON etoro_order_events(event_time);
```

`event_type`: `execution_requested · preflight_started · risk_gate_passed ·
review_gate_passed · quality_gate_passed · instrument_resolved · payload_built ·
dry_run_passed · dry_run_hash_mismatch · order_sent · order_accepted ·
order_rejected · already_executed · sync_started · sync_seen_open ·
sync_seen_closed · manual_close_requested · close_sent · close_accepted ·
sync_error · execution_error`.

### 5.3 `etoro_instruments` (verified mapping cache)

```sql
CREATE TABLE IF NOT EXISTS etoro_instruments (
    symbol TEXT PRIMARY KEY,
    etoro_instrument_id INTEGER NOT NULL,
    etoro_display_name TEXT,
    asset_type TEXT,
    exchange TEXT,
    currency TEXT,
    is_demo_tradeable INTEGER DEFAULT 0,
    last_verified_at TEXT,
    raw_json TEXT
);
```

Resolution + verification:

```text
If no mapping exists:
  search eToro instrument API
  if exactly one high-confidence match:
    cache it (incl. is_demo_tradeable)
  else:
    block execution; ask Human to resolve mapping
Execution gate requires:
  instrument_mapped == true
  is_demo_tradeable == true
  last_verified_at is not too old
If unverifiable → execution_eligibility = blocked_by_missing_instrument
```

### 5.4 `simulated_trades` — new columns

```sql
ALTER TABLE simulated_trades ADD COLUMN simulation_id TEXT;
ALTER TABLE simulated_trades ADD COLUMN etoro_order_id TEXT;
ALTER TABLE simulated_trades ADD COLUMN etoro_position_id TEXT;
ALTER TABLE simulated_trades ADD COLUMN execution_mode TEXT DEFAULT 'simulation_only';
ALTER TABLE simulated_trades ADD COLUMN execution_eligibility TEXT DEFAULT 'not_reviewed';
ALTER TABLE simulated_trades ADD COLUMN last_dry_run_at TEXT;
ALTER TABLE simulated_trades ADD COLUMN last_dry_run_hash TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_simulated_trades_simulation_id
ON simulated_trades(simulation_id);
```

- `simulation_id` — canonical cross-flow identifier (mirrored from sim01 output).
- `execution_eligibility` — whether the WebUI may expose Execute Demo (§9).
- `execution_mode` — where executed (`simulation_only` | `etoro_demo`); mutable
  state set on Human click, DB-only, never in immutable role-output payload.
- `last_dry_run_at` / `last_dry_run_hash` — mandatory dry-run trail (§12).

## 6. eToro API Endpoints Used

Base URL: `https://public-api.etoro.com`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v2/trading/execution/demo/orders` | POST | Open demo position |
| `/api/v1/trading/execution/demo/market-close-orders/positions/{id}` | POST | Close demo position |
| `/api/v1/trading/info/demo/portfolio` | GET | Get portfolio + positions |
| `/api/v1/market-data/search?search={symbol}` | GET | Search instrument ID |

Auth headers on every request: `x-api-key`, `x-user-key`, `x-request-id` (UUID).

## 7. trade-ui API Endpoints

```text
GET  /api/etoro/status
GET  /api/etoro/execution-eligibility/{simulation_id}
POST /api/etoro/dry-run-execute-trade
POST /api/etoro/execute-trade
POST /api/etoro/sync-positions
POST /api/etoro/close-position
GET  /api/etoro/order-events/{simulation_id}
```

Recommended order: `eligibility → dry-run → human approval → execute → sync → scoring`.

### 7.1 `GET /api/etoro/status`
Demo balance, equity, open positions count, P/L summary.

### 7.2 `GET /api/etoro/execution-eligibility/{simulation_id}` — NEW (v4)
Returns the unified gate-result (§10): `eligible`, `blocked_reason`, per-gate
booleans, `warnings`, and a recommended next action. Dry-run should only be
called once eligibility is positive.

### 7.3 `POST /api/etoro/dry-run-execute-trade` — NEW (v4)
```json
{"simulation_id": "SIM-030-TSM-001"}
```
Builds the order payload, validates all gates, hashes the payload, stores
`last_dry_run_at` + `last_dry_run_hash`, logs `dry_run_passed`. **Sends no order
to eToro.** Returns the proposed payload + hash.

### 7.4 `POST /api/etoro/execute-trade`
```json
{"simulation_id": "SIM-030-TSM-001"}
```
Rebuilds the payload, re-hashes, compares to `last_dry_run_hash` (§12), then
places the order on eToro demo. Returns `{"order_id": "13902598", "status": "executed"}`.

### 7.5 `POST /api/etoro/sync-positions`
Fetches current demo positions; updates `simulated_trades` (open→closed), P/L;
logs `sync_*` events.

### 7.6 `POST /api/etoro/close-position`
```json
{"simulation_id": "SIM-030-TSM-001"}
```
Closes the linked eToro demo position.

### 7.7 `GET /api/etoro/order-events/{simulation_id}` — NEW (v4)
Returns the `etoro_order_events` timeline for a simulation (UI audit view).

## 8. Safety Gates (Hard-Enforced)

### 8.1 Demo-Only Enforcement
```python
ETORO_BASE_URL = "https://public-api.etoro.com"
ETORO_DEMO_ONLY = True       # NEVER False without explicit approval
ETORO_ORDER_PATH = "/api/v2/trading/execution/demo/orders"

if "/demo/" not in order_url:
    raise SecurityError("DEMO_ONLY: live trading is disabled")
if "/live/" in order_url:                      # v3 negative check
    raise SecurityError("LIVE_PATH_BLOCKED: live trading path detected")
```
Config must not allow live base paths. The only permitted execution endpoint is
demo.

### 8.2 Position Limits
```python
MAX_POSITION_SIZE_USD = 1000
MAX_DAILY_TRADES = 5
MAX_LEVERAGE = 1
```

### 8.3 Human Approval + No-Auto-Execution
```text
ETORO_LIVE_DISABLED = true      # live impossible
AUTO_EXECUTION_DISABLED = true  # cronjobs may never execute demo trades
```
Cronjobs may create `simulation_order`; only Human WebUI action may execute on
eToro demo.

### 8.4 Kill Switch
```bash
ETORO_API_ENABLED=false  # true to enable
ETORO_API_KEY=...
ETORO_USER_KEY=...
```

## 9. Execution Eligibility Model

Two separate concepts (do not use `status=open` alone as execution permission):

```text
simulation_status     = trade/simulation lifecycle  (the existing simulated_trades.status column)
execution_eligibility = whether WebUI may expose Execute Demo
```

`execution_eligibility` values:

```text
not_reviewed · eligible · blocked_by_risk · blocked_by_review
blocked_by_quality · blocked_by_missing_data · blocked_by_missing_simulation_id
blocked_by_missing_instrument · executed_demo · closed_demo · execution_error
```

Examples:

```text
simulation_status=open · execution_eligibility=eligible       → may execute after Human approval
simulation_status=open · execution_eligibility=blocked_by_quality → must not execute
simulation_status=closed · execution_eligibility=closed_demo  → already executed & closed
```

## 10. Unified Gate-Result Structure — NEW (v4)

`GET /execution-eligibility` (and dry-run preflight) return one object so the
frontend can show exactly why Execute is disabled, the backend can test gates in
isolation, and the audit log can store the full result.

Eligible:
```json
{
  "simulation_id": "SIM-030-TSM-001",
  "eligible": true,
  "blocked_reason": null,
  "gates": {
    "simulation_id_present": true,
    "simulation_order_exists": true,
    "risk_approved": true,
    "review_approved": true,
    "quality_ok": true,
    "instrument_mapped": true,
    "instrument_demo_tradeable": true,
    "position_size_ok": true,
    "daily_trade_limit_ok": true,
    "demo_api_enabled": true,
    "demo_url_verified": true,
    "live_disabled": true,
    "auto_execution_disabled": true,
    "leverage_ok": true,
    "no_existing_order": true,
    "human_approval_required": true
  },
  "warnings": []
}
```

Blocked:
```json
{
  "simulation_id": "SIM-030-TSM-001",
  "eligible": false,
  "blocked_reason": "blocked_by_quality",
  "gates": { "quality_ok": false },
  "warnings": ["quality.data_quality is low"]
}
```

## 11. Minimum Gates for Demo Execution

Demo execution is allowed only if **all** hold:

```text
ETORO_API_ENABLED == true
ETORO_DEMO_ONLY == true
ETORO_LIVE_DISABLED == true
AUTO_EXECUTION_DISABLED == true
endpoint contains /demo/  (and no /live/)
simulation_id exists
simulation_order exists
simulation action is SIMULATED_BUY or SIMULATED_SELL
risk01 risk_decision == APPROVE_SIMULATION
review01 verdict == APPROVED
quality.data_quality != low
quality.confidence is null or >= 0.4
execution_eligibility == eligible
instrument_id exists and is_demo_tradeable == true
position size <= max position size
daily trade count < max daily trades
leverage == 1
dry-run passed
dry-run payload hash == execution payload hash
no existing etoro_order for simulation_id
Human approval confirmed
```

If any gate fails: no eToro API call; an audit event is written; the frontend
shows the blocked reason.

## 12. Mandatory Dry-Run with Payload Hash — NEW (v4)

Demo execution may not be called directly without a passed dry-run.

```text
1. POST /dry-run-execute-trade builds the order payload, hashes it, stores
   last_dry_run_at + last_dry_run_hash, logs dry_run_passed. No order sent.
2. POST /execute-trade rebuilds the payload, re-hashes, and compares to
   last_dry_run_hash.
3. If the hash differs (payload drifted) → block, log dry_run_hash_mismatch,
   require a new dry-run.
```

This prevents "dry-run one order, accidentally send another."

`last_dry_run_hash = sha256(canonical_order_payload_json)`.

## 13. Quality Gate

```python
quality = sim_output.get("quality", {})
data_quality = quality.get("data_quality", "unknown")
confidence = quality.get("confidence")
if data_quality == "low":
    raise SecurityError("QUALITY_GATE: data_quality is low")
if confidence is not None and confidence < 0.4:
    raise SecurityError("QUALITY_GATE: confidence below 0.4")
```

Behavior: `high/medium → allow`; `unknown → allow with warning`; `low → block`;
missing confidence → allow with warning; `confidence < 0.4 → block`. Warnings
written to `etoro_order_events`. Threshold `0.4` is an initial default (§16:
`learn01` may recommend tuning it; only Human may change it).

## 14. Idempotency — Double-Execution Prevention

The unique index on `etoro_orders.simulation_id` makes two orders for the same
simulation impossible. Make it explicit in the backend:

```text
If an etoro_orders row already exists for simulation_id:
  Execute must NOT send a new order.
  Return {"status": "already_executed", "etoro_order_id": "<existing>"}.
  Log the already_executed event.
```

This protects against frontend double-clicks.

## 15. WebUI Behavior

Per simulation in the Daily view, show:

```text
Simulation ID · Symbol · Action · Entry · Stop loss · Take profit · Risk/reward
Risk verdict · Review verdict · Quality status · Execution eligibility
Blocked reason · Dry-run status · eToro order status · Audit events
```

Buttons: `Check Eligibility · Dry-run · Execute DEMO Trade · Sync Position ·
Close DEMO Position · View Audit Events`.

Button rules:

```text
Dry-run enabled only if eligibility == true.
Execute enabled only if dry-run passed and payload hash still matches.
Close enabled only if an eToro demo position is open.
```

Confirmation dialog (concrete, not a generic "Are you sure?"):

```text
You are about to execute a DEMO trade only.

Simulation ID: SIM-030-TSM-001
Symbol: TSM
Action: SIMULATED_BUY
Amount: $1000
Leverage: 1x
Stop loss: 418.00
Take profit: 520.00

This will NOT place a live trade.
This will use eToro demo only.
```

The user must confirm with the explicit button label `Execute DEMO trade`
(not a generic `OK`).

## 16. Scoring & Learning Requirements — NEW (v4)

### 16.1 score01 must distinguish execution modes
`score01_trade` may evaluate both `simulation_only` and `etoro_demo` outcomes,
but must mark which type it scores. Scoring input:

```json
{
  "simulation_id": "SIM-030-TSM-001",
  "execution_mode": "etoro_demo",
  "simulation_status": "closed",
  "demo_execution": {
    "etoro_order_id": "13902598",
    "etoro_position_id": "998877",
    "executed_at": "2026-07-01T14:10:00+02:00",
    "closed_at": null,
    "realized_pl_usd": null,
    "unrealized_pl_usd": 42.5
  }
}
```

### 16.2 learn01 may recommend gate changes — never execute them
`learn01_trade` may recommend changes such as:

```text
- raise confidence threshold from 0.4 to 0.5
- reduce max demo position from $1000 to $500
- block data_quality == unknown after the first 20 runs
```

It must **not** directly change `ETORO_MAX_POSITION_USD`,
`ETORO_MAX_DAILY_TRADES`, quality thresholds, or execution gates. All threshold
changes are Human-approved governance changes (per GATES §13.2
No-Automatic-Rule-Change Gate).

## 17. Configuration

### 17.1 `.env` additions
```bash
ETORO_API_ENABLED=false
ETORO_API_KEY=
ETORO_USER_KEY=
ETORO_MAX_POSITION_USD=1000
ETORO_MAX_DAILY_TRADES=5
```

### 17.2 `config.py` additions
```python
def get_etoro_api_enabled() -> bool:
    return os.getenv("ETORO_API_ENABLED", "false").lower() == "true"
def get_etoro_api_key() -> str:
    return os.getenv("ETORO_API_KEY", "")
def get_etoro_user_key() -> str:
    return os.getenv("ETORO_USER_KEY", "")
def get_etoro_max_position_usd() -> int:
    return int(os.getenv("ETORO_MAX_POSITION_USD", "1000"))
def get_etoro_max_daily_trades() -> int:
    return int(os.getenv("ETORO_MAX_DAILY_TRADES", "5"))
```

`ETORO_DEMO_ONLY`, `ETORO_LIVE_DISABLED`, and `AUTO_EXECUTION_DISABLED` are
hardcoded `True` constants in the bridge module (not env-overridable) — they
are invariants, not configuration.

## 18. Build Phases

### Phase 1A — Bridge Core Dry-run
Build: `scripts/etoro_bridge.py`, config additions, `etoro_orders` /
`etoro_order_events` / `etoro_instruments` tables, dry-run payload builder,
demo-only endpoint validation, eligibility gate evaluator (§10).
Verify: load config; reject disabled API; reject non-demo and `/live/` paths;
resolve `simulation_id`; build payload; write audit events; **no order sent**.

### Phase 1B — Instrument Mapping
Build: symbol→eToro instrument search, `etoro_instruments` cache, ambiguous
mapping block, manual mapping path.
Verify: TSM/NVDA map; BTC-USD maps or blocks safely; ambiguous mappings do not
execute; `is_demo_tradeable` enforced.

### Phase 2 — Execution Endpoint — blocked until §1.1
Build: `POST /dry-run-execute-trade` + `POST /execute-trade`, `simulation_id`
lookup, all gates (§11), dry-run hash compare (§12), idempotency (§14), human
approval handling, `etoro_orders` insert, `etoro_order_events` timeline.
Verify: approved simulation executes; blocked/low-quality/missing-review cannot;
duplicate `simulation_id` returns `already_executed`; hash mismatch blocks.

### Phase 3 — Sync + Monitoring
Build: `POST /sync-positions`, `GET /status`, position sync, P/L sync, closed
detection, `GET /order-events/{simulation_id}`.
Verify: open position appears; closed updates `simulated_trades`; P/L visible;
sync errors logged.

### Phase 4 — WebUI
Build: eToro Demo panel, per-simulation display (§15), button rules,
confirmation dialog, safety banner, execution timeline.
Verify: buttons follow rules; blocked trades show reason; banner visible;
events visible per simulation.

### Phase 5 — Governance + Tests
Update: `SCOPE.md`, `GATES.md`, JSON-standard references, `sim01`/`review01`/
`risk01` governance, `score01`/`learn01` governance (§16).
Tests: demo-only + `/live/` rejection, quality/risk/review gates, duplicate
prevention, daily limit, position size, instrument ambiguity, dry-run no-send,
dry-run hash mismatch, sync update, idempotency.

## 19. What This Does NOT Cover

- Real eToro trading (live account) — separate explicit approval required.
- Automated execution from cronjob — blocked by `AUTO_EXECUTION_DISABLED` + Human gate.
- Leverage (>1x), CFD, copy trading, portfolio rebalancing, multiple eToro accounts.
- Historical backfill of pre-standard runs.
- Automatic threshold changes by `learn01` (§16.2).

## 20. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Accidental live trading | `/demo/` hardcoded + `/live/` negative check; live key rejected; `ETORO_LIVE_DISABLED` invariant |
| Excessive losses | Max $1000/position, max 5/day, leverage 1x |
| API key leak | .env only; .env in .gitignore |
| Unauthorized execution | Human approval per trade; `AUTO_EXECUTION_DISABLED`; cronjobs cannot execute |
| Weak-data execution | §13 Quality Gate |
| Payload drift dry-run→execute | §12 mandatory dry-run + `last_dry_run_hash` compare |
| Double execution | §14 unique index + `already_executed` response |
| Ambiguous symbol mapping | §5.3 cache blocks on non-unique match |
| Silent execution failures | §5.2 `etoro_order_events` timeline + gate-result audit |
| Scoring mode confusion | §16.1 score01 marks `execution_mode` per result |
| Runaway threshold changes | §16.2 learn01 recommend-only |

## 21. Final Architecture Rule

```text
DPMtF roles decide.
sim01 simulates.
Human approves demo execution.
eToro Bridge executes demo only.
SQLite records execution state.
score01 evaluates outcomes (marking execution_mode).
learn01 improves future flow (recommend-only).
```

- No cronjob may execute eToro demo orders automatically.
- No role-output JSON may be mutated after creation to reflect execution.
- No live eToro execution is allowed in this design.
- No dry-run may be skipped before execution.

The system remains:

```text
simulation-first · human-gated · demo-only · auditable · learning-compatible
```
