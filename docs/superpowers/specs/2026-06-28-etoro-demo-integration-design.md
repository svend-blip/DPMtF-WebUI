# Design Spec: eToro Demo Account Integration

> **Status:** Draft — awaiting approval
> **Date:** 2026-06-28
> **Scope:** Connect trade-ui to eToro demo API for simulated→demo trade execution

## 1. Purpose

Bridge the gap between DPMtF's fully simulated trade flow and eToro's demo
trading platform. When sim01_trade outputs `SIMULATED_BUY` or `SIMULATED_SELL`,
the system can optionally execute the corresponding trade on eToro's demo
account — using real market prices but virtual money.

This is NOT real trading. eToro demo accounts use virtual funds. The integration
is a learning tool to validate that DPMtF's trade decisions would execute
correctly in a live environment.

## 2. Architecture

```
DPMtF sim01_trade → JSON → trade-ui inbox → import → SQLite
                                                    ↓
                                          [NEW] eToro Bridge
                                                    ↓
                                          eToro Demo API
                                                    ↓
                                          Demo account positions
                                                    ↓
                                          [NEW] Sync back to SQLite
                                                    ↓
                                          WebUI display
```

### 2.1 New Component: eToro Bridge

A Python module `scripts/etoro_bridge.py` that:
1. Reads `simulated_trade` records with `status=open` and no linked eToro order
2. Translates them to eToro API calls (demo endpoint only)
3. Records the eToro order ID and position ID back to the database
4. Periodically syncs position status (P/L, stop loss hits, etc.)

### 2.2 Database Changes

New table `etoro_orders`:
```sql
CREATE TABLE etoro_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    raw_response_json TEXT,
    FOREIGN KEY(simulated_trade_id) REFERENCES simulated_trades(id)
);
```

New columns in `simulated_trades`:
- `etoro_order_id` TEXT — linked eToro order
- `etoro_position_id` TEXT — linked eToro position
- `execution_mode` TEXT DEFAULT 'simulation_only' — 'simulation_only' | 'etoro_demo'

### 2.3 Safety Architecture

```
┌─────────────────────────────────────────┐
│         HARD SAFETY GATES               │
│                                         │
│  1. ETORO_DEMO_ONLY = TRUE (hardcoded)  │
│  2. API base URL locked to /demo/ path  │
│  3. No live API key accepted            │
│  4. Max position size: $1000/demo trade │
│  5. Max daily trades: 5                 │
│  6. Human approval required per trade   │
│  7. Kill switch: disable via .env       │
└─────────────────────────────────────────┘
```

## 3. eToro API Endpoints Used

Base URL: `https://public-api.etoro.com`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v2/trading/execution/demo/orders` | POST | Open demo position |
| `/api/v1/trading/execution/demo/market-close-orders/positions/{id}` | POST | Close demo position |
| `/api/v1/trading/info/demo/portfolio` | GET | Get portfolio + positions |
| `/api/v1/market-data/search?search={symbol}` | GET | Search instrument ID |

Auth headers on every request:
- `x-api-key` — public API key
- `x-user-key` — user-specific key
- `x-request-id` — unique UUID per request

## 4. New API Endpoints in trade-ui

### 4.1 eToro Status
```
GET /api/etoro/status
```
Returns: demo account balance, equity, open positions count, P/L summary.

### 4.2 Execute Demo Trade
```
POST /api/etoro/execute-trade
Body: {"simulated_trade_id": 42}
```
Reads the simulated_trade, validates all safety gates, places the order on eToro demo.
Returns: `{"order_id": "13902598", "status": "executed"}`

### 4.3 Sync Positions
```
POST /api/etoro/sync-positions
```
Fetches current demo positions from eToro, updates `simulated_trades` status
(open → closed if position closed), updates P/L.

### 4.4 Close Position
```
POST /api/etoro/close-position
Body: {"simulated_trade_id": 42}
```
Closes the linked eToro demo position.

## 5. Safety Gates (Hard-Enforced)

### 5.1 Demo-Only Enforcement
```python
ETORO_BASE_URL = "https://public-api.etoro.com"
ETORO_DEMO_ONLY = True  # NEVER change to False without explicit approval
ETORO_ORDER_PATH = "/api/v2/trading/execution/demo/orders"  # /demo/ is mandatory

# Auto-reject if /demo/ is not in the URL path
if "/demo/" not in order_url:
    raise SecurityError("DEMO_ONLY: live trading is disabled")
```

### 5.2 Position Limits
```python
MAX_POSITION_SIZE_USD = 1000    # Max $1000 per demo trade
MAX_DAILY_TRADES = 5            # Max 5 trades per day
MAX_LEVERAGE = 1                # No leverage on demo
```

### 5.3 Human Approval Gate
Every trade execution requires explicit Human approval via the WebUI.
The cronjob-based flow produces `simulated_trade` records but does NOT
auto-execute on eToro. Execution is a separate manual step.

### 5.4 Kill Switch
```bash
# .env file
ETORO_API_ENABLED=false  # Set to true to enable
ETORO_API_KEY=your_key_here
ETORO_USER_KEY=your_user_key_here
```

## 6. WebUI Changes

### 6.1 New Panel: eToro Demo (in Daily view)
- Demo account balance and equity
- Open demo positions with P/L
- "Execute on Demo" button next to approved simulated trades
- Execution history

### 6.2 Safety Banner Update
```
SIMULATION_ONLY = TRUE
REAL_ORDERS_DISABLED = TRUE
ETORO_DEMO_ENABLED = TRUE    ← NEW
ETORO_LIVE_DISABLED = TRUE   ← NEW
```

## 7. Configuration

### 7.1 .env additions
```bash
ETORO_API_ENABLED=false
ETORO_API_KEY=
ETORO_USER_KEY=
ETORO_MAX_POSITION_USD=1000
ETORO_MAX_DAILY_TRADES=5
```

### 7.2 config.py additions
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

## 8. Build Phases

### Phase 1: eToro Bridge Core (2-3 dage)
- `scripts/etoro_bridge.py` — API client with demo-only enforcement
- `etoro_orders` table + migration
- `config.py` additions
- Manual test: place a demo order via script

### Phase 2: Trade Execution (1-2 dage)
- `POST /api/etoro/execute-trade` endpoint
- Safety gate validation
- Link simulated_trade → etoro_order
- Manual test: execute a simulated trade on demo

### Phase 3: Sync + Monitoring (1-2 dage)
- `POST /api/etoro/sync-positions` endpoint
- `GET /api/etoro/status` endpoint
- P/L sync back to simulated_trades
- Manual test: sync positions after market movement

### Phase 4: WebUI (1-2 dage)
- eToro Demo panel in Daily view
- Execute button with confirmation dialog
- Position display with P/L
- Safety banner update

### Phase 5: Governance + Testing (1 dag)
- Update SCOPE.md, GATES.md
- Safety gate tests
- Demo-only enforcement tests
- End-to-end test: DPMtF → sim01 → eToro demo → position → sync

## 9. What This Does NOT Cover

- Real eToro trading (live account) — requires separate explicit approval
- Automated execution from cronjob — Human approval gate blocks this
- Leverage trading — hardcoded to 1x
- CFD trading — not supported
- Copy trading — not supported
- Portfolio rebalancing — not supported
- Multiple eToro accounts — single demo account only

## 10. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Accidental live trading | `/demo/` path hardcoded, live API key rejected |
| Excessive losses | Max $1000/position, max 5/day, no leverage |
| API key leak | Keys in .env only, .env in .gitignore |
| Unauthorized execution | Human approval required per trade |
| Rate limiting | Exponential backoff, max 5 trades/day |
