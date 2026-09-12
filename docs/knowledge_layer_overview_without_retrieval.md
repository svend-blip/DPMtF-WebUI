# Knowledge Layer Overview (Without Retrieval)

This document is a concise en-US overview of the DPMtF knowledge layer as it
exists in this checkout, written by reading the code directly. It covers the
seven areas named by the run's goal: the provider interface, the repository
indexer, the LEANN adapter, the search API, the retrieval-before-exploration
injection, the evaluation harness and metric collector, and the maintenance
and scope-isolation rules delivered by runs 008 and 009. Each area names its
file paths and the public functions or CLI it exposes. Nothing is described
here that the code does not contain.

The knowledge layer is disabled by default. The configuration helpers
`config.get_knowledge_enabled` and `config.get_knowledge_provider` determine
whether retrieval is active; when disabled, or when the configured provider
is `none`, the layer performs no retrieval work and the compiled context
stays byte-for-byte unchanged. The default provider is the no-op
`NoneProvider`, and all execution code depends on the provider-neutral
interface in `knowledge/provider.py`.

## 1. Provider interface — `knowledge/provider.py`

`knowledge/provider.py` defines the provider-neutral retrieval interface. It
is deliberately small so a future retrieval backend can be added behind it
without redesigning flows.

- `KnowledgeProvider` is an abstract base class with four abstract methods:
  `index()`, `update()`, `remove()`, and `search()`.
- `index()` indexes the given source into the knowledge store; `update()`
  updates previously indexed knowledge for the given source; `remove()`
  removes the given source from the knowledge store.
- `search()` returns knowledge results relevant to a query. Its signature
  takes `query` positionally and keyword-only `scope`, `filters`, `top_k`,
  and `token_budget`, and returns a list.
- `NoneProvider` is the no-op implementation of the same interface:
  `index()`, `update()`, and `remove()` return `None`, and `search()`
  returns an empty list. It is the provider used when retrieval is disabled.

The package re-exports `KnowledgeProvider` and `NoneProvider` from
`knowledge/__init__.py`, so they are the only names in the package's public
surface.

## 2. Repository indexer — `knowledge/indexer.py`

`knowledge/indexer.py` scans one repository read-only and writes a JSONL
manifest of indexable documents. The indexer's own code never writes into the
`--repo` target; the only write it performs is the manifest at the
caller-supplied `--out` path.

- `RepoExclusionError` is raised when repository-specific exclusions cannot
  be loaded.
- `_load_repo_exclusions()` loads the enabled `knowledge_exclusions` rows for
  a scope from the configured database, read-only. It inspects the table
  schema before querying, and a missing table or required column is a hard
  error rather than a silent skip.
- `_iter_documents()` walks a repository and yields
  `(relative_path, content, size_bytes)` triples for indexable files. It
  skips default exclusions (such as `.git`, `.env`, `__pycache__`,
  `node_modules`, `venv`, and `.venv`), skips binary/unreadable files, drops
  files whose decoded content carries private-key or secret-assignment
  markers, and applies repository-specific exclusions loaded for the scope.
- `main()` builds the CLI and returns 0 on success. Required flags are
  `--repo`, `--scope`, and `--out`. Each manifest record is a JSON object
  with the fields `scope`, `path`, `content`, `size_bytes`, and
  `indexed_at`. The summary line is printed to stderr, and the CLI refuses
  an `--out` path that is inside `--repo`.

Read-only-safe invocation:

```
venv/bin/python -m knowledge.indexer --repo <path> --scope <name> --out <file>
```

## 3. LEANN adapter — `knowledge/leann_provider.py`

`knowledge/leann_provider.py` is the only place in the package where
LEANN-specific names may appear. The optional `leann` dependency is imported
lazily so importing this module never puts `leann` into `sys.modules`.

- `LeannProvider` is a `KnowledgeProvider` subclass backed by the optional
  `leann` package. Its constructor accepts keyword-only `backend_name`
  (default `hnsw`), `embedding_model` (default `facebook/contriever`),
  `index_path`, `backend_kwargs`, and `searcher_kwargs`.
