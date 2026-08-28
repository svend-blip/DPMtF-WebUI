# Test Impact Analysis — Architecture Note

> Project-local test policy layer (Run 003).

## Policy layer boundary

The policy layer (`scripts/testing/policy.py`) is the **sole** place where
DPMtF knows which tests belong to which component. Nothing downstream — not the
gate, not the impact analysis, not the symbol or dependency graph modules —
replaces or bypasses it. Its responsibility is limited to:

1. Declaring **what** tests belong to **which** component (via `components` and
   `test_mappings`).
2. Declaring **which files** are high-fanout (via `high_fanout_files`).
3. Declaring **what forces a full regression** (via `full_regression_triggers`).
4. Declaring **component dependencies** (via `component_dependencies`).
5. Declaring the **mandatory smoke test** set (via `mandatory_smoke_tests`).
6. Declaring the **test command** (via `test_command`).

The policy layer knows nothing about **how** test selection works, which flows
or roles consume it, or what analysis is performed on its data. That is the
job of downstream modules.

## DPMtF holds no project-specific mapping

DPMtF itself (the WebUI, the bridge, the decision engine) does **not** maintain
a separate mapping between components and tests. The mapping lives exclusively
in the target repository's `.dpmtf/test-policy.json`. If that file is absent,
the policy loads as empty and downstream analysis degrades to full regression
rather than guessing.

This is intentional: the target repository owns its own test structure, and
DPMtF reads — never writes or caches — that structure.

## OD-1: JSON, stdlib only

The policy file format is **JSON**, read with the Python standard library
(`json` module). `pyyaml` was deliberately excluded because it is imported in
the active interpreter but absent from `requirements.txt`. A future Run may
introduce a YAML reader, but only with its own declared dependency and Human
approval. The parse seam exists internally to make that cost limited to a parser
swap.

## Consumed by

Run 004 onward. This Run delivers the scope ladder, resolution rule table, and
reachability constraints.

## Scope Ladder — Reachability and Resolution Rules

### The Scope Ladder

The scope ladder is the ordered sequence:

```
symbol < file < component < broad < full
```

It is a monotonic escalation chain: deterministic rules may move rightward
(wider) when uncertainty or impact grows, but nothing may move leftward
(narrower). The `planner.py` `SCOPES` tuple encodes this ordering and every
selection path respects it.

### Resolution Rules (Run 004)

The following rules apply in Run 004, as stated in the GOAL:

| Condition | Scope |
|-----------|-------|
| Ordinary source path, known component, with a test mapping | `component` |
| Known component but no test mapping | `broad` |
| Path matching no component | `broad` |
| Path matching a `high_fanout_files` entry | `broad` |
| Path matching a `full_regression_triggers` entry | `full` |
| Critical, configuration, dependency, or test-infrastructure path (as declared by the policy) | `full` |
| An empty policy | `full` |
| Ambiguous component ownership | `full` |
| Any analysis error or unclassifiable input | `broad` or `full` (as the policy directs) |

### Reachability Constraints

- `symbol` and `file` are **valid rungs of the scope ladder** (they exist in
  the `SCOPES` tuple in `scripts/testing/planner.py`) but are **not reachable
  in Run 004**.
- The planner must refuse to emit either rather than pretending it can.
- `symbol` precision requires **changed-symbol detection**, supplied by Run 007.
- `file` precision requires **dependency closure** (transitive file-to-test
  mapping), supplied by Run 008.
- Run 009 opens both rungs once the evidence from Run 007 and Run 008 exists.
- A later reader must not mistake an unreachable rung for an unimplemented one:
  unreachable means the evidence does not yet exist, not that the code is missing.

### `is_exhaustive` Semantics

`is_exhaustive=True` means the runner must run the whole test suite rather than
the individual list produced by the planner. It is always `true` at scope `full`.
    It is also `true` at scope `broad` when the degradation rule applies — that is,
when no component matched any changed path and the fallback is to run the
entire suite.

## Evidence subsystem

The evidence subsystem (`scripts/testing/evidence.py`) is the last piece of the
chain: facts → policy → plan → execution → evidence. Its public API is:

```python
__all__ = ["build_evidence", "write_evidence", "is_stale", "EVIDENCE_SCHEMA_VERSION", "EvidenceError"]
```

`build_evidence` constructs an evidence dict with exactly **nineteen** keys.
Missing or wrong-typed keys raise `EvidenceError`:

