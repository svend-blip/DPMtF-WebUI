# Model Allocator config-dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Father WebUI a dedicated "Model Allocator" page that edits the allocator's aliases + roles (CRUD) and shows/controls runtime status, backed by new write commands in the allocator CLI.

**Architecture:** Two repos. **Phase 1** adds a `config` subcommand group to the `model-allocator` CLI (`config_writer.py` + `cli.py` wiring) that reads config as JSON and writes `models.yaml` / `roles.yaml` with validation, `.bak` backup, and atomic replace. **Phase 2** adds 5 endpoints in the Father WebUI (`routers/bridge.py`) that shell out to those commands (mirroring the existing `list`/`validate`/`status` endpoints), a new `static/js/allocator.js` 3-column dashboard, a new panel-group in `index.html`, CSS, and i18n label seeds.

**Tech Stack:** Python 3.10+, PyYAML 6.0 (already a dep), argparse, pytest; FastAPI + FastAPI TestClient; vanilla JS (no framework), CSS.

## Global Constraints

- **No new dependencies.** PyYAML 6.0 already present in `model-allocator`; FastAPI/pytest/httpx already present in Father. (CLAUDE.md §4.7)
- **No hardcoded `/home/svend/...` paths.** In Father use `config.get_project_path("model-allocator")`. In the CLI use `_config_dir(args)` / `_default_config_dir()`. (CLAUDE.md §3)
- **Parameterized SQL only** — `?` placeholders (init_db.py seeds). (CLAUDE.md §4)
- **No `innerHTML` for dynamic content** — `el()` / `textContent` / `appendChild` / `replaceChildren` / `clear()`. Auto-fail. (CLAUDE.md §4)
- **All user-facing JS text via `lbl(key, fallback)`**; static HTML via `data-slot`. Every new label seeded in **both `da-DK` and `en-US`**. (CLAUDE.md §4, §9)
- **JS:** `const`/`let` only (never `var` in new code), class-based CSS selectors, no inline layout `style=""`, dark GitHub-dark theme, event delegation. (CLAUDE.md §4)
- **Python:** `python3 -m py_compile` must pass; PEP 8; type hints where practical. (CLAUDE.md §4)
- **Git:** Human commits both repos; format `[phase] description`, English, one logical change per commit, `git add <files>` selectively. Human commit permission granted for this work. (CLAUDE.md §5)
- **CLI raw-load rule:** the config editor must read/write **raw** YAML values (do NOT env-resolve `${VAR}`); `config_loader.load_config` env-resolves and must not be reused for the editor path.

---

## Phase 1 — `model-allocator` CLI write layer

> All Phase 1 paths are relative to `/home/svend/model-allocator`. Run tests with `python3 -m pytest` from that repo root.

### Task 1: `config_writer.py` — raw load, validation, safe write

**Files:**
- Create: `src/model_allocator/config_writer.py`
- Test: `tests/test_config_writer.py`

**Interfaces:**
- Produces:
  - `class ConfigWriteError(Exception)`
  - `load_raw(config_dir: str | Path) -> dict` → `{"aliases": {...}, "roles": {...}, "profiles": {...}}` (raw, no env resolution)
  - `set_alias(config_dir, name: str, definition: dict) -> None`
  - `delete_alias(config_dir, name: str) -> None`
  - `set_role(config_dir, name: str, definition: dict) -> None`
  - `delete_role(config_dir, name: str) -> None`

- [ ] **Step 1: Write the failing test**

Create `tests/test_config_writer.py`:

```python
import copy
from pathlib import Path

import pytest

from model_allocator import config_writer as cw


BASE_MODELS = {
    "models": {
        "imple-fast": {"runtime_profile": "local_ollama_cuda0", "real_model": "qwen:latest"}
    }
}
BASE_ROLES = {
    "roles": {
        "imple01": {"default_alias": "imple-fast", "config_dir": "imple01",
                    "client_aliases": {"opencode": "imple-fast"}}
    }
}
BASE_PROFILES = {
    "runtime_profiles": {"local_ollama_cuda0": {"backend": "ollama"}}
}


def _seed(tmp_path: Path) -> Path:
    import yaml
    (tmp_path / "models.yaml").write_text(yaml.safe_dump(BASE_MODELS), encoding="utf-8")
    (tmp_path / "roles.yaml").write_text(yaml.safe_dump(BASE_ROLES), encoding="utf-8")
    (tmp_path / "runtime_profiles.yaml").write_text(yaml.safe_dump(BASE_PROFILES), encoding="utf-8")
    return tmp_path


def test_load_raw_returns_three_sections(tmp_path):
    d = _seed(tmp_path)
    raw = cw.load_raw(d)
    assert set(raw) == {"aliases", "roles", "profiles"}
    assert "imple-fast" in raw["aliases"]
    assert "imple01" in raw["roles"]
    assert "local_ollama_cuda0" in raw["profiles"]


def test_load_raw_does_not_resolve_env(tmp_path):
    import yaml
    d = _seed(tmp_path)
    (d / "models.yaml").write_text(
        yaml.safe_dump({"models": {"llama": {"runtime_profile": "local_ollama_cuda0",
                                             "model_path": "${MODEL_ROOT_GGUF}/x.gguf"}}}),
        encoding="utf-8")
    raw = cw.load_raw(d)
    assert raw["aliases"]["llama"]["model_path"] == "${MODEL_ROOT_GGUF}/x.gguf"


def test_set_alias_upserts_and_roundtrips(tmp_path):
    d = _seed(tmp_path)
    cw.set_alias(d, "new-alias", {"runtime_profile": "local_ollama_cuda0", "real_model": "m:1"})
    raw = cw.load_raw(d)
    assert raw["aliases"]["new-alias"]["real_model"] == "m:1"
    assert "imple-fast" in raw["aliases"]  # existing preserved


def test_set_alias_rejects_unknown_profile(tmp_path):
    d = _seed(tmp_path)
    with pytest.raises(cw.ConfigWriteError):
        cw.set_alias(d, "bad", {"runtime_profile": "nope", "real_model": "m"})


def test_set_alias_writes_backup(tmp_path):
    d = _seed(tmp_path)
    cw.set_alias(d, "new-alias", {"runtime_profile": "local_ollama_cuda0", "real_model": "m"})
    assert (d / "models.yaml.bak").exists()


def test_delete_alias_refused_when_referenced(tmp_path):
    d = _seed(tmp_path)
    with pytest.raises(cw.ConfigWriteError):
        cw.delete_alias(d, "imple-fast")  # referenced by role imple01


def test_delete_alias_removes_unreferenced(tmp_path):
    d = _seed(tmp_path)
    cw.set_alias(d, "temp", {"runtime_profile": "local_ollama_cuda0", "real_model": "m"})
    cw.delete_alias(d, "temp")
    assert "temp" not in cw.load_raw(d)["aliases"]


def test_set_role_rejects_dangling_alias(tmp_path):
    d = _seed(tmp_path)
    with pytest.raises(cw.ConfigWriteError):
        cw.set_role(d, "r2", {"default_alias": "ghost", "config_dir": "r2"})


def test_set_role_upserts(tmp_path):
    d = _seed(tmp_path)
    cw.set_role(d, "r2", {"default_alias": "imple-fast", "config_dir": "r2",
                          "client_aliases": {"opencode": "imple-fast"}})
    assert "r2" in cw.load_raw(d)["roles"]


def test_delete_role_removes(tmp_path):
    d = _seed(tmp_path)
    cw.delete_role(d, "imple01")
    assert "imple01" not in cw.load_raw(d)["roles"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config_writer.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'model_allocator.config_writer'`

- [ ] **Step 3: Write the implementation**

Create `src/model_allocator/config_writer.py`:

