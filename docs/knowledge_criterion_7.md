# Knowledge Criterion 7 — Population Report

> Language: en-US. This report is the honest population summary for family
> 2000 success criterion 7. It compares two populations of different tasks,
> not the same task pair that criterion 7 asks to commission, and it claims
> no causal effect of retrieval. The same-task pair was commissioned on
> 2026-09-15 (runs 043 and 044) and has its own section below.

## What this measures

The numbers in this report come from `scripts/knowledge_run_metrics.py`,
which derives `tool_calls` and `tokens` from FlowRunner `run.json` state and
simple-harness `events.jsonl` session logs, plus the per-run
`time_to_first_implementation`, `total_execution_time`, `review_failures`
and `rework` rendered by `knowledge/run_metrics.py` (the collector
`scripts/knowledge_eval.py` uses). This is a **population comparison of
different tasks, not the same task pair** that success criterion 7 asks
for: each run solved a different goal, so **no causal effect** of retrieval
is claimed or measurable from these numbers. The same-task commissioning
procedure appears in the final section, and the medians below are reported
only as population summaries, not as evidence of a treatment effect.

## Population tables

Six numbers per run: `tool_calls`, `tokens`,
`time_to_first_implementation` (seconds), `total_execution_time` (seconds),
`review_failures`, `rework`. "FlowRunner run" is the short form of the run
id the run's ledger names.

### Before retrieval was available — runs closed before 024 (001–023)

| Run | FlowRunner run | State | tool_calls | tokens | time_to_first_implementation | total_execution_time | review_failures | rework |
|-----|----------------|-------|-----------:|-------:|-----------------------------:|---------------------:|----------------:|-------:|
| 001 | — | no FlowRunner state | — | — | — | — | — | — |
| 002 | — | no FlowRunner state | — | — | — | — | — | — |
| 003 | 0ce394ee5b9e | state present | 1160 | 46925903 | 0 | 3605 | 1 | 2 |
| 004 | 0ce394ee5b9e | state present | 1160 | 46925903 | 615 | 4864 | 0 | 1 |
| 005 | 0ce394ee5b9e | state present | 1160 | 46925903 | 374 | 5020 | 0 | 2 |
| 006 | 0ce394ee5b9e | state present | 1160 | 46925903 | 288 | 2453 | 0 | 1 |
| 007 | 0ce394ee5b9e | state present | 1160 | 46925903 | 286 | 3169 | 0 | 1 |
| 008 | 0ce394ee5b9e | state present | 1160 | 46925903 | 319 | 3698 | 0 | 1 |
| 009 | 0ce394ee5b9e | state present | 1160 | 46925903 | 190 | 3548 | 0 | 1 |
| 010 | 0ce394ee5b9e | state present | 1160 | 46925903 | 210 | 4222 | 1 | 2 |
| 011 | 0ce394ee5b9e | state present | 1160 | 46925903 | 555 | 3890 | 0 | 1 |
| 012 | 0ce394ee5b9e | state present | 1160 | 46925903 | 109 | 678 | 0 | 0 |
| 013 | 0ce394ee5b9e | state present | 1160 | 46925903 | 380 | 3496 | 1 | 1 |
| 014 | 0ce394ee5b9e | state present | 1160 | 46925903 | 307 | 2182 | 0 | 0 |
| 015 | 0ce394ee5b9e | state present | 1160 | 46925903 | 467 | 2825 | 0 | 1 |
| 016 | 0ce394ee5b9e | state present | 1160 | 46925903 | 375 | 2270 | 0 | 1 |
| 017 | 0ce394ee5b9e | state present | 1160 | 46925903 | 237 | 2816 | 0 | 1 |
| 018 | 0ce394ee5b9e | state present | 1160 | 46925903 | 166 | 2173 | 0 | 1 |
| 019 | 0ce394ee5b9e | state present | 1160 | 46925903 | 457 | 5147 | 0 | 2 |
| 020 | 0ce394ee5b9e | state present | 1160 | 46925903 | 713 | 3604 | 0 | 1 |
| 021 | 0ce394ee5b9e | state present | 1160 | 46925903 | 584 | 5649 | 1 | 2 |
| 022 | 0ce394ee5b9e | state present | 1160 | 46925903 | 320 | 1835 | 0 | 1 |
| 023 | 0ce394ee5b9e | state present | 1160 | 46925903 | 219 | 5720 | 1 | 2 |

### After retrieval was available — runs closed 024 onwards (024–039)

