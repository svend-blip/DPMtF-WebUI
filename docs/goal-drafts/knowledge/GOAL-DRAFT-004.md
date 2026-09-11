# GOAL-DRAFT-004 — LEANN backend adapter behind the provider interface

> Status: DRAFT (planning artifact — not promoted)
> Depends on: GOAL-DRAFT-001, GOAL-DRAFT-003
> **Blocked by: HUMAN APPROVAL REQUIRED — new dependency `leann`**
> Target repository: DPMtF-WebUI (this checkout)

## Mission

Implement LEANN as the first concrete `KnowledgeProvider` backend, confined to
one adapter module. The adapter lazy-loads LEANN so DPMtF imports and runs
without it, exposes index/search through the provider-neutral interface, and
leaves the rest of DPMtF free of LEANN-specific concepts (addendum §2, §3,
§6). This Run may be promoted only after the Human has approved the new
`leann` dependency (`CLAUDE.md` §4 auto-fail #6, §10).

## Human approval flag

- **New dependency:** `leann` must be approved by the Human before promotion.
- **Required evidence of approval:** the Human's promotion command with
  `--approved-by` for this draft, plus a recorded note in the Run ledger that
  the LEANN dependency was approved.
- Until then this draft is BLOCKED and must not be implemented or promoted.

## Standing constraints

- No commits, no pushes, no staging by any chain role (`CLAUDE.md` §5).
- en-US for code and tests.
- LEANN-specific imports, types, and concepts live only in
  `knowledge/leann_provider.py`; no other module may name LEANN.
- The provider-neutral interface in `knowledge/provider.py` is not changed
  for LEANN's sake; the abstraction is the contract.
- `requirements.txt` records `leann` only after the Human approval above, in
  a pinned form (`leann>=<approved-version>` or equivalent).

## Scope fence

May modify:

- `knowledge/leann_provider.py` (new)
- `tests/test_leann_provider.py` (new)
- `requirements.txt` — only the approved `leann` line, after Human approval

Must not touch:

- `knowledge/provider.py`, `knowledge/indexer.py`, `config.py`, `dpmtf.ini`,
  `app.py`, `routers/`, `static/`, `templates/`, `scripts/`, `databases/`
- `.env`, `.git/`, `__pycache__/`
- `docs/SCOPE-ADDENDUM-KNOWLEDGE.md`, governance files

Non-goals:

- No change to the default provider (`none`) or the default disabled state.
- No search endpoint, no prompt injection, no UI in this Run.
- No architectural dependence: the engine never imports LEANN except through
  this adapter.

## Dependencies

- GOAL-DRAFT-001: `KnowledgeProvider` interface and `NoneProvider`.
- GOAL-DRAFT-003: the provider-neutral JSONL manifest is the adapter's
  `index` input for a repository.

## Work items (handoff budget: 4)

1. Implement `knowledge/leann_provider.py` with lazy LEANN import,
   `index(source)` accepting a JSONL manifest path, `search(query, scope,
   filters, top_k, token_budget)` returning bounded results with source
   references, and `update`/`remove` delegating to LEANN where supported.
2. Implement `tests/test_leann_provider.py`: interface conformance without
   LEANN installed, and a live index/search roundtrip that runs when LEANN is
   importable (skipped otherwise). Add the approved `leann` line to
   `requirements.txt` after Human approval.

Reserve: 2 handoff slots for rework.

## Acceptance criteria (shell commands)

```testgoals
id: TG1
what: adapter module compiles
run: venv/bin/python -m py_compile knowledge/leann_provider.py
expect: exit 0

id: TG2
what: adapter implements the provider-neutral interface without importing LEANN at module import
run: venv/bin/python -c 'import knowledge.leann_provider as l; import knowledge.provider as p; print(issubclass(l.LeannProvider, p.KnowledgeProvider))'
expect: equals True

id: TG3
what: LEANN-specific code is confined to the adapter module
run: test -f knowledge/leann_provider.py && ! grep -Rqin 'leann' knowledge --exclude=leann_provider.py --exclude-dir=__pycache__
expect: exit 0

id: TG4
what: approved LEANN dependency is installed and importable
run: venv/bin/python -c 'import importlib.util; print(importlib.util.find_spec("leann") is not None)'
expect: equals True

id: TG5
what: requirements.txt records the approved LEANN dependency
run: venv/bin/python -c 'import pathlib, re; t=pathlib.Path("requirements.txt").read_text(); print(any(re.match(r"^\s*leann[ =<>~]", line, re.I) for line in t.splitlines()))'
expect: equals True

id: TG6
what: adapter tests pass
run: venv/bin/python -m pytest tests/test_leann_provider.py -q
expect: exit 0
```

## Reviewer duties

- Confirm LEANN is imported lazily and only inside `leann_provider.py`.
- Confirm `search` enforces `top_k` and `token_budget` and returns usable
  source references (path plus enough context), not bare similarity scores.
- Confirm `requirements.txt` gained exactly the approved `leann` line and no
  other dependency.
- Confirm the rest of the tree still imports and runs with LEANN uninstalled.
- Rehearse under `dash -c`; TG4 is RED until the Human-approved dependency is
  actually installed — that RED is expected while the draft is blocked.
