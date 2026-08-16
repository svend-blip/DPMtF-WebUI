# DPMtF Deterministic Patcher — Usage Guide

> Companion to `docs/specs/DETERMINISTIC_PATCHER_SPEC.md` (the WHAT).
> This page covers HOW to drive the patcher: request and result schemas,
> error codes, the CLI tool, the verification pipeline, and the
> audit-metadata block.

> **Spec Phases 1E–1F are deferred to a follow-up run.** This
> implementation covers Phases 1A–1D only: the package, both engines,
> the verification pipeline, audit metadata, and the CLI. The wiring
> of `implementation_mode = deterministic_patch` into bridge tables
> and role governance, plus a live-flow integration test, are out of
> scope here and belong to a later run.

---

## 1. PatchRequest schema

`PatchRequest` is a frozen dataclass. The CLI and the Python facade
both accept the same JSON shape:

```json
{
  "repo_path": "/abs/path/to/repo",
  "patch_mode": "unified_diff",
  "patch": "diff --git a/x.py b/x.py\n@@ -1 +1 @@\n-old\n+new\n",
  "operations": null,
  "allowed_paths": null,
  "base_revision": null,
  "verification": null
}
```

Field-by-field:

| Field | Type | Required | Meaning |
|------|------|----------|---------|
| `repo_path` | string | yes | Absolute path to the repository root. The CLI does NOT hardcode any path; the value comes from the request. |
| `patch_mode` | string | yes | `"unified_diff"` or `"structural_python"`. Unknown values → `PATCH_UNSUPPORTED_OPERATION`. |
| `patch` | string | for `unified_diff` | A standard unified diff body. Must be non-empty. |
| `operations` | list of objects | for `structural_python` | One or more structural operations, each with an `operation` name and per-operation fields. |
| `allowed_paths` | list of strings | optional | When present, only paths matching one of these prefixes are accepted; everything else → `PATCH_PATH_REJECTED`. |
| `base_revision` | string | optional | A 40-char hex commit hash; the patcher refuses to apply when it does not match the current `HEAD`. |
| `verification` | object | optional | Drives the post-apply verification pipeline; see §5 below. |

### Structural operation shapes

All seven §37 operations are supported:

```json
{"operation": "add_import",       "file": "x.py", "module": "os",           "name": null}
{"operation": "remove_import",    "file": "x.py", "module": "os",           "name": null}
{"operation": "replace_function", "file": "x.py", "function": "alpha",       "replacement": "def alpha():\n    return 42\n"}
{"operation": "add_function",     "file": "x.py", "code": "def gamma():\n    return 3\n"}
{"operation": "replace_method",   "file": "x.py", "class": "Foo", "method": "bar", "replacement": "def bar(self):\n    return 1\n"}
{"operation": "add_method",       "file": "x.py", "class": "Foo", "code": "def baz(self):\n    return 2\n"}
{"operation": "replace_assignment","file": "x.py", "name": "VERSION",          "replacement": "VERSION = 2\n"}
```

`replace_import` (spec §12) is NOT supported — the §37 set excludes
it. A request that names it returns `PATCH_UNSUPPORTED_OPERATION`.

### Authoring `replacement` / `code` fragments — the parse contract

Three rules, all learned the hard way by the first live flow tasks
(pi_test handoffs 008/009, 2026-08-16):

1. **The fragment is parsed as a top-level statement**
   (`cst.parse_statement`), so the `def` must sit at **column 0** —
   even for `replace_method`. The engine re-indents the definition and
   its executable body to the target's depth on insertion. A fragment
   submitted with the target's indentation already applied fails the
   parse (`PATCH_INVALID`, "Syntax Error @ 2:5"), because an indented
   `def` is not a valid top-level statement.
2. **String-literal interiors are NOT re-indented.** A multi-line
   docstring is one token; the engine cannot rewrite its inside. Write
   docstring continuation lines (and the closing `"""`) at the depth
   they must have **in the target file** — for a method under a
   class, that is 8 spaces even though the `def` sits at column 0 in
   your fragment:

   ```python
   def bar(self):
       """Opening line.

           Continuation at TARGET depth (8 spaces for a method),
           not at fragment depth.
           """
       return 1
   ```

   (Yes, the fragment looks over-indented on its own; it is correct
   after insertion.)
3. **Leading blank lines are inherited.** When the fragment carries no
   leading blank lines, the replaced definition's own leading lines
   (the PEP8 separation from its neighbor) are preserved. A fragment
   that starts with explicit blank lines keeps exactly those instead —
   the author's separation wins, nothing is stacked.

---

## 2. PatchResult schema

