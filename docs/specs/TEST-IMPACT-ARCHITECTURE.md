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

### Module vs. Symbol Granularity

The test-impact system operates at two distinct granularity levels. The
architecture distinguishes them explicitly because the scope decision depends
on which level is available.

**Symbol-level granularity** answers: "which symbols in which files changed?"
Produced by `scripts/testing/symbol_analysis.py` — it uses LibCST to parse
changed line ranges into qualified symbol names (e.g. `app.views.index`,
`models.User.create`). The result is a set of symbols or the `UNKNOWN`
sentinel when parsing fails.

**Module-level granularity** answers: "which modules depend on which other
modules (and which symbols)?" Produced by `scripts/testing/dependency_graph.py`
— it builds a deterministic AST-based dependency graph from `.py` files,
tracking both module-to-module edges and symbol-to-symbol edges within a
module. The graph supports reverse-closure computation: given a set of seeds,
it returns all nodes transitively affected.

**When each level applies:**

- The planner (`planner.py`) currently operates at **component** level or above
  (component, broad, full). Symbol and file granularities exist in the scope
  ladder but are not yet reached in Run 004+.
- Symbol-level analysis feeds the `changed_symbols` field of the evidence
  schema (19-key record, `scripts/testing/evidence.py`). It is recorded but
  not yet used for scope resolution — `changed_symbols` starts empty and will
  drive finer-grained plans in a future run.
- Module-level analysis via the dependency graph feeds the symbol-level path:
  when symbol analysis yields `UNKNOWN`, the dependency graph can still resolve
  module-level edges. A module that changed triggers all reverse-closure nodes
  (but the planner must not narrow scope below the file level for symbol-UNKNOWN
  results — the scope ladder rule applies).

**The boundary between levels:** symbol_analysis is file-local (it maps changed
lines within a single file to symbols). dependency_graph is repository-wide
(it builds a cross-module edge set). The dependency graph does NOT depend on
symbol_analysis output — it is self-contained, built from AST analysis of all
`.py` files.

### Resolution Rules

The system resolves scope using a deterministic hierarchy. Rules are ordered
by priority and applied top-down; the first match wins. The hierarchy has
two layers: file-level resolution (which policy rules apply) and granularity
resolution (symbol vs. module vs. file vs. component vs. broad vs. full).

**Layer 1 — File-level resolution** (from `planner.py:_resolve_scope_for_change`):

For each changed path, the planner applies these rules in order:

1. **Full regression trigger** — if the path matches any pattern in
   `policy.full_regression_triggers`, scope is `full`. Reason:
   `"path '{path}' matches full_regression_triggers pattern"`.

2. **High fanout escalation** — if the path matches any entry in
   `policy.high_fanout_files`, scope escalates to `broad` regardless of
   component ownership. Reason: `"path '{path}' is a high_fanout_file"`.

3. **Component ownership resolution** — resolve the path against
   `policy.components` (glob matching). If no component claims the path,
   scope is `broad`. Reason: `"path '{path}' has no owning component"`.

4. **Test mapping check** — if a component owns the path:
   - Has test mappings → scope is `component`. Reason:
     `"path '{path}' belongs to component '{comp}' with test mappings"`.
   - No test mappings → scope is `broad`. Reason:
     `"path '{path}' belongs to component '{comp}' but has no test mappings"`.

**Layer 2 — Granularity escalation** (when symbol analysis yields UNKNOWN):

When `symbol_analysis.changed_symbols()` returns `UNKNOWN` for a changed file,
the system must not narrow scope below the file level. The scope ladder
enforces monotonic escalation (rightward only):

```
symbol < file < component < broad < full
```

If symbol-level impact cannot be determined, the planner uses the file-level
or component-level resolution from Layer 1. The `UNKNOWN` sentinel from
symbol_analysis triggers escalation within the granularity axis, while the
Layer 1 rules govern the component axis.

**Layer 3 — Transitive resolution** (dependency graph reverse closure):

For component-level scope, the planner also resolves transitive dependencies:

1. For each affected component, look up `policy.component_dependencies`.
2. Compute reverse dependencies: for each component with changed paths,
   find every component that transitively depends on it (BFS through the
   reverse dependency map).
3. Collect all test mappings from the expanded component set.
4. The `selected_tests` field of the TestPlan includes tests for the
   expanded component set.

**Combining multiple changes:**

When multiple paths change, the planner resolves each independently, then
takes the union of their resolved scopes using `_scope_max()` (which picks
the stronger scope — higher index in `SCOPES`). The final `escalation_reason`
records all individual reasons joined.

### Integration Chain: Complete Data Flow

