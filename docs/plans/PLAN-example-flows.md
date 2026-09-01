# PLAN — Shipped Example Flows (cross-repo quickstart)

> Status: APPROVED 2026-09-01 — all four §6 decisions made by Human; ready to implement.
> Goal: a fresh `git clone` of DPMtF-WebUI + model-allocator + harness-allocator
> on any PC yields working, cloud-only example flows — one flow following the
> 1-flow principle, one pair following the 2-flow (PLOOP/ELOOP) principle.
> Trade flows are explicitly out of scope.

## 1. Why this is possible now

Until 2026-09-01 `databases/dpmtf.db` was committed, so a fresh clone inherited
all 19 of the owner's flows with dead absolute `target_project_path` values
(`/home/svend/trade-ui`, …). The DB is now untracked and purged from history.
A fresh install therefore gets **exactly what the migrations seed — nothing
else**. Example flows seeded by migration become the entire flow catalogue of
a new installation: clean onboarding by construction.

## 2. Where each repo holds its examples (the "init db" question)

| Repo | Mechanism | NOT the place |
|---|---|---|
| DPMtF-WebUI | **Migration** `scripts/db/091_example_cloud_flows.sql` (next free number; `INSERT OR IGNORE`). `scripts/init_db.py` runs migrations first and deliberately seeds no bridge flows — precedent set by `090_9000_flows.sql`: *"seeded by migration so fresh databases carry it"*. | `init_db.py` — it owns canonical UI/label data only. |
| model-allocator | **`.example` YAMLs** — roles/models live in YAML, not in a DB. `allocator.db` is UI-only and fully re-seeded from code on startup. Every `role_key` the example flows use must appear in `roles.example.yaml` (contract: roles.yaml keys == `bridge_roles.role_key`, exact match), with matching aliases in `models.example.yaml` + `runtime_profiles.example.yaml`. | allocator.db. |
| harness-allocator | **`harness-allocator.ini`** — must resolve the example flows' harness (`opencode` / `claude-code`) portably. The tracked ini still hardcodes `/home/svend/simple-harness/bin/simple-harness` (see §6.3). | — |

## 3. The example flows (DPMtF-WebUI, migration 091)

Model the SQL 1:1 on the two best precedents:

**A. 1-flow principle — `example-cloud`** (template: `scripts/db/028_preferred_cloud_flow.sql`, 69 lines)
- Cyclic chain: `ex-super-cl → ex-imple-cl → ex-review-cl → ex-super-cl`,
  `auto_chain_to_next=1`, supervisor_role=`ex-super-cl`.
- Role keys prefixed `ex-` — globally unique (100_BRIDGE Security Rule 7).

**B. 2-flow principle — `example-01-PLOOP` + `example-02-ELOOP`** (template: `scripts/db/090_9000_flows.sql`, 99 lines)
- Shared `artifact_root='example'`; PLOOP owns run-IDs/GOAL-DRAFT and writes
  only under `example/planning/`; ELOOP owns handoffs/results/verdicts.
- Roles: `example-planning-supervisor`, `example-execution-decomposer`,
  `example-implementer`, `example-reviewer`, `example-escalation-supervisor`.

**Portability rules for the SQL (all verified against the live schema):**
- `target_project_path = NULL`, `workdir_mode='father'` on every role — no
  external repos required on a fresh PC.
- `config_dir = NULL`; `deliverable_dir` relative (resolved under
  `DPMTF_BRIDGE_DIR`).
- Governance files are the SHARED generics only — `HUMAN.md`,
  `500_SUPERVISOR.md`, `EXECUTION_DECOMPOSER.md`, `IMPLEMENTOR.md`,
  `REVIEW.md`, `SUPERVISOR_ESCALATION.md`. Never copies (090 rule).
- `default_model_source='model_allocator'`; aliases only ones present in
  `models.example.yaml` (see §4).