The CLI emits a JSON object with these keys (stable, sorted):

| Key | Type | Meaning |
|-----|------|---------|
| `status` | string | Human label: `"applied"`, `"no_change"`, `"check_passed"`, `"rejected"`, `"internal_error"`. |
| `applied` | bool | `true` iff the working tree was mutated by this call. |
| `engine` | string | `"git_apply"`, `"libcst"`, or `"deterministic_patcher"` for facade-level rejections. |
| `files_changed` | list of strings | Repo-relative paths mutated by this call. |
| `files_rejected` | list of strings | Paths the engine refused to touch. |
| `operations_requested` | int | Count of operations in the request. |
| `operations_applied` | int | Count of operations actually applied. |
| `verification` | object \| null | Structured per-step outcome from the post-apply pipeline; see §5. |
| `resulting_diff` | string \| null | The exact `git diff` the patch produced, limited to touched files. |
| `audit` | object \| null | Machine-readable audit metadata per spec §30; see §6. |
| `error_code` | string \| null | One of the constants in `patcher.errors` on failure; `null` on success. |
| `error` | string \| null | Human-readable failure description. |

---

## 3. Error codes (spec §11)

All 14 constants are stable machine-readable strings. The patcher
never interprets failures semantically — it reports the code and the
orchestration layer decides what to do next.

| Code | Meaning (one line) |
|------|--------------------|
| `PATCH_INVALID` | Schema-level rejection: missing fields, wrong types, contradictory payload. |
| `PATCH_UNSUPPORTED_OPERATION` | Unknown `patch_mode` or operation name. |
| `PATCH_FILE_NOT_FOUND` | Referenced target file does not exist on disk. |
| `PATCH_PATH_REJECTED` | Path security rejection: `..` traversal, absolute outside-repo, symlink escape, unexpected repository root, `allowed_paths` violation. |
| `PATCH_BASE_MISMATCH` | `base_revision` (when supplied) does not match the current `HEAD`. |
| `PATCH_TARGET_NOT_FOUND` | Structural target not found (function / method / import / assignment missing). |
| `PATCH_TARGET_AMBIGUOUS` | More than one matching target — the patcher refuses to guess. |
| `PATCH_CONFLICT` | `git apply --check` (or equivalent) failed; the diff does not apply cleanly. |
| `PATCH_APPLY_FAILED` | Generic filesystem / IO / permission failure during write. |
| `PATCH_APPLIED` | Successful apply; all requested operations completed. |
| `PATCH_APPLIED_SYNTAX_FAILED` | Applied, but post-apply syntax verification failed. Change is LEFT IN PLACE — DPMtF policy decides whether to revert. |
| `PATCH_APPLIED_LINT_FAILED` | Applied, but a configured lint command exited non-zero. |
| `PATCH_APPLIED_TEST_FAILED` | Applied, but a configured test command exited non-zero. |
| `PATCH_INTERNAL_ERROR` | Unhandled bug in the patcher — not a user-input issue. |

---

## 4. CLI

The CLI is `scripts/patcher_cli.py`. It does NOT import `config.py`,
does NOT hardcode any path, and takes its `repo_path` exclusively
from the request payload.

### Invocation

```bash
python3 scripts/patcher_cli.py patch_check   [REQUEST_FILE | -]
python3 scripts/patcher_cli.py patch_apply   [REQUEST_FILE | -]
```

When `REQUEST_FILE` is `-` or omitted, the request is read from stdin.

### Exit-code mapping

