# Secure Execution Runtime — Implementation Plan

**Goal:** Build a production modular Python runtime from the verified spike (Task 4.1 GO, 10/10). Replaces OpenCode/Claude Code as execution adapter for `imple01` when configured.

**Architecture:** Split the spike into modules: `runtime.py` (main loop), `file_tools.py` (safe path + file ops), `prompt_parser.py` (JSON extraction + normalization), `checks.py` (verification registry), `result.py` (result + checkpoint writer). Wire as `execution_backend=python_runtime` in dispatch.py.

**Tech Stack:** Python 3.10+ stdlib, Ollama HTTP API, existing allocator + dispatch.py.

## Tasks

1. `file_tools.py` — safe_resolve, read_file, apply_patch
2. `prompt_parser.py` — extract_json, fix_newlines, normalize_fields
3. `checks.py` — registered check registry (py_compile, node_check)
4. `result.py` — result writer + checkpoint creation
5. `runtime.py` — main loop, model interaction, allocator integration
6. Wire into dispatch.py as `execution_backend=python_runtime`
7. Integration test — end-to-end with real model
8. `cron_tick.py` scheduler integration — scheduler can dispatch via runtime

## Acceptance Criteria

1. All spike tests still pass (path safety, action schema)
2. 10/10 edit reliability maintained
3. Modular code — each module independently testable
4. Runtime resolves model via allocator
5. Runtime produces structured checkpoint
6. dispatch.py can route to python_runtime backend
7. No shell=True, no git commit/push/add
8. 106 existing tests + all new tests green
