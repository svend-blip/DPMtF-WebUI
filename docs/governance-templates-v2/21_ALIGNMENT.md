# 21 — CROSS-PROJECT ALIGNMENT

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Tracks feature alignment across DPMtF-governed projects. Defines the rules for
feature rollout, governance synchronization, and the Father-Child project
relationship. Consolidated from the legacy `superpowertemplates/alignmentstructure.md`
and `superpowertemplates/superpowers.md` Section 1.

## When to Use

- **Architect:** Determine which projects are affected by a design.
- **Review:** Assess cross-project impact of changes.
- **Human:** Decide feature rollout strategy.
- **At every session start:** Run Father-Child governance audit.

---

## Project Registry

| Project | Port | Path | Governance | Role |
|---------|------|------|------------|------|
| **DPMtF-WebUI** | 9130 | `/home/svend/DPMtF-WebUI` | Master in `docs/governance-templates-v2/` | Father project — governance engine |
| **ENO** | 9131 | `/home/svend/ENO` | Project-specific only in `docs/dpmtf/`; structural ref from Father | First Child project |
| **ai-pc-resource-webui-v3** | 9123 | `/home/svend/ai-pc-resource-webui-v3` | Project-specific only in `docs/dpmtf/`; structural ref from Father | Reference project |
| **claude-bridge** | — | `/home/svend/claude-bridge/` | Independent | Bridge infrastructure |

---

## File Classification

| Classification | Files | Sync Rule | Description |
|---------------|-------|-----------|-------------|
| **Role definitions** | 01-04 | **Father only** — Child projects do not receive role files (they are governed by Father's roles) | Role definitions are Father's operational concern. |
| **Structural reference** | 12-24 | **Father only** — Child projects reference Father's copies at /home/svend/DPMtF-WebUI/docs/governance-templates-v2/. No local copies. | Rules that apply equally to all projects. Father's version is the single authoritative source. |
| **Project-specific** | 10, 11, 25, 26, 27, 28, 29 | **Independent** — each Child maintains its own version | Project name, port, repository, phase, history, status. MUST reflect project's own identity. |
| **Interaction & Bridge** | 99, 100 | **Father only** — operational protocols | Role interaction and bridge protocol are Father's operational concern. |

## Father-Child Governance Sync Protocol

### Audit Rules (Mandatory at Every Session)

At every session start (when governance files are loaded), run this audit:

1. **Check ALL Child projects' project-specific files** (10, 11, 25, 26, 27, 28, 29).
2. **Audit questions per Child:**
   - [[10_PROJECT]]: Reflects project's actual name, port, repository?
   - [[11_SCOPE]]: Reflects project's actual current phase?
   - [[25_DECISIONS]]: Contains project's own decisions (not Father's)?
   - [[26_CHANGELOG]]: Contains project's own git history (not Father's)?
   - [[27_NEXT_CONTEXT]]: Reflects project's own status (not Father's)?
   - [[28_IMPLEMENTATION_REPORT]]: Reflects project's latest implementation?
   - [[29_VALIDATION_REPORT]]: Reflects project's latest validation?
3. **If discrepancy:** Trigger GATE-GOVERNANCE-SYNC (see [[20_GATES]]).
4. **Verify Child references Father's paths** correctly.
5. **Document findings** in the Alignment Status section below.

> **After Spor D (Governance Centralization):** Structural governance files are NOT copied to child projects. Child projects reference Father's `docs/governance-templates-v2/` directly. Only project-specific files (10_PROJECT.md, 11_SCOPE.md) live in the child's `docs/dpmtf/`.

### Update Process for Project-Specific Files

When GATE-GOVERNANCE-SYNC confirms update:

1. Read Child project's git history (`git log --oneline --all`).
2. Update project-specific files (10, 11, 25, 26, 27, 28, 29) to reflect the project's own identity.
3. Structural reference files (12-24) are Father-only — no local copies in Child projects.
4. Document in Child's [[26_CHANGELOG]] and [[27_NEXT_CONTEXT]].
5. Update the Alignment Status section below.

## Feature Rollout Rules

### Rule 1: Ask If Not Specified

When a feature is implemented in DPMtF-WebUI and rollout is not specified:

> **Ask:** "Is this DPMtF-WebUI only, or should it also roll out to ENO and/or v3?"

Update the Alignment Matrix with the answer.

### Rule 2: Rollout Order

1. Implement in DPMtF-WebUI (Father) first.
2. Roll out to ENO (first Child project).
3. For v3: trigger GATE-V3 first (see [[20_GATES]]).

### Rule 3: DPMtF-WebUI Only

If a feature is only relevant to DPMtF-WebUI (governance tools, prompt compiler,
validation automation):

- Mark in Alignment Matrix with "✅" only for DPMtF-WebUI.
- Set "—" for other projects.
- Add note explaining why.

### Rule 4: New Projects

When a new project is added:

1. Add to Project Registry above.
2. Verify Child references Father's governance paths at `/home/svend/DPMtF-WebUI/docs/governance-templates-v2/`.
3. Evaluate existing features for rollout.
4. Update project-specific files to reflect the new project's identity.

## Alignment Matrix

| Feature | DPMtF-WebUI | ENO | v3 | Date | Note |
|---------|-------------|-----|-----|------|------|
| {Feature name} | {status} | {status} | {status} | {date} | {note} |

**Legend:** ✅ = Implemented | — = Not relevant / Father only | ⏳ = Planned

## Alignment Status

| Area | DPMtF-WebUI ↔ ENO | DPMtF-WebUI ↔ v3 | Note |
|------|-------------------|-------------------|------|
| Structural reference files (12-24) | {status} | {status} | Father only — Child projects reference Father's copies. |
| Project-specific files (10, 11, 25-29) | {status} | {status} | Independent per project. |
| i18n 4-layer architecture | {status} | {status} | All projects use same architecture. |
| Panel groups | {status} | {status} | Panel groups synced. |
| CSS theme | {status} | {status} | Dark theme (GitHub-dark) standard. |

---
