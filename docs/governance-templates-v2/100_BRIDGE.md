# 100 — BRIDGE PROTOCOL (BridgeV002)

> **en-US is the standard language for all governance-templates-v2 files.**
> All prompts, handoff files, bridge messages, and inter-role communication
> MUST be in English (en-US). The sole exception is 01_HUMAN.md — the Human
> may communicate in any language, but prompts forwarded through the bridge
> MUST be translated to English.

## Purpose

Defines the BridgeV002 protocol for communication between the non-Human roles
(Architect, Implementor, Review). BridgeV002 is a **fully database-driven**
dispatch system integrated into DPMtF-WebUI. It replaces the legacy
`claude-bridge/bridge.py` with flow-based, convention-driven role transitions.

## When to Use

- **Architect:** When generating implementation prompts for dispatch.
- **Review:** When dispatching prompts, receiving results, and escalating.
- **Implementor:** When reading handoff prompts and signaling completion.

---

## BridgeV002 Architecture

BridgeV002 is part of the DPMtF-WebUI repository — not a separate project.
All configuration lives in the database; there are zero INI dependencies.

| Component | Location | Purpose |
|-----------|----------|---------|
| `dispatch.py` | `scripts/bridgeV002/dispatch.py` | Universal dispatcher — four signals: `send`, `complete`, `escalation`, `answer`. |
| `bridge_lib.py` | `scripts/bridgeV002/bridge_lib.py` | Database lookup functions, convention resolution, deliverable validation. |
| `post-dispatch-common.py` | `scripts/bridgeV002/post-dispatch-common.py` | Convention-agnostic post-dispatch: validate deliverable + stop from_role model. |
| `role_setup.py` | `scripts/bridgeV002/role_setup.py` | Ollama model pull for role session preparation. |
| `role_teardown.py` | `scripts/bridgeV002/role_teardown.py` | Ollama model stop + VRAM cleanup. |
| `bridge_roles` | Database table | Role definitions: tmux session, model, governance file, role type. |
| `bridge_flows` | Database table | Flow definitions: step sequence, auto-complete, default flow. |
| `bridge_flow_steps` | Database table | Step definitions: from_role → to_role, deliverable dir/pattern, convention rule. |
| `bridge_convention_rules` | Database table | Convention templates: content template, validation schema, dir/pattern defaults. |
| `bridge_scripts` | Database table | Script registry: path, stage (pre/post/both), required parameters. |

### Deliverable Directories (per flow)

Each flow defines its own deliverable directories via step configuration.
Example for `strict_review`:

```
{bridge_dir}/
├── handoffs/         ← archi01 writes handoff files
├── results/          ← imple01 writes implementation results
├── reviews/          ← review01 writes technical reviews
├── verdicts/         ← review02 writes final verdicts + commit messages
├── escalations/      ← review01/review02 write escalation questions
├── architecttoreview/ ← archi01 writes escalation responses
└── trace.log         ← append-only dispatch log
```

---

## BridgeV002 Signals

Four signals replace the legacy `bridge.py` commands:

| Signal | CLI | From → To | Action |
|--------|-----|-----------|--------|
| **signal_send** | `dispatch.py --db-flow {flow} --signal-send --from-role {from} --to-role {to}` | Review → Implementor | Stop+reload target model, inject handoff prompt. |
| **signal_complete** | `dispatch.py --db-flow {flow} --signal-complete --from-role {from}` | Implementor → Review | Validate deliverable, inject callback prompt, stop from_role model. |
| **signal_escalation** | `dispatch.py --db-flow {flow} --signal-escalation --from-role {from} --to-role {to}` | Review → Architect | Inject escalation question. |
| **signal_answer** | `dispatch.py --db-flow {flow} --signal-answer --from-role {from} --to-role {to}` | Architect → Review | Inject answer callback. |

All signals require `--db-flow` (the flow key). Handoff ID is auto-generated
via `get_next_id_for_flow()` if not provided explicitly.

