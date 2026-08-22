# ADDENDUM_AUTONOMOUS_RUN

> **en-US is the standard language for all governance-templates-v2 files.**

## When This Addendum Binds

This addendum binds when the RUNTIME CONTEXT block carries
`autonomous: yes`. It does not bind when the runtime context carries
`autonomous: no` — a Human-paired flow continues to follow its base
governance unmodified. The addendum never names a flow, a role, or a
model; the binding decision is made by the runtime context at dispatch
time.

The companion model-lifecycle addendum (`ADDENDUM_LOCAL_MODEL_LIFECYCLE.md`)
binds alongside this one — keyed on the runtime context's `model_source`
field. The two addenda are independent: a run can be autonomous without
having a local model, and a local model can run in a non-autonomous
flow. Each addendum only governs the behaviour its name describes.

## The Human Is Not In The Loop

There is nobody to ask. Anything the Mission Contract (`GOAL.md`) does
not authorize is parked for the Human — never improvised. A decision the
contract left open is parked in your result file with the exact options
you considered and the reason you could not choose between them; it is
never guessed into code or guessed into a stop condition.

When in doubt: park. A parked run costs hours; a wrong autonomous
decision can cost the repository. The Decision Matrix in
`SUPERVISOR_AUTONOMOUS.md` and the autonomy rows below share this
discipline.

## Git Is Read-Only — Always

You never commit, push, stage, stash, or amend. The read-only command
set is `status`, `diff`, `log`, `branch`. You NEVER run `checkout`,
`restore`, `reset`, `stash`, `clean`, or `worktree`. `git checkout <file>`
discards the working tree for that file — it does not undo only your own
edits.

The working tree may carry uncommitted work from a previous handoff that
the supervisor has not checkpointed yet. It is not recoverable from a
commit. Treat the working tree as the only durable state you own between
signals.

## The Supervisor Takes The Checkpoint Commit

After an APPROVED verdict, the supervisor named in the RUNTIME CONTEXT
takes the checkpoint commit on the branch named in the Mission Contract's
Standing Approvals. You never commit. The supervisor's checkpoint commit
is what makes your work durable; until the commit lands, the next wake-up
sees the same working tree you just left.

If a handoff leaves the branch in a broken state that rework cannot fix
within 2 attempts, the supervisor rolls back to the last green commit,
records the abandoned approach in the ledger, and either replans or
parks. The rollback path is the supervisor's, not yours.

## Finish Everything Before Signalling

Write your result file, write any ledger or notes, verify every file
you intended to save exists on disk, and only then signal — then stop.
Anything you were still composing when the signal fires is lost.

The signal-mechanics reason WHY this rule exists — the model swap stops
the from-role's reference as part of the signal step — lives in
`ADDENDUM_LOCAL_MODEL_LIFECYCLE.md`. The rule itself, the ordering
guarantee, lives here.

## The Fence Is The Fence

Where a handoff names more than one repository, resolve every edit
against the absolute path in the fence, not against the working
directory your shell happens to be in. The fence is authoritative; the
prose is not. Same-named files in two repositories are the easiest
mistake in a multi-repo flow to make and the hardest to see afterwards —
the edit looks right, the file exists, and nothing complains until the
evidence gate runs.

A larger context window is not permission to widen scope. The handoff's
fence is the fence regardless of what fits in your context. Read what
the handoff names, plus what you need to change it safely — not the
whole repository.

## Cross-Cut Inventory

This appendix maps every section of each of the five source originals
to where it lives in this addendum, in the base files
(`IMPLEMENTOR.md` and `SUPERVISOR_AUTONOMOUS.md`), or in the companion
model-lifecycle addendum. References to the five originals use the bare
index number only (TG2's token grep prohibits the `NNN_`-prefixed
filenames). A dropped **behavioral** rule is a REJECTION — only
identity/mechanical deltas may be classified as dropped; model-lifecycle
prose is classified as "deferred to the model-lifecycle addendum",
never "dropped".

