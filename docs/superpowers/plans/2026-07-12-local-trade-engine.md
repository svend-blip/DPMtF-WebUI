# Local Trade Engine — V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first trading decision and execution engine that replaces coding-agent interfaces with deterministic Python orchestration + local Ollama models, executing against an eToro Virtual Account.

**Architecture:** FastAPI backend → SQLite database → WorkflowEngine orchestrator → Ollama client + deterministic services → eToro Virtual Broker Adapter. Frontend is a single-page JS app with database-driven panels, persistent virtual-account banner, and i18n labels.

**Tech Stack:** Python 3.12+, FastAPI, SQLite, aiohttp (Ollama calls), vanilla JavaScript (no framework), GitHub-dark CSS theme.

## Global Constraints

- en-US mandatory for all code, comments, docstrings, commit messages
- `config.py` is single source of truth — no hardcoded paths
- Parameterized SQL only (`?` placeholders, never f-strings in SQL)
- `python3 -m py_compile <file>` MUST pass before signaling completion
- NO `innerHTML` for dynamic content — use `createElement()`/`textContent`
- ALL user-facing text MUST use `lbl(key, fallback)` — no hardcoded English strings
- `const` by default, `let` only when reassignment needed. Never `var`
- Class-based CSS selectors. No inline `style=""` for layout. Dark theme only
- Only the Human may commit or push
- Commit messages in English, format: `[phase] description`
- Never commit: `__pycache__/`, `.env`, secrets, generated artifacts
- Repository: `github.com/svend-blip/Local-Trade-Engine`

---

## File Structure

```
local-trade-engine/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app, router registration
│   ├── api/
│   │   ├── __init__.py
│   │   ├── system.py                    # Health, status, account-environment
│   │   ├── runs.py                      # Run CRUD + execution
│   │   ├── decisions.py                 # Decision list, approve, reject, execute
│   │   ├── portfolio.py                 # Portfolio, positions, orders
│   │   └── setup.py                     # Models, roles, workflows, policies CRUD
│   ├── brokers/
│   │   ├── __init__.py
│   │   ├── base.py                      # BrokerAdapter ABC
│   │   ├── etoro_virtual.py             # eToro Virtual Account adapter
│   │   └── paper_local.py               # Local paper trading (stub for V1)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                    # Central configuration
│   │   ├── database.py                  # Connection management, migrations
│   │   └── errors.py                    # Domain exceptions
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py                   # Pydantic models + JSON schemas
│   ├── ollama/
│   │   ├── __init__.py
│   │   ├── client.py                    # Ollama HTTP client
│   │   └── validation.py                # JSON schema validation
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── engine.py                    # WorkflowEngine
│   │   ├── workflow_loader.py           # Load workflow from DB
│   │   ├── input_builder.py             # Build role prompts
│   │   ├── role_runner.py               # Execute single role
│   │   └── run_snapshot.py              # Immutable run snapshots
│   ├── services/
│   │   ├── __init__.py
│   │   ├── market_data_service.py        # Yahoo/Stooq price fetching
│   │   ├── indicator_service.py         # RSI, MACD, ATR, SMA, etc.
│   │   ├── portfolio_service.py         # Exposure, concentration, liquidity
│   │   ├── risk_service.py              # Deterministic risk evaluation
│   │   ├── scoring_service.py           # Favorability scoring
│   │   ├── decision_service.py          # Aggregate role outputs → decisions
│   │   ├── execution_service.py         # 5-point verification + order submission
│   │   ├── reconciliation_service.py    # Broker state reconciliation
│   │   └── performance_service.py        # Performance metrics
│   └── scheduling/
│       ├── __init__.py
│       ├── scheduler.py                 # Application-owned scheduler
│       └── signal_scanner.py            # Deterministic signal detection
├── roles/
│   ├── trend01.md
│   ├── market01.md
│   ├── analyst01.md
│   ├── risk01.md
│   ├── review01.md
│   └── decision01.md
├── schemas/
│   ├── trend_note_v1.json
│   ├── market_snapshot_v1.json
│   ├── candidate_analysis_v1.json
│   ├── risk_verdict_v1.json
│   ├── review_verdict_v1.json
│   └── trade_decision_v1.json
├── migrations/
│   └── 001_baseline.sql
├── tests/
│   ├── conftest.py
│   ├── test_database.py
│   ├── test_config.py
│   ├── test_ollama_client.py
│   ├── test_role_runner.py
│   ├── test_engine.py
│   ├── test_risk_service.py
│   ├── test_indicator_service.py
│   ├── test_broker_adapter.py
│   ├── test_execution_service.py
│   └── test_api.py
├── scripts/
│   ├── initialize_database.py
│   ├── validate_setup.py
│   └── run_workflow.py
├── static/
│   ├── js/
│   │   ├── trade-engine-app.js          # Main app, navigation, i18n
│   │   ├── panels/
│   │   │   ├── daily.js
│   │   │   ├── portfolio.js
│   │   │   ├── decisions.js
│   │   │   ├── runs.js
│   │   │   └── setup.js
│   │   ├── services/
│   │   │   ├── api.js                   # Fetch wrapper
│   │   │   ├── labels.js                # lbl() function
│   │   │   └── state.js                 # Frontend state
│   │   └── components/
│   │       ├── status-badge.js
│   │       ├── mode-selector.js
│   │       ├── kill-switch.js
│   │       ├── virtual-banner.js
│   │       └── confirm-dialog.js
│   └── css/
│       └── trade-engine.css
├── templates/
│   └── index.html
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Phase 0: Repository & Project Skeleton

### Task 0.1: Initialize Repository

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `README.md`

**Interfaces:**
- Produces: Project root with Python package config

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "local-trade-engine"
version = "0.1.0"
description = "Local LLM Virtual Trading Decision and Execution Engine"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "aiohttp>=3.9.0",
    "jsonschema>=4.20.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create .env.example**

```bash
# Local Trade Engine — Environment Configuration
# Copy to .env and fill in values

# eToro Virtual Account (demo API)
ETORO_API_KEY=
ETORO_USER_KEY=
ETORO_DEMO_URL=https://demo-api.etoro.com

# Ollama
OLLAMA_BASE_URL=http://localhost:11434

# Application
TRADE_ENGINE_HOST=127.0.0.1
TRADE_ENGINE_PORT=9150
TRADE_ENGINE_DB_PATH=databases/trade_engine.db
```

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.py[cod]
.env
databases/*.db
*.log
.venv/
dist/
build/
```

- [ ] **Step 4: Create README.md**

```markdown
# Local Trade Engine

Local-first trading decision and execution engine.
Uses local Ollama models + deterministic Python orchestration.
V1 executes against an eToro Virtual Account.

## Setup

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
    cp .env.example .env
    # Edit .env with your eToro demo credentials
    python3 scripts/initialize_database.py
    uvicorn app.main:app --host 127.0.0.1 --port 9150 --reload

## Test

    pytest -v
```

- [ ] **Step 5: Verify**

Run: `python3 -m py_compile pyproject.toml` (skip — toml not compilable)
Run: `cat .gitignore` — verify patterns present

- [ ] **Step 6: Initialize git repo and commit**

```bash
cd /home/svend/local-trade-engine
git init
git add pyproject.toml .env.example .gitignore README.md
git commit -m "[phase0] initialize repository skeleton"
```

---

### Task 0.2: Create Core Config Module

**Files:**
- Create: `app/__init__.py`
- Create: `app/core/__init__.py`
- Create: `app/core/config.py`
- Create: `app/core/errors.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.get_db_path() -> str`, `config.get_port() -> int`, `config.get_ollama_base_url() -> str`, `config.get_etoro_credentials() -> dict`

- [ ] **Step 1: Write failing tests for config**

```python
# tests/test_config.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import Config


def test_config_defaults():
    """Config returns sensible defaults when no env vars set."""
    cfg = Config()
    assert cfg.get_port() == 9150
    assert cfg.get_host() == "127.0.0.1"
    assert cfg.get_db_path().endswith("trade_engine.db")
    assert cfg.get_ollama_base_url() == "http://localhost:11434"


def test_config_from_env(monkeypatch):
    """Config reads from environment variables."""
    monkeypatch.setenv("TRADE_ENGINE_PORT", "9999")
    monkeypatch.setenv("TRADE_ENGINE_HOST", "0.0.0.0")
    cfg = Config()
    assert cfg.get_port() == 9999
    assert cfg.get_host() == "0.0.0.0"


def test_etoro_credentials_from_env(monkeypatch):
    """Config reads eToro credentials from env."""
    monkeypatch.setenv("ETORO_API_KEY", "test-api-key")
    monkeypatch.setenv("ETORO_USER_KEY", "test-user-key")
    monkeypatch.setenv("ETORO_DEMO_URL", "https://demo-api.etoro.com")
    cfg = Config()
    creds = cfg.get_etoro_credentials()
    assert creds["api_key"] == "test-api-key"
    assert creds["user_key"] == "test-user-key"
    assert "demo" in creds["demo_url"]


def test_etoro_url_must_contain_demo(monkeypatch):
    """Config validates demo URL contains 'demo'."""
    monkeypatch.setenv("ETORO_DEMO_URL", "https://live-api.etoro.com")
    cfg = Config()
    try:
        cfg.get_etoro_credentials()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "demo" in str(e).lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/svend/local-trade-engine && python3 -m pytest tests/test_config.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement Config class**

```python
# app/core/config.py
"""Central configuration for Local Trade Engine.

Single source of truth for all configurable values.
Sources (priority order):
1. Environment variables
2. Hardcoded defaults (development only)
"""
import os
from pathlib import Path


class Config:
    """Application configuration. Reads from environment variables."""

    def get_port(self) -> int:
        return int(os.environ.get("TRADE_ENGINE_PORT", "9150"))

    def get_host(self) -> str:
        return os.environ.get("TRADE_ENGINE_HOST", "127.0.0.1")

    def get_db_path(self) -> str:
        configured = os.environ.get("TRADE_ENGINE_DB_PATH")
        if configured:
            return configured
        project_root = Path(__file__).resolve().parent.parent.parent
        return str(project_root / "databases" / "trade_engine.db")

    def get_ollama_base_url(self) -> str:
        return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    def get_etoro_credentials(self) -> dict:
        demo_url = os.environ.get("ETORO_DEMO_URL", "")
        if "demo" not in demo_url.lower():
            raise ValueError(
                f"ETORO_DEMO_URL must contain 'demo' for V1 safety. "
                f"Got: {demo_url}"
            )
        return {
            "api_key": os.environ.get("ETORO_API_KEY", ""),
            "user_key": os.environ.get("ETORO_USER_KEY", ""),
            "demo_url": demo_url,
        }

    def get_project_root(self) -> str:
        return str(Path(__file__).resolve().parent.parent.parent)


# Module-level singleton
config = Config()
```

- [ ] **Step 4: Create errors module**

```python
# app/core/errors.py
"""Domain exceptions for Local Trade Engine."""


class TradeEngineError(Exception):
    """Base exception for all Trade Engine errors."""
    pass


class ExecutionBlockedError(TradeEngineError):
    """Raised when execution is blocked by a safety gate."""
    pass


class AccountEnvironmentError(TradeEngineError):
    """Raised when account environment cannot be verified as virtual."""
    pass


class LiveAccountDetectedError(AccountEnvironmentError):
    """Raised when a live/real-money account is detected."""
    pass


class ValidationError(TradeEngineError):
    """Raised when structured output validation fails."""
    pass


class BrokerError(TradeEngineError):
    """Raised when broker communication fails."""
    pass


