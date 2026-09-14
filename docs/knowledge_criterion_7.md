# Knowledge Criterion 7 — Population Report

> Language: en-US. This report is the honest population summary for family
> 2000 success criterion 7. It compares two populations of different tasks,
> not the same task pair that criterion 7 asks to commission, and it claims
> no causal effect of retrieval.

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

## Commissioning procedure — the step the supervising session runs next

The evaluation harness (`scripts/knowledge_eval.py`) already prints this
procedure verbatim; it is quoted here exactly, without paraphrase, as the
step the supervising session takes next:

```text
To commission the representative comparison, run the same representative task twice: once with retrieval enabled and once with retrieval disabled in config. After both RUNs complete, print this script's stdout for the comparison. The with_retrieval arm is populated from knowledge_retrieval_log rows joined to execution records by run_id/handoff_id; the without_retrieval arm comes from execution records with no matching knowledge_retrieval_log row.
```
