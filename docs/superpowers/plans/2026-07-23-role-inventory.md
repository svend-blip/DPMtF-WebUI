================================================================================
DPMtF Role Inventory — 2026-07-23
================================================================================

## Summary by category
  allocator (2): imple01, imple01pay
  claude_code_local (10): analyst01_trade, archi01, archi01cloud, learn01_trade, market01_trade, portfolio01_trade, risk01_trade, score01_trade, sim01_trade, trend01_trade
  cloud_openrouter (1): archi01pay
  freebuff (1): imple01cloud
  human (4): human, humancloud, humanpay, humantrade
  opencode_local (7): review01, review01_trade, review01cloud, review01pay, review02, review02cloud, review02pay

## Roles sharing the same concrete model
  qwen3-coder-30b-48k: market01_trade, portfolio01_trade, risk01_trade, score01_trade
  qwen3.6:27b-q4_K_M: review01cloud, review01pay, review02
  qwen3.6:35b-a3b: review02cloud, review02pay
  qwen3.6:35b-a3b-64k: analyst01_trade, archi01, archi01cloud

## Detailed role listing

### analyst01_trade
  role_type:       agent
  category:        claude_code_local
  tmux_session:    analyst01_trade
  model_type:      ollama
  ollama_model:    qwen3.6:35b-a3b-64k
  cloud_model:     
  default_runtime: claude
  default_provider: local_ollama
  default_model:   qwen3.6:35b-a3b-64k
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      imple01
  governance_file: 433_TRADE_ANALYST01.md

### archi01
  role_type:       agent
  category:        claude_code_local
  tmux_session:    archi01
  model_type:      ollama
  ollama_model:    qwen3.6:35b-a3b-64k
  cloud_model:     
  default_runtime: claude
  default_provider: local_ollama
  default_model:   qwen3.6:35b-a3b-64k
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      None
  governance_file: 402_STRICT_REVIEW_ARCHI01.md

### archi01cloud
  role_type:       agent
  category:        claude_code_local
  tmux_session:    archi01cloud
  model_type:      ollama
  ollama_model:    qwen3.6:35b-a3b-64k
  cloud_model:     
  default_runtime: claude
  default_provider: local_ollama
  default_model:   qwen3.6:35b-a3b-64k
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      None
  governance_file: 412_CLOUD_LLM_ARCHI01CLOUD.md

### archi01pay
  role_type:       agent
  category:        cloud_openrouter
  tmux_session:    archi01pay
  model_type:      cloud
  ollama_model:    None
  cloud_model:     
  default_runtime: claude
  default_provider: openrouter
  default_model:   z-ai/glm-5.2
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      archi01pay
  governance_file: 422_CLOUD_PAY_ARCHI01PAY.md

### human
  role_type:       human
  category:        human
  tmux_session:    human
  model_type:      ollama
  ollama_model:    None
  cloud_model:     None
  default_runtime: None
  default_provider: None
  default_model:   None
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      None
  governance_file: 401_STRICT_REVIEW_HUMAN.md

### humancloud
  role_type:       human
  category:        human
  tmux_session:    humancloud
  model_type:      ollama
  ollama_model:    
  cloud_model:     
  default_runtime: None
  default_provider: None
  default_model:   None
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      None
  governance_file: 411_CLOUD_LLM_HUMANCLOUD.md

### humanpay
  role_type:       human
  category:        human
  tmux_session:    humanpay
  model_type:      ollama
  ollama_model:    
  cloud_model:     
  default_runtime: None
  default_provider: None
  default_model:   None
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      None
  governance_file: 421_CLOUD_PAY_HUMANPAY.md

### humantrade
  role_type:       human
  category:        human
  tmux_session:    humantrade
  model_type:      human
  ollama_model:    None
  cloud_model:     None
  default_runtime: None
  default_provider: None
  default_model:   None
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      None
  governance_file: None

### imple01
  role_type:       agent
  category:        allocator
  tmux_session:    imple01
  model_type:      ollama
  ollama_model:    qwen3-coder:30b-256k
  cloud_model:     minimax/MiniMax-M3
  default_runtime: opencode
  default_provider: local_ollama
  default_model:   qwen3-coder:30b-256k
  model_source:    model_allocator
  model_alias:     imple01-local
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      imple01
  governance_file: 403_STRICT_REVIEW_IMPLE01.md

### imple01cloud
  role_type:       agent
  category:        freebuff
  tmux_session:    imple01cloud
  model_type:      cloud
  ollama_model:    
  cloud_model:     Freebuf
  default_runtime: freebuff
  default_provider: None
  default_model:   freebuff-default
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      None
  governance_file: 413_CLOUD_LLM_IMPLE01CLOUD.md

