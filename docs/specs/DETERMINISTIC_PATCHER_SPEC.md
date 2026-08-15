# DPMtF Deterministic Patcher — Implementation Specification

> Provenance: delivered verbatim by the Human 2026-08-15 as the product
> specification for the Deterministic Patcher capability. This document is
> authoritative for WHAT is built. The Mission Contract for each run
> (`{bridge_dir}/preferred_cloud/runs/{id}/GOAL.md`) binds scope, fence,
> budgets and testgoals for HOW each increment is executed.

## Purpose

Extend DPMtF with an optional Deterministic Patcher capability that separates LLM reasoning from repository mutation.

The feature must be strictly additive.

Existing DPMtF functionality must continue to work unchanged, including:

* existing direct-edit implementation roles
* existing flows and step keys
* existing supervisor behavior
* existing review/verdict handling
* existing Model Allocator behavior
* existing local and cloud model support
* existing execution runtimes

The new Deterministic Patcher must be available as an additional execution path, not as a replacement for current behavior.

## 1. Core Architecture

The new optional execution path should be:

```
Supervisor / Architect
        |
        v
Implementer LLM
        |
        | implementation proposal
        v
Deterministic Patcher
        |
        | deterministic repository mutation
        v
Repository
        |
        v
Existing Review Flow
```

The key separation is:

- **LLM:** decides what code should change
- **Deterministic Patcher:** performs the requested change using deterministic tools
- **DPMtF:** controls orchestration, lifecycle, retries, review and verdict handling

The Deterministic Patcher must not become another autonomous agent.

It is a tool/runtime capability.

Conceptually:

```
result = patcher.apply(request)
```

## 2. Recommended Initial Technology

The recommended initial implementation uses two complementary patch engines.

```
Deterministic Patcher
│
├── structural_python
│     └── LibCST
│
└── unified_diff
      └── git apply
```

The two modes solve different problems.

### 2.1 LibCST

Use LibCST as the preferred deterministic structural patch engine for Python code.

LibCST should handle known, explicitly supported transformations such as:

add import, remove import, replace import, add function, replace function,
remove function, add class method, replace class method, modify function
call, modify function argument, modify decorator, add class attribute,
replace assignment, insert statement at known structural location.

The LLM should not provide replacement source files for these operations.

Instead, it should produce a structured edit request.

Example:

```json
{
  "patch_mode": "structural_python",
  "operations": [
    {
      "operation": "add_import",
      "file": "app/dispatch.py",
      "module": "model_allocator",
      "name": "resolve_model"
    }
  ]
}
```

The LibCST-based patcher performs the transformation.

This provides a deterministic boundary between LLM reasoning and code mutation.

## 3. Unified Diff Mode

Not every code modification can or should initially be represented using predefined LibCST operations.

DPMtF must therefore also support standard unified diffs.

Example:

```json
{
  "patch_mode": "unified_diff",
  "patch": "diff --git a/app/dispatch.py b/app/dispatch.py\n..."
}
```

The deterministic execution sequence should be:

```
receive diff -> validate paths -> git apply --check -> apply -> git diff -> verification
```

Preferred underlying commands:

```
git apply --check
git apply
git diff
git status --porcelain
```

The Patcher should not attempt to semantically repair a failed diff.

If the diff fails, return a deterministic failure result to DPMtF.

## 4. Why Both Modes Are Needed

The initial architecture should deliberately avoid forcing every change through one mechanism.

Use **LibCST** when the requested change maps to a supported structural Python operation.

Use **git apply** when the model needs to propose a more general modification.

Conceptually:

```
             Implementation Proposal
                       |
              determine patch mode
                       |
         +-------------+-------------+
         |                           |
         v                           v
 structural_python             unified_diff
         |                           |
       LibCST                    git apply
         |                           |
         +-------------+-------------+
                       |
                       v
                  PatchResult
```

This allows DPMtF to gradually increase the number of deterministic transformations without requiring a large transformation framework in the first implementation.

## 5. Backward Compatibility

The existing implementation path must remain the default unless explicitly configured otherwise.

Existing behavior:

```
archi01 -> imple01 -> imple01 edits repository directly -> review01
```

