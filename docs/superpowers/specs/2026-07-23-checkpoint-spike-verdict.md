# Checkpoint Spike — Verdict

**Date:** 2026-07-23

## Question
Can every completed step produce a durable, model-independent continuation record?

## Results

### Schema (version 1.0)
22 fields covering:
- Identity (job_id, handoff_id, workflow_run_id, flow_key, step_key, role_key)
- Scope (approved_scope_version, scope_hash, base_commit, result_commit)
- Artifacts (changed_files, verification_results, test_results, implementation_summary, unresolved_items, artifacts)
- Model info (model_alias, resolved_backend, resolved_concrete_model, execution_adapter)
- Timestamps (started_at, completed_at)

### Tested capabilities (6 tests, all green):
- JSON roundtrip (serialize/deserialize)
- Missing field validation
- Schema version validation
- VerificationResult status validation
- Creation from runtime spike output
- Model independence — no conversation/scrollback in checkpoint

### Fresh-context continuation proof
The checkpoint contains everything the next role needs:
1. Changed files → the diff to review
2. Verification results → what passed/failed
3. Implementation summary → what was done
4. Model alias → which model was used (for debugging, not continuation)

It does NOT contain:
- Model conversation messages
- tmux scrollback
- OpenCode/Claude Code session state

## Verdict: GO

The checkpoint schema is viable. The next role can start from:
- The approved contract (handoff file)
- The checkpoint (this schema)
- The relevant diff (git diff)
- Required artifacts (changed_files list)

Production implementation should add:
- SQLite `checkpoints` table or JSON column on `jobs`
- `make_checkpoint()` called automatically after each `signal_complete`
- `load_checkpoint()` called by the next role's startup
- Scope hash computed from `11_SCOPE.md` content hash
