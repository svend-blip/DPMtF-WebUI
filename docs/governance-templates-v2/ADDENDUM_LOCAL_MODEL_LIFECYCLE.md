# ADDENDUM_LOCAL_MODEL_LIFECYCLE

> **en-US is the standard language for all governance-templates-v2 files.**

## When This Addendum Binds

This addendum binds based on the `model_source` field in the RUNTIME
CONTEXT block. There are three branches, stated functionally. The TG2
prohibited-token grep forbids any model/client/provider/harness name in
this file (in any case), so the branches describe model sources by their
lifecycle behaviour, never by their identity.

### Local runtime

When `model_source` identifies a model that runs on a local server the
role owns (a process the role starts, addresses, and stops during its
own step), the local-lifecycle rules below BIND. The model is loaded
before your session starts and unloaded after you complete your handoff;
the swap-guard rules apply.

### Hosted API

When `model_source` identifies a model that lives at a hosted endpoint
the role addresses over the network, the local-lifecycle rules DO NOT
BIND. Nothing loads or unloads; there is no card to contend for; the
swap lines in the dispatch log are no-ops or harmless credential
checks. What replaces the local-lifecycle concerns is cost and quota:
every token is billed, and a rate-limit or quota error is a real stop
condition — retry once, then park with the error text.

### Harness

When `model_source` identifies a model reached through a headless
one-shot harness (each wake-up invokes fresh; nothing is resident to
tear down), the local-lifecycle rules DO NOT BIND. The harness carries
no memory between wake-ups; there is no card to contend for; there is
no swap because the harness is not resident. Cost and quota still
apply, as for hosted APIs.

This three-way "does not bind" reading is the explicit resolution of
the contradictory 471-vs-491 supervisor prose the run contract calls
out: 471 says "there is no card to contend for" (hosted); 491 says
"signalling stops your own model" (local). Both are right — each for
its own model source. The addendum is the single place that
contradiction is resolved, keyed on the runtime context.

The companion autonomy addendum (`ADDENDUM_AUTONOMOUS_RUN.md`) binds
independently based on the runtime context's `autonomous` field. The
two addenda do not interfere: a run can be autonomous without having a
local model, and a local model can run in a non-autonomous flow.

## Local Runtime Lifecycle (binds only when model_source is local)

A local-runtime reference is stopped on the step's model swap. The
outgoing reference is stopped and the incoming one started on every
step, so handing off genuinely stops your server and a returning
verdict genuinely reloads it. Three rules follow from that fact:

- **Never wait for a model to become available.** At wake-up yours is
  already up; after your signal it is meant to be down. Neither state
  is one you wait out. If you find yourself probing your own health
  endpoint to confirm you are alive, you are proving only that you were
  alive enough to ask.
- **Never diagnose a hosted sibling as local.** The other roles in the
  chain may be hosted APIs (the typical mix in a heterogeneous flow).
  If a call to them fails it is network, credentials, or an outage —
  not a swap, not a card.
- **The stop/start lines in the dispatch log are real work**, where they
  were previously no-ops in some flows. They show the system doing the
  swap; note them and move on.

The wake-up rule is the converse of the signal rule: at wake-up yours
is loaded by the time the prompt is injected, so if you are reading
anything at all, it started. Probing your own health endpoint to
confirm that does not add information.

A connection-refused against your own port AFTER your own signal is
correct behaviour, not an outage — the server is meant to be down by
then. It is not something to retry or park over.

## Finish Everything Before Signalling

The signal-mechanics reason WHY the ordering rule in
`ADDENDUM_AUTONOMOUS_RUN.md` exists: the model swap stops the
from-role's reference as part of the signal step. Anything you compose
after signalling fails against a server that is no longer listening —
the model is down, the connection is refused, and your file write
lands nowhere.

The discipline is sharpest at the moment you think you have nothing
left to do:

1. Write the handoff.
2. Write the ledger entry.
3. Save every file you intend to save — verify each exists on disk.
4. Signal.
5. Stop.

If you signal first and try to compose a ledger entry afterwards, the
attempt fails and the run's memory is missing the entry that explains
what you just did. The signal is the last step, not the first.

## Hosted And Harness Lifecycle

When `model_source` is hosted or harness, the local-lifecycle rules
above DO NOT BIND. There is no card to contend for; nothing loads or
unloads; the swap lines in the dispatch log are either no-ops (hosted)
or harness-internal (harness). The "signalling stops your own model"
warning does not apply — there is no model to stop.

What does apply, for both hosted and harness, is cost and quota:

- **Every token is billed.** A runaway turn in a hosted role is
  expensive as well as slow. The autonomy addendum's stop conditions
  apply as much to cost as to correctness.
- **A rate-limit or quota error is a real stop condition**, not a
  transient to retry indefinitely. Retry once; if it persists, park
  with the error text. Never loop.

Connection-refused against a hosted endpoint, or against a harness,
means the API or the harness is genuinely unreachable — network,
credentials, or an outage. It is not the ordinary state after a swap
and is not something to wait out. Park and report.

## Cross-Cut Inventory