### From `452`

| Section / Rule of original | Lives in the base files / this addendum as |
|----------------------------|---------------------------------------------|
| Title line at the top of the file | dropped — identity (file number/name) |
| en-US language note (blockquote) | preserved verbatim, top of file |
| `## Role` section, which named the flow-specific implementer role label, the flow name, the autonomous-supervisor label, and the "no Human to ask" bit | genericized in `IMPLEMENTOR.md`'s `## Role` section — the role label and flow name are replaced with function-only language; the "no Human to ask" bit is generalized to the autonomous-flag rule in `IMPLEMENTOR.md`'s `## Constraints` |
| `## Target Project — resolve this FIRST` section | genericized in `IMPLEMENTOR.md`'s `## Target Project — resolve this FIRST` section — same rationale as 423's mapping |
| `## When You Are Active` section | genericized in `IMPLEMENTOR.md`'s `## When You Are Active` section |
| `## Context-First Rule (mcp-light)` section (with the Father-vs-non-Father caveat) | preserved verbatim in `IMPLEMENTOR.md`'s `## Context-First Rule (mcp-light)` section |
| `## Receiving a Handoff` section (the 6-step list, with the verbatim-evidence step-6 and the fence-narrowing sentence) | preserved in `IMPLEMENTOR.md`'s `## Receiving a Handoff` section — the verbatim-evidence step-6 and the fence-narrowing sentence preserved verbatim |
| `## Before Writing Code — 6 Principles` section | preserved verbatim in `IMPLEMENTOR.md`'s `## Before Writing Code — 6 Principles` section |
| `## Coding Rules (Mandatory)` table | preserved in `IMPLEMENTOR.md`'s `## Coding Rules (Mandatory)` table |
| "Path rule clarification" paragraph | preserved verbatim in `IMPLEMENTOR.md`'s `## Coding Rules (Mandatory)` section |
| `## Git — read-only, always` section (the working-tree-may-carry-uncommitted-work note, the read-only-command list, the NEVER-checkout/restore/reset/stash/clean/worktree prohibition, the never-commit/push/amend rule, the "the supervisor takes the checkpoint commit" note) | preserved in this file's `## Git Is Read-Only — Always` and `## The Supervisor Takes The Checkpoint Commit` sections — the supervisor-name token is generalized to "the supervisor named in the RUNTIME CONTEXT" |
| `## Writing Results` section (with the ANTI-FALSE-COMPLETION sentence) | preserved in `IMPLEMENTOR.md`'s `## Writing Results` section — the ANTI-FALSE-COMPLETION sentence preserved verbatim |
| `## Post-Signal Stop Rule — CRITICAL` section | merged into `IMPLEMENTOR.md`'s `## Post-Signal Stop Rule — CRITICAL` section |
| `## Constraints` section (NEVER commit/push; execute ALL steps; document ambiguity; en-US; "there is no Human in this flow to ask") | preserved in `IMPLEMENTOR.md`'s `## Constraints` section — the "no Human to ask" sentence generalized to the autonomous-flag rule; this addendum's `## The Human Is Not In The Loop` section restates the rule |

### From `462`

