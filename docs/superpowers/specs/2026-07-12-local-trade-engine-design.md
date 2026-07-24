# Local Trade Engine — Design Specification

> **Status:** Design approved — awaiting implementation plan
> **Date:** 2026-07-12
> **Repository:** https://github.com/svend-blip/Local-Trade-Engine.git
> **Language:** en-US

## 0. Executive Summary

Local Trade Engine is a lightweight, local-first trading decision and execution system that replaces code-oriented agent interfaces (Claude Code, OpenCode) with a deterministic Python orchestration layer. The system calls a fixed sequence of local Ollama models, combines their outputs with market data and deterministic calculations, and produces structured buy/sell/hold/reduce/close decisions.

V1 executes against an eToro Virtual Account. The frontend must clearly and persistently show that the system is connected to and trading through a virtual account. The system must not present virtual profits, losses, positions, balances, or orders as real-money results.

**Core principle:** Use language models only for tasks that require interpretation, synthesis, classification, or judgment. Use deterministic Python for everything else.

---

## 1. Five Highest-Leverage Optimizations (from Trade-UI Hardening)

These five optimizations are derived from the Trade-UI hardening phases (flows 065-072) and are built into Local Trade Engine from the start:

### 1. Eliminate Coding-Agent Runtime
**Trade-UI problem:** Claude Code/OpenCode sessions inherit ~10-15k tokens of hooks (superpowers, skills, agents), have tool-selection overhead, session-management complexity, Enter-spam-loops, and non-deterministic execution paths. A coding agent is designed to write code — not to run an analysis pipeline.
**Solution:** Direct Ollama API calls via a dedicated Python client. No shell, no tools, no session-history accumulation. The prompt is exactly what the role needs — nothing else.

