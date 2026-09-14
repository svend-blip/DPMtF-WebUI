# Knowledge Retrieval

DPMtF is a client of the standalone knowledge service. DPMtF keeps only its
client: retrieval, refresh, indexing, grants and the scope guard all live in
the service, not in this checkout.

## The service

The service runs as the systemd user unit `knowledge-service.service` at
`http://127.0.0.1:9140`. Its contract endpoints are `/v1/search`,
`/v1/refresh`, `/v1/scopes`, `/v1/scope-for-path`, and `/v1/health`.

## Configuration

The `[knowledge]` section of `dpmtf.ini` carries these keys, all read by
`config.py`:

| key | meaning | default |
|---|---|---|
| `enabled` | master switch for knowledge retrieval | `false` |
| `scope` | scope of this checkout's own knowledge | `dpmtf-webui` |
| `top_k` | number of results returned per search | `8` |
| `max_context_tokens` | token budget for the injected knowledge block | `12000` |
| `max_document_chars` | maximum characters kept from one document | `20000` |
| `service_url` | base URL of the standalone knowledge service | `http://127.0.0.1:9140` |

When the service requires a token, set the `KNOWLEDGE_SERVICE_TOKEN`
environment variable; `config.get_knowledge_service_token()` reads it, and
the client sends it as the `X-Knowledge-Token` header whenever it is
non-empty.

## Client paths

- `knowledge/service_client.py` is the only module in DPMtF that talks to
  the service. It is stdlib-only and every public function returns
  `(status, payload)` without raising; a transport failure returns
  `(0, {"detail": <text>})`.
- `knowledge/retrieval.py` is the single entry point the Prompt Compiler
  calls (`retrieve_for_context`). When `enabled` is false it returns `None`
  before the service is called, so the compiled context stays byte-for-byte
  unchanged.
- `routers/knowledge.py` exposes `GET /api/knowledge/search` and
  `POST /api/knowledge/refresh`. Both are pure proxies: they forward to the
  service and pass its HTTP status and body back unchanged. A transport
  failure (status 0) becomes a `502`.

## Local responsibilities DPMtF keeps

Two responsibilities stay in this checkout; everything else is the
service's.

### Compiler log row

Every retrieval that reaches the service writes one local
`knowledge_retrieval_log` row through `knowledge/retrieval_log.py`
(`record_retrieval`, parameterized SQL only). The row records provider
`service:<provider>`, the resolved scope, the query, result count and token
count, duration, and the agent/run/handoff ids, plus the `flow_key` so the
local audit trail can be joined to the flow that triggered the retrieval.
Logging failures are reported and never break compilation.

### Slug rule

`knowledge/scopes.py` keeps the compiler's deterministic scope binding
locally as one pure function with no network access. `scope_for_target`
returns the lowercased final directory name with trailing slashes stripped
(`/home/x/FlowRunner/` → `flowrunner`); an empty result falls back to the
configured scope. The duplication with the service's `/v1/scope-for-path`
endpoint is accepted and documented; the local copy exists so scope
resolution works at compile time without a service round-trip.

## Grants

Service access grants are managed with the service's own CLI,
`knowledge_service.cli grant|revoke` — not with DPMtF migrations.

## Refresh

`POST /api/knowledge/refresh` forwards `{"scope": "<name>",
"repo_path": "<existing dir>"}` to the service. The service owns the refresh
work and its response is passed back to the caller unchanged; the service's
daily timer replaces the former ecosystem refresh script.
