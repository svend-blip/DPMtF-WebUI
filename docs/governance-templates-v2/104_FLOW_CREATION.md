# 104 — Flow Creation

> How to create a new two-flow family (PLOOP + ELOOP) correctly and
> uniformly. Read this in full before adding flows. This file is the
> authoritative checklist; the live proof is `mcp-light`'s
> `validate_flow_family(<family>)` — run it green before you call a family
> done. 100_BRIDGE.md rules the protocol; 103_FLOW_STARTUP.md rules startup.

## 1. When this applies

A "flow family" is a matched pair sharing one artifact root:

- `{NNNN}-01-PLOOP` — planning: `human ↔ {NNNN}-planning-supervisor`.
- `{NNNN}-02-ELOOP` — execution: `decomposer → implementer → reviewer`
  (plus an optional escalation role).

Both flows share `artifact_root = '{NNNN}'` and one `cold_start_skill`.
Creating a family means: a migration, model-allocator role entries, a
cold-start skill, and their test registrations — all four, or the family is
half-wired and fails on a fresh build.

## 2. Decide the identity first (write it down before touching anything)

| Field | Rule |
|------|------|
| Family number `{NNNN}` | Distinct from every existing flow. Role keys MUST be unique across ALL flows (100_BRIDGE Security Rule 7). |
| `target_project_path` | The repo the ELOOP builds. **NULL in the migration** (portable, no machine path in a committed file — auto-fail rule + `test_governance_no_hardcoded_paths`), set live in the DB after apply. |
| `artifact_root` | `'{NNNN}'` on BOTH flows. |
| `cold_start_skill` | `'{NNNN}'` on BOTH flows. The skill is created in §6. |
| `supervisor_role` | `{NNNN}-planning-supervisor` on BOTH flows (NULL routes to `supervisor_auto`, which fresh DBs do not carry). |
| `commit_cadence` | PLOOP `none`; ELOOP `none` until a mandate exists, then `per_run` / `per_handoff`. |
| per role: model + harness | Decided in §3 — the compatibility gate. |

## 3. Model / harness compatibility — the gate that bites

A role's `default_model_alias` (model-allocator) MUST declare the role's
`default_harness_source` as a client, or it will not resolve. The three
harnesses in use each demand a different alias shape:

- **claude-code** needs an **Anthropic-endpoint** alias (e.g. `cloud_deepseek`
  → `.../anthropic`, or `opus5` subscription). An OpenAI-only alias cannot
  drive claude-code.
- **simple-harness** needs an **openai_compatible** alias whose `clients:`
  block lists `simple-harness: true` (e.g. `cloud_deepseek_v4pro_direct`).
- **codex** is a NATIVE harness: `default_model_source = 'harness_provider'`,
  `default_model_alias` the literal model id, and codex resolves **ONE
  global provider** from its own `~/.codex/config.toml` — there is NO
  per-role provider. Two codex roles on different providers cannot coexist,
  so do not put a codex role on a second provider while another live flow
  needs the first (this is why 9010's ELOOP moved off codex onto
  simple-harness, 2026-09-07).

Confirm the alias exists in model-allocator `models.yaml` before wiring a
role to it.

## 4. The migration `scripts/db/{NNN}_{family}_flows.sql`

Next free numeric prefix (ignore the 900-series). RAW SQL — no
`BEGIN`/`COMMIT`/`PRAGMA` (migrate.py wraps each file in its own
transaction). Idempotent: `INSERT OR IGNORE` throughout. No absolute machine home paths
anywhere (comments included). Seed, in one file:

1. `bridge_flows` — both rows: `flow_key, name, description, artifact_root,
   target_project_path (NULL), is_active (1), auto_complete_enabled (0),
   ui_category, supervisor_role, cold_start_skill, commit_cadence`.
2. `bridge_roles` — one row per role: `role_key, tmux_session, role_type
   ('agent'), is_active (1), default_model_source, default_model_alias,
   allocator_client, default_harness_source, default_harness_profile,
   workdir_mode ('father' for the supervisor, 'target_project' for chain
   roles), governance_file, config_dir, fresh_session_command`. A resident
   planning supervisor takes `fresh_session_command = NULL` (a `/clear`
   wipes its context on wake-up).
3. `bridge_flow_steps` — see §5.

**Broker-created tables are a trap.** `bridge_materialize_queue` (and any
table `bridge_broker.py` makes with `CREATE TABLE IF NOT EXISTS` at runtime)
does NOT exist on a migration-only build. A migration that touches such a
table MUST first `CREATE TABLE IF NOT EXISTS <table> (<original schema>)` —
a no-op on the live DB, a real create on a fresh one. `bridge_convention_rules`
and the other baseline tables (001) are safe; broker-runtime tables are not.
(Learned when migration 102 passed live and broke every fresh-build test.)

