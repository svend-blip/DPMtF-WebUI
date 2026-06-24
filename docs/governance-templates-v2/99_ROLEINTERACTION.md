# 99 — ROLE INTERACTION

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines the interaction loop between roles in a BridgeV002 flow. This is the
master protocol for how work flows through the role pipeline, how roles hand
off to each other, and how escalations are handled.

BridgeV002 is **flow-key dynamic** — different flows have different role sets
and step sequences. The `strict_review` flow is the primary example.

## When to Use

- **All roles:** Read before any role transition to understand the interaction
  protocol.
- **After `/clear`:** Reconstruct the role loop and current position.
- **Architect:** Understand handoff flow before generating prompts.

---

## The Role Loop (per Flow Key)

Each flow defines its own role sequence via `bridge_flow_steps`. The
`strict_review` flow has 4 roles in a linear pipeline:

```
                          ┌──────────────────────┐
                          │       HUMAN           │
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
                          │      ARCHITECT       │
                          │    (archi01)          │
                          │                      │
                          │  Scope analysis      │
                          │  Technical design    │
                          │  Handoff generation  │
                          │  Escalation target   │
                          └──────────┬───────────┘
                                     │
                          signal_send (dispatch.py)
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────┐
│                    BRIDGEV002 LAYER                           │
│                                                              │
│  ┌──────────────────────┐          ┌──────────────────────┐  │
│  │  REVIEW01 + REVIEW02 │◄────────►│     IMPLEMENTER      │  │
│  │                      │dispatch  │     (imple01)        │  │
│  │  Technical review    │  .py     │                      │  │
│  │  Governance review   │signal_   │  Handoff execution   │  │
│  │  Verdict + commit    │complete  │  Code production     │  │
│  │    message           │          │  Self-validation     │  │
│  │  Escalation to       │          │  Result + notif.     │  │
│  │    Architect          │          │                      │  │
│  └──────────┬───────────┘          └──────────────────────┘  │
│             │                                                 │
└─────────────┼─────────────────────────────────────────────────┘
              │
    verdict + commit message
    (human_delivery — no tmux injection)
              │
              ▼
   ┌──────────────────────┐
   │      HUMAN           │
   │                      │
   │  Approve / Reject    │
   │  Authorize commit    │
   └──────────────────────┘
```

**Other flows** may have fewer roles (e.g., a 2-role flow with just
architect → implementer). The interaction protocol adapts to the flow's
step sequence defined in the database.

---

## Role Loop Phases (strict_review example)

### Phase 1: Scope Definition (Human → Architect)

1. Human defines or updates [[11_SCOPE]] with the new phase.
2. Human communicates the feature request or phase goal to Architect.
3. Human answers any initial gate questions.
4. Architect reads [[11_SCOPE]] and [[402_STRICT_REVIEW_ARCHI01]] and begins analysis.

### Phase 2: Design & Handoff Generation (Architect → Implementer)

1. Architect analyzes scope against [[14_ARCHITECTURE]] and [[21_ALIGNMENT]].
2. Architect designs the technical approach.
3. Architect generates a handoff prompt following the format in
   [[402_STRICT_REVIEW_ARCHI01]] and [[100_BRIDGE]].
4. Architect writes the handoff to `{bridge_dir}/{flow_key}/handoffs/{ID}-handoff.md`
   (via Prompt Compiler "Assign Handoff ID" or manually).
5. Architect dispatches to Implementer:
   ```bash
   python3 {project_root}/scripts/bridgeV002/dispatch.py \
     --db-flow {flow_key} --signal-send --from-role archi01 --to-role imple01 --id {ID}
   ```
   Or click **"Deliver to Bridge"** in the Prompt Compiler UI.

**At this point, Architect's active phase ends. Implementer takes over.**

### Phase 3: Implementation (Implementer)

1. Implementer receives the bridge-injected prompt in their tmux session.
2. Implementer reads the handoff file and [[403_STRICT_REVIEW_IMPLE01]].
3. Implementer executes the `<task>` steps in order.
4. Implementer runs `<validation>` self-checks.
5. Implementer writes result to `{bridge_dir}/{flow_key}/results/{ID}-result.md`.
6. Implementer writes notification to `{bridge_dir}/{flow_key}/results/{ID}-notification.md`.
7. Implementer signals completion:
   ```bash
   python3 {project_root}/scripts/bridgeV002/dispatch.py \
     --db-flow {flow_key} --signal-complete --from-role imple01 --id {ID}
   ```