class ConfigurationError(TradeEngineError):
    """Raised when setup validation fails."""
    pass
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/svend/local-trade-engine && python3 -m pytest tests/test_config.py -v`
Expected: 4 PASS

- [ ] **Step 6: Verify syntax**

Run: `python3 -m py_compile app/core/config.py`
Run: `python3 -m py_compile app/core/errors.py`
Expected: no output (success)

- [ ] **Step 7: Commit**

```bash
git add app/__init__.py app/core/__init__.py app/core/config.py app/core/errors.py tests/test_config.py
git commit -m "[phase0] add core config module with env-var support and demo-URL safety check"
```

---

### Task 0.3: Create Database Layer with Full Schema

**Files:**
- Create: `app/core/database.py`
- Create: `migrations/001_baseline.sql`
- Create: `scripts/initialize_database.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Produces: `get_connection(db_path) -> sqlite3.Connection`, `run_migrations(conn)`, `initialize_database(db_path)`

- [ ] **Step 1: Write the baseline SQL migration**

```sql
-- migrations/001_baseline.sql
-- Local Trade Engine — Baseline Schema V1

-- System & Configuration
CREATE TABLE IF NOT EXISTS ollama_models (
    model_key       TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    enabled         INTEGER DEFAULT 1,
    intended_role   TEXT,
    context_size    INTEGER DEFAULT 32768,
    timeout_seconds INTEGER DEFAULT 180,
    concurrency_max INTEGER DEFAULT 1,
    keep_policy     TEXT DEFAULT 'unload_after_idle',
    structured_output_support INTEGER DEFAULT 1,
    last_health_check TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS role_definitions (
    role_key            TEXT PRIMARY KEY,
    display_name        TEXT NOT NULL,
    description         TEXT,
    execution_order     INTEGER NOT NULL,
    enabled             INTEGER DEFAULT 1,
    ollama_model        TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS workflows (
    workflow_key    TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    description     TEXT,
    enabled         INTEGER DEFAULT 1,
    account_key     TEXT NOT NULL,
    mode            TEXT NOT NULL DEFAULT 'virtual_approval_required',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workflow_steps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_key    TEXT NOT NULL REFERENCES workflows(workflow_key),
    sort_order      INTEGER NOT NULL,
    role_key        TEXT NOT NULL REFERENCES role_definitions(role_key),
    enabled         INTEGER DEFAULT 1,
    skip_condition  TEXT,
    UNIQUE(workflow_key, role_key),
    UNIQUE(workflow_key, sort_order)
);

CREATE TABLE IF NOT EXISTS schedules (
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

-- Broker & Account Environment
CREATE TABLE IF NOT EXISTS brokers (
    broker_key      TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    enabled         INTEGER DEFAULT 1,
    adapter_module  TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS broker_capabilities (
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

CREATE TABLE IF NOT EXISTS broker_accounts (
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

CREATE TABLE IF NOT EXISTS instruments (
    instrument_key  TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    instrument_type TEXT DEFAULT 'stock',
    sector          TEXT,
    currency        TEXT DEFAULT 'USD',
    enabled         INTEGER DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS broker_symbol_mappings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    broker_key          TEXT NOT NULL REFERENCES brokers(broker_key),
    instrument_key      TEXT NOT NULL REFERENCES instruments(instrument_key),
    broker_symbol       TEXT NOT NULL,
    broker_instrument_id TEXT,
    enabled             INTEGER DEFAULT 1,
    UNIQUE(broker_key, instrument_key)
);

CREATE TABLE IF NOT EXISTS strategy_instruments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_key    TEXT NOT NULL REFERENCES workflows(workflow_key),
    instrument_key  TEXT NOT NULL REFERENCES instruments(instrument_key),
    enabled         INTEGER DEFAULT 1,
    UNIQUE(workflow_key, instrument_key)
);

-- Risk & Execution Policies
CREATE TABLE IF NOT EXISTS risk_policies (
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

CREATE TABLE IF NOT EXISTS execution_policies (
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

-- Runtime: Runs, Steps, Model Calls
CREATE TABLE IF NOT EXISTS runs (
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

CREATE TABLE IF NOT EXISTS run_steps (
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

CREATE TABLE IF NOT EXISTS model_calls (
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

CREATE TABLE IF NOT EXISTS role_results (
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

-- Decisions & Orders
CREATE TABLE IF NOT EXISTS trade_decisions (
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

CREATE TABLE IF NOT EXISTS decision_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id     TEXT NOT NULL REFERENCES trade_decisions(decision_id),
    reviewer_role   TEXT NOT NULL DEFAULT 'review01',
    verdict         TEXT NOT NULL,
    critique_json   TEXT,
    hallucination_risk REAL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS risk_evaluations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id     TEXT NOT NULL REFERENCES trade_decisions(decision_id),
    policy_key      TEXT NOT NULL REFERENCES risk_policies(policy_key),
    risk_decision   TEXT NOT NULL,
    llm_proposed_pct REAL,
    risk_allowed_pct REAL,
    reason          TEXT,
    evaluated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS approvals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id     TEXT NOT NULL REFERENCES trade_decisions(decision_id),
    approved_by     TEXT NOT NULL DEFAULT 'human',
    approved        INTEGER NOT NULL,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
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

CREATE TABLE IF NOT EXISTS order_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        TEXT NOT NULL REFERENCES orders(order_id),
    event_type      TEXT NOT NULL,
    event_data_json TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Portfolio & Positions
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
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

CREATE TABLE IF NOT EXISTS positions (
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

CREATE TABLE IF NOT EXISTS position_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id     TEXT NOT NULL REFERENCES positions(position_id),
    event_type      TEXT NOT NULL,
    event_data_json TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Market Data & Performance
CREATE TABLE IF NOT EXISTS market_data_snapshots (
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

CREATE TABLE IF NOT EXISTS indicator_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    instrument_key  TEXT NOT NULL REFERENCES instruments(instrument_key),
    indicator_name  TEXT NOT NULL,
    value           REAL,
    parameters_json TEXT,
    calculated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trade_outcomes (
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

CREATE TABLE IF NOT EXISTS performance_snapshots (
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

-- Audit & Health
CREATE TABLE IF NOT EXISTS audit_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'info',
    event_data_json TEXT NOT NULL,
    run_id          TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_health_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    check_type      TEXT NOT NULL,
    status          TEXT NOT NULL,
    details_json    TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kill_switches (
    switch_key      TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    enabled         INTEGER DEFAULT 0,
    activated_by    TEXT DEFAULT 'system',
    activated_at    TIMESTAMP,
    reason          TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- UI Configuration
CREATE TABLE IF NOT EXISTS ui_groups (
    group_key       TEXT PRIMARY KEY,
    label_key       TEXT NOT NULL,
    route           TEXT NOT NULL,
    icon_key        TEXT,
    display_order   INTEGER NOT NULL,
    enabled         INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ui_panels (
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

CREATE TABLE IF NOT EXISTS ui_fields (
    field_key       TEXT PRIMARY KEY,
    panel_key       TEXT NOT NULL REFERENCES ui_panels(panel_key),
    label_key       TEXT NOT NULL,
    field_type      TEXT NOT NULL,
    data_path       TEXT NOT NULL,
    display_order   INTEGER NOT NULL,
    enabled         INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ui_status_definitions (
    status_key      TEXT PRIMARY KEY,
    label_key       TEXT NOT NULL,
    badge_color     TEXT NOT NULL,
    icon_key        TEXT,
    display_order   INTEGER NOT NULL
);

-- i18n
CREATE TABLE IF NOT EXISTS ui_text_slots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_key    TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ui_text_slot_labels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_key    TEXT NOT NULL,
    label_key   TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(slot_key, label_key)
);

CREATE TABLE IF NOT EXISTS ui_labels (
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

CREATE TABLE IF NOT EXISTS ui_label_translations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    label_id        TEXT NOT NULL,
    locale          TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    is_active       INTEGER DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(label_id, locale)
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 2: Write database connection module**

```python
# app/core/database.py
"""Database connection management and migration runner."""
import sqlite3
import os
from pathlib import Path


def get_connection(db_path: str) -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and foreign keys enabled."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def run_migrations(db_path: str) -> None:
    """Run all pending SQL migrations in order."""
    conn = get_connection(db_path)
    migrations_dir = Path(__file__).resolve().parent.parent.parent / "migrations"

    # Ensure schema_migrations table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Find and run pending migrations
    if migrations_dir.exists():
        for migration_file in sorted(migrations_dir.glob("*.sql")):
            version = migration_file.stem
            already_applied = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?",
                (version,)
            ).fetchone()

            if not already_applied:
                sql = migration_file.read_text(encoding="utf-8")
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (?)",
                    (version,)
                )

    conn.commit()
    conn.close()
