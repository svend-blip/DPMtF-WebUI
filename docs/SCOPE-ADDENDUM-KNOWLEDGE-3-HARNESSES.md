# SCOPE Addendum 3 — Knowledge-Aware Harnesses and FlowApps, including DeepSeek Harness (revised 2026-09-14)

## Purpose

Extend the Knowledge Provider concept beyond DPMtF without coupling any
other repository to LEANN. Applies to simple-harness, FlowRunner, exported
FlowApps and **DeepSeek Harness (DSH)**. Harness Allocator MAY later expose
knowledge capabilities as routing metadata. Model Allocator is explicitly
excluded from semantic knowledge responsibilities (it owns the VRAM reserve
for embedding workloads, nothing more).

Human decision 2026-09-14 **[D4]**: the knowledge layer becomes a standalone
component with its own HTTP contract; DPMtF becomes one client among
several. That decision splits this addendum into two parts with different
timing.

---

# Part A — the standalone knowledge service (before addendum 2)

## A.1 Extraction

Move the knowledge layer out of DPMtF into its own repository
(`knowledge-service`, Python, FastAPI, same dependency set), keeping the
provider abstraction (`none`, `leann`, future providers), the indexer, the
maintenance routine, the scope rules, the scope guard, the retrieval log and
the preflight. DPMtF keeps only its client: the compiler's injection, the
grants table's ownership, and the two `/api/knowledge/*` routes as thin
proxies for one release, then removed.

Sequencing (Human decision 2026-09-14): addendum 1 → Part A → addendum 2 →
Part B. Doing addendum 2 inside DPMtF first would move its code twice.

## A.2 HTTP contract (the provider-neutral interface every client uses)

```text
GET  /v1/search      q, scope, top_k, token_budget, agent_role, flow_key, evidence_level, include_history
POST /v1/refresh     {scope, repo_path}
GET  /v1/scopes      the known scopes with document counts and last refresh
GET  /v1/scope-for-path?path=…   the slug rule, so no client duplicates it
GET  /v1/health      provider, preflight state, free VRAM
```

Responses keep today's shapes (`enabled`, `provider`, `results[{path,
content, score, scope}]`, `bounded`; 403 with `detail` on a denied scope; 503
on a provider that is not ready). Authentication: none on localhost; a
shared token header for Tailscale exposure. The contract is versioned and
frozen before Part B starts.

## A.3 Operations

One systemd user unit, one config file (`knowledge.ini`) carrying what
`[knowledge]` in `dpmtf.ini` carries today, the index directory outside
every repository, a scheduled refresh (timer, daily, only when the
preflight passes), and the GPU rules from addendum 1 §11 unchanged.

---

# Part B — clients (after addendum 2)

## B.1 simple-harness

An optional agent tool `knowledge_search(query, scope="current_repository",
top_k=8)` next to read_file, grep, git and shell. The harness consumes the
HTTP contract through mcp-light's `knowledge_search` tool (DSH trial 1,
2026-09-14) and never imports LEANN. `current_repository` resolves through
`/v1/scope-for-path` with the harness's workspace. Deterministic tools stay;
retrieval assists navigation, especially for local models.

## B.2 DeepSeek Harness

DSH consumes the same mcp-light tool through its MCP client
(`@deepseek-ai/dsh-mcp-client`, streamable-http to mcp-light), registered in
the web and headless profiles' `cordis.patch.yml` beside scope-mcp. Rules:

- The session workspace maps to a scope by the shared slug rule; a DSH
  session on a foreign workspace searches that repository's public scope.
- A DSH session receives no DPMtF development memory unless a grant names
  its role (`agent_role = "dsh"`); the default is denied, exactly as for any
  other caller of an internal scope.
- scope-mcp stays project state, not knowledge. A DSH skill
  `knowledge-first` MAY call `knowledge_search` at session start as retrieval
  before exploration, and again when a goal changes.
- DSH's own retrieval log rows carry `agent_role = dsh` and the workspace as
  `flow_key`, so its usage is auditable like a chain role's.

## B.3 FlowRunner

Optional Knowledge Providers in the FlowApp manifest:

```yaml
knowledge:
  enabled: true
  providers:
    project:    { type: http, endpoint_env: KNOWLEDGE_URL }   # the service of Part A
    enterprise: { type: onyx, endpoint_env: ONYX_URL }
