# 10 — PROJECT

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines the target project's identity, ownership, repository, and current
status. This is the first file read after `/clear` to reconstruct project
context without relying on chat memory.

## When to Use

- **All roles:** Read at session start to confirm project identity.
- **After `/clear`:** Read first (after [[27_NEXT_CONTEXT]]) to reconstruct context.
- **Project initializer:** Fill in before starting a new phase.

---

## Project Name

{PROJECT_NAME} — {SHORT_DESCRIPTION}

## Purpose

{1-3 sentences describing what this project does and its role in the DPMtF ecosystem.}

## Owner / Maintainer

{OWNER_NAME}

## Repository

{PATH_TO_LOCAL_GIT}

Remote: {REMOTE_URL}

## Port

{PORT_NUMBER}

## Current Status

{1-2 sentences describing current project status, completed phases, active phase.}

## Current Commit

{HEAD_COMMIT_HASH} ({COMMIT_DESCRIPTION})

## Runtime Command

```bash
cd {PROJECT_PATH}
.venv/bin/uvicorn app:app --host 0.0.0.0 --port {PORT} --reload
```

## Related Projects

Locations come from `config.get_project_path(name)`; the names below are the
`[projects]` entries in `dpmtf.ini`.

- **DPMtF-WebUI** (port 9130) — Father project.
  Governance engine that owns all master governance templates.
- **ENO** (port 9131) — First Child project.
- **ai-pc-resource-webui-v3** (port 9123) —
  Reference project for testing the DPMtF prompt compiler.
- **BridgeV002** — Integrated into DPMtF-WebUI (`scripts/bridgeV002/`).
  Database-driven dispatch system replacing the legacy `claude-bridge`.
  Flow-specific deliverable directories under `DPMTF_BRIDGE_DIR`.

## Father vs Child Projects

### Father Project (DPMtF-WebUI)

DPMtF-WebUI's `docs/governance-templates-v2/` is the **authoritative source**
for all governance rules. Child projects reference these files directly — no local
copies of structural governance files. DPMtF-WebUI's own governance files reflect
DPMtF-WebUI's identity — not a generic template.

### Child Projects (ENO, v3, future)

After Spor D (Governance Centralization): Child projects **do not receive copies**
of structural reference files (12-24). Instead, they reference Father's files at
`config.get_governance_dir_abs()`. **Project-specific files**
(10, 11, 25, 26, 27, 28, 29) are maintained independently in each Child's
`docs/dpmtf/` directory to reflect its own identity, phase, and history.

### Governance Sync Protocol

See [[21_ALIGNMENT]] for the full Father-Child governance sync protocol,
audit rules, and file classification.

---
