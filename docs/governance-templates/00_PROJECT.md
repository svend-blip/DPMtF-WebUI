# Project Overview

## Purpose

This governance document defines the target project for the current role-based prompt loop session. It establishes identity, ownership, and status so that every role transition (especially after `/clear`) starts from the same factual baseline.

## When to Use

- **Project initializer**: Copy this template before starting a new phase or role sequence.
- **After `/clear`**: Read first to reconstruct project context without relying on chat memory.
- **Role handoff**: All roles reference this file to confirm scope alignment.

---

## Project Name

AI PC Resource WebUI v3

## Purpose

Database-driven web UI for local AI-powered PC resource management, service card orchestration, and Ollama model interaction — built clean from the ground up using DPMtF governance-first principles.

## Owner / Maintainer

Svend Blip

## Repository

/home/svend/ai-pc-resource-webui-v3 (local git)

Remote: https://github.com/svend-blip/ai-pc-resource-webui-v3.git

## Port

9123

## Current Status

Initial skeleton created and pushed. Governance documents initialized in phase 3C-3.

## Current Commit

934a578 3C-2: Create initial v3 skeleton

## Runtime Command

```bash
cd /home/svend/ai-pc-resource-webui-v3
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 9123
```

## Related Projects

- **DPMtF WebUI** — Governance engine. This project is governed by DPMtF governance documents, initialized via `scripts/initialize_target_project_governance.py`.
- **AI PC Resource WebUI v2** (/home/svend/ai-pc-resource-webui-v2) — Functional/design reference only. v3 does not copy v2 code 1:1; v2 serves as inspiration for intended end-state, not as a source to migrate from.

---
