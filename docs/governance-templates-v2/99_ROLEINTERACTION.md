# 99 — ROLE INTERACTION

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines the interaction loop between the four DPMtF governance roles (Human,
Architect, Implementor, Review). This is the master protocol for how work
flows through the role pipeline, how roles hand off to each other, and how
escalations are handled.

## When to Use

- **All roles:** Read before any role transition to understand the interaction
  protocol.
- **After `/clear`:** Reconstruct the role loop and current position.
- **Architect:** Understand handoff flow before generating prompts.

---

## The 4-Role Loop

```
                          ┌──────────────────────┐
                          │      01_HUMAN        │
                          │                      │
                          │  Scope definition    │
                          │  Commit authorization│
                          │  Strategic direction │
                          │  Gate decisions      │
                          └──────────┬───────────┘
                                     │
                          scope definition +
                          feature request
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │    02_ARCHITECT      │
                          │                      │
                          │  Scope analysis      │
                          │  Technical design    │
                          │  Prompt generation   │
                          │  Escalation target   │
                          └──────────┬───────────┘
                                     │
                          implementation prompt
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────┐
│                        BRIDGE LAYER                          │
│                                                              │
│  ┌──────────────────────┐          ┌──────────────────────┐  │
│  │     04_REVIEW        │◄────────►│   03_IMPLEMENTOR     │  │
│  │                      │  bridge  │                      │  │
│  │  Prompt dispatch     │  .py     │  Prompt execution    │  │
│  │  Validation          │  send/   │  Code production     │  │
│  │  Diff review         │  complete│  Self-validation     │  │
│  │  Escalation to       │          │  Result write        │  │
│  │    Architect          │          │                      │  │
│  └──────────┬───────────┘          └──────────────────────┘  │
│             │                                                 │
└─────────────┼─────────────────────────────────────────────────┘
              │
    validation verdict +
    commit proposal
              │
              ▼
   ┌──────────────────────┐
   │     01_HUMAN         │
   │                      │
   │  Approve / Reject    │
   │  Authorize commit    │
   └──────────────────────┘
```

## Role Loop Phases

### Phase 1: Scope Definition (Human → Architect)

1. Human defines or updates [[11_SCOPE]] with the new phase.
2. Human communicates the feature request or phase goal to Architect.
3. Human answers any initial gate questions.
4. Architect reads [[11_SCOPE]] and begins analysis.

### Phase 2: Design & Prompt Generation (Architect → Review)

1. Architect analyzes scope against [[14_ARCHITECTURE]] and [[21_ALIGNMENT]].
2. Architect designs the technical approach.
3. Architect selects the appropriate model per [[22_MODEL_SELECTION]].
4. Architect generates an implementation prompt following the format in
   [[02_ARCHITECT]].
5. Architect writes the prompt to `reviewtoimplementor/{ID}-handoff.md`.
6. Architect signals Review that a handoff is ready.

**At this point, Architect's active phase ends. Review takes over.**

### Phase 3: Implementation Dispatch (Review → Implementor)

1. Review reads the handoff file from Architect.
2. Review verifies the prompt is complete: has `<role>`, `<project>`,
   `<governance>`, `<task>`, `<scope>`, `<validation>`, `<constraint>`.
3. Review dispatches the prompt to Implementor via:
   ```bash
   python3 /home/svend/claude-bridge/bridge.py send {ID}
   ```
4. Bridge sends `/clear` to `claude_implementer`, then injects the handoff
   instruction.

**At this point, Review waits. Implementor is active. No parallel work.**

### Phase 4: Implementation (Implementor)

1. Implementor receives the bridge-injected prompt.
2. Implementor reads the handoff file and all referenced governance files.
3. Implementor executes the `<task>` steps in order.
4. Implementor runs `<validation>` self-checks.
5. Implementor writes result to `implementertoreview/{ID}-result.md`.
6. Implementor writes notification to `implementertoreview/{ID}-notification.md`.
7. Implementor signals completion:
   ```bash
   python3 /home/svend/claude-bridge/bridge.py complete {ID}
   ```

**At this point, Implementor's active phase ends. Review resumes.**

### Phase 5: Validation (Review)

1. Review receives the bridge-injected callback prompt.
2. Review reads the result and notification files.
3. Review runs ALL pre-commit checks from [[13_VALIDATION]].
4. Review inspects `git diff` for scope, coding standards, and file access
   compliance.
5. Review decides:
   - **PASS** → proceed to Phase 6.
   - **PASS with notes** → proceed to Phase 6, document notes.
   - **FAIL** → return to Phase 3 with a new handoff containing specific
     fix instructions.

### Phase 6: Commit Authorization (Review → Human)

1. Review prepares staged changes and a commit message per [[15_GIT_POLICY]].
2. Review writes [[29_VALIDATION_REPORT]] with the validation verdict.
3. Review updates [[27_NEXT_CONTEXT]] with session state.
4. Review presents the validation verdict and commit proposal to Human.
5. Human reviews the diff, validation report, and screenshots (if visual changes).
6. Human decides:
   - **APPROVE** → commit and optionally push.
   - **REJECT** → return to Phase 3 with specific reasons.

