# 20 — GATES

> **en-US is the standard language for all governance-templates-v2 files.**
> All gate questions MUST be asked in English (en-US).

## Purpose

Defines mandatory gate questions that MUST be asked before critical operations.
Gates protect against unintended changes, scope creep, and governance drift.
Consolidated from the legacy `superpowertemplates/gates.md`.

## When to Use

- **Architect:** Trigger gates during design and prompt generation.
- **Review:** Trigger gates during validation and before commit preparation.
- **Human:** Answer gate questions — Human is the gate authority.
- **Any role:** If a gate trigger condition is detected, the gate MUST be asked.

---

## Defined Gates

### GATE-SCOPE: Scope Exceeded

```
TRIGGER: A change falls outside the current phase scope defined in [[11_SCOPE]].

QUESTION: "This change exceeds the current phase scope defined in
[[11_SCOPE]]. Should we update the scope first?"

CONSEQUENCE:
  - Human says YES → update [[11_SCOPE]] + [[25_DECISIONS]] first, then proceed.
  - Human says NO  → stop the change, stay within scope.
```

### GATE-V3: Reference Project Protection

```
TRIGGER: Changes are requested in ai-pc-resource-webui-v3 AND the change
         is NOT a governance template synchronization.

QUESTION: "ai-pc-resource-webui-v3 is the reference project for testing
the DPMtF prompt compiler. Are you sure you want to modify it?"

CONSEQUENCE:
  - Human says YES → proceed with change, document in [[21_ALIGNMENT]].
  - Human says NO  → stop, clarify what should happen instead.
```

### GATE-MODEL: Cheaper Model Available

```
TRIGGER: A task is assessed as mechanical/trivial (1-2 files, well-defined
         spec, no design decisions) AND a cheaper model can handle it.

QUESTION: "This task could be done by a cheaper model. Switch?"

CONSEQUENCE:
  - Human says YES → switch model for this task.
  - Human says NO  → continue with current model.
```

### GATE-FEATURE-ROLLOUT: Feature Rollout Decision

```
TRIGGER: A feature is implemented in DPMtF-WebUI AND the Human has NOT
         specified whether it should roll out to other projects.

QUESTION: "Should this feature also be implemented in ENO?"

CONSEQUENCE:
  - Human says YES → add to alignment matrix in [[21_ALIGNMENT]].
                     Implement in ENO after DPMtF-WebUI is complete.
  - Human says NO  → mark as DPMtF-WebUI only in [[21_ALIGNMENT]].
```

### GATE-GOVERNANCE-SYNC: Governance Divergence

Has two triggers:

#### Trigger A: Structural Template Divergence

```
TRIGGER: Structural reference files (12-24) in a Child project have
         diverged from DPMtF-WebUI's master copies.

QUESTION: "Structural governance files in {project} have diverged from
DPMtF-WebUI master. Is this divergence intentional?"

CONSEQUENCE:
  - Human says INTENTIONAL → document in [[21_ALIGNMENT]] that divergence
                              is intentional. Do not overwrite.
  - Human says SYNC        → overwrite Child's structural files with
                              DPMtF-WebUI's master via initializer script.
                              Document in [[21_ALIGNMENT]].
```

#### Trigger B: Project-Specific Staleness

```
TRIGGER: A Child project's project-specific files (10, 11, 25, 26, 27, 28, 29)
         are still Father copies and do NOT reflect the project's own identity.

QUESTION: "Governance files in {project} have diverged from DPMtF-WebUI
master — but in the wrong direction. {project}'s project-specific files
are still DPMtF-WebUI copies. Should these files be updated to reflect
{project}'s own identity?"

CONSEQUENCE:
  - Human says YES → update the project-specific files to reflect the
                     project's own identity and history. Structural files
                     remain unchanged. Document in [[21_ALIGNMENT]] and
                     the project's [[26_CHANGELOG]].
  - Human says NO  → document in [[21_ALIGNMENT]] that staleness is accepted.
```

## Gate Rules

### Precision

- All gates MUST be asked EXACTLY as defined — not paraphrased.
- Use the exact wording from this file.
- Do not add extra context or opinions to the gate question.

### Documentation

Gate answers are documented in:

- [[21_ALIGNMENT]] for GATE-V3, GATE-FEATURE-ROLLOUT, GATE-GOVERNANCE-SYNC.
- [[25_DECISIONS]] for GATE-SCOPE.
- [[26_CHANGELOG]] for GATE-GOVERNANCE-SYNC Trigger B (Child project update).

### Priority

If multiple gates trigger simultaneously, ask in this order:

1. GATE-SCOPE (scope must be resolved first)
2. GATE-V3 (project protection)
3. GATE-MODEL (model selection)
4. GATE-FEATURE-ROLLOUT (cross-project rollout)
5. GATE-GOVERNANCE-SYNC Trigger A (structural divergence)
6. GATE-GOVERNANCE-SYNC Trigger B (project-specific staleness)

### New Gates

New gates can be added as needed:
- Add a new section in this file with TRIGGER, QUESTION, CONSEQUENCE.
- Document the addition in [[26_CHANGELOG]].
- Update [[99_ROLEINTERACTION]] if the gate affects the role loop.

---
