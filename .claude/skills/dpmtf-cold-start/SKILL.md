---
name: dpmtf-cold-start
description: Orient a freshly dispatched DPMtF worker — identify your role, read the governance that binds it, execute the handoff within its fence, verify with the project's own checks, write the deliverable to the exact path, and signal. Use at the start of any turn that begins with a BridgeV002 dispatch prompt naming a governance file and a handoff to read.
---

# DPMtF Cold Start — For A Dispatched Worker

You have been dispatched into a BridgeV002 chain. This procedure gets you
from an empty context to a delivered result without guessing.

It is written for the worker roles — implementer, reviewer, analyst — not
for a supervisor. Supervisors have their own cold-start procedures naming
their own flow.

**You are stateless by design.** The session you are in may be fresh, or it
may have been reset. Either way, everything you need is on disk or in the
prompt that woke you. Nothing you remember is authoritative.

## Step 0: Read What Already Told You

The dispatch prompt that woke you is not preamble. It names, explicitly:

| It says | You need it for |
|---|---|
| your governance file | the contract you are bound by |
| the handoff path | the work |
| the deliverable path | where the result must be written, exactly |
| the signal command | how the chain advances |
| the target project | where to `cd` before running anything |

Read those five out of the prompt before doing anything else. Do not
reconstruct them from memory, from a previous handoff, or from what a
similar flow does. If any of the five is missing, that is a defect worth
reporting in your result rather than filling in.

**Check where you are.** `pwd` before your first command. A handoff that
names paths relative to the target project, executed from the Father
repository, produces confident results about the wrong files. If a command
reports a missing file or a count disagrees with what the handoff describes,
check `pwd` before concluding anything about the code.

## Step 1: Read Your Governance, By Section

Your governance file is the contract. Read the sections your situation needs
— not the whole file, and not none of it.

At minimum, before your first action: your role's own responsibilities, its
scope limits, and its stop conditions.

This is not tidiness. On a local model with a 65k window, reading a full
governance file can cost minutes of wall-clock before you emit a token, and
context you will want later for the actual work.

## Step 2: Read The Handoff, Then Bound It

Read the handoff file at the path the prompt gave you.

**The handoff's fence is the fence.** It names files, paths or a scope; work
inside it. A larger context window is not permission to widen scope, and
neither is noticing something else that looks wrong. If you find a real
problem outside the fence, write it in your result — that is what the result
is for — and do not fix it.

If the handoff is ambiguous in a way that changes what you would build, say
so in the result and pick the reading you can defend. Do not silently choose
and present it as the only reading.

## Step 3: Do The Work, And Verify It With The Project's Own Checks

Run the project's real checks, not a substitute you invented. Most DPMtF
projects state them; `CLAUDE.md` or `AGENTS.md` in the target project is
where to look.

Three measurement traps that have each cost a real run here:

- **`echo "$(cmd): exit $?"` is always 0** — the substitution's status
  replaces the command's. Capture `rc=$?` on its own line, immediately. For
  pipes, use `PIPESTATUS`.
- **A passing test suite's last line is not the summary.** Measure the exit
  code, not the tail of the output.
- **A count cannot read.** Where the question is whether prose says
  something, read it and quote the sentence.

## Step 4: Write The Deliverable To The Exact Path

Write to the path the prompt named, and only there. No extra copies, no
invented filenames in the working directory, no "also saved a summary".

If the prompt lists required XML sections, include them. Envelope fields the
dispatcher supplies for you are not your job; the content is.

**State what you did and what you measured.** Paste the output you actually
saw. Do not describe a command's result you did not run, and do not round a
number up to the one you expected. A verdict built on a fabricated paste has
happened here, in both directions, and it is the failure that destroys the
most trust for the least gain.

If you could not complete the work, say that plainly with what blocked you.
An honest incomplete result is worth more than a confident wrong one, and
the chain has a supervisor whose job is exactly that decision.

## Step 5: Signal — And Finish Everything First

The prompt gives you an exact signal command. Run it verbatim; the flow,
role and id in it are already resolved.

**Everything you intend to write must be on disk before you signal.**
Signalling advances the chain, and in flows where your model is local it can
stop your own model as part of the same step — your session survives, your
model does not. Anything you were still composing is then lost, and the
record of what you just did goes missing with it.

Order: write the deliverable, write any notes or ledger entries, verify they
exist, then signal, then stop.

**A signal that failed leaves the chain blocked with nobody aware.** If the
command reports a failure — a missing deliverable, a path mismatch — fix it
and signal again. Do not assume it landed.

## Framework Questions Go To mcp-light

If `mcp-light` is available to you, use it for anything about how the flow
is wired rather than deriving it:

| Question | Tool |
|---|---|
| Where does a deliverable go, and under what name? | `get_flow_steps(flow)` |
| What does a governance file say? | `get_governance_file(name)` |
| How is a role configured? | `get_role(role_key)` |
| What did an earlier verdict conclude? | `search_verdicts(query)` |

A cold start in one flow once spent fourteen minutes deriving from
`dispatch.py` what one call returns.

## What Not To Do

- **Do not touch files outside the handoff's fence.** The evidence gate
  compares the working tree, and an unrelated edit is attributed to you.
- **Do not edit anything a check reads in order to make that check pass.**
  Not a timestamp, not a file reverted only until the check has run. If a
  check is wrong, say so with the evidence and stop.
- **Do not read the source of the tools you are told to run.** Their
  invocations are given to you.
- **Do not improvise what the contract left open.** Park it in your result.

## If Your Tools Are Restricted

Some roles are given an explicit tool allowlist — a reviewer that can read
and run commands but not write, for instance. That is governance the client
enforces, not an oversight. If the handoff asks for something your tools
cannot do, say so in the result instead of working around it.

Flow startup contract: docs/governance-templates-v2/103_FLOW_STARTUP.md
