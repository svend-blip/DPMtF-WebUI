# mcp-light — HTTP MCP Transport Migration (Design Spec)

**Date:** 2026-07-05
**Status:** Candidate approved by Human, pending implementation
**Scope:** `/home/svend/mcp-light/` (separate repo) + DPMtF opencode role configs + Claude Code MCP registration

## 1. Problem

`mcp-light` (`/home/svend/mcp-light/server.py`, v1.4.0, phase 4) is a manual
`BaseHTTPRequestHandler` JSON-RPC server. It answers `POST /mcp` for
`tools/list` and `tools/call`, and `GET /health` for a liveness check. All
other paths return 404.

OpenCode and Claude Code expect a real MCP HTTP server (streamable-http
transport with `initialize` / `notifications/initialized` handshake and
`Mcp-Session-Id` management). Symptoms:

- OpenCode: `Mcp-light SSE error: Non-200 status code (404)` — the client
  attempts the MCP HTTP handshake and receives a 404 from the manual server.
- Claude Code: `claude mcp list` reports `mcp-light: ... (HTTP) - ✘ Failed to
  connect`.

The 18 existing tools and the read-only security layer are correct and
unchanged; only the HTTP transport layer is broken.

## 2. Goal

Migrate `mcp-light` from a manual JSON-RPC HTTP server to a real MCP HTTP
server using the official Python MCP SDK (`FastMCP`), exposing the
streamable-http transport on `http://127.0.0.1:9135/mcp`, while reusing all
18 existing tool functions and the existing read-only security rules
unchanged. Standardize all opencode role configs on a single canonical
`mcp` structure. Verify both clients connect and can call tools.

Non-goals (YAGNI):
- No `/sse` quick-workaround (explicitly rejected).
- No start/stop shell scripts — systemd remains the runtime manager.
- No rewrite of tool logic — the 18 `tool_*` functions are reused (behavior
  and read-only security logic unchanged; minimal signature/type-hint
  adjustments allowed only if FastMCP registration requires it).