| Run | FlowRunner run | State | tool_calls | tokens | time_to_first_implementation | total_execution_time | review_failures | rework |
|-----|----------------|-------|-----------:|-------:|-----------------------------:|---------------------:|----------------:|-------:|
| 024 | 0ce394ee5b9e | state present | 1160 | 46925903 | 147 | 6766 | 1 | 3 |
| 025 | 0ce394ee5b9e | state present | 1160 | 46925903 | 362 | 1305 | 0 | 0 |
| 026 | 0ce394ee5b9e | state present | 1160 | 46925903 | 208 | 1950 | 0 | 1 |
| 027 | 0ce394ee5b9e | state present | 1160 | 46925903 | 791 | 9769 | 0 | 4 |
| 028 | 88228d8fbf85 | state present | 549 | 26083789 | 456 | 2968 | 0 | 1 |
| 029 | 88228d8fbf85 | state present | 549 | 26083789 | 986 | 6905 | 1 | 1 |
| 030 | 5e7eb3f92361 | state present | 528 | 12918894 | 221 | 4063 | 1 | 2 |
| 031 | 5e7eb3f92361 | state present | 528 | 12918894 | 317 | 2679 | 0 | 1 |
| 032 | 5e7eb3f92361 | state present | 528 | 12918894 | 508 | 1589 | 0 | 0 |
| 033 | 37ed5b29ee91 | state present | 111 | 1989516 | 345 | 1218 | 0 | 0 |
| 034 | 3937008d313f | state present | 305 | 12080349 | 525 | 4010 | 0 | 1 |
| 035 | fafb13bc62e1 | state present | 472 | 18550278 | 392 | 13358 | 1 | 3 |
| 036 | e8cc90a0f539 | state present | 48 | 723411 | 387 | 489 | 0 | 0 |
| 037 | 6cc9ba5be674 | state present | 271 | 15736485 | 1349 | 4717 | 0 | 1 |
| 038 | 7a3c3aa71eee | state present | 389 | 15928485 | 779 | 5339 | 1 | 1 |
| 039 | 7a3c3aa71eee | state present | 389 | 15928485 | 323 | 1610 | 0 | 0 |

## Medians

Medians are computed with `statistics.median` over the runs that have
FlowRunner state in each population. Runs 001 and 002 are counted out
because no FlowRunner state exists for them.

| Population | Runs included | tool_calls | tokens | time_to_first_implementation | total_execution_time | review_failures | rework |
|------------|---------------|-----------:|-------:|-----------------------------:|---------------------:|----------------:|-------:|
| Before (001–023) | 003–023 (21 runs) | 1160 | 46925903 | 319 | 3548 | 0 | 1 |
| After (024–039) | 024–039 (16 runs) | 528 | 15928485 | 389.5 | 3489 | 0 | 1 |

## Attribution caveat

Several family runs share one FlowRunner run id, so the session-derived
`tool_calls` and `tokens` are the shared FlowRunner run's totals, not one
run's own totals:

- `0ce394ee5b9e` → runs 003–027 (39 sessions)
- `88228d8fbf85` → runs 028–029 (14 sessions)
- `5e7eb3f92361` → runs 030–032 (21 sessions)
- `7a3c3aa71eee` → runs 038–039 (11 sessions)

The remaining runs map one run directory to one FlowRunner run (033, 034,
035, 036, 037). Because the before group is dominated by one shared
FlowRunner run, the two populations are heavily co-attributed and are not
per-run-comparable on `tool_calls` and `tokens`.

## Superseded artefacts

Before this sweep, runs 013 and 014 carried an older, journal-window-derived
`metrics.json` shape. The session-log instrument in this run replaced them
with the values in the tables above; the superseded numbers are preserved
here in prose only:

- Run 013: `tool_calls` 218, `tokens` 6499282, `source`
  "FlowRunner journal events.jsonl (instance eloop2000), usage events
  summed over the ledger window".
- Run 014: `tool_calls` 133, `tokens` 5162267, `source`
  "FlowRunner journal events.jsonl (instance eloop2000), usage events
  summed over the ledger window".

## The same-task pair — runs 043 and 044, measured 2026-09-15

Criterion 7 asks for one representative run that shows whether retrieval
reduces repository exploration, tool calls, tokens or execution time. The
pair below is that run, commissioned as the procedure requires: **the same
GOAL body, byte-identical apart from its title line, from the same baseline
commit `63bcfac`**, once with the knowledge tools removed from the
simple-harness allowlist (arm A, run 043) and once with them available
(arm B, run 044). Both arms closed SUCCESS with 3/3 acceptance criteria and
one review cycle. Arm A's implementation was archived and reverted, not
committed, so arm B could start from the same tree; arm B's work is what
landed (`[run-044]`).

| | arm A — retrieval unavailable (043) | arm B — retrieval available (044) |
|---|---:|---:|
| tool calls | 62 | 75 |
| tokens | 970 460 | 1 177 636 |
| retrieval events | 0 | 0 |
| time to first implementation (s) | 199 | 486 |
| total execution time (s) | 679 | 951 |
| review failures | 0 | 0 |
| rework cycles | 0 | 0 |
| harness sessions | 3 | 4 |
| diff | 5 files, 186 insertions | 5 files, 176 insertions |

