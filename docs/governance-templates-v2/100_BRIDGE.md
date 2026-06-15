# 100 — BRIDGE PROTOCOL

> **en-US is the standard language for all governance-templates-v2 files.**
> All prompts, handoff files, bridge messages, and inter-role communication
> MUST be in English (en-US). The sole exception is 01_HUMAN.md — the Human
> may communicate in any language, but prompts forwarded through the bridge
> MUST be translated to English.

## Purpose

Defines the tmux-based bridge protocol for communication between the three
non-Human roles (Architect, Implementor, Review). Describes the required
content of handoff prompts, the escalation structure, and improvements
over the legacy bridge protocol to ensure reliable sequential execution.

## When to Use

- **Architect:** When generating implementation prompts for dispatch.
- **Review:** When dispatching prompts, receiving results, and escalating.
- **Implementor:** When reading handoff prompts and signaling completion.

---

## Bridge Infrastructure

| Component | Location | Purpose |
|-----------|----------|---------|
| `bridge.py` | `/home/svend/claude-bridge/bridge.py` | Core: tmux injection with correct Enter key handling. Four commands: `send`, `complete`, `ask-architect`, `answer-review`. |
| `reviewtoimplementor/` | `/home/svend/claude-bridge/reviewtoimplementor/` | Review → Implementor: handoff files with unique ID. |
| `implementertoreview/` | `/home/svend/claude-bridge/implementertoreview/` | Implementor → Review: result + notification + callback files. |
| `reviewtoarchitect/` | `/home/svend/claude-bridge/reviewtoarchitect/` | Review → Architect: escalation questions. |
| `architecttoreview/` | `/home/svend/claude-bridge/architecttoreview/` | Architect → Review: escalation responses. |
| `trace.log` | `/home/svend/claude-bridge/trace.log` | Append-only log of all bridge activity. |
| `claude_architect` | tmux session | Architect role. |
| `claude_implementer` | tmux session | Implementor role. |
| `claude_review` | tmux session | Review role. |

---

## Bridge Commands

| Command | From | To | Action |
|---------|------|----|--------|
| `bridge.py send {ID}` | Review | Implementor | `/clear` + inject handoff instruction. |
| `bridge.py complete {ID}` | Implementor | Review | Inject result callback prompt. |
| `bridge.py ask-architect {ID}` | Review | Architect | `/clear` + inject escalation question. |
| `bridge.py answer-review {ID}` | Architect | Review | Inject answer callback prompt. |
| `bridge.py next-id` | Any | — | Find next available handoff ID across all directories. |

---

## Layer 1: Implementation Loop (Review ↔ Implementor)

### Step 1: Review Dispatches to Implementor

Review writes the handoff file and dispatches:

```bash
python3 /home/svend/claude-bridge/bridge.py send {ID}
```

This does:
1. Checks that `claude_implementer` session is running.
2. Verifies handoff file exists at `reviewtoimplementor/{ID}-handoff.md`.
3. Sends `/clear` to `claude_implementer` via tmux.
4. Injects: `"Read and execute /home/svend/claude-bridge/reviewtoimplementor/{ID}-handoff.md"` + Enter.
5. Updates `current.md` symlink.
6. Logs `R→I` in `trace.log`.

### Step 2: Implementor Executes

Implementor:
1. Reads the handoff file.
2. Reads all governance files referenced in `<governance>`.
3. Executes `<task>` steps in order.
4. Runs `<validation>` self-checks.
5. Writes `implementertoreview/{ID}-result.md`.
6. Writes `implementertoreview/{ID}-notification.md`.

### Step 3: Implementor Signals Completion

```bash
python3 /home/svend/claude-bridge/bridge.py complete {ID}
```

This does:
1. Checks that `claude_review` session is running.
2. Writes `implementertoreview/{ID}-callback.md` (if it does not exist).
3. Injects: `"Read and execute /home/svend/claude-bridge/implementertoreview/{ID}-callback.md"` + Enter.
4. Logs `I→R` in `trace.log`.
5. Updates `implementertoreview/current.md` symlink.

