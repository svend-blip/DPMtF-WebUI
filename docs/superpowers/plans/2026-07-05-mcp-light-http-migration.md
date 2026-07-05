# mcp-light HTTP MCP Migration Implementation Plan (Aggressive)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan phase-by-phase. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `/home/svend/mcp-light/server.py`'s manual `BaseHTTPRequestHandler` JSON-RPC server with a real FastMCP streamable-http server on `http://127.0.0.1:9135/mcp`, reusing all 18 tool function bodies and the read-only security layer, so both OpenCode and Claude Code connect to the same endpoint and expose the same 18 read-only tools.

**Architecture:** One clean rewrite of the transport layer — keep constants/security helpers/18 tool bodies, remove `BaseHTTPRequestHandler`/`HTTPServer`/manual JSON-RPC dispatch, register each tool with `@mcp.tool(name=...)`. systemd remains the only runtime manager (no scripts, no sidecar, no `/sse`). OpenCode role configs are standardized in one pass; Claude Code is already registered and just needs to connect. Rollback is via backups + git branch, not by preserving old behavior.

**Tech Stack:** Python 3, `mcp[cli]` (official `modelcontextprotocol/python-sdk` FastMCP v2), pytest (installed but no separate test phase), systemd, OpenCode, Claude Code.

**Spec:** `docs/superpowers/specs/2026-07-05-mcp-light-http-migration-design.md`

## Context

`mcp-light` is not yet used in production workflows, so this migration may be aggressive. Do not preserve the old transport layer. Do not add `/sse`, wrapper scripts, or a sidecar. systemd is the only runtime manager.

## Global Constraints (hard)

- Host `127.0.0.1`, port `9135`, path `/mcp` — unchanged. Never `0.0.0.0`.
- No write tools. No shell-execution tools. No free SQL. No `/sse` workaround. No sidecar. No start/stop scripts.
- Runtime is systemd only.
- Tool names unchanged (frozen list below).
- New dependency `mcp[cli]` approved by Human during brainstorming.
- sudo steps (service file) — Human performs or explicitly authorizes.
- English only for code/comments/commits. Commit format `[phase] description`, no Co-Authored-By trailers.
- Repo boundaries: `mcp-light` repo (`/home/svend/mcp-light/`), opencode-roles dotfiles repo (`~/.config/opencode-roles/`), Father repo (`/home/svend/DPMtF-WebUI/`) — commit each in the right repo. Father repo is NOT modified in this migration (governance rule is a separate follow-up).

### Frozen tool names (18)

```
get_frontend_governance
get_governance_index
get_governance_file
get_required_frontend_impact_block
get_panel_groups
get_panel_subgroups
get_existing_panels
get_index_structure
search_context
search_verdicts
get_flow
get_role
get_flow_steps
get_panel_subgroups_dynamic
get_panel_mappings
validate_frontend_impact
find_reusable_panel
suggest_panel_location
```

---

## Phase 0 — Safety snapshot

- [ ] **Step 1: Git backup branch + system/config backups**

```bash
cd /home/svend/mcp-light
git status
git branch backup/pre-fastmcp-migration-$(date +%Y%m%d-%H%M%S)

sudo cp /etc/systemd/system/mcp-light.service /etc/systemd/system/mcp-light.service.bak-mcp-http

for f in /home/svend/.config/opencode-roles/*/opencode.json; do
  cp "$f" "$f.bak-mcp-http"
done
```

Expected:
- mcp-light git backup branch exists (`git branch` lists it)
- `/etc/systemd/system/mcp-light.service.bak-mcp-http` exists
- `*.opencode.json.bak-mcp-http` files exist for each role

---

## Phase 1 — Create venv and install FastMCP dependency

- [ ] **Step 1: Create venv + install**

```bash
cd /home/svend/mcp-light
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install "mcp[cli]" pytest
pip show mcp
```

- [ ] **Step 2: Update .gitignore**

`/home/svend/mcp-light/.gitignore`:

```text
venv/
__pycache__/
*.pyc
logs/
*.log
```

- [ ] **Step 3: Pin requirements.txt**

`/home/svend/mcp-light/requirements.txt` (use the version from `pip show mcp`):

```text
mcp[cli]==<version-from-pip-show>
```

Do not commit `venv/`.

---

## Phase 2 — Verify FastMCP API quickly

- [ ] **Step 1: Inspect signatures**

```bash
cd /home/svend/mcp-light
source venv/bin/activate

python3 - <<'PY'
import inspect
from mcp.server.fastmcp import FastMCP

print("FastMCP.run:", inspect.signature(FastMCP.run))
print("FastMCP.tool:", inspect.signature(FastMCP.tool))
PY
```

