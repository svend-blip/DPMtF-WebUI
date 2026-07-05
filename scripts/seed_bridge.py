#!/usr/bin/env python3
"""seed_bridge.py — Seed bridge roles, flows, steps, and Machine Profile config.

This script seeds the INITIAL bridge state for a fresh database. It is
idempotent: INSERT OR IGNORE for new rows, WHERE field IS NULL for UPDATEs —
it NEVER overwrites user-configured values after the first seed.

Run AFTER init_db.py (which creates the schema):
    python3 scripts/init_db.py       # schema + canonical defaults
    python3 scripts/seed_bridge.py   # bridge roles/flows/steps (fresh DB only)

After seeding, all changes go through the frontend (role/flow/step editors)
or direct DB edits. The DB (databases/dpmtf.db) is committed to git for
rollback safety.

Per the principle: configuration must be visible & configurable (.env /
machine.local.json / frontend) or deleted — not hardcoded as invisible seed
data that overwrites user choices on restore.
"""

import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

DB_PATH = config.get_db_path()

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ═══════════════════════════════════════════════════════════════════════
# 1. ROLES — bridge_roles (INSERT OR IGNORE — never overwrites)
# ═══════════════════════════════════════════════════════════════════════

cursor.executemany(
    """INSERT OR IGNORE INTO bridge_roles
       (role_key, tmux_session, model_type, cloud_model, ollama_model,
        setup_script, teardown_script, deliver_error_msg) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    [
        # ── strict_review flow ──
        ("archi01", "archi01", "ollama", "", "qwen3.6:35b-a3b",
         "scripts/bridgeV002/role_setup.py", "scripts/bridgeV002/role_teardown.py",
         "archi01 session stopped unexpectedly. Check tmux status with 'tmux ls'."),
        ("imple01", "imple01", "ollama", "", "qwen3.6:27b-q4_K_M",
         "scripts/bridgeV002/role_setup.py", "scripts/bridgeV002/role_teardown.py",
         "imple01 session stopped unexpectedly. Start manually in tmux."),
        ("review01", "review01", "ollama", "", "qwen3.6:35b-a3b",
         "scripts/bridgeV002/role_setup.py", "scripts/bridgeV002/role_teardown.py",
         "review01 session stopped unexpectedly. Check tmux status with 'tmux ls'."),
        ("review02", "review02", "ollama", "", "qwen3.6:27b-q4_K_M",
         "scripts/bridgeV002/role_setup.py", "scripts/bridgeV002/role_teardown.py",
         "review02 session stopped unexpectedly."),
        ("human", "human", "ollama", None, None, None, None, None),
        # ── cloud_pay flow ──
        ("archi01pay", "archi01pay", "ollama", "", "qwen3.6:35b-a3b-64k",
         None, None, "archi01pay session stopped unexpectedly."),
        ("imple01pay", "imple01pay", "opencode", "", "minimax/MiniMax-M3",
         None, None, "imple01pay session stopped unexpectedly."),
        ("review01pay", "review01pay", "ollama", "", "qwen3.6:27b-q4_K_M",
         None, None, "review01pay session stopped unexpectedly."),
        ("review02pay", "review02pay", "ollama", "", "qwen3.6:35b-a3b",
         None, None, "review02pay session stopped unexpectedly."),
        ("humanpay", "humanpay", "ollama", None, None, None, None, None),
        # ── cloud_llm flow ──
        ("archi01cloud", "archi01cloud", "ollama", "", "qwen3.6:35b-a3b-64k",
         None, None, "archi01cloud session stopped unexpectedly."),
        ("imple01cloud", "imple01cloud", "freebuff", None, None,
         None, None, "imple01cloud session stopped unexpectedly."),
        ("review01cloud", "review01cloud", "ollama", "", "qwen3.6:27b-q4_K_M",
         None, None, "review01cloud session stopped unexpectedly."),
        ("review02cloud", "review02cloud", "ollama", "", "qwen3.6:35b-a3b",
         None, None, "review02cloud session stopped unexpectedly."),
        ("humancloud", "humancloud", "ollama", None, None, None, None, None),
        # ── trade_cockpit flow ──
        ("humantrade", "humantrade", "human", None, None, None, None, None),
        ("trend01_trade", "trend01_trade", "ollama", "", "qwen3.6:35b-a3b-64k",
         None, None, "trend01_trade session stopped unexpectedly."),
        ("market01_trade", "market01_trade", "ollama", "", "deepseek-v4-pro:cloud",
         None, None, "market01_trade session stopped unexpectedly."),
        ("analyst01_trade", "analyst01_trade", "opencode", "", "minimax/MiniMax-M3",
         None, None, "analyst01_trade session stopped unexpectedly."),
        ("risk01_trade", "risk01_trade", "ollama", "", "qwen3.6:35b-a3b-64k",
         None, None, "risk01_trade session stopped unexpectedly."),
        ("review01_trade", "review01_trade", "opencode", "", "z-ai/glm-5.2",
         None, None, "review01_trade session stopped unexpectedly."),
        ("sim01_trade", "sim01_trade", "ollama", "", "qwen3.6:27b-q4_K_M",
         None, None, "sim01_trade session stopped unexpectedly."),
        ("score01_trade", "score01_trade", "ollama", "", "qwen3.6:27b-q4_K_M",
         None, None, "score01_trade session stopped unexpectedly."),
        ("learn01_trade", "learn01_trade", "ollama", "", "qwen3.6:27b-q4_K_M",
         None, None, "learn01_trade session stopped unexpectedly."),
        ("portfolio01_trade", "portfolio01_trade", "ollama", "", "qwen3.6:27b-q4_K_M",
         None, None, "portfolio01_trade session stopped unexpectedly."),
    ],
)

# ═══════════════════════════════════════════════════════════════════════
# 2. FLOWS — bridge_flows (INSERT OR IGNORE)
# ═══════════════════════════════════════════════════════════════════════

cursor.executemany(
    """INSERT OR IGNORE INTO bridge_flows
       (flow_key, name, description, step_order, is_default, is_active) VALUES (?, ?, ?, ?, ?, ?)""",
    [
        ("strict_review", "Standard development flow",
         "human/archi01/imple01/review01/review02/human — full governance chain",
         None, 1, 1),
        ("cloud_pay", "Cloud Pay",
         "Using Anthropic API via proxy — trade-ui development",
         None, 0, 1),
        ("cloud_llm", "Using Cloud Freebuff",
         "Cloud LLM development flow",
         None, 0, 1),
        ("trade_cockpit_simulation_v001", "Trade Cockpit Simulation",
         "Daily research-to-simulation chain: trend01→market01→analyst01→risk01→review01→sim01",
         None, 0, 1),
        ("trade_cockpit_scoring_v001", "Trade Cockpit Scoring",
         "Periodic scoring and learning: score01→learn01",
         None, 0, 1),
    ],
)
# Trade Cockpit flows use auto-chain + machine profiles (only set if NULL).
cursor.executemany(
    "UPDATE bridge_flows SET auto_complete_enabled=1, use_machine_profile=1 "
    "WHERE flow_key=? AND auto_complete_enabled IS NULL",
    [("trade_cockpit_simulation_v001",), ("trade_cockpit_scoring_v001",)],
)

# ═══════════════════════════════════════════════════════════════════════
# 3. FLOW STEPS — bridge_flow_steps (INSERT OR IGNORE)
# ═══════════════════════════════════════════════════════════════════════

_trade_inbox = config.get_trade_inbox_dir()

cursor.executemany(
    """INSERT OR IGNORE INTO bridge_flow_steps
       (flow_key, step_key, from_role, to_role, deliverable_dir, deliverable_pattern,
        pre_dispatch_script, post_dispatch_script, error_msg, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    [
        # ── strict_review (4-step manual chain) ──
        ("strict_review", "archi01-imple01", "archi01", "imple01",
         "strict_review/handoffs", "{ID}-handoff.md", None, "post-dispatch-common",
         "Failed to deliver handoff to {to_role}.", 1),
        ("strict_review", "imple01-review01", "imple01", "review01",
         "strict_review/results", "{ID}-result.md", None, "post-dispatch-common",
         "Failed to deliver callback to {to_role}.", 2),
        ("strict_review", "review01-review02", "review01", "review02",
         "strict_review/reviews", "{ID}-review01.md", None, "post-dispatch-common",
         "Failed to deliver callback to {to_role}.", 3),
        ("strict_review", "review02-human", "review02", "human",
         "strict_review/verdicts", "{ID}-verdict.md", None, "post-dispatch-common",
         "Failed to deliver verdict. Present to {to_role} manually.", 4),
        # ── cloud_pay (4-step manual chain) ──
        ("cloud_pay", "archi01-imple01", "archi01pay", "imple01pay",
         "cloud_pay/handoffs", "{ID}-handoff.md", None, "post-dispatch-common",
         "Failed to deliver handoff to {to_role}.", 1),
        ("cloud_pay", "imple01-review01", "imple01pay", "review01pay",
         "cloud_pay/results", "{ID}-result.md", None, "post-dispatch-common",
         "Failed to deliver callback to {to_role}.", 2),
        ("cloud_pay", "review01-review02", "review01pay", "review02pay",
         "cloud_pay/reviews", "{ID}-review01.md", None, "post-dispatch-common",
         "Failed to deliver callback to {to_role}.", 3),
        ("cloud_pay", "review02-human", "review02pay", "humanpay",
         "cloud_pay/verdicts", "{ID}-verdict.md", None, "post-dispatch-common",
         "Failed to deliver verdict. Present to {to_role} manually.", 4),
        # ── trade_cockpit_simulation (7-step auto-chain) ──
        ("trade_cockpit_simulation_v001", "human-trend01", "humantrade", "trend01_trade",
         _trade_inbox, "{ID}_{role_key}.json", None, "post-dispatch-common",
         "Failed to deliver to {to_role}.", 1),
        ("trade_cockpit_simulation_v001", "trend01-market01", "trend01_trade", "market01_trade",
         _trade_inbox, "{ID}_{role_key}.json", None, "post-dispatch-common",
         "Failed to deliver to {to_role}.", 2),
        ("trade_cockpit_simulation_v001", "market01-analyst01", "market01_trade", "analyst01_trade",
         _trade_inbox, "{ID}_{role_key}.json", None, "post-dispatch-common",
         "Failed to deliver to {to_role}.", 3),
        ("trade_cockpit_simulation_v001", "analyst01-risk01", "analyst01_trade", "risk01_trade",
         _trade_inbox, "{ID}_{role_key}.json", None, "post-dispatch-common",
         "Failed to deliver to {to_role}.", 4),
        ("trade_cockpit_simulation_v001", "risk01-review01", "risk01_trade", "review01_trade",
         _trade_inbox, "{ID}_{role_key}.json", None, "post-dispatch-common",
         "Failed to deliver to {to_role}.", 5),
        ("trade_cockpit_simulation_v001", "review01-sim01", "review01_trade", "sim01_trade",
         _trade_inbox, "{ID}_{role_key}.json", None, "post-dispatch-common",
         "Failed to deliver to {to_role}.", 6),
        ("trade_cockpit_simulation_v001", "sim01-portfolio01", "sim01_trade", "portfolio01_trade",
         _trade_inbox, "{ID}_{role_key}.json", None, "post-dispatch-common",
         "Failed to deliver to {to_role}.", 7),
        # ── trade_cockpit_scoring (2-step auto-chain) ──
        ("trade_cockpit_scoring_v001", "human-score01", "humantrade", "score01_trade",
         _trade_inbox, "{ID}_{role_key}.json", None, "post-dispatch-common",
         "Failed to deliver to {to_role}.", 1),
        ("trade_cockpit_scoring_v001", "score01-learn01", "score01_trade", "learn01_trade",
         _trade_inbox, "{ID}_{role_key}.json", None, "post-dispatch-common",
         "Failed to deliver to {to_role}.", 2),
    ],
)
# Trade Cockpit steps auto-chain (only set if NULL — never overwrites).
cursor.execute(
    "UPDATE bridge_flow_steps SET auto_chain_to_next = 1 "
    "WHERE flow_key IN ('trade_cockpit_simulation_v001', 'trade_cockpit_scoring_v001') "
    "AND auto_chain_to_next IS NULL"
)

# ═══════════════════════════════════════════════════════════════════════
# 4. GOVERNANCE FILE MAPPING (UPDATE — only sets NULL fields)
# ═══════════════════════════════════════════════════════════════════════

cursor.executemany(
    "UPDATE bridge_roles SET governance_file = ? WHERE role_key = ? AND governance_file IS NULL",
    [
        ("401_STRICT_REVIEW_HUMAN.md", "human"),
        ("402_STRICT_REVIEW_ARCHI01.md", "archi01"),
        ("403_STRICT_REVIEW_IMPLE01.md", "imple01"),
        ("404_STRICT_REVIEW_REVIEW01.md", "review01"),
        ("405_STRICT_REVIEW_REVIEW02.md", "review02"),
        ("422_CLOUD_PAY_ARCHI01PAY.md", "archi01pay"),
        ("423_CLOUD_PAY_IMPLE01PAY.md", "imple01pay"),
        ("424_CLOUD_PAY_REVIEW01PAY.md", "review01pay"),
        ("425_CLOUD_PAY_REVIEW02PAY.md", "review02pay"),
        ("431_TRADE_TREND01.md", "trend01_trade"),
        ("432_TRADE_MARKET01.md", "market01_trade"),
        ("433_TRADE_ANALYST01.md", "analyst01_trade"),
        ("434_TRADE_RISK01.md", "risk01_trade"),
        ("435_TRADE_REVIEW01.md", "review01_trade"),
        ("436_TRADE_SIM01.md", "sim01_trade"),
        ("437_TRADE_SCORE01.md", "score01_trade"),
        ("438_TRADE_LEARN01.md", "learn01_trade"),
        ("440_TRADE_PORTFOLIO01.md", "portfolio01_trade"),
    ],
)

# ═══════════════════════════════════════════════════════════════════════
# 5. CONFIG_DIR (UPDATE — only sets NULL fields)
# ═══════════════════════════════════════════════════════════════════════

cursor.executemany(
    "UPDATE bridge_roles SET config_dir = ? WHERE role_key = ? AND config_dir IS NULL",
    [
        # Tuple order is (config_dir, role_key) — SQL is "SET config_dir = ? WHERE role_key = ?".
        # Each opencode role gets its own per-role config dir under ~/.config/opencode-roles/.
        ("imple01", "imple01"),
        ("review01", "review01"),
        ("review01cloud", "review01cloud"),
        ("review01pay", "review01pay"),
        ("review02", "review02"),
        ("review02cloud", "review02cloud"),
        ("review02pay", "review02pay"),
        ("glm52trade", "review01_trade"),
        ("imple01pay", "imple01pay"),
        ("imple01", "analyst01_trade"),
    ],
)

# ═══════════════════════════════════════════════════════════════════════
# 6. MACHINE PROFILE — default_runtime/provider/model (UPDATE — only if all NULL)
# ═══════════════════════════════════════════════════════════════════════

cursor.executemany(
    """UPDATE bridge_roles
       SET default_runtime = ?, default_provider = ?, default_model = ?
       WHERE role_key = ?
         AND default_runtime IS NULL
         AND default_provider IS NULL
         AND default_model IS NULL""",
    [
        # Claude + local_ollama
        ("claude", "local_ollama", "qwen3.6:35b-a3b-64k", "archi01"),
        ("claude", "local_ollama", "qwen3.6:35b-a3b-64k", "archi01cloud"),
        ("claude", "local_ollama", "qwen3.6:35b-a3b-64k", "trend01_trade"),
        ("claude", "local_ollama", "qwen3.6:35b-a3b-64k", "risk01_trade"),
        ("claude", "local_ollama", "qwen3.6:27b-q4_K_M", "learn01_trade"),
        ("claude", "local_ollama", "qwen3.6:27b-q4_K_M", "score01_trade"),
        ("claude", "local_ollama", "qwen3.6:27b-q4_K_M", "sim01_trade"),
        ("claude", "local_ollama", "qwen3.6:27b-q4_K_M", "portfolio01_trade"),
        # Claude + cloud_ollama
        ("claude", "cloud_ollama", "deepseek-v4-pro:cloud", "market01_trade"),
        # Claude + openrouter
        ("claude", "openrouter", "z-ai/glm-5.2", "archi01pay"),
        # OpenCode + local_ollama
        ("opencode", "local_ollama", "qwen3.6:27b-q4_K_M", "review01"),
        ("opencode", "local_ollama", "qwen3.6:27b-q4_K_M", "review01cloud"),
        ("opencode", "local_ollama", "qwen3.6:27b-q4_K_M", "review01pay"),
        ("opencode", "local_ollama", "qwen3.6:35b-a3b", "review02"),
        ("opencode", "local_ollama", "qwen3.6:35b-a3b", "review02cloud"),
        ("opencode", "local_ollama", "qwen3.6:35b-a3b", "review02pay"),
        ("opencode", "local_ollama", "qwen3.6-27b-coder:latest", "imple01"),
        # OpenCode + opencode_builtin
        ("opencode", "opencode_builtin", "minimax/MiniMax-M3", "analyst01_trade"),
        # OpenCode + openrouter
        ("opencode", "openrouter", "moonshotai/kimi-k2.7-code", "imple01pay"),
        ("opencode", "openrouter", "z-ai/glm-5.2", "review01_trade"),
        # Freebuff
        ("freebuff", None, "freebuff-default", "imple01cloud"),
    ],
)

# ═══════════════════════════════════════════════════════════════════════
# 7. ENTER_COMMAND NORMALIZATION (idempotent — enforces canonical state)
# ═══════════════════════════════════════════════════════════════════════

# Only freebuff (imple01cloud) uses the two-step 'c-m' Enter style.
# All other roles use 'default'. This normalizes stale values from old restores.
cursor.execute("UPDATE bridge_roles SET enter_command = 'default'")
cursor.execute(
    "UPDATE bridge_roles SET enter_command = 'c-m' WHERE role_key = 'imple01cloud'"
)

# ═══════════════════════════════════════════════════════════════════════
# 8. COUNTERS — bridge_id_counters (INSERT OR IGNORE — never overwrites)
# ═══════════════════════════════════════════════════════════════════════

cursor.executemany(
    """INSERT OR IGNORE INTO bridge_id_counters (flow_key, next_id) VALUES (?, ?)""",
    [
        ("strict_review", 1),
        ("cloud_pay", 1),
        ("cloud_llm", 1),
        ("trade_cockpit_simulation_v001", 1),
        ("trade_cockpit_scoring_v001", 1),
    ],
)

# ═══════════════════════════════════════════════════════════════════════
# Commit + summary
# ═══════════════════════════════════════════════════════════════════════

conn.commit()

roles = cursor.execute("SELECT COUNT(*) FROM bridge_roles").fetchone()[0]
flows = cursor.execute("SELECT COUNT(*) FROM bridge_flows").fetchone()[0]
steps = cursor.execute("SELECT COUNT(*) FROM bridge_flow_steps").fetchone()[0]
counters = cursor.execute("SELECT COUNT(*) FROM bridge_id_counters").fetchone()[0]

print(f"Bridge seed complete: {roles} roles, {flows} flows, {steps} steps, {counters} counters.")
print("All idempotent — re-running this script will NOT overwrite user-configured values.")

conn.close()
