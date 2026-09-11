# GOAL-DRAFT-007 — Evaluation harness for with-vs-without retrieval measurement

> Status: DRAFT (planning artifact — not promoted)
> Depends on: GOAL-DRAFT-002, GOAL-DRAFT-005
> Blocked by: none
> Target repository: DPMtF-WebUI (this checkout)

## Mission

Implement a measurement harness that reads `knowledge_retrieval_log` and the
available execution/trace records and prints the comparison addendum §8
requires: tool calls, tokens consumed, time to first implementation, total
execution time, review failures, and rework — for executions with retrieval
versus without. The harness must produce a useful empty report when no data
exists yet and a documented procedure for the representative RUN required by
success criterion 7. This Run builds the instrument; it does not itself run a
full chain comparison.

## Standing constraints

- No commits, no pushes, no staging by any chain role (`CLAUDE.md` §5).
- en-US for code and report labels.
- Parameterized SQL only; read-only toward `knowledge_retrieval_log` and the
  execution records.
- No new third-party dependencies.
- The harness never writes into `runs/`, `handoffs/`, `results/`, or
  `verdicts/`.

## Scope fence

May modify:

- `scripts/knowledge_eval.py` (new)
- `tests/test_knowledge_eval.py` (new)

Must not touch:

- `knowledge/`, `routers/`, `app.py`, `config.py`, `dpmtf.ini`, `static/`,
  `templates/`, `scripts/init_db.py`, `scripts/db/`, `databases/`
- `.env`, `.git/`, `__pycache__/`
- `runs/`, `handoffs/`, `results/`, `verdicts/`, governance files

Non-goals:

- No changes to how retrieval is logged or performed.
- No autonomous execution of a full comparison RUN in this draft; the output
  procedure is the deliverable, the RUN itself is commissioned separately.

## Dependencies

- GOAL-DRAFT-002: `knowledge_retrieval_log` schema.
- GOAL-DRAFT-005: retrieval is logged with `run_id`, `handoff_id`, and
  `agent_role`, which the harness joins against execution/trace records.

## Work items (handoff budget: 4)

1. Implement `scripts/knowledge_eval.py` with a read-only query of
   `knowledge_retrieval_log`, a join to available execution records for the
   comparison metrics, and a fixed text report whose empty state still prints
   every required metric heading with zero values.
2. Write `tests/test_knowledge_eval.py` seeding a temp SQLite database with
   retrieval-log rows and proving the harness reports both arms
   (`with_retrieval` / `without_retrieval`) and the required metric names.

Reserve: 2 handoff slots for rework.

## Acceptance criteria (shell commands)

```testgoals
id: TG1
what: evaluation harness compiles
run: venv/bin/python -m py_compile scripts/knowledge_eval.py
expect: exit 0

id: TG2
what: harness runs and emits the required comparison headings
run: venv/bin/python scripts/knowledge_eval.py | grep -q 'with_retrieval'
expect: exit 0

id: TG3
what: evaluation harness tests pass
run: venv/bin/python -m pytest tests/test_knowledge_eval.py -q
expect: exit 0

id: TG4
what: harness stays provider-neutral
run: test -f scripts/knowledge_eval.py && ! grep -qin 'leann' scripts/knowledge_eval.py
expect: exit 0
```

## Reviewer duties

- Confirm the harness is read-only toward the databases it opens.
- Confirm the empty report still prints all required headings, so a red
  metric is visibly zero rather than absent.
- Confirm the documented procedure in the report says how to commission the
  representative with-retrieval and without-retrieval RUNs and where to find
  the comparison output.
- Rehearse under `dash -c`; every criterion must be RED on the current tree
  and cannot pass on an empty repository.