| Code | When |
|------|------|
| `0` | Successful outcome: `PATCH_APPLIED`, a successful check (`check_passed`), or a no-change outcome (`no_change`). |
| `1` | Any `PATCH_*` failure status — **including** `PATCH_APPLIED_SYNTAX_FAILED` and `PATCH_APPLIED_TEST_FAILED` (the patcher's job ends at "report verbatim"; the orchestrator decides what to do next). |
| `2` | Invalid invocation: unreadable / invalid JSON, unknown subcommand, missing `repo_path`. |

### stdout / stderr

* **stdout**: the full PatchResult as JSON. **Nothing else.** Callers
  can pipe stdout straight into `json.loads`.
* **stderr**: diagnostics only — usage errors, "cannot read file",
  etc. The PatchResult never appears on stderr.

### Worked example — structural apply

```bash
cat <<'JSON' > /tmp/req.json
{
  "repo_path": "/path/to/repo",
  "patch_mode": "structural_python",
  "operations": [
    {"operation": "add_import", "file": "lib.py", "module": "os"}
  ]
}
JSON

python3 scripts/patcher_cli.py patch_apply /tmp/req.json
# rc=0, stdout: PatchResult JSON with status="applied",
# files_changed=["lib.py"], audit.* populated.
```

### Worked example — unified-diff check

```bash
cat <<'JSON' > /tmp/req.json
{
  "repo_path": "/path/to/repo",
  "patch_mode": "unified_diff",
  "patch": "diff --git a/lib.py b/lib.py\n@@ -1 +1 @@\n-old\n+new\n"
}
JSON

python3 scripts/patcher_cli.py patch_check /tmp/req.json
# rc=0 (check_passed) or rc=1 (PATCH_CONFLICT) — never mutates the tree.
```

### Worked example — verification failure

```bash
cat <<'JSON' > /tmp/req.json
{
  "repo_path": "/path/to/repo",
  "patch_mode": "structural_python",
  "operations": [
    {"operation": "replace_function", "file": "lib.py",
     "function": "alpha", "replacement": "def alpha(:\n    return 0\n"}
  ],
  "verification": {"commands": ["python3 -c \"import sys; sys.exit(3)\""]}
}
JSON

python3 scripts/patcher_cli.py patch_apply /tmp/req.json
# rc=1; error_code=PATCH_APPLIED_SYNTAX_FAILED (or TEST_FAILED if syntax
# passes but the configured command exits 3); the PatchResult.verification
# dict carries the exit code and stderr tail VERBATIM.
```

---

## 5. Verification pipeline (spec §18–§21)

After a successful `apply()`, the patcher runs two layers of
verification. Nothing is hardcoded as mandatory (spec §18) — pytest
and Ruff are NEVER invoked unless they arrive as configured command
strings in the request.

### Layer 1 — syntax check (always available)

Every changed file whose name ends in `.py` is compiled in-process via
`compile(source, path, "exec")`. **Non-Python files are skipped.**
The in-process form leaves **no `.pyc` / `__pycache__` artefacts**
in the target repository — temp-repo fixtures assert byte-identical
trees and a stray cache directory would be a real-world mutation.

A syntax failure produces `error_code = PATCH_APPLIED_SYNTAX_FAILED`,
writes the failing file(s) and the compile error into
`PatchResult.verification`, and **leaves the applied change on
disk**. The surrounding DPMtF policy — never the patcher — decides
whether to revert (spec §20).

### Layer 2 — configured commands (opt-in)

When the request carries a `verification.commands` list, each command
is executed verbatim with `shell=True` and `cwd = repo_path`. The
patcher captures exit code, the last 4096 bytes of stdout, and the
last 4096 bytes of stderr — **verbatim, never interpreted**
(spec §21).

```json
"verification": {
  "commands": [
    "python3 -m pytest tests/test_x.py -q",
    "ruff check path/to/file.py"
  ]
}
```

A nonzero exit code on a configured command produces
`error_code = PATCH_APPLIED_TEST_FAILED`. Commands run in request
order; the pipeline stops after the first nonzero exit and reports
the remaining commands as `"status": "skipped"`. The applied change
is **left on disk** — the orchestrator decides what to do.

When `verification` is missing or empty, no command execution
happens; the syntax check still runs.

### `verification` dict shape in PatchResult

```json
{
  "syntax": "passed",
  "commands": [
    {
      "command": "python3 -m pytest -q",
      "status": "executed",
      "exit_code": 0,
      "stdout_tail": "...last 4096 bytes of stdout...",
      "stderr_tail": "...last 4096 bytes of stderr..."
    }
  ]
}
```

When a configured command fails:

```json
{
  "syntax": "passed",
  "commands": [
    {"command": "...", "status": "executed", "exit_code": 3,
     "stdout_tail": "...", "stderr_tail": "..."},
    {"command": "...", "status": "skipped"}
  ],
  "command_failures": [
    {"command": "...", "exit_code": 3, "stderr_tail": "..."}
  ]
}
```

---

## 6. Audit metadata (spec §30)

Every PatchResult carries a machine-readable `audit` dict. The
patcher populates it through existing mechanisms — no new logging
subsystem, no new files written by the patcher. Callers persist it
via existing DPMtF run/artifact mechanisms.

```json
{
  "started_at": "2026-08-15T19:42:11.123456Z",
  "ended_at":   "2026-08-15T19:42:11.987654Z",
  "patch_mode": "structural_python",
  "engine":     "libcst",
  "repository": "/abs/path/to/repo",
  "base_revision": "16b0eec60c494b0b182bb6df2c6b3d5b65cda455",
  "repo_was_clean_at_invocation": true,
  "files_requested": ["lib.py"],
  "files_changed":   ["lib.py"],
  "operations_requested": 1,
  "operations_applied":   1,
  "resulting_diff_hash":  "<sha256>",
  "resulting_diff_empty": false,
  "resulting_diff_length": 187,
  "verification_status":  "passed",
  "final_status":         "applied",
  "final_error_code":     "PATCH_APPLIED"
}
```

Empty-diff convention: when an apply produces no diff (e.g. an
idempotent `add_import` second run, or a unified-diff request whose
diff happens to be byte-identical to the on-disk content),
`resulting_diff` is `null`, `resulting_diff_empty` is `true`, and
`resulting_diff_hash` is `sha256("") =
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Stable, unambiguous.

Audit fields and where they originate:

* `started_at` / `ended_at` — captured at invocation, UTC ISO-8601
  with `Z` suffix, microsecond precision.
* `patch_mode`, `engine` — copied from the request and the engine
  that handled it.
* `repository`, `base_revision`, `repo_was_clean_at_invocation` —
  captured from `git rev-parse HEAD` and `git status --porcelain`.
* `files_requested` — for `structural_python`, the unique `file`
  fields from `operations`; for `unified_diff`, the paths named in
  `diff --git` headers.
* `files_changed`, `operations_applied`, `resulting_diff_*` — from
  the engine's own work.
* `verification_status` — `"passed"` / `"failed"` / `"not_run"`,
  matching `PatchResult.verification` semantics.
* `final_status`, `final_error_code` — copied from the PatchResult
  itself.

---

## 7. Status

Phases 1E–1F (per spec §38) are delivered as follows:

* `implementation_mode = deterministic_patch` wiring into bridge
  tables, role definitions, and step configuration — DELIVERED.
  Storage: `scripts/db/052_implementation_mode.sql` (+ matching
  rollback file `scripts/db/rollbacks/052_implementation_mode_rollback.sql`).
  Resolution and dispatch injection:
  `scripts/bridgeV002/patch_mode.py` (`resolve_implementation_mode`,
  `apply_mode_block`, and the `PATCH_MODE_BLOCK` constant).
* Role-governance text telling implementers to prefer
  `structural_python` operations — DELIVERED at
  `docs/governance-templates-v2/102_DETERMINISTIC_PATCH_MODE.md`.
  The `PATCH_MODE_BLOCK` references this file by path; roles
  operating under `deterministic_patch` mode inherit the four §26
  rules from it.
* A live-flow integration test that exercises an existing DPMtF flow
  end-to-end with the patcher wired in — DELIVERED at
  `tests/test_patcher_flow_integration.py`. The tests build scratch
  git repositories under `tmp_path` and a scratch SQLite DB with the
  052 schema; the deterministic_patch leg drives
  `DeterministicPatcher().apply` through a JSON-decoded
  `PatchRequest`, and the direct leg proves the same scenario under
  the default mode produces the same on-disk file content and a
  byte-identical dispatched prompt.

### Configuration surface

Three bridge-table columns hold the opt-in switch. Each accepts
`'direct'`, `'deterministic_patch'`, or NULL (inherit):

* `bridge_flows.implementation_mode` (flow-level override)
* `bridge_flow_steps.implementation_mode` (step-level override)
* `bridge_roles.implementation_mode` (role-level override)

The precedence is **`role > step > flow > global default 'direct'`**:
the first non-NULL value in `(role_row, step_row, flow_row)` wins; if
all three are NULL (or the rows are missing), the global default
`'direct'` is used. Empty strings at any level are also treated as
unset. An invalid stored value raises `ValueError` from
`patch_mode.py` naming the table and the identifying key.

### Outstanding deferred work

* Spec §12 Phase-2 LibCST operations: `remove_function`,
  `remove_method`, `modify_call_argument`, `add_call_argument`,
  `remove_call_argument`, `replace_decorator`, `add_decorator`,
  `remove_decorator`, `insert_statement`, `replace_class_attribute`.

---

## 8. Python facade — quick reference

For callers that prefer Python to the CLI:

```python
from patcher import DeterministicPatcher, PatchRequest

patcher = DeterministicPatcher()

req = PatchRequest(
    repo_path="/path/to/repo",
    patch_mode="structural_python",
    operations=[
        {"operation": "add_import", "file": "lib.py", "module": "os"}
    ],
    verification={"commands": ["python3 -m pytest -q"]},
)

result = patcher.apply(req)
if result.error_code == "PATCH_APPLIED":
    print("applied", result.files_changed)
else:
    print("failed", result.error_code, result.error)
    print("verification:", result.verification)
    print("audit:", result.audit)
```

The same `PatchRequest` works for `patcher.check(req)` (dry-run,
never writes).