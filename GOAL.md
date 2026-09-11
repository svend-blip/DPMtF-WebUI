# GOAL-DRAFT-001 — Knowledge config and provider-neutral interface

> Status: PROMOTED 2026-09-11 (approved by the Human) — executed by FlowRunner eloop2000 run 0ce394ee5b9e3e87, COMPLETED
> Depends on: none
> Blocked by: none
> Target repository: DPMtF-WebUI (this checkout)

## Mission

Introduce a provider-neutral `knowledge` package and the configuration getters
for the knowledge layer, with the layer **disabled by default** and the
provider defaulting to `none`. When this Run is complete, DPMtF execution is
byte-for-byte unchanged until a Human enables knowledge retrieval, and a
future LEANN or other backend can be added behind one interface without
redesigning flows (addendum §2, §5, §6).

## Standing constraints

- No commits, no pushes, no staging by any chain role (`CLAUDE.md` §5).
- en-US for all code, comments, docstrings, and bridge communication.
- Config values come from `config.py` getters; never hardcode paths, ports,
  or model names (`CLAUDE.md` §3).
- No new third-party dependencies in this Run.
- A `testgoals` criterion may only be edited to correct a defect with a
  ledger ruling; never to make the check quiet (`CLAUDE.md` §11).

## Scope fence

May modify:

- `knowledge/__init__.py` (new)
- `knowledge/provider.py` (new)
- `config.py` — **Human-approval file** (`CLAUDE.md` §10); promotion of this
  GOAL is that approval
- `dpmtf.ini` — **Human-approval file**; add a `[knowledge]` section only
  with disabled-by-default values
- `tests/test_knowledge_provider.py` (new)
- `tests/test_config_knowledge.py` (new)

Must not touch:

- `app.py`, `routers/`, `static/`, `templates/`, `scripts/`, `databases/`
- `.env`, `.git/`, `__pycache__/`
- `docs/SCOPE-ADDENDUM-KNOWLEDGE.md`, governance files, other projects

Non-goals:

- No LEANN import, install, or requirement in this Run.
- No indexing, search endpoint, or agent-context injection yet.
- No UI changes.

## Dependencies

None.

## Work items (handoff budget: 4)

1. Add `knowledge/provider.py` with the abstract `KnowledgeProvider`
   (`index`, `update`, `remove`, `search`) and `NoneProvider` whose `search`
   returns an empty result list. Add `knowledge/__init__.py`.
2. Add `config.py` getters (`get_knowledge_enabled`, `get_knowledge_provider`,
   `get_knowledge_top_k`, `get_knowledge_max_context_tokens`,
   `get_knowledge_index_dir`) reading `[knowledge]` from `dpmtf.ini` with
   disabled-by-default fallbacks; add the `[knowledge]` section to
   `dpmtf.ini`; add tests.

Reserve: 2 handoff slots for rework.

## Acceptance criteria (shell commands)

```testgoals
id: TG1
what: provider module compiles
run: venv/bin/python -m py_compile knowledge/provider.py
expect: exit 0

id: TG2
what: KnowledgeProvider base class is importable
run: venv/bin/python -c 'import knowledge.provider as p; print(p.KnowledgeProvider.__name__)'
expect: equals KnowledgeProvider

id: TG3
what: knowledge layer is disabled by default
run: venv/bin/python -c 'import config; print(config.get_knowledge_enabled())'
expect: equals False

id: TG4
what: default provider is the no-op provider
run: venv/bin/python -c 'import config; print(config.get_knowledge_provider())'
expect: equals none

id: TG5
what: NoneProvider search returns no results without error
run: venv/bin/python -c 'import knowledge.provider as p; print(p.NoneProvider().search("q", scope="dpmtf", filters={}, top_k=5, token_budget=1000))'
expect: equals []

id: TG6
what: provider interface declares index, update, remove, and search
run: venv/bin/python -c 'import knowledge.provider as p; print(all(hasattr(p.KnowledgeProvider, m) for m in ("index","update","remove","search")))'
expect: equals True

id: TG7
what: provider-neutral module does not name LEANN
run: test -f knowledge/provider.py && ! grep -qin 'leann' knowledge/provider.py
expect: exit 0

id: TG8
what: knowledge provider and config tests pass
run: venv/bin/python -m pytest tests/test_knowledge_provider.py tests/test_config_knowledge.py -q
expect: exit 0
```

## Reviewer duties

- Confirm `KnowledgeProvider` is abstract and `NoneProvider` is the only
  concrete provider in this Run.
- Confirm the `[knowledge]` section in `dpmtf.ini` is commented as
  disabled-by-default and the getters fall back safely when the section is
  absent.
- Confirm no third-party import was added and no LEANN string appears in the
  provider-neutral module.
- Rehearse each testgoal under `dash -c` from the project root; every
  criterion must be RED against the current tree before work and cannot pass
  on an empty repository.
