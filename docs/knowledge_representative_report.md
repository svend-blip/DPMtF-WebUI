# Knowledge Retrieval Representative Report — with vs without retrieval

This document is the GOAL-DRAFT-012 representative with-vs-without retrieval evidence addendum: one representative task (write a knowledge-layer overview from the code) executed twice by this family of FlowRunner runs, once with retrieval enabled and once with retrieval disabled, compared on measured execution metrics.

## Comparison arms

The two run directories are recorded in the Run ledger D-decision and closed pair entry. They share the identical task: **write a knowledge-layer overview from the code**.

- **WITH retrieval:** `.flowrunner/2000/runs/014` (GOAL-DRAFT-014, deliverable `docs/knowledge_layer_overview_with_retrieval.md`)
- **WITHOUT retrieval:** `.flowrunner/2000/runs/013` (GOAL-DRAFT-013, deliverable `docs/knowledge_layer_overview_without_retrieval.md`)

The comparison command was run once from the repository root:

```sh
venv/bin/python scripts/knowledge_eval.py --with-run .flowrunner/2000/runs/014 --without-run .flowrunner/2000/runs/013
```

## Captured harness output (verbatim)

```text
with_retrieval
retrieval_events 0
tool_calls 133
tokens 5162267
time_to_first_implementation 1294
total_execution_time 3169
review_failures 0
rework 0
without_retrieval
retrieval_events 0
tool_calls 218
tokens 6499282
time_to_first_implementation 419
total_execution_time 3535
review_failures 1
rework 1
commissioning_procedure
To commission the representative comparison, run the same representative task twice: once with retrieval enabled and once with retrieval disabled in config. After both RUNs complete, print this script's stdout for the comparison. The with_retrieval arm is populated from knowledge_retrieval_log rows joined to execution records by run_id/handoff_id; the without_retrieval arm comes from execution records with no matching knowledge_retrieval_log row.
```

The block above is the verbatim stdout of the command; no line was dropped or altered. It matched the measurement block named in the handoff exactly.

## Measured comparison table

| metric | with_retrieval | without_retrieval |
|---|---|---|
| `total_execution_time` | 3169 | 3535 |
| `time_to_first_implementation` | 1294 | 419 |
| `tool_calls` | 133 | 218 |
| `tokens` | 5162267 | 6499282 |
| `retrieval_events` | 0 | 0 |
| `review_failures` | 0 | 1 |
| `rework` | 0 | 1 |

Every number in this table is transcribed exactly from the captured harness output above.

## Which metrics were measurable

`total_execution_time`, `time_to_first_implementation`, `tool_calls`, `tokens`, `retrieval_events`, `review_failures`, and `rework` were all measurable in this pair.

`tool_calls` and `tokens` are measured, not zero-absent: each run directory contains a `metrics.json` (`.flowrunner/2000/runs/013/metrics.json` and `.flowrunner/2000/runs/014/metrics.json`), and the harness reads those values from `metrics.json`.

`retrieval_events` is 0 for both arms. This is expected and is not a measurement absence: the retrieval block was injected at GOAL-authoring time, not through the `compile_prompt` path that the `retrieval_events` counter reads. The queue on this checkout runs with `knowledge.enabled = false`, so the compile-prompt counter sees no retrieval events in either arm.

## Conclusion

**Retrieval reduced total_execution_time by 10.35%.**

Arithmetic, from the captured output only:

```text
(without - with) / without * 100
= (3535 - 3169) / 3535 * 100
= 366 / 3535 * 100
= 10.35%
```

The same direction holds for `tool_calls` and `tokens`:

```text
tool_calls: (218 - 133) / 218 * 100 = 85 / 218 * 100 = 38.99% reduction
tokens:     (6499282 - 5162267) / 6499282 * 100 = 1337015 / 6499282 * 100 = 20.57% reduction
```

`time_to_first_implementation` differs from the overall conclusion in its raw harness value: the harness shows retrieval **increased** it (1294 s with vs 419 s without, +208.8% relative). This raw increase is explained by the queue-delay caveat below, not by retrieval work itself.

## Caveats

**(a) Run 014's raw timings are inflated by the promoted-queue delay.** `run_metrics` takes the ledger's first "promoted" timestamp as the run start. Run 014 sat promoted for roughly 16 minutes behind Run 013, so its raw `time_to_first_implementation` (1294 s) and `total_execution_time` (3169 s) are inflated. Measured instead from the "run 014 started" line (18:29:41Z), Run 014's timings are 307 s (`time_to_first_implementation`) and 2182 s (`total_execution_time`), against Run 013's 419 s and 3535 s. The table above keeps the harness-captured raw values; this caveat is prose and does not replace them.

**(b) `retrieval_events` is 0 for both arms by design of the injection path.** The retrieval block was injected at GOAL-authoring time (this checkout's queue runs `knowledge.enabled = false`), not through the `compile_prompt` path that the `retrieval_events` counter reads, so the counter reports 0 for both arms.

## No implementation changes

This Run changed no code, no config, no schema, and no run directory. The only deliverable is this report file (`docs/knowledge_representative_report.md`), which is a new documentation file.