| Section / Rule of original | Lives in the base files / this addendum as |
|----------------------------|---------------------------------------------|
| Title line at the top of the file | dropped — identity (file number/name) |
| en-US language note (blockquote) | preserved verbatim, top of file |
| `## Role` section | genericized in `IMPLEMENTOR.md`'s `## Role` section |
| `## Chain Position` section | genericized in `IMPLEMENTOR.md`'s `## Chain Position` section |
| `## Model` section (model, serving backend, alias, isolation) | deferred to `ADDENDUM_LOCAL_MODEL_LIFECYCLE.md` — identity/mechanical content |
| `## Handoff Format` section | genericized in `IMPLEMENTOR.md`'s `## Receiving a Handoff` section |
| `## Implementation Rules` list | genericized and folded into `IMPLEMENTOR.md`'s `## Receiving a Handoff` and `## Coding Rules (Mandatory)` sections |
| `## Output` section | covered by `IMPLEMENTOR.md`'s `## Writing Results` section |
| `## Working Across Repositories` section (the multi-repo-fence rule, the README.md/config.py/tests/ trap, the `git -C` confirmation step, the "the fence is authoritative, the prose is not" rule) | preserved verbatim in `IMPLEMENTOR.md`'s `## Working Across Repositories` section, and the cross-cut discipline is restated in this addendum's `## The Fence Is The Fence` section |
| `## Reporting Rules` list (with the 2026-08-05 anecdote and the fenced-out-validation rule) | merged with the other originals in `IMPLEMENTOR.md`'s `## Reporting Rules` and `## The Fence Is The Fence` sections |
| `## Stop Condition` section (the dispatch.py command + "Then check that it worked" sentence) | merged into `IMPLEMENTOR.md`'s `## Post-Signal Stop Rule — CRITICAL` section |

### From `472`

| Section / Rule of original | Lives in the base files / this addendum as |
|----------------------------|---------------------------------------------|
| Title line at the top of the file | dropped — identity (file number/name) |
| en-US language note (blockquote) | preserved verbatim, top of file |
| `## Role` section | genericized in `IMPLEMENTOR.md`'s `## Role` section |
| `## Chain Position` section | genericized in `IMPLEMENTOR.md`'s `## Chain Position` section |
| `## Model And Client` section | deferred to `ADDENDUM_LOCAL_MODEL_LIFECYCLE.md` — identity/mechanical content |
| `## Cost Is Now Real` section | deferred to `ADDENDUM_LOCAL_MODEL_LIFECYCLE.md` — hosted-cost content |
| `## Handoff Format` section | genericized in `IMPLEMENTOR.md`'s `## Receiving a Handoff` section |
| `## Implementation Rules` list | genericized and folded into `IMPLEMENTOR.md` |
| `## Output` section | covered by `IMPLEMENTOR.md`'s `## Writing Results` section |
| `## Reporting Rules` list (with the 2026-08-05 anecdote and the "the evidence gate exists because of that" sentence) | merged with the other originals in `IMPLEMENTOR.md`'s `## Reporting Rules` section — the 4 items and the anecdote preserved |
| `## The Fence Is The Fence` section (the evidence-gate framing, the declare-or-explain rule, the "first hypothesis: wrong repo" generalisation, the "fenced-out validation is a defect, not a puzzle" rule, the "never satisfy by reconstruction" rule) | preserved verbatim in `IMPLEMENTOR.md`'s `## The Fence Is The Fence` section; the cross-cut discipline is restated in this addendum's `## The Fence Is The Fence` section |
| "Never edit what a check measures" paragraph | preserved verbatim in `IMPLEMENTOR.md`'s `## Never Edit What A Check Measures` section |
| `## Stop Condition` section | merged into `IMPLEMENTOR.md`'s `## Post-Signal Stop Rule — CRITICAL` section |

### From `492`

