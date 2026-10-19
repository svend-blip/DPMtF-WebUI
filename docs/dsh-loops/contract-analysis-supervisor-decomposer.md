# Contract Analysis — SUPERVISOR_PLANNING & EXECUTION_DECOMPOSER vs. DSH two-session architecture

Files: `docs/governance-templates-v2/SUPERVISOR_PLANNING.md` (SP, 560 ln), `docs/governance-templates-v2/EXECUTION_DECOMPOSER.md` (ED, 215 ln). Cites are file:line.

## 1. SUPERVISOR_PLANNING (SP)

### Mandate
- Planning Supervisor of a two-flow family (PLOOP plans, ELOOP executes) sharing one artifact root (SP:7-9). Turns Human scope into small promotable Run contracts; with a mandate, drives the chain until Runs close (SP:10-12).
- Mandate lives in DB: `bridge_flows.supervisor_mandate/commit_cadence/supervisor_role`; empty mandate → planning only (SP:53, SP:274-290).

### Inputs/outputs & paths
- `SCOPE.md` Human-only (SP:46); drafts `goals/{ID}-GOAL-DRAFT.md` (SP:48); run contract `runs/{NNN}/GOAL.md` written by `promote-goal` only (SP:49); `runs/{NNN}/RUN-LEDGER.md` (SP:50); `END-REPORT.md` written by the decomposer (SP:51); `planning/PLOOP-BACKLOG.md` (SP:52).
- Runs zero-padded `runs/007/`; chain deliverables unpadded `7-handoff.md` / `7-result.md` / `7-verdict.md` (SP:55-57).

### Permitted vs forbidden
- Never: implement/review/write handoff|result|verdict; promote; open a second Run; allocate ELOOP ids; edit SCOPE.md or a promoted GOAL.md; commit outside cadence; act on a verdict without measuring the tree (SP:479-490; SP:40; SP:144-145).
- Promotion is a Human act; supervisor types `promote-goal` only on explicit instruction with `--approved-by` (SP:148-153).
- 5d: re-measure every APPROVED verdict yourself via `git status/diff` + project checker — "two roles agreeing is not evidence" (SP:212-225).

### Handoff rules
- Size Runs to a handoff budget ≈4 (2 work + 2 reserve); decomposer turns Runs into handoffs, "that is its job, not yours" (SP:120-124).
- Kickoff prompt is the only opener of a Run; goes into the decomposer's tmux pane; assembled from `kickoff_packet.py`, 10 mandated items (SP:292-332; SP:39). Ledger first, prompt second, delivery verified third (SP:332).

### Verdict/escalation rules
- Verdict APPROVED → observe + self-verify; REJECTED → decomposer issues rework; verdict with no evidence section = invalid (SP:198-210).
- Escalations under `escalations/` → bounded decision: ANSWER / RETRY WITH CORRECTION (new id) / PARK (SP:208). Intervention ladder rungs 0-8; rung 8 parks for the Human (SP:377-429).

### Iteration limits
- No RUN-level cap. Re-delivery max two attempts per id (SP:396); "two consecutive failed nudges, a gate rejection repeating on the same handoff, or the same defect class three times in one Run: stop and park" (SP:431-432).

### Git rules
- Cadence `none|per_run|per_handoff` from DB (SP:436-445); per_run = add only in-fence approved paths, `git commit -m "[run-NNN] <objective>"`, push branch named in mandate, record sha as next baseline.
- "Never amend, never force-push, never commit to a branch the mandate does not name, never commit a rejected Run's tree" (SP:447-449). Chain roles: "No commits, no pushes, no staging" (SP:130, SP:451-453).

### Model/harness naming rules
- Contract is placeholder-only; "The RUNTIME CONTEXT block in your dispatch prompt names the concrete flow and role keys" (SP:21-23). Runtime assumptions baked in: tmux pane (SP:14), allocator launch status / `ollama ps` (SP:363, SP:369).

## 2. EXECUTION_DECOMPOSER (ED)

