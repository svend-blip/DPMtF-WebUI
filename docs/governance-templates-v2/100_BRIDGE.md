# 100 — BRIDGE PROTOCOL (BridgeV002)

> **en-US is the standard language for all governance-templates-v2 files.**
> All prompts, handoff files, bridge messages, and inter-role communication
> MUST be in English (en-US). The sole exception is 01_HUMAN.md — the Human
> may communicate in any language, but prompts forwarded through the bridge
> MUST be translated to English.

## Purpose

Defines the BridgeV002 protocol for communication between roles in a flow.
BridgeV002 is a **fully database-driven** dispatch system integrated into
DPMtF-WebUI. It replaces the legacy `claude-bridge/bridge.py` with
flow-based, convention-driven role transitions.

## When to Use

- **Architect:** When generating handoff prompts for dispatch.
- **Implementer:** When reading handoff prompts and signaling completion.
- **Review:** When validating deliverables and producing verdicts.
- **Human:** When reading verdicts and deciding on commits.

---

## BridgeV002 Architecture

BridgeV002 is part of the DPMtF-WebUI repository — not a separate project.
All configuration lives in the database; there are zero INI dependencies.

| Component | Location | Purpose |
|-----------|----------|---------|
| `dispatch.py` | `scripts/bridgeV002/dispatch.py` | Universal dispatcher — four signals: `send`, `complete`, `escalation`, `answer`. |
| `bridge_lib.py` | `scripts/bridgeV002/bridge_lib.py` | Database lookup functions, convention resolution, deliverable validation. |
| `post-dispatch-common.py` | `scripts/bridgeV002/post-dispatch-common.py` | Convention-agnostic post-dispatch: validate deliverable + stop from_role model. |
| `start_tmuxflow.py` | `scripts/bridgeV002/start_tmuxflow.py` | Create tmux sessions for all roles in a flow. |
| `start_coding.py` | `scripts/bridgeV002/start_coding.py` | Execute start_cmd for all roles in a flow. |
| `stop_tmuxflow.py` | `scripts/bridgeV002/stop_tmuxflow.py` | Kill all tmux sessions for a flow. |
| `attach_tmux.py` | `scripts/bridgeV002/attach_tmux.py` | Build viewer session with linked windows for all flow roles. |
| `bridge_roles` | Database table | Role definitions: tmux session, start_cmd, model, governance file, role type. |
| `bridge_flows` | Database table | Flow definitions: step sequence, auto-complete, default flow. |
| `bridge_flow_steps` | Database table | Step definitions: from_role → to_role, deliverable dir/pattern, convention rule, pre/post scripts. |
| `bridge_convention_rules` | Database table | Convention templates: content template, validation schema, dir/pattern defaults. |
| `bridge_scripts` | Database table | Script registry: path, stage (pre/post/both), required parameters. |

### Deliverable Directories (per flow)

Each flow defines its own deliverable directories via step configuration in
`bridge_flow_steps.deliverable_dir`. These are **absolute paths** — typically
under `{bridge_dir}/{flow_key}/`.

Example for `strict_review` (`DPMTF_BRIDGE_DIR=/home/<you>/flows`):

```
/home/<you>/flows/strict_review/
├── handoffs/         ← archi01 writes handoff files
├── results/          ← imple01 writes implementation results
├── reviews/          ← review01 writes technical reviews
├── verdicts/         ← review02 writes final verdicts + commit messages
├── escalations/      ← escalation questions + responses
└── trace.log         ← append-only dispatch log
```

> **Note:** The legacy directory names (`implementertoreview/`,
> `reviewtoimplementor/`, `architecttoreview/`) are **no longer used**.
> BridgeV002 uses role-agnostic directory names based on artifact type.

---

## BridgeV002 Signals

Four signals replace the legacy `bridge.py` commands. All signals require
`--db-flow` (the flow key) and `--id` (the handoff ID).

| Signal | CLI | From → To | Action |
|--------|-----|-----------|--------|
| **signal_send** | `dispatch.py --db-flow {flow} --signal-send --from-role {from} --to-role {to} --id {ID}` | Architect → Implementer | Inject handoff prompt into target session. |
| **signal_complete** | `dispatch.py --db-flow {flow} --signal-complete --from-role {from} --id {ID}` | Implementer → Review | Validate deliverable, inject callback prompt, stop from_role model. |
| **signal_escalation** | `dispatch.py --db-flow {flow} --signal-escalation --from-role {from} --to-role {to} --id {ID}` | Review → Architect | Inject escalation question. |
| **signal_answer** | `dispatch.py --db-flow {flow} --signal-answer --from-role {from} --to-role {to} --id {ID}` | Architect → Review | Inject answer callback. |

