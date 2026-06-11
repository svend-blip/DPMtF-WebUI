# Project Overview

## Purpose

This governance document defines the target project for the current role-based prompt loop session. It establishes identity, ownership, and status so that every role transition (especially after `/clear`) starts from the same factual baseline.

## When to Use

- **Project initializer**: Copy this template before starting a new phase or role sequence.
- **After `/clear`**: Read first to reconstruct project context without relying on chat memory.
- **Role handoff**: All roles reference this file to confirm scope alignment.

## Required Inputs

| Input | Description |
|-------|-------------|
| Project name | The target project being governed in this session. |
| Purpose statement | One-sentence description of what the project does and why it exists. |
| Owner / Maintainer | Person or team responsible for the project. |
| Repository location | URL or local filesystem path. |

## Required Outputs

- A filled-in version of this document in `docs/governance-templates/00_PROJECT.md`.
- Status set to one of: `Active`, `Planning`, `Paused`, `Archived`.
- Last updated date in `YYYY-MM-DD` format.

## Rules / Constraints

- This file is the source of truth for project identity across governance documents.
- Do not rely on chat history or memory as the only source of project facts.
- Related projects (e.g., DPMtF WebUI as governance engine) must be listed explicitly.

## Example Placeholder Sections

```markdown
## Project Name
DPMtF WebUI — Phase 3A Governance Foundation

## Purpose
Governance-first orchestration engine for local AI-driven project development using role-based prompt loops and Markdown-driven process control.

## Owner / Maintainer
Svend Blip

## Repository
/home/svend/DPMtF-WebUI (local git)

## Related Projects
- DPMtF WebUI v2 — Pipeline Status and System Resources panels.
- AI PC Resource WebUI — predecessor project with Ollama integration.

## Status
Active

## Last Updated
2026-06-11
```

---
