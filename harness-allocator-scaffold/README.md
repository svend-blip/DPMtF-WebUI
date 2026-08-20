# Harness Allocator — Preferred Cloud Harness Chain for DPMtF — staging

This directory stages two things for the `preferred_cloud_harness` flow:

1. **The standalone `harness_allocator` package** — the independent, optional
   companion project, fully implemented and test-green, staged at
   `harness-allocator/`.
2. **The run-management scaffolding** — the mission contract, run dirs, and
   handoff structure for the flow.

| Artifact | Staged path | Destination (governance location) |
|---|---|---|
| **Package** (whole project) | `harness-allocator/` | `/home/svend/harness-allocator/` |
| **GOAL.md** (Mission Contract, draft) | `flows/preferred_cloud_harness/runs/001/GOAL-DRAFT.md` | `flows/preferred_cloud_harness/runs/001/GOAL-DRAFT.md` — renamed to `GOAL.md` on Human approval |
| **RUNS** | `flows/preferred_cloud_harness/runs/` (run `001`) | `flows/preferred_cloud_harness/runs/` |
| **Handoffs** | `flows/preferred_cloud_harness/handoffs/` (+ `results/`, `verdicts/`) | `flows/preferred_cloud_harness/{handoffs,results,verdicts}/` |
| Product spec | `harness-allocator/GOAL.md` | `/home/svend/harness-allocator/GOAL.md` |

## The package (built and green)

`harness-allocator/` is a stdlib-only, harness-neutral Python package:

```
harness-allocator/
  GOAL.md                product spec (draft)
  README.md              project readme
  pyproject.toml         zero runtime dependencies
  harness-allocator.ini  committed app-config defaults
  harness_allocator/     config/status/definition/adapter/transport/invoke/terminal
  tests/                 all passing
```

Primary interface — the corrected target:

```python
execute(role, harness, model_target, cwd, task)
    -> { status, output, error, elapsed, pid, request_id, ... }
```

**Model boundary:** `model_target` is already resolved by Model Allocator; the
allocator never resolves or substitutes a model (there is no `resolve_model`).

**Atomic dispatch:** the terminal reads length-delimited frames
(`encode_request` / `FrameReader`), so ONE complete semantic task = EXACTLY ONE
harness invocation and embedded newlines never fragment a task.

**Duplicate-request protection:** a completed `(request_id, payload sha256)` is
recorded and never executed twice — a repeat reports `DUPLICATE_REQUEST` and
returns to READY, unless the frame carries an explicit `retry` flag
(`encode_request(..., retry=True)`), which re-executes it.

Verified locally:

- `python3 -c "import harness_allocator"` → OK (no DPMtF config/database import)
- `grep -RInE "bridge_roles|sqlite3|DPMtF-WebUI|scripts/bridgeV002|resolve_model"
  harness_allocator/` → empty (zero coupling, no model resolution)
- `python3 -m pytest tests -q` → 44 passed (atomic transport incl. 20k+ char
  multi-line round-trip, request identity, heartbeat, READY lifecycle,
  duplicate-request protection incl. DUPLICATE_REQUEST -> READY)
- `python3 -m pytest tests/test_preferred_cloud_harness.py -q` (DPMtF-WebUI)
  → 41 passed (unchanged)
- End-to-end framed dispatch smoke test: a multi-line payload piped to
  `python3 -m harness_allocator` produced exactly ONE `[DISPATCH]` / `[RUNNING]`
  / `[SUCCESS]` / `[READY]` cycle with the whole payload as a single argument.

## Why staged here, not in place

The real destinations are not yet written to for this run:

- `/home/svend/harness-allocator/` — target project
  (`bridge_flows.target_project_path`). At the last measurement it was
  read-only to this session; writability is re-checked at run open.
- The flow's bridge dir (`DPMTF_BRIDGE_DIR`) holds the run tree.

## Install (as the Human, or approve an agent to run it)

```bash
# 1. Materialize the whole package project (the companion project).
mkdir -p /home/svend/harness-allocator
cp -R harness-allocator-scaffold/harness-allocator/. /home/svend/harness-allocator/

# 2. Stage the run tree and mission contract.
mkdir -p /home/svend/flows/preferred_cloud_harness/runs/001 \
         /home/svend/flows/preferred_cloud_harness/handoffs \
         /home/svend/flows/preferred_cloud_harness/results \
         /home/svend/flows/preferred_cloud_harness/verdicts

cp harness-allocator-scaffold/flows/preferred_cloud_harness/runs/001/GOAL-DRAFT.md \
   /home/svend/flows/preferred_cloud_harness/runs/001/GOAL-DRAFT.md
```

> The exact bridge dir is read from `DPMTF_BRIDGE_DIR`; do not hardcode
> `/home/svend/flows` at run time.

The package is importable in place (`cd /home/svend/harness-allocator &&
python3 -c "import harness_allocator"`); no install step is required. Run its
tests with `python3 -m pytest tests -q`.

## To open run 001

1. Review `flows/preferred_cloud_harness/runs/001/GOAL-DRAFT.md`; edit any
   **PROPOSED** field (objective, testgoals, scope fence, budgets, standing
   approvals).
2. Rename it to `GOAL.md` in the bridge dir — that rename, not this staging
   copy, is the approval signal that opens the run.
3. On the supervisor's first wake-up it authors `BACKLOG.md`, writes the
   `RUN-LEDGER.md` opening entry, and dispatches handoff `001` per the
   Standing Approvals.

`RUN-LEDGER.md`, `BACKLOG.md` and `END-REPORT.md` are intentionally **not**
staged here: they are authored by the supervisor at run time, and their
absence is what tells `supervisor_state.py` the run has not been opened.