New optional behavior:

```
archi01 -> imple01 -> imple01 generates PatchRequest -> Deterministic Patcher -> review01
```

No current flow should break because the Deterministic Patcher exists.

No existing role should silently change execution mode.

A possible configuration could be:

```
implementation_mode: direct
```

or:

```
implementation_mode: deterministic_patch
```

If a suitable existing DPMtF configuration mechanism already exists, reuse it instead of creating a parallel configuration system.

## 6. Patcher Is Not a Role

Do not implement a `patcher01` agent unless a future requirement explicitly requires a reasoning role.

The Deterministic Patcher should instead behave like other execution infrastructure.

Example:

```
imple01
    |
    | tool call
    v
deterministic_patcher.apply()
```

The Patcher:

* does not need a model
* does not need a context window
* does not require Model Allocator
* does not consume LLM tokens
* does not maintain conversational state
* does not reason about requirements

## 7. Proposed Package Structure

A possible implementation structure is:

```
dpmtf/
└── patcher/
    ├── __init__.py
    ├── service.py
    ├── models.py
    ├── policy.py
    ├── verifier.py
    │
    ├── engines/
    │   ├── __init__.py
    │   ├── base.py
    │   ├── libcst_engine.py
    │   └── git_diff_engine.py
    │
    └── transforms/
        ├── __init__.py
        ├── imports.py
        ├── functions.py
        ├── classes.py
        └── assignments.py
```

Do not force this exact layout if it conflicts with current DPMtF repository conventions.

Prefer integration with existing architectural patterns.

## 8. Core Interface

Provide a small stable abstraction.

For example:

```python
class DeterministicPatcher:
    def check(self, request: PatchRequest) -> PatchResult: ...
    def apply(self, request: PatchRequest) -> PatchResult: ...
```

The orchestration layer should not need to know which underlying engine performs the mutation.

Internal dispatch:

```python
if request.patch_mode == "structural_python":
    engine = LibCSTEngine()
elif request.patch_mode == "unified_diff":
    engine = GitDiffEngine()
```

## 9. PatchRequest

Introduce a machine-readable request object.

Conceptually:

```python
@dataclass
class PatchRequest:
    repo_path: str
    patch_mode: str
    operations: list | None = None
    patch: str | None = None
    allowed_paths: list[str] | None = None
    base_revision: str | None = None
    verification: dict | None = None
```

Example structural request:

```json
{
  "repo_path": "/repository",
  "patch_mode": "structural_python",
  "operations": [
    {
      "operation": "add_import",
      "file": "app/dispatch.py",
      "module": "model_allocator",
      "name": "resolve_model"
    }
  ]
}
```

Example unified diff request:

```json
{
  "repo_path": "/repository",
  "patch_mode": "unified_diff",
  "patch": "diff --git a/app/dispatch.py b/app/dispatch.py\n..."
}
```

## 10. PatchResult

Every patch invocation must return a structured result.

Example:

```json
{
  "status": "applied",
  "applied": true,
  "engine": "libcst",
  "files_changed": ["app/dispatch.py"],
  "files_rejected": [],
  "operations_requested": 1,
  "operations_applied": 1,
  "verification": {"syntax": "passed", "lint": "passed", "tests": "passed"},
  "resulting_diff": "...",
  "error": null
}
```

Failure example:

```json
{
  "status": "rejected",
  "applied": false,
  "engine": "git_apply",
  "files_changed": [],
  "files_rejected": [],
  "verification": {"syntax": "not_run", "lint": "not_run", "tests": "not_run"},
  "error_code": "PATCH_CONFLICT",
  "error": "Patch does not apply cleanly"
}
```

## 11. Suggested Error Codes

Use stable machine-readable states. For example:

```
PATCH_INVALID
PATCH_UNSUPPORTED_OPERATION
PATCH_FILE_NOT_FOUND
PATCH_PATH_REJECTED
PATCH_BASE_MISMATCH
PATCH_TARGET_NOT_FOUND
PATCH_TARGET_AMBIGUOUS
PATCH_CONFLICT
PATCH_APPLY_FAILED
PATCH_APPLIED
PATCH_APPLIED_SYNTAX_FAILED
PATCH_APPLIED_LINT_FAILED
PATCH_APPLIED_TEST_FAILED
PATCH_INTERNAL_ERROR
```

