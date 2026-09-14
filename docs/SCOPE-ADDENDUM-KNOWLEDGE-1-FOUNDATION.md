# SCOPE Addendum — Persistent Project and Ecosystem Memory

## Status

This addendum extends the existing DPMtF scope.

It MUST be planned and implemented only after the currently defined and approved RUNs unless explicitly reprioritized by the human operator.

The purpose of this addendum is not to turn DPMtF into a generic RAG platform.

The purpose is to give DPMtF persistent, searchable memory of the software projects it develops.

LEANN SHALL be evaluated and used as the first retrieval backend where technically appropriate, but DPMtF MUST NOT become architecturally dependent on LEANN.

---

# 1. Mission

Add a persistent knowledge and retrieval layer to DPMtF so that agents can retrieve relevant project knowledge before spending large amounts of context and tool calls exploring repositories.

The system SHOULD allow knowledge accumulated during previous RUNs to improve future RUNs.

The primary objectives are:

* reduce unnecessary repository exploration;
* reduce token consumption;
* reduce repeated tool calls;
* improve local-model effectiveness;
* preserve important project history;
* make previous implementation experience reusable;
* make relevant knowledge available across RUNs;
* eventually make validated knowledge reusable across repositories.

The intended model is:

```text
GOAL
  |
  v
Deterministic DPMtF Context
  |
  +-- governance
  +-- role instructions
  +-- current handoff
  |
  v
Knowledge Retrieval
  |
  +-- current repository
  +-- previous RUNs
  +-- architecture
  +-- validated experience
  |
  v
Agent
```

Semantic retrieval MUST supplement deterministic DPMtF context.

It MUST NOT replace governance, GOAL.md, handoffs, or other authoritative execution artifacts.

---

# 2. Knowledge Provider Abstraction

DPMtF MUST introduce a provider-neutral Knowledge Provider interface.

Conceptually:

```text
Knowledge Provider
    |
    +-- none
    +-- leann
    +-- future providers
```

DPMtF MUST NOT expose LEANN-specific concepts throughout the execution engine.

A minimal logical interface SHOULD support operations equivalent to:

```text
index(source)
update(source)
remove(source)

search(
    query,
    scope,
    filters,
    top_k,
    token_budget
)
```

The exact implementation MAY differ.

The abstraction MUST allow another retrieval engine to replace or supplement LEANN later without redesigning DPMtF flows.

---

# 3. First Backend: LEANN

LEANN SHOULD be evaluated as the first Knowledge Provider backend.

The initial implementation SHOULD focus on local project/repository retrieval.

Candidate indexed content includes:

```text
source code
SCOPE.md
GOAL.md
GOAL drafts where useful
handoffs
architecture documentation
design decisions
test results
review findings
RUN summaries
performance measurements
relevant Markdown documentation
```

Generated build artifacts, dependencies, caches, binaries, secrets, temporary files, and other low-value content MUST NOT be indexed by default.

Repository-specific exclusion rules MUST be supported.

---

# 4. Repository Memory

Each repository SHOULD have an independent knowledge scope.

Example:

```text
knowledge/
    dpmtf/
    model-allocator/
    harness-allocator/
    simple-harness/
    flowrunner/
    other-projects/
```

The physical storage layout is implementation-specific.

The logical separation is mandatory.

When DPMtF operates on FlowRunner, retrieval SHOULD initially prioritize FlowRunner knowledge.

When operating on Model Allocator, retrieval SHOULD initially prioritize Model Allocator knowledge.

This prevents unrelated projects from unnecessarily polluting agent context.

---

# 5. Retrieval Before Exploration

DPMtF SHOULD support semantic retrieval before expensive repository exploration.

Example:

```text
GOAL:
Add automatic fallback from a local FreeToken
runtime to an approved cloud runtime.
```

Before an implementation agent begins broad repository exploration, DPMtF MAY retrieve:

```text
relevant runtime code
previous GOALs
existing fallback logic
related tests
architecture decisions
previous reviewer findings
```

Only high-value results SHOULD be injected into agent context.

Retrieval MUST have configurable limits.

Example:

```yaml
knowledge:
  enabled: true

  provider: leann

  retrieval:
    top_k: 8
    max_context_tokens: 12000
```

Exact defaults MUST be determined through measurement rather than assumption.

---

# 6. Deterministic Context Remains Authoritative

Retrieved knowledge is supplemental context.

The authority hierarchy MUST remain explicit.

Conceptually:

```text
AUTHORITATIVE

GOAL.md
governance
approved architecture
current handoff

        ↓

SUPPLEMENTAL

retrieved project knowledge
previous RUNs
historical implementation context
agent observations
```

A semantic search result MUST NOT silently override current governance or an approved GOAL.

---

# 7. Incremental Knowledge Maintenance

DPMtF SHOULD avoid unnecessary full re-indexing.

The LEANN change-detection/watch capabilities SHOULD be evaluated.

Knowledge indexes SHOULD eventually be updated when relevant repository content changes.

Possible triggers include:

```text
successful RUN completion
approved commit
repository checkout
manual refresh
knowledge-relevant artifact creation
```

Incremental indexing capabilities MUST be verified before relying on them architecturally.

---

# 8. Observability

Knowledge retrieval MUST be observable.

For each retrieval operation, DPMtF SHOULD be able to record:

```text
provider
scope
query
number of results
sources returned
retrieved token count
retrieval duration
agent/role requesting retrieval
RUN
handoff
```

This data SHOULD allow comparison between:

```text
execution without retrieval

vs.

execution with retrieval
```

Important measurements include:

```text
tool calls
tokens consumed
time to first implementation
total execution time
review failures
rework
```

The feature MUST be judged by measured benefit rather than retrieval quality alone.

---

# 9. Security and Isolation

Secrets MUST NOT be indexed.

Repository boundaries MUST be respected.

Knowledge access SHOULD eventually support explicit scope permissions.

A FlowApp or external repository MUST NOT automatically receive access to DPMtF internal development memory.

---

# 10. Initial Success Criteria

The first implementation is successful when:

1. DPMtF can build a knowledge index for one selected repository.
2. An agent can semantically search that repository through DPMtF.
3. Results contain usable source references.
4. Retrieval context is bounded by a configurable budget.
5. DPMtF execution works unchanged when knowledge retrieval is disabled.
6. LEANN can be replaced through the Knowledge Provider abstraction.
7. At least one representative RUN demonstrates whether retrieval reduces repository exploration, tool calls, tokens, or execution time.

The initial objective is measurable retrieval assistance.

Autonomous learning is NOT required for the first implementation.