The five subsystems form a deterministic pipeline. Data flows through in
this order:

```
git_changes.py → symbol_analysis.py ──┐
                                       ├──→ planner.py → runner.py → evidence.py
dependency_graph.py ───────────────────┘
```

**Step 1 — Facts (git_changes.py):**
- `resolve_baseline(repo_root, baseline)` → resolved commit SHA or "HEAD"
- `changed_files(repo_root, baseline)` → list of (status_letter, path) tuples
- `changed_ranges(repo_root, baseline, path)` → list of (start, end) line ranges for each changed file

Output: a dict mapping file paths to change labels (e.g. `{"src/app.py": "modified", "new/module.py": "added"}`).

**Step 2 — Symbol analysis (symbol_analysis.py):**
- `changed_symbols(file_path, source_code, ranges)` → set of qualified symbol names or UNKNOWN
- Uses LibCST with PositionProvider metadata to map line ranges to definition paths
- Handles decorators, nested classes, class methods, and module-level attribute assignments
- One adapter registered for `.py` files; unknown extensions yield UNKNOWN

Output: for each changed file, a set of changed symbols or the UNKNOWN sentinel.

**Step 3 — Dependency graph (dependency_graph.py):**
- `build_graph(root_dir)` → Graph containing all nodes, forward edges, reverse edges, unresolved set
- Parses AST from all `.py` files, tracks imports (static and dynamic), and call targets
- `reverse_closure(graph, seeds)` → Closure containing reachable nodes, unresolved nodes, and is_safe flag
- Handles: star imports (marks importing module unresolved), parse failures (marks file unresolved),
  import cycles (terminates via visited set), dynamic imports (importlib → unresolved)

Output: a Graph that maps modules to their dependencies and a Closure computation that answers
"which modules are transitively affected by these changed nodes?"

**Step 4 — Policy and planning (planner.py):**
- `Policy` loads from `.dpmtf/test-policy.json` — validates top-level keys, maps components to
  source globs, test globs, and dependencies
- `plan_tests(repo_root, policy, changes, requested_scope)` → TestPlan
  - Resolves each changed path through the Layer 1 rules
  - Expands components through transitive dependencies
  - Takes scope union across all changes
  - Computes plan_hash (SHA-256 over canonical JSON serialization)

Output: a TestPlan with resolved_scope, selected_tests, affected_components, escalation_reason,
policy_hash, plan_hash, and is_exhaustive flag.

**Step 5 — Execution (runner.py):**
- `run_plan(repo_root, plan, policy, timeout=None)` → evidence dict
- If plan.is_exhaustive → runs the whole test suite (ignores selected_tests)
- If plan.is_not_exhaustive → runs exactly selected_tests
- Non-zero exit → status "FAIL"
- Command cannot run → status "ERROR", never "PASS"
- Uncollectable selected test → status "ERROR"

Output: an evidence dict with all 19 required keys (schema_version, generated_at, repository,
baseline, head_sha, worktree_fingerprint, changed_files, changed_symbols, affected_components,
requested_scope, resolved_scope, escalation_reason, selected_tests, is_exhaustive, policy_hash,
plan_hash, test_command, status, duration_seconds).

**Step 6 — Staleness check (evidence.py):**
- `is_stale(evidence, repo_root)` → bool
- Compares evidence.head_sha and evidence.worktree_fingerprint against current repo state
- Any error during measurement → True (unknown means stale)
- Never answers False when measurement fails

### Scope Ladder Reference

| Level   | Scope in SCOPES index | When used                                    |
|---------|----------------------|----------------------------------------------|
| symbol  | 0                    | Symbol-level analysis available and safe     |
| file    | 1                    | File-level impact without symbol granularity |
| component | 2                  | Component ownership resolved with test maps  |
| broad   | 3                    | No component, high fanout, or no test maps   |
| full    | 4                    | Full regression trigger matched              |

Monotonic escalation: the scope can only move rightward (higher index).
Nothing moves leftward. `_scope_max(a, b)` returns the scope with the
higher index.

### Reference: dependency_graph.py

The dependency graph builder is the second fact module (after symbol_analysis).
Unlike symbol_analysis, it does NOT use LibCST — it uses Python stdlib `ast`.

Key properties:

| Property         | Detail                                                         |
|------------------|----------------------------------------------------------------|
| Parsing          | stdlib `ast.parse` — no external dependencies                  |
| Edge types       | Module-to-module (imports) and symbol-to-symbol (calls)        |
| Dynamic targets  | `importlib`, `eval`, `setattr`, `globals()` → UNRESOLVED mark  |
| Star imports     | `from a import *` → importing module marked UNRESOLVED         |
| Parse failures   | Syntax error → file node marked UNRESOLVED                     |
| Cycles           | Terminates via visited set (finite closure guaranteed)         |
| Serialization    | `serialize_nodes()` / `serialize_reverse()` — deterministic, sorted |
| Node ID format   | `path` for modules, `path<TAB>symbol` for symbol nodes         |
| Idempotency      | `_add_node()` is idempotent; `_add_edge()` creates both directions |

The dependency graph is **self-contained** — it does not depend on symbol_analysis
output. It is built by scanning all `.py` files in a directory tree. The graph
can be used independently of the symbol analysis pipeline.

### Reference: planner.py scope resolution

The planner's `_resolve_scope_for_change` implements the five-layer rule set
(first match wins):

```
1. full_regression_triggers   → full
2. high_fanout_files          → broad
3. no component               → broad
4. component, no test maps    → broad
5. component, has test maps   → component
```

In Run 004+, `_REACHABLE` is restricted to `("component", "broad", "full")`.
The `symbol` and `file` levels exist in `SCOPES` but are not reachable until
a future run extends the resolution rules.

The planner also computes `is_exhaustive`: `True` when `resolved_scope` is
`"broad"` or `"full"`, meaning the runner should ignore `selected_tests`
and execute the full suite.

## Fallback-Not-Floor Rule and Narrowing Gate

### Part 1: The fallback-not-floor rule

A component's test mapping is a **fallback**, not a **floor**. It becomes
mandatory when the effective scope IS component or broader, or when symbol
and file analysis cannot safely narrow. It is NOT added on top of a safely
resolved symbol answer. In other words: if the five narrowing conditions are
met and the result is symbol scope, the component test mapping is irrelevant —
you do not union the symbol tests with the component tests. The component
mapping only kicks in when narrowing cannot proceed (no symbol info, no file
info, empty mapping) and the result is component scope or broader.

### Part 2: The five narrowing conditions (§3 formulation)

The five conditions that must ALL be true for the planner to safely narrow
below component scope:

(a) Every changed file's symbol result is a real answer, not UNKNOWN.

(b) The reverse closure is safe — `Closure.is_safe` is True.

(c) Every affected symbol maps to at least one indexed test.

(d) The policy is not empty.

(e) No changed path matches `high_fanout` or `full_regression` triggers.

### Part 3: The five conditions as they appear in code (§4 narrowing gate)

Each condition is independently checked in the narrowing gate, and each
produces a `narrowing_blocker` entry when false:

- `_UNKNOWN` symbols → `narrowing_blocker`: "symbol resolution unknown"
- `not closure.is_safe()` → `narrowing_blocker`: "unsafe reverse closure"
- No tests mapped for a symbol → `narrowing_blocker`: "symbol has no indexed tests"
- Empty policy → `narrowing_blocker`: "policy is empty"
- `high_fanout` or `full_regression` trigger → `narrowing_blocker`: "high fanout / full regression trigger"

If any condition fails, narrowing is refused and the scope falls back to
component or broader.

### Part 4: The asymmetry for unresolved tests

An unresolved test module is always selected (appears in every selection)
rather than excluded. An unresolved source widens the closure (not narrows).
Neither reduces the set of selected tests. This is an asymmetry: unknowns
widen, they never narrow.

## Lifecycle Baselines (Run 010)

### OD-3: Baseline at Promotion

When a GOAL-DRAFT is promoted to GOAL.md, the target repository's HEAD at that
moment becomes the Run baseline, recorded durably in the RUN-LEDGER.md entry
`promote-goal`. This commit is discovered by parsing the ledger line:

```
- baseline: `<sha>` in `<repo_path>` (working tree: <N> uncommitted path(s) at promotion)
```

The baseline is the honest answer to _what did the Human approve this Run
against_. It cannot drift because promotion happens once per Run.

### What the engine knows (and does not)

The engine (`scripts/testing/`) knows **nothing** about runs, flows, promotion,
or the RUN-LEDGER. It receives a baseline as a parameter — handed to it. The
gate (`scripts/bridgeV002/gate-test-impact.py`) learns to read the baseline
out of the run's RUN-LEDGER.md and pass it to the engine.

This separation is critical:
- One engine serves both work-unit diffs (`baseline=None` → HEAD/index) and
  accumulated Run diffs (`baseline=<sha>` → stable diff).
- The RUN-LEDGER reader lives in `gate-test-impact.py`, NOT in `scripts/testing/`.
  TG8 mechanically enforces this.

### Three lifecycle points

The engine is invoked at three distinct lifecycle points, distinguished by the
`lifecycle_point` evidence field:

| Lifecycle point | Baseline | Scope | Purpose |
|-----------------|----------|-------|---------|
| `work_unit` | `None` (HEAD/index) | Narrow | Per-handoff impact analysis |
| `run_baseline` | SHA from RUN-LEDGER | At least `broad` | Accumulated Run diff |
| `explicit_gate` | `None` (or explicit) | `full` | Explicit release/high-risk gate |

The gate determines the lifecycle point and sets the scope accordingly.
`explicit_gate` scope is **never downgradable** — a role cannot lower it.

### The dirty-tree condition

A baseline is only meaningful against a clean tree. If the target carried
uncommitted work at promotion, the recorded commit describes something other
than what was on disk. The gate must:

```
read whether the tree was clean at promotion, if the ledger states it
if the ledger does not state it            → treat cleanliness as UNKNOWN (dirty)
if it was dirty, or is unknown            → record in evidence AND escalate scope
never                                       → silently measure past it
```

The `baseline_tree_state` evidence field records: `"clean"`, `"dirty"`, or
`None` (unknown). None is treated as dirty for escalation — absent information
is the dirty answer, never the clean one.

### Fail-closed: unresolvable baseline

The recorded commit can be missing, unreadable, or no longer present in the
repository (rebase, force-push, ledger never written). The behaviour is fixed:

```
the required baseline resolves
    → use the accumulated diff and plan impact normally

the required baseline does NOT resolve
    → narrow impact analysis is UNAVAILABLE, not approximate
    → escalate to full regression, IF a full regression can be executed
    → record the baseline-resolution failure in the evidence, naming the commit

no safe regression can be performed at all
    → BLOCK. Do not pass, do not warn, do not run a partial suite.
```

**Never substitute `HEAD`, the previous commit, or any other baseline.** A
substituted baseline silently erases whatever part of the accumulated change
happened before it.

`baseline_resolution` evidence field records: `"resolved"` or `"unresolved"`.

### Failure modes under rebase and revert

- **Rebase:** The baseline commit may still exist as an orphaned commit.
  `git rev-parse --verify <sha>` will succeed and return the SHA, so the
  baseline resolves. However, the diff against it includes the rebase's
  changes, which is correct — the baseline is the exact point of approval.

- **Revert:** A revert commit is a new commit at the current HEAD. The
  baseline SHA still exists; the diff against it is correct. No special
  handling needed.

- **Force-push:** If the baseline SHA no longer exists in the repository
  (true deletion, not a rebase), `resolve_baseline()` raises `ValueError`.
  The gate interprets this as `unresolved` and escalates to full regression.

- **Ledger never written:** The baseline reader returns `None`. The gate
  treats this identically to an unresolvable SHA — escalates to full
  regression.

### Evidence fields

Three new fields enrich the 22-key evidence schema:

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `lifecycle_point` | `str` | `"work_unit"`, `"run_baseline"`, `"explicit_gate"` | Which lifecycle point produced this record |
| `baseline_tree_state` | `str or None` | `"clean"`, `"dirty"`, `None` | Was the tree clean at promotion? None = unknown (treated as dirty) |
| `baseline_resolution` | `str or None` | `"resolved"`, `"unresolved"`, `None` | Did the baseline resolve? None = not applicable (work_unit) |

## Coverage-Assisted Impact Index (Run 013)

Run 013 introduces an optional, additive layer over the static test
index: a `CoverageRecord` that maps each symbol to the set of test
paths that **actually executed** it during a broad or full regression
run. The static index remains the authority; coverage is **supporting
evidence only**.

### Why coverage is supporting evidence, not authority

A previous run exercised whatever behaviours it happened to reach.
Treating that record as the complete set of dependents would narrow the
mandatory surface on the strength of what nobody thought to test. A
test that the previous run never invoked becomes invisible to the next
selector. Coverage is corroboration, never enumeration.

This is the principle behind three hard rules that bind every change in
this Run:

```text
coverage may ADD a test                                   yes
coverage may REMOVE a test                                never
coverage may permit a narrowing the static rules refuse   never
"only the tests seen in a previous coverage run"          never
```

The third rule is the one worth naming explicitly: even when coverage
has seen a symbol executed, it cannot authorise a narrowing below the
scope the five-condition gate has already chosen. If the static rules
landed on `component` because condition (c) failed, coverage cannot
move that to `symbol` or `file`.

### What invalidates a record

A `CoverageRecord` is bound to two pieces of state at collection time:

- `repo_fingerprint` — SHA-256 over `git rev-parse HEAD`.
- `policy_fingerprint` — `policy.policy_hash` from the canonical
  serialization.

A record is **discarded**, not trusted, when:

```text
its own fingerprints are empty                  — unknown → incompatible
the current policy's hash mismatches            — different policy → incompatible
the current repo's HEAD differs                 — different repository → incompatible
```

Unknown compatibility is incompatibility — the same fail-closed rule
Run 005 applies to evidence staleness. A record that cannot be proven
fresh is never used, and the static selection is the answer that stands.

### How coverage merges into the union

When `tests_for()` receives a compatible `coverage_record`, the merge is
strictly additive:

```text
static_tests   = tests_for(index, changed, symbols, closure, policy)
                       # Run 009 selection — five-condition narrowing
coverage_tests = ⋃ { tests for sym in coverage_record.symbol_to_tests }
final_tests    = static_tests ∪ coverage_tests
```

The merge is implemented as a single union at the end of `tests_for()`,
after the static scope is resolved. Coverage never re-enters the
narrowing-gate evaluation; it can only add to the set the gate already
produced. `narrowing_blockers` are preserved verbatim on the returned
`Selection`, because the gate's blockers are still the reasons the
scope is what it is.

There is no `intersection()`, no `&=`, no `& set(...)` anywhere on this
path — TG8 mechanically enforces it.

### Why coverage cannot narrow below static scope

The static scope decision happens **first**. Once that decision is
made, coverage consults `coverage_record.symbol_to_tests` and unions
those paths into the test set. The resolved scope, the rationale, and
the narrowing blockers are all preserved. Coverage cannot:

- Replace a `component` decision with `symbol` because some symbols
  appeared in the record.
- Replace a `broad` decision with `file` because the coverage record
  has file-level observations.
- Reduce the blocker list to silence what the gate has already refused.

The contract: coverage changes the **set of tests**, never the **scope
ladder rung**. A reviewer reading the resulting `Selection.rationale`
sees the same scope reasoning they would see without coverage, plus a
`+N coverage test(s) merged` suffix on the rationale.

### Collection is off by default

The runner's `run_plan()` accepts a `collect_coverage: bool = False`
parameter. With the default, behaviour is exactly as Run 005 left it:
no coverage overhead, no extra subprocess, no new file. The change is
opt-in at the call site and only proceeds when the plan's
`resolved_scope` is `broad` or `full` — coverage at narrower rungs is
meaningless and is silently skipped.

When collection does proceed, the runner:

1. Reads the current `repo_fingerprint` from `git rev-parse HEAD`.
2. Reads the current `policy_fingerprint` from `policy.policy_hash`.
3. Builds an empty `CoverageRecord` bound to those fingerprints (this
   Run does not parse `.coverage` or `coverage.json` — the binding
   infrastructure is the deliverable; content parsing is deferred to
   a later Run).
4. Persists the record to `<repo_root>/.dpmtf/coverage-index.json` for
   a later handoff to read.

The 22-key evidence schema is **unchanged** — coverage never alters
evidence. The record lives in a separate index file that downstream
handoffs may consult via `CoverageRecord.from_dict()`.

### `CoverageRecord` contract

```python
@dataclass(frozen=True)
class CoverageRecord:
    symbol_to_tests:    dict[str, set[str]]
    repo_fingerprint:   str
    policy_fingerprint: str
    run_scope:          str   # "broad" | "full"
    collected_at:       str   # ISO-8601 UTC
    schema_version:     str   # constant for now
```

Frozen dataclass; `merge()` returns a new record; the original is never
mutated. `is_compatible(repo_fp, policy_fp)` returns `True` only when
both pairs of fingerprints are non-empty and equal. `empty()` returns
a sentinel record whose fingerprints are the empty string — it is
never compatible with any state and is equivalent to passing `None`
into `tests_for()`.

### Module surface

```python
# scripts/testing/coverage_index.py
__all__ = ["CoverageRecord", "COVERAGE_RECORD_SCHEMA_VERSION", "CoverageError"]
```

The module is **only** imported by `scripts/testing/test_index.py` (as
the type for the optional `coverage_record` parameter on `tests_for()`)
and by `scripts/testing/runner.py` (as the type to build and persist
when `collect_coverage=True`). The rest of the test-impact subsystem
does not know coverage exists — Run 009 invariance is preserved
mechanically by the `coverage_record=None` default and by the
optionality of the parameter.

### Invariant guard

`tests_for()` without a `coverage_record` produces the same
`Selection` Run 009 delivered. This is enforced by
`test_tests_for_without_coverage_unchanged`, which compares the byte-
for-byte `Selection` produced with and without the new parameter.
TG6 (the existing test_index test suite) also pins this from the other
direction: every test that existed before Run 013 must still pass.

