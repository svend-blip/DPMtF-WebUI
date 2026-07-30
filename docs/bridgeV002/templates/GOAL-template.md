# GOAL — {run_id}: {one-line objective}

> Copy to `{bridge_dir}/supervisor/runs/{run_id}/GOAL.md`, fill in together
> with the Human, get explicit Human approval, then start the run.
> This file is IMMUTABLE during the run (451_SUPERVISED_REVIEW_SUPERVISOR.md).

## Objective

{What must be TRUE when the run is complete. Outcome, not activity.
One paragraph. If it cannot be verified by the testgoals below, it does
not belong here.}

## Testgoals (executable — the only definition of progress)

<!-- Each testgoal is a runnable command with an expected result.
     A testgoal the supervisor cannot run mechanically is invalid. -->

- TG1: `cd {project_root} && python3 -m pytest tests/{suite} -q` → exit 0
- TG2: `curl -s http://localhost:{port}/api/{endpoint}` → `{"expected": "json"}`
- TG3: `grep -RIn "{forbidden_pattern}" {paths}` → empty output
- TG4: ...

## Scope Fence

Files/directories the run MAY modify:
- {project_root}/{path}/
- {project_root}/{path}/

Files/directories the run MUST NOT touch:
- {project_root}/app.py, config.py, scripts/init_db.py (Human-approval files per 16_FILE_ACCESS.md)
- .env, .git/, other projects' directories

Non-goals (explicitly out of scope):
- {things a drifting run might be tempted to do — name them}

## Budgets

| Budget | Value |
|--------|-------|
| Max handoffs | {8–12 typical} |
| Max wall-clock | {8–12 h} |
| Max rework attempts per handoff | 2 |
| Max consecutive no-progress cycles | 2 |

## Standing Approvals

- Branch: `{feature/branch-name}` — all commits go here, never master
- Commit after each APPROVED verdict: {yes/no}
- Push to remote feature branch: {yes/no}
- {other pre-authorized decisions, or "none"}

## Stop Conditions (run-specific, in addition to 451 §Stop)

- {e.g. "park if TG2 requires touching the scheduler", or "none"}

## Human Approval

- Approved by: {name}
- Date: {ISO date}
