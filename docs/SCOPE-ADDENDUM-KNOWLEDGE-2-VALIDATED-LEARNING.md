# SCOPE Addendum 2 — Validated Cross-Repository Ecosystem Memory (revised 2026-09-14)

## Status and dependency

This addendum depends on the Persistent Project and Ecosystem Memory
foundation (addendum 1, runs 001–032 of family 2000) and on the knowledge
layer being a standalone component with an HTTP contract (addendum 3a).
It MUST NOT be implemented before both are closed (Human decision
2026-09-14: the order is addendum 1 → 3A → 2 → 3B).

What the foundation already delivers, so this addendum does not re-plan it:
ten repository scopes (one LEANN store per scope, rebuilt in seconds),
scope resolution from a flow's target project, the scope guard with grants,
the retrieval log, preflight and daemon-free search, change detection that
reports `noop`, and the compiler injecting one bounded block per dispatch.

Human decisions 2026-09-14 are binding and are marked **[D1]–[D4]** below.

---

# 1. Mission

Preserve selected, validated development experience independently from
individual repository history, so that what a run learned while developing
one repository is retrievable when DPMtF later develops another.

```text
Repo A run ──► closed SUCCESS ──► learning artifact ──► experience scope
                                                          │
                                        future Repo A run ┤ Repo B run ┤ Repo C run
```

Autonomous learning is not the goal; auditable, retractable, validated
memory is.

---

# 2. Three memory classes as three kinds of scope

| class | answers | scope(s) | guard |
|---|---|---|---|
| Repository memory | how does this repository work? | the existing per-repository scopes (`dpmtf-webui`, `flowrunner`, …) | as today: internal scopes need a grant |
| Ecosystem memory | how do our repositories work together? | one scope `ecosystem` | public |
| Validated experience | what did previous executions teach us? | one scope `experience` | public, but filtered by evidence level (§4) |

Logical separation is mandatory; physical storage is one LEANN store per
scope under the configured index directory, exactly as the ten repository
scopes today. Ecosystem memory is authored by humans and by learning
artifacts whose `architecture_implications` field is non-empty; it is not
scraped from repositories.

---

# 3. Learning artifacts

A learning artifact is one YAML document per closed run, stored outside every
repository under `<index_dir>/learning/<family>/<run>.yaml`, and ingested by a
dedicated manifest builder (`knowledge/learning.py`) into the `experience`
scope. Schema (all keys required; empty lists allowed):

```yaml
topic: one line
scope: experience
repository: <slug of the target project>
family: 2000
run: 029
problem: what the run set out to change and why
approach: what was actually done
result: what the reviewer verified, with the verdict ids
failed_approaches: [ ... ]        # each with the reason it failed
important_files: [ ... ]          # repository-relative paths
architecture_implications: [ ... ]  # promoted into ecosystem memory when non-empty
validation:
  evidence_level: tests | measured_runtime | approved_architecture | reviewer_conclusion | observation
  verdicts: [ "002 APPROVED", ... ]
  testgoals: "7/7"
confidence: high | medium | low
supersedes: []                    # "family/run" references (§5)
admitted_by: supervisor           # who admitted it, §3.2
```

## 3.1 Author **[D3]**

The execution decomposer drafts the artifact in the END-REPORT cycle, from
the verdicts, the END-REPORT and the testgoal measurements it already holds.
It writes `<run dir>/LEARNING-DRAFT.yaml`. It is admitted to the `experience`
scope only when the run closes SUCCESS; a run closed BLOCKED or FAILED
contributes nothing. The resident supervisor may reject or edit the draft
before admission (a ledger line records either). The Human can retract an
admitted artifact later (§7). A GOAL may carry `learning: none` to prevent
the run from contributing at all.

## 3.2 Admission is mechanical

`knowledge/learning.py admit <family> <run>` copies the draft to
`<index_dir>/learning/…`, validates the schema, refuses any artifact whose
`validation.evidence_level` is `hypothesis` or whose run is not closed
SUCCESS, rewrites the `experience` manifest and rebuilds that one scope.
No model is involved in admission.

