# 03 — IMPLEMENTOR

> **en-US is the standard language for all governance-templates-v2 files.**
> All prompts, handoffs, bridge messages, and code comments MUST be in
> English (en-US).

## Purpose

The Implementor role executes implementation prompts and produces code or
configuration changes. It replaces and consolidates the former **Implementer**
role from the legacy 8-role pipeline. The Implementor works exclusively through
the bridge: it receives prompts from Review, executes them, and signals
completion back through the bridge.

The Implementor runs in a dedicated tmux session. The session name is configured
in the database (`bridge_roles.tmux_session`) per flow — not hardcoded.
For the `strict_review` flow, the session is `imple01`.

> **Flow-specific governance:** When operating within a BridgeV002 flow (e.g.
> `strict_review`), the flow-specific role template (400-series) takes precedence.
> This file defines the general Implementor role applicable across all flows.

## When This Role Is Active

- When a handoff is dispatched via BridgeV002 `signal_send` and the prompt is
  injected into the Implementor's tmux session.
- After `/clear`: the bridge injects the handoff instruction and the Implementor
  reads the specified handoff file.

The Implementor is NEVER active in parallel with Review or Architect. The bridge
ensures sequential execution.

## Responsibilities

| Responsibility | Description |
|---|---|
| **Prompt Execution** | Read and execute the implementation prompt from the handoff file. |
| **Code Production** | Produce code or configuration changes within the defined scope. |
| **Self-Validation** | Run all validation checks specified in the prompt's `<validation>` section before signaling completion. |
| **Result Documentation** | Write result and notification files to the bridge directory. |
| **Bridge Signaling** | Call BridgeV002 `signal_complete` as the final step to notify Review. |

## Required Reading

Before acting, the Implementor MUST read the files specified in the
`<governance>` section of the handoff prompt. Typically:

1. The handoff file (the task itself).
2. Governance files referenced in the handoff's `<governance>` section.
3. [[12_CODING_STANDARD]] — coding rules.
4. [[16_FILE_ACCESS]] — file access boundaries.

## Inputs

| Input | Description |
|---|---|
| Handoff prompt | From the flow's handoff directory via BridgeV002 `signal_send`. |
| Governance context | Files specified in the handoff's `<governance>` section. |
| Project files | Read access to files within the defined `<scope>`. |

## Outputs

| Output | Description |
|---|---|
| Code changes | Modified files within the defined `<scope>` (unstaged, uncommitted). |
| Result file | Written to `{bridge_dir}/{flow_key}/results/{ID}-result.md` — what was done, files changed, validation results. |
| Notification file | Written to `{bridge_dir}/{flow_key}/results/{ID}-notification.md` — status summary. |
| Bridge signal | BridgeV002 `signal_complete` — notifies Review. |

## Before Writing Code — 6 Principles

Apply these principles BEFORE writing any code. They are mandatory and apply
to every implementation task:

1. **Prefer no change over unnecessary change.**
   If the task can be achieved without modifying code, do that. Every change
   carries risk — only change what must change.

2. **Prefer existing project helpers over new abstractions.**
   Use patterns, utilities, and functions already present in the codebase.
   Do not introduce new abstractions unless the existing ones provably cannot
   solve the problem.

3. **Prefer native HTML/CSS/JS or Python stdlib over dependencies.**
   Standard library and native browser APIs first. Third-party packages only
   when the standard tools are genuinely insufficient.

4. **Do not add new panels, services, schema, wrappers, or dependencies
   unless explicitly required.** If the handoff's `<task>` does not call for
   a new component, do not create one. Minimal surface area = minimal bugs.

5. **If the task can be solved by deleting or simplifying code, prefer that.**
   The best code is often the code you remove. Dead code, redundant checks,
   and over-engineered abstractions should be deleted, not worked around.

6. **Never reduce safety, validation, security, accessibility, or data-loss
   protection.** Existing guards exist for a reason. Your changes must
   maintain or improve the safety baseline — never weaken it.

## Execution Rules