---

## No-Kill Dispatch Protocol

BridgeV002 uses **no-kill mode** — tmux sessions are persistent. Context is
cleared by stopping the Ollama model, not by killing tmux sessions.

### Golden Rule Sequence (signal_complete)

```
1. Load flow + steps from DB
2. Find current step (by step_key or from_role)
3. Build payload from step + convention rule
4. Load to_role from DB → get tmux_session
5. Check session_alive(to_role) — fail if not running
6. Verify deliverable file exists (written by completing role)
7. Validate deliverable against convention schema (if validation_required)
8. Resolve content_template placeholders ({handoff_id}, {source_role}, ...)
9. Prepend governance_file reference for target role
10. Inject callback prompt into to_role's tmux session (tool-aware)
11. Post-dispatch: stop from_role's Ollama model (VRAM cleanup)
12. Update current.md symlink + log to trace.log
13. If auto_complete_enabled: chain to next step
```

### Human Recipients (G1)

When `to_role` has `role_type = "human"`, dispatch skips tmux injection
entirely. The deliverable file is written to disk for Human to read manually.

### Tool-Aware Injection

| Tool | Detection | Injection Method |
|------|-----------|-----------------|
| **OpenCode** | `pane_current_command` contains "opencode" | `tmux load-buffer` + `paste-buffer` with soft-clear preamble |
| **Claude Code** | `pane_current_command` contains "node" or "claude" | `tmux load-buffer` + `send-keys Enter` |

---

## Flow-Based Role Transition

### Layer 1: Implementation Loop (example: strict_review)

```
Step 1: archi01 → imple01   [handoff]
  Architect writes handoff → dispatch injects prompt → Implementer executes

Step 2: imple01 → review01  [technical_review]
  Implementer writes result → dispatch injects callback → Review01 validates

Step 3: review01 → review02 [verdict]
  Review01 writes technical review → dispatch injects callback → Review02 validates

Step 4: review02 → human    [human_delivery]
  Review02 writes verdict → Human reads manually (no tmux injection)
```

Each step is configured in `bridge_flow_steps` with:
- `from_role` / `to_role` — which roles transition
- `rule_key` — which convention rule governs the content template
- `deliverable_dir` / `deliverable_pattern` — where files are written
- `validation_required` — whether the deliverable is schema-validated before dispatch

### Layer 2: Escalation Loop

```
Review01 or Review02                  Architect
    │                                     │
    │ signal_escalation                   │
    │ (writes question file first)        │
    ├────────────────────────────────────→│
    │                                     │ reads question, makes decision
    │                                     │ writes response
    │          signal_answer              │
    │←────────────────────────────────────┤
    │                                     │
    │ continues validation                │
```

---

## Handoff Prompt Format

This is the CRITICAL artifact. The handoff prompt MUST contain all information
the Implementor needs to execute the task without ambiguity. All text MUST be
in English (en-US).

### Required XML Sections

