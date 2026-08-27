-- 081: Move 1000-reviewer off Qwen38-Standard onto the FreeToken MoE alias.
--
-- Not a preference. The llama.cpp build serving Qwen38-Standard faulted the
-- GPU three times on 2026-08-27, each within a minute of starting:
--
--   10:37:42  NVRM: Xid (PCI:0000:01:00): 8, name=llama-server
--   11:21:06  NVRM: Xid (PCI:0000:01:00): 8, name=llama-server
--   11:25:40  NVRM: Xid (PCI:0000:01:00): 8, name=llama-server
--
-- All three are llama-server. None are FreeToken, which served for hours on
-- the same card the same day without a fault. The card itself is healthy:
-- 43 C, 15 W idle, no throttling, no ECC errors. The fault is specific to
-- that build, not to the hardware and not to load, so it left the Reviewer
-- unable to run at all — its verdict for run 002 handoff 3 was written and
-- then sat undeliverable while the chain watchdog escalated twice.
--
-- Consequence worth knowing before changing this back: the three ELOOP roles
-- now share ONE model. That is what `lifecycle_policy: stop_after_step` on
-- the alias already assumes — the flow swaps the resident model per role —
-- and it removes the 30 GB + 25 GB collision that made two aliases
-- unable to coexist on a 32 GB card anyway.
--
-- The Reviewer's context was 48.6K when this was written, against the
-- alias's measured 65536 KV budget. That fits, but not with much room. If a
-- review ever needs more, the answer is a declared limit and compaction, not
-- a larger allocation: 131072 was measured on this card and died under a
-- real prefill (see model-allocator eeac92c).
--
-- Idempotent: a plain UPDATE keyed on role_key, safe to re-run.

UPDATE bridge_roles
   SET default_model_alias = 'freetoken-qwen36-35b-a3b',
       updated_at          = datetime('now')
 WHERE role_key = '1000-reviewer';
