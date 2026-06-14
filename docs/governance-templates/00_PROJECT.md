# Project Overview

## Purpose

This governance document defines the target project for the current role-based prompt loop session. It establishes identity, ownership, and status so that every role transition (especially after `/clear`) starts from the same factual baseline.

## When to Use

- **Project initializer**: Copy this template before starting a new phase or role sequence.
- **After `/clear`**: Read first to reconstruct project context without relying on chat memory.
- **Role handoff**: All roles reference this file to confirm scope alignment.

---

## Project Name

DPMtF-WebUI — Governance-first Orchestration Engine

## Purpose

**Father project** for DPMtF governance framework. Database-driven web UI that serves as the central governance engine — prompt template manager, prompt compiler, validation automation, git sync management, platform adapter framework, Claude Code session manager, and prompt→implementer→validator workflow loop. Holder ALLE governance templates som autoritativ kilde og udruller dem til Child projects via `initialize_target_project_governance.py`.

## Owner / Maintainer

Svend Blip

## Repository

/home/svend/DPMtF-WebUI (local git)

Remote: https://github.com/svend-blip/DPMtF-WebUI.git

## Port

9130

## Current Status

**Blok 6 (2H-2O) komplet.** Alle faser 1A-2O er gennemført og committed. Governance-infrastruktur er fuldt bygget og empirisk valideret (2O: 3 parallel-kørsler, 9/9 first-try lokal model). Python bridge.py med symmetrisk send/complete tmux-kommunikation valideret. Næste roadmap skal defineres.

## Current Commit

c2b81dd feat: Python bridge.py med symmetrisk send/complete tmux-kommunikation

## Runtime Command

```bash
cd /home/svend/DPMtF-WebUI
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 9130
```

## Related Projects

- **ENO** (Evaluate Next Optimization, port 9131) — Første Child project. Database-driven evaluering og optimering af AI prompt execution.
- **ai-pc-resource-webui-v3** (port 9123) — Reference-projekt til test af DPMtF prompt compiler.
- **claude-bridge** (/home/svend/claude-bridge/) — Tmux bridge infrastruktur til cloud↔lokal model kommunikation via Python bridge.py.

---
