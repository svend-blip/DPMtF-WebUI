# Contract analysis — IMPLEMENTOR.md & REVIEW.md for DSH workflow-loop architecture

Sources (read once each, line refs to them):
`docs/governance-templates-v2/IMPLEMENTOR.md` (=IMP, 627 lines), `docs/governance-templates-v2/REVIEW.md` (=REV, 423 lines).
Architecture assumed: DSH subagent calls, explicit provider/model per call; DECOMPOSER → IMPLEMENTOR → REVIEW (APPROVED|REJECTED) → SUPERVISOR, one execution loop; no BridgeV002/tmux/OpenCode/allocators; mcp-light stays; run dir holds `handoff.md` / `result.md` / `verdict.md`; configurable iteration cap.

## A. IMPLEMENTOR (IMP)

### Mandate
- Implementer for the active step; executes implementation handoffs, produces code/config changes within defined scope (IMP:7-9).
- Identity (flow/step/siblings) comes from injected RUNTIME CONTEXT; nothing hardcoded in the contract (IMP:11-15).
- Delivers results to the reviewer; one role active at a time, "the bridge ensures sequential execution" (IMP:19-21).

### Mandated inputs/outputs & paths
- Input: handoff file from injected prompt + `<role>` governance file + `<project>` target path; resolve target and `cd` FIRST (IMP:47-91; cd+pwd+git branch IMP:59-65; no Target Project block → Father default IMP:66-68).
- Result file: `{bridge_dir}/{flow_key}/results/{ID}-result.md` (IMP:270); notification `{ID}-notification.md` (IMP:325).
- Scratch files only in `{bridge_dir}/{flow_key}/runs/{run_id}/`, never the checkout (IMP:572-584, 610-618).

### Permitted vs forbidden
- Allowed: edits only inside the scope fence — "a file the handoff does not name is forbidden even when changing it would help" (IMP:87-89); fence authoritative over prose (IMP:173-174); multi-repo edits via absolute paths (IMP:151-174).
- Forbidden: governance edits unless fenced (IMP:118); new deps (IMP:124); subagents/self-review/planning agents (IMP:125); exploration beyond handoff scope (IMP:126); internal reasoning in output (IMP:127); committing (IMP:128, 380); editing what a check measures — no touch/revert-to-pass (IMP:253-262); guessing — document ambiguity instead (IMP:382-383).
- 6 Principles (no-change-over-unnecessary, existing helpers, stdlib, no new panels/schema/deps, prefer deletion, never reduce safety) (IMP:93-104).
- Language: en-US everywhere (IMP:384).

### Report format (exact fields)
- MUST start with XML sections — dispatch validation rejects files without them (IMP:272-288):
  `<handoff_id>` / `<source_role>` / `<deliverable_input>` (handoff path) / `<deliverable_output>` (result + notification paths).
- MUST end with `## README Impact` block: `README impact: yes|no` + `Reason:` (IMP:290-298).
- Body: `## Summary` / `## Target Project` (path @ branch) / `## Files Changed` / `## Validation Results` table incl. verbatim test summary + verbatim `git status --short` (IMP:300-321).
- Notification: `Status: IMPLEMENTED` / `Task Summary` / `Files Changed` / `Next Action` (IMP:327-333).

### Evidence requirements
- Run `<validation>` self-checks, paste VERBATIM output before signaling (IMP:90-91).
- `py_compile` / `node --check` / `bash -n` on changed files (IMP:119-121); run target's own suite with target's interpreter, quote summary line verbatim (IMP:122).
- Report only edits actually made — run `git status --short` + `git diff --stat` first (IMP:205-207); never invent output (IMP:208-211); doing-nothing/partial work are legitimate results (IMP:212-217).
- ANTI-FALSE-COMPLETION: result without `git status --short` + verbatim test summary is rejected; no "(except one test issue)" (IMP:219-222).
- Fence breach undeclared = rejection; dirty tree not yours → declare (IMP:229-241).

### Escalation / repetition
- Stop after 2 failed patch attempts → document and escalate, do NOT guess (IMP:123).
- Validation step fenced out = handoff defect: report and move on, never reconstruct output (IMP:242-251).
- Signal ONCE with explicit `--id`, verify once via trace.log grep; after TWO total failed attempts STOP and go idle (IMP:341-350).
- Post-signal: stop all activity immediately — one role active at a time (IMP:335-359).

