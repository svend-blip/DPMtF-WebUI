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