**At this point, Implementer's active phase ends. Review01 resumes.**
Post-dispatch stops Implementer's Ollama model to free VRAM.

### Phase 4: Technical Review (Review01)

1. Review01 receives the bridge-injected callback prompt.
2. Review01 reads the result and notification files.
3. Review01 reads [[404_STRICT_REVIEW_REVIEW01]] and runs ALL technical checks.
4. Review01 inspects `git diff` for scope, coding standards, and file access.
5. Review01 writes technical review to `{bridge_dir}/{flow_key}/reviews/{ID}-review01.md`
   (MUST include required XML sections per [[404_STRICT_REVIEW_REVIEW01]]).
6. Review01 signals completion:
   ```bash
   python3 {project_root}/scripts/bridgeV002/dispatch.py \
     --db-flow {flow_key} --signal-complete --from-role review01 --id {ID}
   ```

### Phase 5: Governance Review (Review02)

1. Review02 receives the bridge-injected callback prompt.
2. Review02 reads the technical review and original implementation artifacts.
3. Review02 reads [[405_STRICT_REVIEW_REVIEW02]] and runs governance checks.
4. Review02 decides:
   - **APPROVED** → write verdict + commit message, signal to Human.
   - **APPROVED WITH NOTES** → write verdict with notes, signal to Human.
   - **REJECTED** → write verdict with reasons, signal to Human.
5. Review02 writes verdict to `{bridge_dir}/{flow_key}/verdicts/{ID}-verdict.md`
   (MUST include required XML sections per [[405_STRICT_REVIEW_REVIEW02]]).
6. Review02 signals completion:
   ```bash
   python3 {project_root}/scripts/bridgeV002/dispatch.py \
     --db-flow {flow_key} --signal-complete --from-role review02 --id {ID}
   ```

**Note:** The `review02 → human` step has `role_type = "human"` — dispatch
skips tmux injection. Human reads the verdict files from disk.

### Phase 6: Commit Authorization (Human)

1. Human reads the verdict at `{bridge_dir}/{flow_key}/verdicts/{ID}-verdict.md`.
2. Human reviews the diff, validation results, and commit message.
3. Human decides:
   - **APPROVE** → commit and optionally push.
   - **REJECT** → return to Phase 2 with specific reasons.

---

## Escalation Structure

### Escalation Levels

```
Level 0: Implementer → Review (routine)
         All implementation results flow to Review via signal_complete.

Level 1: Review → Architect (architectural decision needed)
         Via signal_escalation / signal_answer.
         When: architectural ambiguity, cross-project impact,
               design pattern conflict, complex rework needed.

Level 2: Architect/Review → Human (authority exceeded)
         Direct communication.
         When: scope creep, gate triggers, commit authorization,
               architect decision contradicts Human instructions.
```

### Escalation Flow

