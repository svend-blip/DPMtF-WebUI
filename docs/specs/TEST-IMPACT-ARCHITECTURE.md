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

Run 004 onward. This Run delivers the fact source and its hash only.