**CRITICAL: `bridge.py complete` is called WITHOUT `/clear` first.**
A `/clear` would overwrite the injected prompt before the receiver sees it.

---

## Layer 2: Escalation Loop (Review ↔ Architect)

### When Review Escalates

Review escalates to Architect when it encounters a decision it cannot make alone:
- Architectural ambiguity.
- Cross-project impact (see [[21_ALIGNMENT]]).
- Design pattern conflict with [[14_ARCHITECTURE]].
- Complex rework requiring redesign.

### Step 1: Review Escalates to Architect

```bash
python3 /home/svend/claude-bridge/bridge.py ask-architect {ID}
```

This does:
1. Checks that `claude_architect` session is running.
2. Verifies handoff file exists at `reviewtoarchitect/{ID}-handoff.md`.
3. Sends `/clear` to `claude_architect` via tmux.
4. Injects: `"Read and execute /home/svend/claude-bridge/reviewtoarchitect/{ID}-handoff.md"` + Enter.
5. Updates `reviewtoarchitect/current.md` symlink.
6. Logs `R→A` in `trace.log`.

### Step 2: Architect Responds

Architect:
1. Reads the escalation handoff file.
2. Analyzes context and cross-project overview.
3. Makes a decision.
4. Writes `architecttoreview/{ID}-response.md`.
5. Writes `architecttoreview/{ID}-notification.md`.

### Step 3: Architect Signals Response

```bash
python3 /home/svend/claude-bridge/bridge.py answer-review {ID}
```

This does:
1. Checks that `claude_review` session is running.
2. Writes `architecttoreview/{ID}-callback.md` (if it does not exist).
3. Injects: `"Read and execute /home/svend/claude-bridge/architecttoreview/{ID}-callback.md"` + Enter.
4. Logs `A→R` in `trace.log`.
5. Updates `architecttoreview/current.md` symlink.

---

## Handoff Prompt Format (Improved)

### Review → Implementor Handoff

This is the CRITICAL artifact. The handoff prompt MUST contain all information
the Implementor needs to execute the task without ambiguity. All text MUST be
in English (en-US).

```markdown
<role>You are Implementor in the DPMtF governance loop. Your role is defined
in /home/svend/DPMtF-WebUI/docs/governance-templates-v2/03_IMPLEMENTOR.md.
Read it now before proceeding.</role>

<handoff_id>{ID}</handoff_id>

<project>/home/svend/{project-name}</project>

<context>
{WHY this task exists — what problem it solves, what phase it belongs to.
This gives the Implementor understanding of purpose, not just steps.}
</context>

<governance>
Read and apply these governance files BEFORE starting:
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/12_CODING_STANDARD.md
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/16_FILE_ACCESS.md

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
   /home/svend/claude-bridge/implementertoreview/{ID}-result.md
   Format per 03_IMPLEMENTOR.md — include Summary, Files Changed,
   Validation Results table.

2. Write notification file to:
   /home/svend/claude-bridge/implementertoreview/{ID}-notification.md
   Format per 03_IMPLEMENTOR.md — Status, Task Summary, Files Changed,
   Next Action.

3. SIGNAL completion (NO /clear before this):
   python3 /home/svend/claude-bridge/bridge.py complete {ID}
</task>

<scope>
Files you MAY modify:
- {/full/path/to/allowed/file1}
- {/full/path/to/allowed/file2}

Files you MUST NOT touch:
- {/full/path/to/forbidden/file1}
- /home/svend/DPMtF-WebUI/ (Father project)
- /home/svend/ENO/ (other Child project)
</scope>

<validation>
Before signaling completion, run these checks yourself:
1. {python3 -m py_compile <file>} — must pass
2. {node --check <file>} — must pass
3. git diff --stat — verify only allowed files changed
4. grep -RIn "innerHTML" static templates — must be empty
5. {Other phase-specific checks}
</validation>

<constraint>
DO NOT COMMIT. Leave all changes unstaged.
Execute ALL steps in <task> — especially step 3 (bridge.py complete).
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
| 6 | `<task>` | Step-by-step instructions INCLUDING bridge complete as final step. |
| 7 | `<scope>` | Allowed files (full paths) and forbidden files (full paths). |
| 8 | `<validation>` | Concrete self-validation checks with commands. |
| 9 | `<constraint>` | "DO NOT COMMIT" + "Execute ALL steps" + ambiguity/escalation rules. |

### Review → Architect Escalation Handoff

```markdown
<role>You are Architect in the DPMtF governance loop. Your role is defined
in /home/svend/DPMtF-WebUI/docs/governance-templates-v2/02_ARCHITECT.md.
Read it now before proceeding.</role>