**The treatment was never applied.** Arm B's retrieval-event count is zero:
the roles had `knowledge_search` registered (the harness exits 2 when an
MCP server is unreachable, and both arms ran to completion) and used only
the built-in tools — `read_file`, `list_directory`, `shell`, `apply_patch`,
`write_file`. So the numbers above compare two runs of the same task that
both worked without retrieval, and the differences between them are
run-to-run variance, not an effect of retrieval. **Criterion 7 is therefore
not yet answered by measurement**, and no causal claim is made here.

What the pair does establish:

1. The instrument works end to end: the same GOAL, one baseline, derived
   metrics from FlowRunner state and harness session logs, and a verdict
   in each arm.
2. Availability is not use. Making retrieval reachable changes nothing on
   its own for a task an agent judges it can solve by reading the files in
   front of it.
3. The next attempt must either instruct the role to consult the knowledge
   layer before exploring (the `knowledge-first` skill exists for exactly
   this) or choose a task whose answer is not in the files the role would
   open anyway — a convention decided in another repository, a decision
   recorded in a closed run, an interface used from a sibling project.

## Second pair — runs 045 and 046, measured 2026-09-15, with the treatment applied

The first pair failed to apply its treatment: the tools were available in
arm B and the roles never called them. This pair carries the
retrieve-before-exploring instruction **in both GOAL bodies**, so the only
difference between the arms is whether `knowledge_search` is in the
harness's allowlist. Same GOAL text apart from the title, same baseline
`c12d399`, same task (a `--markdown` renderer for this harness). Both arms
closed SUCCESS with 4/4 acceptance criteria. Arm A's implementation was
archived and reverted; arm B's is what landed (`[run-046]`).

**The treatment arrived.** Measured in the session logs, not from the
roles' own reports: arm A made 0 `knowledge_search` calls (its implementer
reported the tool absent and read files instead); arm B made 5, one in
each of its decomposer, implementer and reviewer sessions.

### The comparable slice — cycle 1 of each arm

Arm B needed a second cycle for a reason unrelated to retrieval (its first
implementer left five scratch files inside the run directory; the reviewer
rejected on that and the rework fixed it). Comparing whole runs therefore
compares one cycle against two. Cycle 1 is the like-for-like slice:

| cycle 1 | arm A — no retrieval (045) | arm B — retrieval (046) | difference |
|---|---:|---:|---|
| tool calls | 91 | 79 | −13 % |
| tokens | 2 752 655 | 2 368 005 | −14 % |
| `knowledge_search` calls | 0 | 3 | treatment applied |
| implementer alone, tool calls | 48 | 34 | −29 % |
| implementer alone, tokens | 1 958 419 | 1 385 512 | −29 % |

### Whole runs, for completeness

| | arm A (045) | arm B (046) |
|---|---:|---:|
| cycles | 1 | 2 |
| tool calls | 102 | 149 |
| tokens | 2 927 631 | 3 847 126 |
| `knowledge_search` calls | 0 | 5 |
| time to first implementation (s) | 1170 | 788 |
| total execution time (s) | 1794 | 3437 |
| review failures | 0 | 1 |
| harness sessions | 4 | 7 |

### Reading

In the comparable cycle the arm that retrieved opened fewer files and spent
fewer tokens, and its implementer — the role that does the exploring — used
29 % fewer of both. Its time to first implementation was also shorter
(788 s against 1170 s). Over the whole run arm B cost more, because an
unrelated review failure added a second cycle; that is a property of this
one run, not of retrieval.

**This is one observation, not a measurement of effect size.** n = 1 per
arm, one task, one model, and the second cycle confounds the totals.
Criterion 7 asks whether retrieval reduces exploration for a representative
run, and this pair answers *yes for the cycle in which it was applied*,
with the caveats stated. A second and third pair on different tasks would
be needed before the percentages mean anything.

One defect this pair exposed: `knowledge_eval.py` renders `retrieval
events 0` for both arms because it counts rows in DPMtF's local
`knowledge_retrieval_log` joined by run id, while a role's retrieval goes
through mcp-light to the knowledge service and is logged there. The
harness's own counter (`scripts/knowledge_run_metrics.py`, which counts
`knowledge_*` tool calls in the session logs) is the one that saw the five
calls.

## Commissioning procedure — the step the supervising session runs next

The evaluation harness (`scripts/knowledge_eval.py`) already prints this
procedure verbatim; it is quoted here exactly, without paraphrase, as the
step the supervising session takes next:

```text
To commission the representative comparison, run the same representative task twice: once with retrieval enabled and once with retrieval disabled in config. After both RUNs complete, print this script's stdout for the comparison. The with_retrieval arm is populated from knowledge_retrieval_log rows joined to execution records by run_id/handoff_id; the without_retrieval arm comes from execution records with no matching knowledge_retrieval_log row.
```
