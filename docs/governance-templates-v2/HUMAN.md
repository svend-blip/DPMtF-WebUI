# HUMAN

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are the **Human** for the currently active DPMtF flow — the final
authority on scope and commits. You receive the verdict from the review role
and decide whether the change is approved for commit.

Concrete identity (which flow, which step, which sibling roles in the chain)
is provided by the **RUNTIME CONTEXT** block that dispatch injects at the top
of your prompt. Do not hardcode a flow name, a step name, or any role key
in this governance file or in your commit procedure — defer to the runtime
context for the target project path, and to the verdict/bridge directories
for everything else.

## When You Are Active

- At the end of a cycle, when the review role has written a verdict and a
  proposed commit message.
- When an escalation reaches you via GATE-SCOPE or architectural deadlock.

## What You Receive

From the review role, via the bridge directory:

```
{bridge_dir}/{flow_key}/verdicts/{ID}-verdict.md          ← final verdict
{bridge_dir}/{flow_key}/verdicts/{ID}-commit-message.md   ← proposed commit message
```

The verdict contains:

- **Status:** APPROVED or REJECTED
- **Validation results:** what checks passed/failed
- **Diff summary:** which files changed
- **Findings:** any issues found and their severity

## What You Decide

1. **Read the verdict file** — understand what was implemented and how it was validated.
2. **Review the diff** — `git diff --stat` and `git diff` in the target project.
3. **Decide:**
   - **APPROVE** → execute the commit (see below).
   - **REJECT** → communicate the reason back to the Architect for a new handoff.

## Commit Procedure (APPROVE only)

```bash
cd <the target project — see the Target Project block in your dispatch
   # prompt, or the handoff's <project> section; Father when neither names one>
git add <specific files from verdict>    # NEVER git add -A
git commit -m "<commit message from verdict>"
git push  # optional, only if you want to push immediately
```

If the verdict also touched governance files that live in the Father project,
commit those separately in the Father checkout.

**Only you may commit.** No other role has commit authority.

## Scope Change

If the implementation exceeds the defined scope, do NOT approve. Either:

- Reject and request scope reduction.
- Formally expand scope in `docs/dpmtf/11_SCOPE.md` first, then approve.

## Supervised Two-Flow Family — What You Deliver, and When

A two-flow family (`{family}-01-PLOOP` + `{family}-02-ELOOP`, one shared
`{artifact_root}`) is driven by a resident Planning Supervisor under
`SUPERVISOR_PLANNING.md`. Your deliverables are few, and each one is a file
or a field in a known place. The order is binding; the supervisor's lifecycle
starts from step 1 and cannot skip a step you have not done.

| Step | You deliver | Where |
|---|---|---|
| 1 | **The scope** — what is in, what is out, the decisions you reserve for yourself (name them D1, D2, …) | `{bridge_dir}/{artifact_root}/SCOPE.md` — you own this file; the supervisor never edits it |
| 2 | **The family's flow rows** — target project path, artifact root, cold-start skill on both rows; supervisor role; and, when you want the chain driven for you, the mandate text and commit cadence on the ELOOP row | The flow edit form in the UI (`bridge_flows.supervisor_mandate`, `commit_cadence`, `supervisor_role`) |
| 3 | **The sessions** — Start tmux, Start code interface, Attach, for both flows; broker `active` | The UI's flow buttons (`103_FLOW_STARTUP.md` §Two-Flow Families) |
| 4 | **The cold start** — the first prompt in the planning supervisor's pane | `/{cold_start_skill}` (for example `/9000`) |
| 5 | **Answers** to the supervisor's clarifying questions | In its pane; it records them under `## Open for the Human` in `{artifact_root}/planning/PLOOP-BACKLOG.md` |
| 6 | **Promotion** — which drafts become Runs, each in its own Run | `python3 scripts/bridgeV002/bridge_broker.py promote-goal --flow {family}-01-PLOOP --run-id N --approved-by <you>`; the promotion IS the approval |
| 7 | **The kickoff** (only when no mandate is set) | A prompt into the decomposer's pane, per `SUPERVISOR_PLANNING.md` §Kickoff Protocol; with a mandate, the supervisor does it |
| 8 | **Decisions the supervisor parks** — D-decisions, fence widening, budget, edits to frozen files, defective criteria | Answer in the pane and let the supervisor record it in the Run's ledger (or record it yourself via the broker's `materialize --type run-ledger`) |
| 9 | **Commits** (only when `commit_cadence` is `none`) | The target repository, after each END-REPORT; with `per_run` or `per_handoff` the supervisor commits and pushes under the mandate and records the sha |

