# 200 — HARDENING V2

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Archives the initial prompt that initiated the governance-templates-v2
hardening. This file serves as the design rationale and requirements
specification for the v2 governance structure.

## Date

2026-06-15

## Initial Prompt

```
This is a governance task to harden the current governance-templates into a
new aggregated governance-templates-v2.

Examine conflicts between:
/home/svend/DPMtF-WebUI/docs/governance-templates
AND
/home/svend/DPMtF-WebUI/docs/governance-templates/superpowertemplates

Create a new folder:
/home/svend/DPMtF-WebUI/docs/governance-templates-v2

The new roles are grouped like this:

Human: The project owner. Architect: Part of the loop when developing new
functionality (running in tmux session claude_architect). Implementor: Part
of the loop when developing new functionality (running in tmux session
claude_implementer). Review: Part of the loop when developing new
functionality (running in tmux session claude_review).

Make new governance-templates-v2, based on the role structure:
- 01_HUMAN.md, 02_ARCHITECT.md, 03_IMPLEMENTOR.md, 04_REVIEW.md
- Reference .md files grouped logically per role
- 99_ROLEINTERACTION.md — the loop between roles with principle of least
  possible HUMAN interaction, scope creep prevention, commit authorization
- 100_BRIDGE.md — bridge improvements: what must be sent between roles,
  input prompt content requirements, escalation structure
- 200_HARDENING_V2.md — this prompt archived

Second loop: conflict check between all new files.
```

## Design Decisions

### Decision 1: 8-Role → 4-Role Consolidation

**Legacy:** The v1 governance templates defined 8 roles: Analyst, Solution
Architect, Prompt Engineer, Implementer, Validator, Human Approval Gate,
Release Operator, Handoff Writer.

**v2:** Consolidated to 4 roles matching the actual bridge workflow:
- **Human** = Human Approval Gate + Release Operator + strategic decisions
- **Architect** = Analyst + Solution Architect + Prompt Engineer + technical design
- **Implementor** = Implementer (code execution, no commit)
- **Review** = Validator + Handoff Writer + quality gate + workflow coordination

**Rationale:** The 8-role pipeline existed only on paper. The actual bridge
workflow used 3 roles (Architect, Implementor, Review) plus Human. The v2
governance files should reflect reality.

### Decision 2: File Numbering Scheme

**Legacy:** 00-17 with superpowertemplates in a subdirectory.

**v2:** Flat numbering 01-04 (roles), 10-29 (references), 99-200 (interaction/bridge/hardening).

**Rationale:** Clear separation between role definitions (01-04), reference
files (10-29), and meta-documents (99-200).

### Decision 3: en-US Language Standard

**Legacy:** Mixed Danish/English — templates in English, superpowertemplates
in Danish.

**v2:** English (en-US) is the mandatory standard for ALL files except
01_HUMAN.md which allows multilingual communication. All bridge prompts
between models MUST be in English.

**Rationale:** Models perform better with English prompts. Consistency
across all governance files reduces confusion. Human can use any language
but forwarded prompts must be translated.

### Decision 4: Reference File Grouping

Reference files (10-29) are grouped by function:
- **10-11:** Project Identity & Scope
- **12-14:** Technical Standards
- **15-19:** Operations & Policies
- **20-22:** Cross-Project Governance
- **23-29:** Runbooks, Reports & Logs

### Decision 5: Father-Child File Classification

**v2:** Clear classification of which files are Father-controlled vs
project-specific:
- **Role definitions (01-04):** Father only — operational concern
- **Structural reference (12-24):** Synchronized with Father
- **Project-specific (10, 11, 25-29):** Independent per project
- **Interaction & Bridge (99-100):** Father only — operational protocols

## Conflicts Found Between Legacy Templates

### Conflict 1: Role Pipeline vs Bridge Reality

`01_ROLES.md` defined Analyst → Solution Architect → Prompt Engineer →
Implementer → Validator → Human Approval Gate → Release Operator →
Handoff Writer. But `bridge-protocol.md` described only 3 roles:
Architect, Implementor, Review. The 8-role pipeline was never used in
practice.

