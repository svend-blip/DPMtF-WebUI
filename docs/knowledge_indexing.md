# Knowledge Indexing

This file documents the default exclusions and the document size cap applied
by `knowledge/indexer.py`.

## Default directory-name exclusions

`logs`, `jobs`, `.flowrunner`, `.pytest_cache`, `.playwright-mcp`,
`.superpowers`, `.ruff_cache`, `.mypy_cache`, `.claude`, `knowledge_index`,
`dist`, `build`, `exports`, `backups`.

## Prefix exclusion

Any directory or file whose name starts with `.aider` is excluded
(`_DEFAULT_EXCLUDED_PREFIXES`).

## Default suffix exclusions

`.log`, `.jsonl`, `.bak`, `.tar`, `.gz`, `.zip`, `.whl`, `.parquet`,
`.leann`, `.idx`.

## Document size cap

`config.get_knowledge_max_document_chars()` reads
`[knowledge] max_document_chars` from `dpmtf.ini` and defaults to `20000`
when the key or section is absent. When a document's content is longer than
the cap, the indexer truncates `content` to that many characters and sets
`"truncated": true` on the emitted record; the key is absent otherwise.
`size_bytes` always keeps the real, pre-truncation file size. The CLI flag
`--max-document-chars N` overrides the configured value for one run; a
non-positive `N` is rejected with exit 1 before any manifest is written.

## Maintenance-loop consequence

`knowledge/maintenance.py` compares freshly loaded document text against the
manifest's **capped** `content`, so a document larger than the cap is
reported as changed on every maintenance pass. This is the intended
consequence of capping at record-build time; `knowledge/maintenance.py` is
not modified by this run.

## Repository-specific exclusions

The indexer reads `<repo>/.knowledgeignore` when it is present; a missing
file is not an error. One pattern per line; `#` comments and blank lines
are ignored; a trailing `/` marks a directory pattern.

Patterns are matched with `fnmatch` against both the repository-relative
path and the basename, so `*.tmp` matches at any depth and `data/` prunes
the directory during the walk. Directory patterns apply only to
directories; file patterns apply only to files.

File rules are merged with the `knowledge_exclusions` rows for the
requested scope; neither replaces the other. Default exclusions are
applied first, and a file or directory is skipped when any default
exclusion, DB row, or `.knowledgeignore` rule matches. A
present-but-unreadable or non-UTF-8 `.knowledgeignore` aborts the run
(exit 1, no silent skip).

This repository ships `.knowledgeignore` with `jobs/`, `logs/`,
`.flowrunner/`, `databases/*.bak`, `knowledge_index/`, and `*.pyc`. The
first five are already covered by the default exclusions, so the shipped
file demonstrates the mechanism and satisfies TG3 rather than newly
excluding trees the defaults already exclude.

The `.knowledgeignore` control file itself is excluded from indexing by default (it is in `_DEFAULT_EXCLUDED_NAMES`), so a repository scan never emits the control file as a document.

## Refreshing an index

`POST /api/knowledge/refresh` re-runs the indexer and the configured provider
for one scope. The body is `{"scope": "<name>", "repo_path": "<existing dir>"}`.

When knowledge is disabled the endpoint returns the search endpoint's disabled
envelope (`enabled: false`, `results: []`, `bounded: true`) without touching
the indexer, provider, or database.

Otherwise it compares the repository against the existing manifest first. An
unchanged repository returns `{"status": "noop", "manifest": "<index_dir>/<scope>.jsonl"}`
without calling the provider. A changed or missing manifest re-indexes and
returns `{"status": "reindexed", "documents": N, "manifest": "<index_dir>/<scope>.jsonl"}`.
The manifest lives under `config.get_knowledge_index_dir()`.

curl shape:

    curl -sS -X POST http://127.0.0.1:8000/api/knowledge/refresh \
      -H 'Content-Type: application/json' \
      -d '{"scope": "dpmtf-webui", "repo_path": "/absolute/path/to/repo"}'

### Ecosystem refresh script

`scripts/knowledge_refresh_ecosystem.py` refreshes every repository the flows
target in one run. It reads every distinct non-empty
`bridge_flows.target_project_path` from the configured database, adds Father
(`config.get_project_root()`), derives each target's scope through
`knowledge.scopes.scope_for_target` (Father keeps its configured scope), skips
targets that no longer exist on disk, and calls
`knowledge.maintenance.refresh_scope` for each existing target. It prints one
tab-separated line per existing target (`<scope>\t<status>\t<documents>`), with
missing-target and per-target failure lines on stderr. `--dry-run` lists the
targets and scopes without touching anything. The exit code is 0 only when
every existing target refreshed or was a noop, and 1 when any target failed.

## GPU requirement

Retrieval still needs a free GPU: the LEANN call path does its embedding
work on the GPU at query time, not only during indexing.

The new default is daemon-free. `[knowledge] leann_use_daemon` is `false`,
read by `config.get_knowledge_leann_use_daemon()` and forwarded to
`LeannSearcher` as `use_daemon=False`. In this mode no
`hnsw_embedding_server` daemon is spawned and nothing stays resident after
the search.

Measured 2026-09-14 on the `dpmtf-webui` store (656 passages, free GPU):

| mode | per search | resident afterwards |
|---|---|---|
| daemon (today) | 7.1 s cold, 1.0 s warm | daemon 1.6–2.2 GB, 900 s TTL |
| `use_daemon=False` | 8.3–9.3 s every time | nothing |

Same top-3 results on three queries. One retrieval per dispatch makes
9 seconds acceptable, so the daemon's failure modes are not worth the
warm-cache speedup.

### When the daemon is switched on

When `leann_use_daemon = true`, redirect a searching process's stdout/stderr
to `/dev/null` or the harness that captures it waits forever (run 024, gate TG7
timed out after 900 s).

Measured 2026-09-13: with the GPU held by a resident local model, a
649-document build did not finish in 10 minutes and three of three searches
against a warm server aborted with `SIGABRT` on the compiled-in 30-second ZMQ
timeout. A `SIGABRT` inside a provider call kills the whole calling process
(uvicorn worker / a dispatch).

> The stdout/stderr-inheritance note about a harness that captures a
> searching process hanging forever applies only when the daemon is
> switched on (`leann_use_daemon = true`), not in the default
> `use_daemon=False` mode.

The readiness contract is provider-neutral. `[knowledge]
min_free_vram_mib` (default `4096`) is read by
`config.get_knowledge_min_free_vram_mib()` and enforced by
`KnowledgeProvider.preflight()` before any provider call. When
`preflight()` raises `ProviderNotReady`:

- `GET /api/knowledge/search` and `POST /api/knowledge/refresh` both
  return HTTP 503 with the readiness reason as the detail.
- In `refresh`, the provider is resolved and preflighted before the
  indexer runs and before the manifest is rewritten, so a busy GPU costs
  no repository scan and overwrites nothing.
- The Prompt Compiler path (`retrieve_for_context`) logs the reason at
  ERROR, writes no `knowledge_retrieval_log` row, and returns `None` so
  the compiled context stays byte-for-byte unchanged.

Operator rule: never set `enabled = true` while a resident local model
(FreeToken, Ollama, llama.cpp) holds the GPU.