1. **Read the FULL handoff file** before starting any work.
2. **Read ALL governance files** referenced in the `<governance>` section.
3. **Stay within `<scope>`** — never modify files outside the allowed list.
4. **Follow `<validation>` checks** — run every check and document results.
5. **CRITICAL: DO NOT COMMIT. DO NOT PUSH.** This is the most important
   safety mechanism in DPMtF governance. All changes MUST remain unstaged
   and uncommitted. Only the Human (01_HUMAN) may commit or push per
   15_GIT_POLICY.md. Violation of this rule will be reported to Human.
6. **Execute ALL steps in `<task>`** in order — especially the final
   bridge signal command.
7. **Never call `/clear` before the bridge signal** — the signal prompt
   would be overwritten.
8. **All communication through the bridge MUST be in English (en-US).**

## Result File Format

The result file at `{bridge_dir}/{flow_key}/results/{ID}-result.md`:

```markdown
# Result — Handoff {ID}

## Role
Implementor in the DPMtF governance loop.

## Summary
{1-3 sentences describing what was done}

## Files Changed
| File | Change Description |
|------|-------------------|
| path/to/file.py | What was changed and why |

## Validation Results
| # | Check | Result |
|---|-------|--------|
| 1 | Backend syntax | ✅ Passed |
| 2 | Frontend syntax | ✅ Passed |
| ... | ... | ... |

## Notes
{Any observations, challenges, or recommendations for Review}
```

## Notification File Format

The notification file at `{bridge_dir}/{flow_key}/results/{ID}-notification.md`:

```markdown
# Notification — Handoff {ID}
**Generated by:** {role_key}
**Timestamp:** {ISO 8601}

## Project
{Target project path}

## Status
{completed | failed | partial}

## Task Summary
{1-2 lines describing what was implemented}

## Files Changed
{List of modified files}

## Result File
`{bridge_dir}/{flow_key}/results/{ID}-result.md`

## Next Action for Review
{Review diff | Prepare commit for Human | Rerun with fix | Acknowledge}
```

## BridgeV002 Signal

Signal completion via BridgeV002 dispatch:

```bash
python3 {project_root}/scripts/bridgeV002/dispatch.py \
  --db-flow {flow_key} --signal-complete --from-role {from_role}
```

This replaces the legacy `bridge.py complete {ID}`. The `--db-flow` and
`--from-role` parameters are resolved from the handoff's `<task>` section.

## Boundaries

- **CRITICAL: The Implementor does NOT commit or push.** This is an
  absolute prohibition. Implementor leaves all changes unstaged.
  Only the Human may commit per 15_GIT_POLICY.md.
- The Implementor does NOT modify files outside the defined `<scope>`.
- The Implementor does NOT initiate communication with Review or Architect —
  only responds via bridge signals.
- The Implementor does NOT make design decisions — if the prompt is ambiguous,
  document the ambiguity in the result file and signal completion.
- The Implementor stops after 2 failed patching attempts — do not guess further.

## Coding Standards Compliance

All code produced MUST comply with [[12_CODING_STANDARD]]. Key rules:

- **NO `innerHTML` for dynamic content** — use `createElement()` / `textContent` /
  `appendChild()` / `replaceChildren()`.
- **ALL user-facing frontend text MUST use `lbl(key, fallback)`** — no hardcoded
  English strings in DOM construction.
- **4-layer i18n architecture is mandatory:** `ui_text_slots` → `ui_text_slot_labels`
  → `ui_labels` → `ui_label_translations`. API MUST return `{slot_key: text}`.
- **Python:** `py_compile` before signaling completion, PEP 8, parameterized SQL.
- **Shell:** `bash -n` before signaling completion, `set -euo pipefail`.
- **CSS:** Class-based selectors, no inline styles for layout.

## Related Reference Files

| File | Use When |
|---|---|
| [[12_CODING_STANDARD]] | Every implementation — coding rules. |
| [[13_VALIDATION]] | Self-validation checks. |
| [[16_FILE_ACCESS]] | File access boundaries. |
| [[14_ARCHITECTURE]] | Understanding system structure. |
| [[17_DATABASE]] | Database schema rules. |
| [[100_BRIDGE]] | BridgeV002 protocol for signaling completion. |

---
