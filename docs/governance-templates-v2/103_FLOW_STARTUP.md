# 103 — The Flow Startup Contract

This document is the binding cold-start contract for every BridgeV002
flow. It describes ONLY what is live at authoring time — every
command runs as written, every referenced path exists in the tree,
every named role, flow, or column is a current fact.

The generic behavioral governance files
(`docs/governance-templates-v2/IMPLEMENTOR.md`, `REVIEW.md`,
`SUPERVISOR_AUTONOMOUS.md`, `SUPERVISOR_PLANNING.md`,
`SUPERVISOR_ESCALATION.md`, `EXECUTION_DECOMPOSER.md`, `ARCHITECT.md`,
`HUMAN.md`, `ADDENDUM_AUTONOMOUS_RUN.md`,
`ADDENDUM_LOCAL_MODEL_LIFECYCLE.md`) are the live resolution: the
step-key resolver (`scripts/bridgeV002/execution_config.py`) walks
STEP → ROLE → SYSTEM, so a step binds the generic file its role
family carries. The pre-GH numbered per-flow files (4xx/5xx
originals) remain as role-level fallbacks only — do NOT cite them as
the live governance surface.

`bridge_flows.supervisor_role` is seeded and live for the five
autonomous flows (migration 065, Run 011): `supervised_review →
supervisor_auto`, `llama_SG → supervisor01_llama`, `reveng →
Rev_Supervisor`, `preferred_cloud → Pre-super-cl`,
`preferred_cloud_harness → super-deep-deep4`. The
`_supervisor_wake_up` function in
`scripts/bridgeV002/chain_watchdog.py` reads this column to name the
stall-escalation wake-up target. Migration 097 seeds it for the
two-flow families: both `{family}-01-PLOOP` and `{family}-02-ELOOP`
name `{family}-planning-supervisor` (Claude Code, workdir = the Father
project, bound to `SUPERVISOR_PLANNING.md`). The watchdog sends the
target role's `fresh_session_command` before the wake-up, which is
why that command is NULL for resident planning supervisors — their
session is already running and must not be replaced.

---

## Supervisor-Driven Flows

Flows: `llama_SG`, `preferred_cloud`, `preferred_cloud_harness`,
`reveng`. (`supervised_review` carries an autonomous supervisor —
`supervisor_auto` — and follows the same shape.)

| Aspect | Binding |
|---|---|
| Start artifacts | `{bridge_dir}/{flow_key}/runs/{NNN}/GOAL.md`, `BACKLOG.md`, `RUN-LEDGER.md` (default bridge dir: `/home/svend/flows`) |
| WHO writes each | **Human** approves the run by renaming `GOAL-DRAFT.md` → `GOAL.md` — that rename IS the approval act; a draft is never adopted. The **supervisor role** materializes `BACKLOG.md` and `RUN-LEDGER.md` via the broker seam (`scripts/bridgeV002/bridge_broker.py materialize`) — never direct filesystem writes. |
| First dispatch | A wake-up to the value of `bridge_flows.supervisor_role` for the flow. The wake-up is enqueued via `scripts/bridgeV002/bridge_broker.py enqueue --action signal-send`. |
| Verification | `python3 scripts/bridgeV002/supervisor_state.py --flow {flow_key}` reports the active run with its floor and counter (NOT `PARK`). |

A directory is NOT a run until it holds at least one of the three
artifacts (and the GOAL has been approved — see the Binding Rules).

## Two-Flow Families (PLOOP / ELOOP)

Flows: the `1000-`, `1010-`, `9000-`, `9010-` and `example-` pairs.
A family is two flow rows sharing one `artifact_root`:
`{family}-01-PLOOP` (steps human-planning → planning-human) and
`{family}-02-ELOOP` (decomposer-implementer → implementer-reviewer →
reviewer-decomposer). The planning supervisor
(`{family}-planning-supervisor`, Claude Code, workdir = the Father
project) is bound to `SUPERVISOR_PLANNING.md` (migration 097) and is
named in `bridge_flows.supervisor_role` on BOTH rows.
`bridge_flows.supervisor_mandate` (NULL = planning only) and
`bridge_flows.commit_cadence` (`none` | `per_run` | `per_handoff`)
exist from migration 096 and are UI-managed.