Do not encode orchestration decisions into these states.

DPMtF decides what to do next.

## 12. Initial LibCST Operations

Keep the first version intentionally small.

Recommended Phase 1 operations:

```
add_import
remove_import
replace_import
replace_function
add_function
replace_method
add_method
replace_assignment
```

Potential Phase 2 operations:

```
remove_function
remove_method
modify_call_argument
add_call_argument
remove_call_argument
replace_decorator
add_decorator
remove_decorator
insert_statement
replace_class_attribute
```

Only implement structural operations when they can have clear deterministic semantics.

Avoid generic operations such as "change this code so it works better". That belongs to the LLM.

## 13. Target Identification

Structural transformations must identify targets precisely.

For example:

```json
{
  "operation": "replace_function",
  "file": "app/dispatch.py",
  "function": "dispatch_job",
  "replacement": "..."
}
```

For methods:

```json
{
  "operation": "replace_method",
  "file": "app/runtime.py",
  "class": "ExecutionRuntime",
  "method": "start",
  "replacement": "..."
}
```

If the target cannot be uniquely identified, fail. Do not guess.

Example: `PATCH_TARGET_AMBIGUOUS`

## 14. Path Security

Every request must be constrained to the selected repository.

Reject:

```
../
absolute paths outside repo
symlink escape
unexpected repository roots
```

Example malicious target: `../../etc/passwd` must fail before any write.

If `allowed_paths` is configured:

```json
{"allowed_paths": ["app/", "tests/"]}
```

then modifications outside those paths must fail.

## 15. Dry-Run / Check Mode

Both engines should support validation without repository mutation.

Interface: `result = patcher.check(request)`

For LibCST this should: parse target file, validate requested operation,
locate target, apply transformation in memory, ensure generated Python
remains parseable, produce proposed diff, do not write.

For unified diff: validate paths, `git apply --check`, do not write.

This becomes useful later for multi-worker patch evaluation.

## 16. Apply Mode

Apply mode: `result = patcher.apply(request)`

Recommended sequence:

1. Resolve repository root.
2. Record current repository state.
3. Validate request schema.
4. Validate all target paths.
5. Validate optional base revision.
6. Perform dry-run/check.
7. Abort if check fails.
8. Apply transformation.
9. Capture exact resulting git diff.
10. Run deterministic verification.
11. Return PatchResult.

## 17. Atomicity

Patch application should be atomic where practical.

For a request containing multiple operations, desired behavior is: all
operations applied, or none applied.

Do not silently leave partial application unless the API explicitly reports
and supports transactional partial application.

Initial implementation should prefer fail-all semantics.

## 18. Verification Pipeline

After successful mutation, optionally run deterministic verification.

Recommended layers: syntax -> formatter/linter -> tests.

For Python: `python -m py_compile`, Ruff, pytest.

Reuse existing project commands/configuration where available.

Do not hardcode pytest or Ruff as mandatory if a repository already defines its own verification commands.

Conceptually:

```yaml
patch_verification:
  syntax: true
  lint_command: "ruff check ."
  test_command: "pytest -q"
```

## 19. Ruff

Ruff may be used after a Python transformation for lint validation, optional
import cleanup, optional formatting.

Formatting should not occur unexpectedly. If formatting is enabled, it should
be explicitly configured. The Patcher should record whether formatting changed
additional lines beyond the original transformation.

## 20. Python Syntax Validation

At minimum, changed Python files should be syntax checked.

Possible implementation: `python -m py_compile path/to/file.py` or equivalent
in-process Python compilation.

Syntax failure should produce `PATCH_APPLIED_SYNTAX_FAILED`.

The surrounding DPMtF policy can decide whether to revert or hand the failure
to an implementer/reviewer.

## 21. Test Execution

The Patcher may execute configured tests after mutation.

Example:

```json
{"verification": {"commands": ["pytest tests/test_dispatch.py -q"]}}
```

The Patcher executes the command and returns:

```json
{"exit_code": 0, "status": "passed"}
```

The Patcher should not interpret test failures semantically. It simply reports them.

## 22. Existing Review Flow Remains Authoritative

The Patcher must not replace review.

The intended flow is: imple01 -> patcher -> repository -> review01.

The review role should evaluate the actual resulting repository state.

Suggested handoff information: original task, implementation summary,
PatchRequest, PatchResult, resulting git diff, verification output.

## 23. Failure Handling

The Patcher must never invoke an LLM itself to fix failures.

Incorrect: git apply fails -> patcher calls model -> model rewrites patch.

Correct: git apply fails -> PATCH_CONFLICT -> return to DPMtF -> existing
supervisor/retry/review mechanism decides next action.

This separation is essential.

## 24. Model Allocator

The Deterministic Patcher is not a model and must not be treated as one.

Therefore it should have: no model alias, no model provider, no context
allocation, no VRAM allocation, no model lifecycle, no token accounting.

The implementer invoking it may still be managed by Model Allocator normally.

Example:

```
imple01
    |
Model Allocator resolves Fable 5
    |
Fable 5 generates PatchRequest
    |
Deterministic Patcher executes locally
```

## 25. DPMtF Tool Exposure

The Patcher should be callable from whichever coding frontend or runtime DPMtF uses.

Conceptually expose operations similar to `patch_check` and `patch_apply`.

Example tool call:

```json
{
  "tool": "patch_apply",
  "arguments": {
    "patch_mode": "structural_python",
    "operations": [
      {"operation": "add_import", "file": "app/dispatch.py",
       "module": "model_allocator", "name": "resolve_model"}
    ]
  }
}
```

The caller should receive a structured PatchResult.

## 26. LLM Instructions

When deterministic patch mode is active, the implementation role should be explicitly told:

> Do not directly modify repository files when the requested change can be
> performed through the Deterministic Patcher.
> Prefer structural_python operations for supported Python transformations.
> Use unified_diff when the requested change cannot be represented using
> available structural operations.
> Do not attempt to manually repair a rejected patch without returning control
> through the normal DPMtF execution flow.

This behavior can be added to role governance without affecting existing direct-edit roles.

## 27. Example: LibCST Operation

Suppose imple01 determines that dispatch.py needs an additional import.

Instead of editing `from model_allocator import resolve_model` directly, it requests:

```json
{
  "patch_mode": "structural_python",
  "operations": [
    {"operation": "add_import", "file": "app/dispatch.py",
     "module": "model_allocator", "name": "resolve_model"}
  ]
}
```

The LibCST engine: loads module -> parses concrete syntax tree -> checks
whether import already exists -> inserts import deterministically -> renders
source -> generates resulting diff.

If the import already exists, the operation should preferably be idempotent.

Example result:

```json
{"status": "no_change", "applied": true, "operations_applied": 0,
 "reason": "Import already exists"}
```

## 28. Idempotency

Whenever practical, structural operations should be idempotent.

For example, `add_import X` executed twice should not create a duplicate
import. Similarly, `add_method` should detect a conflicting existing method
before mutation.

Return a deterministic result rather than guessing what the user intended.

## 29. Example: Unified Diff

For a more complex change, the model may produce a standard unified diff.

The GitDiffEngine should perform approximately: `git apply --check patch.diff`;
if successful, `git apply patch.diff`; then capture `git diff`.

If `git apply --check` fails, no mutation occurs.

## 30. Logging and Auditability

Every deterministic patch invocation should be traceable.

Recommended metadata: request_id, job_id, flow_key, step_key, role,
patch_mode, patch_engine, repository, base_revision, files_requested,
files_changed, operation count, patch hash, resulting diff hash, verification
status, start timestamp, end timestamp, final status.

Where appropriate, store PatchRequest, PatchResult, resulting diff and
verification logs using existing DPMtF run/artifact mechanisms.

Do not introduce an independent logging subsystem if DPMtF already provides one.

## 31. Repository State

Record repository state before applying the patch.

At minimum: HEAD revision, dirty/clean state, existing changed files.

