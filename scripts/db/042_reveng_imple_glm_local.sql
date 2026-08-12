-- 042: Rev_Imple moves from MiniMax-M3 to the local GLM-4.5-Air-Derestricted
--      that Rev_Supervisor already uses.
--
-- WHY. MiniMax-M3 returned its own pseudo-XML tool syntax as plain text
-- instead of structured tool_calls. The turn then ends normally — finish
-- "stop", no truncation, no error anywhere — with no tool executed, no
-- deliverable written and no signal sent. Measured from the role's own
-- OpenCode session exports:
--
--   sessions of 2026-08-11/12 (handoffs 001-010):  1 of 18 completed turns
--   session of 2026-08-12     (handoff 022):       5 of 7 completed turns
--
-- The second rate makes the role unusable: dispatch, nudge and manual
-- "continue" each produced one more dead turn. It is an upstream parser
-- failure and cannot be prevented from here.
--
-- GLM was verified to return structured tool_calls before it was adopted for
-- Rev_Supervisor (finish_reason "tool_calls", well-formed JSON arguments).
--
-- SHARING THE SUPERVISOR'S ALIAS IS INTENTIONAL. dispatch stops the outgoing
-- model only when from_alias != to_alias, so supervisor->imple no longer
-- tears the server down and reloads it — which also removes, for that step,
-- the case where signalling cuts the supervisor off mid-turn (491). The
-- alias runs one llama.cpp slot; these two roles never run concurrently, so
-- the only cost is prompt reprocessing when the active role changes.
--
-- CONSEQUENCE TO WATCH. Rev_Imple's window drops from MiniMax's 1,000,000
-- tokens to 65536. Its sessions were using ~29k, so the ceiling is not
-- obviously too low — but an implementer reading a large capture file will
-- find it sooner than the supervisor does.
--
-- ALLOCATOR SIDE (must match, or the binding is silently ignored):
--   roles.yaml -> Rev_Imple.client_aliases.opencode = glm-air-derestricted-local
--
-- The session must be restarted before this takes effect: the model comes
-- from opencode.json, which the allocator rewrites on the next `run`.
--
-- Idempotent: an UPDATE of an existing row; re-running changes nothing.

UPDATE bridge_roles
SET default_model_alias = 'glm-air-derestricted-local',
    updated_at          = CURRENT_TIMESTAMP
WHERE role_key = 'Rev_Imple';