**Resolution:** v2 uses 4 roles matching reality.

### Conflict 2: Superpowertemplates as Parallel System

The superpowertemplates aggregated rules from the 17 main templates but
also added new concepts (gates, alignment, model selection) not present
in the main templates. There was no clear rule for when to read which.

**Resolution:** v2 integrates all content into a single flat structure.
Gates, alignment, and model selection are now first-class reference files
(20, 21, 22).

### Conflict 3: DPMtF-WebUI Templates Serve Dual Purpose

The templates in `docs/governance-templates/` served both as master copies
for initialization AND as active governance for DPMtF-WebUI. This created
confusion about what was template vs project-specific.

**Resolution:** v2's [[10_PROJECT]] explicitly documents the Father-Child
relationship and file classification. DPMtF-WebUI's governance files
reflect DPMtF-WebUI's identity.

### Conflict 4: Language Inconsistency

Main templates were in English. Superpowertemplates were in Danish.
Bridge handoffs mixed both.

**Resolution:** v2 enforces en-US as the standard, with 01_HUMAN.md as the
sole exception for Human communication.

## v2 File Inventory

| # | File | Type | Description |
|---|------|------|-------------|
| 01 | 01_HUMAN.md | Role | Human role — scope authority, commit gate, strategic direction. |
| 02 | 02_ARCHITECT.md | Role | Architect role — design, prompt generation, cross-project oversight. |
| 03 | 03_IMPLEMENTOR.md | Role | Implementor role — prompt execution, code production, self-validation. |
| 04 | 04_REVIEW.md | Role | Review role — validation, diff review, workflow coordination. |
| 10 | 10_PROJECT.md | Reference | Project identity, repository, port, Father-Child relationship. |
| 11 | 11_SCOPE.md | Reference | Phase scope definition, constraints, success criteria. |
| 12 | 12_CODING_STANDARD.md | Reference | Coding rules for Python, JavaScript, CSS, Shell, Markdown. i18n mandatory standard. |
| 13 | 13_VALIDATION.md | Reference | Pre-commit checks, functional validation, prohibited changes. |
| 14 | 14_ARCHITECTURE.md | Reference | System architecture, components, data flow, i18n layers. |
| 15 | 15_GIT_POLICY.md | Reference | Git conventions, Human-gated commits, branch strategy. |
| 16 | 16_FILE_ACCESS.md | Reference | Role-specific file permissions, forbidden paths. |
| 17 | 17_DATABASE.md | Reference | Database vs governance files, schema change policy. |
| 18 | 18_PERMISSION_MODE.md | Reference | Auto-execute boundaries, stop-and-ask rules. |
| 19 | 19_OFFLINE_MODE.md | Reference | Offline operation, local model default, sync recovery. |
| 20 | 20_GATES.md | Reference | Mandatory gate questions before critical operations. |
| 21 | 21_ALIGNMENT.md | Reference | Cross-project feature alignment, Father-Child sync protocol. |
| 22 | 22_MODEL_SELECTION.md | Reference | Model selection decision tree, role-to-model mapping. |
| 23 | 23_RESTART.md | Reference | Application restart, tmux recovery, /clear reconstruction. |
| 24 | 24_TESTPLAN.md | Reference | Test cases, manual verification, sign-off criteria. |
| 25 | 25_DECISIONS.md | Reference | Append-only decision log. |
| 26 | 26_CHANGELOG.md | Reference | Append-only change history. |
| 27 | 27_NEXT_CONTEXT.md | Reference | Session handoff artifact, reconstruction rules. |
| 28 | 28_IMPLEMENTATION_REPORT.md | Reference | Implementation report template. |
| 29 | 29_VALIDATION_REPORT.md | Reference | Validation report template. |
| 99 | 99_ROLEINTERACTION.md | Meta | Role loop, escalation structure, sequential execution guarantee. |
| 100 | 100_BRIDGE.md | Meta | Bridge protocol, handoff formats, improvements over legacy. |
| 200 | 200_HARDENING_V2.md | Meta | This file — design rationale and requirements archive. |

---
