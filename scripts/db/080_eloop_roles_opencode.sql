-- 080: Move the two 1000 ELOOP execution roles from qwen to OpenCode.
--
-- Run 002 was blocked before its first handoff and the cause was not the
-- wiring. freetoken-qwen36-35b-a3b advertises `context: 262144` and actually
-- holds `num_tokens: 49152` — the runtime is VRAM-bound on a 32 GB card.
-- Qwen Code has no way to be told that: its context table is hardcoded and
-- contains only glm-* entries, so every other model falls to a ~1M default.
-- The decomposer filled the real budget while its own display read
-- "1.0m Context 4.9% used" — the same ~49k tokens, measured once against the
-- truth and once against an assumption. FreeToken then clamped the reply to
-- 31 tokens and the stream ended without visible progress.
--
-- That failure is deterministic, not transient: a client that cannot learn
-- its limit can never compress toward it, so every session ends the same way.
--
-- OpenCode CAN be told, through `limit.context` in its generated config, so
-- these two roles join the reviewer on OpenCode against the same alias. The
-- companion fix lives in model-allocator (adapters/opencode._client_context):
-- the config now carries the SMALLER of `context` and `num_tokens`. Without
-- it, OpenCode would have been told 262144 as well and this migration would
-- have relocated the failure rather than removed it.
--
-- allocator_client is written alongside default_harness_source only because
-- rows here carry the deprecated mirror; default_harness_source is the
-- authoritative source both readers consult first.
--
-- config_dir is set because OpenCode roles have one: the allocator renders
-- ~/.config/opencode-roles/<config_dir>/opencode.json before launch. The qwen
-- path needed no config file, which is why the column was empty.
--
-- Idempotent: a plain UPDATE keyed on role_key, safe to re-run.

UPDATE bridge_roles
   SET default_harness_source = 'opencode',
       allocator_client       = 'opencode',
       config_dir             = '1000-execution-decomposer',
       updated_at             = datetime('now')
 WHERE role_key = '1000-execution-decomposer';

UPDATE bridge_roles
   SET default_harness_source = 'opencode',
       allocator_client       = 'opencode',
       config_dir             = '1000-implementer',
       updated_at             = datetime('now')
 WHERE role_key = '1000-implementer';
