# GOAL-DRAFT-006 — Retrieval-before-exploration injection into compiled context

> Status: DRAFT (planning artifact — not promoted)
> Depends on: GOAL-DRAFT-001, GOAL-DRAFT-005
> Blocked by: none (real retrieval additionally requires GOAL-DRAFT-004)
> Target repository: DPMtF-WebUI (this checkout)

## Mission

Make the Prompt Compiler consult the knowledge layer before an implementation
agent begins broad repository exploration, and inject only high-value,
bounded, clearly supplemental knowledge into the compiled agent context. When
`knowledge.enabled` is false the compiled context is byte-for-byte unchanged.
Retrieved knowledge never overrides `GOAL.md`, governance, approved
architecture, or the current handoff (addendum §5, §6).

## Standing constraints

- No commits, no pushes, no staging by any chain role (`CLAUDE.md` §5).
- en-US for code and injected text.
- Config values via `config.py` getters; no hardcoded paths or provider
  names.
- The compiled context's authoritative sections stay above any retrieved
  block; the retrieved block is labelled supplemental.
- No new third-party dependencies.
- No LEANN-specific code in the compiler; retrieval goes through the
  provider-neutral service only.

## Scope fence

May modify:

- `routers/prompt_compiler.py`
- `knowledge/retrieval.py` (new service: one retrieval entry point for the
  compiler)
- `tests/test_knowledge_injection.py` (new)

Must not touch:

- `knowledge/provider.py`, `knowledge/leann_provider.py`,
  `knowledge/indexer.py`, `routers/knowledge.py`, `config.py`, `dpmtf.ini`,
  `app.py`, `static/`, `templates/`, `scripts/`, `databases/`
- `.env`, `.git/`, `__pycache__/`
- governance files, `docs/SCOPE-ADDENDUM-KNOWLEDGE.md`, and any handoff,
  result, or verdict files

Non-goals:

- No frontend or API changes in this Run.
- No change to retrieval ranking or logging (GOAL-DRAFT-005 owns that).
- No autonomous learning or knowledge write-back from the agent.

## Dependencies

- GOAL-DRAFT-001: `get_knowledge_enabled`, `get_knowledge_top_k`,
  `get_knowledge_max_context_tokens`, provider selection.
- GOAL-DRAFT-005: the search service and its bounded result shape.
- GOAL-DRAFT-004 is required only for live LEANN results; injection is
  testable with a stub provider before then.

## Work items (handoff budget: 4)

1. Implement `knowledge/retrieval.py` with
   `retrieve_for_context(query, scope, agent_role, run_id, handoff_id)` that
   returns a bounded, marked supplemental block or `None` when disabled.
2. Integrate the call into `routers/prompt_compiler.py` immediately before
   the agent-context assembly, behind `config.get_knowledge_enabled()`, and
   write `tests/test_knowledge_injection.py` proving: disabled = unchanged
   output, enabled stub = supplemental block present below authoritative
   sections, and the token budget is enforced.

Reserve: 2 handoff slots for rework.

## Acceptance criteria (shell commands)

```testgoals
id: TG1
what: prompt compiler and retrieval service compile
run: venv/bin/python -m py_compile routers/prompt_compiler.py knowledge/retrieval.py
expect: exit 0

id: TG2
what: retrieval injection tests pass
run: venv/bin/python -m pytest tests/test_knowledge_injection.py -q
expect: exit 0

id: TG3
what: prompt compiler stays provider-neutral
run: test -f routers/prompt_compiler.py && ! grep -qin 'leann' routers/prompt_compiler.py
expect: exit 0
```

## Reviewer duties

- Confirm the retrieved block is labelled supplemental and appears only below
  authoritative context, never above or replacing it.
- Confirm disabled mode produces byte-identical compiled context and performs
  no retrieval call.
- Confirm the token budget is measured on the injected block, not assumed.
- Confirm no LEANN string or LEANN import appears in the compiler.
- Rehearse under `dash -c`; every criterion must be RED on the current tree
  and cannot pass on an empty repository.