### imple01pay
  role_type:       agent
  category:        allocator
  tmux_session:    imple01pay
  model_type:      cloud
  ollama_model:    
  cloud_model:     OpenRouter
  default_runtime: opencode
  default_provider: openrouter
  default_model:   moonshotai/kimi-k2.7-code
  model_source:    model_allocator
  model_alias:     imple01-local
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      imple01pay
  governance_file: 423_CLOUD_PAY_IMPLE01PAY.md

### learn01_trade
  role_type:       agent
  category:        claude_code_local
  tmux_session:    learn01_trade
  model_type:      ollama
  ollama_model:    qwen3.6-27b-32k
  cloud_model:     
  default_runtime: claude
  default_provider: local_ollama
  default_model:   qwen3.6-27b-32k
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      None
  governance_file: 438_TRADE_LEARN01.md

### market01_trade
  role_type:       agent
  category:        claude_code_local
  tmux_session:    market01_trade
  model_type:      ollama
  ollama_model:    qwen3-coder-30b-48k
  cloud_model:     
  default_runtime: claude
  default_provider: local_ollama
  default_model:   qwen3-coder-30b-96k
  model_source:    None
  model_alias:     None
  max_output_tokens: 81920
  trade_mcp_push_mode: market
  config_dir:      None
  governance_file: 432_TRADE_MARKET01.md

### portfolio01_trade
  role_type:       agent
  category:        claude_code_local
  tmux_session:    portfolio01_trade
  model_type:      ollama
  ollama_model:    qwen3-coder-30b-48k
  cloud_model:     
  default_runtime: claude
  default_provider: local_ollama
  default_model:   qwen3-coder-30b-96k
  model_source:    None
  model_alias:     None
  max_output_tokens: 81920
  trade_mcp_push_mode: None
  config_dir:      None
  governance_file: 440_TRADE_PORTFOLIO01.md

### review01
  role_type:       agent
  category:        opencode_local
  tmux_session:    review01
  model_type:      ollama
  ollama_model:    ornith35b-q5-64k
  cloud_model:     
  default_runtime: opencode
  default_provider: local_ollama
  default_model:   ornith35b-q5-64k
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      review01
  governance_file: 404_STRICT_REVIEW_REVIEW01.md

### review01_trade
  role_type:       agent
  category:        opencode_local
  tmux_session:    review01_trade
  model_type:      ollama
  ollama_model:    qwen3.6-27b-48k
  cloud_model:     
  default_runtime: opencode
  default_provider: local_ollama
  default_model:   qwen3.6-27b-48k
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      glm52trade
  governance_file: 435_TRADE_REVIEW01.md

### review01cloud
  role_type:       agent
  category:        opencode_local
  tmux_session:    review01cloud
  model_type:      ollama
  ollama_model:    qwen3.6:27b-q4_K_M
  cloud_model:     
  default_runtime: opencode
  default_provider: local_ollama
  default_model:   qwen3.6:27b-q4_K_M
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      review01cloud
  governance_file: 414_CLOUD_LLM_REVIEW01CLOUD.md

### review01pay
  role_type:       agent
  category:        opencode_local
  tmux_session:    review01pay
  model_type:      ollama
  ollama_model:    qwen3.6:27b-q4_K_M
  cloud_model:     
  default_runtime: opencode
  default_provider: local_ollama
  default_model:   qwen3.6:27b-q4_K_M
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      review01pay
  governance_file: 424_CLOUD_PAY_REVIEW01PAY.md

### review02
  role_type:       agent
  category:        opencode_local
  tmux_session:    review02
  model_type:      ollama
  ollama_model:    qwen3.6:27b-q4_K_M
  cloud_model:     
  default_runtime: opencode
  default_provider: local_ollama
  default_model:   qwen3.6:27b-q4_K_M
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      review02
  governance_file: 405_STRICT_REVIEW_REVIEW02.md

### review02cloud
  role_type:       agent
  category:        opencode_local
  tmux_session:    review02cloud
  model_type:      ollama
  ollama_model:    qwen3.6:35b-a3b
  cloud_model:     
  default_runtime: opencode
  default_provider: local_ollama
  default_model:   qwen3.6:35b-a3b
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      review02cloud
  governance_file: 415_CLOUD_LLM_REVIEW02CLOUD.md