### Mandate
- Turns one approved `GOAL.md` into implementation handoffs, one at a time; "you do not implement, you do not review, and you do not plan new Runs" (ED:7-10). "You NEVER open a Run" — kickoff event required; never roll a close into the next Run in the same wake-up (ED:21-35).

### Inputs/outputs & paths
- READS `runs/{run_id}/GOAL.md` (ED:14); WRITES `handoffs/{ID}-handoff.md` (ED:15). Chain: `{ID}-handoff.md` → `{ID}-result.md` → `{ID}-verdict.md` (ED:39-49).
- END-REPORT lists every testgoal MEASURED via `check_testgoals.py` — "a verdict's word is not a measurement" (ED:68-74). `LEARNING-DRAFT.yaml` only at SUCCESS closure unless `> Learning: none` (ED:77-90).

### Permitted vs forbidden
- NEVER writes code, results, verdicts, GOAL files, or Run allocations (ED:16). Ambiguous GOAL → ESCALATION, "never be guessed into a handoff" (ED:17-20). Handoff "may narrow … may never widen" the fence (ED:184-188). "Git — read-only, always" (ED:212-215).

### Handoff rules
- One handoff = one coherent deliverable with verifiable evidence; follow the GOAL's decomposition or state the deviation (ED:107-109). Every handoff starts empty: baseline, deliverable, evidence, signal (ED:119-122).
- MUST state recipient's signal verb + the `auto_dispatch` value, phrased as the recipient's onward command (ED:156-182, ED:190-210). "You always signal a NEW handoff with `--signal-send --to-role {implementer}` … the flow counter allocates the id when you signal" (ED:207-210).

### Verdict/escalation rules
- APPROVED → next handoff; REJECT with a named decomposition defect → decomposer; implementation defect → Implementer (ED:61-64). Verdict wake-up carries `<verdict_summary>` / `<next_action>` blocks, read first (ED:93-99).
- Escalate when: GOAL ambiguous/contradictory; a testgoal can't go green; budget can't cover; "two consecutive verdicts rejected the same handoff" (ED:130-140).

### Iteration limits
- "The GOAL's handoff budget is a hard cap and you own its spending"; reserve ≥1 rework slot; when short, "STOP and escalate — do not compress"; never exceed the cap (ED:124-128).

### Git rules
- "You never commit, stage, stash, or push. Commit authority in this flow is deterministic (the Git gate) or the Human's — never yours." (ED:212-215).

### Model/harness naming rules
- No model names in the contract; roles addressed by key (IMPLEMENTOR, REVIEW); envelope skeleton from `handoff_skeleton.py` (ED:147-152).

## CONFLICTS

