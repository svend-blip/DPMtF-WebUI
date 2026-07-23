# Test Baseline — 2026-07-23

## model-allocator
- **Tests:** 95 passed, 0 failed, 0 skipped
- **Runtime:** ~4.6s
- **Pre-existing failures:** None

## DPMtF-WebUI
- **Tests:** 17 passed, 2 failed, 0 skipped
- **Runtime:** ~3.5s
- **Pre-existing failures:**
  1. `tests/test_migrate.py::test_migrate_idempotent` — test expects 2 migrations but DB has 4 (003, 004 added since test was written). Test assertion is stale, not a code bug.
  2. `tests/test_migrate.py::test_schema_migrations_tracks_baseline` — same root cause: expects 2 rows in schema_migrations, but 4 exist.

## Gate rule
Future gates compare against this baseline. No new failures may be introduced.
The 2 pre-existing failures in test_migrate.py are documented and accepted.