| Key | Type | Description |
|-----|------|-------------|
| `schema_version` | `str` | Evidence schema version |
| `generated_at` | `str` | ISO-8601 UTC timestamp |
| `repository` | `str` | Repository path |
| `baseline` | `str` | Resolved baseline or "HEAD" |
| `head_sha` | `str` | Current HEAD commit SHA |
| `worktree_fingerprint` | `str` | 64-char SHA-256 over the sorted change set |
| `changed_files` | `list[str]` | Files changed since baseline |
| `changed_symbols` | `list[str]` | Empty until Run 007; key exists now |
| `affected_components` | `list[str]` | Components impacted by changes |
| `requested_scope` | `str or None` | Scope requested by the caller |
| `resolved_scope` | `str` | Scope chosen by the planner |
| `escalation_reason` | `str` | Reason for scope escalation (empty if none) |
| `selected_tests` | `list[str]` | Individual test paths (empty when exhaustive) |
| `is_exhaustive` | `bool` | Whether the full suite should run |
| `policy_hash` | `str` | Hash of the policy file used |
| `plan_hash` | `str` | Hash of the plan that produced this evidence |
| `test_command` | `list[str]` | Command used to run tests |
| `status` | `str` | One of "PASS", "FAIL", "ERROR" |
| `duration_seconds` | `float` | Execution time, rounded to 2 decimal places |

The `REQUIRED_KEYS` constant (not in `__all__` but part of the schema) lists all
nineteen keys and is used by `_validate_evidence` to enforce completeness.
`EVIDENCE_SCHEMA_VERSION` is a non-empty string.

**The staleness rule:** `is_stale(evidence, repo_root)` returns `True` when
`head_sha` or `worktree_fingerprint` no longer match the repository. Any error
while measuring — missing repo, read failure, subprocess error — returns `True`.
**Stale means stale, and unknown means stale.** A staleness check that cannot
complete must never answer `False`.