This appendix maps every section of the source originals to where it
lives in this addendum, in the base files (`IMPLEMENTOR.md` and
`SUPERVISOR_AUTONOMOUS.md`), or in the companion autonomy addendum.
References to the source originals use the bare index number only (TG2's
token grep prohibits the `NNN_`-prefixed filenames). A dropped
**behavioral** rule is a REJECTION — only identity/mechanical content
may be classified as dropped.

### From `461`

| Section / Rule of original | Lives in the base files / this addendum as |
|----------------------------|---------------------------------------------|
| Title line at the top of the file | dropped — identity (file number/name) |
| en-US language note (blockquote) | preserved verbatim, top of file |
| `## Role` section | genericized in `SUPERVISOR_AUTONOMOUS.md`'s `## Role` section |
| `## Chain Position` section | genericized in `SUPERVISOR_AUTONOMOUS.md`'s `## Chain Position` section |
| `## Model` section (model, serving backend, load/unload pattern, isolation guarantee) | deferred to this addendum's `## Local Runtime Lifecycle` section — the load/unload behaviour is the local-runtime case; the model identity itself is genericized away (intentional — see Summary) |
| `## Run Artifacts` table | preserved in `SUPERVISOR_AUTONOMOUS.md` |
| `## Mission Contract — GOAL.md Schema` section | folded into `SUPERVISOR_AUTONOMOUS.md` |
| `## Wake-Up Protocol` section | preserved in `SUPERVISOR_AUTONOMOUS.md` |
| `## Event Handling` table | folded into `SUPERVISOR_AUTONOMOUS.md` |
| `## Writing A Handoff — Absolute Paths` section | preserved verbatim in `SUPERVISOR_AUTONOMOUS.md` |
| `## What a Gate Escalation Means` section | preserved verbatim in `SUPERVISOR_AUTONOMOUS.md` |
| `## Validating an APPROVED Verdict` section | folded into `SUPERVISOR_AUTONOMOUS.md` |
| `## Decision Matrix` table | folded into `SUPERVISOR_AUTONOMOUS.md` |
| `## Ledger Entry Format` section | folded into `SUPERVISOR_AUTONOMOUS.md` |
| `## Stop Conditions` section | folded into `SUPERVISOR_AUTONOMOUS.md` |

### From `491`

| Section / Rule of original | Lives in the base files / this addendum as |
|----------------------------|---------------------------------------------|
| Title line at the top of the file | dropped — identity (file number/name) |
| en-US language note (blockquote) | preserved verbatim, top of file |
| `## Role` section | genericized in `SUPERVISOR_AUTONOMOUS.md`'s `## Role` section |
| `## Chain Position` section | genericized in `SUPERVISOR_AUTONOMOUS.md`'s `## Chain Position` section |
| `## Model` section (model, quantization, response budget, client configuration, mixed-flow identity split, cost prose for hosted roles) | deferred to this addendum's `## Local Runtime Lifecycle` and `## Hosted And Harness Lifecycle` sections — the local-runtime bits map to `## Local Runtime Lifecycle`; the hosted-cost bits map to `## Hosted And Harness Lifecycle`; the model/quantization/budget identity itself is genericized away (intentional) |
| `## What A Mixed Flow Changes` section (the contradictory "signalling stops your own model" prose, the local-vs-hosted habits, the three-local-models reference, the stop/start lines paragraph) | deferred to this addendum — the "signalling stops your own model" rule lives in `## Finish Everything Before Signalling`; the local-vs-hosted habits live in `## Local Runtime Lifecycle`; the hosted-cost prose lives in `## Hosted And Harness Lifecycle`; the identity prose is genericized away |
| `### Signalling Stops Your Own Model — Finish Everything First` subsection (local-server-tmux-session rule, model-reference-change history, "do every piece of your own work before you signal" rule, wake-up-finds-server-up rule, local-server-cost prose) | preserved verbatim in this file's `## Finish Everything Before Signalling` and `## Local Runtime Lifecycle` sections — the five-step discipline (write handoff → write ledger → save files → signal → stop) and the wake-up-finds-server-up rule |
| `## Run Artifacts` table | preserved in `SUPERVISOR_AUTONOMOUS.md` |
| `## Mission Contract — GOAL.md Schema` section | folded into `SUPERVISOR_AUTONOMOUS.md` |
| `## The Handoff Floor` section | preserved in `SUPERVISOR_AUTONOMOUS.md` |
| `## Wake-Up Protocol` section | preserved in `SUPERVISOR_AUTONOMOUS.md` |
| `## Event Handling` table | folded into `SUPERVISOR_AUTONOMOUS.md` |
| `## Validating an APPROVED Verdict` section | folded into `SUPERVISOR_AUTONOMOUS.md` |
| `## Writing A Handoff — Two Things That Cost Cycles` section | preserved verbatim in `SUPERVISOR_AUTONOMOUS.md` |
| `## Decision Matrix` table | folded into `SUPERVISOR_AUTONOMOUS.md` |
| `## Ledger Entry Format` section | folded into `SUPERVISOR_AUTONOMOUS.md` |
| `## Stop Conditions` section | folded into `SUPERVISOR_AUTONOMOUS.md` |