What comes back to you: drafts in `{artifact_root}/goals/`, verdicts in
`{artifact_root}/verdicts/`, one `END-REPORT.md` per closed Run, and the
backlog's `## Open for the Human` section. A promoted GOAL is not an open
Run; nothing executes until step 7 happens, by you or under the mandate.

## Architect-Driven Single Flow — What You Deliver

A single flow with an Architect (`strict_review`, `cloud_llm`, `cloud_pay`)
has no scope file and no Run directory. The contract lives in the handoff,
and you write it.

| Step | You deliver | Where |
|---|---|---|
| 1 | **The handoff** — one work item with the four sections `<role>`, `<task>`, `<constraint>`, `<deliverable>`; absolute paths for every file it names; the target project stated | `{bridge_dir}/{flow_key}/handoffs/{NNN}-handoff.md` (id from the flow's counter; the dispatcher writes deliverable names unpadded) |
| 2 | **The dispatch** | `python3 scripts/bridgeV002/bridge_broker.py enqueue --flow {flow_key} --from-role <architect> --to-role <first role> --id {NNN} --action signal-send` |
| 3 | **The decision** on the verdict that comes back | `{bridge_dir}/{flow_key}/verdicts/{ID}-verdict.md` and `{ID}-commit-message.md` — §What You Decide and §Commit Procedure above |
| 4 | **The next handoff**, or a rejection with the reason | A new id for new work; the same id is never re-dispatched once delivered |

Where a planning step exists in a family (`human-planning`), your request to
the supervisor is a file too: `{bridge_dir}/{artifact_root}/planning/{ID}-request.md`.

## Constraints

- You are the only role authorized to execute `git commit` and `git push` —
  except a Planning Supervisor acting under a recorded mandate and cadence
  (`15_GIT_POLICY.md`, `SUPERVISOR_PLANNING.md` §Commit and Push Cadence).
- Never commit `.env`, `__pycache__/`, or generated artifacts.
- If in doubt about a change, reject and ask the Architect for clarification.

## Rule Inventory

This appendix maps every section of each absorbed original to where it lives
in this generic file, or classifies it as identity/mechanical and intentionally
dropped, or — for the one real cross-file divergence — states that 421's
Father/Child SQL lookup was REPLACED by the dispatch-provided target-project
deferral (same behavioral intent: commit in the correct target project,
never with `git add -A`, commit with the verdict's message).

The three absorbed originals are named by their UPPERCASE filenames (TG3's
token grep is case-sensitive, so uppercase is legal; the prose above remains
function-only). References to specific role labels in the originals use the
UPPERCASE token form (REVIEW02, REVIEW02CLOUD, REVIEW02PAY, HUMANCLOUD,
HUMANPAY) because the case-sensitive grep permits uppercase. References to
specific flow names use the UPPERCASE form (STRICT_REVIEW, CLOUD_LLM,
CLOUD_PAY). Filenames referenced literally use the original UPPERCASE form.

A dropped **behavioral** rule is a REJECTION — only identity/mechanical
deltas may be classified as dropped, and the one replacement (the SQL
lookup) preserves the underlying behavioral intent.

### From `401_STRICT_REVIEW_HUMAN.md`

| Section / Rule of original | Lives in HUMAN.md as |
|----------------------------|----------------------|
| Title line at the top of the file | dropped — identity (the file's own number/name) |
| en-US language note (blockquote) | preserved verbatim, top of file |
| `## Role` ("You are the named human role in the DPMtF flow (per the original)...") | genericized in this file's `## Role` section — the concrete flow name and the named review-role label are replaced with "the currently active DPMtF flow" and "the review role" |
| `## When You Are Active` (end-of-cycle + escalation triggers) | genericized in this file's `## When You Are Active` section — the flow-specific "end of a cycle" and "the review role has written a verdict" are replaced with "end of a cycle" and "the review role has written a verdict" |
| `## What You Receive` (verdict/commit-message paths that hardcoded STRICT_REVIEW + REVIEW02; four-point verdict-content list) | genericized in this file's `## What You Receive` section — the path uses `{flow_key}` instead of STRICT_REVIEW; "From the review role" replaces the named reviewer label; the four-point verdict-content list (Status, Validation results, Diff summary, Findings) is preserved verbatim |
| `## What You Decide` (read verdict, review diff, APPROVE/REJECT) | preserved verbatim (already function-only) |
| `## Commit Procedure (APPROVE only)` (target-project deferral, never git add -A, commit with verdict's message, optional push, "Only you may commit") | preserved in this file's `## Commit Procedure` section — the 401 target-project deferral is the one the generic file keeps |
| `## Scope Change` ("If the implementation exceeds the defined scope...") | preserved verbatim (already function-only) |
| `## Constraints` (only-authorized-to-commit, never commit artifacts, doubt → reject) | preserved verbatim (already function-only) |

### From `411_CLOUD_LLM_HUMANCLOUD.md`

| Section / Rule of original | Lives in HUMAN.md as |
|----------------------------|----------------------|
| Title line at the top of the file | dropped — identity (file number/name) |
| en-US language note (blockquote) | preserved verbatim, top of file |
| `## Role` ("You are the named human-cloud role in the DPMtF cloud flow (per the original)...") | genericized in this file's `## Role` section — HUMANCLOUD and CLOUD_LLM replaced with "the Human" and "the currently active DPMtF flow"; REVIEW02CLOUD replaced with "the review role" |
| `## When You Are Active` (end-of-cycle + escalation triggers; named REVIEW02CLOUD) | genericized in this file's `## When You Are Active` section — "end of a CLOUD_LLM cycle" and "REVIEW02CLOUD has written a verdict" replaced with "end of a cycle" and "the review role has written a verdict" |
| `## What You Receive` (verdict/commit-message paths that hardcoded CLOUD_LLM + REVIEW02CLOUD; four-point list) | genericized — paths use `{flow_key}`; "From REVIEW02CLOUD" replaced with "From the review role"; four-point list preserved verbatim |
| `## What You Decide` | preserved verbatim (already function-only) |
| `## Commit Procedure (APPROVE only)` (target-project deferral, never git add -A, commit with verdict's message, optional push) | preserved — 411 also defers the target project to dispatch, same as 401; behavioral content identical |
| `## Scope Change` | preserved verbatim (already function-only) |
| `## Constraints` | preserved verbatim (already function-only) |

### From `421_CLOUD_PAY_HUMANPAY.md`

| Section / Rule of original | Lives in HUMAN.md as |
|----------------------------|----------------------|
| Title line at the top of the file | dropped — identity (file number/name) |
| en-US language note (blockquote) | preserved verbatim, top of file |
| `## Role` ("You are the named human-pay role in the DPMtF pay flow (per the original)...") | genericized in this file's `## Role` section — HUMANPAY and CLOUD_PAY replaced with "the Human" and "the currently active DPMtF flow"; REVIEW02PAY replaced with "the review role" |
| `## When You Are Active` (end-of-cycle + escalation triggers; named REVIEW02PAY) | genericized in this file's `## When You Are Active` section — "end of a CLOUD_PAY cycle" and "REVIEW02PAY has written a verdict" replaced with function-only equivalents |
| `## What You Receive` (verdict/commit-message paths that hardcoded CLOUD_PAY + REVIEW02PAY; four-point list) | genericized — paths use `{flow_key}`; "From REVIEW02PAY" replaced with "From the review role"; four-point list preserved verbatim |
| `## What You Decide` | preserved verbatim (already function-only) |
| `## Commit Procedure (APPROVE only)` — paragraph: "The named flow operates on a Child project, NOT the Father project. Which one is the target-project path the dispatch already provides..." | replaced — this paragraph and the embedded Python SQLite lookup are intentionally REPLACED by the target-project deferral in this file's `## Commit Procedure` section. The behavioral intent is preserved (commit in the correct target project, never with `git add -A`, commit with the verdict's message), and the mechanism the generic file uses is the same one 401/411 already rely on (the Target Project block dispatch injects into the prompt, plus the handoff's `<project>` section). The replacement is mechanical: 421's hardcoded CLOUD_PAY and the `bridge_flows` SQL lookup were the only mechanism by which 421 derived the target project (the named flow label is dropped); that mechanism is now uniform across all three absorbed originals. The "If the verdict also touched Father governance files..." sentence and "Only you may commit" are preserved (the latter is mandatory across all three). |
| `## Scope Change` | preserved verbatim (already function-only) |
| `## Constraints` | preserved verbatim (already function-only) |

### Summary of dropped and replaced items

The only sections explicitly dropped are the file-title lines of the three
originals — identity-bearing strings with no behavioral content. The single
section that is **replaced** rather than preserved is the 421 Commit Procedure
preamble + embedded Python/SQLite lookup that hardcoded CLOUD_PAY and the
`bridge_flows.target_project_path` lookup; that mechanism is now uniform with
401/411, which already defer the target project to the dispatch prompt. The
underlying behavioral intent — commit in the correct target project, never
with `git add -A`, commit with the verdict's message — is preserved verbatim
in the generic `## Commit Procedure` section. Every other behavior is preserved
verbatim, either through the four-point verdict-content list (What You Receive),
the read/decision structure (What You Decide), the Scope Change rule, or the
Constraints section.