---

# 4. Validation is mandatory **[D1]**

Six evidence levels are recognised, from strongest to weakest:

```text
tests                  validated by deterministic tests
measured_runtime       validated by measured runtime behaviour
approved_architecture  approved architecture decision
reviewer_conclusion    accepted reviewer conclusion
observation            implementation observation
hypothesis             agent hypothesis
```

Rules:

- Only artifacts from closed runs with an APPROVED final verdict are admitted.
- Retrieval from `experience` returns, by default, only the three strongest
  levels. `reviewer_conclusion` and `observation` are returned only when the
  caller passes `evidence_level` explicitly (the provider's metadata filter
  carries the level).
- `hypothesis` is never admitted.
- The evidence level is stored in each passage's metadata; retrieval never
  infers it from text.

---

# 5. Knowledge evolution **[D2]**

Knowledge is superseded by editing the manifest and rebuilding the one
affected scope; hnsw cannot delete a passage in place, and a scope rebuild
takes seconds. Concretely: an admitted artifact whose `supersedes` names an
earlier artifact causes the earlier one to be moved from the live manifest
into `<index_dir>/learning/history/`, with a `superseded_by` field written
into it. The live store then holds only the current conclusion. History is
retrievable only when a caller asks for it explicitly
(`include_history=true`), which searches a separate `experience-history`
store built from that directory.

Example: run 021 recorded "Runtime X appears not to support Y" as an
observation; run 044 measures that X supports Y after configuration Z.
Run 044's artifact names `supersedes: ["9000/021"]`; after admission a
default search returns only run 044's conclusion.

---

# 6. Cross-repository retrieval

The compiler and the `knowledge_search` tool search, by default:

```text
current repository scope  +  ecosystem  +  experience
```

with one budget split explicitly: 60 % of `max_context_tokens` to the
repository scope, 20 % to ecosystem, 20 % to experience; unused share flows
to the repository scope. Other repository scopes are searched only when the
GOAL or the caller names them. Every search of a foreign scope is logged
with the requesting role, run and handoff, as today.

---

# 7. Human control

The operator can, without a chain run: disable ecosystem and experience
retrieval (`knowledge.cross_repo = false`), restrict retrieval to the
current repository, list what a given run retrieved (retrieval log), list
admitted artifacts, retract one (`learning.py retract <family> <run>`, which
moves it to history and rebuilds), supersede one by hand, and mark a GOAL
`learning: none`. Every admission, retraction and supersede is a ledger line
in the family's backlog.

---

# 8. Platform note

Learning artifacts are plain YAML with repository-relative, forward-slash
paths in `important_files`; the `experience` and `ecosystem` scopes are
ordinary scopes of the standalone service (addendum 3 Part A) and therefore
work on any provider, including the portable one. Nothing in this addendum
assumes Linux, a GPU, or LEANN.

# 9. Sequencing and non-goals

- Depends on addendum 3a (standalone knowledge service). The learning
  manifest builder, admission and history stores are service-side; the
  decomposer's draft and the supervisor's admission are DPMtF-side.
- Not in scope: automatic extraction from repositories other than through
  closed runs; learning from FlowApps; any Onyx or enterprise source.

---

# 10. Success criteria

1. `experience` and `ecosystem` are separate stores from the repository scopes.
2. A closed SUCCESS run produces a schema-valid learning draft; admission
   refuses drafts from non-SUCCESS runs and from any `hypothesis` level.
3. Evidence level is stored per passage and filters retrieval as in §4.
4. An admitted artifact naming `supersedes` removes the older one from the
   live store and keeps it retrievable as history.
5. A run in one repository retrieves, through the default three-scope
   search, an artifact that originated in another repository.
6. Cross-repository retrieval stays within the split budget and every foreign
   retrieval is in the log.
7. One measured pair (same GOAL, with and without the `experience` scope)
   shows fewer tool calls, tokens or rework — the same instrument as
   addendum 1 criterion 7.
