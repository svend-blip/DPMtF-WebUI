-- 045: Rev_Imple's session reset moves from /clear to /new.
--
-- WHAT THE TWO DO. `/clear` is a soft clear: it sends a prompt telling the
-- model to disregard earlier context, and the session — with all of its
-- history and every token of it — continues. `/new` starts a genuinely new
-- session. Only the second reclaims the window.
--
-- WHY IT MATTERS HERE. Rev_Imple runs glm-air-derestricted-local, whose
-- window is 65,536 tokens. Rev_Supervisor already uses /new for the same
-- reason, and the implementer needs it more: it reads capture files and
-- source, so it fills a window faster than a supervisor reading contracts.
-- Under /clear its consumption is monotonic across an entire run — a soft
-- clear costs tokens rather than freeing them, because the instruction is
-- itself appended to the history it asks the model to ignore.
--
-- A MEASUREMENT THAT MOTIVATED THIS BUT DOES NOT DIRECTLY APPLY. On
-- 2026-08-12/13 an OpenCode + MiniMax-M3 session was driven through 31
-- turns of heredoc analysis over an 11 MB capture, without resetting
-- context. Structured tool calls degraded sharply and at a clean threshold:
--
--     18,092 - 468,954 tokens   22 turns, 0 failures
--    469,498 - 539,600 tokens    9 turns, 6 failures
--
-- A failed turn emitted MiniMax's pseudo-XML tool syntax as prose, ran no
-- tool, and ended with finish "stop" and no error. The internal check is
-- the context growth: a clean turn added ~21,500 tokens of tool output, a
-- failed one ~500, so the failures are exactly the turns where nothing ran.
--
-- That measurement is of MiniMax, not GLM, and no equivalent threshold has
-- been established for glm-air-derestricted-local. It is recorded here
-- because it shows accumulated context degrading tool-call reliability on
-- at least one model, which is a reason to keep sessions short generally —
-- not because 47% of a window is known to be dangerous for this one.
--
-- WHAT IT DOES NOT EXPLAIN. The reveng session that first showed this
-- failure was at 269k tokens, well inside the range that stayed clean in
-- the reproduction. Something lowered its threshold. The leading candidate
-- is that its history contained merged instructions from the delivery
-- defect fixed in 8c36e6d, where a /clear template and a task arrived as
-- one message. That is unproven, and is the open question this migration
-- does not close.
--
-- Idempotent: an UPDATE of an existing row; re-running changes nothing.

UPDATE bridge_roles
SET fresh_session_command = '/new',
    updated_at            = CURRENT_TIMESTAMP
WHERE role_key = 'Rev_Imple';