- Seed `bridge_id_counters` rows explicitly (self-heal exists, but be clear).
- Zero literal `/home/svend` anywhere in the file.

## 4. model-allocator additions (`.example` YAMLs)

- `roles.example.yaml`: add the eight example role keys above, mapped to the
  chosen alias(es).
- `models.example.yaml`: already carries `cloud_minimax`; add the second cloud
  alias if §6.2 chooses an Anthropic default (e.g. `sonnet5` with
  `ANTHROPIC_API_KEY` env reference — never values).
- `runtime_profiles.example.yaml`: ensure the referenced cloud runtime profile
  exists (`freetoken`/API-based, no GPU assumptions).

## 5. Wiring, docs and guards

- **SETUP.md (DPMtF-WebUI)** — new section "Quickstart: example flows":
  clone the three repos side by side, `cp` each `.example` config into place,
  export the one API key env var, `python3 scripts/init_db.py`, create/point
  `DPMTF_BRIDGE_DIR`, start uvicorn, dispatch `example-cloud` from the UI
  (per the drive-flows-via-UI preference).
- **Bridge dir**: `DPMTF_BRIDGE_DIR` target does not exist on a fresh PC and
  init_db does not create it — either create it during seed/startup or make
  the SETUP step explicit. Decide during implementation; document either way.
- **Tests (DPMtF-WebUI)**: `tests/test_migrate.py` already runs 091 against an
  empty DB automatically. Add one test asserting: the three example flows
  exist after migration, every `governance_file` they reference exists in
  `docs/governance-templates-v2/`, and `scripts/db/091_*.sql` contains no
  literal `/home/svend` (the existing no-hardcoded-paths guard does not cover
  `scripts/db/*.sql`).
- **Stale doc**: `docs/bridgeV002/README.md` still describes the retired
  INI-based flow system — update or archive it in the same change, since the
  quickstart will point new users straight at this area.

## 6. Decisions (Human, 2026-09-01)

1. **`ui_category = 'standard'`** — the example flows appear in the main Flows
   panel; onboarding discoverability wins over daily-panel quiet.
2. **Default combo: `cloud_minimax` + `opencode`** for both examples — the
   alias and runtime profile already exist in the `.example` configs; one
   `MINIMAX_API_KEY` env var suffices. SETUP gets a note on switching combos.
3. **`harness-allocator.ini` → `harness-allocator.ini.example`** — path to
   simple-harness resolved relative to a sibling clone (`../simple-harness`);
   the real `.ini` joins `.gitignore`, matching the service-unit pattern.
4. **simple-harness IS part of the quickstart set** — four repos cloned side
   by side; the ini's sibling default then works out of the box, and the
   committed runtime binary means nothing needs building (~7 MB clone).

## 7. Implementation order

1. `scripts/db/091_example_cloud_flows.sql` (+ rollback file per the
   `scripts/db/rollbacks/` pattern).
2. model-allocator `.example` YAML additions.
3. harness-allocator ini decision (§6.3) applied.
4. SETUP.md quickstart section + bridge-dir handling.
5. New migration test; full suite green; fresh-DB run of
   `python3 scripts/init_db.py` verified.
6. Optional: prune/park the retired `scripts/_deprecated_phase0/seed_bridge.py`
   reference material once 091 supersedes it as prior art.

## 8. Reusable references

- `scripts/db/090_9000_flows.sql` — canonical two-flow seed shape.
- `scripts/db/028_preferred_cloud_flow.sql` — canonical 1-flow cloud seed.
- `scripts/_deprecated_phase0/seed_bridge.py` — only prior seed code for the
  cloud_llm-era flows (convert, do not resurrect).
- `POST /api/bridge-v2/export` (`routers/bridge.py:1846`) — dump an existing
  flow as JSON to draft the SQL from live rows.
- `scripts/bridgeV002/bridge_lib.py:593` `get_effective_artifact_root()` — the
  one canonical artifact-root resolver; never reimplement.
