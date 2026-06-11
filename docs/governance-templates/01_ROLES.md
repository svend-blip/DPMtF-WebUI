# Roles

## Purpose

This governance document defines the roles used in the DPMtF role-based prompt loop, each role's responsibilities, and the rules for handoff between roles. The complete role flow ensures that every phase passes through analysis, design, implementation, validation, and controlled release before handoff.

## When to Use

- **Project initializer**: Fill in role assignments before starting a new session.
- **Role transition**: Read this file to determine the current role and next role.
- **After `/clear`**: Reconstruct which role is active and what governance files to read.

## Role Flow

The canonical role flow for each phase or task:

```
Analyst → Solution Architect → Prompt Engineer → Implementer → Validator
→ [Human Approval Gate, if required] → Release Operator → Handoff Writer
```

| Step | Role | Responsibility |
|------|------|---------------|
| 1 | **Analyst** | Analyze requirements, scope, and constraints. Produce a scoped analysis document. |
| 2 | **Solution Architect** | Design the technical approach. Define architecture changes, data flow impact, and risk assessment. |
| 3 | **Prompt Engineer** | Generate specific implementation prompts from governance files and the architect's design. Prompts must reference this document explicitly. |
| 4 | **Implementer** | Execute prompts and produce code or configuration changes. Must validate locally before handing off to Validator. |
| 5 | **Validator** | Verify changes against coding standards, validation rules, and scope constraints. Run syntax checks, diff reviews, and functional tests. |
| 6 | **Human Approval Gate** *(conditional)* | Final human review before commit when visual changes, schema changes, or dependency additions are involved. See [[06_VALIDATION]] for triggers. |
| 7 | **Release Operator** | Commit verified changes, update changelog, and perform optional sync (GitHub push) if online. |
| 8 | **Handoff Writer** | Update `NEXT_CONTEXT.md` with session state, completed work, remaining work, and open questions for the next session. |

## Role Handoff Rules

1. Each role reads the governance files before acting. Minimum: `00_PROJECT.md`, `01_ROLES.md`, `02_SCOPE.md`.
2. Analyst output feeds into Solution Architect input.
3. Solution Architect design feeds into Prompt Engineer prompt generation.
4. Validator must pass before Human Approval Gate is requested.
5. **Use `/clear` between role transitions** to reset the context window. See [[07_RESTART]] for details.
6. After `/clear`, prompts must be reconstructed from governance documents and `NEXT_CONTEXT.md`. Do not rely on chat memory as the only source of truth.

## Local Agent Roles (ROLELOCAL)

When running locally with offline models, the same role pipeline applies but all execution happens on-machine:

- Use local LLM (e.g., Ollama) for each role step.
- Use local git for version control — it is the source of truth. See [[15_GIT_POLICY]].
- No external API calls unless explicitly authorized per-run.
- If offline, commit locally and mark push as pending. See [[14_OFFLINE_MODE]].

## Required Inputs

| Input | Description |
|-------|-------------|
| Active phase key | E.g., `3A — Governance Foundation`. |
| Current role in the flow | Which role is acting now. |
| Previous role output | The document, design, prompts, or changes produced by the prior step. |

## Required Outputs

- Completed role output (analysis document, architecture design, generated prompts, code changes, validation report, commit, or handoff note).
- Updated `NEXT_CONTEXT.md` reflecting the transition.

## Human Approval Triggers

Human approval via **Human Approval Gate** is required when:

- Visual frontend changes are involved (screenshot review required).
- Database schema changes are proposed (`ALTER TABLE`, new tables).
- New dependencies are added.
- User-visible functionality is removed or permanently deleted.
- The scope changes beyond what `02_SCOPE.md` defines.

---