1. SP:40 / SP:234-235 / SP:481 — "Never … writes a handoff" — the SAME role+model as Session-2 Execution Supervisor may create ADDITIONAL HANDOFFS within the current RUN. The contract forbids exactly the authority the new supervisor holds. Needs a role-variant.
2. SP:40 — ELOOP column "Never … commits" — architecture gives git commit+push to Session 2's Execution Supervisor; commit authority moves into the execution side.
3. SP:14, SP:185, SP:294-295 — "a Claude Code session in your own tmux pane", kickoff "into the decomposer's tmux pane (the dispatcher's paste shape; never `signal-send`)" — no tmux in DSH; kickoff is a cross-session message.
4. SP:38, SP:49, SP:151 — promotion via `bridge_broker.py promote-goal` — no BridgeV002; Session 1 is the ONLY RUN creator and persists RUNs as files; the promotion ceremony needs a new mechanism (Human-gate may stay).
5. SP:53, SP:274-290 — mandate in `bridge_flows` DB rows — no DPMtF runtime; must move to repo/session config, including the "current RUN only" scope.
6. SP:171-172, SP:194-196, SP:342-375 — preconditions/event loop/watchers keyed on panes READY, `trace.log`, dispatch/materialize queues, `bridge-broker.service`, `events.jsonl`, allocator — all absent; Session 2's fixed workflow replaces them.
7. SP:297, SP:133, ED:69, ED:148 — `kickoff_packet.py`, `check_testgoals.py`, `handoff_skeleton.py` under `scripts/bridgeV002/` — deterministic packet/skeleton/checker helpers do not exist in the new runtime.
8. ED:156-176, ED:190-210 — entire signal-verb duty, `auto_dispatch` semantics, and "the flow counter allocates the id when you signal" — no BridgeV002 signals or counters; DSH runtime must define completion and handoff-id allocation.
9. ED:48 — "deterministic routing / Git gate → next handoff or END-REPORT" — replaced by the Execution Supervisor, who routes (re-invokes the decomposer, returns REJECTED for correction, closes the RUN).
10. ED:124-128 + SP:120-124 — budget owned by the decomposer, escalation on shortfall — vs architecture: supervisor may add handoffs; a CONFIGURABLE ITERATION CAP governs; cap hit must NOT mark an incomplete RUN COMPLETED. Neither contract has cap-hit≠complete (closure = END-REPORT + measured testgoals only, SP:227-237; outcome vocabulary is SUCCESS|PARTIAL|FAILED, SP:543 — "COMPLETED" is a new state that must be barred on cap hit).
11. ED:23-25, ED:56-67 — kickoffs come from "the Human or … the family's planning supervisor" — must explicitly add Session 2's Execution Supervisor re-invoking the decomposer within the current RUN; ED only models kickoff + verdict wake-ups.
12. ED:63 vs ED:140 — verdict word "REJECT" vs architecture APPROVED|REJECTED (SP:204 uses REJECTED); and default routing is REJECTED → implementer correction up to the cap, while ED escalates after "two consecutive verdicts rejected the same handoff" — the cap, not the second rejection, should bound in-RUN correction.
13. SP:363, SP:369 — "the allocator's `completed` event", "the allocator's launch status", "`ollama ps`" — Model/Harness Allocator is banned; models are fixed config names (llamacpp-p620-1/qwen35-122b-a10b-q5; strata-local; llamacpp-p620-2). The SP:21-23 RUNTIME CONTEXT injection is the correct surviving hook.
14. SP:443, SP:499, SP:545 — per_run cadence pushes unconditionally and the closed entry records "baseline <sha> committed/pushed (<cadence>)" — architecture: push ONLY if repo config allows, no force-push (SP:447 agrees), and a failed push must not be recorded as success; one "committed/pushed" field cannot express push-denied/failed.
15. SP:248-250, ED:77-90 — learning admit pipeline via the knowledge service's CLI — no DPMtF runtime; the file draft convention survives, admission has no home (partial conflict).

## SPLIT

### Needs contract edit (DSH variants of both files)
- Authority split + Execution-Supervisor role variant: extra handoffs allowed (C1), scoped commit/push (C2), current-RUN-only, never creates RUNs (keep SP:482 "never open a second Run").
- Replacement of promotion, kickoff, id-allocation, signal and routing mechanisms (C4, C8, C9, C11).
- Removal of runtime plumbing: tmux/pane, trace.log, watchers table, intervention-ladder host rungs, broker, bridgeV002 scripts (C3, C6, C7) — keep the durable-signal watcher rules (SP:342-355) in runtime-neutral form.
- Budget/cap model + closure semantics: cap hit → never COMPLETED (C10); budget ownership; verdict vocabulary REJECTED (C12).
- Mandate → repo/session config (C5); push-permission + split committed/pushed ledger field (C14); learning admission (C15).

### Satisfied by runtime config / prompts (no contract edit)
- Model/harness names (llamacpp-p620-1/qwen35-122b-a10b-q5, strata-local, llamacpp-p620-2, supervisor=strata-local) via session config + prompt injection — the RUNTIME CONTEXT pattern SP:21-23 already sanctions (C13).
- File-deliverable convention `runs/{NNN}/GOAL.md` + `{ID}-handoff/result/verdict.md` already matches (SP:55-57; ED:39-49).
- One-Run-at-a-time (SP:178), fence may-narrow-never-widen (ED:184-188), never-guess-escalate (ED:17-20), verify-the-tree-before-trusting-a-verdict (SP:212-225), RUN-ID in commit message + no force-push (SP:441-447) carry over unchanged.
- Iteration-cap VALUE and push-allow flag are config values once the cap semantics (C10) are written into the contract.
