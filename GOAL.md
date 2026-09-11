# GOAL-DRAFT-003 — Provider-neutral content extraction and repository scoping

> Status: PROMOTED 2026-09-12 (approved by the Human) — execute with FlowRunner eloop2000
> Depends on: GOAL-DRAFT-001, GOAL-DRAFT-002
> Blocked by: none
> Target repository: DPMtF-WebUI (this checkout)

## Mission

Implement a provider-neutral index builder that scans one selected repository,
applies default and repository-specific exclusion rules, and writes a JSONL
manifest of indexable documents with their `scope` and source path. It builds
the index input for any backend (addendum §3, §4, §9) without importing or
naming LEANN, and it never writes into the repository it scans.

## Standing constraints

- No commits, no pushes, no staging by any chain role (`CLAUDE.md` §5).
- en-US for code, docstrings, and tests.
- Paths come from `config.py` getters where config is needed; no hardcoded
  `/home/...` paths.
- No new third-party dependencies.
- The indexer is read-only toward the scanned repository; the only write is
  the manifest at the caller-supplied output path.
- Default exclusions must cover at least: `.git`, `.env`, `__pycache__`,
  `*.pyc`, `node_modules`, `venv`, `.venv`, `*.db`, `*.sqlite`, `*.bin`,
  images, and files containing private-key or secret markers.

## Scope fence

May modify:

- `knowledge/indexer.py` (new)
- `knowledge/content.py` (new, optional extraction helpers)
- `tests/test_knowledge_indexer.py` (new)

Must not touch:

- `knowledge/provider.py`, `config.py`, `dpmtf.ini`, `app.py`, `routers/`,
  `static/`, `templates/`, `scripts/`, `databases/`
- `.env`, `.git/`, `__pycache__/`
- any file inside a scanned repository

Non-goals:

- No LEANN, no vector store, no search API in this Run.
- No background indexing, watching, or scheduling yet (addendum §7 is a later
  run and requires measurement first).

## Dependencies

- GOAL-DRAFT-001: the manifest format is provider-neutral and feeds the
  `KnowledgeProvider.index` contract.
- GOAL-DRAFT-002: `knowledge_exclusions` is the source of repository-specific
  rules; default exclusions are code constants in this Run.

## Work items (handoff budget: 4)

1. Implement `knowledge/indexer.py` with a CLI
   (`venv/bin/python -m knowledge.indexer --repo <path> --scope <name> --out <file>`)
   that walks text files, applies default exclusions and any enabled
   `knowledge_exclusions` rows for the scope, and writes one JSON object per
   document: `{"scope", "path", "content", "size_bytes", "indexed_at"}`.
2. Implement `tests/test_knowledge_indexer.py` with a temp fixture containing
   a source file, a `.env`-style secret, a private-key marker, a
   `node_modules` dependency, a `__pycache__` artifact, and a binary; assert
   only the source file is emitted, scope and path are correct, and
   per-scope exclusion rows are honored.

Reserve: 2 handoff slots for rework.

## Acceptance criteria (shell commands)

```testgoals
id: TG1
what: indexer module compiles
run: venv/bin/python -m py_compile knowledge/indexer.py
expect: exit 0

id: TG2
what: indexer unit tests pass
run: venv/bin/python -m pytest tests/test_knowledge_indexer.py -q
expect: exit 0

id: TG3
what: CLI indexes the current repository and emits at least one document
run: tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT; venv/bin/python -m knowledge.indexer --repo . --scope dpmtf-webui --out "$tmp/manifest.jsonl"; wc -l < "$tmp/manifest.jsonl"
expect: at least 1

id: TG4
what: a dot-env secret file is never indexed
run: tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT; mkdir -p "$tmp/repo"; printf 'hello\n' > "$tmp/repo/README.md"; printf 'SECRET=abc\n' > "$tmp/repo/.env"; venv/bin/python -m knowledge.indexer --repo "$tmp/repo" --scope test --out "$tmp/manifest.jsonl"; grep -c 'SECRET=abc' "$tmp/manifest.jsonl"
expect: equals 0

id: TG5
what: indexer does not name LEANN
run: test -f knowledge/indexer.py && ! grep -qin 'leann' knowledge/indexer.py
expect: exit 0
```

## Reviewer duties

- Confirm the CLI never writes inside the scanned repository and the manifest
  only goes to `--out`.
- Confirm secrets are excluded by filename and by private-key/secret content
  markers, not merely by extension.
- Confirm per-scope exclusion rows from `knowledge_exclusions` are honored and
  the scope is recorded verbatim on every document.
- Rehearse under `dash -c`; every criterion must be RED before work and cannot
  pass on an empty repository.