```python
"""Read/write allocator config (models.yaml, roles.yaml) for the config editor.

Unlike config_loader.load_config, this loads RAW values (no ${ENV} resolution)
so edits round-trip without baking resolved env values back into the files.
runtime_profiles.yaml is read-only here and is never written.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import yaml


class ConfigWriteError(Exception):
    """Raised when a config write is rejected (validation or IO)."""


def _find(config_dir: Path, name: str) -> Path:
    for ext in (".yaml", ".yml"):
        candidate = config_dir / f"{name}{ext}"
        if candidate.exists():
            return candidate
    return config_dir / f"{name}.yaml"


def _raw_load(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_raw(config_dir: str | Path) -> dict:
    """Load raw aliases/roles/profiles without env-var resolution."""
    d = Path(config_dir)
    return {
        "aliases": _raw_load(_find(d, "models")).get("models", {}) or {},
        "roles": _raw_load(_find(d, "roles")).get("roles", {}) or {},
        "profiles": _raw_load(_find(d, "runtime_profiles")).get("runtime_profiles", {}) or {},
    }


def _safe_write(path: Path, top_key: str, body: dict) -> None:
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        yaml.safe_dump({top_key: body}, fh, sort_keys=False, allow_unicode=True)
    os.replace(tmp, path)


def _role_alias_refs(role: dict) -> list:
    refs = []
    if role.get("default_alias"):
        refs.append(role["default_alias"])
    refs.extend((role.get("client_aliases") or {}).values())
    return refs


def set_alias(config_dir: str | Path, name: str, definition: dict) -> None:
    if not name:
        raise ConfigWriteError("alias name is required")
    d = Path(config_dir)
    raw = load_raw(d)
    profile = definition.get("runtime_profile")
    if profile and profile not in raw["profiles"]:
        raise ConfigWriteError(f"unknown runtime_profile: {profile}")
    aliases = raw["aliases"]
    aliases[name] = definition
    _safe_write(_find(d, "models"), "models", aliases)


def delete_alias(config_dir: str | Path, name: str) -> None:
    d = Path(config_dir)
    raw = load_raw(d)
    for role_name, role in raw["roles"].items():
        if name in _role_alias_refs(role):
            raise ConfigWriteError(f"alias '{name}' is referenced by role '{role_name}'")
    aliases = raw["aliases"]
    if name not in aliases:
        raise ConfigWriteError(f"unknown alias: {name}")
    del aliases[name]
    _safe_write(_find(d, "models"), "models", aliases)


def set_role(config_dir: str | Path, name: str, definition: dict) -> None:
    if not name:
        raise ConfigWriteError("role name is required")
    d = Path(config_dir)
    raw = load_raw(d)
    known = set(raw["aliases"].keys())
    for ref in _role_alias_refs(definition):
        if ref not in known:
            raise ConfigWriteError(f"role references unknown alias: {ref}")
    roles = raw["roles"]
    roles[name] = definition
    _safe_write(_find(d, "roles"), "roles", roles)


def delete_role(config_dir: str | Path, name: str) -> None:
    d = Path(config_dir)
    raw = load_raw(d)
    roles = raw["roles"]
    if name not in roles:
        raise ConfigWriteError(f"unknown role: {name}")
    del roles[name]
    _safe_write(_find(d, "roles"), "roles", roles)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_config_writer.py -q`
Expected: PASS (10 passed)

- [ ] **Step 5: Compile check**

Run: `python3 -m py_compile src/model_allocator/config_writer.py`
Expected: no output (exit 0)

- [ ] **Step 6: Commit**

```bash
git add src/model_allocator/config_writer.py tests/test_config_writer.py
git commit -m "[V4] config_writer: raw load + validated safe write for aliases/roles"
```

---

### Task 2: Wire `config` subcommands into the CLI

**Files:**
- Modify: `src/model_allocator/cli.py` (add command functions + `build_parser` subparsers)
- Test: `tests/test_config_cli.py`

**Interfaces:**
- Consumes: `config_writer` functions from Task 1; `_config_dir`, `EXIT_OK`, `EXIT_ERROR`, `EXIT_USAGE` from `cli.py`.
- Produces CLI: `config show`, `config set-alias --name X --json '{...}'`, `config delete-alias --name X`, `config set-role --name X --json '{...}'`, `config delete-role --name X`. `show` prints `{"aliases":...,"roles":...,"profiles":...}` JSON to stdout. Errors print `{"error": "..."}` JSON to stderr and return `EXIT_ERROR`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_config_cli.py`:

```python
import json
from pathlib import Path

import yaml

from model_allocator.cli import main


def _seed(tmp_path: Path) -> Path:
    (tmp_path / "models.yaml").write_text(
        yaml.safe_dump({"models": {"a1": {"runtime_profile": "p1", "real_model": "m"}}}),
        encoding="utf-8")
    (tmp_path / "roles.yaml").write_text(
        yaml.safe_dump({"roles": {}}), encoding="utf-8")
    (tmp_path / "runtime_profiles.yaml").write_text(
        yaml.safe_dump({"runtime_profiles": {"p1": {"backend": "ollama"}}}), encoding="utf-8")
    return tmp_path


