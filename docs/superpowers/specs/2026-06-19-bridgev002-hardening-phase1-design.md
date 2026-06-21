---
name: bridgev002-hardening-phase1-config-infrastructure
date: 2026-06-19
handoff: 102
status: approved
---

# BridgeV002 Hardening — Fase 1: Konfiguration & Infrastructure

## Problem Statement

`bridge_lib.py` (BridgeV002 core library) owns independent path-resolution fallbacks that bypass `config.py`, violating the governance rule that `config.py` is the single source of truth for all configurable values. Specifically:

- `resolve_placeholders()` defaults to `"~/.bridge"` when no env-var or parameter is provided
- `_find_project_root()` falls back to `Path.home() / "DPMtF-WebUI"` (hardcoded home-path)
- No `[bridge]` section exists in `dpmtf.ini` — bridge configuration lives implicitly in `[paths] bridge_dir`

Per CLAUDE.md §5: "Hardcoding `/home/svend/...` anywhere else is an auto-fail in validation."

## Scope

| File | Change | Lines (est.) |
|------|--------|-------------|
| `dpmtf.ini` | Add `[bridge] base_path` section | +3 |
| `config.py` | Add `get_bridge_base_path()` getter | +7 |
| `scripts/bridgeV002/bridge_lib.py` | Replace 2 hardcoded fallbacks with config.getters | ~4 |
| `.gitignore` | Add bridge/runtime artifact patterns | +5 |

**Total:** ~19 lines of changes across 4 files.

## Design Decisions (Why These Choices)

### Decision 1: New `[bridge]` section alongside existing `[paths] bridge_dir`

Rationale: No code currently references `[bridge] base_path`, so no breakage. Existing `get_bridge_dir()` remains unchanged. Cleanup of duplicate keys happens after BridgeV002 is stable.

```ini
# BEFORE
[paths]
bridge_dir = /home/svend/claude-bridge

# AFTER (additive only)
[paths]
bridge_dir = /home/svend/claude-bridge

[bridge]
base_path = /home/svend/claude-bridge
```

### Decision 2: `get_bridge_base_path()` is independent of `get_bridge_dir()`

Rationale: Both return the same path value, but are independent getters. This avoids breaking any code that reads `[paths] bridge_dir` directly (bypassing `config.py`). Future cleanup task will consolidate.

Fallback chain:
1. `[bridge] base_path` from dpmtf.ini
2. Derived fallback: `config.get_project_root() / "claude-bridge"` (relative path, not hardcoded)

### Decision 3: Only fix `bridge_dir` fallback in `resolve_placeholders()`

Rationale: `_find_project_root()` refactoring is separate concern — it affects INI loading logic used by role config and flow config. Touched later when scope includes full path independence from `/home/svend`.

### Decision 4: `.gitignore` covers runtime artifacts only

Rationale: Focus on bridge-related artifacts. `node_modules/` and npm artifacts are unrelated to BridgeV002 hardening.

## Detailed Changes

### 1. `dpmtf.ini` — Add `[bridge]` section

Insert before `[projects]` section:

```ini
[bridge]
base_path = /home/svend/claude-bridge
```

### 2. `config.py` — Add `get_bridge_base_path()` getter

Insert after `get_bridge_dir()` (line ~56) for logical grouping:

```python
def get_bridge_base_path() -> str:
    """Bridge base path. .ini [bridge] base_path, or fallback to project_root/claude-bridge."""
    configured = _config.get("bridge", "base_path", fallback=None)
    if configured:
        return configured
    return str(Path(get_project_root()) / "claude-bridge")
```

### 3. `scripts/bridgeV002/bridge_lib.py` — Replace hardcoded fallbacks

**Line 19-26 in `resolve_placeholders()`:**

```python
# BEFORE:
def resolve_placeholders(text, bridge_dir=None, project_root=None):
    """Replace {BRIDGE_DIR}, {PROJECT_ROOT}, {SCRIPTS_DIR} in config values."""
    if bridge_dir is None:
        bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR", os.path.expanduser("~/.bridge"))
    if project_root is None:
        project_root = os.environ.get(
            "DPMTF_PROJECT_ROOT"
        ) or str(Path(__file__).resolve().parent.parent)

# AFTER:
def resolve_placeholders(text, bridge_dir=None, project_root=None):
    """Replace {BRIDGE_DIR}, {PROJECT_ROOT}, {SCRIPTS_DIR} in config values."""
    if bridge_dir is None:
        bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR") or config.get_bridge_base_path()
    if project_root is None:
        project_root = os.environ.get("DPMTF_PROJECT_ROOT") or config.get_project_root()
```

**Why this works:** `bridge_lib.py` already imports `config` (line 17). The new getters are called only when env-vars are absent, providing the same values as before but sourced from dpmtf.ini instead of hardcoded strings.

### 4. `.gitignore` — Add runtime artifact patterns

Append to existing file:

```
# Bridge runtime artifacts
databases/*.bak.*
databases/*.preh99.*
.playwright-mcp/
screenshot-*.png
```

## Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| `get_bridge_base_path()` returns wrong path | Low | Verification step 3 confirms return value |
| Breaking existing code that uses `config.get_bridge_dir()` | None | That function is unchanged |
| `bridge_lib.py` import error | None | Already imports `config`; new getter exists before any call |
| Server needs restart to pick up changes | Yes | Normal — not a failure condition |

## Out of Scope (Deferred)

- Migrating `[paths] bridge_dir` to use only `[bridge] base_path` (future cleanup)
- Refactoring `_find_project_root()` in `bridge_lib.py` (Phase 1 scope per Spørgsmål 3 answer)
- Removing `node_modules/`, `package-lock.json` from untracked status (unrelated focus)

## Verification Steps

1. `python3 -m py_compile config.py` — syntax passes
2. `python3 -m py_compile scripts/bridgeV002/bridge_lib.py` — syntax passes
3. `python3 -c "import config; print(config.get_bridge_base_path())"` → prints `/home/svend/claude-bridge`
4. `python3 scripts/bridgeV002/bridge_lib.py` — runs without errors, shows same output as before
5. `git diff --stat` — shows exactly 4 files changed: dpmtf.ini, config.py, bridge_lib.py, .gitignore
6. `grep -n "'/home/svend" scripts/bridgeV002/bridge_lib.py` — returns NO results post-change (in resolved scope)

## Dependencies

- Requires: Spor J complete (BridgeV002 operational, commits `a2fa53b`, `4d3b1ed`)
- Blocks: Fase 2 (Script Registry), Fase 3 (Convention Rules)
- Uses: `config.py` getter pattern established in handoffs 023-029