`write_evidence(evidence, path)` validates the evidence first (calls
`build_evidence`'s validation), then writes it as JSON to the given path.

**OD-5 status:** The GOAL posed whether evidence should additionally be recorded
in the database so a run's history is queryable. Decision: **deferred**. Not
needed for correctness, so it was not decided in this Run. A future Run may
address it.

**Execution engine** (`scripts/testing/runner.py`) runs a `TestPlan` and produces
an evidence dict. Its public API is:

```python
__all__ = ["run_plan", "RunnerError"]
```

```text
run_plan(repo_root, plan, policy, timeout=None) -> dict   # an evidence dict
    plan.is_exhaustive True  -> run the whole suite, ignoring selected_tests
    plan.is_exhaustive False -> run exactly selected_tests
    test command: policy.test_command, else the repository default
    non-zero exit            -> status "FAIL"
    the command cannot run   -> status "ERROR", never "PASS"
    a selected test that cannot be collected -> status "ERROR"
```

That last line is a measured hazard: five AGRA test files fail to import under
this interpreter for want of `PIL`. A selector that quietly drops an
uncollectable test would report PASS for a suite it never ran.

## Gate integration (Run 006)

### Integration point

`gate-test-impact.py` is registered as a pre-dispatch script via the
`bridge_scripts` table and wired to a single step: `implementer-reviewer`
in the `1000-02-ELOOP` flow. The `dispatch.py` `_run_pre_dispatch_scripts()`
function invokes it automatically before every handoff dispatch on that step,
passing the standard ten CLI fields plus `--mode block`.

The gate resolves the target repository from `--flow-key` via
`bridge_flows.target_project_path`, loads the policy from that repository,
and runs the full test-impact chain (changes → policy → planner → runner →
evidence). Evidence is written under the flow's artifact root
(`/home/svend/flows/1000/artifacts/test-impact/{flow_key}/`), never into the
target working tree.

### Warn-mode rollout

The migration (`scripts/db/085_gate_test_impact.sql`) registers the script
key and appends it to the `implementer-reviewer` step, but does **not**
set `block` mode. The gate runs in warn mode (the default in the
migration), which reports issues and exits 0 — allowing the workspace to
observe the gate's behaviour on real handoffs before trusting it to stop
the chain.

Turning the gate to `block` mode is a separate, explicit Human decision —
not part of this Run's scope.

### What OD-3 would unblock

OD-3 (not delivered in this Run) would address:

- **Accumulated Run-level baselines.** This Run uses `baseline=None`, which
  measures against the working tree / HEAD/index. A future Run could pass
  an explicit baseline SHA so the gate evaluates a stable diff rather than
  the live working tree.
- **Scope ladder expansion.** The `symbol` and `file` rungs of the scope
  ladder are unreachable in this Run. OD-3 (or a successor Run) would supply
  changed-symbol detection and dependency closure, enabling those rungs.
- **Block mode activation.** A future Run could evaluate the warn-mode logs
  and, upon Human approval, flip the gate to `block` mode.

### Flow independence

The engine call in `gate-test-impact.py` uses `get_effective_artifact_root()`
and `get_flow_target_project()` from `bridge_lib.py`, which resolve paths
from the `bridge_flows` table. These lookups are topology-agnostic: the same
code path serves both `1000-01-PLOOP` (continuous) and `1000-02-ELOOP`
(split PLOOP/ELOOP) because both flows share the same target project and
the same policy file. No branching on flow topology is needed or present
in the engine modules under `scripts/testing/`.

## Sentinel contract (Run 007)

### UNKNOWN is a distinct sentinel object

The symbol analysis layer (`scripts/testing/symbol_analysis.py`) exports a
single sentinel:

```python
UNKNOWN: object = object()
```

`UNKNOWN` is a bare `object()` instance — it is **not** an empty list (`[]`),
not `None`, not an empty string (`""`), and not any other falsy or list-like
value. This distinction is the safety property of the entire symbol analysis
layer: any caller that receives `UNKNOWN` can unambiguously determine that
symbol analysis failed rather than "found nothing changed."

An empty list, by contrast, means "the analysis succeeded and no symbols were
touched." Mixing these two outcomes — failure and zero-impact — is the precise
bug this sentinel prevents. The `changed_symbols()` return type is annotated as
`list[str] | object` so that static checkers (and human readers) can see the
sentinel is a deliberate return value, not an oversight.

### Why a language with no registered adapter yields UNKNOWN

The symbol analysis layer implements **OD-2** — an adapter seam for language-
specific parsers. Adapters are registered in `_ADAPTERS`, keyed by file
extension. In Run 007, only the Python adapter (`.py`) is registered, backed
by LibCST.

When `changed_symbols()` receives a file whose extension maps to no registered
adapter — `.js`, `.ts`, `.md`, `.yaml`, or any other extension — the dispatcher
at line 325–328 looks up `_ADAPTERS.get(ext)`, finds `None`, and returns
`UNKNOWN` immediately.

This is the correct behaviour because answering an empty list for an unknown
language would be a **guess**: the system has no parser for that language and
therefore no basis to claim the file contains no changed symbols. An empty list
on failure is a *silent narrow* — it tells the downstream consumer "nothing to
test" when the truth is "we do not know." A silent narrow voids the mandatory
test set, which is the core safety property the scope ladder enforces.

JS and TS adapters are deferred (not delivered in this Run). The seam is built
and tested with Python only; future Runs that add adapters register them against
the same `_ADAPTERS` dict without changing the return contract.

### Downstream propagation

When `changed_symbols()` returns `UNKNOWN`, every downstream consumer must
treat it as **whole-module impact** — not as "nothing changed." Specifically:

- **The planner** must not filter the test set on the strength of a parse
  failure. An `UNKNOWN` result for a changed file means the planner cannot
  determine which symbols were touched, so it must not narrow scope to fewer
  tests than it would for the entire module.
- **The runner** receives the planner's scope decision (which may escalate to
  `broad` or `full` based on `UNKNOWN` inputs) and executes accordingly. It
  must never interpret `UNKNOWN` as a zero-impact signal.
- **The gate** must not suppress the test run when any file in the diff yields
  `UNKNOWN`. The gate's purpose is to widen scope on uncertainty, not narrow it.

In practice, the planner resolves `UNKNOWN` by escalating the scope rung on the
ladder — from `symbol` upward to `file`, `component`, `broad`, or `full`,
depending on which other inputs are available. The escalation is monotonic
(rightward) and conservative: uncertainty always widens, never narrows.

### Reference: symbol_analysis.py

The sentinel is defined and used at:

| Location | Behaviour |
|----------|-----------|
| Line 36 | `UNKNOWN: object = object()` — the sentinel itself |
| Line 214–217 | ParserSyntaxError or any parse exception → `return UNKNOWN` |
| Line 221–222 | Definition collection exception → `return UNKNOWN` |
| Line 236 | No definitions found in valid Python → `return UNKNOWN` |
| Line 316 | File not found → `return UNKNOWN` |
| Line 322 | OSError reading file → `return UNKNOWN` |
| Line 327 | No registered adapter for extension → `return UNKNOWN` |

Every call site returns `UNKNOWN` rather than `[]`, `None`, or any other value
that could be mistaken for a successful zero-impact result.