## 5. Steps — the canonical shape

PLOOP (2 steps):

| step_key | from → to | deliverable_dir | pattern | rule_key | governance |
|---|---|---|---|---|---|
| `human-planning` | human → planning-supervisor | `{NNNN}/planning` | `{ID}-request.md` | `handoff` | `HUMAN.md` |
| `planning-human` | planning-supervisor → human | `{NNNN}/goals` | `{ID}-GOAL-DRAFT.md` | `callback` | `SUPERVISOR_PLANNING.md` |

ELOOP (3 steps, `validation_required = 1`):

| step_key | from → to | deliverable_dir | pattern | rule_key | governance |
|---|---|---|---|---|---|
| `decomposer-implementer` | decomposer → implementer | `{NNNN}/handoffs` | `{ID}-handoff.md` | `handoff` | `EXECUTION_DECOMPOSER.md` |
| `implementer-reviewer` | implementer → reviewer | `{NNNN}/results` | `{ID}-result.md` | `callback` | `IMPLEMENTOR.md` |
| `reviewer-decomposer` | reviewer → decomposer | `{NNNN}/verdicts` | `{ID}-verdict.md` | `agent_delivery` | `REVIEW.md` |

Reuse the shipped generic governance files above unless the family needs its
own; never invent role governance a role cannot find.

## 6. Model-allocator `roles.yaml`

One entry per `role_key`, matching `bridge_roles` EXACTLY (the keys are the
contract). For each role:

```yaml
  {NNNN}-<role>:
    default_alias: <alias>
    # config_dir: only the planning supervisor, mirroring 9000
    client_aliases:
      <harness>: <alias>
```

A codex `harness_provider` role needs NO roles.yaml entry (codex owns the
model). Every other role needs one, or the allocator cannot resolve it.

## 7. Cold-start skill `{NNNN}`

Create it in BOTH places, byte-identical:

- `~/.claude/skills/{NNNN}/SKILL.md` — the one `/{NNNN}` actually loads.
- `{repo}/.claude/skills/{NNNN}/SKILL.md` — the version-controlled copy.

Model it on `.claude/skills/9000/SKILL.md`: front-matter `name`/`description`,
the flow facts (both flow keys, artifact root, target repo, per-role model +
harness), the Step-0 context diet, the shell fallback, an "If you are
{NNNN}-planning-supervisor" section, and the flow-specific hazards. It exists
to be paste-runnable on THIS machine, so it carries literal paths — and
therefore EVERY absolute home-path line MUST be added to `ALLOWED_LINES` under
`"{NNNN}/SKILL.md"` in `tests/test_governance_no_hardcoded_paths.py`, or the
governance test fails.

## 8. Test registrations

- `tests/test_governance_no_hardcoded_paths.py` — the `{NNNN}/SKILL.md`
  allow-list entry (§7).
- `tests/test_migration_005.py` — add any `codex`/`dsh` **native-harness**
  role to `HARNESS_ROLES` (it must carry `harness_provider`); do NOT list a
  `model_allocator` role there. Removing a role from codex means removing it
  from this list.

## 9. Verify before declaring done

1. **Fresh build**: `migrate.run_migrations(<temp db>)` on an EMPTY DB runs
   clean and the new flows appear. Live-apply does NOT prove this (§4).
2. **Resolve**: for each role, `bridge_lib.get_effective_model_source(role)`
   returns the intended `(source, alias)`, and the model-allocator resolve
   yields the expected endpoint/model.
3. **Tests**: `test_governance_no_hardcoded_paths`, `test_migration_005`,
   `test_example_flows_seed`, `test_migrate` all green.
4. **Set the live target path**: `UPDATE bridge_flows SET
   target_project_path=... WHERE flow_key LIKE '{NNNN}%'` (not in the
   committed migration).
5. **id counter**: seed `bridge_id_counters` for the PLOOP flow if the first
   draft must not land at id 1.
6. **mcp-light**: `validate_flow_family('{NNNN}')` is green on every item.

## 10. mcp-light exposure

This checklist is served read-only through mcp-light:

- `get_governance_index` lists it; `get_governance_file('104_FLOW_CREATION.md')`
  returns it (add `section='<n>'` for one section).
- `validate_flow_family('{NNNN}')` runs the §9 structural checks against the
  live DB, `roles.yaml`, and the skill files, returning a per-item PASS/FAIL
  report. A family is not done until it is green.

## 11. Git

The migration, the skill repo-copy, and the test edits are one change set
(the Human commits per 15_GIT_POLICY). The model-allocator `roles.yaml` edit
ships in the same change set on the model-allocator repo. `databases/dpmtf.db`
carries the live rows (the standing exception) and the live `target_project_path`.