```
IMPLEMENTER
    │
    │ signal_complete
    ▼
REVIEW01
    │
    ├─ Can validate alone?
    │   ├─ YES → Write review, signal_complete to Review02.
    │   └─ NO  → Escalate to Architect.
    │
    ├─ signal_escalation
    ▼
ARCHITECT
    │
    │ signal_answer
    ▼
REVIEW01
    │
    └─ Continue validation, signal_complete to Review02.
        │
        ▼
    REVIEW02
        │
        └─ Write verdict, signal_complete to Human.
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
| **Implementer** | **Review01** | Task complete or task failed (signal_complete). |
| **Review01/Review02** | **Architect** | Architectural ambiguity, cross-project impact, design pattern conflict, complex rework needed. |
| **Review02** | **Human** | Verdict ready — APPROVED, REJECTED, or APPROVED WITH NOTES. |
| **Architect** | **Human** | Proposed change exceeds scope, new dependency/schema/visual change, cross-project alignment conflict. |

---

## Sequential Execution Guarantee

The role loop guarantees that only ONE role is active at any time:

1. **Bridge enforces sequentiality:** `dispatch.py` injects a prompt with a
   soft-clear preamble ("Start a new logical task now..."). The target role
   cannot continue previous work.
2. **No polling:** Roles do not poll for work. They are activated by bridge
   signals injected into their tmux session.
3. **No parallel work:** When a role dispatches to the next, it stops.
   Post-dispatch `ollama stop` clears the predecessor's model from VRAM.
4. **Role handoff is explicit:** Each role transition is marked by a bridge
   signal (`signal_send`, `signal_complete`, `signal_escalation`,
   `signal_answer`).

### Violation Prevention

| Violation | Prevention |
|-----------|------------|
| Implementer continues after signaling | `signal_complete` injects into Review01's session. Post-dispatch stops Implementer's model. Implementer's governance file (403) mandates "After Signaling — Stop". |
| Review starts new work while Implementer runs | Review's session receives no prompt until `signal_complete` injects one. |
| Architect and Review both active | Architect is only activated by `signal_escalation` and deactivates after `signal_answer`. |
| Implementer commits code | Constraint in every handoff: "DO NOT COMMIT". Enforced by Review validation. |

---

## Scope Creep Prevention

Scope creep is prevented through multiple layers:

1. **Architect** validates all designs against [[11_SCOPE]] before handoff
   generation. Any out-of-scope element triggers GATE-SCOPE → Human.
2. **Implementer** is constrained by the `<scope>` section in the handoff
   prompt. The handoff specifies exact files allowed and forbidden.
   [[403_STRICT_REVIEW_IMPLE01]] forbids modifying governance files unless
   explicitly listed in `<scope>`.
3. **Review01** checks `git diff --stat` against the handoff scope. Any
   scope violation is documented in findings.
4. **Review02** validates scope boundaries as part of governance review.
   GATE-SCOPE triggers rejection.
5. **Human** is the only role authorized to change scope via the formal
   scope change process in [[11_SCOPE]].

---

## Commit Authorization Flow

Only the Human may authorize commits. The flow:

1. Review01 validates all changes pass technical checks.
2. Review02 validates governance compliance and writes verdict + commit message.
3. Review02 signals completion to Human (files written to disk, no tmux injection).
4. Human reads verdict at `{bridge_dir}/{flow_key}/verdicts/{ID}-verdict.md`.
5. Human reviews and decides:
   - **APPROVE:** Human executes `git commit` and optionally `git push`.
   - **REJECT:** Human communicates reasons to Architect, who creates a new
     handoff for Implementer.

---

## Role Interaction Rules

1. **All inter-role communication via bridge MUST be in English (en-US).**
2. **Human may communicate in any language** — but prompts forwarded to
   other roles MUST be translated to English.
3. **Each role reads its flow-specific governance file before acting:**
   - Architect: [[402_STRICT_REVIEW_ARCHI01]]
   - Implementer: [[403_STRICT_REVIEW_IMPLE01]]
   - Review01: [[404_STRICT_REVIEW_REVIEW01]]
   - Review02: [[405_STRICT_REVIEW_REVIEW02]]
   Plus [[10_PROJECT]], [[11_SCOPE]], [[100_BRIDGE]].
4. **No-kill mode:** Context is cleared by `ollama stop` between role
   transitions — not by killing tmux sessions or running `/clear`.
5. **After restart, reconstruct from durable files** — not chat memory.
   Use `/STRICTREVIEW` skill for Architect cold-start.
6. **If governance files conflict with chat memory, governance files win.**
7. **If governance files conflict with each other, escalate to Human.**
8. **Different flows have different role sets.** The interaction protocol
   adapts to the flow's step sequence. Roles are defined per flow in
   `bridge_roles` and `bridge_flow_steps`.

---

## Related Reference Files

| File | Use When |
|------|----------|
| [[01_HUMAN]] | Human role — scope authority, commit gate, strategic direction. |
| [[402_STRICT_REVIEW_ARCHI01]] | Architect role (strict_review) — design, handoff generation. |
| [[403_STRICT_REVIEW_IMPLE01]] | Implementer role (strict_review) — execution, self-validation. |
| [[404_STRICT_REVIEW_REVIEW01]] | Technical Review role (strict_review) — validation, diff review. |
| [[405_STRICT_REVIEW_REVIEW02]] | Governance Review role (strict_review) — verdict, commit message. |
| [[10_PROJECT]] | Project identity, port, repository, Father-Child relationship. |
| [[11_SCOPE]] | Phase scope boundaries and constraints. |
| [[13_VALIDATION]] | Validation checks and auto-fail rules. |
| [[15_GIT_POLICY]] | Commit authorization and git conventions. |
| [[20_GATES]] | Gate questions and escalation triggers. |
| [[100_BRIDGE]] | BridgeV002 protocol, signals, and handoff formats. |
| [[300_SETUPINSTRUCTION]] | PC migration and fresh install guide. |
