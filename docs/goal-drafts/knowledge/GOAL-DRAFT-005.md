# GOAL-DRAFT-005 — Search API and retrieval observability

> Status: DRAFT (planning artifact — not promoted)
> Depends on: GOAL-DRAFT-001, GOAL-DRAFT-002, GOAL-DRAFT-003, GOAL-DRAFT-004
> Blocked by: none (LEANN approval is inherited from GOAL-DRAFT-004)
> Target repository: DPMtF-WebUI (this checkout)

## Mission

Expose semantic retrieval through a DPMtF API endpoint that selects the
configured provider, bounds results by configurable limits, and records every
real retrieval in the append-only `knowledge_retrieval_log`. When the
knowledge layer is disabled or the provider is `none`, the endpoint returns a
structured disabled envelope and writes no log row, so existing execution is
unchanged (addendum §5, §6, §8; success criterion 5).

## Standing constraints

- No commits, no pushes, no staging by any chain role (`CLAUDE.md` §5).
- en-US for code, docstrings, and API responses.
- Config values via `config.py` getters; no hardcoded paths, ports, or
  provider names.
- Parameterized SQL only for the retrieval log insert.
- No new third-party dependencies.
- The API never invents or overrides authoritative context; it returns
  supplemental results only.

## Scope fence

May modify:

- `routers/knowledge.py` (new)
- `knowledge/search.py` (new service layer, optional)
- `app.py` — **Human-approval file** (`CLAUDE.md` §10); only the
  `include_router` line for the knowledge router
- `tests/test_knowledge_api.py` (new)

Must not touch:

- `knowledge/provider.py`, `knowledge/leann_provider.py`,
  `knowledge/indexer.py`, `config.py`, `dpmtf.ini`, `static/`, `templates/`,
  `scripts/`, `databases/`
- `.env`, `.git/`, `__pycache__/`
- governance files and `docs/SCOPE-ADDENDUM-KNOWLEDGE.md`

Non-goals:

- No frontend panel or UI for search in this Run.
- No background indexing, watching, or scheduling.
- No agent-context injection (that is GOAL-DRAFT-006).

## Dependencies

- GOAL-DRAFT-001: provider selection and disabled-by-default config.
- GOAL-DRAFT-002: `knowledge_retrieval_log` table.
- GOAL-DRAFT-003: the manifest built by the indexer is the indexed source.
- GOAL-DRAFT-004: the `leann` provider becomes the first real backend; the
  API stays provider-neutral.

## Work items (handoff budget: 4)

1. Implement `routers/knowledge.py` with `GET /api/knowledge/search`
   (`q`, `scope`, `top_k`, `token_budget` query params with config fallbacks).
   Disabled or `none` provider returns `{"enabled": false, "provider":
   <provider>, "results": [], "bounded": true}` and does not log. Enabled
   providers return bounded results with source references and write one
   `knowledge_retrieval_log` row (provider, scope, query, result count,
   sources, token count, duration, agent_role, run_id, handoff_id).
2. Mount the router in `app.py` and write `tests/test_knowledge_api.py` for
   disabled-mode shape, stub-provider search, log-row insertion, and budget
   enforcement.

Reserve: 2 handoff slots for rework.

## Acceptance criteria (shell commands)

```testgoals
id: TG1
what: knowledge router compiles
run: venv/bin/python -m py_compile routers/knowledge.py
expect: exit 0

id: TG2
what: knowledge route is mounted on the FastAPI app
run: venv/bin/python -c 'import app; print(any(getattr(r, "path", "").startswith("/api/knowledge") for r in app.app.routes))'
expect: equals True

id: TG3
what: knowledge API tests pass
run: venv/bin/python -m pytest tests/test_knowledge_api.py -q
expect: exit 0

id: TG4
what: API layer stays provider-neutral
run: test -f routers/knowledge.py && ! grep -qin 'leann' routers/knowledge.py
expect: exit 0
```

## Reviewer duties

- Confirm the disabled envelope is stable JSON and that disabled mode does
  not insert a retrieval-log row.
- Confirm the enabled path logs every retrieval and never exceeds the
  configured `top_k`/`token_budget`.
- Confirm the endpoint returns source references usable by an agent, not
  scores alone, and does not expose cross-scope results for the requested
  `scope`.
- Confirm `app.py` changed only by adding the router.
- Rehearse under `dash -c`; every criterion must be RED on the current tree
  and cannot pass on an empty repository.
