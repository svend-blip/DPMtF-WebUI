-- Migration: 2000_roles_deepseek
-- Human 2026-09-12: FlowRunner's eloop2000 has run the implementer and
-- reviewer on cloud_deepseek_v4pro_direct since GOAL-002 (the Flash
-- implementer overflowed max-turns). The 2000-02-ELOOP definition must
-- match what FlowRunner runs, so a future export of the flow imports
-- with the same models. The decomposer stays on cloud_qwen38flash.
-- Data-only; idempotent.
UPDATE bridge_roles
   SET default_model_alias = 'cloud_deepseek_v4pro_direct',
       updated_at = datetime('now')
 WHERE role_key IN ('2000-implementer', '2000-reviewer')
   AND default_model_alias IS NOT 'cloud_deepseek_v4pro_direct';