The Patcher should not assume the repository is clean unless DPMtF policy
requires it. However, it must distinguish changes that existed before the
patch from changes caused by the patch.

This is particularly important for autonomous execution.

## 32. Existing Dirty Working Trees

Do not automatically reject all dirty working trees unless current DPMtF
governance requires this. Instead, detect and record pre-existing changes.

The patch operation must not accidentally overwrite unrelated modifications.

Where safe application cannot be guaranteed, return a deterministic failure:
`PATCH_BASE_MISMATCH` or `PATCH_CONFLICT`.

## 33. No Automatic Commit Requirement

The Patcher should not automatically create Git commits in the first
implementation. Its responsibility ends at: validated mutation +
verification + structured result.

Any commit/checkpoint behavior should remain under existing or future DPMtF
execution/checkpoint governance.

## 34. Future Multi-Worker Architecture

The interface should support a later architecture where multiple workers
generate candidates, each patch is first checked deterministically
(`patcher.check`), an evaluator/supervisor selects among the valid ones, and
only the selected patch is applied.

The Deterministic Patcher itself does not perform candidate selection.

## 35. Future Structural Operation Library

Over time, DPMtF can build a library of trusted deterministic transformations
(Python: imports/functions/classes/decorators/assignments/calls). Later,
other languages can use different engines (JS/TS CST engine, deterministic
JSON/YAML mutation, generic git apply).

The initial implementation should not attempt to solve all languages.
Start with Python + unified diff.

## 36. Engine Abstraction

Avoid coupling DPMtF orchestration directly to LibCST. Use an engine interface:

```python
class PatchEngine:
    def check(self, request): raise NotImplementedError
    def apply(self, request): raise NotImplementedError
```

Implementations: `LibCSTEngine(PatchEngine)`, `GitDiffEngine(PatchEngine)`.

This allows additional deterministic patch engines later without changing the
orchestration API.

## 37. Initial Implementation Scope

Phase 1 should remain deliberately small.

Implement:

```
PatchRequest
PatchResult
DeterministicPatcher.check()
DeterministicPatcher.apply()
LibCST engine
LibCST operations:
- add_import
- remove_import
- replace_function
- add_function
- replace_method
- add_method
- replace_assignment
Git unified diff engine
path validation
git apply --check
atomic apply behavior where practical
resulting git diff capture
Python syntax verification
optional existing test command execution
structured errors
unit tests
```

Do not initially implement:

```
LLM-based conflict resolution
semantic patch repair
automatic candidate ranking
new supervisor logic
distributed queueing
automatic commits
automatic rollback strategy beyond safe local transaction handling
large cross-language transformation framework
```

## 38. Suggested Development Order

```
Phase 1A: PatchRequest, PatchResult, base engine interface, path validation,
          GitDiffEngine.check(), GitDiffEngine.apply()
Phase 1B: LibCST dependency, LibCSTEngine, add_import, replace_function,
          add_function
Phase 1C: replace_method, add_method, replace_assignment, remove_import
Phase 1D: syntax verification, configured lint/test verification, resulting
          diff capture, audit metadata
Phase 1E: optional DPMtF flow/step integration,
          implementation_mode = deterministic_patch
Phase 1F: role governance instructions, integration tests with one existing
          DPMtF flow
```

Each phase should preserve existing test behavior.

## 39. Test Requirements

Use TDD where consistent with existing DPMtF development governance.

At minimum test:

```
valid unified diff applies
invalid unified diff changes nothing
git apply check failure changes nothing
path traversal is rejected
absolute external path is rejected
allowed-path policy works
LibCST add_import works
LibCST add_import is idempotent
LibCST replace_function replaces only selected function
LibCST method target includes class identity
ambiguous structural targets fail
invalid Python transformation fails safely
multiple structural operations apply atomically
PatchResult contains resulting diff
direct-edit DPMtF mode remains unchanged
deterministic_patch mode is opt-in
Patcher has no dependency on Model Allocator
existing DPMtF tests remain green
```

## 40. Integration Test Example

Create one integration test based on an existing DPMtF implementation flow:
archi/goal input -> imple role -> produces PatchRequest -> Deterministic
Patcher -> repository mutation -> existing review.