| Aspect | Binding |
|---|---|
| Start artifacts | `{bridge_dir}/{artifact_root}/SCOPE.md` (Human-owned) → `{bridge_dir}/{artifact_root}/goals/{ID}-GOAL-DRAFT.md` → `{bridge_dir}/{artifact_root}/runs/{NNN}/GOAL.md` (+ `RUN-LEDGER.md`, `END-REPORT.md`); planning backlog at `{bridge_dir}/{artifact_root}/planning/PLOOP-BACKLOG.md` |
| WHO writes each | The **Human** writes `SCOPE.md`. The **planning supervisor** drafts GOALs. The **Human** promotes: `python3 scripts/bridgeV002/bridge_broker.py promote-goal --flow {family}-01-PLOOP --run-id N --approved-by <human>` — the promotion IS the approval act (the `testgoals` block is parse-gated by `promote-goal`). |
| First dispatch | A promoted GOAL is NOT an open Run. The Run opens with a kickoff prompt from the planning supervisor (under mandate) or the Human, pasted into the decomposer's pane — `SUPERVISOR_PLANNING.md` §Kickoff Protocol. Never `--signal-send`. |
| Verification | `python3 scripts/bridgeV002/supervisor_state.py --flow {family}-01-PLOOP` and `--flow {family}-02-ELOOP`, plus the "Run NNN opened" entry in `runs/{NNN}/RUN-LEDGER.md`. |

The Human's startup order:

1. Write `{bridge_dir}/{artifact_root}/SCOPE.md`.
2. Set the family's flow rows in the UI: `target_project_path`,
   `artifact_root` and `cold_start_skill` on both rows,
   `supervisor_role` on both rows, `supervisor_mandate` and
   `commit_cadence` on the ELOOP row.
3. `python3 scripts/bridgeV002/start_tmuxflow.py {family}-01-PLOOP`
   and `python3 scripts/bridgeV002/start_tmuxflow.py {family}-02-ELOOP`.
4. `python3 scripts/bridgeV002/start_coding.py` for both flows.
5. `systemctl --user is-active bridge-broker.service` → `active`.
6. Attach to the planning supervisor's tmux session; the first prompt
   is `/{cold_start_skill}`.
7. Answer its clarifying questions; review the drafts it writes to
   `{bridge_dir}/{artifact_root}/goals/`.
8. Promote: `python3 scripts/bridgeV002/bridge_broker.py promote-goal
   --flow {family}-01-PLOOP --run-id N --approved-by <human>`.
9. With a mandate set, the planning supervisor kicks off Run N itself;
   without one, the Human pastes the kickoff prompt into the
   decomposer's pane (`SUPERVISOR_PLANNING.md` §Kickoff Protocol).

## Architect-Driven Flows

Flows: `strict_review`, `cloud_llm`, `cloud_pay`.

| Aspect | Binding |
|---|---|
| Start artifact | A handoff file at `{bridge_dir}/{flow_key}/handoffs/{NNN}-handoff.md` (no `GOAL.md` is required; the contract lives in the handoff) |
| WHO writes it | The **Human / Architect** writes the handoff directly. |
| First dispatch | `python3 scripts/bridgeV002/dispatch.py --signal-send --flow {flow_key} --handoff-id {NNN} --from-role <architect>` (or the equivalent broker seam). |
| Verification | The first role's cold-start skill (per `.claude/skills/{SKILL}/SKILL.md`) reconstructs its context and accepts the handoff. No `supervisor_state.py` assessment applies. |

## Bare Flows

Flows: `supervisor`, `pi_test`, `lightworker`.

| Aspect | Binding |
|---|---|
| Contract | Minimal — no `GOAL.md` run directory, no Architect handoff file. Each flow has whatever per-flow file its owner maintains. |
| WHO writes it | **Human**, ad hoc. |
| First dispatch | Manual — no broker-mediated chain. |
| Verification | n/a — no `supervisor_state` assessment and no cold-start skill bind here. |

Only state what is live: if a bare flow has no contract file at all,
say so.

## Cold Start From Nothing

The bring-up sequence, in order. Every command below has been
executed against the live tree; runnable as written.

1. **Bring up tmux sessions for the flow's roles.**

   ```bash
   python3 scripts/bridgeV002/start_tmuxflow.py {flow_key}
   ```

   `start_tmuxflow.py` ensures every `tmux_session` in the flow's
   role set exists; it creates what is missing and leaves the rest.

2. **Start the coding frontend in each tmux session.**

   ```bash
   python3 scripts/bridgeV002/start_coding.py {flow_key}
   ```

   `start_coding.py` resolves each role's harness source (the
   `default_harness_source` column, with `allocator_client` as the
   deprecated fallback) and launches the matching client.

3. **For harness-backed roles, launch the persistent Harness
   Terminal.**

   ```bash
   python3 scripts/bridgeV002/harness_terminal.py \
     --role {role_key} \
     --harness {harness_key} \
     --model {model_alias} \
     --flow {flow_key} \
     --cwd {path}
   ```

   The flag shape comes from `start_coding.py`'s
   `_harness_terminal_command` — do not invent flags.