<handoff_id>{ID}</handoff_id>

<escalation_from>claude_review</escalation_from>

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
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/02_ARCHITECT.md
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/21_ALIGNMENT.md
- /home/svend/DPMtF-WebUI/docs/governance-templates-v2/14_ARCHITECTURE.md
</governance>

<task>
1. Read <context> and <question> — understand what Review needs.
2. Consult relevant governance files for overview.
3. Make a decision and write response to:
   /home/svend/claude-bridge/architecttoreview/{ID}-response.md
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
   /home/svend/claude-bridge/architecttoreview/{ID}-notification.md
5. SIGNAL completion:
   python3 /home/svend/claude-bridge/bridge.py answer-review {ID}
</task>

<constraint>
ONLY answer the question. Do not start new implementations.
Execute ALL steps in <task> — especially step 5 (bridge.py answer-review).
All response text MUST be in English (en-US).
</constraint>
```

---

## Input Prompt Content Requirements

### For Implementor

The handoff prompt to Implementor MUST enable the Implementor to work
autonomously without asking questions. The prompt must contain:

1. **Identity:** Which project, which phase, which handoff ID.
2. **Context:** WHY this task is needed — purpose understanding prevents
   mechanical errors.
3. **Exact steps:** What to do, in what order, with what files.
4. **Boundaries:** What NOT to do, what NOT to touch.
5. **Self-checks:** How to verify correctness before signaling.
6. **Completion protocol:** Exactly how to signal completion (bridge.py complete).

### For Architect

The escalation prompt to Architect MUST enable a fast, focused decision:

1. **Context:** What Review was doing and why.
2. **The blocker:** What specific decision Review cannot make.
3. **Options:** Proposed options with implications — reduces Architect's
   analysis time.
4. **Response format:** Exactly how to structure the response.
5. **Completion protocol:** bridge.py answer-review.

### For Review (Callback from Implementor)

The callback prompt injected by `bridge.py complete`:

```markdown
Handoff {ID} is complete.

Read the result and notification:
- /home/svend/claude-bridge/implementertoreview/{ID}-result.md
- /home/svend/claude-bridge/implementertoreview/{ID}-notification.md

Review the implementation per:
/home/svend/DPMtF-WebUI/docs/governance-templates-v2/04_REVIEW.md

Run validation checks, review the diff, and decide: pass, pass with notes,
or return to Implementor.
```

### For Review (Callback from Architect)

The callback prompt injected by `bridge.py answer-review`:

```markdown
Architect has answered escalation {ID}.

Read the response:
- /home/svend/claude-bridge/architecttoreview/{ID}-response.md
- /home/svend/claude-bridge/architecttoreview/{ID}-notification.md

