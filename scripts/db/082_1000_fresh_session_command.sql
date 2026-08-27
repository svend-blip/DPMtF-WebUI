-- 082: Give the four 1000-* roles the context reset every other flow already has.
--
-- Human-stated design rule, 2026-08-27: "Context skal resettes ved skift af
-- rolle, det er en af ideerne ved opdelingen i forskellige roller og lokal
-- afvikling." The roles are meant to be stateless between dispatches and to
-- rebuild what they need from durable files — GOAL.md, the run ledger, the
-- verdict, trace.log. That is why each of them has a cold-start skill.
--
-- The mechanism already exists and is not new here. `dispatch.inject_prompt`
-- sends `bridge_roles.fresh_session_command` as its OWN submission before the
-- task text, and every role in every other flow carries it — 39 of them,
-- `/new` for opencode and pi, `/clear` for claude-code. The four 1000-* roles
-- were the ONLY ones left empty, so their sessions accumulated across every
-- handoff of a run.
--
-- Measured consequence, run 002 on 2026-08-27: 1000-execution-decomposer
-- reached 88% of its 65536-token KV budget on its THIRD handoff and OpenCode
-- began an automatic compaction. Nothing failed — the compaction is
-- preventive, firing at (65536 - 8192)/65536 — but the role then continues
-- from a summary of its own earlier turns rather than from the files. That is
-- the state the split into roles exists to avoid, and it arrives silently.
--
-- `/new` is an OpenCode BUILT-IN (`command.session.new`), not one of the two
-- custom commands defined in the role config dirs (`clear`, `rev-eng`).
-- Verified in the installed binary before this migration was written, because
-- a fresh_session_command that does not exist is not a no-op: it would be
-- typed into the prompt box ahead of the task.
--
-- 1000-escalation-supervisor is deliberately NOT given one. It runs the dsh
-- harness in headless profile, which start_coding.py invokes one-shot per
-- wakeup — it holds no resident session to reset, and a slash command sent to
-- its Harness Terminal would land in a bash prompt.
--
-- Not affected, and deliberately so: `_handle_gate_rejection` returns a
-- blocked deliverable to its author WITHOUT a fresh_session_command, because
-- that role needs to remember what it was doing in order to fix it. This
-- migration does not touch that path.
--
-- Idempotent: plain UPDATEs keyed on role_key, safe to re-run.

UPDATE bridge_roles
   SET fresh_session_command = '/new',
       updated_at            = datetime('now')
 WHERE role_key IN ('1000-execution-decomposer',
                    '1000-implementer',
                    '1000-reviewer');

UPDATE bridge_roles
   SET fresh_session_command = '/clear',
       updated_at            = datetime('now')
 WHERE role_key = '1000-planning-supervisor';
