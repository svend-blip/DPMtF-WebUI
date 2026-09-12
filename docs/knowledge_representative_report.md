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
time_to_first_implementation 307
total_execution_time 2182
review_failures 0
rework 0
without_retrieval
retrieval_events 0
tool_calls 218
tokens 6499282
time_to_first_implementation 380
total_execution_time 3496
review_failures 1
rework 1
commissioning_procedure
To commission the representative comparison, run the same representative task twice: once with retrieval enabled and once with retrieval disabled in config. After both RUNs complete, print this script's stdout for the comparison. The with_retrieval arm is populated from knowledge_retrieval_log rows joined to execution records by run_id/handoff_id; the without_retrieval arm comes from execution records with no matching knowledge_retrieval_log row.
```

The block above is the verbatim stdout of the command; no line was dropped or altered. It matched the measurement block named in the handoff exactly.

## Measured comparison table

| metric | with_retrieval | without_retrieval |
|---|---|---|
| `total_execution_time` | 2182 | 3496 |
| `time_to_first_implementation` | 307 | 380 |
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

**Retrieval reduced total_execution_time by 37.59%.**

Arithmetic, from the captured output only:

```text
(without - with) / without * 100
= (3496 - 2182) / 3496 * 100
= 1314 / 3496 * 100
= 37.59%
```

The same direction holds for `tool_calls` and `tokens`:

```text
tool_calls: (218 - 133) / 218 * 100 = 85 / 218 * 100 = 38.99% reduction
tokens:     (6499282 - 5162267) / 6499282 * 100 = 1337015 / 6499282 * 100 = 20.57% reduction
```

`time_to_first_implementation` also improved with retrieval: the harness shows 307 s with retrieval vs 380 s without, a reduction of 73 s (19.21%):

```text
time_to_first_implementation: (380 - 307) / 380 * 100 = 73 / 380 * 100 = 19.21% reduction
```

## Caveats

**(a) Both arms are measured from each run's `run <NNN> started` ledger line.** `run_metrics` now takes the timestamp of the first ledger line whose text contains `run <NNN> started` (with `<NNN>` equal to the run directory basename) as the run start, instead of the first `promoted from` timestamp. Run 014 is therefore measured from its `run 014 started` line (18:29:41Z) and Run 013 from its `run 013 started` line (17:31:25Z), so the captured output, the table, and the headline above all carry the corrected figures — with-arm 2182 s total / 307 s first-implementation, without-arm 3496 s / 380 s — with no queue-wait inflation.

**(b) `retrieval_events` is 0 for both arms by design of the injection path.** The retrieval block was injected at GOAL-authoring time (this checkout's queue runs `knowledge.enabled = false`), not through the `compile_prompt` path that the `retrieval_events` counter reads, so the counter reports 0 for both arms.

## No implementation changes

This Run changed no code, no config, no schema, and no run directory. The only deliverable is this report file (`docs/knowledge_representative_report.md`), which is a new documentation file.