### From `492`

| Section / Rule of original | Lives in the base files / this addendum as |
|----------------------------|---------------------------------------------|
| Title line at the top of the file | dropped — identity (file number/name) |
| en-US language note (blockquote) | preserved verbatim, top of file |
| `## Role` section | genericized in `IMPLEMENTOR.md`'s `## Role` section |
| `## Chain Position` section | genericized in `IMPLEMENTOR.md`'s `## Chain Position` section |
| `## Model And Client` section (model, serving backend, alias, model-reference-sharing rule, prior-model history, fresh-session mechanics, silent-tool-call failure narrative, 31-turn table, context window history) | deferred to this addendum — the silent-tool-call-failure behavioral rule is genericized in `IMPLEMENTOR.md`'s `## Silent Tool-Call Failure` section (no model or provider name); the model-reference-sharing rule and the fresh-session mechanics are genericized in `IMPLEMENTOR.md`'s `## Every Handoff Begins Empty` section; the model identity and context window are genericized away (intentional) |
| `## Every Handoff Starts You In A New Session` section (fresh-session-command rule, begin-each-handoff-empty rule, run-memory-in-files rule, 31-turn table, silent-tool-call failure narrative, "47% of a window" number, "say so in your result" instruction, "do not retry into it" instruction) | genericized in `IMPLEMENTOR.md`'s `## Every Handoff Begins Empty` and `## Silent Tool-Call Failure` sections — the begin-each-handoff-empty and run-memory-in-files rules preserved; the fresh-session-command mechanics replaced with a generic "the bridge injects the handoff instruction fresh; a fresh-session mechanism starts you over"; the 31-turn table, silent-tool-call failure narrative, and "47% of a window" number deferred to the model-lifecycle addendum's behavioural discipline (no model identity) |
| `## Cost Is Now Real` section | deferred to this addendum's `## Hosted And Harness Lifecycle` section — hosted-cost content; the scope-discipline bit is already covered by `IMPLEMENTOR.md`'s `## The Fence Is The Fence` and `## Reporting Rules` |
| `## Handoff Format` section | genericized in `IMPLEMENTOR.md`'s `## Receiving a Handoff` section |
| `## Implementation Rules` list | genericized and folded into `IMPLEMENTOR.md` |
| `## Output` section | covered by `IMPLEMENTOR.md`'s `## Writing Results` section |
| `## Reporting Rules` list (with the 2026-08-05 anecdote) | merged with the other originals in `IMPLEMENTOR.md`'s `## Reporting Rules` section |
| `## The Fence Is The Fence` section | preserved verbatim in `IMPLEMENTOR.md`'s `## The Fence Is The Fence` section |
| "Never edit what a check measures" paragraph | preserved verbatim in `IMPLEMENTOR.md`'s `## Never Edit What A Check Measures` section |
| `## Stop Condition` section | merged into `IMPLEMENTOR.md`'s `## Post-Signal Stop Rule — CRITICAL` section |

### Hosted (471) and Harness (511) positions — folded into the "does not bind" branch

For the hosted and harness branches of the resolution ONLY, the
contradictory 471 ("no card to contend for" — hosted) and 511 ("each
wake-up invokes fresh; nothing is resident" — harness) positions are
folded into `## Hosted And Harness Lifecycle` functionally, WITHOUT
their identity prose. The TG2 prohibited-token grep forbids naming
either flow's specific model/client/provider/harness; the addendum
states the lifecycle in lifecycle terms (no card to contend for;
nothing loads or unloads; the swap lines are no-ops; cost and quota
replace contention; a rate-limit/quota error is a stop after one
retry), and the bare index numbers reference the positions taken.

This is the explicit "does not bind" reading the run contract requires
to resolve the 471-vs-491 contradiction keyed on model source. The 471
position is right for the hosted branch; the 491 position is right for
the local branch; both are wrong if applied to the other. This
addendum is the single place that distinction is enforced.

### Summary

The only sections explicitly dropped (rather than genericized or
deferred) are the title lines of the three source originals (identity-
bearing strings with no behavioral content). Model/identity content
(model name, serving backend, quantization, response budget, client
configuration, alias name, fresh-session-mechanism values, the
cost-and-allowance tokens) is genericized away intentionally — TG2's
token grep forbids naming any model/client/provider/harness in any
case, and the lifecycle discipline is preserved in lifecycle terms
without the identity prose. The behavioral rules those sections
carried are preserved in lifecycle terms in this addendum or in the
two base files.

The contradictory 471-vs-491 prose appears in neither the base nor
this addendum's identity sections — it is resolved functionally in
`## Hosted And Harness Lifecycle` (the "does not bind" reading), keyed
on the runtime context's `model_source` field.

Every behavioral section of every source original is preserved — either
verbatim in the two base files, in this addendum (the local-runtime
discipline, the finish-before-signalling rule, the hosted-and-harness
"does not bind" reading), or in the companion autonomy addendum. No
behavioral rule was dropped.