---

## Escalation Structure

### Escalation Levels

```
Level 0: Implementor → Review (routine)
         All implementation results flow to Review via bridge.

Level 1: Review → Architect (architectural decision needed)
         Via bridge.py ask-architect / answer-review.
         When: architectural ambiguity, cross-project impact,
               design pattern conflict, complex rework needed.

Level 2: Architect/Review → Human (authority exceeded)
         Direct communication.
         When: scope creep, gate triggers, commit authorization,
               architect decision contradicts Human instructions.
```

### Escalation Flow

```
IMPLEMENTOR
    │
    │ bridge.py complete {ID}
    ▼
REVIEW
    │
    ├─ Can decide alone?
    │   ├─ YES → Validate, prepare commit, escalate to Human.
    │   └─ NO  → Escalate to Architect.
    │
    ├─ bridge.py ask-architect {ID}
    ▼
ARCHITECT
    │
    │ bridge.py answer-review {ID}
    ▼
REVIEW
    │
    └─ Validate, prepare commit, escalate to Human.
        │
        ▼
    HUMAN
        │
        ├─ APPROVE → Commit + Push.
        └─ REJECT → Return to Architect with reasons.
```

### Escalation Triggers

| From | To | Trigger |
|------|----|---------|
| **Implementor** | **Review** | Task complete or task failed. |
| **Review** | **Architect** | Architectural ambiguity, cross-project impact, design pattern conflict, complex rework needed. |
| **Review** | **Human** | Scope creep detected, gate trigger, commit ready, validation complete. |
| **Architect** | **Human** | Proposed change exceeds scope, new dependency/schema/visual change, cross-project alignment conflict. |

---

## Sequential Execution Guarantee

The role loop guarantees that only ONE role is active at any time:

1. **Bridge enforces sequentiality:** `bridge.py send` does `/clear` on the
   target session and injects a new prompt. The target role cannot continue
   previous work.
2. **No polling:** Roles do not poll for work. They are activated by bridge
   signals.
3. **No parallel work:** The bridge architecture ensures that when Review
   dispatches to Implementor, Review waits. When Implementor signals completion,
   Implementor waits.
4. **Role handoff is explicit:** Each role transition is marked by a bridge
   signal or direct Human communication.

---

## Scope Creep Prevention

Scope creep is prevented through multiple layers:

1. **Architect** validates all designs against [[11_SCOPE]] before prompt
   generation. Any out-of-scope element triggers GATE-SCOPE → Human.
2. **Implementor** is constrained by the `<scope>` section in the handoff
   prompt. The handoff specifies exact files allowed and forbidden.
3. **Review** checks `git diff --stat` against [[11_SCOPE]]. Any scope
   violation triggers GATE-SCOPE → Human.
4. **Human** is the only role authorized to change scope via the formal
   scope change process in [[11_SCOPE]].

---

## Commit Authorization Flow

Only the Human may authorize commits. The flow:

1. Review validates all changes pass [[13_VALIDATION]].
2. Review stages changes (`git add <files>`) and writes a commit message.
3. Review presents to Human: diff summary, validation report, commit message.
4. Human reviews and decides:
   - **APPROVE:** Human executes `git commit` and optionally `git push`,
     or authorizes Review to execute on their behalf.
   - **REJECT:** Human communicates reasons to Review, who creates a new
     handoff for Implementor.

---

## Role Interaction Rules

1. **All inter-role communication via bridge MUST be in English (en-US).**
2. **Human may communicate in any language** — but prompts forwarded to
   other roles MUST be translated to English.
3. **Each role reads its governance file before acting** — minimum:
   [[01_HUMAN]] for Human, [[02_ARCHITECT]] for Architect,
   [[03_IMPLEMENTOR]] for Implementor, [[04_REVIEW]] for Review,
   plus [[10_PROJECT]], [[11_SCOPE]].
4. **Use `/clear` between role transitions** to reset context. Governance
   files are the source of truth.
5. **After `/clear`, reconstruct from [[27_NEXT_CONTEXT]]** — not chat memory.
6. **If governance files conflict with chat memory, governance files win.**
7. **If governance files conflict with each other, escalate to Human.**

---

## Related Reference Files

| File | Use When |
|------|----------|
| [[01_HUMAN]] | Human role — scope authority, commit gate, strategic direction. |
| [[02_ARCHITECT]] | Architect role — design, prompt generation, cross-project oversight. |
| [[03_IMPLEMENTOR]] | Implementor role — prompt execution, code production, self-validation. |
| [[04_REVIEW]] | Review role — validation, diff review, workflow coordination. |
| [[10_PROJECT]] | Project identity, port, repository, Father-Child relationship. |
| [[11_SCOPE]] | Phase scope boundaries and constraints. |
| [[13_VALIDATION]] | Validation checks and auto-fail rules. |
| [[15_GIT_POLICY]] | Commit authorization and git conventions. |
| [[20_GATES]] | Gate questions and escalation triggers. |
| [[100_BRIDGE]] | Bridge protocol and handoff formats. |

---