```

FlowRunner families running simple-harness get retrieval through B.1 with
no FlowRunner change. FlowRunner itself only needs to pass the provider
endpoint(s) into the harness environment and to record retrieval counts in
its run journal. No provider is required for ordinary flows.

## B.4 FlowApps and isolation

An exported FlowApp MAY bundle its own knowledge: a `knowledge/` directory
of documents plus either a bundled sidecar of the Part A service (Linux) or
a connection to a remote one (Windows, Tailscale). Exporting a FlowApp MUST
NOT export DPMtF run history, handoffs, developer observations, other
repository knowledge or ecosystem memory: the export copies only scopes the
manifest names, and the service refuses to serve an internal scope to a
FlowApp client (no grant can be granted from a FlowApp).

## B.5 Harness Allocator

MAY describe `capabilities: {repository_search, semantic_retrieval,
knowledge_provider}` per harness so a flow can pick a knowledge-aware
harness; it never operates an index.

## B.6 Onyx and LEANN

Two provider classes behind the same contract: LEANN for local, private and
embedded knowledge; Onyx for enterprise, permission-aware, multi-source
knowledge. A FlowApp may use both. LEANN stays replaceable; adding Onyx is a
new adapter in the Part A service, not a FlowRunner change.

## B.7 Model Allocator boundary

Model Allocator stays deterministic: model and runtime state, ports, VRAM,
aliases, lifecycle and routing remain structured data and runtime APIs. It
owns the VRAM reserve that lets the embedding workload coexist with a
resident model (2026-09-14: 2.2 GB reserve, 131k KV on the abliterated
Flash-Next), and nothing else knowledge-related.

---

# Platform independence (Human requirement 2026-09-14)

Everything that can be platform-neutral is designed so; only the provider
that computes embeddings is allowed to be platform-specific, and even that
has a portable fallback.

1. **The HTTP contract is the platform boundary.** FlowRunner (Go, Linux and
   Windows), DSH (Node), simple-harness and mcp-light (Python) only ever
   speak HTTP or MCP to the service. None of them imports a provider, torch
   or LEANN. Their only platform code is where they find the endpoint
   (environment variable) and the workspace path they send.
2. **Paths are normalised on the service side.** `/v1/scope-for-path`
   accepts Windows and POSIX paths, strips trailing separators of either
   kind, ignores drive-letter case, and returns the same slug for
   `C:\Projects\FlowRunner\` and `/home/svend/FlowRunner/`. Clients never
   compute the slug themselves (the duplication in DSH trial 1 is removed
   once this route exists).
3. **Two provider tiers behind one interface:**
   - `leann` — the default where its wheels and a CUDA GPU exist (this
     host). Linux-first; Windows support is measured, not assumed.
   - `portable` — a pure-Python provider with no compiled backend: SQLite
     for passages and metadata, `onnxruntime` for a small multilingual
     embedding model, brute-force or `hnswlib`-free cosine search. Slower
     and simpler; it is what a Windows FlowApp or a machine without a GPU
     runs. Same manifests, same scopes, same routes, same tests.
   The provider is chosen per installation in `knowledge.ini`; a FlowApp
   export names which one it bundles.
4. **The service itself is portable:** FastAPI, one config file, no
   systemd assumption in code (the unit files are Linux packaging, the
   Windows packaging is a scheduled task or a FlowRunner-managed child,
   as the FlowRunner desktop already does for its runtime child).
5. **Remote is a first-class deployment.** A Windows client may point at a
   Linux service over Tailscale with the shared-token header instead of
   running a provider locally; the contract does not distinguish the two.
6. **Tests run on both platforms** for everything above the provider
   boundary; provider tests are tagged by platform and skipped, never
   silently green, where a backend is unavailable.

What stays Linux-only for now and is said so: the LEANN provider's
compiled HNSW backend, the GPU preflight (`nvidia-smi`), and the systemd
units. Nothing a client depends on.

---

# Success criteria

Part A:
1. The service answers the five routes with today's response shapes; DPMtF's
   compiler injection works unchanged against it (the smoke test of run 028
   passes with the proxy routes).
2. All ten scopes are served by the service; DPMtF's own `knowledge/`
   package is gone or reduced to the client.
3. A scheduled refresh ran at least once unattended and reported `noop`.

Part B:
4. simple-harness invokes `knowledge_search` through mcp-light against a
   foreign repository and gets sources; a local model uses it before broad
   exploration in one measured run.
5. DeepSeek Harness invokes the same tool on a foreign workspace and is
   refused on `dpmtf-webui` without a grant.
6. FlowRunner passes a provider endpoint into a family's harness and records
   retrieval counts; ordinary flows run with no provider configured.
7. A FlowApp exported with bundled knowledge answers from it and cannot
   reach any internal DPMtF scope.
8. LEANN remains replaceable; an Onyx adapter can be added without touching
   FlowRunner or DSH.
9. The `portable` provider passes the same contract tests as `leann` on a
   Windows machine (the son's PC over Tailscale is the reference), and a
   FlowApp exported with it answers from bundled knowledge there.
