# Knowledge Layer Overview

> Language: en-US. This document describes the DPMtF knowledge layer as it
> exists in this checkout after run 037 removed the in-process knowledge
> path. DPMtF is now a client of the standalone knowledge service. Nothing
> is described here as present in this repository unless the file named
> exists there.

## The split after run 037

Run 037 removed the in-process knowledge path from this checkout. What
remains in DPMtF is a thin client: a stdlib HTTP client, the compiler-side
retrieval path, a deterministic scope helper, one local retrieval-log row,
two pure proxy routes, and the read-only evaluation harness and metric
collector. The provider, the indexer, the maintenance loop, the scope
guard, the grants, and the learning stores live in the standalone service;
DPMtF never imports or runs them. This document describes both sides of
that split.

## What DPMtF holds

### The service client

`knowledge/service_client.py` is the only module in this checkout that
talks to the knowledge service. It is stdlib-only (`urllib` plus `config`
getters), and every public function returns `(status, payload)` without
raising. It exposes three service calls:

- `search(...)` — `GET /v1/search` with the query, scope, `top_k`,
  `token_budget`, and the agent/run/handoff/flow ids.
- `refresh(scope, repo_path)` — `POST /v1/refresh`.
- `health()` — `GET /v1/health`.

The client sends the `X-Knowledge-Token` header only when
`config.get_knowledge_service_token()` is non-empty. A transport failure is
returned as `(0, {"detail": <text>})`, never raised; an HTTP error status
(including 400/403/503) is returned with its decoded body, and an
undecodable body is returned as `{"detail": <text>}`.

### The compiler's three-scope injection and its split

`knowledge/retrieval.py` is the single entry point the Prompt Compiler
calls (`retrieve_for_context`). It renders one bounded, clearly marked
`<supplemental_knowledge>` block of plain en-US text, which
`routers/prompt_compiler.py::_append_retrieval_block` appends below every
authoritative section of the compiled prompt. The block is supplemental
only and never overrides `GOAL.md`, governance, approved architecture, or
the current handoff.

Since run 038, when `[knowledge] cross_repo` is true (the default), one
`retrieve_for_context` call performs three searches through the service:

1. the caller's repository scope (the `scope` argument),
2. the `ecosystem` learning scope,
3. the `experience` learning scope.

The context budget (`config.get_knowledge_max_context_tokens()`) is split
60 % to the repository scope and 20 % to each learning scope. The two
learning scopes are searched and fitted first, and whatever budget they
leave unused flows to the repository scope. `top_k` applies per scope, and
the rendered block lists results in repository → ecosystem → experience
order, with each result carrying its `source:` line and a `scope:` line.
Set `cross_repo = false` to restrict retrieval to the repository scope
only.

When retrieval is disabled (`config.get_knowledge_enabled()` false),
`retrieve_for_context` returns `None` before the service is called, so the
compiled context stays byte-for-byte unchanged. Every search that reaches
the service writes exactly one local `knowledge_retrieval_log` row (see
below); a retrieval failure is logged at ERROR and the prompt is returned
unchanged.

### The local retrieval-log row

`knowledge/retrieval_log.py::record_retrieval` is the single writer of the
append-only `knowledge_retrieval_log` table. This is the one audit record
DPMtF keeps locally. Each real provider call writes one row with
parameterized SQL only, recording:

- the provider as `service:<provider>` — the provider name comes back from
  the service's response envelope,
- the resolved scope and the query,
- the result count, the JSON-encoded result paths, and the summed
  whitespace-split token count of the result content,
- the retrieval duration, and the `agent_role`, `run_id`, `handoff_id` and
  `flow_key` of the retrieval.

`flow_key` is recorded when the column exists (migration 114 onward), so
the local audit trail can be joined to the flow that triggered the
retrieval. A database failure on this path is surfaced as an HTTP 500
rather than swallowed; logging failures during compilation are reported at
ERROR and never break compilation.

### The slug rule

`knowledge/scopes.py::scope_for_target` keeps the deterministic scope
binding locally as one pure function with no network access. It strips
trailing slashes, takes the final path component, and lowercases it:
`/home/x/FlowRunner/` → `flowrunner`, `/home/x/AI_AdvisoryBoard` →
`ai_advisoryboard`. An empty path (or one whose final component is empty
after stripping) returns `config.get_knowledge_scope()`, which defaults to
`dpmtf-webui`. `scope_for_flow` resolves a flow's target through the bridge
library and applies the same rule, falling back to the configured scope
when there is no flow, no database, no flow row, or no target on disk.