Verify that the patch is applied, the actual diff is handed to review, and
existing verdict behavior remains unchanged.

Then run the same flow using `implementation_mode: direct` and verify that
existing behavior remains unchanged.

## 41. Configuration Principle

Do not make deterministic patching globally mandatory.

The hierarchy should allow gradual adoption. For example: global default
`direct`; flow override `deterministic_patch`; step override
`deterministic_patch`; specific role `direct`.

The exact precedence should reuse existing DPMtF configuration semantics
rather than introducing a new independent precedence model.

## 42. Example Configuration

Conceptual only:

```yaml
roles:
  imple01:
    implementation_mode: deterministic_patch
patcher:
  enabled: true
  structural_python:
    enabled: true
    engine: libcst
  unified_diff:
    enabled: true
    engine: git_apply
  verification:
    syntax: true
    lint: false
    tests: true
```

If DPMtF already stores comparable configuration elsewhere, integrate there.

## 43. Fable 5 Usage

Fable 5 or another strong implementation model can use the feature without
having direct write authority for supported operations.

The expensive reasoning model remains responsible for: architecture
comprehension, implementation reasoning, selecting files and symbols,
choosing intended code changes, producing replacement implementation
fragments when necessary.

Deterministic code performs: target location, structural mutation, path
enforcement, application checks, syntax checks, tests, diff generation.

## 44. Important Distinction

The Deterministic Patcher does not make code generation deterministic.

The LLM may still generate different implementations.

What becomes deterministic is the mutation procedure once the model has
produced a specific PatchRequest.

Therefore: same repository state + same PatchRequest + same tool
versions/configuration = same repository transformation.

That is the desired property.

## 45. Architectural Boundary

Maintain this boundary throughout implementation:

- Supervisor decides orchestration
- Architect decides architecture
- Implementer LLM proposes implementation
- Deterministic Patcher executes requested mutation
- Verifier runs deterministic checks
- Reviewer evaluates correctness
- Existing DPMtF verdict handling decides continuation

Do not move supervisor, reviewer or repair reasoning into the Patcher.

## 46. Acceptance Criteria

The implementation is complete when all of the following are true:

* Existing DPMtF direct editing continues to work unchanged.
* Deterministic patching is opt-in.
* The Patcher is callable as a tool/runtime capability rather than an agent.
* LibCST is implemented as the initial Python structural patch engine.
* git apply --check / git apply is supported for general unified diffs.
* Structural PatchRequests are machine-readable.
* Patch results are machine-readable.
* Path traversal and repository escape are prevented.
* Failed patch validation causes no repository mutation.
* Multi-operation structural patches do not leave accidental partial state.
* Resulting repository diff is captured.
* Python syntax verification is available.
* Existing test commands can optionally be run after patching.
* Patch failures are returned to existing DPMtF orchestration rather than repaired internally.
* The Patcher does not interact with Model Allocator.
* The Patcher does not invoke any LLM.
* Existing review/verdict handling remains authoritative.
* Existing DPMtF test suites remain green.

## 47. Non-Goals

This implementation must not become a general redesign of DPMtF.

Specifically, do not use this task to: replace existing flows, replace Model
Allocator, replace role governance, replace implementation agents, replace
review roles, introduce a new agent framework, introduce a new job queue,
redesign execution runtime, convert all existing implementation roles to
patch mode, implement ensemble reasoning, implement multi-worker patch
ranking, implement distributed execution.

Those may be future independent projects.

## 48. Final Implementation Principle

The feature should introduce one new architectural capability:

```
LLM-generated intent
        |
        v
structured mutation request
        |
        v
deterministic execution
        |
        v
existing DPMtF governance
```

The recommended initial implementation is:

```
DPMtF Deterministic Patcher
│
├── LibCST
│    └── deterministic structural Python transformations
│
├── git apply
│    └── deterministic unified diff application
│
├── Python syntax validation
│
├── optional Ruff
│
├── optional existing test commands
│
└── structured PatchResult
```

The existing direct-edit path remains available and unchanged.

The Deterministic Patcher should therefore be implemented as an extension to
DPMtF's execution capabilities, not as a replacement architecture.
