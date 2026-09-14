# Knowledge Scope Isolation

## Grant semantics

A scope is internal when it is exactly `dpmtf` or begins with `dpmtf-`; internal scopes require a matching grant. Non-internal scopes are always allowed without a grant or database access.

The `knowledge_scope_grants` table may hold more than one row for the same
`(scope, agent_role, NULL)` triple: SQLite does not deduplicate NULLs in a
`UNIQUE` constraint. The guard reads `SELECT 1 … LIMIT 1`, so grant behavior
is unaffected.

- `scope` must match the requested scope exactly.
- `agent_role` must match the requested role exactly.
- `flow_key` is the flow dimension only: NULL `flow_key` matches any
  caller flow, non-NULL matches only that flow. It never relaxes `scope`
  or `agent_role`.
- Absence of any matching grant denies access to an internal scope.

## Recording a grant

A Human records a grant by hand against `databases/dpmtf.db`; code paths
never write grants. The SQL shape is parameterized; the Human fills the
values when executing it:

```sql
INSERT INTO knowledge_scope_grants (scope, agent_role, flow_key)
VALUES (?, ?, ?);
```

## Read-only guard behavior

- A missing or unreadable database means no grants (internal scopes deny); the guard opens the database read-only and never creates or writes a DB file.

## Superseded texts

This document supersedes two out-of-fence passages: the exact-grant-triple
wording in `docs/knowledge_layer_overview_with_retrieval.md` lines 238–241,
and the "it is not a wildcard" comments in
`scripts/db/109_knowledge_scope_grants.sql` lines 19/42/45.

## Ecosystem scopes

A flow asks for knowledge about the repository it operates on, so the
compiler binds the knowledge scope to the flow's
`bridge_flows.target_project_path` instead of this checkout's own scope.
`scope_for_target(target_path)` strips trailing slashes, takes the final
path component, and lowercases it: `/home/x/FlowRunner/` → `flowrunner`,
`/home/x/AI_AdvisoryBoard` → `ai_advisoryboard`. An empty path returns
`config.get_knowledge_scope()`.

`scope_for_flow(flow_key)` resolves the flow's target through
`bridge_lib.get_flow_target_project`. A flow with no `target_project_path`,
or one whose target equals `config.get_project_root()` (Father, compared by
resolved path), keeps `config.get_knowledge_scope()`. A missing database, a
missing flow row, or a target that does not exist on disk also falls back to
the configured scope; `scope_for_flow` never raises.

Scope grants keep their existing semantics: a scope is internal when it is
exactly `dpmtf` or begins with `dpmtf-`, and internal scopes require a
matching `knowledge_scope_grants` row. Every other derived scope
(`flowrunner`, `ai_advisoryboard`, `simple-harness`, `trade-ui`, …) is
non-internal and is public under the existing guard, so it needs no grant.

Index layout invariant: one LEANN store per scope, named `<scope>.leann`
under the configured index directory.

Current `bridge_flows` targets and their derived scopes (read from the live
database at write time):

| flow_key | target_project_path | derived scope |
|----------|---------------------|---------------|
| `1000-01-PLOOP` | `/home/svend/DPMtF-WebUI` | `dpmtf-webui` |
| `1000-02-ELOOP` | `/home/svend/DPMtF-WebUI` | `dpmtf-webui` |
| `1010-01-PLOOP` | `/home/svend/simple-harness` | `simple-harness` |
| `1010-02-ELOOP` | `/home/svend/simple-harness` | `simple-harness` |
| `1020-01-PLOOP` | `/home/svend/AI_AdvisoryBoard/` | `ai_advisoryboard` |
| `1020-02-ELOOP` | `/home/svend/AI_AdvisoryBoard/` | `ai_advisoryboard` |
| `2000-01-PLOOP` | — | `dpmtf-webui` |
| `2000-02-ELOOP` | — | `dpmtf-webui` |
| `9000-01-PLOOP` | `/home/svend/FlowRunner/` | `flowrunner` |
| `9000-02-ELOOP` | `/home/svend/FlowRunner/` | `flowrunner` |
| `9010-01-PLOOP` | — | `dpmtf-webui` |
| `9010-02-ELOOP` | — | `dpmtf-webui` |
| `cloud_llm` | — | `dpmtf-webui` |
| `cloud_pay` | `/home/svend/trade-ui` | `trade-ui` |
| `example-01-PLOOP` | — | `dpmtf-webui` |
| `example-02-ELOOP` | — | `dpmtf-webui` |
| `example-cloud` | — | `dpmtf-webui` |
| `lightworker` | `/home/svend/DPMtF-LightWorker` | `dpmtf-lightworker` |
| `llama_SG` | `/home/svend/DPMtF-WebUI` | `dpmtf-webui` |
| `pi_test` | `/home/svend/model-allocator` | `model-allocator` |
| `preferred_cloud` | `/home/svend/AI-Genealogy-Research-Assistant/` | `ai-genealogy-research-assistant` |
| `preferred_cloud_harness` | `/home/svend/harness-allocator` | `harness-allocator` |
| `reveng` | `/home/svend/ruizu-player/` | `ruizu-player` |
| `strict_review` | — | `dpmtf-webui` |
| `supervised_review` | — | `dpmtf-webui` |
| `supervisor` | — | `dpmtf-webui` |
| `trade_cockpit_scoring_v001` | — | `dpmtf-webui` |
| `trade_cockpit_simulation_v001` | — | `dpmtf-webui` |

## Which roles hold the internal dpmtf-webui grant and why

The operator grant `('dpmtf-webui', 'human', NULL)` is in place (run 024 /
migration 111). Migration 112 adds one grant per active, non-`example`
chain-role step whose flow targets Father, with no wildcard `flow_key` and no
wildcard role: `('dpmtf-webui', <to_role>, <flow_key>)`.

The compiler passes the step's `to_role` key as `agent_role`
(`routers/prompt_compiler.py`, `role_name = to_role_key`), so the role key is
the exact string the scope guard compares. The grant is what lets chain roles
read this checkout's own internal `dpmtf-webui` knowledge.

Foreign-targeted flows derive non-internal scopes from their own target
(`ai_advisoryboard`, `flowrunner`, …) and therefore need no `dpmtf-webui`
grant.