4. **Verify the broker daemon is live — REQUIRED for any flow with
   sandboxed roles.**

   ```bash
   systemctl --user is-active bridge-broker.service
   ```

   The unit file is `scripts/bridgeV002/bridge-broker.service`
   (installed to `~/.config/systemd/user/bridge-broker.service`).
   It MUST print `active`. If it does not, the sandboxed-role chain
   cannot advance — the broker is the host-side seam a sandboxed role
   uses to request a transition without gaining unrestricted host
   access. Without `active`, queued signal rows pile up and the chain
   silently stalls (preferred_cloud run 004 paid for this once,
   2026-07-21). Install + start the unit:

   ```bash
   install -m 0644 scripts/bridgeV002/bridge-broker.service \
     ~/.config/systemd/user/bridge-broker.service
   systemctl --user daemon-reload
   systemctl --user enable --now bridge-broker.service
   ```

## Binding Rules

The run-proven laws. Each one is a load-bearing invariant; the chain
fails or silently stalls when any is broken.

1. **A directory is not a run until it holds a run artifact;
   `GOAL-DRAFT.md` is never adopted.** The Human approves a run by
   renaming `GOAL-DRAFT.md` → `GOAL.md`; the rename IS the approval
   act. A `GOAL-DRAFT.md` is not a contract and may not be read as
   one.

2. **Materialize the handoff BEFORE enqueueing its signal-send.** The
   broker's materialize row must be on disk before the signal-send
   row is enqueued. Enqueueing a signal-send whose target file is
   missing causes the receiver to fail to find its contract and the
   chain to mis-stall.

3. **The closing turn persists `END-REPORT.md` via broker
   materialize — never direct filesystem writes from a sandbox.** A
   sandboxed role (Codex workspace-write; DeepSeek Harness sandbox)
   cannot write to `{bridge_dir}/` directly. The closing role
   enqueues a materialize row via `bridge_broker.py materialize`;
   the daemon writes the file host-side.

4. **Governance resolves STEP → ROLE → SYSTEM.** The resolver at
   `scripts/bridgeV002/execution_config.py` walks
   `bridge_flow_steps.governance_file` →
   `bridge_roles.governance_file` → SYSTEM (legacy fallback). The
   generic behavioral files — `IMPLEMENTOR.md`, `REVIEW.md`,
   `SUPERVISOR_AUTONOMOUS.md`, `ARCHITECT.md`, `HUMAN.md`, plus the
   ADDENDUM files where relevant — are the live resolution for
   almost every step; the pre-GH 4xx/5xx originals survive only as
   role-level fallbacks.

5. **The RUNTIME CONTEXT block carries the concrete identity.** The
   five-field block injected at the top of a role's prompt
   (`flow_key`, `step_key`, `from_role`, `to_role`,
   `governance_file`) names the concrete instance — the generic
   behavioral files bind on that block rather than naming flows,
   roles, or models.

6. **`bridge_flows.supervisor_role` names the wake-up target for
   stall escalation.** `scripts/bridgeV002/chain_watchdog.py`'s
   `_supervisor_wake_up` reads this column. Migration 065 (Run 011)
   seeded it for the five autonomous flows: `supervised_review →
   supervisor_auto`, `llama_SG → supervisor01_llama`, `reveng →
   Rev_Supervisor`, `preferred_cloud → Pre-super-cl`,
   `preferred_cloud_harness → super-deep-deep4`. Migration 097 seeds
   it for the two-flow families: both `{family}-01-PLOOP` and
   `{family}-02-ELOOP` → `{family}-planning-supervisor`. The column is
   seeded and live — not opt-in. The watchdog sends the target role's
   `fresh_session_command` before the wake-up; for resident planning
   supervisors that command is NULL so the running session is woken,
   not replaced.

7. **`bridge_broker.service` is a precondition for any flow with
   sandboxed roles.** See step 4 of the Cold Start From Nothing
   sequence; a non-`active` broker daemon stalls the chain silently.

8. **A promoted GOAL is not an open Run; the kickoff is a separate
   event, recorded in the Run's ledger before the prompt is
   delivered.** `promote-goal` writes `runs/{NNN}/GOAL.md`; the Run
   opens only when a kickoff prompt from the planning supervisor
   (under mandate) or the Human is pasted into the decomposer's pane
   (`SUPERVISOR_PLANNING.md` §Kickoff Protocol), never via
   `--signal-send`.
