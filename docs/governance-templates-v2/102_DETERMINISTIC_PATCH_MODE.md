# 102 — Deterministic Patch Mode

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines the governance that binds any implementation role operating under the
Deterministic Patcher mode — the bridge configuration
`implementation_mode = 'deterministic_patch'`. This file is referenced by the
injected instruction block (the constant `PATCH_MODE_BLOCK` in
`scripts/bridgeV002/patch_mode.py`) and carries the rules of operation a
dispatches the model inherits from the moment the mode is on.

The mode is strictly additive (spec §5, §41): enabling it for a flow changes
ONLY the prompt the implementer receives and the route by which their work
reaches the repository. The dispatch, the review flow, and the verdict
machinery are unchanged.

---

## 1. What the Mode Is

Deterministic patch mode is an **opt-in implementation_mode** in which
implementation roles route repository changes through the Deterministic
Patcher (the `patcher/` package, see
`docs/specs/DETERMINISTIC_PATCHER_SPEC.md`) instead of editing files
directly.

The mode is resolved from the bridge tables with the precedence

```
    role > step > flow > global default 'direct'
```

The first non-NULL value in `(role_row, step_row, flow_row)` wins; absent or
NULL at every level inherits the global default `'direct'`. Storage is
provided by migration `scripts/db/052_implementation_mode.sql`; resolution
and prompt injection live in `scripts/bridgeV002/patch_mode.py`.

**Nothing is opted in by default.** After migration 052 applies, every
existing flow, step and row in the bridge tables resolves to `direct` until
a Human intentionally opts a level in.

---

## 2. The Four Rules (spec §26)

A role operating under this mode MUST follow these four rules. They are
governance, not advice: violation makes the role's output non-conformant
regardless of whether the resulting repository state happens to look
correct.

1. **Do not directly modify repository files when the requested change can
   be performed through the Deterministic Patcher.** When the patcher
   supports the change, the route is the patcher — direct edits are a
   governance failure, not a stylistic choice.

2. **Prefer `structural_python` operations for supported Python
   transformations.** LibCST operations are the deterministic, idempotent
   path for the seven §37 operations (`add_import`, `remove_import`,
   `replace_function`, `add_function`, `replace_method`, `add_method`,
   `replace_assignment`). Use them whenever the change fits.

3. **Use `unified_diff` when the change cannot be represented with
   available structural operations.** The patcher's `git_apply` engine
   exists for exactly this case. The role's job is to author the diff,
   not to apply it.

4. **Never manually repair a rejected patch outside the normal DPMtF
   execution flow.** A patcher rejection is a structured signal
   (`PATCH_INVALID`, `PATCH_CONFLICT`, `PATCH_PATH_REJECTED`,
   `PATCH_TARGET_NOT_FOUND`, etc.). When the patcher says no, the role
   returns control to the flow — supervisor / retry / review —
   exactly as for any other failure. The patcher will NEVER invoke an
   LLM on its own behalf to repair its own output (spec §23); the role
   MUST NOT compensate for that by silently editing files after a
   rejection either.

---

## 3. The Architectural Boundary

This is the property the mode preserves, and the one reviewers will check.

```
    LLM (the role)                Deterministic Patcher (the tool)
    ─────────────                 ────────────────────────────────
    decides WHAT changes          decides and performs HOW
    authors a PatchRequest        validates, applies, verifies, audits
    reasons about code structure  executes mutations on disk
    picks structural vs unified    never calls an LLM (spec §23)
                                  never reasons about correctness
                                  (spec §22, §23)
```

The LLM authors the `PatchRequest` (a JSON-shaped intent — see
`docs/specs/DETERMINISTIC_PATCHER_USAGE.md` §1 and §8). The Deterministic
Patcher validates the request, executes the mutation, runs the configured
verification pipeline and produces the audit metadata. The patcher's job
ends at the PatchResult. The existing DPMtF review flow remains
authoritative over the resulting diff — the patcher does NOT replace
review (spec §22), and it MUST NOT be reasoned about as a replacement for
correctness reasoning (spec §45).

Supervisor, Architect, Reviewer, Verifier and the verdict machinery are
unaffected by this mode. The mutation path is what changes; the roles and
their governance around the patch are unchanged.

---

## 4. How the Mode Reaches a Role

The bridge does not edit role files to turn the mode on. Instead,
`scripts/bridgeV002/patch_mode.py:resolve_implementation_mode` resolves the
effective mode for `(flow, step, role)` against the bridge tables at
dispatch time, and `apply_mode_block` conditionally appends the
`PATCH_MODE_BLOCK` constant to the composed prompt before it is injected
into the role's tmux session.

Two consequences a role can rely on:

- When the resolved mode is `deterministic_patch`, the role's dispatched
  prompt contains the `PATCH_MODE_BLOCK` as a literal block. The four
  rules above are inside it, plus the pointer back to this file. Reading
  this file is a precondition for acting under the mode.
- When the resolved mode is anything other than `deterministic_patch`
  (i.e. `'direct'`, or nothing configured, or a pre-migration database
  without the column), dispatched prompts are byte-identical to the
  pre-mode prompt — same string object, no normalization (see
  `apply_mode_block`'s contract in `scripts/bridgeV002/patch_mode.py`).

The mode is therefore invisible unless a Human opts it in. A role that
sees the `PATCH_MODE_BLOCK` in its dispatched prompt is operating under
this governance and is bound by all four rules above. A role that does
not see it operates under its role-specific governance unchanged.

---

## 5. What This File Does NOT Cover

This file governs the implementer-side behavior of the mode. It does
NOT cover:

- The bridge-side resolution and injection helpers — those are
  `scripts/bridgeV002/patch_mode.py` (per
  `docs/governance-templates-v2/100_BRIDGE.md`).
- The deterministic mutation pipeline itself — that is the patcher
  package (`patcher/*.py`) per the product specification.
- The patcher's verification pipeline, audit metadata, CLI, or schema —
  see `docs/specs/DETERMINISTIC_PATCHER_USAGE.md`.
- Live acceptance decisions. **No flow, step or role in the production
  database is opted into `deterministic_patch` at the close of the run
  that introduced this file** (spec §5/§41; binding during the run).
  Enabling the mode for a live flow is a Human decision made afterwards.

A role pointing at this file is responsible for the implementer
behavior the four rules prescribe; nothing else.