- [ ] **Step 2: Record only what is needed**

Record (mentally or in VERIFICATION.md later):
- correct `run()` parameters
- whether endpoint path is configured via `path=` or `streamable_http_path=`
- whether `@mcp.tool(name=...)` is supported

If `@mcp.tool(name=...)` is not supported, use the SDK-supported equivalent — but the public tool names must remain unchanged.

---

## Phase 3 — Rewrite server.py aggressively

- [ ] **Step 1: Identify what to keep vs remove**

```bash
cd /home/svend/mcp-light
grep -n "^def \|^class \|^TOOLS\|^if __name__\|^ALLOWED\|^DB_PATH\|^[A-Z_]* =" server.py
```

**Keep:**
- constants
- `ALLOWED_ROOTS`, `ALLOWED_FILES`, `DB_PATH`, `ALLOWED_TABLES`, `ALLOWED_COLUMNS`
- `_is_allowed_path`, `_resolve_governance_file`, `_safe_table`, `_safe_columns`, `_get_db_connection`
- all 18 tool function bodies

**Remove:**
- `BaseHTTPRequestHandler`, `HTTPServer`
- manual JSON-RPC dispatcher
- `TOOLS` dict as runtime transport mechanism
- manual `tools/list` and `tools/call` handling
- old GET/POST route handling

- [ ] **Step 2: Add FastMCP import + instance**

Near the top of `/home/svend/mcp-light/server.py`, after stdlib imports:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mcp-light")
```

- [ ] **Step 3: Register each tool with @mcp.tool(name=...)**

Example (function body unchanged):

```python
@mcp.tool(name="get_governance_index", description="Return list of governance v2 templates and their purpose")
def tool_get_governance_index() -> str:
    ...
```

For tools with parameters, add minimal type hints (bodies unchanged):

```python
@mcp.tool(name="get_governance_file", description="Return a specific governance template by name")
def tool_get_governance_file(name: str) -> str:
    ...
```

Apply to all 18 functions with the frozen public names and their existing descriptions (from the `TOOLS` dict being removed). Type-hint parameters for: `tool_get_governance_file(name)`, `tool_search_context(query)`, `tool_search_verdicts(query)`, `tool_get_flow(flow_key)`, `tool_get_role(role_key)`, `tool_get_flow_steps(flow_key)`, `tool_validate_frontend_impact(report_text)`, `tool_find_reusable_panel(feature_name)`, `tool_suggest_panel_location(feature_name)`.

- [ ] **Step 4: Add the final __main__ block**

```python
if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=9135,
        path="/mcp",
    )
```

If `path=` is not valid per Phase 2 findings, use the verified SDK equivalent, e.g. `streamable_http_path="/mcp"`.

---

## Phase 4 — Drop /health unless trivial

- [ ] **Step 1: Decide /health**

Do not block the migration on `/health`. Decision:

```text
If FastMCP supports /health cleanly in the same process, keep it.
If not, drop /health.
Do not add a sidecar.
Do not reintroduce BaseHTTPServer just for /health.
```

Health is verified via:
```bash
systemctl status mcp-light --no-pager
journalctl -u mcp-light -n 80 --no-pager
MCP client list_tools test
```

---

## Phase 5 — Local validation before systemd restart

- [ ] **Step 1: py_compile**

```bash
cd /home/svend/mcp-light
source venv/bin/activate

python3 -m py_compile server.py
```

Preferred: avoid parallel complexity (no temporary-port manual start) and move directly to systemd after compile passes.

---

## Phase 6 — Update systemd service

- [ ] **Step 1: Edit the service file**

`/etc/systemd/system/mcp-light.service` `[Service]` section:

```ini
[Service]
WorkingDirectory=/home/svend/mcp-light
ExecStart=/home/svend/mcp-light/venv/bin/python /home/svend/mcp-light/server.py
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1
```

- [ ] **Step 2: Reload + restart + status**

```bash
sudo systemctl daemon-reload
sudo systemctl restart mcp-light
systemctl status mcp-light --no-pager
journalctl -u mcp-light -n 80 --no-pager
```

Expected: `active (running)`, listening on `127.0.0.1:9135`.

- [ ] **Step 3: Verify listening**

```bash
ss -ltnp | grep 9135
```

---

## Phase 7 — Verify real MCP handshake

- [ ] **Step 1: Python MCP client list_tools**

```bash
cd /home/svend/mcp-light
source venv/bin/activate

python3 - <<'PY'
import asyncio
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession

EXPECTED = {
    "get_frontend_governance",
    "get_governance_index",
    "get_governance_file",
    "get_required_frontend_impact_block",
    "get_panel_groups",
    "get_panel_subgroups",
    "get_existing_panels",
    "get_index_structure",
    "search_context",
    "search_verdicts",
    "get_flow",
    "get_role",
    "get_flow_steps",
    "get_panel_subgroups_dynamic",
    "get_panel_mappings",
    "validate_frontend_impact",
    "find_reusable_panel",
    "suggest_panel_location",
}

async def main():
    async with streamablehttp_client("http://127.0.0.1:9135/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            print("TOOLS:", sorted(names))
            missing = EXPECTED - names
            extra = names - EXPECTED
            assert not missing, f"missing tools: {sorted(missing)}"
            print("OK: all expected tools present")
            if extra:
                print("NOTE: extra tools:", sorted(extra))

asyncio.run(main())
PY
```

Expected: `OK: all expected tools present` (no missing tools).

- [ ] **Step 2: Optional inspector**

```bash
npx -y @modelcontextprotocol/inspector http://127.0.0.1:9135/mcp
```

(Optional — Python client check above is the authoritative proof. Real tool-call testing happens in OpenCode/Claude Code in Phases 9-10.)

---

## Phase 8 — Standardize OpenCode configs in one pass

- [ ] **Step 1: Patch all configs**

Canonical structure:
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

```bash
python3 - <<'PY'
import json
from pathlib import Path

root = Path("/home/svend/.config/opencode-roles")

mcp_light = {
    "type": "remote",
    "url": "http://127.0.0.1:9135/mcp",
    "enabled": True,
    "timeout": 10000,
}

files = sorted(root.glob("*/opencode.json"))

for p in files:
    data = json.loads(p.read_text(encoding="utf-8"))

    # Remove old/noncanonical structure.
    data.pop("mcpServers", None)

    mcp = data.get("mcp")
    if not isinstance(mcp, dict):
        mcp = {}

    mcp["mcp-light"] = mcp_light
    data["mcp"] = mcp

    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("updated", p)
PY
```

- [ ] **Step 2: Verify**

```bash
grep -Rni '"mcpServers"' /home/svend/.config/opencode-roles 2>/dev/null && echo "FAIL: mcpServers still present" || echo "OK: no mcpServers"

for f in /home/svend/.config/opencode-roles/*/opencode.json; do
  echo "---- $f"
  python3 -c "import json; d=json.load(open('$f')); print(d.get('mcp',{}).get('mcp-light'))"
done
```

Expected for every role:
```text
{'type': 'remote', 'url': 'http://127.0.0.1:9135/mcp', 'enabled': True, 'timeout': 10000}
```

---

## Phase 9 — Claude Code verification

- [ ] **Step 1: Check current registration**

```bash
claude mcp list
claude mcp get mcp-light
```

Expected: `mcp-light: http://127.0.0.1:9135/mcp (HTTP)` — connected (it was already registered; now the server is real).

- [ ] **Step 2: Re-register only if still failing**

```bash
claude mcp remove mcp-light
claude mcp add --transport http mcp-light http://127.0.0.1:9135/mcp
claude mcp list
```

- [ ] **Step 3: Functional call**

Inside Claude Code, `/mcp` to confirm connected, then prompt:
```text
Use mcp-light to call get_required_frontend_impact_block.
```

---

## Phase 10 — OpenCode verification

- [ ] **Step 1: Start an active role (e.g. imple01)**

```bash
cd /home/svend/DPMtF-WebUI && CLAUDE_CODE_MAX_OUTPUT_TOKENS=131072 OPENCODE_CONFIG_DIR="$HOME/.config/opencode-roles/imple01" OPENCODE_CONFIG="$HOME/.config/opencode-roles/imple01/opencode.json" /home/svend/.opencode/bin/opencode --model ollama/qwen3.6-27b-coder:latest
```

- [ ] **Step 2: /mcp inside OpenCode**

```text
/mcp
```

Expected:
```text
mcp-light connected
no SSE 404 error
tools visible
```

- [ ] **Step 3: Tool call prompt**

```text
Use mcp-light to call get_governance_index and summarize the available governance templates.
```

Expected: tool call succeeds; no fallback to repo grep required.

---

## Phase 11 — Minimal documentation

- [ ] **Step 1: Create VERIFICATION.md**

`/home/svend/mcp-light/VERIFICATION.md`:

```markdown
# mcp-light FastMCP migration verification

Date: 2026-07-05

## Server

- systemd status: active
- endpoint: http://127.0.0.1:9135/mcp
- transport: streamable-http
- bind: 127.0.0.1 only

## Tools

Verified 18 expected tools via Python MCP client.

## OpenCode

- /mcp shows mcp-light connected
- no SSE 404 observed
- get_governance_index call succeeds

## Claude Code

- claude mcp list shows mcp-light connected
- get_required_frontend_impact_block call succeeds

## Write capability review

No write/create/update/delete/exec tools exposed.
```

---

## Phase 12 — Commits

- [ ] **Step 1: mcp-light repo**

```bash
cd /home/svend/mcp-light
git status
git add .gitignore requirements.txt server.py VERIFICATION.md
git commit -m "[server] Migrate mcp-light to FastMCP streamable-http"
```

Do not add `venv/` (gitignored).

- [ ] **Step 2: opencode-roles repo**

```bash
cd /home/svend/.config/opencode-roles
git status
git add */opencode.json
git commit -m "[configs] Standardize mcp-light HTTP MCP config"
```

Do not commit `.bak-mcp-http` files (gitignored via `*.bak*`).

- [ ] **Step 3: Father repo — NOT modified in this migration**

Do not modify the Father repo in this migration unless the server and both clients are verified. The governance "mcp-light-first" rule is a separate follow-up after real usage is confirmed.

---

## Phase 13 — Rollback

If the FastMCP migration fails:

- [ ] **Step 1: Revert mcp-light repo**

```bash
cd /home/svend/mcp-light
git reset --hard backup/pre-fastmcp-migration-<timestamp>
```

- [ ] **Step 2: Restore systemd**

```bash
sudo cp /etc/systemd/system/mcp-light.service.bak-mcp-http /etc/systemd/system/mcp-light.service
sudo systemctl daemon-reload
sudo systemctl restart mcp-light
```

- [ ] **Step 3: Restore OpenCode configs**

```bash
for f in /home/svend/.config/opencode-roles/*/opencode.json.bak-mcp-http; do
  cp "$f" "${f%.bak-mcp-http}"
done
```

- [ ] **Step 4: Restart/check**

```bash
systemctl status mcp-light --no-pager
journalctl -u mcp-light -n 80 --no-pager
```

---

## Acceptance criteria

Migration is accepted when ALL are true:

```text
1. systemctl status mcp-light shows active running.
2. ss -ltnp shows 127.0.0.1:9135 listening.
3. Python MCP client can initialize against http://127.0.0.1:9135/mcp.
4. Python MCP client lists all 18 expected tools.
5. OpenCode /mcp shows mcp-light connected.
6. OpenCode no longer logs SSE 404.
7. Claude Code mcp-light is connected or can be re-registered as HTTP.
8. No write/exec/delete/update tools are exposed.
9. OpenCode configs use only canonical mcp.mcp-light, not mcpServers.
```

---

## Removed from the earlier plan (complexity reduction)

```text
- separate smoke_server.py on port 9136
- full characterization test phase before rewrite
- hard requirement to preserve /health
- governance rule in the same migration (deferred to follow-up)
- many small commits (collapsed to 2)
- sidecar discussion
- script-based runtime
```

Reason: `mcp-light` is not an active production dependency yet. The safest path is a clean direct migration plus strong rollback.

---

## Self-Review (plan author)

**Spec coverage:** Spec §2 (goals) → Phases 3-10. §3 (decisions) → Global Constraints + Phase 6 (systemd) + Phase 8 (standardize) + Phase 9 (verify-only). §4 (architecture) → Phase 3. §5.1-5.5 → Phases 1,3,6,8,9. §6 (security) → Global Constraints + Phase 3 (reused helpers). §7 phases → Phases 0-13 (governance-rule phase deferred per user direction — noted in Phase 12 Step 3). §8 (SDK verification) → Phase 2. §10 (acceptance) → Acceptance criteria. §11 (risks) → Phase 2 (path kwarg), Phase 6 (sudo). §12 (rollback) → Phase 13. §13 (out of scope) → Global Constraints + "Removed" section. The governance rule (spec §7 phase 8) is intentionally deferred to a follow-up per this plan — a small spec note is added to keep the two docs consistent.

**Placeholder scan:** The only deferred value is the `mcp[cli]` version pin in `requirements.txt` (filled in Phase 1 from `pip show mcp`) and the `path=` vs `streamable_http_path=` choice (resolved in Phase 2, consumed in Phase 3 Step 4). Both have concrete sources. No "TODO"/"TBD".

**Name consistency:** 18 tool names consistent across Global Constraints, Phase 3, Phase 7's EXPECTED set, and Acceptance criteria. `mcp-light` instance/config/registration name consistent everywhere. Port 9135 / path `/mcp` / host 127.0.0.1 consistent everywhere.
