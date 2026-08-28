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