### Git rules
- Read-only only: `status`/`diff`/`log`/`branch` (IMP:143). NEVER checkout/restore/reset/stash/clean/worktree — prior handoff's uncommitted work is unrecoverable (IMP:140-146).
- Never commit/push/amend; supervisor takes the checkpoint commit after APPROVED (IMP:128, 147-149).

### Model / harness naming
- Base file names no model, provider marker, or context threshold — deferred to model-lifecycle addendum (IMP:186, 194-196; Rule Inventory: model/cost prose deferred IMP:550-559).
- Silent tool-call failure (pseudo-XML shown as text): say so in result, do not retry into it (IMP:188-196).
- Fresh session per handoff; "run's memory lives in the files, not in you" (IMP:176-183).

## B. REVIEW (REV)

### Mandate
- Single Review layer for the active step; validates reality/scope/correctness/test evidence/governance/completeness; writes one-layer verdict for the downstream supervisor/decision role (REV:7-12).
- Two-role-deep chain; sole review layer; verdict IS the review the downstream reads (REV:22-28).

### Mandated inputs/outputs & paths
- Inputs: handoff + result file only from the implementer side; session isolated (REV:37-40).
- Verdict to "the exact deliverable path the dispatch prompt … names" — wrong name → `signal_complete_failed | Deliverable missing`, chain stalls silently (REV:171-179).
- Activated when implementer signals `signal_complete` (REV:47-48).
- Escalation file: `{bridge_dir}/{flow_key}/escalations/{ID}-{source_role_short}-question.md` (REV:279-283).

### Permitted vs forbidden
- Forbidden: commit/push/stage — supervisor commits from unstaged tree (REV:293-296); modifying implementation to make a check pass — report it (REV:297); treating verdict as the decision — it is input (REV:298-299); running checks in non-target Father (read-only reference) (REV:218-220).
- Core rule: "You review the working tree. You never review the result file" — result is a list of assertions to check (REV:65-79).
- Review order: Reality → Scope → Correctness → Test evidence → Governance → Completeness; N/A when artifact absent; PASS on absent files is a false claim (REV:81-95).
- mcp-light indexes Father only; never present it as evidence about a non-Father target (REV:57-60); unavailable → report the fixed sentence (REV:62-63).

### Verdict format (exact fields)
- `# Verdict {handoff_id}`; `**Status:** APPROVED | REJECTED`; `## Evidence`; `## Findings` ({claim} → VERIFIED|FALSE|UNVERIFIED (why)); `## Test Results` (test-impact scope/status, command→result, check_testgoals n/m + "by defect"/"by work"); `## Recommendation` (REV:181-205).
- Evidence section mandatory; verdict without it is rejected back (REV:207-209).

### Evidence requirements (absolute; breaking one invalidates verdict — REV:97-99)
1. Run commands yourself, paste real output (REV:101-103). 2. Never copy output from the result file (REV:104-106).
3. Start with `git status --short` + `git diff --stat`; claimed-but-absent file = REJECTED, stop (REV:107-109).
4. Check the specific assertion, not the area (REV:110-112). 5. Unverified = REJECTED (REV:113-114).
6. A passing check you did not run does not exist (REV:115-116). 7. Paste the command verbatim — garbled regex = false evidence (REV:117-122).
8. Measure the Run's testgoals via `check_testgoals.py` as the gate does; red-against-correct-work → "RED by defect" with alternative measurement (REV:123-134).
9. Closing test measure follows gate scope via test-impact evidence file; re-run selection when scope=PASS, else full suite; may escalate, never narrow (REV:135-148).
- "Counting Is Not Reading": prose questions are read and quoted, not grep-counted (REV:150-167).

### Escalation / repetition
- Escalate (ambiguity, cross-project impact, incomplete upstream result): write question file + `--signal-escalation` dispatch (REV:272-289).
- Verdict dispatch: verb per `auto_dispatch` step value; run once; "check that it worked" on `signal_complete_failed`, then stop (REV:226-244, 249-257).
- Post-signal: stop all activity; one role active at a time (REV:259-270).

### Git rules
- NEVER commit, push, or stage; staging breaks supervisor's scope check; committing is never the reviewer's job (REV:293-296).

