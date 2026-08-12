---
description: Rev_Supervisor cold-start for the reveng flow — rebuild run state from GOAL.md, RUN-LEDGER.md and BACKLOG.md, then act once.
---

Run the **Rev-Eng** cold-start procedure now.

It is `.claude/skills/REVENG/SKILL.md` in this repository — the same file
Claude Code reads, and the same one OpenCode also exposes as the `/Rev-Eng`
skill. Read it and follow it exactly, in order, starting at Step 0.

This command exists because the skill's own name is capitalised, so it is
only reachable as `/Rev-Eng`. `/rev-eng` is the form that gets typed.

The invocation carries no arguments and needs none: everything about the
current run is discoverable, and Step 0 discovers it. Do not ask which run is
active, which handoff is next, or whether a guard is running — read the state.