| Section / Rule of original | Lives in the base files / this addendum as |
|----------------------------|---------------------------------------------|
| Title line at the top of the file | dropped — identity (file number/name) |
| en-US language note (blockquote) | preserved verbatim, top of file |
| `## Role` section | genericized in `IMPLEMENTOR.md`'s `## Role` section |
| `## Chain Position` section | genericized in `IMPLEMENTOR.md`'s `## Chain Position` section |
| `## Model And Client` section (model, serving backend, alias, prior-model history, fresh-session mechanics, context window, silent-tool-call failure narrative, 31-turn table) | deferred to `ADDENDUM_LOCAL_MODEL_LIFECYCLE.md` — identity/mechanical content; the silent-tool-call-failure behavioral rule is genericized in `IMPLEMENTOR.md`'s `## Silent Tool-Call Failure` section (no model or provider name) |
| `## Every Handoff Starts You In A New Session` section | genericized in `IMPLEMENTOR.md`'s `## Every Handoff Begins Empty` section — the fresh-session-command rule is replaced with a generic "the bridge injects the handoff instruction fresh; a fresh-session mechanism starts you over" |
| `## Cost Is Now Real` section | deferred to `ADDENDUM_LOCAL_MODEL_LIFECYCLE.md` — hosted-cost content |
| `## Handoff Format` section | genericized in `IMPLEMENTOR.md`'s `## Receiving a Handoff` section |
| `## Implementation Rules` list | genericized and folded into `IMPLEMENTOR.md` |
| `## Output` section | covered by `IMPLEMENTOR.md`'s `## Writing Results` section |
| `## Reporting Rules` list (with the 2026-08-05 anecdote) | merged with the other originals in `IMPLEMENTOR.md`'s `## Reporting Rules` section |
| `## The Fence Is The Fence` section | preserved verbatim in `IMPLEMENTOR.md`'s `## The Fence Is The Fence` section; the cross-cut discipline is restated in this addendum's `## The Fence Is The Fence` section |
| "Never edit what a check measures" paragraph | preserved verbatim in `IMPLEMENTOR.md`'s `## Never Edit What A Check Measures` section |
| `## Stop Condition` section | merged into `IMPLEMENTOR.md`'s `## Post-Signal Stop Rule — CRITICAL` section |

### From `512`

| Section / Rule of original | Lives in the base files / this addendum as |
|----------------------------|---------------------------------------------|
| Title line at the top of the file | dropped — identity (file number/name) |
| en-US language note (blockquote) | preserved verbatim, top of file |
| `## Role` section | genericized in `IMPLEMENTOR.md`'s `## Role` section |
| `## Chain Position` section | genericized in `IMPLEMENTOR.md`'s `## Chain Position` section |
| `## Model And Harness` section (model, harness, provider config, credential env var) | deferred to `ADDENDUM_LOCAL_MODEL_LIFECYCLE.md` — identity/mechanical content |
| `## Cost Is Now Real` section | deferred to `ADDENDUM_LOCAL_MODEL_LIFECYCLE.md` — hosted-cost content |
| `## Handoff Format` section | genericized in `IMPLEMENTOR.md`'s `## Receiving a Handoff` section |
| `## Implementation Rules` list | genericized and folded into `IMPLEMENTOR.md` |
| `## Output` section | covered by `IMPLEMENTOR.md`'s `## Writing Results` section |
| `## Reporting Rules` list | merged with the other originals in `IMPLEMENTOR.md`'s `## Reporting Rules` section |
| `## The Fence Is The Fence` section | preserved verbatim in `IMPLEMENTOR.md`'s `## The Fence Is The Fence` section; the cross-cut discipline is restated in this addendum's `## The Fence Is The Fence` section |
| `## Stop Condition` section | merged into `IMPLEMENTOR.md`'s `## Post-Signal Stop Rule — CRITICAL` section |

### Summary

Every behavioral section of every one of the five originals is preserved
— either verbatim in the two base files (IMPLEMENTOR.md and
SUPERVISOR_AUTONOMOUS.md), in this addendum (the autonomy cross-cut
itself — git-read-only, no-Human, finish-before-signalling, the
supervisor-takes-the-checkpoint-commit, fence discipline), or deferred
to the companion model-lifecycle addendum. No behavioral rule was
dropped; only the title lines of the five originals (identity) and the
identity/mechanical model-lifecycle content are not carried here.

The two base files already generalize the autonomy rules (their "## Git
— read-only, always" and "## Constraints" sections carry the same
discipline as this addendum). This addendum's role is to be the
SHARED, EXPLICIT, and CONDITIONAL authority — bound by `autonomous: yes`
in the runtime context — that makes those rules deterministic regardless
of which base file a role is reading.