- `_import_leann()` imports and caches the optional `leann` package on first
  use. If LEANN is not installed, it raises a clear en-US `ImportError`.
- `index()` reads the JSONL manifest at the source path record by record,
  hands each record's `content` to a fresh LEANN builder, and builds the
  index next to the manifest as `<manifest>.leann` unless an `index_path`
  was supplied.
- `update()` and `remove()` delegate to the `ivf` backend only when `ivf` is
  registered in `leann.BACKEND_REGISTRY`; otherwise they raise
  `NotImplementedError` instead of faking success, because the installed
  `hnsw` and `diskann` backends cannot replace or remove previously indexed
  passages.
- `search()` queries the active LEANN index and returns a list of dicts with
  at least `path` and `content`, plus `score` and `scope` when available.
  `top_k` bounds the number of results (the default when it is `None` is
  LEANN's own default of 5), and `token_budget` bounds the total
  whitespace-split token count of the returned content, truncating the last
  included snippet to fit without adding padding.

Private helpers read and cited exactly: `_new_builder()`,
`_resolve_index_path()`, `_read_manifest()`, `_passage_id()`,
`_metadata_for()`, `_passage_ids()`, `_build_metadata_filters()`,
`_map_hit()`, and `_apply_token_budget()`.

## 4. Search API — `knowledge/search.py` and `routers/knowledge.py`

Provider resolution lives in `knowledge/search.py` so the API router can stay
free of any concrete provider name.

- `PROVIDER_LOADERS` maps the configured provider keys `none` and `leann` to
  zero-argument loaders returning the provider class.
- `_load_leann_provider()` imports and returns `LeannProvider` on first use,
  keeping the LEANN import lazy.
- `resolve_provider()` returns the provider class for a configured provider
  key. `none` and any unknown key resolve to `NoneProvider`, so a
  misconfigured provider key never raises and never takes the API down.

`routers/knowledge.py` exposes the search endpoint.

- `GET /api/knowledge/search` is implemented by `search_knowledge()`. In
  disabled mode (knowledge disabled or provider `none`) it returns the stable
  envelope `{"enabled": false, "provider": <key>, "results": [], "bounded":
  true}` and writes no log row. In enabled mode it resolves the configured
  provider, runs the search, clamps `top_k` and `token_budget` to the
  configured ceilings (a caller may lower them but never raise them), and
  defensively truncates the returned list to `top_k`.
- `require_scope_access()` from `knowledge/scope_guard.py` is checked before
  searching; a `ScopeAccessDenied` becomes an HTTP 403.
- `_record_retrieval()` appends one `knowledge_retrieval_log` row for a real
  retrieval using parameterized SQL with `?` placeholders only, and a
  database failure is surfaced to the caller as a 500.

## 5. Retrieval-before-exploration injection — `knowledge/retrieval.py` and `routers/prompt_compiler.py`

`knowledge/retrieval.py` is the single entry point the Prompt Compiler calls
when it needs a bounded, clearly marked supplemental knowledge block.

- `retrieve_for_context()` returns a bounded, marked supplemental block, or
  `None` when retrieval is disabled, the configured provider is `none`, scope
  access is denied, or there are no results. Disabled mode returns `None`
  before any provider is resolved or called.
- `_render_block()` renders the block in plain en-US text, wrapped in the
  fixed `<supplemental_knowledge>` markers with one `<knowledge_result>` per
  result and a fixed non-override sentence stating that retrieved knowledge
  is supplemental context only and never overrides `GOAL.md`, governance,
  approved architecture, or the current handoff.
- `_fit_block_to_budget()` drops trailing results until the rendered block
  fits the configured token budget, truncating a single remaining result's
  content if needed, and returns `None` if even the wrapper alone exceeds the
  budget.

`routers/prompt_compiler.py` injects the block below every authoritative
section of the compiled prompt.

- `_append_retrieval_block()` appends the supplemental block to the compiled
  `lines` only when `config.get_knowledge_enabled` is true; otherwise it
  leaves `lines` byte-for-byte unchanged. `_append_retrieval_block()` is
  called twice from `compile_prompt` (`POST /api/prompt-compiler/compile`) —
  once in the `standard` + BridgeV002 branch (line 380) and once in the
  legacy / accelerated / no-flow branch (line 507) — each time immediately
  after the authoritative sections have been assembled and before
  `prompt = "\n".join(lines)`.
  `POST /api/prompt-compiler/dispatch` does not inject retrieval.
- The same router also defines three UI-label helpers.
  `get_ui_labels_for_domain()` resolves labels for a domain through the
  four-layer i18n architecture and is called by
  `GET /api/ui-labels/{label_domain}` (line 168). `_resolve_ui_label_text()`
  resolves translated text for a single label row with the fallback chain,
  and `_load_knowledge_fragment()` loads and cleans a knowledge fragment
  file; both are defined in the module (lines 66 and 107) and are not called
  anywhere in this checkout.

## 6. Evaluation harness and metric collector — `scripts/knowledge_eval.py` and `knowledge/run_metrics.py`

`scripts/knowledge_eval.py` is the knowledge evaluation harness.

- CLI: `venv/bin/python scripts/knowledge_eval.py`, with optional
  `--with-run <dir>` and `--without-run <dir>`. `main(argv=None)` returns 0
  on success.
- With no flags, it opens the configured SQLite database read-only, counts
  `knowledge_retrieval_log` rows with `_count_retrieval_events()`, and prints
  the fixed comparison report for the `with_retrieval` and
  `without_retrieval` arms with the six canonical metric headings.
- With `--with-run`/`--without-run`, each arm is rendered from
  `collect_run_metrics()` for the supplied run directories; a missing flag or
  unreadable directory renders that arm as the all-zero state.
- Helpers: `_open_readonly()`, `_available_execution_columns()`,
  `_metric_values()`, `_print_report()`, and `_print_run_report()`.

`knowledge/run_metrics.py` is the read-only metric collector.

- `collect_run_metrics()` collects the six canonical metrics from a run
  directory: `tool_calls`, `tokens`, `time_to_first_implementation`,
  `total_execution_time`, `review_failures`, and `rework`. It reads
  `RUN-LEDGER.md` timestamps, counts REJECTED verdict files under
  `verdicts/`, and reports tool-call/token numbers only from an explicit
  `metrics.json`. It opens nothing for writing and never creates files.

## 7. Maintenance and scope isolation — `knowledge/maintenance.py`, `knowledge/scope_guard.py`, and `scripts/db/109_knowledge_scope_grants.sql`

Run 008 delivered the maintenance rules in `knowledge/maintenance.py` and run
009 delivered the scope-isolation rules in `knowledge/scope_guard.py` plus
the grant-table migration.

`knowledge/maintenance.py` compares a repository tree against the last JSONL
manifest emitted by the indexer and reports whether re-indexing is needed.

- `MaintenancePlan` is a dataclass with `status` (one of `noop`, `changed`,
  or `missing`), `changed_paths`, and `removed_paths`.
- `detect_changes()` reuses the indexer's exclusion loading and document walk
  so the maintenance scan sees exactly the files a fresh index would see. A
  missing manifest reports `missing`; otherwise it reports `noop` or
  `changed` with sorted path lists.
- `record_index()` upserts one `knowledge_indexes` row for a scope using
  parameterized SQL; the scope's UNIQUE constraint makes a repeated call an
  update instead of a duplicate row.
- `probe_provider_capabilities()` probes a provider's index, update, and
  remove support through the provider-neutral interface only, resolving the
  provider via `resolve_provider()` and treating `NotImplementedError` as
  "not supported".
- `main()` is the CLI. It accepts `--repo`, `--scope`, `--manifest`,
  `--record-index`, `--provider`, `--location`, `--document-count`, and
  `--probe-provider <key>`.

`knowledge/scope_guard.py` enforces repository boundaries at the knowledge
layer rather than assuming the provider enforces them.

- `ScopeAccessDenied` is raised when access to an internal knowledge scope is
  denied; its message carries the exact denied triple.
- `is_internal_scope()` returns true only for `dpmtf` or strings beginning
  with `dpmtf-`; anything else (including `None`) is not internal.
- `can_access_scope()` allows every non-internal scope without touching the
  database. Internal scopes require an explicit, exact-match grant row in the
  `knowledge_scope_grants` table; a missing or unreadable database means no
  grants exist, so access is denied and no database file is ever created.
- `require_scope_access()` raises `ScopeAccessDenied` when the triple may not
  be read, and otherwise does nothing.

The grant table itself is created by
`scripts/db/109_knowledge_scope_grants.sql`. It creates one table,
`knowledge_scope_grants`, with a UNIQUE constraint over
`(scope, agent_role, flow_key)`. `agent_role` and `flow_key` are nullable on
purpose: a stored NULL is an exact-match value, never a wildcard, which is
default-deny expressed in storage. Grants are maintained with plain SQL by
the operator.

## Verified against

Every file read for this overview, with the exact function names cited:

- `knowledge/provider.py` — `KnowledgeProvider`, `NoneProvider`, `index()`,
  `update()`, `remove()`, `search()`
- `knowledge/__init__.py` — package re-exports of `KnowledgeProvider` and
  `NoneProvider`
- `knowledge/indexer.py` — `RepoExclusionError`, `_fail()`,
  `_default_name_excluded()`, `_contains_secret_markers()`,
  `_load_repo_exclusions()`, `_matches_repo_exclusion()`, `_iter_documents()`,
  `main()`
- `knowledge/leann_provider.py` — `LeannProvider`, `_import_leann()`,
  `index()`, `update()`, `remove()`, `search()`, `_new_builder()`,
  `_resolve_index_path()`, `_read_manifest()`, `_passage_id()`,
  `_metadata_for()`, `_passage_ids()`, `_build_metadata_filters()`,
  `_map_hit()`, `_apply_token_budget()`
- `knowledge/search.py` — `PROVIDER_LOADERS`, `_load_leann_provider()`,
  `resolve_provider()`
- `routers/knowledge.py` — `_record_retrieval()`, `search_knowledge()`
- `knowledge/retrieval.py` — `retrieve_for_context()`, `_render_block()`,
  `_fit_block_to_budget()`
- `routers/prompt_compiler.py` — `_resolve_ui_label_text()`,
  `get_ui_labels_for_domain()`, `_load_knowledge_fragment()`,
  `_append_retrieval_block()`
- `scripts/knowledge_eval.py` — `_open_readonly()`,
  `_count_retrieval_events()`, `_available_execution_columns()`,
  `_metric_values()`, `_print_report()`, `_print_run_report()`, `main()`
- `knowledge/run_metrics.py` — `collect_run_metrics()`, `_parse_timestamp()`,
  `_read_ledger_text()`, `_ledger_timestamps()`, `_first_cycle1_timestamp()`,
  `_line_declares_rejected()`, `_count_rejected_verdicts()`,
  `_metrics_payload()`, `_non_negative_int()`
- `knowledge/maintenance.py` — `MaintenancePlan`, `_fail()`,
  `_read_manifest_mapping()`, `detect_changes()`, `record_index()`,
  `probe_provider_capabilities()`, `main()`
- `knowledge/scope_guard.py` — `ScopeAccessDenied`, `is_internal_scope()`,
  `can_access_scope()`, `require_scope_access()`
- `scripts/db/109_knowledge_scope_grants.sql` — migration that creates the
  `knowledge_scope_grants` table
- `config.py` — consulted for the configuration helpers referenced in prose:
  `get_knowledge_enabled`, `get_knowledge_provider`, `get_knowledge_top_k`,
  `get_knowledge_max_context_tokens`, `get_knowledge_index_dir`