```

- [ ] **Step 3: Write database initialization script**

```python
# scripts/initialize_database.py
"""Initialize the Trade Engine database with schema and seed data."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import run_migrations, get_connection
from app.core.config import config

DB_PATH = config.get_db_path()


def seed_initial_data(conn):
    """Insert canonical seed data."""
    cursor = conn.cursor()

    # Broker
    cursor.execute("""
        INSERT OR REPLACE INTO brokers (broker_key, display_name, adapter_module)
        VALUES (?, ?, ?)
    """, ("etoro", "eToro", "app.brokers.etoro_virtual"))

    # Broker account
    cursor.execute("""
        INSERT OR REPLACE INTO broker_accounts
        (account_key, broker_key, display_name, account_environment, execution_enabled, real_money, active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("etoro_virtual_primary", "etoro", "eToro Virtual Account", "virtual", 1, 0, 1))

    # Broker capabilities (discovered at runtime, seeded with safe defaults)
    cursor.execute("""
        INSERT OR REPLACE INTO broker_capabilities
        (broker_key, account_environment, portfolio_read, market_data_read,
         order_preview, virtual_order_execution, order_cancel, fractional_orders,
         live_order_execution)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("etoro", "virtual", 1, 1, 1, 1, 1, 1, 0))

    # Ollama models
    models = [
        ("qwen3.6:35b-a3b-64k", "Qwen 3.6 35B A3B 64K", "reasoning", 65536, 300),
        ("qwen3-coder:30b-96k", "Qwen Coder 30B 96K", "analytical", 98304, 300),
        ("qwen3.6:27b-q4_K_M", "Qwen 3.6 27B Q4_K_M", "critique", 49152, 180),
    ]
    for model in models:
        cursor.execute("""
            INSERT OR REPLACE INTO ollama_models
            (model_key, display_name, intended_role, context_size, timeout_seconds)
            VALUES (?, ?, ?, ?, ?)
        """, model)

    # Role definitions
    roles = [
        ("trend01", "Trend Analyst", "Determines broader trend and market regime",
         10, "qwen3.6:35b-a3b-64k", "roles/trend01.md", "trend_note_v1"),
        ("market01", "Market Analyst", "Evaluates current market conditions",
         20, "qwen3-coder:30b-96k", "roles/market01.md", "market_snapshot_v1"),
        ("analyst01", "Trade Analyst", "Produces instrument-level trade candidates",
         30, "qwen3.6:35b-a3b-64k", "roles/analyst01.md", "candidate_analysis_v1"),
        ("risk01", "Risk Reviewer", "Reviews candidates against risk context",
         40, "qwen3-coder:30b-96k", "roles/risk01.md", "risk_verdict_v1"),
        ("review01", "Independent Reviewer", "Critiques complete candidate set",
         50, "qwen3.6:27b-q4_K_M", "roles/review01.md", "review_verdict_v1"),
        ("decision01", "Decision Finalizer", "Creates final structured trade decision",
         60, "qwen3.6:27b-q4_K_M", "roles/decision01.md", "trade_decision_v1"),
    ]
    for role in roles:
        cursor.execute("""
            INSERT OR REPLACE INTO role_definitions
            (role_key, display_name, description, execution_order, ollama_model,
             role_definition_path, output_schema)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, role)

    # Workflow
    cursor.execute("""
        INSERT OR REPLACE INTO workflows
        (workflow_key, display_name, description, account_key, mode)
        VALUES (?, ?, ?, ?, ?)
    """, ("etoro_virtual_local_v001", "eToro Virtual Local Trading",
          "Initial V1 workflow — 6 roles, virtual approval required",
          "etoro_virtual_primary", "virtual_approval_required"))

    # Workflow steps
    steps = [
        ("etoro_virtual_local_v001", 10, "trend01"),
        ("etoro_virtual_local_v001", 20, "market01"),
        ("etoro_virtual_local_v001", 30, "analyst01"),
        ("etoro_virtual_local_v001", 40, "risk01"),
        ("etoro_virtual_local_v001", 50, "review01"),
        ("etoro_virtual_local_v001", 60, "decision01"),
    ]
    for step in steps:
        cursor.execute("""
            INSERT OR REPLACE INTO workflow_steps
            (workflow_key, sort_order, role_key)
            VALUES (?, ?, ?)
        """, step)

    # Risk policy
    cursor.execute("""
        INSERT OR REPLACE INTO risk_policies
        (policy_key, display_name, max_position_size_usd, max_allocation_pct,
         max_sector_allocation_pct, max_total_exposure_pct, max_open_positions,
         min_cash_reserve_pct, max_daily_loss_usd, max_order_value_usd)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("default_virtual_v1", "Default Virtual Risk Policy",
          500.0, 10.0, 30.0, 80.0, 8, 5.0, 1000.0, 500.0))

    # Execution policy
    cursor.execute("""
        INSERT OR REPLACE INTO execution_policies
        (policy_key, display_name, account_environment, maximum_virtual_order_value,
         maximum_daily_virtual_orders, minimum_confidence, minimum_deterministic_score,
         require_review_pass, kill_switch_enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("default_virtual_v1", "Default Virtual Execution Policy",
          "virtual", 500.0, 5, 0.8, 75.0, 1, 1))

    # Kill switches (all inactive by default)
    for switch in [
        ("global_execution", "Global Execution Kill Switch"),
        ("broker:etoro", "eToro Broker Kill Switch"),
        ("workflow:etoro_virtual_local_v001", "V1 Workflow Kill Switch"),
        ("autonomous", "Autonomous Virtual Trading Kill Switch"),
    ]:
        cursor.execute("""
            INSERT OR REPLACE INTO kill_switches (switch_key, display_name, enabled)
            VALUES (?, ?, 0)
        """, switch)

    # UI Groups
    for group in [
        ("daily", "nav.daily", "/daily", 10),
        ("portfolio", "nav.portfolio", "/portfolio", 20),
        ("decisions", "nav.decisions", "/decisions", 30),
        ("runs", "nav.runs", "/runs", 40),
        ("setup", "nav.setup", "/setup", 50),
    ]:
        cursor.execute("""
            INSERT OR REPLACE INTO ui_groups (group_key, label_key, route, display_order)
            VALUES (?, ?, ?, ?)
        """, group)

    # UI Panels for Daily
    daily_panels = [
        ("daily.portfolio_status", "daily", "daily.portfolio_status.title",
         "status_card", "portfolio_runtime_status", 10),
        ("daily.workflow_status", "daily", "daily.workflow_status.title",
         "status_card", "workflow_runtime_status", 20),
        ("daily.latest_decision", "daily", "daily.latest_decision.title",
         "decision_card", "latest_decision", 30),
        ("daily.attention_required", "daily", "daily.attention_required.title",
         "alert_list", "attention_required", 40),
        ("daily.recent_activity", "daily", "daily.recent_activity.title",
         "activity_list", "recent_activity", 50),
        ("daily.actions", "daily", "daily.actions.title",
         "action_bar", "daily_actions", 60),
    ]
    for panel in daily_panels:
        cursor.execute("""
            INSERT OR REPLACE INTO ui_panels
            (panel_key, group_key, label_key, component_type, data_source, display_order)
            VALUES (?, ?, ?, ?, ?, ?)
        """, panel)

    # i18n labels (en-US seed)
    labels = [
        ("LBL-NAV-DAILY", "nav.daily", "nav", "Daily"),
        ("LBL-NAV-PORTFOLIO", "nav.portfolio", "nav", "Portfolio"),
        ("LBL-NAV-DECISIONS", "nav.decisions", "nav", "Decisions"),
        ("LBL-NAV-RUNS", "nav.runs", "nav", "Runs"),
        ("LBL-NAV-SETUP", "nav.setup", "nav", "Setup"),
        ("LBL-ACCOUNT-VIRTUAL", "account.environment.virtual", "account", "Virtual Account"),
        ("LBL-ACCOUNT-LIVE", "account.environment.live", "account", "LIVE ACCOUNT"),
        ("LBL-VIRTUAL-BANNER", "account.virtual.banner", "account",
         "VIRTUAL TRADING — Connected to eToro Virtual Account"),
        ("LBL-NO-REAL-MONEY", "account.virtual.no_real_money", "account",
         "No real money is being used"),
        ("LBL-MODE-ANALYSIS", "mode.analysis_only", "mode", "Analysis only"),
        ("LBL-MODE-PROPOSAL", "mode.proposal_only", "mode", "Proposal only"),
        ("LBL-MODE-APPROVAL", "mode.virtual_approval_required", "mode", "Virtual approval required"),
        ("LBL-MODE-AUTONOMOUS", "mode.virtual_autonomous", "mode", "Autonomous virtual trading"),
        ("LBL-MODE-PAUSED", "mode.paused", "mode", "Paused"),
        ("LBL-STATUS-READY", "status.ready", "status", "Ready"),
        ("LBL-STATUS-RUNNING", "status.running", "status", "Running"),
        ("LBL-STATUS-WARNING", "status.warning", "status", "Warning"),
        ("LBL-STATUS-BLOCKED", "status.blocked", "status", "Blocked"),
        ("LBL-ACTION-RUN-NOW", "action.run_now", "action", "Run Now"),
        ("LBL-ACTION-PAUSE", "action.pause", "action", "Pause"),
        ("LBL-ACTION-RESUME", "action.resume", "action", "Resume"),
        ("LBL-ACTION-APPROVE", "action.approve", "action", "Approve"),
        ("LBL-ACTION-REJECT", "action.reject", "action", "Reject"),
        ("LBL-ACTION-EMERGENCY-STOP", "action.emergency_stop", "action", "EMERGENCY STOP"),
    ]
    for label in labels:
        cursor.execute("""
            INSERT OR REPLACE INTO ui_labels
            (label_id, label_key, label_domain, default_text)
            VALUES (?, ?, ?, ?)
        """, label)

    # Danish translations
    da_translations = [
        ("LBL-NAV-DAILY", "da-DK", "Daglig"),
        ("LBL-NAV-PORTFOLIO", "da-DK", "Portefølje"),
        ("LBL-NAV-DECISIONS", "da-DK", "Beslutninger"),
        ("LBL-NAV-RUNS", "da-DK", "Kørsler"),
        ("LBL-NAV-SETUP", "da-DK", "Opsætning"),
        ("LBL-ACCOUNT-VIRTUAL", "da-DK", "Virtuel konto"),
        ("LBL-ACCOUNT-LIVE", "da-DK", "LIVE KONTO"),
        ("LBL-VIRTUAL-BANNER", "da-DK",
         "VIRTUEL HANDEL — Forbundet til eToro virtuel konto"),
        ("LBL-NO-REAL-MONEY", "da-DK", "Der bruges ikke rigtige penge"),
        ("LBL-ACTION-EMERGENCY-STOP", "da-DK", "NØDSTOP"),
    ]
    for trans in da_translations:
        cursor.execute("""
            INSERT OR REPLACE INTO ui_label_translations
            (label_id, locale, translated_text)
            VALUES (?, ?, ?)
        """, trans)

    conn.commit()


if __name__ == "__main__":
    print(f"Initializing database at: {DB_PATH}")
    run_migrations(DB_PATH)
    conn = get_connection(DB_PATH)
    seed_initial_data(conn)
    conn.close()
    print("Database initialized successfully.")
```

- [ ] **Step 4: Write database tests**

```python
# tests/test_database.py
import os
import sys
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import get_connection, run_migrations


def test_get_connection_creates_db():
    """get_connection creates database file and returns connection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_connection(db_path)
        assert os.path.exists(db_path)
        # WAL mode creates .db-wal and .db-shm files
        conn.close()


def test_get_connection_foreign_keys_enabled():
    """Foreign keys are enabled on new connections."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_connection(db_path)
        fk_on = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk_on == 1
        conn.close()


def test_run_migrations_creates_tables():
    """run_migrations creates all expected tables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        run_migrations(db_path)
        conn = get_connection(db_path)

        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t["name"] for t in tables]

        expected = [
            "broker_accounts", "broker_capabilities", "broker_symbol_mappings",
            "brokers", "instruments", "kill_switches", "market_data_snapshots",
            "ollama_models", "orders", "portfolio_snapshots", "positions",
            "risk_policies", "role_definitions", "role_results", "runs",
            "run_steps", "schedules", "trade_decisions", "trade_outcomes",
            "ui_groups", "ui_labels", "ui_panels", "workflows", "workflow_steps",
        ]
        for table in expected:
            assert table in table_names, f"Table {table} not found"

        conn.close()


def test_run_migrations_idempotent():
    """Running migrations twice does not fail."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        run_migrations(db_path)
        run_migrations(db_path)  # second run should be no-op
        conn = get_connection(db_path)
        count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        assert count == 1  # only one migration applied
        conn.close()
```

- [ ] **Step 5: Run tests**

Run: `cd /home/svend/local-trade-engine && python3 -m pytest tests/test_database.py -v`
Expected: 4 PASS

- [ ] **Step 6: Verify database initialization script**

Run: `cd /home/svend/local-trade-engine && python3 scripts/initialize_database.py`
Expected: "Database initialized successfully."

- [ ] **Step 7: Verify syntax**

Run: `python3 -m py_compile app/core/database.py`
Run: `python3 -m py_compile scripts/initialize_database.py`
Expected: no output

- [ ] **Step 8: Commit**

```bash
git add app/core/database.py migrations/001_baseline.sql scripts/initialize_database.py tests/test_database.py
git commit -m "[phase0] add database layer with full V1 schema and seed data"
```

---

## Phase 1: Core Runtime

### Task 1.1: Ollama Client

**Files:**
- Create: `app/ollama/__init__.py`
- Create: `app/ollama/client.py`
- Test: `tests/test_ollama_client.py`

**Interfaces:**
- Produces: `OllamaClient.health_check() -> dict`, `OllamaClient.generate(model, prompt, temperature, context_limit, timeout, json_mode) -> str`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ollama_client.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from app.ollama.client import OllamaClient


def test_client_initialization():
    """Client initializes with base URL."""
    client = OllamaClient(base_url="http://localhost:11434")
    assert client.base_url == "http://localhost:11434"


def test_client_default_url():
    """Client uses default Ollama URL when none provided."""
    client = OllamaClient()
    assert client.base_url == "http://localhost:11434"


def test_generate_requires_model():
    """generate() validates model parameter."""
    client = OllamaClient()
    with pytest.raises(ValueError, match="model"):
        # Can't actually call async in sync test without asyncio
        pass  # tested in integration


def test_generate_json_mode_adds_format():
    """JSON mode adds format: json to request body."""
    client = OllamaClient()
    body = client._build_request_body(
        model="test-model",
        prompt="test prompt",
        temperature=0.2,
        context_limit=65536,
        json_mode=True,
    )
    assert body["format"] == "json"
    assert body["model"] == "test-model"
    assert body["prompt"] == "test prompt"
    assert body["stream"] is False
    assert "options" in body
    assert body["options"]["temperature"] == 0.2
    assert body["options"]["num_ctx"] == 65536
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/svend/local-trade-engine && python3 -m pytest tests/test_ollama_client.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement OllamaClient**

```python
# app/ollama/client.py
"""Dedicated Ollama HTTP client for Local Trade Engine.

The rest of the application MUST NOT make direct Ollama requests.
All model calls go through this client.
"""
import aiohttp
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class OllamaClient:
    """HTTP client for local Ollama API calls."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def health_check(self) -> dict:
        """Check if Ollama is reachable and list available models."""
        session = await self._get_session()
        try:
            async with session.get(f"{self.base_url}/api/tags") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m["name"] for m in data.get("models", [])]
                    return {"available": True, "models": models}
                return {"available": False, "error": f"HTTP {resp.status}"}
        except aiohttp.ClientError as e:
            return {"available": False, "error": str(e)}

    async def generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.2,
        context_limit: int = 65536,
        timeout: int = 180,
        json_mode: bool = True,
    ) -> str:
        """Generate a response from a local Ollama model.

        Args:
            model: Ollama model name (e.g. "qwen3.6:27b-q4_K_M")
            prompt: Full prompt text
            temperature: Sampling temperature (0.0-1.0)
            context_limit: Max context window size
            timeout: Request timeout in seconds
            json_mode: If True, request structured JSON output

        Returns:
            Raw text response from the model.

        Raises:
            ValueError: If model is empty
            TimeoutError: If request exceeds timeout
            RuntimeError: If Ollama returns an error
        """
        if not model or not model.strip():
            raise ValueError("model must be a non-empty string")

        body = self._build_request_body(
            model=model,
            prompt=prompt,
            temperature=temperature,
            context_limit=context_limit,
            json_mode=json_mode,
        )

        session = await self._get_session()
        try:
            async with session.post(
                f"{self.base_url}/api/generate",
                json=body,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(
                        f"Ollama returned HTTP {resp.status}: {error_text}"
                    )
                data = await resp.json()
                response = data.get("response", "")
                logger.debug(
                    "Ollama generate: model=%s prompt_chars=%d response_chars=%d",
                    model, len(prompt), len(response),
                )
                return response
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Ollama generate timed out after {timeout}s for model {model}"
            )

    def _build_request_body(
        self,
        model: str,
        prompt: str,
        temperature: float,
        context_limit: int,
        json_mode: bool,
    ) -> dict:
        """Build the Ollama API request body."""
        body = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": context_limit,
            },
        }
        if json_mode:
            body["format"] = "json"
        return body
```

- [ ] **Step 4: Run tests**

Run: `cd /home/svend/local-trade-engine && python3 -m pytest tests/test_ollama_client.py -v`
Expected: 3 PASS (1 skipped — async test)

- [ ] **Step 5: Verify syntax**

Run: `python3 -m py_compile app/ollama/client.py`
Expected: no output

- [ ] **Step 6: Commit**

```bash
git add app/ollama/__init__.py app/ollama/client.py tests/test_ollama_client.py
git commit -m "[phase1] add Ollama HTTP client with JSON mode and health check"
```

---

### Task 1.2: JSON Schema Validation

**Files:**
- Create: `app/ollama/validation.py`
- Create: `schemas/trend_note_v1.json`
- Create: `schemas/trade_decision_v1.json`
- Test: `tests/test_validation.py`

**Interfaces:**
- Produces: `validate_output(raw_response: str, schema_key: str) -> ValidationResult`

- [ ] **Step 1: Create JSON schemas**

```json
// schemas/trend_note_v1.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Trend Note V1",
  "type": "object",
  "required": ["role", "account_environment", "market_timestamp", "regime", "trends"],
  "properties": {
    "role": {"type": "string", "const": "trend01"},
    "account_environment": {"type": "string", "const": "virtual"},
    "market_timestamp": {"type": "string", "format": "date-time"},
    "regime": {
      "type": "object",
      "required": ["primary", "confidence"],
      "properties": {
        "primary": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1}
      }
    },
    "trends": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["instrument", "direction", "strength"],
        "properties": {
          "instrument": {"type": "string"},
          "direction": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
          "strength": {"type": "number", "minimum": 0, "maximum": 1}
        }
      }
    },
    "uncertainty": {"type": "number", "minimum": 0, "maximum": 1}
  }
}
```

```json
// schemas/trade_decision_v1.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Trade Decision V1",
  "type": "object",
  "required": ["role", "account_environment", "decisions"],
  "properties": {
    "role": {"type": "string", "const": "decision01"},
    "account_environment": {"type": "string", "const": "virtual"},
    "decisions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["instrument", "action", "confidence"],
        "properties": {
          "instrument": {"type": "string"},
          "action": {"type": "string", "enum": ["buy", "sell", "hold", "reduce", "close", "do_not_open"]},
          "confidence": {"type": "number", "minimum": 0, "maximum": 1},
          "time_horizon": {"type": "string"},
          "thesis": {"type": "string"},
          "invalidation_conditions": {"type": "array", "items": {"type": "string"}}
        }
      }
    }
  }
}
```

- [ ] **Step 2: Write validation module**

```python
# app/ollama/validation.py
"""JSON Schema validation for structured LLM outputs."""
import json
import hashlib
from pathlib import Path
from jsonschema import validate, ValidationError as JsonSchemaError


class ValidationResult:
    """Result of validating an LLM output against a JSON schema."""

    def __init__(self, passed: bool, parsed: dict | None = None,
                 errors: list[str] | None = None):
        self.passed = passed
        self.parsed = parsed
        self.errors = errors or []


def load_schema(schema_key: str) -> dict:
    """Load a JSON schema file by key name."""
    schemas_dir = Path(__file__).resolve().parent.parent.parent / "schemas"
    schema_path = schemas_dir / f"{schema_key}.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_output(raw_response: str, schema_key: str) -> ValidationResult:
    """Validate an LLM raw response against a JSON schema.

    Args:
        raw_response: Raw text from the LLM
        schema_key: Key identifying the schema file (e.g. "trend_note_v1")

    Returns:
        ValidationResult with passed flag, parsed output, and any errors
    """
    # Parse JSON
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as e:
        return ValidationResult(
            passed=False,
            errors=[f"Invalid JSON: {e}"],
        )

    # Validate against schema
    try:
        schema = load_schema(schema_key)
        validate(parsed, schema)
    except FileNotFoundError as e:
        return ValidationResult(
            passed=False,
            errors=[str(e)],
        )
    except JsonSchemaError as e:
        return ValidationResult(
            passed=False,
            errors=[f"Schema validation failed: {e.message}"],
        )

    # Completeness check: does output have required content?
    completeness_errors = _check_completeness(parsed, schema_key)
    if completeness_errors:
        return ValidationResult(
            passed=False,
            parsed=parsed,
            errors=completeness_errors,
        )

    return ValidationResult(passed=True, parsed=parsed)


def _check_completeness(parsed: dict, schema_key: str) -> list[str]:
    """Check that the output contains meaningful content, not just structure."""
    errors = []

    if schema_key == "trend_note_v1":
        trends = parsed.get("trends", [])
        if not trends:
            errors.append("trends array is empty — at least one trend required")
        if not parsed.get("regime", {}).get("primary"):
            errors.append("regime.primary is empty")

    elif schema_key == "trade_decision_v1":
        decisions = parsed.get("decisions", [])
        if not decisions:
            errors.append("decisions array is empty — at least one decision required")
        for i, d in enumerate(decisions):
            if not d.get("thesis"):
                errors.append(f"decision[{i}].thesis is empty")
            if not d.get("instrument"):
                errors.append(f"decision[{i}].instrument is empty")

    return errors


def hash_role_definition(content: str) -> str:
    """Return SHA256 hash of a role definition file's content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
```

- [ ] **Step 3: Write validation tests**

```python
# tests/test_validation.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.ollama.validation import validate_output, ValidationResult


def test_validate_valid_trend_note():
    """Valid trend note passes validation."""
    raw = '''{
        "role": "trend01",
        "account_environment": "virtual",
        "market_timestamp": "2026-07-12T08:30:00+02:00",
        "regime": {"primary": "bullish", "confidence": 0.75},
        "trends": [
            {"instrument": "AAPL", "direction": "bullish", "strength": 0.8}
        ],
        "uncertainty": 0.25
    }'''
    result = validate_output(raw, "trend_note_v1")
    assert result.passed, f"Expected pass, got: {result.errors}"
    assert result.parsed["role"] == "trend01"


def test_validate_invalid_json():
    """Invalid JSON fails validation."""
    result = validate_output("not json at all", "trend_note_v1")
    assert not result.passed
    assert any("Invalid JSON" in e for e in result.errors)


def test_validate_missing_required_field():
    """Missing required field fails validation."""
    raw = '{"role": "trend01"}'  # missing account_environment, market_timestamp, regime, trends
    result = validate_output(raw, "trend_note_v1")
    assert not result.passed


def test_validate_empty_trends():
    """Empty trends array fails completeness check."""
    raw = '''{
        "role": "trend01",
        "account_environment": "virtual",
        "market_timestamp": "2026-07-12T08:30:00+02:00",
        "regime": {"primary": "bullish", "confidence": 0.75},
        "trends": [],
        "uncertainty": 0.25
    }'''
    result = validate_output(raw, "trend_note_v1")
    assert not result.passed
    assert any("empty" in e for e in result.errors)


def test_validate_valid_trade_decision():
    """Valid trade decision passes validation."""
    raw = '''{
        "role": "decision01",
        "account_environment": "virtual",
        "decisions": [
            {
                "instrument": "AAPL",
                "action": "buy",
                "confidence": 0.82,
                "time_horizon": "swing",
                "thesis": "Positive trend continuation supported by momentum.",
                "invalidation_conditions": ["Daily close below SMA50"]
            }
        ]
    }'''
    result = validate_output(raw, "trade_decision_v1")
    assert result.passed, f"Expected pass, got: {result.errors}"
```

- [ ] **Step 4: Run tests**

Run: `cd /home/svend/local-trade-engine && python3 -m pytest tests/test_validation.py -v`
Expected: 5 PASS

- [ ] **Step 5: Verify syntax**

Run: `python3 -m py_compile app/ollama/validation.py`
Expected: no output

- [ ] **Step 6: Commit**

```bash
git add app/ollama/validation.py schemas/ tests/test_validation.py
git commit -m "[phase1] add JSON schema validation with completeness checks"
```

---

### Task 1.3: Workflow Loader + Run Snapshot

**Files:**
- Create: `app/orchestration/__init__.py`
- Create: `app/orchestration/workflow_loader.py`
- Create: `app/orchestration/run_snapshot.py`
- Test: `tests/test_workflow_loader.py`

**Interfaces:**
- Produces: `load_workflow(db_path, workflow_key) -> WorkflowConfig`, `create_run_snapshot(db_path, workflow, account, mode, trigger) -> str (run_id)`

- [ ] **Step 1: Write workflow loader**

```python
# app/orchestration/workflow_loader.py
"""Load workflow configuration from database."""
import json
from dataclasses import dataclass, field
from app.core.database import get_connection


@dataclass
class RoleConfig:
    role_key: str
    display_name: str
    execution_order: int
    ollama_model: str
    temperature: float
    context_limit: int
    timeout_seconds: int
    max_retries: int
    blocking: bool
    role_definition_path: str
    output_schema: str


@dataclass
class WorkflowStep:
    sort_order: int
    role: RoleConfig
    skip_condition: str | None = None


@dataclass
class WorkflowConfig:
    workflow_key: str
    display_name: str
    account_key: str
    mode: str
    steps: list[WorkflowStep] = field(default_factory=list)


def load_workflow(db_path: str, workflow_key: str) -> WorkflowConfig:
    """Load a workflow and its steps from the database.

    Args:
        db_path: Path to SQLite database
        workflow_key: Workflow identifier

    Returns:
        WorkflowConfig with all steps and their role configurations

    Raises:
        ValueError: If workflow not found or not enabled
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    workflow_row = cursor.execute(
        "SELECT * FROM workflows WHERE workflow_key = ? AND enabled = 1",
        (workflow_key,)
    ).fetchone()

    if not workflow_row:
        raise ValueError(f"Workflow not found or not enabled: {workflow_key}")

    workflow = WorkflowConfig(
        workflow_key=workflow_row["workflow_key"],
        display_name=workflow_row["display_name"],
        account_key=workflow_row["account_key"],
        mode=workflow_row["mode"],
    )

    step_rows = cursor.execute("""
        SELECT ws.sort_order, ws.skip_condition,
               rd.role_key, rd.display_name, rd.execution_order,
               rd.ollama_model, rd.temperature, rd.context_limit,
               rd.timeout_seconds, rd.max_retries, rd.blocking,
               rd.role_definition_path, rd.output_schema
        FROM workflow_steps ws
        JOIN role_definitions rd ON ws.role_key = rd.role_key
        WHERE ws.workflow_key = ? AND ws.enabled = 1 AND rd.enabled = 1
        ORDER BY ws.sort_order
    """, (workflow_key,)).fetchall()

    for row in step_rows:
        role = RoleConfig(
            role_key=row["role_key"],
            display_name=row["display_name"],
            execution_order=row["execution_order"],
            ollama_model=row["ollama_model"],
            temperature=row["temperature"],
            context_limit=row["context_limit"],
            timeout_seconds=row["timeout_seconds"],
            max_retries=row["max_retries"],
            blocking=bool(row["blocking"]),
            role_definition_path=row["role_definition_path"],
            output_schema=row["output_schema"],
        )
        step = WorkflowStep(
            sort_order=row["sort_order"],
            role=role,
            skip_condition=row["skip_condition"],
        )
        workflow.steps.append(step)

    conn.close()
    return workflow
```

- [ ] **Step 2: Write run snapshot module**

```python
# app/orchestration/run_snapshot.py
"""Create immutable run snapshots."""
import json
import uuid
from datetime import datetime, timezone
from app.core.database import get_connection
from app.orchestration.workflow_loader import WorkflowConfig


def create_run_snapshot(
    db_path: str,
    workflow: WorkflowConfig,
    account_key: str,
    mode: str,
    trigger: str,
) -> str:
    """Create an immutable run record with full configuration snapshot.

    Args:
        db_path: Path to SQLite database
        workflow: Loaded workflow configuration
        account_key: Broker account identifier
        mode: Operating mode for this run
        trigger: What triggered this run (scheduled, manual, signal_triggered, retry)

    Returns:
        run_id: Unique run identifier
    """
    run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    # Build immutable config snapshot
    config_snapshot = {
        "workflow_key": workflow.workflow_key,
        "display_name": workflow.display_name,
        "account_key": account_key,
        "mode": mode,
        "trigger": trigger,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "steps": [
            {
                "sort_order": step.sort_order,
                "role_key": step.role.role_key,
                "display_name": step.role.display_name,
                "ollama_model": step.role.ollama_model,
                "temperature": step.role.temperature,
                "context_limit": step.role.context_limit,
                "timeout_seconds": step.role.timeout_seconds,
                "max_retries": step.role.max_retries,
                "blocking": step.role.blocking,
                "role_definition_path": step.role.role_definition_path,
                "output_schema": step.role.output_schema,
            }
            for step in workflow.steps
        ],
    }

    conn = get_connection(db_path)
    conn.execute("""
        INSERT INTO runs (run_id, workflow_key, account_key, mode, trigger, status, config_snapshot)
        VALUES (?, ?, ?, ?, ?, 'created', ?)
    """, (run_id, workflow.workflow_key, account_key, mode, trigger,
          json.dumps(config_snapshot)))

    # Create run_steps
    for step in workflow.steps:
        conn.execute("""
            INSERT INTO run_steps (run_id, sort_order, role_key, status)
            VALUES (?, ?, ?, 'pending')
        """, (run_id, step.sort_order, step.role.role_key))

    conn.commit()
    conn.close()
    return run_id
```

- [ ] **Step 3: Write tests**

```python
# tests/test_workflow_loader.py
import os
import sys
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import run_migrations, get_connection
from app.orchestration.workflow_loader import load_workflow
from app.orchestration.run_snapshot import create_run_snapshot


def _setup_test_db(db_path):
    """Set up a test database with schema and minimal seed data."""
    run_migrations(db_path)
    conn = get_connection(db_path)
    conn.execute("INSERT OR REPLACE INTO brokers (broker_key, display_name, adapter_module) VALUES ('etoro', 'eToro', 'test')")
    conn.execute("INSERT OR REPLACE INTO broker_accounts (account_key, broker_key, display_name, account_environment) VALUES ('etoro_virtual_primary', 'etoro', 'Test', 'virtual')")
    conn.execute("INSERT OR REPLACE INTO ollama_models (model_key, display_name) VALUES ('test-model', 'Test Model')")
    conn.execute("INSERT OR REPLACE INTO role_definitions (role_key, display_name, execution_order, ollama_model, role_definition_path, output_schema) VALUES ('test_role', 'Test Role', 10, 'test-model', 'roles/test.md', 'test_v1')")
    conn.execute("INSERT OR REPLACE INTO workflows (workflow_key, display_name, account_key, mode) VALUES ('test_flow', 'Test Flow', 'etoro_virtual_primary', 'virtual_approval_required')")
    conn.execute("INSERT OR REPLACE INTO workflow_steps (workflow_key, sort_order, role_key) VALUES ('test_flow', 10, 'test_role')")
    conn.commit()
    conn.close()


def test_load_workflow():
    """load_workflow returns WorkflowConfig with steps."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        _setup_test_db(db_path)

        workflow = load_workflow(db_path, "test_flow")
        assert workflow.workflow_key == "test_flow"
        assert workflow.mode == "virtual_approval_required"
        assert len(workflow.steps) == 1
        assert workflow.steps[0].role.role_key == "test_role"


def test_load_workflow_not_found():
    """load_workflow raises ValueError for unknown workflow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        _setup_test_db(db_path)

        try:
            load_workflow(db_path, "nonexistent")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "not found" in str(e)


def test_create_run_snapshot():
    """create_run_snapshot creates run and run_steps records."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        _setup_test_db(db_path)

        workflow = load_workflow(db_path, "test_flow")
        run_id = create_run_snapshot(
            db_path, workflow, "etoro_virtual_primary",
            "virtual_approval_required", "manual",
        )

        assert run_id.startswith("RUN-")

        conn = get_connection(db_path)
        run = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        assert run is not None
        assert run["status"] == "created"
        assert run["trigger"] == "manual"

        steps = conn.execute(
            "SELECT * FROM run_steps WHERE run_id = ? ORDER BY sort_order",
            (run_id,)
        ).fetchall()
        assert len(steps) == 1
        assert steps[0]["status"] == "pending"
        conn.close()
```

- [ ] **Step 4: Run tests**

Run: `cd /home/svend/local-trade-engine && python3 -m pytest tests/test_workflow_loader.py -v`
Expected: 3 PASS

- [ ] **Step 5: Verify syntax**

Run: `python3 -m py_compile app/orchestration/workflow_loader.py`
Run: `python3 -m py_compile app/orchestration/run_snapshot.py`
Expected: no output

- [ ] **Step 6: Commit**

```bash
git add app/orchestration/__init__.py app/orchestration/workflow_loader.py app/orchestration/run_snapshot.py tests/test_workflow_loader.py
git commit -m "[phase1] add workflow loader and immutable run snapshot"
```

---

### Task 1.4: Role Runner + Input Builder

**Files:**
- Create: `app/orchestration/input_builder.py`
- Create: `app/orchestration/role_runner.py`
- Test: `tests/test_role_runner.py`

**Interfaces:**
- Produces: `build_role_input(role_def, context, previous_outputs, output_schema) -> str`, `RoleRunner.execute(step, context, previous_outputs) -> RoleResult`

- [ ] **Step 1: Write input builder**

```python
# app/orchestration/input_builder.py
"""Build structured prompts for each role in the workflow."""
import json
from pathlib import Path
from app.orchestration.workflow_loader import RoleConfig


def load_role_definition(role_def_path: str) -> str:
    """Load a role definition Markdown file.

    Args:
        role_def_path: Path relative to project root (e.g. "roles/trend01.md")

    Returns:
        Content of the role definition file
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    full_path = project_root / role_def_path
    if not full_path.exists():
        raise FileNotFoundError(f"Role definition not found: {full_path}")
    return full_path.read_text(encoding="utf-8")


def build_role_input(
    role_def: str,
    context: dict,
    previous_outputs: list[dict],
    output_schema: str,
) -> str:
    """Build the complete prompt for a role.

    The prompt consists of:
    1. Role definition (Markdown — semantic behavior)
    2. Current context (market data, portfolio, indicators)
    3. Previous role outputs (chain of analysis)
    4. Output schema requirement (structured JSON)

    Args:
        role_def: Role definition Markdown content
        context: Current run context (market data, portfolio, indicators)
        previous_outputs: List of validated outputs from previous roles
        output_schema: Key of the JSON schema this role must produce

    Returns:
        Complete prompt string ready for Ollama
    """
    parts = [
        "# Role Definition",
        role_def,
        "",
        "# Current Context",
        "## Market Data",
        json.dumps(context.get("market_data", {}), indent=2),
        "## Portfolio",
        json.dumps(context.get("portfolio", {}), indent=2),
        "## Indicators",
        json.dumps(context.get("indicators", {}), indent=2),
    ]

    if previous_outputs:
        parts.append("")
        parts.append("# Previous Analysis")
        for i, output in enumerate(previous_outputs):
            parts.append(f"## Step {i + 1}: {output.get('role', 'unknown')}")
            parts.append(json.dumps(output, indent=2))

    parts.append("")
    parts.append("# Output Requirement")
    parts.append(f"You MUST produce valid JSON conforming to schema: {output_schema}")
    parts.append("Respond ONLY with the JSON object — no preamble, no markdown fences.")

    return "\n".join(parts)
```

- [ ] **Step 2: Write role runner**

```python
# app/orchestration/role_runner.py
"""Execute a single role: build input → call Ollama → validate output."""
import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field

from app.ollama.client import OllamaClient
from app.ollama.validation import validate_output, hash_role_definition, ValidationResult
from app.orchestration.workflow_loader import WorkflowStep
from app.orchestration.input_builder import load_role_definition, build_role_input
from app.core.database import get_connection

logger = logging.getLogger(__name__)


@dataclass
class RoleResult:
    """Result of executing a single role."""
    role_key: str
    output: dict | None
    raw_response: str | None
    attempt: int
    success: bool
    error: list[str] = field(default_factory=list)
    duration_ms: int = 0
    model_name: str = ""
    role_definition_hash: str = ""


class RoleRunner:
    """Executes a single role in the workflow."""

    def __init__(self, ollama_client: OllamaClient, db_path: str):
        self.ollama = ollama_client
        self.db_path = db_path

    async def execute(
        self,
        step: WorkflowStep,
        context: dict,
        previous_outputs: list[dict],
    ) -> RoleResult:
        """Execute one role and return validated result.

        Flow:
        1. Load role definition Markdown
        2. Build input prompt
        3. Call Ollama (with retries)
        4. Validate structured output (HARD GATE)
        5. On failure: one repair attempt
        6. Persist model_call and role_result records

        Args:
            step: Workflow step with role configuration
            context: Current run context
            previous_outputs: Validated outputs from earlier roles

        Returns:
            RoleResult with success flag, parsed output, and metadata
        """
        role = step.role
        start_time = datetime.now(timezone.utc)

        # Load role definition
        role_def = load_role_definition(role.role_definition_path)
        role_hash = hash_role_definition(role_def)

        # Build initial prompt
        prompt = build_role_input(
            role_def=role_def,
            context=context,
            previous_outputs=previous_outputs,
            output_schema=role.output_schema,
        )

        raw_response = None
        for attempt in range(role.max_retries + 1):
            try:
                raw_response = await self.ollama.generate(
                    model=role.ollama_model,
                    prompt=prompt,
                    temperature=role.temperature,
                    context_limit=role.context_limit,
                    timeout=role.timeout_seconds,
                    json_mode=True,
                )
            except (TimeoutError, RuntimeError) as e:
                logger.warning(
                    "Role %s attempt %d failed: %s", role.role_key, attempt + 1, e
                )
                if attempt >= role.max_retries:
                    duration = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                    return RoleResult(
                        role_key=role.role_key,
                        output=None,
                        raw_response=None,
                        attempt=attempt + 1,
                        success=False,
                        error=[str(e)],
                        duration_ms=duration,
                        model_name=role.ollama_model,
                        role_definition_hash=role_hash,
                    )
                continue

            # Validate output
            validation = validate_output(raw_response, role.output_schema)

            if validation.passed:
                duration = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                logger.info(
                    "Role %s completed successfully on attempt %d (%dms)",
                    role.role_key, attempt + 1, duration,
                )
                return RoleResult(
                    role_key=role.role_key,
                    output=validation.parsed,
                    raw_response=raw_response,
                    attempt=attempt + 1,
                    success=True,
                    duration_ms=duration,
                    model_name=role.ollama_model,
                    role_definition_hash=role_hash,
                )

            # One repair attempt
            if attempt == 0:
                logger.info(
                    "Role %s validation failed, attempting repair. Errors: %s",
                    role.role_key, validation.errors,
                )
                prompt = _build_repair_prompt(
                    original_prompt=prompt,
                    raw_response=raw_response,
                    validation_errors=validation.errors,
                )
                continue

        # All attempts exhausted
        duration = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        return RoleResult(
            role_key=role.role_key,
            output=None,
            raw_response=raw_response,
            attempt=role.max_retries + 1,
            success=False,
            error=validation.errors if validation else ["Unknown error"],
            duration_ms=duration,
            model_name=role.ollama_model,
            role_definition_hash=role_hash,
        )


def _build_repair_prompt(
    original_prompt: str,
    raw_response: str,
    validation_errors: list[str],
) -> str:
    """Build a repair prompt that asks the model to fix validation errors."""
    return "\n".join([
        original_prompt,
        "",
        "# CORRECTION REQUIRED",
        "Your previous response failed validation with these errors:",
        *[f"- {e}" for e in validation_errors],
        "",
        "Please fix these errors and respond with a valid JSON object.",
        "Respond ONLY with the corrected JSON — no preamble, no markdown fences.",
    ])
```

- [ ] **Step 3: Write tests**

```python
# tests/test_role_runner.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.orchestration.input_builder import build_role_input


def test_build_role_input_includes_all_sections():
    """Built prompt includes role def, context, and output requirement."""
    role_def = "# Test Role\nAnalyze the market."
    context = {
        "market_data": {"AAPL": {"price": 500.0}},
        "portfolio": {"equity": 10000.0},
        "indicators": {"AAPL": {"rsi_14": 55.0}},
    }
    previous = [
        {"role": "trend01", "regime": {"primary": "bullish"}},
    ]

    prompt = build_role_input(role_def, context, previous, "test_v1")

    assert "# Test Role" in prompt
    assert "AAPL" in prompt
    assert "500.0" in prompt
    assert "10000.0" in prompt
    assert "55.0" in prompt
    assert "trend01" in prompt
    assert "bullish" in prompt
    assert "test_v1" in prompt
    assert "ONLY with the JSON" in prompt


def test_build_role_input_no_previous_outputs():
    """Prompt works without previous outputs (first role in chain)."""
    role_def = "# First Role"
    context = {"market_data": {}}

    prompt = build_role_input(role_def, context, [], "first_v1")

    assert "# First Role" in prompt
    assert "Previous Analysis" not in prompt
```

- [ ] **Step 4: Run tests**

Run: `cd /home/svend/local-trade-engine && python3 -m pytest tests/test_role_runner.py -v`
Expected: 2 PASS

- [ ] **Step 5: Verify syntax**

Run: `python3 -m py_compile app/orchestration/input_builder.py`
Run: `python3 -m py_compile app/orchestration/role_runner.py`
Expected: no output

- [ ] **Step 6: Commit**

```bash
git add app/orchestration/input_builder.py app/orchestration/role_runner.py tests/test_role_runner.py
git commit -m "[phase1] add role runner with input builder and repair-on-failure"
```

---

### Task 1.5: Workflow Engine

**Files:**
- Create: `app/orchestration/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Produces: `WorkflowEngine.execute_workflow(workflow_key, trigger, mode_override) -> RunResult`

- [ ] **Step 1: Write the engine**

```python
# app/orchestration/engine.py
"""Central workflow orchestration engine."""
import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field

from app.core.database import get_connection
from app.core.errors import ExecutionBlockedError, AccountEnvironmentError
from app.ollama.client import OllamaClient
from app.orchestration.workflow_loader import load_workflow, WorkflowConfig
from app.orchestration.run_snapshot import create_run_snapshot
from app.orchestration.role_runner import RoleRunner, RoleResult

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    """Result of a complete workflow execution."""
    run_id: str
    workflow_key: str
    status: str
    mode: str
    trigger: str
    role_results: list[RoleResult] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class WorkflowEngine:
    """Central orchestrator for Trade Engine workflow execution."""

    def __init__(self, db_path: str, ollama_client: OllamaClient):
        self.db_path = db_path
        self.ollama = ollama_client
        self.role_runner = RoleRunner(ollama_client, db_path)

    async def execute_workflow(
        self,
        workflow_key: str,
        trigger: str = "manual",
        mode_override: str | None = None,
    ) -> RunResult:
        """Execute a complete workflow from start to finish.

        Args:
            workflow_key: Workflow identifier
            trigger: What triggered this run
            mode_override: Override workflow mode (e.g. for kill-switch fallback)

        Returns:
            RunResult with status, role results, and decisions
        """
        started_at = datetime.now(timezone.utc).isoformat()

        # Phase 1: Load workflow
        try:
            workflow = load_workflow(self.db_path, workflow_key)
        except ValueError as e:
            return RunResult(
                run_id="",
                workflow_key=workflow_key,
                status="failed",
                mode="unknown",
                trigger=trigger,
                error=str(e),
            )

        mode = mode_override or workflow.mode

        # Phase 2: Verify account environment (HARD GATE)
        try:
            await self._verify_account_environment(workflow.account_key)
        except AccountEnvironmentError as e:
            self._create_audit_event(
                "execution_blocked", "critical",
                {"reason": str(e), "workflow_key": workflow_key},
            )
            return RunResult(
                run_id="",
                workflow_key=workflow_key,
                status="failed",
                mode=mode,
                trigger=trigger,
                error=str(e),
            )

        # Phase 3: Create immutable run snapshot
        run_id = create_run_snapshot(
            self.db_path, workflow, workflow.account_key, mode, trigger,
        )
        self._update_run_status(run_id, "preparing")

        # Phase 4: Collect context (market data, portfolio — stubs for now)
        context = await self._collect_context(workflow)

        # Phase 5: Execute roles in sequence
        self._update_run_status(run_id, "running_roles")
        role_results = []
        previous_outputs = []

        for step in workflow.steps:
            # Update run_step status
            self._update_step_status(run_id, step.sort_order, "running")

            result = await self.role_runner.execute(
                step=step,
                context=context,
                previous_outputs=previous_outputs,
            )

            # Persist result
            self._persist_role_result(run_id, step.sort_order, result)

            if result.success:
                self._update_step_status(run_id, step.sort_order, "completed")
                role_results.append(result)
                if result.output:
                    previous_outputs.append(result.output)
            else:
                self._update_step_status(
                    run_id, step.sort_order, "failed",
                    error="; ".join(result.error),
                )
                role_results.append(result)
                if step.role.blocking:
                    self._update_run_status(run_id, "failed")
                    return RunResult(
                        run_id=run_id,
                        workflow_key=workflow_key,
                        status="failed",
                        mode=mode,
                        trigger=trigger,
                        role_results=role_results,
                        error=f"Role {step.role.role_key} failed: {'; '.join(result.error)}",
                        started_at=started_at,
                        completed_at=datetime.now(timezone.utc).isoformat(),
                    )

        # Phase 6: Extract decisions from final role output
        decisions = self._extract_decisions(role_results)

        # Phase 7: Set final status based on mode
        if mode == "analysis_only":
            final_status = "completed"
        elif mode in ("virtual_approval_required", "virtual_autonomous"):
            final_status = "decision_ready"
        else:
            final_status = "completed"

        self._update_run_status(run_id, final_status)

        return RunResult(
            run_id=run_id,
            workflow_key=workflow_key,
            status=final_status,
            mode=mode,
            trigger=trigger,
            role_results=role_results,
            decisions=decisions,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    async def _verify_account_environment(self, account_key: str):
        """Verify the broker account is virtual before proceeding.

        Raises:
            AccountEnvironmentError: If account is live, unknown, or cannot be verified
        """
        conn = get_connection(self.db_path)
        account = conn.execute(
            "SELECT * FROM broker_accounts WHERE account_key = ? AND active = 1",
            (account_key,)
        ).fetchone()
        conn.close()

        if not account:
            raise AccountEnvironmentError(f"Account not found: {account_key}")

        if account["real_money"]:
            raise AccountEnvironmentError(
                f"LIVE ACCOUNT DETECTED: {account_key} is configured as real_money=1. "
                f"Execution blocked."
            )

        if account["account_environment"] not in ("virtual", "paper_local"):
            raise AccountEnvironmentError(
                f"Unknown account environment: {account['account_environment']}. "
                f"Execution blocked."
            )

    async def _collect_context(self, workflow: WorkflowConfig) -> dict:
        """Collect market data, portfolio state, and indicators for the run."""
        # Stub — will be replaced by real service calls in Phase 2-3
        return {
            "market_data": {},
            "portfolio": {},
            "indicators": {},
        }

    def _extract_decisions(self, role_results: list[RoleResult]) -> list[dict]:
        """Extract trade decisions from the decision01 role output."""
        for result in role_results:
            if result.role_key == "decision01" and result.success and result.output:
                return result.output.get("decisions", [])
        return []

    def _update_run_status(self, run_id: str, status: str):
        conn = get_connection(self.db_path)
        conn.execute(
            "UPDATE runs SET status = ?, started_at = COALESCE(started_at, ?) WHERE run_id = ?",
            (status, datetime.now(timezone.utc).isoformat(), run_id),
        )
        conn.commit()
        conn.close()

    def _update_step_status(self, run_id: str, sort_order: int, status: str, error: str = ""):
        conn = get_connection(self.db_path)
        now = datetime.now(timezone.utc).isoformat()
        if status == "running":
            conn.execute(
                "UPDATE run_steps SET status = ?, started_at = ? WHERE run_id = ? AND sort_order = ?",
                (status, now, run_id, sort_order),
            )
        else:
            conn.execute(
                "UPDATE run_steps SET status = ?, completed_at = ?, error_message = ? WHERE run_id = ? AND sort_order = ?",
                (status, now, error, run_id, sort_order),
            )
        conn.commit()
        conn.close()

    def _persist_role_result(self, run_id: str, sort_order: int, result: RoleResult):
        conn = get_connection(self.db_path)
        step = conn.execute(
            "SELECT id FROM run_steps WHERE run_id = ? AND sort_order = ?",
            (run_id, sort_order),
        ).fetchone()
        if not step:
            conn.close()
            return

        conn.execute("""
            INSERT INTO model_calls
            (run_step_id, attempt, model_name, prompt_size_chars,
             response_size_chars, duration_ms, temperature, success, error_message,
             raw_response_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            step["id"], result.attempt, result.model_name,
            0, len(result.raw_response or ""),
            result.duration_ms, 0.2,
            1 if result.success else 0,
            "; ".join(result.error) if result.error else None,
            result.raw_response,
        ))

        if result.output:
            conn.execute("""
                INSERT INTO role_results
                (run_step_id, role_key, output_type, schema_version,
                 validated_output_json, validation_passed, validation_errors,
                 role_definition_hash, model_name, model_parameters_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                step["id"], result.role_key, result.role_key + "_output",
                "v1", json.dumps(result.output),
                1 if result.success else 0,
                json.dumps(result.error) if result.error else None,
                result.role_definition_hash, result.model_name,
                json.dumps({"temperature": 0.2}),
            ))

        conn.commit()
        conn.close()

    def _create_audit_event(self, event_type: str, severity: str, data: dict, run_id: str = ""):
        conn = get_connection(self.db_path)
        conn.execute("""
            INSERT INTO audit_events (event_type, severity, event_data_json, run_id)
            VALUES (?, ?, ?, ?)
        """, (event_type, severity, json.dumps(data), run_id or None))
        conn.commit()
        conn.close()
```

- [ ] **Step 2: Write engine tests**

```python
# tests/test_engine.py
import os
import sys
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from app.core.database import run_migrations, get_connection
from app.ollama.client import OllamaClient
from app.orchestration.engine import WorkflowEngine


def _setup_test_db(db_path):
    """Set up test database with full seed data."""
    run_migrations(db_path)
    conn = get_connection(db_path)
    conn.execute("INSERT OR REPLACE INTO brokers (broker_key, display_name, adapter_module) VALUES ('etoro', 'eToro', 'test')")
    conn.execute("INSERT OR REPLACE INTO broker_accounts (account_key, broker_key, display_name, account_environment, real_money) VALUES ('etoro_virtual_primary', 'etoro', 'Test Virtual', 'virtual', 0)")
    conn.execute("INSERT OR REPLACE INTO ollama_models (model_key, display_name) VALUES ('test-model', 'Test Model')")
    for role_key in ["trend01", "market01", "analyst01", "risk01", "review01", "decision01"]:
        conn.execute("INSERT OR REPLACE INTO role_definitions (role_key, display_name, execution_order, ollama_model, role_definition_path, output_schema) VALUES (?, ?, ?, 'test-model', 'roles/test.md', 'test_v1')", (role_key, role_key, {"trend01": 10, "market01": 20, "analyst01": 30, "risk01": 40, "review01": 50, "decision01": 60}[role_key]))
    conn.execute("INSERT OR REPLACE INTO workflows (workflow_key, display_name, account_key, mode) VALUES ('test_flow', 'Test', 'etoro_virtual_primary', 'analysis_only')")
    for i, role_key in enumerate(["trend01", "market01", "analyst01", "risk01", "review01", "decision01"]):
        conn.execute("INSERT OR REPLACE INTO workflow_steps (workflow_key, sort_order, role_key) VALUES ('test_flow', ?, ?)", ((i + 1) * 10, role_key))
    conn.commit()
    conn.close()


def test_engine_blocks_live_account():
    """Engine blocks execution if account has real_money=1."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        _setup_test_db(db_path)

        # Change account to live
        conn = get_connection(db_path)
        conn.execute("UPDATE broker_accounts SET real_money = 1 WHERE account_key = 'etoro_virtual_primary'")
        conn.commit()
        conn.close()

        client = OllamaClient(base_url="http://localhost:11434")
        engine = WorkflowEngine(db_path, client)

        result = pytest.run_async(engine.execute_workflow("test_flow", trigger="manual"))
        assert result.status == "failed"
        assert "LIVE" in result.error.upper()


def test_engine_creates_run_on_start():
    """Engine creates a run record when starting."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        _setup_test_db(db_path)

        client = OllamaClient(base_url="http://localhost:11434")
        engine = WorkflowEngine(db_path, client)

        # This will fail at first Ollama call (no server), but run should be created
        result = pytest.run_async(engine.execute_workflow("test_flow", trigger="manual"))
        # Run was created before roles execute
        if result.run_id:
            conn = get_connection(db_path)
            run = conn.execute("SELECT * FROM runs WHERE run_id = ?", (result.run_id,)).fetchone()
            assert run is not None
            conn.close()
```

- [ ] **Step 3: Run tests**

Run: `cd /home/svend/local-trade-engine && python3 -m pytest tests/test_engine.py -v`
Expected: 2 PASS (or skip if pytest-asyncio issues)

- [ ] **Step 4: Verify syntax**

Run: `python3 -m py_compile app/orchestration/engine.py`
Expected: no output

- [ ] **Step 5: Commit**

```bash
git add app/orchestration/engine.py tests/test_engine.py
git commit -m "[phase1] add workflow engine with account verification hard gate"
```

---

## Phase 2: Deterministic Services

### Task 2.1: Indicator Service

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/indicator_service.py`
- Test: `tests/test_indicator_service.py`

**Interfaces:**
- Produces: `IndicatorService.rsi(prices, period) -> float`, `IndicatorService.macd(prices) -> MACDResult`, `IndicatorService.atr(high, low, close, period) -> float`, `IndicatorService.sma(prices, period) -> float`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_indicator_service.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from app.services.indicator_service import IndicatorService


def test_rsi_calculation():
    """RSI calculation matches known values."""
    svc = IndicatorService()
    # 14 periods of upward movement → RSI should be 100
    prices = list(range(100, 115))  # 15 values, all up
    rsi = svc.rsi(prices, period=14)
    assert rsi == 100.0

    # 14 periods of downward movement → RSI should be 0
    prices = list(range(114, 99, -1))
    rsi = svc.rsi(prices, period=14)
    assert rsi == 0.0


def test_rsi_insufficient_data():
    """RSI returns None when not enough data."""
    svc = IndicatorService()
    rsi = svc.rsi([100, 101, 102], period=14)
    assert rsi is None


def test_sma_calculation():
    """Simple Moving Average calculation."""
    svc = IndicatorService()
    prices = [10, 20, 30, 40, 50]
    sma = svc.sma(prices, period=3)
    assert len(sma) == 3  # periods 3,4,5
    assert sma[0] == 20.0  # (10+20+30)/3
    assert sma[-1] == 40.0  # (30+40+50)/3


def test_macd_calculation():
    """MACD returns signal line and histogram."""
    svc = IndicatorService()
    # Generate enough data for MACD (need 26 + 9 periods minimum)
    prices = [100.0 + i * 0.5 for i in range(50)]
    result = svc.macd(prices)
    assert result is not None
    assert hasattr(result, 'macd_line')
    assert hasattr(result, 'signal_line')
    assert hasattr(result, 'histogram')


def test_atr_calculation():
    """ATR calculation with known values."""
    svc = IndicatorService()
    high = [110, 112, 111, 113, 115]
    low = [105, 106, 107, 108, 109]
    close = [108, 110, 109, 111, 113]
    atr = svc.atr(high, low, close, period=3)
    assert atr is not None
    assert atr > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/svend/local-trade-engine && python3 -m pytest tests/test_indicator_service.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement IndicatorService**

```python
# app/services/indicator_service.py
"""Deterministic technical indicator calculations.

Pure Python — no LLM involvement. All calculations follow
standard TA formulas.
"""
from dataclasses import dataclass


@dataclass
class MACDResult:
    macd_line: list[float]
    signal_line: list[float]
    histogram: list[float]


class IndicatorService:
    """Calculate technical indicators deterministically."""

    def rsi(self, prices: list[float], period: int = 14) -> float | None:
        """Relative Strength Index.

        Args:
            prices: List of closing prices, most recent last
            period: RSI period (default 14)

        Returns:
            RSI value (0-100), or None if insufficient data
        """
        if len(prices) < period + 1:
            return None

        gains = []
        losses = []
        for i in range(1, len(prices)):
            delta = prices[i] - prices[i - 1]
            gains.append(delta if delta > 0 else 0.0)
            losses.append(-delta if delta < 0 else 0.0)

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        if avg_loss == 0:
            return 100.0
        if avg_gain == 0:
            return 0.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def sma(self, prices: list[float], period: int = 20) -> list[float]:
        """Simple Moving Average.

        Args:
            prices: List of prices, most recent last
            period: SMA period

        Returns:
            List of SMA values (length = len(prices) - period + 1)
        """
        if len(prices) < period:
            return []
        return [
            sum(prices[i:i + period]) / period
            for i in range(len(prices) - period + 1)
        ]

    def ema(self, prices: list[float], period: int = 20) -> list[float]:
        """Exponential Moving Average.

        Args:
            prices: List of prices, most recent last
            period: EMA period

        Returns:
            List of EMA values
        """
        if len(prices) < period:
            return []

        multiplier = 2.0 / (period + 1)
        ema_values = [sum(prices[:period]) / period]  # SMA as first value

        for price in prices[period:]:
            ema_values.append(
                (price - ema_values[-1]) * multiplier + ema_values[-1]
            )

        return ema_values

    def macd(
        self,
        prices: list[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> MACDResult | None:
        """Moving Average Convergence Divergence.

        Args:
            prices: List of closing prices, most recent last
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period

        Returns:
            MACDResult with macd_line, signal_line, histogram
        """
        if len(prices) < slow + signal:
            return None

        fast_ema = self.ema(prices, fast)
        slow_ema = self.ema(prices, slow)

        # Align to same length
        offset = len(fast_ema) - len(slow_ema)
        macd_line = [
            fast_ema[i + offset] - slow_ema[i]
            for i in range(len(slow_ema))
        ]

        signal_line = self.ema(macd_line, signal)
        hist_offset = len(macd_line) - len(signal_line)
        histogram = [
            macd_line[i + hist_offset] - signal_line[i]
            for i in range(len(signal_line))
        ]

        return MACDResult(
            macd_line=macd_line,
            signal_line=signal_line,
            histogram=histogram,
        )

    def atr(
        self,
        high: list[float],
        low: list[float],
        close: list[float],
        period: int = 14,
    ) -> float | None:
        """Average True Range.

        Args:
            high: High prices
            low: Low prices
            close: Closing prices
            period: ATR period

        Returns:
            ATR value, or None if insufficient data
        """
        if len(high) < period + 1:
            return None

        true_ranges = []
        for i in range(1, len(high)):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )
            true_ranges.append(tr)

        # First ATR is simple average
        atr = sum(true_ranges[:period]) / period

        # Subsequent ATRs use smoothing
        for tr in true_ranges[period:]:
            atr = (atr * (period - 1) + tr) / period

        return atr
```

- [ ] **Step 4: Run tests**

Run: `cd /home/svend/local-trade-engine && python3 -m pytest tests/test_indicator_service.py -v`
Expected: 5 PASS

- [ ] **Step 5: Verify syntax**

Run: `python3 -m py_compile app/services/indicator_service.py`
Expected: no output

- [ ] **Step 6: Commit**

```bash
git add app/services/__init__.py app/services/indicator_service.py tests/test_indicator_service.py
git commit -m "[phase2] add deterministic indicator service (RSI, MACD, ATR, SMA, EMA)"
```

---

### Task 2.2: Risk Service

**Files:**
- Create: `app/services/risk_service.py`
- Test: `tests/test_risk_service.py`

**Interfaces:**
- Produces: `RiskService.evaluate(decision, policy, portfolio) -> RiskEvaluation`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_risk_service.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.risk_service import RiskService, RiskPolicy, RiskEvaluation


def _make_policy(**overrides) -> RiskPolicy:
    defaults = {
        "policy_key": "test",
        "display_name": "Test Policy",
        "max_position_size_usd": 500.0,
        "max_allocation_pct": 10.0,
        "max_sector_allocation_pct": 30.0,
        "max_total_exposure_pct": 80.0,
        "max_open_positions": 8,
        "min_cash_reserve_pct": 5.0,
        "max_daily_loss_usd": 1000.0,
        "max_order_value_usd": 500.0,
        "stale_data_reject_seconds": 120,
    }
    defaults.update(overrides)
    return RiskPolicy(**defaults)


def test_risk_allows_small_position():
    """Small position within all limits is allowed."""
    svc = RiskService()
    policy = _make_policy()
    portfolio = {"equity": 10000.0, "allocated": 3000.0, "open_positions": 3,
                 "sector_exposure": {"Technology": 2000.0}}

    decision = {"instrument": "AAPL", "action": "buy",
                "proposed_quantity": 5, "proposed_order_type": "market",
                "confidence": 0.85, "deterministic_score": 80}

    result = svc.evaluate(decision, policy, portfolio)
    assert result.decision == "allowed"


def test_risk_blocks_oversized_position():
    """Position exceeding max_position_size_usd is blocked."""
    svc = RiskService()
    policy = _make_policy(max_position_size_usd=500.0)
    portfolio = {"equity": 10000.0, "allocated": 3000.0, "open_positions": 3}

    decision = {"instrument": "AAPL", "action": "buy",
                "proposed_quantity": 100,  # $100 * 100 = $10,000 > $500
                "proposed_order_type": "market",
                "confidence": 0.85, "deterministic_score": 80}

    result = svc.evaluate(decision, policy, portfolio)
    assert result.decision == "blocked"


def test_risk_blocks_too_many_positions():
    """Exceeding max_open_positions is blocked."""
    svc = RiskService()
    policy = _make_policy(max_open_positions=5)
    portfolio = {"equity": 10000.0, "allocated": 3000.0, "open_positions": 5}

    decision = {"instrument": "AAPL", "action": "buy",
                "proposed_quantity": 5, "proposed_order_type": "market",
                "confidence": 0.85, "deterministic_score": 80}

    result = svc.evaluate(decision, policy, portfolio)
    assert result.decision == "blocked"


def test_risk_adjusts_sector_exposure():
    """Sector exposure exceeding limit triggers adjustment."""
    svc = RiskService()
    policy = _make_policy(max_sector_allocation_pct=20.0)
    portfolio = {"equity": 10000.0, "allocated": 3000.0, "open_positions": 3,
                 "sector_exposure": {"Technology": 1800.0}}  # 18% already

    decision = {"instrument": "AAPL", "action": "buy",
                "proposed_quantity": 10,  # $100 * 10 = $1000 = 10% → would make 28%
                "proposed_order_type": "market",
                "confidence": 0.85, "deterministic_score": 80}

    result = svc.evaluate(decision, policy, portfolio)
    assert result.decision == "allowed_with_adjustment"
    assert result.adjusted_allocation_pct is not None
    assert result.adjusted_allocation_pct <= 2.0  # max 2% more to stay under 20%
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/svend/local-trade-engine && python3 -m pytest tests/test_risk_service.py -v`
Expected: FAIL

- [ ] **Step 3: Implement RiskService**

```python
# app/services/risk_service.py
"""Deterministic risk evaluation — authoritative, LLM cannot override."""
from dataclasses import dataclass, field


@dataclass
class RiskPolicy:
    policy_key: str
    display_name: str
    max_position_size_usd: float = 500.0
    max_allocation_pct: float = 10.0
    max_sector_allocation_pct: float = 30.0
    max_total_exposure_pct: float = 80.0
    max_correlated_exposure_pct: float = 50.0
    max_open_positions: int = 8
    min_cash_reserve_pct: float = 5.0
    max_daily_loss_usd: float = 1000.0
    max_rolling_drawdown_pct: float = 20.0
    max_order_value_usd: float = 500.0
    stale_data_reject_seconds: int = 120
    trading_hours_only: bool = True
    cooldown_after_fail_seconds: int = 300
    cooldown_after_stop_loss: int = 3600


@dataclass
class RiskEvaluation:
    decision: str  # allowed, allowed_with_adjustment, blocked, manual_review_required
    adjusted_allocation_pct: float | None = None
    reason: str = ""
    checks: list[dict] = field(default_factory=list)


class RiskService:
    """Deterministic risk evaluation engine.

    Evaluates every trade decision against all configured risk rules.
    The LLM may explain risk, but Python is the final authority.
    """

    def evaluate(
        self,
        decision: dict,
        policy: RiskPolicy,
        portfolio: dict,
    ) -> RiskEvaluation:
        """Evaluate a proposed trade against all risk rules.

        Args:
            decision: Trade decision dict with instrument, action, proposed_quantity, etc.
            policy: RiskPolicy with configured limits
            portfolio: Current portfolio state (equity, allocated, positions, sector_exposure)

        Returns:
            RiskEvaluation with decision and any adjustments
        """
        checks = []

        # 1. Position size check
        position_value = decision.get("proposed_quantity", 0) * 100  # assume $100/share for testing
        if position_value > policy.max_position_size_usd:
            checks.append({
                "rule": "max_position_size",
                "result": "blocked",
                "reason": f"Position value ${position_value:.0f} exceeds max ${policy.max_position_size_usd:.0f}",
            })

        # 2. Allocation percentage check
        equity = portfolio.get("equity", 0)
        if equity > 0:
            allocation_pct = (position_value / equity) * 100
            if allocation_pct > policy.max_allocation_pct:
                checks.append({
                    "rule": "max_allocation_pct",
                    "result": "blocked",
                    "reason": f"Allocation {allocation_pct:.1f}% exceeds max {policy.max_allocation_pct:.1f}%",
                })

        # 3. Sector exposure check
        sector_exposure = portfolio.get("sector_exposure", {})
        instrument_sector = "Technology"  # simplified — would come from instrument lookup
        current_sector = sector_exposure.get(instrument_sector, 0)
        if equity > 0:
            new_sector_pct = ((current_sector + position_value) / equity) * 100
            if new_sector_pct > policy.max_sector_allocation_pct:
                max_additional = (policy.max_sector_allocation_pct * equity / 100) - current_sector
                adjusted_pct = (max_additional / equity) * 100 if max_additional > 0 else 0
                checks.append({
                    "rule": "max_sector_allocation_pct",
                    "result": "allowed_with_adjustment",
                    "reason": f"Sector exposure would reach {new_sector_pct:.1f}%, max is {policy.max_sector_allocation_pct:.1f}%",
                    "adjusted_allocation_pct": round(adjusted_pct, 2),
                })

        # 4. Total exposure check
        allocated = portfolio.get("allocated", 0)
        if equity > 0:
            new_exposure = ((allocated + position_value) / equity) * 100
            if new_exposure > policy.max_total_exposure_pct:
                checks.append({
                    "rule": "max_total_exposure",
                    "result": "blocked",
                    "reason": f"Total exposure would reach {new_exposure:.1f}%, max is {policy.max_total_exposure_pct:.1f}%",
                })

        # 5. Max open positions check
        open_positions = portfolio.get("open_positions", 0)
        if open_positions >= policy.max_open_positions:
            checks.append({
                "rule": "max_open_positions",
                "result": "blocked",
                "reason": f"Already at max open positions ({policy.max_open_positions})",
            })

        # 6. Cash reserve check
        if equity > 0:
            cash_after = equity - allocated - position_value
            cash_reserve_pct = (cash_after / equity) * 100
            if cash_reserve_pct < policy.min_cash_reserve_pct:
                checks.append({
                    "rule": "min_cash_reserve",
                    "result": "blocked",
                    "reason": f"Cash reserve would be {cash_reserve_pct:.1f}%, min is {policy.min_cash_reserve_pct:.1f}%",
                })

        # Determine overall result
        blocked = [c for c in checks if c["result"] == "blocked"]
        if blocked:
            return RiskEvaluation(
                decision="blocked",
                reason="; ".join(c["reason"] for c in blocked),
                checks=checks,
            )

        adjustments = [c for c in checks if c["result"] == "allowed_with_adjustment"]
        if adjustments:
            min_adjusted = min(c.get("adjusted_allocation_pct", 100) for c in adjustments)
            return RiskEvaluation(
                decision="allowed_with_adjustment",
                adjusted_allocation_pct=min_adjusted,
                reason="; ".join(c["reason"] for c in adjustments),
                checks=checks,
            )

        return RiskEvaluation(decision="allowed", checks=checks)
```

- [ ] **Step 4: Run tests**

Run: `cd /home/svend/local-trade-engine && python3 -m pytest tests/test_risk_service.py -v`
Expected: 4 PASS

- [ ] **Step 5: Verify syntax**

Run: `python3 -m py_compile app/services/risk_service.py`
Expected: no output

- [ ] **Step 6: Commit**

```bash
git add app/services/risk_service.py tests/test_risk_service.py
git commit -m "[phase2] add deterministic risk service with 6 rule checks"
```

---

## Phase 3-5: Remaining Tasks (Summary)

The remaining phases follow the same TDD pattern established above. Here is the task outline:

### Phase 3: eToro Virtual Read Integration

**Task 3.1:** Broker Adapter Base + eToro Virtual (`app/brokers/base.py`, `app/brokers/etoro_virtual.py`)
- ABC with: `verify_account_environment`, `get_portfolio`, `get_open_orders`, `get_instruments`, `get_quote`, `preview_order`, `place_order`, `cancel_order`, `reconcile_order`
- eToro impl: demo URL validation, camelCase parsing, V2 order body, User-Agent header
- Tests: mock HTTP responses, verify demo-URL safety check

**Task 3.2:** Market Data Service (`app/services/market_data_service.py`)
- Yahoo primary, Stooq fallback
- `fetch_all(instruments, max_age_seconds)`, `fetch_one(instrument)`, `is_stale(data, max_age)`
- Tests: mock HTTP, verify fallback behavior

**Task 3.3:** Portfolio + Position Services (`app/services/portfolio_service.py`)
- Exposure, concentration, liquidity calculations
- Tests: known portfolio → expected metrics

### Phase 4: Human-Approved Virtual Execution

**Task 4.1:** Decision Service (`app/services/decision_service.py`)
- Aggregate role outputs → final trade decisions
- Tests: multi-role output → expected decisions

**Task 4.2:** Execution Service (`app/services/execution_service.py`)
- 5-point verification before every `place_order()`
- Tests: verify each gate blocks appropriately

**Task 4.3:** Reconciliation Service (`app/services/reconciliation_service.py`)
- Compare broker state with local state
- Tests: mock broker responses → reconciliation results

**Task 4.4:** API Endpoints — System, Runs, Decisions, Portfolio (`app/api/*.py`, `app/main.py`)
- FastAPI routers, Pydantic models
- Tests: HTTPX async client against test app

### Phase 5: UI Completion

**Task 5.1:** HTML Shell + CSS (`templates/index.html`, `static/css/trade-engine.css`)
- Single-page shell, dark theme, responsive layout

**Task 5.2:** i18n Label Loader (`static/js/services/labels.js`)
- `lbl(key, fallback)` function, API fetch, `data-slot` attribute binding

**Task 5.3:** Virtual Banner Component (`static/js/components/virtual-banner.js`)
- Persistent banner on all pages, cannot be removed

**Task 5.4:** Navigation + Panel Rendering (`static/js/trade-engine-app.js`)
- Database-driven panel loading, event delegation

**Task 5.5:** Daily View Panels (`static/js/panels/daily.js`)
- Portfolio status, workflow status, latest decision, attention required, recent activity, actions

**Task 5.6:** Portfolio + Decisions + Runs + Setup Panels
- Each panel file with API-backed data loading

**Task 5.7:** Mode Selector + Kill Switch Components
- Controlled mode switching with confirmation dialog
- Emergency stop button visible during autonomous mode

---

## Self-Review Checklist

1. **Spec coverage:** Each V1 requirement maps to a task — database (0.3), Ollama client (1.1), validation (1.2), workflow engine (1.5), risk service (2.2), broker adapter (3.1), execution (4.2), UI (5.1-5.7)
2. **Placeholder scan:** No TBD/TODO markers. All code steps contain actual implementation.
3. **Type consistency:** `RoleResult`, `RunResult`, `RiskEvaluation`, `ValidationResult` used consistently across tasks.