**Always use `--id`** — the handoff ID from the current handoff. Omitting it
causes the database counter to increment, creating ID mismatches.

---

## No-Kill Dispatch Protocol

BridgeV002 uses **no-kill mode** — tmux sessions are persistent. Context is
cleared by stopping the Ollama model via `post-dispatch-common.py`, not by
killing tmux sessions.

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
11. Post-dispatch: run post_dispatch_script (stops from_role's Ollama model)
12. Update current.md symlink + log to trace.log
13. If auto_complete_enabled: chain to next step
```

### Human Recipients (G1)

When `to_role` has `role_type = "human"`, dispatch skips tmux injection
entirely. The deliverable file is written to disk for Human to read manually.

### Tool-Aware Injection

| Tool | Detection | Injection Method |
|------|-----------|-----------------|
| **OpenCode** | `pane_current_command` contains "opencode" | `tmux load-buffer` + `paste-buffer` + `send-keys Enter` with soft-clear preamble |
| **Claude Code** | `pane_current_command` contains "node" or "claude" | `tmux load-buffer` + `send-keys Enter` |

---

## Flow-Based Role Transition

Each flow defines its own step sequence. The `strict_review` flow is the
primary example — other flows may have fewer or different steps.

### strict_review Flow

```
Step 1: archi01 → imple01   [handoff convention]
  Architect writes handoff → dispatch injects prompt → Implementer executes

Step 2: imple01 → review01  [technical_review convention]
  Implementer writes result → dispatch injects callback → Review01 validates

Step 3: review01 → review02 [verdict convention]
  Review01 writes technical review → dispatch injects callback → Review02 validates

Step 4: review02 → human    [human_delivery convention]
  Review02 writes verdict → Human reads manually (no tmux injection)
```

Each step is configured in `bridge_flow_steps` with:
- `from_role` / `to_role` — which roles transition
- `rule_key` — which convention rule governs the content template
- `deliverable_dir` / `deliverable_pattern` — where files are written (absolute paths)
- `validation_required` — whether the deliverable is schema-validated before dispatch
- `pre_dispatch_script` / `post_dispatch_script` — scripts to run before/after dispatch

### Escalation Loop

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

The handoff prompt MUST contain all information the Implementer needs to
execute the task without ambiguity. All text MUST be in English (en-US).

### Required XML Sections

```markdown
<role>You are {role_key} in the DPMtF {flow_key} flow.
Your role is defined in {project_root}/docs/governance-templates-v2/{governance_file}.
Read it now before proceeding.</role>

<handoff_id>{ID}</handoff_id>

<project>{project_path}</project>

<context>
{WHY this task exists — what problem it solves, what phase it belongs to.
This gives the Implementer understanding of purpose, not just steps.}
</context>

<governance>
Read and apply your role definition BEFORE starting:
- {project_root}/docs/governance-templates-v2/{governance_file}

Key rules from your governance file apply in full.
</governance>

<task>
{Specific, step-by-step instructions. Each step must be concrete and
verifiable. Include file paths, function names, and expected outcomes.}

When ALL steps are complete, execute the bridge signal:

1. Write result file to {bridge_dir}/{flow_key}/results/{ID}-result.md
2. Write notification file to {bridge_dir}/{flow_key}/results/{ID}-notification.md
3. SIGNAL completion:
   python3 {project_root}/scripts/bridgeV002/dispatch.py \
     --db-flow {flow_key} --signal-complete --from-role {from_role} --id {ID}
</task>

<scope>
Files you MAY modify:
- {/full/path/to/allowed/file1}

Files you MUST NOT touch:
- {/full/path/to/forbidden/file1}
</scope>

<validation>
Before signaling completion, run these checks yourself:
1. python3 -m py_compile {file} — must pass
2. node --check {file} — must pass
3. git diff --stat — verify only allowed files changed
4. grep -RIn "innerHTML" static templates — must be empty
</validation>

<constraint>
DO NOT COMMIT. Leave all changes unstaged.
Execute ALL steps in <task> — especially the bridge signal.
Stop after 2 failed patching attempts — document, do not guess.
</constraint>
```

### Required Content Checklist

| # | Required Element | Purpose |
|---|-----------------|---------|
| 1 | `<role>` | Tells Implementer which role definition to read. |
| 2 | `<handoff_id>` | Unique identifier for traceability. |
| 3 | `<project>` | Full path to the target project. |
| 4 | `<context>` | WHY this task exists — purpose and phase context. |
| 5 | `<governance>` | Governance file to read + extracted key rules. |
| 6 | `<task>` | Step-by-step instructions INCLUDING bridge signal as final step. |
| 7 | `<scope>` | Allowed files (full paths) and forbidden files (full paths). |
| 8 | `<validation>` | Concrete self-validation checks with commands. |
| 9 | `<constraint>` | "DO NOT COMMIT" + "Execute ALL steps" + stop-after-2-failures. |

---

## Escalation Handoff Format

### Review → Architect Escalation

```markdown
<role>You are {architect_role} in the DPMtF {flow_key} flow.
Your role is defined in {project_root}/docs/governance-templates-v2/{governance_file}.
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
</options>

<governance>
Read and apply:
- {project_root}/docs/governance-templates-v2/{governance_file}
- {project_root}/docs/governance-templates-v2/21_ALIGNMENT.md
- {project_root}/docs/governance-templates-v2/14_ARCHITECTURE.md
</governance>

<task>
1. Read <context> and <question> — understand what Review needs.
2. Consult relevant governance files for overview.
3. Make a decision and write response to:
   {bridge_dir}/{flow_key}/escalations/{ID}-response.md
4. Write notification to:
   {bridge_dir}/{flow_key}/escalations/{ID}-notification.md
5. SIGNAL completion:
   python3 {project_root}/scripts/bridgeV002/dispatch.py \
     --db-flow {flow_key} --signal-answer --from-role {from_role} --to-role {to_role} --id {ID}
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

1. **One active role at a time:** When a role dispatches to the next, it WAITS.
   The receiving role is the only active role.
2. **Signal-based activation:** Roles are activated by bridge-injected prompts,
   not by polling. A role does nothing until it receives a signal.
3. **No background work:** When a role signals completion, it stops.
   The next role resumes.
4. **Escalation is synchronous:** When Review escalates to Architect,
   Review WAITS. Architect answers, then Review resumes.
5. **No-kill enforcement:** Post-dispatch `ollama stop` clears the predecessor's
   model from VRAM, ensuring the predecessor cannot continue work.

### Violation Prevention

| Violation | Prevention |
|-----------|------------|
| Implementer continues after signaling | `signal_complete` injects into next role's session — Implementer receives no further prompts. Post-dispatch stops Implementer's model. |
| Review starts new work while Implementer runs | Review's session receives no prompt until `signal_complete` injects one. |
| Architect and Review both active | Architect is only activated by `signal_escalation` and deactivates after `signal_answer`. |
| Implementer commits code | Constraint in every handoff: "DO NOT COMMIT". Enforced by Review validation. |

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
- `content_template` — the prompt injected into the next role's tmux session
- `validation_schema` — required XML sections in the deliverable
- `dir_template` / `pattern_template` — default deliverable location (fallback)
- `error_template` — error message if dispatch fails

> **Note:** `dir_template` and `pattern_template` are fallbacks only.
> Actual deliverable paths come from `bridge_flow_steps.deliverable_dir`
> and `deliverable_pattern` (absolute paths).

---

## Security Rules

1. **Implementer NEVER commits** — constraint in every handoff.
2. **Review ALWAYS validates before verdict** — no automatic approval.
3. **Human ALWAYS authorizes commit** — Human Approval Gate.
4. **Rollback always possible** — `git reset --hard <baseline>` if result rejected.
5. **No-kill mode** — `ollama stop` clears context between role transitions.
   No tmux sessions are killed or created during dispatch.
6. **Handoff IDs are unique and sequential per flow** — auto-generated via
   `get_next_id_for_flow()`. Gaps from incomplete handoffs are normal.
7. **trace.log is append-only** — never edit existing entries.
8. **`signal_complete` and `signal_answer` called WITHOUT `/clear`** —
   otherwise the prompt is overwritten before the receiver sees it.
9. **Architect escalation is read-only** — Architect only makes decisions,
   never implements. Implementation always goes through the
   Implementer → Review loop.
10. **No direct Architect → Implementer communication** — all communication
    goes through the Review layer.
11. **Human recipients skip tmux injection** — `role_type = "human"` means
    the dispatch returns success after writing the deliverable file.
12. **All database-driven** — zero hardcoded paths, zero INI dependencies.
    Role config, flow steps, and convention templates are resolved from
    the database at runtime.