- No sidecar or second process in this phase (Health endpoints, if needed,
  rely on FastMCP's own capability only — see §5.1).
- No `claude mcp add` — Claude Code already has mcp-light registered as HTTP.

## 3. Decisions (approved)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| HTTP transport implementation | FastMCP + venv | Official SDK guarantees protocol correctness; minimal code; future-proof |
| Runtime management | Keep systemd | Already active+enabled; preserves autostart + auto-restart; consistent with current ops |
| Opencode config scope | Standardize all 11 consistently | Fix 2 broken + add `timeout:10000` to 9 working; one canonical structure |
| Claude Code config | Verify only (no action) | `claude mcp list` shows it already registered as HTTP; will auto-connect once server is real |

**Dependency approval:** installing `mcp[cli]` in a venv is a new dependency
(CLAUDE.md auto-fail #6). The Human explicitly approved this in the
brainstorming session.

## 4. Architecture

```
┌──────────────────────────────────────────────────────────┐
│  /home/svend/mcp-light/server.py  (rewritten)            │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  FastMCP transport layer  (NEW)                    │  │
│  │  - streamable-http on /mcp                         │  │
│  │  - initialize / notifications/initialized handshake│  │
│  │  - Mcp-Session-Id management                       │  │
│  └───────────────────────┬────────────────────────────┘  │
│                          │ calls                         │
│  ┌───────────────────────┴────────────────────────────┐  │
│  │  18 tool functions  (REUSED unchanged)             │  │
│  │  tool_get_governance_index, tool_get_flow, ...     │  │
│  │  decorated with @mcp.tool()                        │  │
│  └───────────────────────┬────────────────────────────┘  │
│                          │                               │
│  ┌───────────────────────┴────────────────────────────┐  │
│  │  Security layer  (REUSED unchanged)                │  │
│  │  _is_allowed_path, _safe_table, realpath, 127.0.0.1│  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
              ↑                                    ↑
   ┌──────────┴──────────┐              ┌─────────┴─────────┐
   │ systemd             │              │ venv               │
   │ mcp-light.service   │              │ /home/svend/       │
   │ ExecStart → venv-py │              │  mcp-light/venv    │
   └─────────────────────┘              │  (mcp[cli] pip)    │
                                        └────────────────────┘
```

**Key principle:** replace only the HTTP transport layer; reuse all tool
logic and security rules. The 18 `tool_*` functions are pure,
transport-independent logic (read files/DB, return text). Decorating them
with `@mcp.tool()` and reusing the implementation minimizes risk and
preserves the security rules already hardened across phases 1-4. Tool
behavior and read-only security logic must remain unchanged; minimal
function signature/type-hint adjustments are allowed only if required by
FastMCP registration.

## 5. Components

### 5.1 `server.py` (rewritten)

- Import `from mcp.server.fastmcp import FastMCP`.
- `mcp = FastMCP("mcp-light")`.
- Each of the 18 existing `tool_*` functions is decorated with `@mcp.tool()`
  and exposed under the same name. Tool behavior and read-only security
  logic remain unchanged; minimal function signature/type-hint adjustments
  are allowed only if required by FastMCP registration.
- Tool names preserved exactly (clients depend on them):
  `get_frontend_governance`, `get_governance_index`, `get_governance_file`,
  `get_required_frontend_impact_block`, `get_panel_groups`,
  `get_panel_subgroups`, `get_existing_panels`, `get_index_structure`,
  `search_context`, `search_verdicts`, `get_flow`, `get_role`,
  `get_flow_steps`, `get_panel_subgroups_dynamic`, `get_panel_mappings`,
  `validate_frontend_impact`, `find_reusable_panel`, `suggest_panel_location`.
- `__main__` block calls
  `mcp.run(transport="streamable-http", host="127.0.0.1", port=9135, path="/mcp")`.
  Exact parameter names are verified against the installed SDK version in
  Phase 1 before the block is written.
- `/health` endpoint: retain `/health` only if FastMCP supports it without a
  sidecar. If FastMCP cannot serve a non-MCP custom route, drop `/health` in
  this phase and rely on `systemctl status mcp-light`, `journalctl -u
  mcp-light`, and MCP client/inspector checks for liveness. Do not add a
  sidecar unless the Human explicitly approves it. Resolved in Phase 1.

### 5.2 `venv/` (new)

- Created at `/home/svend/mcp-light/venv`.
- `pip install -U pip && pip install "mcp[cli]"`.
- `requirements.txt` updated to list `mcp[cli]` with a version pin.

### 5.3 `mcp-light.service` (updated)

- `ExecStart` changed from `/usr/bin/python3 /home/svend/mcp-light/server.py`
  to `/home/svend/mcp-light/venv/bin/python /home/svend/mcp-light/server.py`.
- `Environment=PYTHONUNBUFFERED=1` added for reliable logs.
- Before editing, back up the service file:
  `sudo cp /etc/systemd/system/mcp-light.service /etc/systemd/system/mcp-light.service.bak-mcp-http`
- After editing:
  `sudo systemctl daemon-reload && sudo systemctl restart mcp-light && systemctl status mcp-light --no-pager`
- Requires `sudo` for the edit + reload + restart (Human performs or
  explicitly authorizes).

### 5.4 Opencode role configs (standardized)

**Preflight before patching** — confirm exactly which role configs exist and
which mention mcp/mcpServers/mcp-light/9135:

```bash
find /home/svend/.config/opencode-roles -maxdepth 2 -name opencode.json -print
grep -Rni '"mcp"\|"mcpServers"\|"mcp-light"\|9135' /home/svend/.config/opencode-roles 2>/dev/null
```

Patch only existing role configs that are confirmed relevant by the preflight.

All role configs that have (or should have) mcp-light get one canonical
structure:

```json
"mcp": {
  "mcp-light": {
    "type": "remote",
    "url": "http://127.0.0.1:9135/mcp",
    "enabled": true,
    "timeout": 10000
  }
}
```

Concrete actions:
- `implementer` — currently uses `mcpServers`; migrate to `mcp` block with
  mcp-light entry.
- `review` — currently has neither `mcp` nor `mcpServers`; add the full
  canonical block.
- The other 9 (`glm52trade`, `imple01`, `imple01pay`, `review01`,
  `review01cloud`, `review01pay`, `review02`, `review02cloud`, `review02pay`)
  — already have the correct `mcp` block; add `timeout:10000` for
  consistency.
- `mcpServers` is removed everywhere it still appears.

A `.bak-mcp-http` backup of each config is taken before patching (rollback
hook).

### 5.5 Claude Code config (verify only)

`claude mcp list` already shows
`mcp-light: http://127.0.0.1:9135/mcp (HTTP)`. No `claude mcp add` needed.
After the server migration it should auto-connect. Only if it still fails
after migration: `claude mcp remove mcp-light && claude mcp add --transport
http mcp-light http://127.0.0.1:9135/mcp`.

## 6. Security rules (preserved from current server)

The server may only:
- read whitelisted files
- read whitelisted SQLite tables
- run fixed queries
- return text/JSON
- validate paths with `realpath`
- bind to `127.0.0.1`

The server may not:
- write files
- modify the database
- run shell commands
- accept free SQL
- follow paths outside `ALLOWED_ROOTS`
- expose on `0.0.0.0`

These are already implemented (`_is_allowed_path`, `_safe_table`,
`_safe_columns`, `realpath` resolution, 127.0.0.1 bind) and are reused
unchanged in the rewritten `server.py`.

## 7. Phased implementation

| Phase | Action | Replaces doc phase |
|-------|--------|--------------------|
| 1 | SDK verification: create venv, install `mcp[cli]`, inspect `FastMCP.run` signature; resolve `/health` custom-route question | New (replaces doc's SDK uncertainty) |
| 2 | Rewrite `server.py` around FastMCP, reuse 18 tool functions unchanged | Doc Fase 1, with reuse principle |
| 3 | Update `mcp-light.service` `ExecStart` + `requirements.txt` | New (doc had scripts instead) |
| 4 | `systemctl daemon-reload && systemctl restart mcp-light` | Replaces doc Fase 2 start script |
| 5 | Standardize all 11 opencode configs (fix 2 broken + add timeout to 9); backup `.bak-mcp-http` first | Doc Fase 4, with corrected file list |
| 6 | Claude Code: verify `claude mcp list` shows connected (no action expected) | Doc Fase 5, reduced to verification |
| 7 | Verification: MCP inspector + tool calls from both clients | Doc Fase 3 + 8 |
| 8 | Add governance rule to startup prompts (mcp-light first when task touches governance/frontend/bridge) — **deferred to a separate follow-up after real usage is confirmed; not part of this migration** | Doc Fase 7 |
| 9 | Rollback procedure documented (git revert in mcp-light repo + restore configs from `.bak-mcp-http`) | Doc Fase 9 |

## 8. SDK verification (Phase 1, before code)

```bash
cd /home/svend/mcp-light && python3 -m venv venv && source venv/bin/activate
pip install -U pip && pip install "mcp[cli]"
python3 -c "from mcp.server.fastmcp import FastMCP; import inspect; print(inspect.signature(FastMCP.run))"
```

Only once the real `FastMCP.run` signature is known is the `__main__` block
of `server.py` written. This replaces guesswork about parameter names.

## 9. Error handling

- Tool functions' existing error handling (try/except, path validation) is
  preserved.
- FastMCP converts tool exceptions into MCP error responses automatically.
- systemd `Restart=on-failure` monitors process death (not `/health`).

## 10. Testing / acceptance criteria

1. `python3 -m py_compile server.py` passes before restart.
2. If `/health` is retained, `curl -s http://127.0.0.1:9135/health` returns
   `{"status":"ok",...}`. If `/health` is not retained (dropped per §5.1),
   this is not a failure — liveness is verified via `systemctl status
   mcp-light` and `journalctl -u mcp-light` instead.
3. `npx -y @modelcontextprotocol/inspector http://127.0.0.1:9135/mcp` lists
   all 18 tools (requires node/npm — availability verified in Phase 7).
4. `claude mcp list` shows mcp-light connected.
5. OpenCode `/mcp` shows mcp-light connected; no `SSE 404` error.
6. `get_governance_index` callable from both clients.
7. `get_required_frontend_impact_block` callable from both clients.
8. No write-capabilities exposed (manual review of tool list).

## 11. Risks

- **FastMCP `/health` custom route:** uncertain whether FastMCP permits
  non-MCP routes. Resolved in Phase 1. Per §5.1: retain only if supported
  without a sidecar; otherwise drop `/health` (no sidecar in this phase).
- **MCP inspector requires node/npm:** availability must be verified in
  Phase 7.
- **SDK breaking changes:** `mcp[cli]` is under active development;
  `requirements.txt` must version-pin.
- **`sudo` required for service file:** the Human must perform the
  `mcp-light.service` edit + `systemctl daemon-reload` + restart, or
  authorize Claude to run them with sudo.

## 12. Rollback

- `cd /home/svend/mcp-light && git revert <migration-commit>` to restore the
  manual `BaseHTTPRequestHandler` server.
- Restore opencode configs from `.bak-mcp-http` backups (per-file `cp`).
- `systemctl restart mcp-light` (after reverting service file `ExecStart`
  to `/usr/bin/python3`).
- `claude mcp remove mcp-light` only if Claude Code is broken.

## 13. Out of scope

- Start/stop shell scripts (systemd handles runtime).
- `/sse` workaround (explicitly rejected).
- `claude mcp add` (already registered).
- Rewrite of tool logic (reused unchanged).
- Any change to the 18 tool names or signatures.
- Governance "mcp-light-first" startup-prompt rule — deferred to a separate
  follow-up after real usage is confirmed (not part of this migration).