Apply the Architect's decision and continue with the task.
```

---

## Sequential Execution Protocol

The bridge guarantees that roles do not run in parallel:

1. **One active role at a time:** When Review dispatches to Implementor via
   `bridge.py send`, Review WAITS. Implementor is the only active role.
2. **Signal-based activation:** Roles are activated by bridge-injected prompts,
   not by polling. A role does nothing until it receives a signal.
3. **No background work:** When Implementor signals completion via
   `bridge.py complete`, Implementor stops. Review resumes.
4. **Escalation is synchronous:** When Review escalates to Architect,
   Review WAITS. Architect answers, then Review resumes.

### Violation Prevention

| Violation | Prevention |
|-----------|------------|
| Implementor continues after signaling | `bridge.py complete` injects into claude_review — claude_implementer receives no further prompts until next `send`. |
| Review starts new work while Implementor runs | Review's session receives no prompt until `complete` injects one. |
| Architect and Review both active | Architect is only activated by `ask-architect` and deactivates after `answer-review`. |
| Implementor commits code | Constraint in every handoff: "DO NOT COMMIT". Enforced by Review validation. |

---

## Bridge Improvements Over Legacy

This section documents improvements to the bridge protocol compared to the
legacy `superpowertemplates/bridge-protocol.md` (v1).

### Improvement 1: Mandatory Context Section

**Legacy:** Handoff files had `<role>`, `<project>`, `<governance>`, `<task>`,
`<scope>`, `<validation>`, `<constraint>` — but no explanation of WHY.

**Improved:** Added mandatory `<context>` section that explains the purpose
and phase context. This prevents the Implementor from executing mechanically
without understanding intent.

### Improvement 2: Handoff Completeness Checklist

**Legacy:** No formal check that handoff prompts contain all required elements
before dispatch.

**Improved:** Review MUST verify the 9-element checklist before dispatching.
Missing elements = return to Architect.

### Improvement 3: Explicit Escalation Criteria

**Legacy:** "Review rammer en beslutning den ikke kan tage alene" — vague.

**Improved:** Four explicit escalation triggers with examples:
- Architectural ambiguity
- Cross-project impact
- Design pattern conflict
- Complex rework needed

### Improvement 4: English-Only Inter-Role Communication

**Legacy:** No language policy for bridge communication.

**Improved:** All prompts, handoffs, and bridge messages MUST be in English
(en-US). This ensures model consistency (models perform better in English)
and prevents translation errors.

### Improvement 5: Structured Response Formats

**Legacy:** Response format loosely defined — Architect could respond in
varying formats.

**Improved:** Architect escalation response MUST follow a fixed structure:
Decision, Rationale, Next Steps for Review, Affected Projects/Files.
This ensures Review can parse and apply the response immediately.

### Improvement 6: Callback Prompt Standardization

**Legacy:** Callback prompts were ad-hoc.

**Improved:** Standardized callback prompts for both `complete` and
`answer-review` callbacks — each tells Review exactly which files to read
and what to do next.

### Improvement 7: Sequential Execution Guarantee Documentation

**Legacy:** Sequential execution was implied but not formally documented.

**Improved:** Explicit documentation of HOW the bridge prevents parallel
execution, with violation scenarios and prevention mechanisms.

---

## Security Rules

1. **Implementor NEVER commits** — constraint in every handoff.
2. **Review ALWAYS validates before commit proposal** — no automatic commit.
3. **Human ALWAYS authorizes commit** — Human Approval Gate.
4. **Rollback always possible** — `git reset --hard <baseline>` if result rejected.
5. **`/clear` between role transitions** — handled by `bridge.py send` and
   `bridge.py ask-architect`.
6. **Handoff IDs are unique and sequential** — use `bridge.py next-id`.
7. **trace.log is append-only** — never edit existing entries.
8. **`bridge.py complete` and `answer-review` called WITHOUT `/clear`** —
   otherwise the prompt is overwritten before the receiver sees it.
9. **Architect escalation is read-only** — Architect only makes decisions,
   never implements. Implementation always goes through the
   Implementor → Review loop.
10. **No direct Architect → Implementor communication** — all communication
    goes through the Review layer.

---
