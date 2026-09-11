# Knowledge Layer — Draft Series

Planning decomposition of `docs/SCOPE-ADDENDUM-KNOWLEDGE.md` into one-implementer,
one-run contracts. Drafts are numbered in dependency order and are NOT promoted
contracts: promotion remains a Human act.

## Sequence

| Draft | Objective | Depends on | Blocked by |
|-------|-----------|------------|------------|
| GOAL-DRAFT-001 | Config + provider-neutral interface + `none` provider (disabled-by-default) | none | none |
| GOAL-DRAFT-002 | SQL migration for knowledge indexes, exclusions, retrieval log | 001 | none |
| GOAL-DRAFT-003 | Provider-neutral content extraction + exclusions + repository scoping | 001, 002 | none |
| GOAL-DRAFT-004 | LEANN backend adapter behind the provider interface | 001, 003 | **Human approval: new dependency `leann`** |
| GOAL-DRAFT-005 | Search API + retrieval observability log | 001, 002, 003, 004 | none |
| GOAL-DRAFT-006 | Retrieval-before-exploration injection into compiled agent context | 001, 005 | none |
| GOAL-DRAFT-007 | Evaluation harness for with-vs-without retrieval measurement | 002, 005 | none |

## Human approval flag — LEANN

`docs/SCOPE-ADDENDUM-KNOWLEDGE.md` names LEANN as the first retrieval backend.
LEANN is a **new dependency** and therefore an auto-fail under `CLAUDE.md` §4
until a Human approves it. It is confined to **GOAL-DRAFT-004**, which is
`Blocked by: Human approval of new dependency "leann"`.

No other draft imports, names, or requires LEANN. The provider-neutral
interface in GOAL-DRAFT-001 and the indexer in GOAL-DRAFT-003 are deliberate:
they make LEANN replaceable and keep DPMtF from becoming architecturally
dependent on it (addendum §2, §6).

## Reading a draft

Each draft follows this shape:

1. **Mission** — outcome, not activity.
2. **Standing constraints** — chain-wide rules plus `CLAUDE.md` rules.
3. **Scope fence** — may modify / must not touch / frozen paths / non-goals.
4. **Dependencies** — other drafts or D-decisions.
5. **Work items + handoff budget** — small enough for one implementer run.
6. **Acceptance criteria** — a machine-readable `testgoals` block of POSIX
   shell commands (rehearse under `dash -c`; see `CLAUDE.md` §11).
7. **Reviewer duties** — what a count cannot read.

## Cross-cutting decisions

- **Default is disabled.** `knowledge.enabled` defaults to `false` and the
  provider defaults to `none`, so existing DPMtF execution is unchanged until
  a Human enables the layer (addendum success criterion 5).
- **Authority is unchanged.** Retrieval output is supplemental. `GOAL.md`,
  governance, approved architecture, and the current handoff remain
  authoritative (addendum §6). GOAL-DRAFT-006 encodes this in the compiled
  context shape.
- **No commits, no pushes, no staging** by any chain role; `CLAUDE.md` §5.
