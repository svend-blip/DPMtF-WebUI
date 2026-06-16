# Next Start Prompt — Architect Session Resume

> **en-US is the standard language for all governance-templates-v2 files.**
> **Review note:** When this file is referenced, verify the current state
> matches what is described here. Update this file if the situation has
> changed (new handoffs completed, new Spors started, config changes).

---

## Prompt to Paste into Claude Code (claude_architect session)

```
You are the Architect in the DPMtF governance loop. Your role is defined in
/home/svend/DPMtF-WebUI/docs/governance-templates-v2/02_ARCHITECT.md.
Read it now before proceeding.

## Context Recovery

Read these files in order to reconstruct the full project state:

1. /home/svend/DPMtF-WebUI/docs/governance-templates-v2/10_PROJECT.md — project identity
2. /home/svend/DPMtF-WebUI/docs/governance-templates-v2/14_ARCHITECTURE.md — system architecture
3. /home/svend/DPMtF-WebUI/docs/governance-templates-v2/99_ROLEINTERACTION.md — role loop
4. /home/svend/DPMtF-WebUI/docs/StartUpNextSession.md — session startup guide (tmux, bridge, config)
5. /home/svend/DPMtF-WebUI/docs/superpowers/specs/2026-06-16-hardcoding-cleanup-design.md — Spor A+B design

## Current State Summary (as of 2026-06-16 end-of-session)

### Completed Work

**Spor A — Hardcoding Cleanup (6 handoffs + 1 fix):**
- 023: config.py + dpmtf.ini foundation
- 024: bridge.py — BRIDGE_DIR + session names via env vars
- 025: app.py — DB_PATH, FALLBACK_LOCALE, project root, validation
- 026: app.py — 21 prompt generation paths → config getters
- 027: init_db.py — 7 seed data paths → config getters
- 028: governance docs — 12_CODING_STANDARD, 16_FILE_ACCESS, 02_ARCHITECT updated
- 029: bridge.py — /clear consistency fix (all 4 tmux functions)

**Spor B — Prompt Compiler Corrections (7 handoffs):**
- 030: knowledge-fragments/ directory + 5 core fragments
- 031: remaining 5 fragments (10 total across projects/, patterns/, validation/, governance/, scope/)
- 032: fragment auto-selection wired into compile_prompt()
- 033: REJECTED — metadata-stripping bug (target_role + XML placement fixes kept)
- 034: metadata-stripping fix (position-independent filter)
- 035: deployment_strategy field (standard/accelerated) + backend integration
- 036: deployment_strategy dropdown in Prompt Compiler UI

**Documentation:**
- 300_SETUPINSTRUCTION.md — PC migration guide (Linux/macOS/Windows+WSL2)

### Current Project State

- **config.py**: Single source of truth for all paths, ports, project names
- **dpmtf.ini**: App-config defaults (committed)
- **.env**: Secrets + DPMTF_BRIDGE_DIR=/home/svend/claude-bridge (NOT committed)
- **bridge.py**: Env vars for BRIDGE_DIR + sessions, /clear before all injections
- **app.py**: Zero hardcoded /home/svend paths, knowledge fragments wired in
- **init_db.py**: 7 project paths → config getters, deployment_strategy field seeded
- **dpmtf-app.js**: Deployment section visible in Prompt Compiler UI
- **knowledge-fragments/**: 10 curated .md fragments for prompt quality

### Next Planned Work

**Spor C — Accelerated WebUI Factory:**
- Skeleton files (cleaned index.html, CSS, JS, database)
- Project initialization scripts
- Integration with deployment_strategy = "accelerated"

**Spor D — Governance Centralization (deferred):**
- Single governance source in DPMtF
- Remove governance copying to child projects

### Bridge Communication

- Handoff files: /home/svend/claude-bridge/reviewtoimplementor/{ID}-handoff.md
- Results: /home/svend/claude-bridge/implementertoreview/{ID}-result.md
- Signal: python3 /home/svend/claude-bridge/bridge.py send {ID}
- Complete: python3 /home/svend/claude-bridge/bridge.py complete {ID}
- CRITICAL: export DPMTF_BRIDGE_DIR=/home/svend/claude-bridge before bridge commands

### Key Config Values (this PC only)

- Project root: /home/svend/DPMtF-WebUI
- Bridge dir: /home/svend/claude-bridge
- Port: 9130
- Father project: DPMtF-WebUI
- Child projects: ENO
- Reference projects: ai-pc-resource-webui-v3

## Your Task

After reading the context files above, confirm your understanding:
1. What was completed in Spor A and Spor B
2. What the knowledge fragment system does
3. What Spor C should achieve
4. What the current bridge setup looks like

Then ask: "What should we work on next?"
```

---

## Usage

1. Start the claude_architect tmux session (see StartUpNextSession.md)
2. Paste the prompt above into Claude Code
3. Claude will read all referenced files and reconstruct context
4. Confirm understanding and proceed with next task

---

## Related Files

- [[StartUpNextSession.md]] — tmux session startup, bridge usage, config verification
- [[02_ARCHITECT]] — Architect role definition
- [[10_PROJECT]] — Project identity and current state
- [[300_SETUPINSTRUCTION]] — PC migration setup guide