### review02pay
  role_type:       agent
  category:        opencode_local
  tmux_session:    review02pay
  model_type:      ollama
  ollama_model:    qwen3.6:35b-a3b
  cloud_model:     
  default_runtime: opencode
  default_provider: local_ollama
  default_model:   qwen3.6:35b-a3b
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      review02pay
  governance_file: 425_CLOUD_PAY_REVIEW02PAY.md

### risk01_trade
  role_type:       agent
  category:        claude_code_local
  tmux_session:    risk01_trade
  model_type:      ollama
  ollama_model:    qwen3-coder-30b-48k
  cloud_model:     
  default_runtime: claude
  default_provider: local_ollama
  default_model:   qwen3-coder-30b-48k
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: risk
  config_dir:      None
  governance_file: 434_TRADE_RISK01.md

### score01_trade
  role_type:       agent
  category:        claude_code_local
  tmux_session:    score01_trade
  model_type:      ollama
  ollama_model:    qwen3-coder-30b-48k
  cloud_model:     
  default_runtime: claude
  default_provider: local_ollama
  default_model:   qwen3-coder-30b-48k
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      None
  governance_file: 437_TRADE_SCORE01.md

### sim01_trade
  role_type:       agent
  category:        claude_code_local
  tmux_session:    sim01_trade
  model_type:      ollama
  ollama_model:    ornith35b-q5-48k
  cloud_model:     
  default_runtime: claude
  default_provider: local_ollama
  default_model:   qwen3.6:35b-a3b-64k
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: None
  config_dir:      None
  governance_file: 436_TRADE_SIM01.md

### trend01_trade
  role_type:       agent
  category:        claude_code_local
  tmux_session:    trend01_trade
  model_type:      ollama
  ollama_model:    qwen3.6-35b-48k
  cloud_model:     
  default_runtime: claude
  default_provider: local_ollama
  default_model:   qwen3.6-35b-48k
  model_source:    None
  model_alias:     None
  max_output_tokens: None
  trade_mcp_push_mode: watchlist
  config_dir:      None
  governance_file: 431_TRADE_TREND01.md

