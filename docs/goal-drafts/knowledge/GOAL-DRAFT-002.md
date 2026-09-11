# GOAL-DRAFT-002 — Knowledge storage schema and retrieval log

> Status: DRAFT (planning artifact — not promoted)
> Depends on: GOAL-DRAFT-001
> Blocked by: none
> Target repository: DPMtF-WebUI (this checkout)

## Mission

Add the durable storage for the knowledge layer as a versioned SQL migration:
one table for repository-scoped indexes, one for repository-specific exclusion
rules, and one append-only retrieval log that makes every retrieval observable
(addendum §3, §4, §8). The migration is idempotent, numbered after the current
last migration, and `scripts/init_db.py` applies it unchanged.

## Standing constraints

- No commits, no pushes, no staging by any chain role (`CLAUDE.md` §5).
- en-US for all SQL comments and Python tests.
- Versioned migrations live in `scripts/db/*.sql`; `scripts/init_db.py`
  applies them via `migrate.run_migrations` — do not edit `init_db.py`
  unless a seed is strictly required and idempotent.
- Parameterized SQL only; `CREATE TABLE IF NOT EXISTS`; never destructive.
- No new third-party dependencies.

## Scope fence

May modify:

- `scripts/db/107_knowledge_tables.sql` (new)
- `tests/test_migration_107_knowledge.py` (new)

Must not touch:

- `scripts/migrate.py`, `scripts/init_db.py`
- `app.py`, `routers/`, `static/`, `templates/`, `knowledge/`, `config.py`,
  `dpmtf.ini`
- `.env`, `.git/`, `__pycache__/`, `databases/` (except what `init_db.py`
  itself writes)
- existing migration files in `scripts/db/` (never renumber or edit)

Non-goals:

- No Python knowledge package, indexer, provider, or API in this Run.
- No seed data beyond what the migration itself must contain for exclusion
  defaults.

## Dependencies

- GOAL-DRAFT-001: the config getter for the database path already exists and
  is the only DB-path access used by tests.

## Work items (handoff budget: 4)

1. Write `scripts/db/107_knowledge_tables.sql` with:

   - `knowledge_indexes` — `id`, `scope` (UNIQUE), `provider`, `location`,
     `document_count`, `status`, `updated_at`.
   - `knowledge_exclusions` — `id`, `scope`, `pattern`, `kind`
     (`path`|`name`|`content`), `enabled`, `created_at`, UNIQUE(scope, pattern).
   - `knowledge_retrieval_log` — `id`, `provider`, `scope`, `query`,
     `result_count`, `sources`, `retrieved_token_count`,
     `retrieval_duration_ms`, `agent_role`, `run_id`, `handoff_id`,
     `created_at`.

2. Write `tests/test_migration_107_knowledge.py` proving the migration
   applies to a fresh temp DB, applies idempotently a second time, and
   exposes the required columns.

Reserve: 2 handoff slots for rework.

## Acceptance criteria (shell commands)

```testgoals
id: TG1
what: migration file exists and is discoverable by the migration runner
run: venv/bin/python -c 'import pathlib; print(pathlib.Path("scripts/db/107_knowledge_tables.sql").is_file())'
expect: equals True

id: TG2
what: migration applies cleanly and idempotently to a temp database
run: venv/bin/python -m pytest tests/test_migration_107_knowledge.py -q
expect: exit 0

id: TG3
what: init_db applies the migration without error
run: venv/bin/python scripts/init_db.py
expect: exit 0

id: TG4
what: retrieval log table carries the observability columns
run: venv/bin/python -c 'import sqlite3, config; c=sqlite3.connect(config.get_db_path()); cols=[r[1] for r in c.execute("PRAGMA table_info(knowledge_retrieval_log)")]; print(all(k in cols for k in ("provider","scope","query","result_count","sources","retrieved_token_count","retrieval_duration_ms","agent_role","run_id","handoff_id")))'
expect: equals True

id: TG5
what: all three knowledge tables exist
run: venv/bin/python -c 'import sqlite3, config; c=sqlite3.connect(config.get_db_path()); names=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type=\"table\" AND name LIKE \"knowledge_%\"")]; print(len(names))'
expect: at least 3
```

## Reviewer duties

- Confirm the migration number is the next after the current last migration
  and no existing migration was edited.
- Confirm the SQL is non-destructive (`IF NOT EXISTS`, no `DROP`, no
  `DELETE`) and that the retrieval log is append-oriented.
- Confirm the exclusion table supports per-scope rules (`kind`, `enabled`).
- Rehearse under `dash -c`; every criterion must be RED on the current tree
  before the migration exists.
