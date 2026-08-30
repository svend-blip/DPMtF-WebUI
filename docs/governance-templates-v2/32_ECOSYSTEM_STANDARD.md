# 32 — Ecosystem Standard (naming, UI, ports, boundaries)

> Binding across the six ecosystem repositories: **DPMtF-WebUI** (Father),
> **model-allocator**, **harness-allocator**, **simple-harness**,
> **DPMtF-LightWorker**, **mcp-light**. Established 2026-08-30 (Human
> alignment decision, recorded in 25_DECISIONS.md). Where a repo's own
> governance conflicts, this file rules for cross-repo naming and UI;
> the repo rules for its internals.

## 1. Vocabulary (one term, one meaning, everywhere)

| Term | Meaning | Not to be confused with |
|------|---------|-------------------------|
| **Model** | The actual LLM (real_model, e.g. `MiniMax-M3`) | Alias |
| **Alias** | model-allocator's logical name for a model + runtime choice (`cloud_minimax`) | Model |
| **Backend** | The runtime kind serving a model (`ollama`, `llama_cpp`, `sglang`, `freetoken`, `openai_compatible`, `anthropic`, `external`) | Harness |
| **Runtime profile** | model-allocator's named backend configuration; the UI section listing them is called **Backends** | — |
| **Harness** | The coding interface a role runs (`claude-code`, `opencode`, `codex`, `dsh`, `qwen`, `goose`, `crush`, `whip`, `simple-harness`) | Client (retired term in UI) |
| **Client** | model-allocator's internal name for a harness adapter (`clients:` in models.yaml, `allocator_client` on roles). UI-facing labels say **Harness** | — |
| **Flow / Role / Step / Run / Handoff** | BridgeV002 terms, defined by 100_BRIDGE.md | — |
| **LaunchSpec / StopSpec / ResetSpec** | harness-allocator's per-harness declarations: how an interface starts, stops, and resets its context | — |

Danish UI labels use: Harness (uændret), Backend (uændret), Alias
(uændret), Model (uændret), Flow (uændret). Never translate these.

## 2. Ownership boundaries (Human-pinned 2026-08-25)

- **model-allocator** owns models and runtimes: which model an alias
  resolves to, which backend serves it, endpoint and credentials (by
  env-var NAME, never value).
- **harness-allocator** owns every interface launch: argv, env shape,
  LaunchSpec/StopSpec/ResetSpec, the harness roster. `launch_owner` in
  the spec says who builds the launch (native → harness-allocator;
  claude-code/opencode/whip → model-allocator's client adapters — a
  declared asymmetry, formalized rather than migrated).
- **DPMtF-WebUI (Father)** owns orchestration: flows, roles, dispatch,
  tmux, gates, the DB. It consumes both allocators — model-allocator
  via CLI subprocess, harness-allocator as an imported package — and
  hardcodes neither's knowledge.
- **simple-harness** is an execution kernel for one role; it refuses
  orchestration, harness selection, and model allocation by SCOPE.
- **DPMtF-LightWorker** executes role envelopes on a remote machine via
  Father's HTTP API; it has its own model-allocator instance and never
  touches Father's DB.
- **mcp-light** is the read-only context server (governance, flows,
  roles, panel structure) on 9135. It reads Father's DB and imports
  Father's `execution_config` — a deliberate, documented coupling.

## 3. Port register (ports are data — config, never hardcoded)

| Port | Service | Config source |
|------|---------|---------------|
| 9130 | DPMtF-WebUI (Father) | dpmtf.ini `[app] port` |
| 9135 | mcp-light (loopback + tailnet unit) | `MCP_LIGHT_PORT` |
| 9141 | model-allocator web UI | `ALLOCATOR_WEB_PORT` |
| 9142 | harness-allocator web UI (`python3 -m harness_allocator.web`) | `HARNESS_WEB_PORT` |
| 9121 | ai-pc-resource-webui-v2 (adjacent, not one of the six) | its systemd unit |

Father's frontend reaches the companion UIs via
`GET /api/bridge-v2/ui-links` (backed by `[integration]` in dpmtf.ini).
A hardcoded port in JS is an auto-fail.

## 4. UI standard (every web frontend in the ecosystem)

- GitHub-dark palette, no light theme.
- `lbl(key, fallback)` for every user-facing string; no hardcoded
  English. Standalone components without the 4-layer DB chain may use a
  local label table, but the `lbl()` call shape is mandatory.
- No `innerHTML` for dynamic content; `createElement`/`textContent`.
- Event delegation on containers; `const`/`let`, never `var` in new code.
- Class-based CSS selectors; no inline `style=""` for layout.
- Panel groups with expand/collapse; empty groups are hidden
  (`is_visible = 0`), not rendered as shells. Vocabulary pickers guide
  with datalists; they do not gate (free text stays possible).
- A web UI without auth binds loopback by default; widening the bind is
  an explicit config decision.

## 5. README standard

`31_README_STANDARD.md` is authoritative; `scripts/validate_readme.py`
is the gate (Requirements → Installation (3 H3s) → Configuration →
Running → Testing). Every ecosystem repo's README must pass with 0
errors and reflect current state — a README that documents two of nine
harnesses is stale, not short.

## 6. Context reset (per harness — item 15, 2026-08-30)

Declared in harness-allocator's `get_reset_spec(harness)` and served by
Father's `GET /api/bridge-v2/harnesses`:

| Harness | Reset |
|---------|-------|
| claude-code | `/clear` (in-session) |
| opencode | `/new` (in-session) |
| codex | restart — no in-session reset; `codex_fresh_context_policy=work_unit` is exactly this |
| dsh | restart (terminal wrapper launches per wakeup) |
| qwen, goose, crush, whip, simple-harness | restart — a fresh invocation IS a fresh context |
| sweagent, aider (experimental) | restart |

Father's per-role `fresh_session_command` column is the operational
knob dispatch sends before injection; the ResetSpec is the harness fact
it must agree with.