## JSON
{
  "generated_at": "2026-07-23",
  "db_path": "/home/svend/DPMtF-WebUI/databases/dpmtf.db",
  "flows": [
    {
      "flow_key": "strict_review",
      "name": "Standard development flow"
    },
    {
      "flow_key": "cloud_llm",
      "name": "Using Cloud Freebuff"
    },
    {
      "flow_key": "cloud_pay",
      "name": "Cloud Pay"
    },
    {
      "flow_key": "trade_cockpit_simulation_v001",
      "name": "Trade Cockpit Simulation"
    },
    {
      "flow_key": "trade_cockpit_scoring_v001",
      "name": "Trade Cockpit Scoring"
    }
  ],
  "roles": [
    {
      "role_key": "analyst01_trade",
      "tmux_session": "analyst01_trade",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3.6:35b-a3b-64k",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "433_TRADE_ANALYST01.md",
      "default_runtime": "claude",
      "default_provider": "local_ollama",
      "default_model": "qwen3.6:35b-a3b-64k",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": "imple01",
      "primary_output_type": "candidate_note",
      "category": "claude_code_local"
    },
    {
      "role_key": "archi01",
      "tmux_session": "archi01",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3.6:35b-a3b-64k",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "402_STRICT_REVIEW_ARCHI01.md",
      "default_runtime": "claude",
      "default_provider": "local_ollama",
      "default_model": "qwen3.6:35b-a3b-64k",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": null,
      "primary_output_type": null,
      "category": "claude_code_local"
    },
    {
      "role_key": "archi01cloud",
      "tmux_session": "archi01cloud",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3.6:35b-a3b-64k",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "412_CLOUD_LLM_ARCHI01CLOUD.md",
      "default_runtime": "claude",
      "default_provider": "local_ollama",
      "default_model": "qwen3.6:35b-a3b-64k",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": null,
      "primary_output_type": null,
      "category": "claude_code_local"
    },
    {
      "role_key": "archi01pay",
      "tmux_session": "archi01pay",
      "model_type": "cloud",
      "cloud_model": "",
      "ollama_model": null,
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "422_CLOUD_PAY_ARCHI01PAY.md",
      "default_runtime": "claude",
      "default_provider": "openrouter",
      "default_model": "z-ai/glm-5.2",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": "archi01pay",
      "primary_output_type": null,
      "category": "cloud_openrouter"
    },
    {
      "role_key": "human",
      "tmux_session": "human",
      "model_type": "ollama",
      "cloud_model": null,
      "ollama_model": null,
      "role_type": "human",
      "enter_command": "default",
      "governance_file": "401_STRICT_REVIEW_HUMAN.md",
      "default_runtime": null,
      "default_provider": null,
      "default_model": null,
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": null,
      "primary_output_type": null,
      "category": "human"
    },
    {
      "role_key": "humancloud",
      "tmux_session": "humancloud",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "",
      "role_type": "human",
      "enter_command": "default",
      "governance_file": "411_CLOUD_LLM_HUMANCLOUD.md",
      "default_runtime": null,
      "default_provider": null,
      "default_model": null,
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": null,
      "primary_output_type": null,
      "category": "human"
    },
    {
      "role_key": "humanpay",
      "tmux_session": "humanpay",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "",
      "role_type": "human",
      "enter_command": "default",
      "governance_file": "421_CLOUD_PAY_HUMANPAY.md",
      "default_runtime": null,
      "default_provider": null,
      "default_model": null,
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": null,
      "primary_output_type": null,
      "category": "human"
    },
    {
      "role_key": "humantrade",
      "tmux_session": "humantrade",
      "model_type": "human",
      "cloud_model": null,
      "ollama_model": null,
      "role_type": "human",
      "enter_command": "default",
      "governance_file": null,
      "default_runtime": null,
      "default_provider": null,
      "default_model": null,
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": null,
      "primary_output_type": null,
      "category": "human"
    },
    {
      "role_key": "imple01",
      "tmux_session": "imple01",
      "model_type": "ollama",
      "cloud_model": "minimax/MiniMax-M3",
      "ollama_model": "qwen3-coder:30b-256k",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "403_STRICT_REVIEW_IMPLE01.md",
      "default_runtime": "opencode",
      "default_provider": "local_ollama",
      "default_model": "qwen3-coder:30b-256k",
      "default_model_source": "model_allocator",
      "default_model_alias": "imple01-local",
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": "imple01",
      "primary_output_type": null,
      "category": "allocator"
    },
    {
      "role_key": "imple01cloud",
      "tmux_session": "imple01cloud",
      "model_type": "cloud",
      "cloud_model": "Freebuf",
      "ollama_model": "",
      "role_type": "agent",
      "enter_command": "c-m",
      "governance_file": "413_CLOUD_LLM_IMPLE01CLOUD.md",
      "default_runtime": "freebuff",
      "default_provider": null,
      "default_model": "freebuff-default",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": null,
      "primary_output_type": null,
      "category": "freebuff"
    },
    {
      "role_key": "imple01pay",
      "tmux_session": "imple01pay",
      "model_type": "cloud",
      "cloud_model": "OpenRouter",
      "ollama_model": "",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "423_CLOUD_PAY_IMPLE01PAY.md",
      "default_runtime": "opencode",
      "default_provider": "openrouter",
      "default_model": "moonshotai/kimi-k2.7-code",
      "default_model_source": "model_allocator",
      "default_model_alias": "imple01-local",
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": "imple01pay",
      "primary_output_type": null,
      "category": "allocator"
    },
    {
      "role_key": "learn01_trade",
      "tmux_session": "learn01_trade",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3.6-27b-32k",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "438_TRADE_LEARN01.md",
      "default_runtime": "claude",
      "default_provider": "local_ollama",
      "default_model": "qwen3.6-27b-32k",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": null,
      "primary_output_type": "learning_update",
      "category": "claude_code_local"
    },
    {
      "role_key": "market01_trade",
      "tmux_session": "market01_trade",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3-coder-30b-48k",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "432_TRADE_MARKET01.md",
      "default_runtime": "claude",
      "default_provider": "local_ollama",
      "default_model": "qwen3-coder-30b-96k",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": 81920,
      "trade_mcp_push_mode": "market",
      "config_dir": null,
      "primary_output_type": "market_snapshot",
      "category": "claude_code_local"
    },
    {
      "role_key": "portfolio01_trade",
      "tmux_session": "portfolio01_trade",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3-coder-30b-48k",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "440_TRADE_PORTFOLIO01.md",
      "default_runtime": "claude",
      "default_provider": "local_ollama",
      "default_model": "qwen3-coder-30b-96k",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": 81920,
      "trade_mcp_push_mode": null,
      "config_dir": null,
      "primary_output_type": "allocation_plan",
      "category": "claude_code_local"
    },
    {
      "role_key": "review01",
      "tmux_session": "review01",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "ornith35b-q5-64k",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "404_STRICT_REVIEW_REVIEW01.md",
      "default_runtime": "opencode",
      "default_provider": "local_ollama",
      "default_model": "ornith35b-q5-64k",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": "review01",
      "primary_output_type": null,
      "category": "opencode_local"
    },
    {
      "role_key": "review01_trade",
      "tmux_session": "review01_trade",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3.6-27b-48k",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "435_TRADE_REVIEW01.md",
      "default_runtime": "opencode",
      "default_provider": "local_ollama",
      "default_model": "qwen3.6-27b-48k",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": "glm52trade",
      "primary_output_type": "review_verdict",
      "category": "opencode_local"
    },
    {
      "role_key": "review01cloud",
      "tmux_session": "review01cloud",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3.6:27b-q4_K_M",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "414_CLOUD_LLM_REVIEW01CLOUD.md",
      "default_runtime": "opencode",
      "default_provider": "local_ollama",
      "default_model": "qwen3.6:27b-q4_K_M",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": "review01cloud",
      "primary_output_type": null,
      "category": "opencode_local"
    },
    {
      "role_key": "review01pay",
      "tmux_session": "review01pay",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3.6:27b-q4_K_M",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "424_CLOUD_PAY_REVIEW01PAY.md",
      "default_runtime": "opencode",
      "default_provider": "local_ollama",
      "default_model": "qwen3.6:27b-q4_K_M",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": "review01pay",
      "primary_output_type": null,
      "category": "opencode_local"
    },
    {
      "role_key": "review02",
      "tmux_session": "review02",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3.6:27b-q4_K_M",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "405_STRICT_REVIEW_REVIEW02.md",
      "default_runtime": "opencode",
      "default_provider": "local_ollama",
      "default_model": "qwen3.6:27b-q4_K_M",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": "review02",
      "primary_output_type": null,
      "category": "opencode_local"
    },
    {
      "role_key": "review02cloud",
      "tmux_session": "review02cloud",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3.6:35b-a3b",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "415_CLOUD_LLM_REVIEW02CLOUD.md",
      "default_runtime": "opencode",
      "default_provider": "local_ollama",
      "default_model": "qwen3.6:35b-a3b",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": "review02cloud",
      "primary_output_type": null,
      "category": "opencode_local"
    },
    {
      "role_key": "review02pay",
      "tmux_session": "review02pay",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3.6:35b-a3b",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "425_CLOUD_PAY_REVIEW02PAY.md",
      "default_runtime": "opencode",
      "default_provider": "local_ollama",
      "default_model": "qwen3.6:35b-a3b",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": "review02pay",
      "primary_output_type": null,
      "category": "opencode_local"
    },
    {
      "role_key": "risk01_trade",
      "tmux_session": "risk01_trade",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3-coder-30b-48k",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "434_TRADE_RISK01.md",
      "default_runtime": "claude",
      "default_provider": "local_ollama",
      "default_model": "qwen3-coder-30b-48k",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": "risk",
      "config_dir": null,
      "primary_output_type": "risk_verdict",
      "category": "claude_code_local"
    },
    {
      "role_key": "score01_trade",
      "tmux_session": "score01_trade",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3-coder-30b-48k",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "437_TRADE_SCORE01.md",
      "default_runtime": "claude",
      "default_provider": "local_ollama",
      "default_model": "qwen3-coder-30b-48k",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": null,
      "primary_output_type": "simulation_score",
      "category": "claude_code_local"
    },
    {
      "role_key": "sim01_trade",
      "tmux_session": "sim01_trade",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "ornith35b-q5-48k",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "436_TRADE_SIM01.md",
      "default_runtime": "claude",
      "default_provider": "local_ollama",
      "default_model": "qwen3.6:35b-a3b-64k",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": null,
      "config_dir": null,
      "primary_output_type": "simulation_order",
      "category": "claude_code_local"
    },
    {
      "role_key": "trend01_trade",
      "tmux_session": "trend01_trade",
      "model_type": "ollama",
      "cloud_model": "",
      "ollama_model": "qwen3.6-35b-48k",
      "role_type": "agent",
      "enter_command": "default",
      "governance_file": "431_TRADE_TREND01.md",
      "default_runtime": "claude",
      "default_provider": "local_ollama",
      "default_model": "qwen3.6-35b-48k",
      "default_model_source": null,
      "default_model_alias": null,
      "max_output_tokens": null,
      "trade_mcp_push_mode": "watchlist",
      "config_dir": null,
      "primary_output_type": "trend_note",
      "category": "claude_code_local"
    }
  ],
  "step_overrides": []
}
