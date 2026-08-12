-- 041: Rev_Supervisor moves from DeepSeek V4 Pro (hosted) to a local
--      GLM-4.5-Air-Derestricted served by llama.cpp, driven through OpenCode.
--
-- WHAT CHANGES, AND WHY IT IS MORE THAN A MODEL SWAP.
--
-- 040 wired all three reveng roles to hosted APIs, and 491 was written on
-- that basis: nothing is loaded or unloaded, there is no card to contend
-- for, and `ConnectionRefused` means a genuine outage. One local role
-- falsifies all three statements for that role, because dispatch's lifecycle
-- machinery is not flow-specific -- it stops the outgoing alias and starts
-- the incoming one on every step. Handing off to Rev_Imple now really does
-- shut the supervisor's server down, and the supervisor really does find
-- port 8080 refusing connections afterwards. 491 and the Rev-Eng skill are
-- revised in the same change; a migration that moved only these three
-- columns would leave the role reading instructions that misdiagnose its own
-- normal state.
--
-- THE FRONTEND CHANGES WITH THE MODEL. llama.cpp reaches a client through
-- @ai-sdk/openai-compatible, which is OpenCode's path, not Claude Code's --
-- so allocator_client becomes 'opencode' and the session-reset command
-- becomes OpenCode's own '/new' instead of Claude Code's '/clear'.
--
-- config_dir was NULL, which worked only because `model-allocator run` falls
-- back to the role key when it is unset. It is now stated, so the OpenCode
-- config directory (~/.config/opencode-roles/Rev_Supervisor) is a matter of
-- record rather than a coincidence of that fallback.
--
-- ALLOCATOR SIDE (must match, or the binding is silently ignored):
--   models.yaml  -> alias `glm-air-derestricted-local`
--                   (local_llamacpp_cuda0, port 8080, ctx 65536,
--                    n_cpu_moe 32, q8_0 KV, load_mode none)
--   roles.yaml   -> Rev_Supervisor.client_aliases.opencode = that alias
--
-- MEASURED 2026-08-12 on the 5090, with the model loaded:
--   load to /health 35s · VRAM 27.3 GB · RSS 37.7 GB
--   prompt 121 tok/s · generation 16.8 tok/s · tool_calls structured
--
-- Idempotent: an UPDATE of existing rows; re-running changes nothing.

UPDATE bridge_roles
SET default_model_alias = 'glm-air-derestricted-local',
    allocator_client    = 'opencode',
    fresh_session_command = '/new',
    config_dir          = 'Rev_Supervisor',
    updated_at          = CURRENT_TIMESTAMP
WHERE role_key = 'Rev_Supervisor';