```markdown
<role>You are Implementor in the DPMtF governance loop. Your role is defined
in {project_root}/docs/governance-templates-v2/03_IMPLEMENTOR.md.
Read it now before proceeding.</role>

<handoff_id>{ID}</handoff_id>

<project>{project_path}</project>

<context>
{WHY this task exists — what problem it solves, what phase it belongs to.
This gives the Implementor understanding of purpose, not just steps.}
</context>

<governance>
Read and apply these governance files BEFORE starting:
- {project_root}/docs/governance-templates-v2/12_CODING_STANDARD.md
- {project_root}/docs/governance-templates-v2/16_FILE_ACCESS.md

Key rules extracted:
1. NO innerHTML for dynamic content — use createElement()/textContent.
2. ALL user-facing text MUST use lbl(key, fallback) — no hardcoded English strings.
3. Python: py_compile before signaling completion, parameterized SQL.
4. 4-layer i18n is mandatory: slots → bindings → labels → translations.
</governance>

<task>
{Specific, step-by-step instructions. Each step must be concrete and
verifiable. Include file paths, function names, and expected outcomes.}

Step 1: {First action}
Step 2: {Second action}
...

When ALL steps are complete, execute the bridge signal:

1. Write result file to:
   {bridge_dir}/implementertoreview/{ID}-result.md
   Format per 03_IMPLEMENTOR.md — include Summary, Files Changed,
   Validation Results table.

2. Write notification file to:
   {bridge_dir}/implementertoreview/{ID}-notification.md
   Format per 03_IMPLEMENTOR.md — Status, Task Summary, Files Changed,
   Next Action.

3. SIGNAL completion (NO /clear before this):
   python3 {project_root}/scripts/bridgeV002/dispatch.py \
     --db-flow {flow_key} --signal-complete --from-role {from_role}
</task>

<scope>
Files you MAY modify:
- {/full/path/to/allowed/file1}
- {/full/path/to/allowed/file2}

Files you MUST NOT touch:
- {/full/path/to/forbidden/file1}
- {project_root}/ (Father project)
- /home/svend/ENO/ (other Child project)
</scope>

<validation>
Before signaling completion, run these checks yourself:
1. python3 -m py_compile {file} — must pass
2. node --check {file} — must pass
3. git diff --stat — verify only allowed files changed
4. grep -RIn "innerHTML" static templates — must be empty
5. {Other phase-specific checks}
</validation>

<constraint>
DO NOT COMMIT. Leave all changes unstaged.
Execute ALL steps in <task> — especially step 3 (bridge signal).
If you encounter an ambiguity, document it in the result file — do NOT guess.
Stop after 2 failed patching attempts.
</constraint>
```

### Required Content Checklist

Before dispatching a handoff, Review MUST verify the handoff contains:

| # | Required Element | Purpose |
|---|-----------------|---------|
| 1 | `<role>` | Tells Implementor which role definition to read. |
| 2 | `<handoff_id>` | Unique identifier for traceability. |
| 3 | `<project>` | Full path to the target project. |
| 4 | `<context>` | WHY this task exists — purpose and phase context. |
| 5 | `<governance>` | Governance files to read + extracted key rules (2-4 rules). |
| 6 | `<task>` | Step-by-step instructions INCLUDING bridge signal as final step. |
| 7 | `<scope>` | Allowed files (full paths) and forbidden files (full paths). |
| 8 | `<validation>` | Concrete self-validation checks with commands. |
| 9 | `<constraint>` | "DO NOT COMMIT" + "Execute ALL steps" + ambiguity/escalation rules. |

---

## Escalation Handoff Format

### Review → Architect Escalation

```markdown
<role>You are Architect in the DPMtF governance loop. Your role is defined
in {project_root}/docs/governance-templates-v2/02_ARCHITECT.md.
Read it now before proceeding.</role>

<handoff_id>{ID}</handoff_id>

<escalation_from>{from_role}</escalation_from>

<context>
{What Review was working on — project, phase, task, current state.}
</context>

<question>
{The specific question — what Review cannot decide alone.}
</question>

<options>
- {Option A: Description and implications}
- {Option B: Description and implications}
- {Option C: Description and implications}
</options>

<governance>
Read and apply:
- {project_root}/docs/governance-templates-v2/02_ARCHITECT.md
- {project_root}/docs/governance-templates-v2/21_ALIGNMENT.md
- {project_root}/docs/governance-templates-v2/14_ARCHITECTURE.md
</governance>

<task>
1. Read <context> and <question> — understand what Review needs.
2. Consult relevant governance files for overview.
3. Make a decision and write response to:
   {bridge_dir}/architecttoreview/{ID}-response.md
   Format:
   ## Decision
   {Clear, unambiguous decision}
   ## Rationale
   {Why this decision — context from cross-project overview}
   ## Next Steps for Review
   {Concrete instructions for what Review should do now}
   ## Affected Projects/Files
   {List if relevant}
4. Write NOTIFICATION to:
   {bridge_dir}/architecttoreview/{ID}-notification.md
5. SIGNAL completion:
   python3 {project_root}/scripts/bridgeV002/dispatch.py \
     --db-flow {flow_key} --signal-answer --from-role {from_role} --to-role {to_role}
</task>

<constraint>
ONLY answer the question. Do not start new implementations.
Execute ALL steps in <task> — especially step 5 (bridge signal).
All response text MUST be in English (en-US).
</constraint>
```

