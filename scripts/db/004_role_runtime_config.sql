-- 004 — Role runtime configuration columns (config-consolidation pass,
-- 2026-07-11). Moves hardcoded dispatch/runtime behavior into visible,
-- frontend-editable role configuration per the "config must be visible
-- and configurable or deleted" principle.
--
-- trade_mcp_push_mode: which deterministic trade-mcp context dispatch
--   prepends to this role's work prompt (NULL = none, 'watchlist', 'risk').
--   Replaces the hardcoded _TRADE_MCP_PUSH dict in dispatch.py.
-- max_output_tokens: per-role CLAUDE_CODE_MAX_OUTPUT_TOKENS override
--   (NULL = machine-profile default). Replaces manual session hacks
--   (market01's 64k need, flow 067/068).

ALTER TABLE bridge_roles ADD COLUMN trade_mcp_push_mode TEXT;
ALTER TABLE bridge_roles ADD COLUMN max_output_tokens INTEGER;