def test_config_show_prints_json(tmp_path, capsys):
    d = _seed(tmp_path)
    rc = main(["--config-dir", str(d), "config", "show"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "a1" in out["aliases"]
    assert out["profiles"]["p1"]["backend"] == "ollama"


def test_config_set_alias_writes(tmp_path, capsys):
    d = _seed(tmp_path)
    payload = json.dumps({"runtime_profile": "p1", "real_model": "m2"})
    rc = main(["--config-dir", str(d), "config", "set-alias", "--name", "a2", "--json", payload])
    assert rc == 0
    assert "a2" in yaml.safe_load((d / "models.yaml").read_text())["models"]


def test_config_set_alias_bad_profile_returns_error(tmp_path, capsys):
    d = _seed(tmp_path)
    payload = json.dumps({"runtime_profile": "ghost", "real_model": "m"})
    rc = main(["--config-dir", str(d), "config", "set-alias", "--name", "bad", "--json", payload])
    assert rc == 1
    assert "error" in json.loads(capsys.readouterr().err)


def test_config_delete_role(tmp_path):
    d = _seed(tmp_path)
    (d / "roles.yaml").write_text(
        yaml.safe_dump({"roles": {"r1": {"default_alias": "a1", "config_dir": "r1"}}}),
        encoding="utf-8")
    rc = main(["--config-dir", str(d), "config", "delete-role", "--name", "r1"])
    assert rc == 0
    assert yaml.safe_load((d / "roles.yaml").read_text())["roles"] == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config_cli.py -q`
Expected: FAIL — `config` is an invalid choice / SystemExit(2)

- [ ] **Step 3: Add command functions to `cli.py`**

Add these imports near the top of `cli.py` (after the existing `from model_allocator...` imports):

```python
from model_allocator import config_writer
```

Add these functions just above `def build_parser()`:

```python
def cmd_config_show(args: argparse.Namespace) -> int:
    raw = config_writer.load_raw(_config_dir(args))
    print(json.dumps(raw, indent=2, default=str))
    return EXIT_OK


def _parse_json_arg(raw: str) -> dict:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise config_writer.ConfigWriteError(f"invalid --json payload: {exc}")
    if not isinstance(value, dict):
        raise config_writer.ConfigWriteError("--json payload must be a JSON object")
    return value


def _config_write(args: argparse.Namespace, action) -> int:
    try:
        action()
    except config_writer.ConfigWriteError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return EXIT_ERROR
    print(json.dumps({"ok": True, "name": args.name}))
    return EXIT_OK


def cmd_config_set_alias(args: argparse.Namespace) -> int:
    try:
        definition = _parse_json_arg(args.json)
    except config_writer.ConfigWriteError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return EXIT_ERROR
    return _config_write(args, lambda: config_writer.set_alias(_config_dir(args), args.name, definition))


def cmd_config_delete_alias(args: argparse.Namespace) -> int:
    return _config_write(args, lambda: config_writer.delete_alias(_config_dir(args), args.name))


def cmd_config_set_role(args: argparse.Namespace) -> int:
    try:
        definition = _parse_json_arg(args.json)
    except config_writer.ConfigWriteError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return EXIT_ERROR
    return _config_write(args, lambda: config_writer.set_role(_config_dir(args), args.name, definition))


def cmd_config_delete_role(args: argparse.Namespace) -> int:
    return _config_write(args, lambda: config_writer.delete_role(_config_dir(args), args.name))
```

- [ ] **Step 4: Register the subparsers in `build_parser()`**

Immediately before `return parser` at the end of `build_parser()`, add:

```python
    p_config = sub.add_parser("config", help="Read/write allocator config (aliases, roles)")
    config_sub = p_config.add_subparsers(dest="config_command", required=True)

    c_show = config_sub.add_parser("show", help="Print full config (aliases, roles, profiles) as JSON")
    c_show.set_defaults(func=cmd_config_show)

    c_set_alias = config_sub.add_parser("set-alias", help="Create/update an alias")
    c_set_alias.add_argument("--name", required=True, help="Alias name")
    c_set_alias.add_argument("--json", required=True, help="Alias definition as a JSON object")
    c_set_alias.set_defaults(func=cmd_config_set_alias)

    c_del_alias = config_sub.add_parser("delete-alias", help="Delete an alias")
    c_del_alias.add_argument("--name", required=True, help="Alias name")
    c_del_alias.set_defaults(func=cmd_config_delete_alias)

    c_set_role = config_sub.add_parser("set-role", help="Create/update a role")
    c_set_role.add_argument("--name", required=True, help="Role name")
    c_set_role.add_argument("--json", required=True, help="Role definition as a JSON object")
    c_set_role.set_defaults(func=cmd_config_set_role)

    c_del_role = config_sub.add_parser("delete-role", help="Delete a role")
    c_del_role.add_argument("--name", required=True, help="Role name")
    c_del_role.set_defaults(func=cmd_config_delete_role)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_config_cli.py tests/test_config_writer.py -q`
Expected: PASS (all)

- [ ] **Step 6: Full suite + compile + manual smoke**

Run: `python3 -m pytest -q && python3 -m py_compile src/model_allocator/cli.py`
Expected: full suite green, no compile output.

Manual smoke (from repo root, against real config):
Run: `./scripts/model-allocator config show | python3 -m json.tool | head`
Expected: JSON with `aliases`, `roles`, `profiles` keys.

- [ ] **Step 7: Commit**

```bash
git add src/model_allocator/cli.py tests/test_config_cli.py
git commit -m "[V4] CLI: config show/set-alias/delete-alias/set-role/delete-role subcommands"
```

---

## Phase 2 — Father WebUI (`/home/svend/DPMtF-WebUI`)

> Run tests with `python3 -m pytest` from the Father repo root. `routers/bridge.py` already imports `os`, `json`, `subprocess`, `config`, and `HTTPException`.

### Task 3: Backend endpoints in `routers/bridge.py`

**Files:**
- Modify: `routers/bridge.py` (add 5 endpoints after the existing `/allocator/stop` endpoint)
- Test: `tests/test_allocator_config_endpoints.py`

**Interfaces:**
- Consumes: `config.get_project_path("model-allocator")`, the wrapper `scripts/model-allocator`, and the Phase-1 `config` subcommands.
- Produces HTTP:
  - `GET /api/bridge-v2/allocator/config` → `{"aliases":{...},"roles":{...},"profiles":{...}}`
  - `POST /api/bridge-v2/allocator/config/alias` body `{"name": str, "definition": obj}` → `{"ok": true}`
  - `DELETE /api/bridge-v2/allocator/config/alias/{name}` → `{"ok": true}`
  - `POST /api/bridge-v2/allocator/config/role` body `{"name": str, "definition": obj}` → `{"ok": true}`
  - `DELETE /api/bridge-v2/allocator/config/role/{name}` → `{"ok": true}`
  - Validation/CLI failure → HTTP 400 with the CLI's error message; timeout/other → 502.

- [ ] **Step 1: Write the failing test**

Create `tests/test_allocator_config_endpoints.py`:

```python
import json
import subprocess

import routers.bridge as bridge


def _completed(stdout="", stderr="", rc=0):
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


def test_get_config_returns_sections(client, monkeypatch):
    payload = {"aliases": {"a1": {}}, "roles": {}, "profiles": {"p1": {}}}
    monkeypatch.setattr(bridge.subprocess, "run",
                        lambda *a, **k: _completed(stdout=json.dumps(payload)))
    resp = client.get("/api/bridge-v2/allocator/config")
    assert resp.status_code == 200
    assert resp.json()["aliases"] == {"a1": {}}


def test_post_alias_ok(client, monkeypatch):
    captured = {}

    def fake_run(cmd, *a, **k):
        captured["cmd"] = cmd
        return _completed(stdout=json.dumps({"ok": True, "name": "a2"}))

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    resp = client.post("/api/bridge-v2/allocator/config/alias",
                       json={"name": "a2", "definition": {"runtime_profile": "p1"}})
    assert resp.status_code == 200
    assert "set-alias" in captured["cmd"]
    assert "--name" in captured["cmd"] and "a2" in captured["cmd"]


def test_post_alias_validation_error_is_400(client, monkeypatch):
    monkeypatch.setattr(bridge.subprocess, "run",
                        lambda *a, **k: _completed(stderr=json.dumps({"error": "unknown runtime_profile: ghost"}), rc=1))
    resp = client.post("/api/bridge-v2/allocator/config/alias",
                       json={"name": "bad", "definition": {"runtime_profile": "ghost"}})
    assert resp.status_code == 400
    assert "ghost" in resp.json()["detail"]


def test_delete_role_ok(client, monkeypatch):
    captured = {}

    def fake_run(cmd, *a, **k):
        captured["cmd"] = cmd
        return _completed(stdout=json.dumps({"ok": True, "name": "r1"}))

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    resp = client.delete("/api/bridge-v2/allocator/config/role/r1")
    assert resp.status_code == 200
    assert "delete-role" in captured["cmd"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_allocator_config_endpoints.py -q`
Expected: FAIL — 404 (routes not defined).

- [ ] **Step 3: Add the endpoints**

Find the end of the existing `/allocator/stop` endpoint in `routers/bridge.py` and add, after it:

```python
def _allocator_script() -> str:
    return os.path.join(
        config.get_project_path("model-allocator"),
        "scripts",
        "model-allocator",
    )


def _run_allocator(cmd_args: list) -> subprocess.CompletedProcess:
    """Run the allocator CLI, raising HTTPException on failure.

    A nonzero exit is treated as a validation/usage error (HTTP 400) whose
    detail is the CLI's error message (JSON {"error": ...} on stderr, or raw text).
    """
    try:
        result = subprocess.run(
            [_allocator_script()] + cmd_args,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=502, detail="model-allocator timed out after 30s")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"model-allocator error: {exc}")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        try:
            detail = json.loads(detail).get("error", detail)
        except json.JSONDecodeError:
            pass
        raise HTTPException(status_code=400, detail=detail or "model-allocator config command failed")
    return result


@router.get("/allocator/config")
async def bridge_v2_allocator_config():
    """Return the full allocator config (aliases, roles, profiles)."""
    result = _run_allocator(["config", "show"])
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"model-allocator config show returned invalid JSON: {exc}")


@router.post("/allocator/config/alias")
async def bridge_v2_allocator_set_alias(request: Request):
    data = await request.json()
    name = data.get("name")
    definition = data.get("definition")
    if not name or not isinstance(definition, dict):
        raise HTTPException(status_code=400, detail="name and definition (object) are required")
    _run_allocator(["config", "set-alias", "--name", name, "--json", json.dumps(definition)])
    return {"ok": True}


@router.delete("/allocator/config/alias/{name}")
async def bridge_v2_allocator_delete_alias(name: str):
    _run_allocator(["config", "delete-alias", "--name", name])
    return {"ok": True}


@router.post("/allocator/config/role")
async def bridge_v2_allocator_set_role(request: Request):
    data = await request.json()
    name = data.get("name")
    definition = data.get("definition")
    if not name or not isinstance(definition, dict):
        raise HTTPException(status_code=400, detail="name and definition (object) are required")
    _run_allocator(["config", "set-role", "--name", name, "--json", json.dumps(definition)])
    return {"ok": True}


@router.delete("/allocator/config/role/{name}")
async def bridge_v2_allocator_delete_role(name: str):
    _run_allocator(["config", "delete-role", "--name", name])
    return {"ok": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_allocator_config_endpoints.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Compile + full bridge test suite**

Run: `python3 -m py_compile routers/bridge.py app.py && python3 -m pytest tests/test_bridge_endpoints.py tests/test_allocator_config_endpoints.py -q`
Expected: no compile output; tests green.

- [ ] **Step 6: Commit**

```bash
git add routers/bridge.py tests/test_allocator_config_endpoints.py
git commit -m "[V4] WebUI: allocator config CRUD endpoints (config show/set/delete)"
```

---

### Task 4: i18n label seeds + panel-group markup + CSS

**Files:**
- Modify: `scripts/init_db.py` (append label rows to the 4 i18n layers — **approval-required file**)
- Modify: `templates/index.html` (new `pg-allocator` panel-group + second `<script>`)
- Modify: `static/css/dpmtf-theme.css` (3-column grid classes)

**Interfaces:**
- Produces label keys (used by Task 5/6/7 via `lbl()`): `pg_allocator`, `lbl_alloc_aliases`, `lbl_alloc_roles`, `lbl_alloc_detail`, `lbl_alloc_new_alias`, `lbl_alloc_new_role`, `lbl_alloc_profiles`, `lbl_alloc_select_hint`, `lbl_alloc_field_name`, `lbl_alloc_field_profile`, `lbl_alloc_field_model`, `lbl_alloc_field_model_path`, `lbl_alloc_field_context`, `lbl_alloc_field_lifecycle`, `lbl_alloc_field_clients`, `lbl_alloc_field_config_dir`, `lbl_alloc_field_default_alias`, `lbl_alloc_field_client_aliases`, `lbl_alloc_save`, `lbl_alloc_delete`, `lbl_alloc_saved`, `lbl_alloc_confirm_delete`.
- Produces DOM mount point: `<div id="allocator-dashboard">` inside a `panel-group`.
- Produces CSS classes: `.allocator-grid`, `.allocator-col`, `.allocator-list-item`, `.allocator-list-item.selected`.

- [ ] **Step 1: Append the `ui_labels` rows**

In `scripts/init_db.py`, inside the `_bridge_setup_labels = [ ... ]` list, immediately before the closing `]` (the line at the end containing just `]` followed by `for label in _bridge_setup_labels:`), add:

```python
    # ── V4: Model Allocator config-dashboard labels ──
    ("LBL-1000400", "pg_allocator", "main", "🧩 Model Allocator", "Model Allocator panel group heading"),
    ("LBL-1000401", "lbl_alloc_aliases", "main", "Aliases", "Allocator aliases column heading"),
    ("LBL-1000402", "lbl_alloc_roles", "main", "Roles", "Allocator roles column heading"),
    ("LBL-1000403", "lbl_alloc_detail", "main", "Detail", "Allocator detail column heading"),
    ("LBL-1000404", "lbl_alloc_new_alias", "main", "+ New alias", "Create new alias button"),
    ("LBL-1000405", "lbl_alloc_new_role", "main", "+ New role", "Create new role button"),
    ("LBL-1000406", "lbl_alloc_profiles", "main", "Runtime profiles (read-only)", "Runtime profiles reference heading"),
    ("LBL-1000407", "lbl_alloc_select_hint", "main", "Select an alias or role to edit", "Empty detail hint"),
    ("LBL-1000408", "lbl_alloc_field_name", "main", "Name", "Name field label"),
    ("LBL-1000409", "lbl_alloc_field_profile", "main", "Runtime profile", "Runtime profile field label"),
    ("LBL-1000410", "lbl_alloc_field_model", "main", "Real model", "Real model field label"),
    ("LBL-1000411", "lbl_alloc_field_model_path", "main", "Model path", "Model path field label"),
    ("LBL-1000412", "lbl_alloc_field_context", "main", "Context", "Context field label"),
    ("LBL-1000413", "lbl_alloc_field_lifecycle", "main", "Lifecycle policy", "Lifecycle policy field label"),
    ("LBL-1000414", "lbl_alloc_field_clients", "main", "Clients", "Clients field label"),
    ("LBL-1000415", "lbl_alloc_field_config_dir", "main", "Config dir", "Config dir field label"),
    ("LBL-1000416", "lbl_alloc_field_default_alias", "main", "Default alias", "Default alias field label"),
    ("LBL-1000417", "lbl_alloc_field_client_aliases", "main", "Client aliases", "Client aliases field label"),
    ("LBL-1000418", "lbl_alloc_save", "main", "Save", "Save button"),
    ("LBL-1000419", "lbl_alloc_delete", "main", "Delete", "Delete button"),
    ("LBL-1000420", "lbl_alloc_saved", "main", "Saved", "Saved confirmation message"),
    ("LBL-1000421", "lbl_alloc_confirm_delete", "main", "Delete '{name}'?", "Confirm delete dialog message"),
```

- [ ] **Step 2: Append the translation rows (`da-DK` + `en-US`)**

Locate the translations list in `init_db.py` — the list containing rows like `("LBL-1000377", "en-US", "Stop the allocator runtime for '{alias}'?")` and `("LBL-1000377", "da-DK", "Stop allocator-runtime for '{alias}'?")`. Immediately before that list's closing `]`, add:

```python
    ("LBL-1000400", "en-US", "🧩 Model Allocator"), ("LBL-1000400", "da-DK", "🧩 Model Allocator"),
    ("LBL-1000401", "en-US", "Aliases"), ("LBL-1000401", "da-DK", "Aliaser"),
    ("LBL-1000402", "en-US", "Roles"), ("LBL-1000402", "da-DK", "Roller"),
    ("LBL-1000403", "en-US", "Detail"), ("LBL-1000403", "da-DK", "Detalje"),
    ("LBL-1000404", "en-US", "+ New alias"), ("LBL-1000404", "da-DK", "+ Nyt alias"),
    ("LBL-1000405", "en-US", "+ New role"), ("LBL-1000405", "da-DK", "+ Ny rolle"),
    ("LBL-1000406", "en-US", "Runtime profiles (read-only)"), ("LBL-1000406", "da-DK", "Runtime-profiler (skrivebeskyttet)"),
    ("LBL-1000407", "en-US", "Select an alias or role to edit"), ("LBL-1000407", "da-DK", "Vælg et alias eller en rolle for at redigere"),
    ("LBL-1000408", "en-US", "Name"), ("LBL-1000408", "da-DK", "Navn"),
    ("LBL-1000409", "en-US", "Runtime profile"), ("LBL-1000409", "da-DK", "Runtime-profil"),
    ("LBL-1000410", "en-US", "Real model"), ("LBL-1000410", "da-DK", "Model"),
    ("LBL-1000411", "en-US", "Model path"), ("LBL-1000411", "da-DK", "Model-sti"),
    ("LBL-1000412", "en-US", "Context"), ("LBL-1000412", "da-DK", "Kontekst"),
    ("LBL-1000413", "en-US", "Lifecycle policy"), ("LBL-1000413", "da-DK", "Livscyklus-politik"),
    ("LBL-1000414", "en-US", "Clients"), ("LBL-1000414", "da-DK", "Klienter"),
    ("LBL-1000415", "en-US", "Config dir"), ("LBL-1000415", "da-DK", "Config-mappe"),
    ("LBL-1000416", "en-US", "Default alias"), ("LBL-1000416", "da-DK", "Standard-alias"),
    ("LBL-1000417", "en-US", "Client aliases"), ("LBL-1000417", "da-DK", "Klient-aliaser"),
    ("LBL-1000418", "en-US", "Save"), ("LBL-1000418", "da-DK", "Gem"),
    ("LBL-1000419", "en-US", "Delete"), ("LBL-1000419", "da-DK", "Slet"),
    ("LBL-1000420", "en-US", "Saved"), ("LBL-1000420", "da-DK", "Gemt"),
    ("LBL-1000421", "en-US", "Delete '{name}'?"), ("LBL-1000421", "da-DK", "Slet '{name}'?"),
```

> If the translations list rows are `(label_id, locale, text)` tuples as shown, match that arity exactly. If the surrounding rows include a 4th element, append that element's observed default to each row above to match.

- [ ] **Step 3: Append the slot-definition and slot-label rows**

Locate the two smaller lists near the end of the bridge label seeding:
1. The list with rows like `("lbl_bridge_validate_allocator", "Validate allocator alias button")` (slot definitions: `(slot_key, description)`).
2. The list with rows like `("lbl_bridge_validate_allocator", "lbl_bridge_validate_allocator")` (slot→label mapping).

Into list (1), before its closing `]`, add one row per new key:

```python
    ("pg_allocator", "Model Allocator panel group heading"),
    ("lbl_alloc_aliases", "Allocator aliases column heading"),
    ("lbl_alloc_roles", "Allocator roles column heading"),
    ("lbl_alloc_detail", "Allocator detail column heading"),
    ("lbl_alloc_new_alias", "Create new alias button"),
    ("lbl_alloc_new_role", "Create new role button"),
    ("lbl_alloc_profiles", "Runtime profiles reference heading"),
    ("lbl_alloc_select_hint", "Empty detail hint"),
    ("lbl_alloc_field_name", "Name field label"),
    ("lbl_alloc_field_profile", "Runtime profile field label"),
    ("lbl_alloc_field_model", "Real model field label"),
    ("lbl_alloc_field_model_path", "Model path field label"),
    ("lbl_alloc_field_context", "Context field label"),
    ("lbl_alloc_field_lifecycle", "Lifecycle policy field label"),
    ("lbl_alloc_field_clients", "Clients field label"),
    ("lbl_alloc_field_config_dir", "Config dir field label"),
    ("lbl_alloc_field_default_alias", "Default alias field label"),
    ("lbl_alloc_field_client_aliases", "Client aliases field label"),
    ("lbl_alloc_save", "Save button"),
    ("lbl_alloc_delete", "Delete button"),
    ("lbl_alloc_saved", "Saved confirmation message"),
    ("lbl_alloc_confirm_delete", "Confirm delete dialog message"),
```

Into list (2), before its closing `]`, add one `(key, key)` row per new key:

```python
    ("pg_allocator", "pg_allocator"),
    ("lbl_alloc_aliases", "lbl_alloc_aliases"),
    ("lbl_alloc_roles", "lbl_alloc_roles"),
    ("lbl_alloc_detail", "lbl_alloc_detail"),
    ("lbl_alloc_new_alias", "lbl_alloc_new_alias"),
    ("lbl_alloc_new_role", "lbl_alloc_new_role"),
    ("lbl_alloc_profiles", "lbl_alloc_profiles"),
    ("lbl_alloc_select_hint", "lbl_alloc_select_hint"),
    ("lbl_alloc_field_name", "lbl_alloc_field_name"),
    ("lbl_alloc_field_profile", "lbl_alloc_field_profile"),
    ("lbl_alloc_field_model", "lbl_alloc_field_model"),
    ("lbl_alloc_field_model_path", "lbl_alloc_field_model_path"),
    ("lbl_alloc_field_context", "lbl_alloc_field_context"),
    ("lbl_alloc_field_lifecycle", "lbl_alloc_field_lifecycle"),
    ("lbl_alloc_field_clients", "lbl_alloc_field_clients"),
    ("lbl_alloc_field_config_dir", "lbl_alloc_field_config_dir"),
    ("lbl_alloc_field_default_alias", "lbl_alloc_field_default_alias"),
    ("lbl_alloc_field_client_aliases", "lbl_alloc_field_client_aliases"),
    ("lbl_alloc_save", "lbl_alloc_save"),
    ("lbl_alloc_delete", "lbl_alloc_delete"),
    ("lbl_alloc_saved", "lbl_alloc_saved"),
    ("lbl_alloc_confirm_delete", "lbl_alloc_confirm_delete"),
```

> Match the exact arity/shape of the rows already in each list. If either list uses a different tuple shape than shown here (verify by reading 2-3 existing rows), adapt these rows to that shape before inserting.

- [ ] **Step 4: Add the panel-group markup + script tag to `index.html`**

In `templates/index.html`, after the closing `</section>` of `pg-setup` (the line `</section>` that closes `<section class="panel-group" id="pg-setup">`, i.e. right before `</main>`), add:

```html
        <!-- Model Allocator -->
        <section class="panel-group" id="pg-allocator">
            <div class="panel-group-header" data-group="allocator">
                <h2 data-slot="pg_allocator">🧩 Model Allocator</h2>
                <span class="panel-group-toggle">▼</span>
            </div>
            <div class="panel-group-body">
                <div id="allocator-dashboard"></div>
            </div>
        </section>
```

Then change the single script tag at the bottom from:

```html
    <script src="/static/js/dpmtf-app.js"></script>
```

to:

```html
    <script src="/static/js/dpmtf-app.js"></script>
    <script src="/static/js/allocator.js"></script>
```

- [ ] **Step 5: Add CSS classes to `dpmtf-theme.css`**

Append to `static/css/dpmtf-theme.css`:

```css
/* ── Model Allocator dashboard ── */
.allocator-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1.6fr;
  gap: 12px;
  align-items: start;
}
@media (max-width: 900px) {
  .allocator-grid { grid-template-columns: 1fr; }
}
.allocator-col {
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 10px;
  background: #0d1117;
}
.allocator-list-item {
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  color: #c9d1d9;
}
.allocator-list-item:hover { background: #161b22; }
.allocator-list-item.selected { background: #1f6feb33; color: #58a6ff; }
.allocator-profiles { margin-top: 12px; font-size: 0.85em; color: #8b949e; }
```

- [ ] **Step 6: Verify DB seed + no innerHTML + compile**

Run: `python3 scripts/init_db.py && python3 scripts/seed_bridge.py`
Expected: runs without error (idempotent).

Run: `grep -RIn "innerHTML" static/ templates/`
Expected: empty (the new markup uses no innerHTML).

Run: `python3 -c "import sqlite3; c=sqlite3.connect('databases/dpmtf.db'); print(c.execute(\"SELECT COUNT(*) FROM ui_labels WHERE label_key LIKE 'lbl_alloc_%'\").fetchone())"`
Expected: `(21,)` (or the count of new lbl_alloc_* labels).

- [ ] **Step 7: Commit**

```bash
git add scripts/init_db.py templates/index.html static/css/dpmtf-theme.css
git commit -m "[V4] WebUI: allocator dashboard i18n labels, panel-group, grid CSS"
```

---

### Task 5: `allocator.js` — config load, lists, profiles, selection

**Files:**
- Create: `static/js/allocator.js`
- Modify: `static/js/dpmtf-app.js` (call `initAllocator` after labels load)

**Interfaces:**
- Consumes globals from `dpmtf-app.js`: `el(tag, className, text)`, `clear(el)`, `lbl(key, fallback)`, `labelMap`.
- Consumes endpoint: `GET /api/bridge-v2/allocator/config`.
- Produces globals (used by Tasks 6 & 7): `window.allocatorState = {config, selected}`, `window.initAllocator()`, `renderAllocatorDashboard()`, `selectAllocatorItem(type, name)`, `reloadAllocatorConfig()`. `config` = `{aliases, roles, profiles}`; `selected` = `{type: "alias"|"role"|null, name: string|null}`.
- Produces DOM containers with ids: `allocator-aliases-list`, `allocator-roles-list`, `allocator-detail`, `allocator-profiles`.

- [ ] **Step 1: Add the init hook in `dpmtf-app.js`**

In `static/js/dpmtf-app.js`, make `loadLabels()` return its top-level `fetch(...)` promise chain (add `return` before the outermost `fetch(`). Then in `onReady()`, replace the line `loadLabels();` with:

```javascript
  loadLabels().then(function () {
    if (window.initAllocator) window.initAllocator();
  });
```

- [ ] **Step 2: Write `allocator.js` (scaffold + lists + profiles)**

Create `static/js/allocator.js`:

```javascript
/* Model Allocator config dashboard (V4). Depends on el/clear/lbl from dpmtf-app.js. */
"use strict";

window.allocatorState = { config: { aliases: {}, roles: {}, profiles: {} }, selected: { type: null, name: null } };

function reloadAllocatorConfig() {
  return fetch("/api/bridge-v2/allocator/config")
    .then(function (res) { if (!res.ok) throw new Error("HTTP " + res.status); return res.json(); })
    .then(function (cfg) {
      window.allocatorState.config = {
        aliases: cfg.aliases || {},
        roles: cfg.roles || {},
        profiles: cfg.profiles || {}
      };
      renderAllocatorDashboard();
    })
    .catch(function (err) {
      const mount = document.getElementById("allocator-dashboard");
      if (mount) { clear(mount); mount.appendChild(el("div", "dpmtf-text-danger", "Allocator: " + err.message)); }
    });
}

function _allocatorListColumn(titleKey, titleFallback, newKey, newFallback, listId, onNew) {
  const col = el("div", "allocator-col");
  col.appendChild(el("h4", null, lbl(titleKey, titleFallback)));
  const list = el("div", null);
  list.id = listId;
  col.appendChild(list);
  const newBtn = el("button", "dpmtf-btn", lbl(newKey, newFallback));
  newBtn.style.marginTop = "8px";
  newBtn.onclick = onNew;
  col.appendChild(newBtn);
  return col;
}

function _renderList(listId, names, type) {
  const list = document.getElementById(listId);
  if (!list) return;
  clear(list);
  const sel = window.allocatorState.selected;
  names.sort().forEach(function (name) {
    const item = el("div", "allocator-list-item", name);
    if (sel.type === type && sel.name === name) item.className += " selected";
    item.onclick = function () { selectAllocatorItem(type, name); };
    list.appendChild(item);
  });
}

function _renderProfiles() {
  const box = document.getElementById("allocator-profiles");
  if (!box) return;
  clear(box);
  box.appendChild(el("div", "dpmtf-muted", lbl("lbl_alloc_profiles", "Runtime profiles (read-only)")));
  const profiles = window.allocatorState.config.profiles;
  Object.keys(profiles).sort().forEach(function (pname) {
    const backend = (profiles[pname] && profiles[pname].backend) || "?";
    box.appendChild(el("div", null, pname + " — " + backend));
  });
}

function renderAllocatorDashboard() {
  const mount = document.getElementById("allocator-dashboard");
  if (!mount) return;
  clear(mount);

  const grid = el("div", "allocator-grid");
  grid.appendChild(_allocatorListColumn("lbl_alloc_aliases", "Aliases", "lbl_alloc_new_alias", "+ New alias",
    "allocator-aliases-list", function () { selectAllocatorItem("alias", null); }));
  grid.appendChild(_allocatorListColumn("lbl_alloc_roles", "Roles", "lbl_alloc_new_role", "+ New role",
    "allocator-roles-list", function () { selectAllocatorItem("role", null); }));

  const detailCol = el("div", "allocator-col");
  detailCol.appendChild(el("h4", null, lbl("lbl_alloc_detail", "Detail")));
  const detail = el("div", null);
  detail.id = "allocator-detail";
  detailCol.appendChild(detail);
  grid.appendChild(detailCol);

  mount.appendChild(grid);

  const profiles = el("div", "allocator-profiles");
  profiles.id = "allocator-profiles";
  mount.appendChild(profiles);

  _renderList("allocator-aliases-list", Object.keys(window.allocatorState.config.aliases), "alias");
  _renderList("allocator-roles-list", Object.keys(window.allocatorState.config.roles), "role");
  _renderProfiles();
  renderAllocatorDetail();
}

function selectAllocatorItem(type, name) {
  window.allocatorState.selected = { type: type, name: name };
  _renderList("allocator-aliases-list", Object.keys(window.allocatorState.config.aliases), "alias");
  _renderList("allocator-roles-list", Object.keys(window.allocatorState.config.roles), "role");
  renderAllocatorDetail();
}

/* renderAllocatorDetail is completed in Task 6 (alias) and Task 7 (role). */
function renderAllocatorDetail() {
  const detail = document.getElementById("allocator-detail");
  if (!detail) return;
  clear(detail);
  detail.appendChild(el("div", "dpmtf-muted", lbl("lbl_alloc_select_hint", "Select an alias or role to edit")));
}

function initAllocator() {
  if (!document.getElementById("allocator-dashboard")) return;
  reloadAllocatorConfig();
}
window.initAllocator = initAllocator;
```

- [ ] **Step 3: Syntax check**

Run: `node --check static/js/allocator.js && node --check static/js/dpmtf-app.js`
Expected: no output (exit 0).

- [ ] **Step 4: Manual verify in browser**

Start the server: `uvicorn app:app --host 0.0.0.0 --port 9130 --reload` (if not already running).
Open `http://localhost:9130`, expand the "🧩 Model Allocator" group.
Expected: three columns (Aliases / Roles / Detail), the aliases + roles lists populated from live config, a read-only runtime-profiles list at the bottom, and clicking an item highlights it and shows the "Select an alias or role to edit" hint (detail forms come in Tasks 6-7).

- [ ] **Step 5: Commit**

```bash
git add static/js/allocator.js static/js/dpmtf-app.js
git commit -m "[V4] WebUI: allocator dashboard scaffold — config load, lists, profiles, selection"
```

---

### Task 6: `allocator.js` — alias detail form + runtime status

**Files:**
- Modify: `static/js/allocator.js` (replace `renderAllocatorDetail` with alias-aware version + helpers)

**Interfaces:**
- Consumes: `window.allocatorState`, `reloadAllocatorConfig()`, `selectAllocatorItem()` (Task 5); endpoints `POST/DELETE /api/bridge-v2/allocator/config/alias`, `POST /api/bridge-v2/allocator/{validate,status,start,stop}`.
- Produces: `renderAliasForm(name)`, `renderAllocatorStatus(container, alias, client)`.

- [ ] **Step 1: Replace `renderAllocatorDetail` and add the alias form**

In `static/js/allocator.js`, replace the entire `function renderAllocatorDetail() { ... }` placeholder from Task 5 with:

```javascript
function _field(parent, labelKey, labelFallback, inputEl) {
  const row = el("div", null);
  row.style.marginTop = "8px";
  const lab = el("label", "dpmtf-small dpmtf-muted", lbl(labelKey, labelFallback));
  lab.style.display = "block";
  row.appendChild(lab);
  row.appendChild(inputEl);
  parent.appendChild(row);
  return inputEl;
}

function _textInput(value) {
  const i = el("input");
  i.type = "text";
  i.className = "dpmtf-input";
  if (value !== undefined && value !== null) i.value = String(value);
  return i;
}

function _profileSelect(value) {
  const s = el("select");
  s.className = "dpmtf-input";
  Object.keys(window.allocatorState.config.profiles).sort().forEach(function (p) {
    const o = el("option", null, p);
    o.value = p;
    if (p === value) o.selected = true;
    s.appendChild(o);
  });
  return s;
}

function _checkbox(checked) {
  const c = el("input");
  c.type = "checkbox";
  c.checked = !!checked;
  return c;
}

function renderAliasForm(name) {
  const detail = document.getElementById("allocator-detail");
  clear(detail);
  const existing = name ? (window.allocatorState.config.aliases[name] || {}) : {};

  const nameInput = _textInput(name || "");
  nameInput.disabled = !!name; // renaming = delete+create; keep key stable while editing
  _field(detail, "lbl_alloc_field_name", "Name", nameInput);

  const profileSel = _profileSelect(existing.runtime_profile);
  _field(detail, "lbl_alloc_field_profile", "Runtime profile", profileSel);

  const modelInput = _textInput(existing.real_model || "");
  _field(detail, "lbl_alloc_field_model", "Real model", modelInput);

  const modelPathInput = _textInput(existing.model_path || "");
  _field(detail, "lbl_alloc_field_model_path", "Model path", modelPathInput);

  const contextInput = _textInput(existing.context !== undefined ? existing.context : "");
  _field(detail, "lbl_alloc_field_context", "Context", contextInput);

  const lifecycleInput = _textInput(existing.lifecycle_policy || "");
  _field(detail, "lbl_alloc_field_lifecycle", "Lifecycle policy", lifecycleInput);

  const clientsWrap = el("div", null);
  const clients = existing.clients || {};
  const ocCb = _checkbox(clients.opencode);
  const ccCb = _checkbox(clients["claude-code"]);
  clientsWrap.appendChild(ocCb); clientsWrap.appendChild(el("span", null, " opencode  "));
  clientsWrap.appendChild(ccCb); clientsWrap.appendChild(el("span", null, " claude-code"));
  _field(detail, "lbl_alloc_field_clients", "Clients", clientsWrap);

  const msg = el("div", "dpmtf-small");
  msg.style.marginTop = "8px";

  const saveBtn = el("button", "dpmtf-btn", lbl("lbl_alloc_save", "Save"));
  saveBtn.onclick = function () {
    const key = (name || nameInput.value).trim();
    if (!key) { msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = "name required"; return; }
    const definition = {};
    if (profileSel.value) definition.runtime_profile = profileSel.value;
    if (modelInput.value.trim()) definition.real_model = modelInput.value.trim();
    if (modelPathInput.value.trim()) definition.model_path = modelPathInput.value.trim();
    if (contextInput.value.trim()) {
      const n = parseInt(contextInput.value.trim(), 10);
      definition.context = isNaN(n) ? contextInput.value.trim() : n;
    }
    if (lifecycleInput.value.trim()) definition.lifecycle_policy = lifecycleInput.value.trim();
    definition.clients = { opencode: ocCb.checked, "claude-code": ccCb.checked };
    saveBtn.disabled = true;
    fetch("/api/bridge-v2/allocator/config/alias", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: key, definition: definition })
    })
      .then(function (res) { return res.json().then(function (b) { return { ok: res.ok, body: b }; }); })
      .then(function (r) {
        saveBtn.disabled = false;
        if (!r.ok) { msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = r.body.detail || "error"; return; }
        reloadAllocatorConfig().then(function () { selectAllocatorItem("alias", key); });
      })
      .catch(function (e) { saveBtn.disabled = false; msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = e.message; });
  };
  detail.appendChild(saveBtn);

  if (name) {
    const delBtn = el("button", "dpmtf-btn", lbl("lbl_alloc_delete", "Delete"));
    delBtn.style.marginLeft = "8px";
    delBtn.onclick = function () {
      if (!confirm(lbl("lbl_alloc_confirm_delete", "Delete '{name}'?").replace("{name}", name))) return;
      fetch("/api/bridge-v2/allocator/config/alias/" + encodeURIComponent(name), { method: "DELETE" })
        .then(function (res) { return res.json().then(function (b) { return { ok: res.ok, body: b }; }); })
        .then(function (r) {
          if (!r.ok) { msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = r.body.detail || "error"; return; }
          selectAllocatorItem(null, null);
          reloadAllocatorConfig();
        });
    };
    detail.appendChild(delBtn);
  }
  detail.appendChild(msg);

  if (name) {
    const statusBox = el("div", "dpmtf-card");
    statusBox.style.marginTop = "12px";
    detail.appendChild(statusBox);
    const client = (existing.clients && existing.clients.opencode) ? "opencode" : "claude-code";
    renderAllocatorStatus(statusBox, name, client);
  }
}

function renderAllocatorStatus(container, alias, client) {
  clear(container);
  container.appendChild(el("h5", null, lbl("lbl_bridge_runtime_status", "Runtime Status")));
  const info = el("div", "dpmtf-small");
  container.appendChild(info);

  function setInfo(text, cls) { clear(info); info.appendChild(el("span", cls || null, text)); }

  const btns = el("div", null);
  btns.style.marginTop = "8px";
  const valBtn = el("button", "dpmtf-btn", lbl("lbl_bridge_validate_allocator", "Validate"));
  const startBtn = el("button", "dpmtf-btn", lbl("lbl_bridge_start", "Start"));
  const stopBtn = el("button", "dpmtf-btn", lbl("lbl_bridge_stop", "Stop"));
  startBtn.style.marginLeft = "6px"; stopBtn.style.marginLeft = "6px";
  btns.appendChild(valBtn); btns.appendChild(startBtn); btns.appendChild(stopBtn);
  container.appendChild(btns);

  function post(path) {
    return fetch(path, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ alias: alias, client: client })
    }).then(function (res) { if (!res.ok) throw new Error("HTTP " + res.status); return res.json(); });
  }

  valBtn.onclick = function () {
    setInfo("…");
    post("/api/bridge-v2/allocator/validate")
      .then(function (r) { setInfo(lbl("lbl_bridge_validation_status", "Validation") + ": " + (r.validation_status || "?"),
        r.validation_status === "OK" ? "dpmtf-text-success" : "dpmtf-text-warning"); })
      .catch(function (e) { setInfo(e.message, "dpmtf-text-danger"); });
  };
  startBtn.onclick = function () { setInfo("…"); post("/api/bridge-v2/allocator/start").then(function () { refresh(); }).catch(function (e) { setInfo(e.message, "dpmtf-text-danger"); }); };
  stopBtn.onclick = function () {
    if (!confirm(lbl("lbl_bridge_confirm_stop", "Stop the allocator runtime for '{alias}'?").replace("{alias}", alias))) return;
    setInfo("…"); post("/api/bridge-v2/allocator/stop").then(function () { refresh(); }).catch(function (e) { setInfo(e.message, "dpmtf-text-danger"); });
  };

  function refresh() {
    post("/api/bridge-v2/allocator/status")
      .then(function (d) {
        const running = d && d.running;
        setInfo((running ? lbl("lbl_bridge_running", "Running") : lbl("lbl_bridge_not_running", "Not running")) +
          (d && d.pid ? "  pid " + d.pid : "") + (d && d.port ? "  :" + d.port : ""),
          running ? "dpmtf-text-success" : "dpmtf-text-muted");
      })
      .catch(function (e) { setInfo(e.message, "dpmtf-text-danger"); });
  }
  refresh();
}
```

- [ ] **Step 2: Route alias selection to the form**

In `selectAllocatorItem` (from Task 5), the call already ends with `renderAllocatorDetail()`. Update `renderAllocatorDetail` to dispatch by type — replace its body with:

```javascript
function renderAllocatorDetail() {
  const detail = document.getElementById("allocator-detail");
  if (!detail) return;
  const sel = window.allocatorState.selected;
  if (sel.type === "alias") { renderAliasForm(sel.name); return; }
  clear(detail);
  detail.appendChild(el("div", "dpmtf-muted", lbl("lbl_alloc_select_hint", "Select an alias or role to edit")));
}
```

- [ ] **Step 3: Syntax check**

Run: `node --check static/js/allocator.js`
Expected: no output.

- [ ] **Step 4: Manual verify**

Reload `http://localhost:9130`, expand Model Allocator. Click an alias → the alias form appears pre-filled; click "+ New alias" → empty form with editable name. Create a test alias (pick a profile, set a real model, tick opencode), Save → it appears in the list. Click Validate/Start/Stop and confirm the status line updates. Delete the test alias → it disappears. Try deleting an alias referenced by a role → the error banner shows the server's refusal message.

- [ ] **Step 5: Commit**

```bash
git add static/js/allocator.js
git commit -m "[V4] WebUI: allocator alias detail form + runtime status controls"
```

---

### Task 7: `allocator.js` — role detail form

**Files:**
- Modify: `static/js/allocator.js` (add `renderRoleForm`, dispatch role type in `renderAllocatorDetail`)

**Interfaces:**
- Consumes: `window.allocatorState`, `_field`, `_textInput` (Task 6), `reloadAllocatorConfig`, `selectAllocatorItem`; endpoints `POST/DELETE /api/bridge-v2/allocator/config/role`.
- Produces: `renderRoleForm(name)`, and an `_aliasSelect(value, includeBlank)` helper.

- [ ] **Step 1: Add `_aliasSelect` and `renderRoleForm`**

Append to `static/js/allocator.js`:

```javascript
function _aliasSelect(value, includeBlank) {
  const s = el("select");
  s.className = "dpmtf-input";
  if (includeBlank) { const o = el("option", null, "—"); o.value = ""; s.appendChild(o); }
  Object.keys(window.allocatorState.config.aliases).sort().forEach(function (a) {
    const o = el("option", null, a);
    o.value = a;
    if (a === value) o.selected = true;
    s.appendChild(o);
  });
  return s;
}

function renderRoleForm(name) {
  const detail = document.getElementById("allocator-detail");
  clear(detail);
  const existing = name ? (window.allocatorState.config.roles[name] || {}) : {};
  const ca = existing.client_aliases || {};

  const nameInput = _textInput(name || "");
  nameInput.disabled = !!name;
  _field(detail, "lbl_alloc_field_name", "Name", nameInput);

  const configDirInput = _textInput(existing.config_dir || "");
  _field(detail, "lbl_alloc_field_config_dir", "Config dir", configDirInput);

  const defaultAliasSel = _aliasSelect(existing.default_alias, true);
  _field(detail, "lbl_alloc_field_default_alias", "Default alias", defaultAliasSel);

  const ocSel = _aliasSelect(ca.opencode, true);
  _field(detail, "lbl_alloc_field_client_aliases", "Client aliases (opencode)", ocSel);
  const ccSel = _aliasSelect(ca["claude-code"], true);
  _field(detail, "lbl_alloc_field_client_aliases", "Client aliases (claude-code)", ccSel);

  const msg = el("div", "dpmtf-small");
  msg.style.marginTop = "8px";

  const saveBtn = el("button", "dpmtf-btn", lbl("lbl_alloc_save", "Save"));
  saveBtn.onclick = function () {
    const key = (name || nameInput.value).trim();
    if (!key) { msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = "name required"; return; }
    const definition = {};
    if (defaultAliasSel.value) definition.default_alias = defaultAliasSel.value;
    if (configDirInput.value.trim()) definition.config_dir = configDirInput.value.trim();
    const clientAliases = {};
    if (ocSel.value) clientAliases.opencode = ocSel.value;
    if (ccSel.value) clientAliases["claude-code"] = ccSel.value;
    if (Object.keys(clientAliases).length) definition.client_aliases = clientAliases;
    saveBtn.disabled = true;
    fetch("/api/bridge-v2/allocator/config/role", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: key, definition: definition })
    })
      .then(function (res) { return res.json().then(function (b) { return { ok: res.ok, body: b }; }); })
      .then(function (r) {
        saveBtn.disabled = false;
        if (!r.ok) { msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = r.body.detail || "error"; return; }
        reloadAllocatorConfig().then(function () { selectAllocatorItem("role", key); });
      })
      .catch(function (e) { saveBtn.disabled = false; msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = e.message; });
  };
  detail.appendChild(saveBtn);

  if (name) {
    const delBtn = el("button", "dpmtf-btn", lbl("lbl_alloc_delete", "Delete"));
    delBtn.style.marginLeft = "8px";
    delBtn.onclick = function () {
      if (!confirm(lbl("lbl_alloc_confirm_delete", "Delete '{name}'?").replace("{name}", name))) return;
      fetch("/api/bridge-v2/allocator/config/role/" + encodeURIComponent(name), { method: "DELETE" })
        .then(function (res) { return res.json().then(function (b) { return { ok: res.ok, body: b }; }); })
        .then(function (r) {
          if (!r.ok) { msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = r.body.detail || "error"; return; }
          selectAllocatorItem(null, null);
          reloadAllocatorConfig();
        });
    };
    detail.appendChild(delBtn);
  }
  detail.appendChild(msg);
}
```

- [ ] **Step 2: Dispatch role type in `renderAllocatorDetail`**

Update `renderAllocatorDetail` so it handles the role branch — replace its body with:

```javascript
function renderAllocatorDetail() {
  const detail = document.getElementById("allocator-detail");
  if (!detail) return;
  const sel = window.allocatorState.selected;
  if (sel.type === "alias") { renderAliasForm(sel.name); return; }
  if (sel.type === "role") { renderRoleForm(sel.name); return; }
  clear(detail);
  detail.appendChild(el("div", "dpmtf-muted", lbl("lbl_alloc_select_hint", "Select an alias or role to edit")));
}
```

- [ ] **Step 3: Syntax check**

Run: `node --check static/js/allocator.js`
Expected: no output.

- [ ] **Step 4: Manual verify**

Reload the page. Click a role → role form pre-filled (config dir, default alias, client-alias dropdowns). Create a new role referencing an existing alias, Save → appears in list. Try saving a role whose default alias is blank-then-set to a non-existent value — not possible via dropdown (dropdowns only list real aliases), confirming the dangling-reference guard is enforced at the UI too. Delete the test role.

- [ ] **Step 5: Final validation checklist (CLAUDE.md §6)**

Run each and confirm:
```bash
python3 -m py_compile app.py routers/bridge.py
node --check static/js/allocator.js static/js/dpmtf-app.js
grep -RIn "innerHTML" static/ templates/          # must be empty
grep -n '"/home/svend' routers/bridge.py static/js/allocator.js   # must be empty
python3 -m pytest tests/test_allocator_config_endpoints.py tests/test_bridge_endpoints.py -q
git diff --stat                                    # only expected files
git diff requirements.txt                           # no new deps
```
Expected: all green, greps empty, diff scoped.

- [ ] **Step 6: Commit**

```bash
git add static/js/allocator.js
git commit -m "[V4] WebUI: allocator role detail form"
```

---

## Self-Review notes

- **Spec coverage:** §4 CLI write layer → Tasks 1-2. §5 endpoints → Task 3. §6 frontend (alias form, role form, profiles read-only, runtime status reuse) → Tasks 5-7. §7 error handling → `_run_allocator` (400/502) + inline `msg` banners + confirm dialogs. §8 testing → pytest in Tasks 1-3, manual walkthroughs + §6 checklist. §9 phasing/git → phase split + per-task commits; init_db.py flagged approval-required.
- **Raw-load rule:** enforced by `config_writer.load_raw` (never calls `config_loader.load_config`); test `test_load_raw_does_not_resolve_env` guards it.
- **Type consistency:** `load_raw` → `{aliases, roles, profiles}` used identically in CLI `config show`, endpoint `GET /allocator/config`, and JS `allocatorState.config`. Form field names (`runtime_profile`, `real_model`, `model_path`, `context`, `lifecycle_policy`, `clients`, `config_dir`, `default_alias`, `client_aliases`) match the YAML shapes in models.yaml/roles.yaml.
- **Deferred (out of scope per spec §2):** editing runtime_profiles.yaml; standalone allocator HTTP service.