### The proxy routes

`routers/knowledge.py` exposes exactly two endpoints under
`/api/knowledge`:

- `GET /api/knowledge/search` — forwards a search to the service.
- `POST /api/knowledge/refresh` — forwards a refresh request.

Both are pure pass-through proxies: they call `knowledge/service_client.py`
and pass the service's HTTP status and body back unchanged. A transport
failure (status `0`) is converted to a `502` with the service's detail
message. The router has no local provider, indexer, scope guard, or
maintenance branch of its own.

### Evaluation harness and metric collector

`scripts/knowledge_eval.py` is the with-vs-without retrieval evaluation
harness. With `--with-run <dir>` / `--without-run <dir>` it renders each
arm from `knowledge/run_metrics.py::collect_run_metrics`; with no flags it
prints the fixed database-backed empty-state report. Either way it prints
the two arms plus the `commissioning_procedure` prose that tells the
supervising session how to commission the same-task comparison.

`knowledge/run_metrics.py` is the read-only metric collector. It reads a
run directory and returns the six canonical metric keys:

`tool_calls`, `tokens`, `time_to_first_implementation`,
`total_execution_time`, `review_failures`, `rework`.

The two durations come from ISO-8601 timestamps in `RUN-LEDGER.md`,
`review_failures` counts REJECTED verdict files under `verdicts/`, `rework`
counts corrective handoffs, and `tool_calls`/`tokens` are read only from an
explicit `metrics.json` in the run directory. Missing or unreadable sources
are the zero state, never a crash; the module opens nothing for writing.

### Grants are the service's

Scope grants are owned by the service, not by DPMtF. DPMtF performs no
grant check locally: the service's scope guard decides whether an internal
scope may be read, and grants are managed with the service's own CLI.
DPMtF's part is only to pass the requested scope and the agent identity
through to the service on each search.

### Learning drafts (run 039)

Run 039 split learning the same way. At the close of a run, the execution
decomposer authors one schema-valid `LEARNING-DRAFT.yaml` in the run
directory (`docs/LEARNING-ARTIFACT.md` defines its fifteen keys); the draft
is a proposal, not an admission. The resident supervisor admits, edits or
rejects it. DPMtF never calls the learning service directly: the draft is
authored DPMtF-side, and admission is the service's act.

## What lives in the service

The standalone knowledge service owns everything DPMtF no longer runs:

- the **provider** — the retrieval backend that answers search requests;
- the **indexer** — the repository scan and manifest builder that turns
  documents into the index the provider searches;
- the **maintenance loop** — the change detection and re-index scheduling
  that keeps each scope's index current;
- the **scope guard** — the access check that grants or denies internal
  scopes against the service's grant store;
- the **learning stores** — the `ecosystem` and `experience` scope storage
  plus the admission, retraction and supersede logic for learning
  artifacts.

DPMtF reaches all of these only through the service's HTTP contract
(`/v1/search`, `/v1/refresh`, `/v1/scopes`, `/v1/scope-for-path`,
`/v1/health`), never by importing their code.

## Verified against

The DPMtF side of this document was written by reading these files in this
checkout:

- `knowledge/service_client.py` — `_http`, `_service_call`, `search`,
  `refresh`, `health`.
- `knowledge/retrieval.py` — `retrieve_for_context`, `_repository_results`,
  `_learning_results`, `_retrieve_cross_repo`, `_render_block`,
  `_fit_results_to_budget`, `_fit_scoped_results`, `_fit_block_to_budget`.
- `knowledge/retrieval_log.py` — `record_retrieval`.
- `knowledge/scopes.py` — `scope_for_target`, `scope_for_flow`.
- `knowledge/run_metrics.py` — `collect_run_metrics`.
- `routers/knowledge.py` — `search_knowledge`, `refresh_knowledge`,
  `_proxy_response`.
- `routers/prompt_compiler.py` — `_append_retrieval_block`.
- `scripts/knowledge_eval.py` — `main`, `_print_report`, `_print_run_report`,
  `COMMISSIONING_PROCEDURE`.
- `config.py` — the `[knowledge]` getters referenced in prose.
- `docs/LEARNING-ARTIFACT.md` and
  `docs/SCOPE-ADDENDUM-KNOWLEDGE-2-VALIDATED-LEARNING.md` — the run 039
  learning-draft contract.