---

## Sequential Execution Protocol

The bridge guarantees that roles do not run in parallel:

1. **One active role at a time:** When Review dispatches to Implementor via
   `signal_send`, Review WAITS. Implementor is the only active role.
2. **Signal-based activation:** Roles are activated by bridge-injected prompts,
   not by polling. A role does nothing until it receives a signal.
3. **No background work:** When Implementor signals completion via
   `signal_complete`, Implementor stops. Review resumes.
4. **Escalation is synchronous:** When Review escalates to Architect,
   Review WAITS. Architect answers, then Review resumes.
5. **No-kill enforcement:** Post-dispatch `ollama stop` clears the predecessor's
   model from VRAM, ensuring the predecessor cannot continue work.

### Violation Prevention

| Violation | Prevention |
|-----------|------------|
| Implementor continues after signaling | `signal_complete` injects into Review's session — Implementor receives no further prompts until next `signal_send`. |
| Review starts new work while Implementor runs | Review's session receives no prompt until `signal_complete` injects one. |
| Architect and Review both active | Architect is only activated by `signal_escalation` and deactivates after `signal_answer`. |
| Implementor commits code | Constraint in every handoff: "DO NOT COMMIT". Enforced by Review validation. |

---

## Convention Rules

Convention rules govern the content template injected at each step transition.
They are stored in `bridge_convention_rules` and resolved at runtime.

| Rule Key | Step Type | Used For |
|----------|-----------|----------|
| `handoff` | Handoff | Architect → Implementer: initial task dispatch |
| `technical_review` | TechnicalReview | Implementer → Review Layer 1: technical validation |
| `verdict` | Verdict | Review Layer 1 → Review Layer 2: governance validation |
| `human_delivery` | HumanDelivery | Review Layer 2 → Human: final verdict delivery |
| `callback` | Callback | Generic callback (used by non-strict_review flows) |
| `escalation` | Escalation | Review → Architect: architectural question |
| `verdict_feedback` | VerdictFeedback | Architect feedback on verdict |

Each convention defines:
- `dir_template` / `pattern_template` — default deliverable location
- `content_template` — the prompt injected into the next role's tmux session
- `validation_schema` — required XML sections in the deliverable
- `error_template` — error message if dispatch fails

---

## Security Rules

1. **Implementor NEVER commits** — constraint in every handoff.
2. **Review ALWAYS validates before commit proposal** — no automatic commit.
3. **Human ALWAYS authorizes commit** — Human Approval Gate.
4. **Rollback always possible** — `git reset --hard <baseline>` if result rejected.
5. **No-kill mode** — `ollama stop` clears context between role transitions.
   No tmux sessions are killed or created during dispatch.
6. **Handoff IDs are unique and sequential per flow** — auto-generated via
   `get_next_id_for_flow()`.
7. **trace.log is append-only** — never edit existing entries.
8. **`signal_complete` and `signal_answer` called WITHOUT `/clear`** —
   otherwise the prompt is overwritten before the receiver sees it.
9. **Architect escalation is read-only** — Architect only makes decisions,
   never implements. Implementation always goes through the
   Implementor → Review loop.
10. **No direct Architect → Implementor communication** — all communication
    goes through the Review layer.
11. **Human recipients skip tmux injection** — `role_type = "human"` means
    the dispatch returns success after writing the deliverable file.
12. **All database-driven** — zero hardcoded paths, zero INI dependencies.
    Role config, flow steps, and convention templates are resolved from
    the database at runtime.

---