### Model / harness naming
- Model/harness named by runtime context, never hardcoded — in the file or in the emitted verdict (REV:16-19, 32-33).
- Notes regardless of model: session isolated; implementer may have different client/context size → check specific claims (REV:34-43).

## CONFLICTS (rule contradicts / needs adapting for DSH loop)
1. "deliver implementation results to the reviewer" via bridge, "the bridge ensures sequential execution" (IMP:19-21) — no bridge; sequencing is the DSH execution loop.
2. Result path `{bridge_dir}/{flow_key}/results/{ID}-result.md` (IMP:270) — architecture uses run-dir `result.md` per handoff; template meaningless.
3. XML envelope mandates bridge paths incl. `notification: …{ID}-notification.md` (IMP:280-288) — no notification deliverable exists in the DSH loop.
4. Notification file itself (IMP:323-333) — superseded: supervisor is in-loop, no async handoff notification.
5. Signal machinery: `--signal-complete`/`--signal-send` verbs, trace.log verification, `signal_complete_failed`, `--db-path` prohibition (IMP:335-376) — no dispatch tool; DSH child call simply returns.
6. Scratch home `{bridge_dir}/{flow_key}/runs/{run_id}/` (IMP:574, 611) — bridge_dir template; becomes the run directory literal.
7. "Stop after 2 failures" fixed (IMP:123) vs configurable iteration cap — cap value must come from runtime, contract hardcodes 2.
8. Target-project fallback defined via "the project whose `scripts/bridgeV002/` contains the dispatch tool" (IMP:66-72) — no bridge; default-target rule needs a new anchor.
9. Reviewer activation "when the upstream implementer role signals completion via `signal_complete`" (REV:47-48) — no signal; the loop sequences REVIEW after IMPLEMENTOR returns.
10. Verdict path "named by the dispatch prompt and convention rules", else `signal_complete_failed | Deliverable missing` (REV:171-179) — no dispatch; path is fixed (`verdict.md` in run dir).
11. Verdict dispatch via `dispatch.py --signal-complete … --id {handoff_id}` (REV:241-247) and auto_dispatch verb logic (REV:226-238) — absent; same for escalation signal `--signal-escalation` (REV:284-289).
12. Testgoal measurement bound to `python3 scripts/bridgeV002/check_testgoals.py … from the Father checkout` (REV:125) — no BridgeV002 runtime; testgoal tooling must be re-anchored or dropped; REJECTED routing to "implementation or decomposition" has no contract hook — verdict reaches only "the supervisor/decision role" (REV:26-28), routing is the loop's job.

## SPLIT
Contract edits needed:
- Replace all signal/dispatch sections (IMP:335-376; REV:222-257) with "return to the execution loop"; delete trace.log/notification/escalation-signal mechanics (IMP:323-333, 341-350; REV:279-289).
- Re-anchor deliverable paths: `handoff.md` / `result.md` / `verdict.md` in run dir (IMP:270, 325; REV:171-179); simplify or drop the XML envelope to fields the loop actually needs (handoff_id, status) (IMP:272-288).
- Re-anchor or drop testgoal command + test-impact path (REV:123-148); re-anchor scratch dir (IMP:572-627) and target-project default (IMP:66-72).
- Make the patch-failure cap a runtime parameter (IMP:123).

Satisfied by runtime config / prompt (no contract edit):
- Provider/model per call: both files already defer model/harness to runtime context (IMP:186, 194-196; REV:16-19, 32-33) — DSH prompt injection satisfies the naming rule as written.
- Fresh session + isolation per call: native to DSH subagent calls (IMP:176-183; REV:37-40).
- Sequential single-role execution: enforced by the execution loop (matches IMP:21, REV:268-270).
- Target Project / RUNTIME CONTEXT blocks: carried in the call prompt (IMP:56-58; REV:213-216).
- mcp-light Context-First rules keep working unchanged (IMP:30-45; REV:51-63) — mcp-light stays available.
- Missing test-impact evidence → full suite fallback already handles absence (REV:142-143).
- Approver/implementor separation already contractually enforced (IMP:125 no self-review; REV:297 no fixing); APPROVED|REJECTED literals already match (REV:184); git rules (read-only, supervisor commits) carry over as-is (IMP:138-149; REV:293-296) if EXECUTION SUPERVISOR owns commits.
