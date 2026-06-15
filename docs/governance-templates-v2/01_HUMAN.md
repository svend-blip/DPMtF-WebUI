# 01 — HUMAN

## Language Policy

> **en-US is the standard language for all governance-templates-v2 files.**
> All non-human communication (prompts, handoffs, bridge messages, role outputs)
> MUST be in English (en-US).
>
> 01_HUMAN.md is the sole exception: the Human may communicate in any language
> they choose. All prompts forwarded through the bridge to other roles MUST be
> translated to English before dispatch.

## Purpose

The Human role is the ultimate authority in the DPMtF governance loop. The Human
owns the product vision, approves all commits, defines scope, and is the only
role permitted to push code to remote repositories. This role replaces and
consolidates the former **Human Approval Gate** and **Release Operator** roles
from the legacy 8-role pipeline.

## When This Role Is Active

- At the start of every new phase or feature cycle (scope definition).
- At every **Human Approval Gate** trigger (see [[20_GATES]]).
- Before any `git commit` or `git push`.
- When escalated to by Review or Architect for decisions exceeding their authority.

## Responsibilities

| Responsibility | Description |
|---|---|
| **Scope Authority** | Define and approve phase scope. Only the Human may authorize scope changes. See [[11_SCOPE]]. |
| **Commit Gate** | All commits MUST be approved by the Human. No other role may commit or push. See [[15_GIT_POLICY]]. |
| **Strategic Direction** | Define project roadmap, phase priorities, and success criteria. |
| **Gate Decisions** | Answer all gate questions (GATE-SCOPE, GATE-V3, GATE-MODEL, GATE-FEATURE-ROLLOUT, GATE-GOVERNANCE-SYNC). See [[20_GATES]]. |
| **Escalation Target** | Final decision-maker when Architect and Review cannot resolve an issue within their authority. |
| **Visual Approval** | Review and approve all visual frontend changes via screenshot comparison. |

## Required Reading

Before acting, the Human reads:

1. [[10_PROJECT]] — project identity, port, repository, current commit.
2. [[11_SCOPE]] — current phase boundaries, in/out of scope.
3. [[99_ROLEINTERACTION]] — the role loop and escalation structure.

The Human may additionally read any reference file as needed.

## Human Approval Gate Triggers

The Human MUST be asked for approval when:

- Visual frontend changes are involved (screenshot review required).
- Database schema changes are proposed (`ALTER TABLE`, new tables).
- New dependencies are added.
- User-visible functionality is removed or permanently deleted.
- The scope changes beyond what [[11_SCOPE]] defines.
- Any `git commit` or `git push` is performed.

## Inputs

| Input | Description |
|---|---|
| Scope proposal | From Architect: proposed phase scope and success criteria. |
| Review verdict | From Review: validated changes with pass/fail verdict. |
| Escalation question | From Architect or Review: decision exceeding their authority. |
| Screenshots | From Implementor/Review: before/after visual comparison. |

## Outputs

| Output | Description |
|---|---|
| Approved scope | Signed-off [[11_SCOPE]] with phase definition. |
| Gate answers | Responses to gate questions documented in [[20_GATES]] and [[25_DECISIONS]]. |
| Commit authorization | Explicit approval for `git commit` / `git push`. |
| Strategic direction | Roadmap decisions, priority changes, new phase initiation. |

## Boundaries

- The Human does NOT write code, generate prompts, or modify files directly
  (except governance documents).
- The Human does NOT interact with the bridge directly — all bridge communication
  is handled by Architect, Implementor, and Review.
- The Human may read any file in any project at any time.

## Related Reference Files

| File | Use When |
|---|---|
| [[10_PROJECT]] | Confirming project identity and current commit. |
| [[11_SCOPE]] | Defining or reviewing phase scope. |
| [[12_CODING_STANDARD]] | Understanding code quality rules. |
| [[15_GIT_POLICY]] | Commit/push authorization. |
| [[20_GATES]] | Answering gate questions. |
| [[21_ALIGNMENT]] | Cross-project feature rollout decisions. |
| [[25_DECISIONS]] | Recording strategic decisions (append-only). |
| [[99_ROLEINTERACTION]] | Understanding the full role loop. |

---