### 2. Deterministic Python for All Calculations
**Trade-UI problem:** Models hallucinated completions (claimed files written when disk was empty), fabricated prices (analyst01's PLTR price), made arithmetic errors, and produced invalid JSON. Every calculation left to an LLM was a failure source.
**Solution:** Python owns ALL calculations: indicators, position sizing, risk limits, scoring, validation. The LLM sees only finished numbers and interprets them — it never calculates them.

### 3. Database as Operational State Store (Not Files)
**Trade-UI problem:** File-based handoffs caused dangling symlinks, import deadlocks ("database is locked" from nested connections), duplicate dispatch (watchdog re-nudging completed steps), and file-naming races.
**Solution:** SQLite is the authoritative state store. Runs, steps, decisions, orders, portfolio snapshots — everything is in the database with transactional integrity. No files as runtime state.

### 4. Structured Output Validation Gate BEFORE State Transition
**Trade-UI problem:** The single-write + validation gate pattern was added late (flow 069/070). Before this, models could signal completion without producing valid output. Coder models especially hallucinated completions.
**Solution:** Every role output is validated with JSON schema BEFORE any state transition. Invalid output → one repair attempt → fail if still invalid. Blocking roles stop the workflow. No order can be generated from unvalidated output.

### 5. Account Environment Verification as First-Class Hard Gate
**Trade-UI problem:** AUTO_EXECUTION_DISABLED, DEMO_ONLY, and LIVE_DISABLED gates were added reactively. Models could ignore risk rules (risk01 approved R:R 1.52 despite §9.4 explicitly forbidding it).
**Solution:** Account environment is verified deterministically 5 times: at startup, at broker connectivity check, before order preview, before order submission, and during reconciliation. Unknown environment = execution denied. No LLM can bypass this gate.

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                       Trade Engine UI                        │
│  ⚠ VIRTUAL TRADING banner on every operational screen      │
│  Daily | Portfolio | Decisions | Runs | Setup               │
└────────────────────────────┬─────────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────────┐
│                     Trade Engine API (FastAPI)                 │
│  Run Control | Decision API | Virtual Execution | Setup API   │
└───────────────┬──────────────────┬───────────────────────────┘
                │                  │
                ▼                  ▼
┌────────────────────────┐  ┌──────────────────────────────────┐
│ Workflow Orchestrator  │  │ Deterministic Trading Services  │
│ Fixed role sequence    │  │ Indicators, Portfolio, Risk,     │
│ Input construction     │  │ Scoring, Decision, Execution,    │
│ Ollama calls           │  │ Reconciliation, Performance      │
│ Output validation      │  │                                  │
│ Retry policy           │  │ Python owns ALL calculations     │
└────────────┬───────────┘  └────────────────┬─────────────────┘
             │                               │
             ▼                               ▼
┌────────────────────────┐  ┌──────────────────────────────────┐
│ Local Ollama Runtime   │  │ Broker Adapter Layer             │
│ Fixed local models     │  │ eToro Virtual Adapter            │
│ Structured outputs     │  │ verify_environment() before      │
│ JSON mode enabled      │  │ every place_order()              │
└────────────────────────┘  └────────────────┬─────────────────┘
                                            │
                                            ▼
                              ┌──────────────────────────────┐
                              │ eToro Virtual Account        │
                              │ Market and portfolio data    │
                              │ Virtual order execution      │
                              └──────────────────────────────┘

                All state, results, and audit data
                             │
                             ▼
                   ┌──────────────────────┐
                   │ Local SQL Database   │
                   │ SQLite (V1)          │
                   └──────────────────────┘
```

---

## 3. Database Schema

### 3.1 System & Configuration

```sql
-- Ollama model registry
CREATE TABLE ollama_models (
    model_key       TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    enabled         INTEGER DEFAULT 1,
    intended_role   TEXT,              -- reasoning, analytical, critique, fast
    context_size    INTEGER DEFAULT 32768,
    timeout_seconds INTEGER DEFAULT 180,
    concurrency_max INTEGER DEFAULT 1,
    keep_policy     TEXT DEFAULT 'unload_after_idle',
    structured_output_support INTEGER DEFAULT 1,
    last_health_check TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Role definitions (DB controls operations, Markdown files control semantics)
CREATE TABLE role_definitions (
    role_key            TEXT PRIMARY KEY,
    display_name        TEXT NOT NULL,
    description         TEXT,
    execution_order     INTEGER NOT NULL,
    enabled             INTEGER DEFAULT 1,
    ollama_model        TEXT NOT NULL REFERENCES ollama_models(model_key),
    temperature         REAL DEFAULT 0.2,
    context_limit       INTEGER DEFAULT 65536,
    timeout_seconds     INTEGER DEFAULT 180,
    max_retries         INTEGER DEFAULT 1,
    blocking            INTEGER DEFAULT 1,
    role_definition_path TEXT NOT NULL,
    input_schema        TEXT,
    output_schema       TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Workflows
CREATE TABLE workflows (
    workflow_key    TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    description     TEXT,
    enabled         INTEGER DEFAULT 1,
    account_key     TEXT NOT NULL REFERENCES broker_accounts(account_key),
    mode            TEXT NOT NULL DEFAULT 'virtual_approval_required',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Workflow steps
CREATE TABLE workflow_steps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_key    TEXT NOT NULL REFERENCES workflows(workflow_key),
    sort_order      INTEGER NOT NULL,
    role_key        TEXT NOT NULL REFERENCES role_definitions(role_key),
    enabled         INTEGER DEFAULT 1,
    skip_condition  TEXT,
    UNIQUE(workflow_key, role_key),
    UNIQUE(workflow_key, sort_order)
);

-- Schedules
CREATE TABLE schedules (
    schedule_key    TEXT PRIMARY KEY,
    workflow_key    TEXT NOT NULL REFERENCES workflows(workflow_key),
    enabled         INTEGER DEFAULT 1,
    timezone        TEXT NOT NULL DEFAULT 'Europe/Madrid',
    schedule_type   TEXT NOT NULL,
    cron_expression TEXT,
    mode_override   TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 Broker & Account Environment

```sql
CREATE TABLE brokers (
    broker_key      TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    enabled         INTEGER DEFAULT 1,
    adapter_module  TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE broker_capabilities (
    broker_key              TEXT PRIMARY KEY REFERENCES brokers(broker_key),
    account_environment     TEXT NOT NULL,
    portfolio_read          INTEGER DEFAULT 1,
    market_data_read        INTEGER DEFAULT 1,
    order_preview           INTEGER DEFAULT 0,
    virtual_order_execution INTEGER DEFAULT 0,
    order_cancel            INTEGER DEFAULT 0,
    fractional_orders       INTEGER DEFAULT 0,
    live_order_execution    INTEGER DEFAULT 0,
    last_validated          TIMESTAMP,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE broker_accounts (
    account_key         TEXT PRIMARY KEY,
    broker_key          TEXT NOT NULL REFERENCES brokers(broker_key),
    display_name        TEXT NOT NULL,
    account_environment TEXT NOT NULL,
    execution_enabled   INTEGER DEFAULT 1,
    real_money          INTEGER DEFAULT 0,
    active              INTEGER DEFAULT 1,
    credential_ref      TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE instruments (
    instrument_key  TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    instrument_type TEXT DEFAULT 'stock',
    sector          TEXT,
    currency        TEXT DEFAULT 'USD',
    enabled         INTEGER DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE broker_symbol_mappings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    broker_key          TEXT NOT NULL REFERENCES brokers(broker_key),
    instrument_key      TEXT NOT NULL REFERENCES instruments(instrument_key),
    broker_symbol       TEXT NOT NULL,
    broker_instrument_id TEXT,
    enabled             INTEGER DEFAULT 1,
    UNIQUE(broker_key, instrument_key)
);

CREATE TABLE strategy_instruments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_key    TEXT NOT NULL REFERENCES workflows(workflow_key),
    instrument_key  TEXT NOT NULL REFERENCES instruments(instrument_key),
    enabled         INTEGER DEFAULT 1,
    UNIQUE(workflow_key, instrument_key)
);
```

### 3.3 Risk & Execution Policies

```sql
CREATE TABLE risk_policies (
    policy_key                  TEXT PRIMARY KEY,
    display_name                TEXT NOT NULL,
    enabled                     INTEGER DEFAULT 1,
    max_position_size_usd       REAL,
    max_allocation_pct          REAL,
    max_sector_allocation_pct   REAL,
    max_total_exposure_pct      REAL,
    max_correlated_exposure_pct REAL,
    max_open_positions          INTEGER,
    min_cash_reserve_pct        REAL,
    max_daily_loss_usd          REAL,
    max_rolling_drawdown_pct    REAL,
    max_order_value_usd         REAL,
    stale_data_reject_seconds   INTEGER DEFAULT 120,
    trading_hours_only          INTEGER DEFAULT 1,
    cooldown_after_fail_seconds INTEGER DEFAULT 300,
    cooldown_after_stop_loss    INTEGER DEFAULT 3600,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE execution_policies (
    policy_key                      TEXT PRIMARY KEY,
    display_name                    TEXT NOT NULL,
    enabled                         INTEGER DEFAULT 1,
    account_environment             TEXT NOT NULL DEFAULT 'virtual',
    allowed_instruments_json        TEXT,
    maximum_virtual_order_value     REAL DEFAULT 500,
    maximum_daily_virtual_orders    INTEGER DEFAULT 3,
    minimum_confidence              REAL DEFAULT 0.8,
    minimum_deterministic_score     REAL DEFAULT 75,
    require_review_pass             INTEGER DEFAULT 1,
    require_portfolio_reconciliation INTEGER DEFAULT 1,
    maximum_market_data_age_seconds INTEGER DEFAULT 120,
    kill_switch_enabled             INTEGER DEFAULT 1,
    created_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.4 Runtime — Runs, Steps, Model Calls

```sql
CREATE TABLE runs (
    run_id              TEXT PRIMARY KEY,
    workflow_key        TEXT NOT NULL,
    account_key         TEXT NOT NULL,
    mode                TEXT NOT NULL,
    trigger             TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'created',
    config_snapshot     TEXT NOT NULL,
    started_at          TIMESTAMP,
    completed_at        TIMESTAMP,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE run_steps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    sort_order      INTEGER NOT NULL,
    role_key        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    duration_ms     INTEGER,
    retry_count     INTEGER DEFAULT 0,
    error_message   TEXT,
    UNIQUE(run_id, sort_order)
);

CREATE TABLE model_calls (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_step_id         INTEGER NOT NULL REFERENCES run_steps(id),
    attempt             INTEGER DEFAULT 1,
    model_name          TEXT NOT NULL,
    prompt_size_chars   INTEGER,
    response_size_chars INTEGER,
    duration_ms         INTEGER,
    temperature         REAL,
    success             INTEGER DEFAULT 1,
    error_message       TEXT,
    raw_response_json   TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE role_results (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_step_id             INTEGER NOT NULL REFERENCES run_steps(id),
    role_key                TEXT NOT NULL,
    output_type             TEXT NOT NULL,
    schema_version          TEXT NOT NULL,
    validated_output_json   TEXT NOT NULL,
    validation_passed       INTEGER DEFAULT 1,
    validation_errors       TEXT,
    role_definition_hash    TEXT NOT NULL,
    model_name              TEXT NOT NULL,
    model_parameters_json   TEXT NOT NULL,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.5 Decisions & Orders

```sql
CREATE TABLE trade_decisions (
    decision_id            TEXT PRIMARY KEY,
    run_id                 TEXT NOT NULL REFERENCES runs(run_id),
    account_environment    TEXT NOT NULL DEFAULT 'virtual',
    instrument_key         TEXT NOT NULL REFERENCES instruments(instrument_key),
    action                 TEXT NOT NULL,
    proposed_quantity      REAL,
    proposed_order_type    TEXT DEFAULT 'market',
    limit_price            REAL,
    time_horizon           TEXT,
    confidence             REAL,
    deterministic_score    REAL,
    thesis                 TEXT,
    supporting_signals_json TEXT,
    conflicting_signals_json TEXT,
    risk_assessment_json   TEXT,
    invalidation_conditions_json TEXT,
    status                 TEXT NOT NULL DEFAULT 'draft',
    expires_at             TIMESTAMP,
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE decision_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id     TEXT NOT NULL REFERENCES trade_decisions(decision_id),
    reviewer_role   TEXT NOT NULL DEFAULT 'review01',
    verdict         TEXT NOT NULL,
    critique_json   TEXT,
    hallucination_risk REAL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE risk_evaluations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id     TEXT NOT NULL REFERENCES trade_decisions(decision_id),
    policy_key      TEXT NOT NULL REFERENCES risk_policies(policy_key),
    risk_decision   TEXT NOT NULL,
    llm_proposed_pct REAL,
    risk_allowed_pct REAL,
    reason          TEXT,
    evaluated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE approvals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id     TEXT NOT NULL REFERENCES trade_decisions(decision_id),
    approved_by     TEXT NOT NULL DEFAULT 'human',
    approved        INTEGER NOT NULL,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders (
    order_id            TEXT PRIMARY KEY,
    decision_id         TEXT NOT NULL REFERENCES trade_decisions(decision_id),
    broker_order_id     TEXT,
    account_environment TEXT NOT NULL DEFAULT 'virtual',
    instrument_key      TEXT NOT NULL,
    action              TEXT NOT NULL,
    quantity            REAL,
    order_type          TEXT DEFAULT 'market',
    limit_price         REAL,
    status              TEXT NOT NULL DEFAULT 'pending',
    broker_response_json TEXT,
    submitted_at        TIMESTAMP,
    filled_at           TIMESTAMP,
    filled_price        REAL,
    filled_quantity     REAL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        TEXT NOT NULL REFERENCES orders(order_id),
    event_type      TEXT NOT NULL,
    event_data_json TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.6 Portfolio & Positions

```sql
CREATE TABLE portfolio_snapshots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    account_key         TEXT NOT NULL REFERENCES broker_accounts(account_key),
    account_environment TEXT NOT NULL DEFAULT 'virtual',
    snapshot_type       TEXT NOT NULL,
    run_id              TEXT,
    balance_usd         REAL,
    equity_usd          REAL,
    available_cash_usd  REAL,
    allocated_usd       REAL,
    unrealized_pnl_usd  REAL,
    realized_pnl_usd    REAL,
    raw_broker_json     TEXT,
    source_timestamp    TIMESTAMP,
    retrieved_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE positions (
    position_id         TEXT PRIMARY KEY,
    broker_position_id  TEXT,
    account_key         TEXT NOT NULL REFERENCES broker_accounts(account_key),
    account_environment TEXT NOT NULL DEFAULT 'virtual',
    instrument_key      TEXT NOT NULL REFERENCES instruments(instrument_key),
    quantity            REAL,
    open_price          REAL,
    current_price       REAL,
    market_value_usd    REAL,
    unrealized_pnl_usd  REAL,
    realized_pnl_usd    REAL,
    opened_at           TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE position_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id     TEXT NOT NULL REFERENCES positions(position_id),
    event_type      TEXT NOT NULL,
    event_data_json TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.7 Market Data & Performance

```sql
CREATE TABLE market_data_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_key  TEXT NOT NULL REFERENCES instruments(instrument_key),
    source          TEXT NOT NULL,
    price           REAL,
    bid             REAL,
    ask             REAL,
    volume          REAL,
    source_timestamp TIMESTAMP,
    retrieved_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_quality    TEXT DEFAULT 'unknown',
    max_age_seconds INTEGER DEFAULT 120
);

CREATE TABLE indicator_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    instrument_key  TEXT NOT NULL REFERENCES instruments(instrument_key),
    indicator_name  TEXT NOT NULL,
    value           REAL,
    parameters_json TEXT,
    calculated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE trade_outcomes (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id             TEXT NOT NULL REFERENCES trade_decisions(decision_id),
    order_id                TEXT REFERENCES orders(order_id),
    entry_time              TIMESTAMP,
    entry_price             REAL,
    exit_time               TIMESTAMP,
    exit_price              REAL,
    position_size           REAL,
    realized_pnl_usd        REAL,
    unrealized_pnl_usd      REAL,
    pct_return              REAL,
    holding_period_hours    REAL,
    max_favorable_excursion_pct REAL,
    max_adverse_excursion_pct REAL,
    stop_loss_activated     INTEGER DEFAULT 0,
    take_profit_activated   INTEGER DEFAULT 0,
    exit_reason             TEXT,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE performance_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_key     TEXT NOT NULL REFERENCES broker_accounts(account_key),
    period_start    TIMESTAMP NOT NULL,
    period_end      TIMESTAMP NOT NULL,
    total_pnl_usd   REAL,
    pct_return      REAL,
    win_rate        REAL,
    avg_win_usd     REAL,
    avg_loss_usd    REAL,
    profit_factor   REAL,
    sharpe_ratio    REAL,
    max_drawdown_pct REAL,
    total_trades    INTEGER,
    winning_trades  INTEGER,
    losing_trades   INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.8 Audit & Health

```sql
CREATE TABLE audit_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'info',
    event_data_json TEXT NOT NULL,
    run_id          TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE system_health_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    check_type      TEXT NOT NULL,
    status          TEXT NOT NULL,
    details_json    TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE kill_switches (
    switch_key      TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    enabled         INTEGER DEFAULT 0,
    activated_by    TEXT DEFAULT 'system',
    activated_at    TIMESTAMP,
    reason          TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.9 UI Configuration (Database-Driven Frontend)

```sql
CREATE TABLE ui_groups (
    group_key       TEXT PRIMARY KEY,
    label_key       TEXT NOT NULL,
    route           TEXT NOT NULL,
    icon_key        TEXT,
    display_order   INTEGER NOT NULL,
    enabled         INTEGER DEFAULT 1
);

CREATE TABLE ui_panels (
    panel_key       TEXT PRIMARY KEY,
    group_key       TEXT NOT NULL REFERENCES ui_groups(group_key),
    label_key       TEXT NOT NULL,
    component_type  TEXT NOT NULL,
    data_source     TEXT NOT NULL,
    display_order   INTEGER NOT NULL,
    enabled         INTEGER DEFAULT 1,
    refresh_seconds INTEGER DEFAULT 30,
    visibility_condition TEXT
);

CREATE TABLE ui_fields (
    field_key       TEXT PRIMARY KEY,
    panel_key       TEXT NOT NULL REFERENCES ui_panels(panel_key),
    label_key       TEXT NOT NULL,
    field_type      TEXT NOT NULL,
    data_path       TEXT NOT NULL,
    display_order   INTEGER NOT NULL,
    enabled         INTEGER DEFAULT 1
);

CREATE TABLE ui_status_definitions (
    status_key      TEXT PRIMARY KEY,
    label_key       TEXT NOT NULL,
    badge_color     TEXT NOT NULL,
    icon_key        TEXT,
    display_order   INTEGER NOT NULL
);
```

### 3.10 i18n (4-Layer Architecture — from DPMtF)

```sql
CREATE TABLE ui_text_slots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_key    TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ui_text_slot_labels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_key    TEXT NOT NULL,
    label_key   TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(slot_key, label_key)
);

CREATE TABLE ui_labels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    label_id    TEXT UNIQUE NOT NULL,
    label_key   TEXT UNIQUE NOT NULL,
    label_domain TEXT NOT NULL,
    default_text TEXT NOT NULL,
    description TEXT,
    is_active   INTEGER DEFAULT 1,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ui_label_translations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    label_id        TEXT NOT NULL,
    locale          TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    is_active       INTEGER DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(label_id, locale)
);
```

### Key Database Design Decisions

1. **`account_environment` is a pervasive field** — present on orders, positions, portfolio_snapshots, trade_decisions. Impossible to "forget" whether a record is virtual or live.
2. **Immutable JSON alongside normalized fields** — `raw_broker_json`, `validated_output_json`, `config_snapshot` provide full reproducibility without sacrificing searchability.
3. **Every order/position has an event table** — full audit trail from preview to filled/cancelled. No state is lost.
4. **Kill switches are database records** — not environment variables or code constants. Activatable via API, readable by all components.
5. **Strategy-instrument allowlists** — explicit mapping between workflow and allowed instruments. No implicit "all instruments allowed."

---

## 4. Frontend Architecture

### 4.1 Navigation

Five primary areas + two secondary:

| Area | Route | Purpose |
|------|-------|---------|
| **Daily** | `/daily` | Operational cockpit (default landing) |
| **Portfolio** | `/portfolio` | Balance, positions, exposure |
| **Decisions** | `/decisions` | Trade decisions, approve/reject |
| **Runs** | `/runs` | Workflow execution history |
| **Setup** | `/setup` | Database-driven configuration |
| *Performance* | `/performance` | Secondary — deferred |
| *Audit* | `/audit` | Secondary — deferred |

### 4.2 Persistent Virtual Account Banner

Every operational screen must display:

```
⚠ VIRTUAL TRADING — Connected to eToro Virtual Account
No real money is being used
```

The banner is injected by a dedicated `virtual-banner.js` component and cannot be accidentally removed.

### 4.3 Daily View — Panel Composition

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠ VIRTUAL TRADING — Connected to eToro Virtual Account     │
├──────────────────────────────────────────────────────────────┤
│  ┌─ Portfolio Status ──────────────────────────────────────┐ │
│  │ Virtual Equity: $12,450.32    Available Cash: $3,200   │ │
│  │ Open Positions: 4             Daily P/L: +$145.20       │ │
│  │ Exposure: 62%                 Mode: AUTONOMOUS VIRTUAL  │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─ Workflow Status ──────────────────────────────────────┐ │
│  │ Frequency: Every 60 minutes                             │ │
│  │ Last run: 08:00 — Completed (3 decisions, 1 trade)     │ │
│  │ Next run: 09:00  Scheduler: ● Running                   │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─ Latest Decision ──────────────────────────────────────┐ │
│  │ AAPL — BUY — Confidence 0.82 — Risk: ALLOWED           │ │
│  │ Status: EXECUTED VIRTUALLY — $498.50                   │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─ Attention Required ────────────────────────────────────┐ │
│  │ (hidden when empty)                                     │ │
│  │ ⚠ 2 decisions awaiting approval                        │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─ Recent Activity ──────────────────────────────────────┐ │
│  │ 08:02  Virtual BUY order filled for AAPL               │ │
│  │ 08:00  Hourly workflow completed (7/7 steps)           │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─ Actions ──────────────────────────────────────────────┐ │
│  │ [Run Now]  [Pause]  [EMERGENCY STOP]                   │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 4.4 JavaScript File Structure

```
static/
├── js/
│   ├── trade-engine-app.js      # Main app: navigation, panel rendering, i18n
│   ├── panels/
│   │   ├── daily.js             # Daily cockpit panels
│   │   ├── portfolio.js         # Portfolio display
│   │   ├── decisions.js         # Decision list + approval
│   │   ├── runs.js              # Run history
│   │   └── setup.js             # Setup CRUD forms
│   ├── services/
│   │   ├── api.js               # API calls (fetch wrapper)
│   │   ├── labels.js            # i18n label loader (lbl() function)
│   │   └── state.js             # Frontend state management
│   └── components/
│       ├── status-badge.js      # Reusable status display
│       ├── mode-selector.js     # Mode switcher component
│       ├── kill-switch.js       # Emergency stop button
│       ├── virtual-banner.js    # Persistent virtual account banner
│       └── confirm-dialog.js    # Confirmation dialog
├── css/
│   └── trade-engine.css         # Dark theme (GitHub-dark palette)
└── templates/
    └── index.html               # Single-page shell
```

### 4.5 Frontend Coding Standards (from DPMtF)

1. **`lbl(key, fallback)`** — ALL user-facing text. No hardcoded English strings.
2. **`createElement()` / `textContent`** — never `innerHTML` for dynamic content.
3. **Event delegation** — listeners on container elements, not individual buttons.
4. **Database-driven rendering** — panels, fields, status definitions fetched from API.
5. **Virtual banner is persistent** — injected on ALL pages, cannot be removed accidentally.
6. **`const` by default, `let` only when reassignment needed. Never `var`.**
7. **Class-based CSS selectors. No inline `style=""` for layout.**
8. **Dark theme only (GitHub-dark palette).**

### 4.6 Frontend Acceptance Criteria

1. Active portfolio identifiable immediately
2. eToro Virtual Account identifiable immediately
3. Mode visible without opening Setup
4. Execution frequency visible without opening Setup
5. Last and next scheduled run visible
6. Schedule creatable/editable/pausable from frontend
7. No cron syntax required for normal schedule creation
8. Application scheduler monitorable from frontend
9. Missed/blocked/failed scheduled runs clearly visible
10. Pending decision approvable/rejectable from Daily
11. Autonomous virtual execution pausable from Daily
12. Global emergency stop visible during autonomous operation
13. All frontend labels use stable i18n keys
14. Navigation, panels, labels, ordering, visibility follow database-driven structure
15. Business, risk, and execution logic remain in backend
16. Main operational state understandable without reading model transcripts

---

## 5. Business Logic Architecture

### 5.1 Repository Structure

```
local-trade-engine/
├── app/
│   ├── api/
│   │   ├── dashboard.py
│   │   ├── decisions.py
│   │   ├── portfolio.py
│   │   ├── orders.py
│   │   ├── runs.py
│   │   ├── performance.py
│   │   ├── setup.py
│   │   └── audit.py
│   ├── brokers/
│   │   ├── base.py              # BrokerAdapter abstract interface
│   │   ├── etoro_virtual.py     # eToro Virtual Account adapter
│   │   └── paper_local.py       # Local paper trading adapter
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── logging.py
│   │   └── errors.py
│   ├── models/
│   │   ├── database.py          # SQLAlchemy/SQLite models
│   │   ├── domain.py            # Domain objects
│   │   └── schemas.py           # JSON schemas for validation
│   ├── ollama/
│   │   ├── client.py            # Dedicated Ollama HTTP client
│   │   ├── lifecycle.py         # Model keep_loaded/unload management
│   │   └── validation.py        # JSON schema validation
│   ├── orchestration/
│   │   ├── engine.py            # Central WorkflowEngine
│   │   ├── workflow_loader.py   # Load workflow + steps from DB
│   │   ├── input_builder.py     # Build prompt input per role
│   │   ├── role_runner.py       # Execute role: call Ollama → validate
│   │   └── run_snapshot.py      # Create immutable run snapshot
│   ├── services/
│   │   ├── market_data_service.py
│   │   ├── indicator_service.py
│   │   ├── portfolio_service.py
│   │   ├── position_service.py
│   │   ├── decision_service.py
│   │   ├── risk_service.py
│   │   ├── scoring_service.py
│   │   ├── execution_service.py
│   │   ├── reconciliation_service.py
│   │   └── performance_service.py
│   ├── scheduling/
│   │   ├── scheduler.py         # Application-owned scheduler
│   │   └── signal_scanner.py    # Deterministic signal detection
│   └── main.py
├── roles/
│   ├── trend01.md
│   ├── market01.md
│   ├── analyst01.md
│   ├── risk01.md
│   ├── review01.md
│   └── decision01.md
├── schemas/                     # JSON schema files
├── migrations/                  # Versioned SQL migrations
├── tests/
├── scripts/
│   ├── initialize_database.py
│   ├── validate_setup.py
│   ├── verify_virtual_account.py
│   ├── run_workflow.py
│   └── backup_database.py
├── ui/                          # Frontend files
├── data/
├── .env.example
├── README.md
└── pyproject.toml
```

### 5.2 Workflow Engine — Run Lifecycle

```
created → preparing → verifying_virtual → collecting_data → calculating
→ running_roles → validating → decision_ready
→ awaiting_approval → approved → executing_virtual_order → reconciling → completed
```

**Hard gates:**
- `verifying_virtual`: `broker.verify_account_environment()` — unknown/live → `ExecutionBlockedError`
- `validating`: Every role output validated against JSON schema — invalid → one repair attempt → fail
- `executing_virtual_order`: 5-point verification before every `place_order()`

### 5.3 Role Runner — Validation Gate

```python
async def execute(step, context, previous_outputs) -> RoleResult:
    for attempt in range(step.role.max_retries + 1):
        raw_response = await ollama.generate(
            model=step.role.ollama_model,
            prompt=input_prompt,
            json_mode=True,
        )
        validation = await validate_output(raw_response, step.role.output_schema)
        if validation.passed:
            return RoleResult(success=True, output=validation.parsed)
        if attempt == 0:
            input_prompt = build_repair_prompt(input_prompt, raw_response, validation.errors)
            continue
    return RoleResult(success=False, error=validation.errors)
```

### 5.4 Broker Adapter Interface

```python
class BrokerAdapter(ABC):
    @abstractmethod
    async def verify_account_environment(self, account) -> AccountEnvironment: ...
    @abstractmethod
    async def get_portfolio(self) -> list[BrokerPosition]: ...
    @abstractmethod
    async def preview_order(self, order) -> OrderPreview: ...
    @abstractmethod
    async def place_order(self, order) -> BrokerOrderResult: ...
    @abstractmethod
    async def cancel_order(self, broker_order_id) -> BrokerOrderResult: ...
    @abstractmethod
    async def reconcile_order(self, broker_order_id) -> BrokerOrderState: ...
```

**Mandatory:** `place_order()` MUST call `verify_account_environment()` internally before submission. Any result other than `{environment: "virtual", verified: true, real_money: false}` MUST block execution.

### 5.5 Deterministic Risk Service

The risk service evaluates every decision against all configured risk rules. The LLM may explain risk, but Python is the final authority.

```python
class RiskService:
    def evaluate(decision, policy, portfolio) -> RiskEvaluation:
        checks = [
            check_position_size, check_allocation_pct, check_sector_exposure,
            check_total_exposure, check_correlated_exposure, check_max_open_positions,
            check_cash_reserve, check_daily_loss, check_drawdown,
            check_order_value, check_stale_data, check_duplicate_order,
            check_trading_hours,
        ]
        # Any blocked → overall blocked
        # Adjustments applied but don't block
        return RiskEvaluation(decision=..., checks=checks)
```

### 5.6 Execution Service — 5-Point Verification

Before every `place_order()`:
1. Verify account environment (virtual, verified, not real_money)
2. Re-verify market data freshness (not stale)
3. Re-verify risk (portfolio may have changed since decision)
4. Preview order (if broker supports it)
5. Check all kill switches (global, broker, workflow, autonomous, instrument)

### 5.7 Failure Handling

| Category | Response |
|----------|----------|
| `configuration_error` | Stop workflow, alert |
| `account_environment_unknown` | **BLOCK**, critical audit event |
| `live_account_detected` | **BLOCK**, critical audit event, alert |
| `market_data_error` | Retry or skip (stale data → block) |
| `broker_error` | Retry with backoff |
| `ollama_unavailable` | Retry, then fail |
| `model_timeout` | Retry once, then fail |
| `invalid_model_output` | One repair attempt, then fail |
| `risk_validation_error` | Block decision |
| `database_error` | Fail workflow |
| `virtual_execution_error` | Retry, then fail |
| `reconciliation_error` | Mark for manual review |

**Critical rule:** `LIVE_ACCOUNT_DETECTED` and `ACCOUNT_ENVIRONMENT_UNKNOWN` must NEVER result in retry. They must always block and create critical audit events.

### 5.8 Kill Switches

| Switch | Scope |
|--------|-------|
| `global_execution` | Stops all new virtual order submissions |
| `workflow:{key}` | Disables a specific workflow |
| `broker:{key}` | Disables execution through a specific broker adapter |
| `instrument:{key}` | Blocks decisions/execution for a specific instrument |
| `autonomous` | Immediately changes autonomous workflows to `virtual_approval_required` |

Kill-switch activation must not depend on an LLM. Activation takes effect immediately.

### 5.9 Scheduler Architecture

- **Database** is the authoritative schedule configuration store
- **Trade Engine Scheduler** (Python `asyncio` loop) calculates due runs and starts workflows
- **Frontend** creates, edits, pauses, and monitors schedules
- **Systemd** keeps the Trade Engine service running
- **Cron** is an optional health watchdog only — NOT the primary scheduler

Schedule presets: Manual only, Every 15 minutes, Every 30 minutes, Every hour, Every 4 hours, Daily, Weekdays, Signal triggered, Custom.

### 5.10 API Endpoints

```
System:
  GET  /api/health
  GET  /api/system/status
  GET  /api/system/account-environment

Runs:
  POST /api/runs
  GET  /api/runs
  GET  /api/runs/{run_id}
  POST /api/runs/{run_id}/cancel

Decisions:
  GET  /api/decisions
  GET  /api/decisions/{decision_id}
  POST /api/decisions/{decision_id}/approve
  POST /api/decisions/{decision_id}/reject
  POST /api/decisions/{decision_id}/execute-virtual

Portfolio:
  GET  /api/portfolio
  POST /api/portfolio/refresh
  GET  /api/positions
  GET  /api/orders
  GET  /api/trades

Setup:
  GET  /api/setup/models
  GET  /api/setup/roles
  GET  /api/setup/workflows
  GET  /api/setup/risk-policies
  GET  /api/setup/execution-policies
  GET  /api/setup/broker-account
  POST /api/setup/validate
  POST /api/setup/verify-virtual-account

Performance:
  GET /api/performance/summary
  GET /api/performance/by-strategy
  GET /api/performance/by-instrument

Audit:
  GET /api/audit/events
  GET /api/audit/runs/{run_id}
  GET /api/audit/orders/{order_id}
```

---

## 6. Role Architecture

### 6.1 Fixed Roles

| Role | Responsibility | Model Type |
|------|---------------|------------|
| **trend01** | Broader trend and market regime determination | Fast reasoning |
| **market01** | Current market conditions, liquidity, volatility, cross-asset signals | General analytical |
| **analyst01** | Instrument-level trade candidates from normalized data | Stronger reasoning |
| **risk01** | Reviews candidates against portfolio exposure and risk context | Conservative review |
| **review01** | Critiques complete candidate set, identifies contradictions | Independent critique |
| **decision01** | Creates final structured trade decision and explanation | Fast structured-output |

### 6.2 Role Definition Files

```
roles/
├── trend01.md
├── market01.md
├── analyst01.md
├── risk01.md
├── review01.md
└── decision01.md
```

Database controls operational parameters. Markdown files control semantic role behavior. Each run stores: role-definition path, content hash, configuration snapshot, model name, model parameters.

---

## 7. V1 Scope

### 7.1 Included
- Separate `local-trade-engine` repository
- Local web UI with persistent virtual-account banner
- Local API (FastAPI)
- SQLite database
- Database-driven Setup
- Fixed 6-role workflow
- Markdown role definitions
- Direct local Ollama integration
- Structured JSON role outputs
- Deterministic market calculations
- Deterministic risk validation
- eToro Virtual Account adapter
- Virtual account verification (5-point)
- Virtual portfolio synchronization
- Virtual order execution
- Virtual order reconciliation
- Human-approved virtual trading
- Policy-controlled autonomous virtual trading
- Run/decision/order/trade/performance/audit history
- System and setup validation (12-point check)
- Manual and scheduled workflow execution
- Global execution kill switch
- Automatic block if live account detected

### 7.2 Excluded (V1)
- Real-money execution
- Live-account order submission
- Cloud-hosted language models
- Multiple brokers
- Unrestricted workflow editing
- Broker-specific logic outside the adapter
- Model-generated Python execution
- Shell access for roles
- Vector database
- Exchange-level high-frequency trading

### 7.3 V1 Constraints
- One active virtual portfolio
- One eToro Virtual Account
- One primary workflow initially
- Local Ollama only
- No real-money execution
- No live-account order submission

---

## 8. Implementation Phases

| Phase | Name | Key Deliverables |
|-------|------|-----------------|
| **0** | Scope & Extraction | Identify reusable Trade-UI concepts, define schemas, define broker interface |
| **1** | Core Runtime | Repository, database layer, domain schemas, Ollama client, role loader, workflow orchestrator, output validation, run persistence |
| **2** | Deterministic Services | Market data normalization, indicators, portfolio calculations, scoring, position sizing, risk-policy engine, decision normalization |
| **3** | eToro Virtual Read | Verify virtual account, retrieve balance/portfolio/positions, map instruments, store snapshots, show virtual state in frontend |
| **4** | Human-Approved Virtual Execution | Create decision, preview order, human approval, 5-point verification, virtual order submission, reconciliation, outcome persistence |
| **5** | UI Completion | Dashboard, virtual-account banner, decisions, portfolio, positions, orders/trades, runs, performance, Setup, audit, health status |
| **6** | Autonomous Virtual Trading | Virtual-autonomy policy, instrument allowlist, order-size limits, daily loss limit, automatic execution, automatic reconciliation, kill switch |
| **7** | Higher-Frequency Workflows | Deterministic signal scanner, event-triggered workflows, incremental data updates, model lifecycle optimization |
| **8** | Virtual Learning & Evaluation | Connect decisions to outcomes, strategy-performance reports, role-version comparison, confidence calibration |
| **9** | Future Live-Trading Assessment | Outside V1 — separate scope, security review, and implementation project |

---

## 9. Architectural Decisions

1. **No Coding-Agent Runtime** — Trade Engine calls Ollama directly, no Claude Code or OpenCode dependency
2. **Separate Repository** — Independent repository at `github.com/svend-blip/Local-Trade-Engine`
3. **Database as Operational Authority** — All generated results, decisions, runs, orders, portfolio snapshots, and configuration stored in SQLite
4. **Markdown for Semantic Role Definitions** — Human-readable Markdown files referenced by database configuration
5. **Deterministic Risk Authority** — Python risk policy has final authority over all LLM decisions
6. **eToro Virtual Account in V1** — V1 may submit and manage trades through a verified eToro Virtual Account
7. **Virtual State Must Be Prominent** — Frontend persistently identifies account, balance, positions, P/L, orders, and performance as virtual
8. **Autonomous Virtual Trading Is Permitted** — V1 may support policy-controlled autonomous execution against the verified virtual account
9. **Real-Money Trading Is Prohibited** — V1 must block execution if account environment is live or cannot be verified
10. **Local Ollama Only** — V1 does not include cloud inference adapters
11. **Structured Output Only** — Executable decisions must originate from validated structured output, never free-form text
12. **Realistic Data Collection Starts Early** — Virtual execution included early to collect meaningful market, portfolio, execution, and performance data
13. **Controlled Learning** — Learning may suggest changes, but no configuration, strategy, risk policy, or execution environment may self-modify without approval

---

## 10. Relationship to Trade-UI

**Trade Engine reuses:**
- Role definitions, workflow ordering, market scoring, portfolio-allocation logic
- Risk-review patterns, decision schemas, report structures
- Learning and review outputs, instrument mappings, eToro integration knowledge

**Trade Engine replaces:**
- Claude Code sessions, OpenCode sessions, shell-based role execution
- File-based handoffs, general coding-agent orchestration
- Unstructured proposal files as runtime state

**Recommended separation:**
```
Trade-UI (research, experimentation, role development, strategy design)
    │
    ▼ Approved role definitions, schemas, strategies, policies
Local Trade Engine (scheduled analysis, virtual decisions, virtual execution)
    │
    ▼
eToro Virtual Account
```

---

## 11. V1 Acceptance Criteria

1. System runs without Claude Code or OpenCode
2. All model calls use local Ollama
3. Workflow configurable through database records and role Markdown paths
4. Roles execute in fixed validated order
5. Every role output is schema-validated
6. Deterministic Python calculates indicators, sizing, and risk limits
7. System connects to an eToro Virtual Account
8. Account positively verified as virtual before execution
9. Frontend persistently displays eToro Virtual Account status
10. Virtual balances, positions, orders, and P/L labelled as virtual
11. Validated decision can be approved and submitted to virtual account
12. Policy-controlled autonomous virtual execution can be enabled
13. Live or unknown account environment blocks execution
14. Virtual orders reconciled and stored locally
15. Trading decisions connected to eventual virtual outcomes
16. Market, decision, order, portfolio, and performance data stored locally
17. Broker implementation isolated behind adapter
18. Every input, output, configuration snapshot, approval, and execution event auditable
19. Global execution kill switch exists
20. No V1 path can submit a real-money order
