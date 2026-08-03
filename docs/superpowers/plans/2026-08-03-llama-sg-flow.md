# llama_SG Flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SGLang runtime to model-allocator, configure Laguna (llama.cpp) alias, create the `llama_SG` autonomous flow with 3 roles, governance templates, and cold-start skill.

**Architecture:** New `adapters/sglang.py` follows the `llama_cpp.py` server-management pattern (start/stop/status via PID file + /health polling). The opencode adapter is extended to handle `backend: sglang` identically to `llama_cpp` (both expose OpenAI-compatible /v1 endpoints). Model switching between Laguna and SGLang is handled by `pre_dispatch_script`/`post_dispatch_script` on flow steps.

**Tech Stack:** Python 3.12 stdlib, pyyaml, unittest (model-allocator tests), SQLite (Father DB migrations)

## Global Constraints

- `python3 -m py_compile <file>` MUST pass on every touched Python file
- All existing model-allocator tests stay green (currently 122, 1 pre-existing failure)
- Single runtime dependency stays `pyyaml` — NO new dependencies
- TDD: write failing test → implement → green
- Backwards compatibility: existing CLI output formats consumed by Father keep working
- Git policy: Human approves commits; tasks end with `git add <files>` and STOP
- en-US for all code, comments, commit messages
- No hardcoded `/home/svend` paths — use config or env vars

---

### Task 1: SGLang Adapter

**Files:**
- Create: `/home/svend/model-allocator/src/model_allocator/adapters/sglang.py`
- Create: `/home/svend/model-allocator/tests/test_sglang.py`

**Interfaces:**
- Produces: `SGLangAdapter(resolved: dict, state_dir: str | None)` class with `start(timeout) -> dict`, `stop(timeout) -> dict`, `status(use_pid) -> dict`, `unload() -> dict`

The SGLang adapter manages an `sglang.launch_server` process. It follows the exact same pattern as `LlamaCppAdapter` (PID file, /health polling, SIGTERM→SIGKILL stop). The server exposes an OpenAI-compatible API at `http://{host}:{port}/v1`.

- [ ] **Step 1: Write the adapter**

```python
"""SGLang server backend adapter for model-allocator."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any


class SGLangAdapterError(Exception):
    pass


class SGLangAdapter:
    def __init__(self, resolved: dict, state_dir: str | None = None):
        self.resolved = resolved
        self.alias = resolved.get("alias", "sglang")
        self.port = self._resolve_port()
        self.host = resolved.get("host", resolved.get("default_host", "127.0.0.1"))
        self.state_dir = state_dir or self._default_state_dir()
        self.pid_file = os.path.join(
            self.state_dir, f"model-allocator-{self.alias}-{self.port}.pid"
        )

    @staticmethod
    def _default_state_dir() -> str:
        return os.environ.get("MODEL_ALLOCATOR_STATE_DIR", tempfile.gettempdir())

    def _resolve_port(self) -> int:
        configured = self.resolved.get("port")
        if configured is None:
            configured = self.resolved.get("default_port")
        if configured is None:
            return self._find_free_port()
        return int(configured)

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _python_bin(self) -> str:
        venv = self.resolved.get("venv", "")
        if venv:
            python = os.path.join(venv, "bin", "python")
            if not (os.path.isfile(python) and os.access(python, os.X_OK)):
                raise SGLangAdapterError(f"Python not found in venv: {python}")
            return python
        return "python3"

    def _build_argv(self) -> list[str]:
        model_path = self.resolved.get("model_path", "")
        if not model_path:
            raise SGLangAdapterError("No model_path configured for SGLang alias")

        served_name = self.resolved.get("served_model_name", "qwen-shared")
        context = self.resolved.get("context", 32768)
        mem_frac = self.resolved.get("mem_fraction_static", 0.82)
        max_requests = self.resolved.get("max_running_requests", 2)
        tool_parser = self.resolved.get("tool_call_parser", "qwen")

        argv = [
            self._python_bin(), "-m", "sglang.launch_server",
            "--model-path", model_path,
            "--served-model-name", served_name,
            "--host", self.host,
            "--port", str(self.port),
            "--context-length", str(context),
            "--mem-fraction-static", str(mem_frac),
            "--max-running-requests", str(max_requests),
            "--tool-call-parser", tool_parser,
        ]

        if self.resolved.get("enable_cache_report"):
            argv.append("--enable-cache-report")

        return argv

    def start(self, timeout: int = 120) -> dict:
        try:
            argv = self._build_argv()
        except SGLangAdapterError as exc:
            return {"started": False, "error": str(exc)}

        os.makedirs(self.state_dir, exist_ok=True)
        try:
            process = subprocess.Popen(
                argv,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as exc:
            return {"started": False, "error": f"Failed to start sglang server: {exc}"}

        Path(self.pid_file).write_text(str(process.pid), encoding="utf-8")

        start_ts = time.time()
        while time.time() - start_ts < timeout:
            if process.poll() is not None:
                return {"started": False, "error": "sglang server exited early"}
            status = self.status(use_pid=process.pid)
            if status["running"]:
                return {
                    "started": True, "error": None,
                    "pid": process.pid, "port": self.port,
                }
            time.sleep(0.5)

        self._kill_pid(process.pid, timeout=10)
        return {
            "started": False,
            "error": f"sglang server health endpoint did not become ready within {timeout}s",
        }

    def status(self, use_pid: int | None = None) -> dict:
        pid = use_pid
        if pid is None:
            try:
                pid = int(Path(self.pid_file).read_text(encoding="utf-8").strip())
            except (FileNotFoundError, ValueError):
                return {"running": False, "error": "No PID file", "pid": None}

        try:
            os.kill(pid, 0)
            alive = True
        except (OSError, ProcessLookupError):
            alive = False

        health_url = f"http://{self.host}:{self.port}/health"
        try:
            urllib.request.urlopen(health_url, timeout=2)
            healthy = True
            health_error = None
        except Exception as exc:
            healthy = False
            health_error = str(exc)

        running = alive and healthy
        return {
            "running": running,
            "alive": alive,
            "healthy": healthy,
            "pid": pid,
            "port": self.port,
            "error": health_error,
        }

    @staticmethod
    def _kill_pid(pid: int, timeout: int = 30) -> dict:
        try:
            os.kill(pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            return {"stopped": True, "error": None}

        start_ts = time.time()
        while time.time() - start_ts < timeout:
            try:
                os.kill(pid, 0)
            except (OSError, ProcessLookupError):
                return {"stopped": True, "error": None}
            time.sleep(0.2)

        try:
            os.kill(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
        return {"stopped": True, "error": None}

    def stop(self, timeout: int = 30) -> dict:
        try:
            pid = int(Path(self.pid_file).read_text(encoding="utf-8").strip())
        except (FileNotFoundError, ValueError):
            return {"stopped": True, "error": None}

        result = self._kill_pid(pid, timeout=timeout)
        try:
            os.unlink(self.pid_file)
        except OSError:
            pass
        return result

    def unload(self) -> dict:
        return self.stop()
```

- [ ] **Step 2: Compile check**

```bash
cd /home/svend/model-allocator && python3 -m py_compile src/model_allocator/adapters/sglang.py
```

- [ ] **Step 3: Write tests**

```python
"""Tests for SGLang adapter."""
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from model_allocator.adapters import sglang as sglang_adapter


class TestSGLangAdapter(unittest.TestCase):
    def setUp(self):
        self.resolved = {
            "alias": "qwen-shared-sglang",
            "model_path": "/home/svend/models/sglang/Qwen3-Coder-30B-A3B-Instruct-AWQ",
            "served_model_name": "qwen-shared",
            "context": 32768,
            "port": 30000,
            "host": "127.0.0.1",
            "venv": "/home/svend/venvs/sglang",
        }
        self.state_dir = tempfile.mkdtemp()

    def test_argv_assembly(self):
        adapter = sglang_adapter.SGLangAdapter(self.resolved, state_dir=self.state_dir)
        argv = adapter._build_argv()
        self.assertIn("sglang.launch_server", argv[2])
        self.assertIn("--model-path", argv)
        self.assertIn("--served-model-name", argv)
        self.assertIn("qwen-shared", argv)
        self.assertIn("--port", argv)
        self.assertIn("30000", argv)
        self.assertIn("--context-length", argv)
        self.assertIn("32768", argv)
        self.assertIn("--tool-call-parser", argv)

    def test_argv_uses_defaults_when_fields_absent(self):
        minimal = {"model_path": "/tmp/model"}
        adapter = sglang_adapter.SGLangAdapter(minimal, state_dir=self.state_dir)
        argv = adapter._build_argv()
        self.assertIn("--served-model-name", argv)
        self.assertIn("qwen-shared", argv)  # default
        self.assertIn("--context-length", argv)
        self.assertIn("32768", argv)  # default

    def test_missing_model_path_raises(self):
        with self.assertRaises(sglang_adapter.SGLangAdapterError):
            sglang_adapter.SGLangAdapter({}, state_dir=self.state_dir)._build_argv()

    def test_finds_free_port_when_not_configured(self):
        minimal = {"model_path": "/tmp/model"}
        adapter = sglang_adapter.SGLangAdapter(minimal, state_dir=self.state_dir)
        port = adapter.port
        self.assertGreater(port, 0)
        self.assertNotEqual(port, 30000)  # not the default when free-port is used

    def test_stop_removes_pid_file(self):
        adapter = sglang_adapter.SGLangAdapter(self.resolved, state_dir=self.state_dir)
        Path(adapter.pid_file).write_text("99999", encoding="utf-8")
        with patch.object(sglang_adapter.SGLangAdapter, "_kill_pid", return_value={"stopped": True, "error": None}):
            result = adapter.stop()
        self.assertTrue(result["stopped"])
        self.assertFalse(os.path.exists(adapter.pid_file))

    def test_stop_no_pid_file_is_noop(self):
        adapter = sglang_adapter.SGLangAdapter(self.resolved, state_dir=self.state_dir)
        result = adapter.stop()
        self.assertTrue(result["stopped"])

    def test_status_no_pid_file(self):
        adapter = sglang_adapter.SGLangAdapter(self.resolved, state_dir=self.state_dir)
        status = adapter.status()
        self.assertFalse(status["running"])
        self.assertIsNone(status["pid"])

    def test_unload_calls_stop(self):
        adapter = sglang_adapter.SGLangAdapter(self.resolved, state_dir=self.state_dir)
        result = adapter.unload()
        self.assertTrue(result["stopped"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run tests**

```bash
cd /home/svend/model-allocator && PYTHONPATH=src python3 -m unittest tests.test_sglang -v
```

Expected: 8 tests pass.

- [ ] **Step 5: Stage files**

```bash
cd /home/svend/model-allocator && git add src/model_allocator/adapters/sglang.py tests/test_sglang.py
```

---

### Task 2: Schema Update for SGLang

**Files:**
- Modify: `/home/svend/model-allocator/src/model_allocator/schema.py`

**Interfaces:**
- Consumes: none new
- Produces: `SGLANG_ALIAS_FIELDS` dict, updated `BACKENDS` tuple, updated `PROFILE_FIELDS`

- [ ] **Step 1: Add SGLang to BACKENDS and add field definitions**

In `schema.py`, change line 33:
```python
BACKENDS = ("ollama", "llama_cpp", "openai_compatible", "onyx", "anthropic", "sglang")
```

After `LLAMACPP_ALIAS_FIELDS` (after line 75), add:

```python
SGLANG_ALIAS_FIELDS: dict[str, object] = {
    "model_path": str,
    "served_model_name": str,
    "port": int,
    "host": str,
    "venv": str,
    "context": int,
    "mem_fraction_static": (int, float),
    "max_running_requests": int,
    "tool_call_parser": str,
    "enable_cache_report": bool,
    "max_output_tokens": int,
}
```

In `PROFILE_FIELDS` (after line 98), add:
```python
    "venv": str,
    "default_host": str,
```

- [ ] **Step 2: Wire SGLang alias fields into validate_alias**

In `validate_alias()` in schema.py, find the backend-specific field dispatch (around line 170). Add after the llama_cpp block:

```python
    elif backend == "sglang":
        alias_fields = {**COMMON_ALIAS_FIELDS, **SGLANG_ALIAS_FIELDS}
```

- [ ] **Step 3: Compile check**

```bash
cd /home/svend/model-allocator && python3 -m py_compile src/model_allocator/schema.py
```

- [ ] **Step 4: Run existing tests to verify no regression**

```bash
cd /home/svend/model-allocator && PYTHONPATH=src python3 -m unittest discover tests -v 2>&1 | grep -E '^(test_|OK|FAIL|Ran |ERROR)'
```

- [ ] **Step 5: Stage**

```bash
cd /home/svend/model-allocator && git add src/model_allocator/schema.py
```

---

### Task 3: Wire SGLang into CLI

**Files:**
- Modify: `/home/svend/model-allocator/src/model_allocator/cli.py`

**Interfaces:**
- Consumes: `SGLangAdapter` from `adapters.sglang`
- Produces: `_get_backend_adapter` handles `backend == "sglang"`, `cmd_start`/`cmd_stop`/`cmd_status` dispatch to SGLangAdapter

- [ ] **Step 1: Add import**

In `cli.py`, after line 17 (`from model_allocator.adapters import llama_cpp as llama_cpp_adapter`), add:

```python
from model_allocator.adapters import sglang as sglang_adapter
```

- [ ] **Step 2: Add SGLang to `_get_backend_adapter`**

In `_get_backend_adapter()` (line 44), after the `llama_cpp` block (after line 59), add:

```python
    if backend == "sglang":
        return sglang_adapter.SGLangAdapter(resolved)
```

- [ ] **Step 3: Add SGLang to `cmd_status`**

In `cmd_status()` (line 135), after the `llama_cpp` block (after line 161), add:

```python
    elif backend == "sglang":
        report.update(adapter.status())
```

And update the warning check on line 168 from `backend in ("openai_compatible", "llama_cpp")` to:

```python
    if backend in ("openai_compatible", "llama_cpp", "sglang") and not report.get("running", False):
```

- [ ] **Step 4: Add SGLang to `cmd_start`**

In `cmd_start()` (line 249), after the `llama_cpp` block (after line 269), add:

```python
    elif backend == "sglang":
        result = adapter.start(timeout=args.timeout)
```

- [ ] **Step 5: Add SGLang to `cmd_stop`**

In `cmd_stop()` (line 282), find the backend dispatch (around line 297). After the `llama_cpp` block, add:

```python
    elif backend == "sglang":
        result = adapter.stop(timeout=args.timeout)
```

- [ ] **Step 6: Compile check**

```bash
cd /home/svend/model-allocator && python3 -m py_compile src/model_allocator/cli.py
```

- [ ] **Step 7: Run CLI tests**

```bash
cd /home/svend/model-allocator && PYTHONPATH=src python3 -m unittest tests.test_v2.TestCliV2 -v 2>&1 | tail -5
```

- [ ] **Step 8: Stage**

```bash
cd /home/svend/model-allocator && git add src/model_allocator/cli.py
```

---

### Task 4: Wire SGLang into Validator

**Files:**
- Modify: `/home/svend/model-allocator/src/model_allocator/validator.py`

- [ ] **Step 1: Add import**

In `validator.py`, after line 13 (`from model_allocator.adapters import openai_compatible as openai_adapter`), add:

```python
from model_allocator.adapters import sglang as sglang_adapter
```

- [ ] **Step 2: Add SGLang validation**

In the `validate()` method, find the backend-specific validation blocks. After the `llama_cpp` validation block, add:

```python
        elif backend == "sglang":
            model_path = resolved.get("model_path", "")
            if not model_path:
                result["warnings"].append("model_path not configured for SGLang alias")
            venv = resolved.get("venv", "")
            if venv and not os.path.isdir(venv):
                result["warnings"].append(f"SGLang venv not found: {venv}")
```

- [ ] **Step 3: Compile check**

```bash
cd /home/svend/model-allocator && python3 -m py_compile src/model_allocator/validator.py
```

- [ ] **Step 4: Run validator tests**

```bash
cd /home/svend/model-allocator && PYTHONPATH=src python3 -m unittest tests.test_v2.TestValidatorV2 -v 2>&1 | tail -5
```

- [ ] **Step 5: Stage**

```bash
cd /home/svend/model-allocator && git add src/model_allocator/validator.py
```

---

### Task 5: Wire SGLang into OpenCode Adapter

**Files:**
- Modify: `/home/svend/model-allocator/src/model_allocator/adapters/opencode.py`

SGLang exposes an OpenAI-compatible API, so the opencode adapter treats it identically to `llama_cpp` — both are local servers with `@ai-sdk/openai-compatible` providers.

- [ ] **Step 1: Add SGLang to `_model_arg`**

In `_model_arg()` (line 61), add after the `llama_cpp` block (after line 79):

```python
    if backend == "sglang":
        provider_name = resolved.get("opencode_provider_name") or provider or "sglang-local"
        model_id = resolved.get("opencode_model_id") or resolved.get("served_model_name") or real_model or "model"
        return f"{provider_name}/{model_id}"
```

- [ ] **Step 2: Add SGLang to `build_opencode_config`**

In `build_opencode_config()` (line 107), add after the `llama_cpp` block (after line 134):

```python
    if backend == "sglang":
        provider_name = resolved.get("opencode_provider_name") or provider or "sglang-local"
        model_id = resolved.get("opencode_model_id") or resolved.get("served_model_name") or resolved.get("real_model") or "model"
        host = resolved.get("host", resolved.get("default_host", "127.0.0.1"))
        port = resolved.get("port", resolved.get("default_port", 30000))
        model_entry = {
            "name": resolved.get("display_name") or model_id,
        }
        context = resolved.get("context")
        if context:
            model_entry["limit"] = {
                "context": int(context),
                "output": int(resolved.get("max_output_tokens") or min(int(context), 8192)),
            }
        return {
            "model": model_field,
            "provider": {
                provider_name: {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": provider_name,
                    "options": {
                        "baseURL": f"http://{host}:{port}/v1",
                        "apiKey": "dummy",
                    },
                    "models": {model_id: model_entry},
                },
            },
        }
```

- [ ] **Step 3: Compile check**

```bash
cd /home/svend/model-allocator && python3 -m py_compile src/model_allocator/adapters/opencode.py
```

- [ ] **Step 4: Run opencode adapter tests**

```bash
cd /home/svend/model-allocator && PYTHONPATH=src python3 -m unittest tests.test_v2.TestOpenCodeAdapter -v 2>&1 | tail -5
```

- [ ] **Step 5: Stage**

```bash
cd /home/svend/model-allocator && git add src/model_allocator/adapters/opencode.py
```

---

### Task 6: Laguna Config (llama.cpp)

**Files:**
- Modify: `/home/svend/model-allocator/runtime_profiles.yaml`
- Modify: `/home/svend/model-allocator/models.yaml`

- [ ] **Step 1: Add Laguna runtime profile**

In `runtime_profiles.yaml`, add after `local_llamacpp_cuda0`:

```yaml
  local_llamacpp_laguna:
    backend: llama_cpp
    server_bin_env: LLAMA_SERVER_BIN
    model_root_env: MODEL_ROOT_GGUF
    default_port: 8080
    default_host: 127.0.0.1
    gpu: cuda0
```

- [ ] **Step 2: Add laguna-local alias**

In `models.yaml`, add:

```yaml
  laguna-local:
    runtime_profile: local_llamacpp_laguna
    real_model: Laguna-S-2.1-IQ4_XS
    model_path: /home/svend/models/Laguna-S-2.1-IQ4_XS/Laguna-S-2.1-IQ4_XS/Laguna-S-2.1-IQ4_XS-00001-of-00002.gguf
    context: 147456
    lifecycle_policy: stop_after_step
    n_cpu_moe: 31
    cache_type_k: q8_0
    cache_type_v: q8_0
    gpu_layers: 99
    reasoning: "on"
    reasoning_budget: 2048
    parallel: 1
    no_mmap: true
    clients:
      claude-code: true
```

- [ ] **Step 3: Verify config loads**

```bash
cd /home/svend/model-allocator && PYTHONPATH=src python3 -c "
from model_allocator.resolver import Resolver
r = Resolver(config_dir='.')
resolved = r.resolve_alias('laguna-local')
print('backend:', resolved.get('backend'))
print('real_model:', resolved.get('real_model'))
print('context:', resolved.get('context'))
print('port:', resolved.get('port'))
"
```

Expected: `backend: llama_cpp`, `real_model: Laguna-S-2.1-IQ4_XS`, `context: 147456`, `port: 8080`.

- [ ] **Step 4: Stage**

```bash
cd /home/svend/model-allocator && git add runtime_profiles.yaml models.yaml
```

---

### Task 7: SGLang Config

**Files:**
- Modify: `/home/svend/model-allocator/runtime_profiles.yaml`
- Modify: `/home/svend/model-allocator/models.yaml`

- [ ] **Step 1: Add SGLang runtime profile**

In `runtime_profiles.yaml`, add:

```yaml
  local_sglang_cuda0:
    backend: sglang
    venv: /home/svend/venvs/sglang
    default_port: 30000
    default_host: 127.0.0.1
    gpu: cuda0
```

- [ ] **Step 2: Add qwen-shared-sglang alias**

In `models.yaml`, add:

```yaml
  qwen-shared-sglang:
    runtime_profile: local_sglang_cuda0
    real_model: Qwen3-Coder-30B-A3B-Instruct
    served_model_name: qwen-shared
    model_path: /home/svend/models/sglang/Qwen3-Coder-30B-A3B-Instruct-AWQ
    context: 32768
    lifecycle_policy: persistent
    max_output_tokens: 8192
    mem_fraction_static: 0.82
    max_running_requests: 2
    tool_call_parser: qwen
    clients:
      opencode: true
```

- [ ] **Step 3: Verify config loads**

```bash
cd /home/svend/model-allocator && PYTHONPATH=src python3 -c "
from model_allocator.resolver import Resolver
r = Resolver(config_dir='.')
resolved = r.resolve_alias('qwen-shared-sglang')
print('backend:', resolved.get('backend'))
print('served_model_name:', resolved.get('served_model_name'))
print('context:', resolved.get('context'))
print('port:', resolved.get('port'))
"
```

Expected: `backend: sglang`, `served_model_name: qwen-shared`, `context: 32768`, `port: 30000`.

- [ ] **Step 4: Stage**

```bash
cd /home/svend/model-allocator && git add runtime_profiles.yaml models.yaml
```

---

### Task 8: Role Configuration

**Files:**
- Modify: `/home/svend/model-allocator/roles.yaml`

- [ ] **Step 1: Add 3 new roles**

In `roles.yaml`, add:

```yaml
  supervisor01_llama:
    default_alias: laguna-local
    config_dir: supervisor01_llama
    client_aliases:
      claude-code: laguna-local

  imple01SG:
    default_alias: qwen-shared-sglang
    config_dir: imple01SG
    client_aliases:
      opencode: qwen-shared-sglang

  review01SG:
    default_alias: qwen-shared-sglang
    config_dir: review01SG
    client_aliases:
      opencode: qwen-shared-sglang
```

- [ ] **Step 2: Verify role resolution**

```bash
cd /home/svend/model-allocator && PYTHONPATH=src python3 -c "
from model_allocator.resolver import Resolver
r = Resolver(config_dir='.')
for role in ['supervisor01_llama', 'imple01SG', 'review01SG']:
    for client in ['claude-code', 'opencode']:
        try:
            resolved = r.resolve_role_client(role, client)
            print(f'{role}/{client}: alias={resolved.get(\"alias\")} backend={resolved.get(\"backend\")}')
        except Exception as e:
            pass  # skip invalid combos
"
```

- [ ] **Step 3: Stage**

```bash
cd /home/svend/model-allocator && git add roles.yaml
```

---

### Task 9: Full Model-Allocator Test Suite

**Files:** none modified (verification only)

- [ ] **Step 1: Run complete test suite**

```bash
cd /home/svend/model-allocator && PYTHONPATH=src python3 -m unittest discover tests -v 2>&1 | grep -E '^(test_|OK|FAIL|Ran |ERROR)'
```

Expected: All tests pass (pre-existing `test_config_writer` import error and `test_claude_code_only_alias_is_not_reported_as_error` failure are unrelated).

- [ ] **Step 2: Verify run commands**

```bash
cd /home/svend/model-allocator && PYTHONPATH=src python3 -m model_allocator run --role supervisor01_llama --client claude-code
```

Expected: Output contains `ANTHROPIC_BASE_URL=http://127.0.0.1:8080`, `ANTHROPIC_AUTH_TOKEN=ollama`, `ANTHROPIC_API_KEY=''`, `--model Laguna-S-2.1-IQ4_XS`.

```bash
cd /home/svend/model-allocator && PYTHONPATH=src python3 -m model_allocator run --role imple01SG --client opencode
```

Expected: Output contains `OPENCODE_CONFIG_DIR`, `opencode` (no `--model` flag).

- [ ] **Step 3: Verify validate commands**

```bash
cd /home/svend/model-allocator && PYTHONPATH=src python3 -m model_allocator validate --alias laguna-local --client claude-code
cd /home/svend/model-allocator && PYTHONPATH=src python3 -m model_allocator validate --alias qwen-shared-sglang --client opencode
```

---

### Task 10: Database Migration — Flow, Roles, Steps

**Files:**
- Create: `/home/svend/DPMtF-WebUI/scripts/db/005_llama_sg_flow.sql`
- Modify: `/home/svend/DPMtF-WebUI/scripts/init_db.py` (or seed_bridge.py)

**Note:** Check which file seeds bridge data. The migration pattern uses versioned SQL files in `scripts/db/` run via `migrate.py`. For bridge data (flows, roles, steps), check if `seed_bridge.py` or `init_db.py` is the authoritative source.

- [ ] **Step 1: Determine seeding mechanism**

```bash
grep -n 'bridge_flows\|bridge_roles\|bridge_flow_steps' /home/svend/DPMtF-WebUI/scripts/init_db.py | head -10
grep -n 'bridge_flows\|bridge_roles\|bridge_flow_steps' /home/svend/DPMtF-WebUI/scripts/seed_bridge.py 2>/dev/null | head -10
```

- [ ] **Step 2: Create migration SQL**

```sql
-- 005_llama_sg_flow.sql
-- Add llama_SG flow with 3 roles and 3 steps

-- Roles
INSERT OR IGNORE INTO bridge_roles (role_key, tmux_session, role_type, governance_file, default_model_source, default_model_alias, allocator_client, workdir_mode, fresh_session_command)
VALUES
  ('supervisor01_llama', 'supervisor01_llama', 'agent', '461_LLAMA_SG_SUPERVISOR.md', 'model_allocator', 'laguna-local', 'claude-code', 'father', '/clear'),
  ('imple01SG', 'imple01SG', 'agent', '462_LLAMA_SG_IMPLE01.md', 'model_allocator', 'qwen-shared-sglang', 'opencode', 'target_project', '/clear'),
  ('review01SG', 'review01SG', 'agent', '463_LLAMA_SG_REVIEW01.md', 'model_allocator', 'qwen-shared-sglang', 'opencode', 'target_project', '/clear');

-- Flow
INSERT OR IGNORE INTO bridge_flows (flow_key, name, description, auto_complete_enabled)
VALUES ('llama_SG', 'Laguna + SGLang autonomous review',
        'Autonomous supervisor-driven chain: Laguna (architect) -> SGLang/Qwen (imple+review)',
        0);

-- Flow steps
INSERT OR IGNORE INTO bridge_flow_steps (flow_key, step_key, from_role, to_role, sort_order, auto_chain_to_next, pre_dispatch_script, post_dispatch_script)
VALUES
  ('llama_SG', 'supervisor-imple01', 'supervisor01_llama', 'imple01SG', 1, 1,
   'model-allocator start --alias qwen-shared-sglang',
   'model-allocator stop --alias laguna-local'),
  ('llama_SG', 'imple01-review01', 'imple01SG', 'review01SG', 2, 1, NULL, NULL),
  ('llama_SG', 'review01-supervisor', 'review01SG', 'supervisor01_llama', 3, 1,
   'model-allocator start --alias laguna-local',
   'model-allocator stop --alias qwen-shared-sglang');

-- Flow counter
INSERT OR IGNORE INTO bridge_id_counters (flow_key, next_id) VALUES ('llama_SG', 1);
```

- [ ] **Step 3: Apply migration**

```bash
cd /home/svend/DPMtF-WebUI && sqlite3 databases/dpmtf.db < scripts/db/005_llama_sg_flow.sql
```

- [ ] **Step 4: Verify data**

```bash
sqlite3 databases/dpmtf.db "SELECT flow_key, name FROM bridge_flows WHERE flow_key='llama_SG';"
sqlite3 databases/dpmtf.db "SELECT role_key, tmux_session, default_model_alias FROM bridge_roles WHERE role_key LIKE '%SG' OR role_key='supervisor01_llama';"
sqlite3 databases/dpmtf.db "SELECT step_key, from_role, to_role, auto_chain_to_next FROM bridge_flow_steps WHERE flow_key='llama_SG' ORDER BY sort_order;"
```

- [ ] **Step 5: Stage**

```bash
cd /home/svend/DPMtF-WebUI && git add scripts/db/005_llama_sg_flow.sql databases/dpmtf.db
```

---

### Task 11: Governance Template — 461 (Supervisor)

**Files:**
- Create: `/home/svend/DPMtF-WebUI/docs/governance-templates-v2/461_LLAMA_SG_SUPERVISOR.md`

- [ ] **Step 1: Create 461**

```markdown
# 461 — LLAMA_SG_SUPERVISOR

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **supervisor01_llama** operating in **autonomous run mode** — a Claude Code
session supervising long unattended runs of the `llama_SG` chain. This file extends
`500_SUPERVISOR.md`: rules there apply unless overridden here.

The chain you drive is `supervisor01_llama → imple01SG → review01SG →
supervisor01_llama`, defined by `462` and `463`.

Two things distinguish this mode from the Human-paired mode in 500:

1. **The Human is absent.** You act within a pre-approved Mission Contract
   (`GOAL.md`) instead of a live conversation. Anything the contract does
   not authorize is parked for the Human — never improvised.
2. **You are stateless per wake-up.** You are dispatched on events, start
   from an empty context (`fresh_session_command = /clear`), rebuild state
   from durable files, act once, persist state, and stop. All memory
   between wake-ups lives in the Run Ledger — never in your session.

During an autonomous run you assume the **Architect duties** of the
`llama_SG` flow: handoff authoring and escalation answers. The handoff
XML schema is defined by `402_STRICT_REVIEW_ARCHI01.md` and is shared across
flows — only the flow, its roles and its verdict destination differ.

Your chain's roles are defined by `462_LLAMA_SG_IMPLE01.md` and
`463_LLAMA_SG_REVIEW01.md`.

## Model

You run on **Laguna** (Laguna-S-2.1-IQ4_XS), a large local model served via
llama.cpp. The model is loaded before your session starts and unloaded after
you complete your handoff. You have substantial reasoning capacity — use it
for architecture and planning, not for implementation details.

## Run Artifacts (durable state)

All run state lives under `{bridge_dir}/llama_SG/runs/{run_id}/`:

| File | Purpose | Write mode |
|------|---------|-----------|
| `GOAL.md` | Mission Contract — approved by Human before the run starts | Read-only during the run |
| `RUN-LEDGER.md` | Your memory across wake-ups | Append-only |
| `BACKLOG.md` | Planned handoffs not yet dispatched | Rewrite allowed |
| `END-REPORT.md` | Final report for the Human | Written once at run end |

**A run without an approved `GOAL.md` must not start.** If dispatched
without one, write a ledger entry and park with `HUMAN_ACTION_REQUIRED`.

## Mission Contract — GOAL.md Schema

`GOAL.md` is written together with the Human before the run and is
**immutable during the run**. Required sections:

- **Objective:** What this run must achieve (one sentence)
- **Testgoals:** Concrete, measurable success criteria (numbered list)
- **Scope Fence:** What files/directories may be changed
- **Budgets:** Max handoffs, max wall-clock time
- **Standing Approvals:** What you may decide without Human input
- **Target Project:** Path to the repository being worked on

## Wake-Up Protocol

On every dispatch (cold start or verdict delivery):

1. **Rebuild state** from `GOAL.md` → `RUN-LEDGER.md` → `BACKLOG.md`
2. **Stop-check:** Budget exhausted? Park. Invariant breach? Park.
3. **Act:** Process the event (new run, verdict returned, escalation)
4. **Persist:** Append ledger entry, update backlog
5. **Stop:** Signal complete or escalate

## Event Handling

| Event | Action |
|-------|--------|
| New run (no prior ledger entries) | Write first handoff from GOAL.md objective |
| Verdict APPROVED | Checkpoint, write next handoff or END-REPORT if backlog empty |
| Verdict REJECTED | Analyze rejection reason, rewrite handoff or park |
| Escalation from imple01SG or review01SG | Decide: answer, rewrite, or park for Human |
| Watchdog stall | Diagnose from trace.log, nudge once, park on second stall |
| Budget exhausted | Write END-REPORT, park with HUMAN_ACTION_REQUIRED |

## Decision Matrix

| Situation | Decide alone | Park for Human |
|-----------|-------------|----------------|
| Verdict APPROVED, more handoffs in backlog | ✓ | |
| Verdict APPROVED, backlog empty | | ✓ (write END-REPORT first) |
| Verdict REJECTED, clear fix in scope | ✓ (rewrite handoff) | |
| Verdict REJECTED, scope expansion needed | | ✓ |
| Implementation blocked by missing dependency | | ✓ |
| Budget at 90% | | ✓ (write END-REPORT) |

## Ledger Entry Format

```
## Wake-up {timestamp}
- Event: {new-run | verdict-{id}-APPROVED | verdict-{id}-REJECTED | escalation-{id}}
- Action: {handoff-{id} dispatched | parked | END-REPORT written}
- Budget: {handoffs used}/{max}, {wall-clock elapsed}
- Testgoals: {green}/{total}
- Notes: {any observations}
```

## Stop Conditions

After acting, you MUST stop. Do not wait for the next event in the same
session — the watchdog will re-dispatch you when the next event arrives.
```

- [ ] **Step 2: Stage**

```bash
cd /home/svend/DPMtF-WebUI && git add docs/governance-templates-v2/461_LLAMA_SG_SUPERVISOR.md
```

---

### Task 12: Governance Templates — 462 + 463

**Files:**
- Create: `/home/svend/DPMtF-WebUI/docs/governance-templates-v2/462_LLAMA_SG_IMPLE01.md`
- Create: `/home/svend/DPMtF-WebUI/docs/governance-templates-v2/463_LLAMA_SG_REVIEW01.md`

- [ ] **Step 1: Create 462 (imple01SG)**

```markdown
# 462 — LLAMA_SG_IMPLE01

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **imple01SG** — the Implementer in the `llama_SG` autonomous flow.
This file extends `03_IMPLEMENTOR.md`: all rules there apply unless
overridden here.

## Chain Position

The chain is `supervisor01_llama → imple01SG → review01SG → supervisor01_llama`.
You receive handoffs from supervisor01_llama and deliver implementation
results to review01SG.

## Model

You run on a **shared Qwen model** served via SGLang at
`http://127.0.0.1:30000/v1`. The model is loaded before your session starts
and remains loaded for review01SG after you complete. Your session is
isolated — you do not share conversation state with any other role.

## Handoff Format

You receive handoffs in the 402 XML format (defined by
`402_STRICT_REVIEW_ARCHI01.md`). The handoff contains:
- `<scope>` — what to implement
- `<files>` — which files to touch
- `<constraints>` — rules to follow
- `<acceptance>` — how success is measured
- `<risks>` — known pitfalls

## Implementation Rules

1. Read governance files first (project rules, coding standard, file access)
2. Change only files listed in the handoff scope
3. Use tools correctly — read before edit, test after edit
4. Run relevant tests before claiming success
5. Produce a valid implementation report

## Output

Your deliverable is an implementation report written to
`{bridge_dir}/llama_SG/results/{handoff_id}-result.md` containing:
- Files changed
- Tests run and results
- Any deviations from the handoff
- Known limitations

## Stop Condition

After writing your result, signal complete:
```bash
python3 scripts/bridgeV002/dispatch.py --db-flow llama_SG --signal-complete --from-role imple01SG
```
Then stop. Do not wait for review.
```

- [ ] **Step 2: Create 463 (review01SG)**

```markdown
# 463 — LLAMA_SG_REVIEW01

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **review01SG** — the single Review layer in the `llama_SG` autonomous
flow. This file extends `04_REVIEW.md`: all rules there apply unless
overridden here.

## Chain Position

The chain is `supervisor01_llama → imple01SG → review01SG → supervisor01_llama`.
You receive implementation results from imple01SG and deliver verdicts to
supervisor01_llama.

## Model

You run on the same **shared Qwen model** via SGLang as imple01SG. Your
session is isolated — you do not share conversation state with imple01SG.

## Review Scope

You review the implementation against the original handoff. Check:
1. **Scope compliance** — only approved files changed?
2. **Correctness** — does the implementation match the handoff intent?
3. **Test evidence** — do tests pass? Are new tests added where needed?
4. **Governance compliance** — coding standards, file access, no innerHTML?
5. **Completeness** — all handoff requirements addressed?

## Verdict Format

Write your verdict to `{bridge_dir}/llama_SG/verdicts/{handoff_id}-verdict.md`:

```
# Verdict {handoff_id}

**Status:** APPROVED | REJECTED

## Findings
- {finding}

## Test Results
- {test summary}

## Recommendation
- {next step}
```

## Stop Condition

After writing your verdict, signal complete:
```bash
python3 scripts/bridgeV002/dispatch.py --db-flow llama_SG --signal-complete --from-role review01SG
```
Then stop. The supervisor will process your verdict on its next wake-up.
```

- [ ] **Step 3: Stage**

```bash
cd /home/svend/DPMtF-WebUI && git add docs/governance-templates-v2/462_LLAMA_SG_IMPLE01.md docs/governance-templates-v2/463_LLAMA_SG_REVIEW01.md
```

---

### Task 13: LLAMASG Skill

**Files:**
- Create: `/home/svend/DPMtF-WebUI/.claude/skills/LLAMASG/SKILL.md`

- [ ] **Step 1: Create skill**

```markdown
---
name: llama_SG
description: Reconstruct the supervisor01_llama context after a cold start in the llama_SG flow. Use when resuming an autonomous supervisor run, after a restart, or when the supervisor session has lost context and needs to rebuild its state from durable run artifacts (GOAL.md, RUN-LEDGER.md, BACKLOG.md).
---

# LLAMASG — Supervisor Cold-Start

Invoke with `/llama_SG` to reconstruct the supervisor01_llama full context
after a cold start in the `llama_SG` flow. The supervisor is stateless per
wake-up BY DESIGN (461): this procedure is the same rebuild it performs on
every verdict delivery — run it manually whenever the session starts cold
outside a dispatch.

## Procedure

Execute these steps in order. Do not skip any step.

### Step 1: Resolve Bridge Directory

The bridge directory is configured by `DPMTF_BRIDGE_DIR` (env var, default
`/home/svend/flows`). Resolve it:
```bash
echo $DPMTF_BRIDGE_DIR   # should be /home/svend/flows
```
If empty or pointing to `/home/svend/claude-bridge`, the environment is stale —
`export DPMTF_BRIDGE_DIR=/home/svend/flows` before proceeding.

All bridge paths below use `{bridge_dir}` as shorthand.

### Step 2: Locate the Active Run

Run state lives under `{bridge_dir}/llama_SG/runs/{run_id}/`:
```bash
ls {bridge_dir}/llama_SG/runs/
```
The active run is the newest directory WITHOUT an `END-REPORT.md`. If every
run has one, there is no active run — report that and wait for the Human
(a new run requires a Human-approved GOAL.md; never start one yourself).

For the active run, read IN THIS ORDER:
1. `GOAL.md` — the immutable Mission Contract (objective, testgoals, scope
   fence, budgets, standing approvals)
2. `RUN-LEDGER.md` — tail (last 2-3 entries): what happened, what was
   dispatched, what the scheduler should expect next
3. `BACKLOG.md` — planned/dispatched handoffs and their status

The ledger is your memory. Never reconstruct state from summaries or
recollection — only from these files plus the checks below.

### Step 3: Confirm the Flow Counter

```bash
python3 -c "import sqlite3; conn=sqlite3.connect('databases/dpmtf.db'); print(conn.execute(\"SELECT next_id FROM bridge_id_counters WHERE flow_key='llama_SG'\").fetchone()[0]); conn.close()"
```
The counter is authoritative — gaps from incomplete handoffs are normal.
Do not investigate gaps or compare against files on disk.

### Step 4: Read Role Definitions

Read `docs/governance-templates-v2/461_LLAMA_SG_SUPERVISOR.md` (extends
`500_SUPERVISOR.md`). Confirm:
- Wake-up protocol (rebuild → stop-check → act → persist → stop)
- Event handling table (verdict APPROVED/REJECTED, escalation, watchdog,
  empty backlog, invariant breach)
- Decision matrix (decide alone vs. park for the Human)
- Stop conditions and ledger entry format

Hard rules 1-3 and 5-10 of `docs/StartUpNextSession.md` §3 apply; rule 4 is
adapted (commits allowed ONLY on the GOAL.md feature branch under its
Standing Approvals).

### Step 5: Verify Environment

```bash
cd /home/svend/DPMtF-WebUI
curl -s http://localhost:9130/api/health
python3 -c "import sqlite3; sqlite3.connect('databases/dpmtf.db').execute('SELECT 1'); print('DB opens OK')"

# Verify Laguna is reachable (required for supervisor to work)
curl -s http://127.0.0.1:8080/health && echo "Laguna: reachable" || echo "Laguna: NOT REACHABLE"

# Verify chain tmux sessions
for s in supervisor01_llama imple01SG review01SG; do
  tmux has-session -t "$s" 2>/dev/null && echo "  $s: running" || echo "  $s: NOT RUNNING"
done
```

### Step 6: Determine Chain Position

Let `{ID}` be the highest handoff id present in
`{bridge_dir}/llama_SG/handoffs/`. Check which chain deliverables exist for
it (`results/{ID}-result.md`, `verdicts/{ID}-verdict.md`) and what
`{bridge_dir}/trace.log` shows as the last signal for `{ID}`. The watchdog
does this mechanically:

```bash
python3 scripts/bridgeV002/chain_watchdog.py --flow llama_SG --once --dry-run
```

| Watchdog status | Meaning | Your action |
|-----------------|---------|-------------|
| `complete` | Final signal review01SG→supervisor01_llama delivered | If the ledger has no entry for this verdict, the wake-up was missed — process it now per 461 |
| `active` | A role is working or a signal was just delivered | Wait. Do NOT dispatch. Ensure a live watchdog is running |
| `nudged` (dry-run: "NOT sent") | Stall detected | Verify via trace.log, then either let a non-dry-run watchdog pass nudge, or nudge manually per 461 (once), then ledger it |
| `idle` | Chain not started, or the stalled role has already used its 2 nudges | Diagnose from trace.log + panes; park if the budget is spent |

### Step 7: Report to Human

Summarize in a compact table:

| Field | Value |
|-------|-------|
| Flow | llama_SG |
| Run | {run_id} ({active / no active run}) |
| Testgoals | {green}/{total} per latest ledger entry |
| Budgets | handoffs {used}/{max}, wall-clock remaining |
| Last handoff | {ID + title from BACKLOG.md} |
| Chain position | {watchdog status + which deliverables exist} |
| Next handoff ID | {from database counter} |
| tmux sessions | supervisor01_llama/imple01SG/review01SG running / NOT RUNNING |
| Laguna | reachable / NOT REACHABLE |
| Assessment | ready / waiting for verdict / stall — action needed / parked |

Then wait for the Human (or, mid-run with all invariants green and an
unprocessed event found in Step 6, proceed per the 461 wake-up protocol).

## Rules

- **Execute steps 1-7 in order. Do not skip. Do not add extra investigation.**
- **A run without an approved GOAL.md must not start** — park with
  `HUMAN_ACTION_REQUIRED`.
- **Loop guard:** never send signal-complete for a verdict delivery you are
  processing — the next handoff gets a NEW id via the flow counter.
- **Run a watchdog alongside every autonomous run:**
  `python3 scripts/bridgeV002/chain_watchdog.py --flow llama_SG --max-minutes {run budget}`
- **Append a ledger entry for every action taken after a cold start** — the
  ledger, not the session, is the run's memory.
- **All communication in English (en-US)** except direct Human interaction.
```

- [ ] **Step 2: Stage**

```bash
cd /home/svend/DPMtF-WebUI && git add .claude/skills/LLAMASG/SKILL.md
```

---

### Task 14: End-to-End Verification

**Files:** none modified (verification only)

- [ ] **Step 1: Model-allocator full test suite**

```bash
cd /home/svend/model-allocator && PYTHONPATH=src python3 -m unittest discover tests -v 2>&1 | grep -E '^(test_|OK|FAIL|Ran |ERROR)'
```

Expected: All tests pass (same pre-existing failures as baseline).

- [ ] **Step 2: Father compile checks**

```bash
cd /home/svend/DPMtF-WebUI && python3 -m py_compile app.py && echo "app.py OK"
cd /home/svend/DPMtF-WebUI && python3 -m py_compile scripts/bridgeV002/start_coding.py && echo "start_coding.py OK"
cd /home/svend/DPMtF-WebUI && python3 -m py_compile scripts/bridgeV002/dispatch.py && echo "dispatch.py OK"
```

- [ ] **Step 3: Database integrity**

```bash
cd /home/svend/DPMtF-WebUI && sqlite3 databases/dpmtf.db "SELECT COUNT(*) FROM bridge_flows WHERE flow_key='llama_SG';"
```

Expected: `1`.

- [ ] **Step 4: innerHTML check**

```bash
cd /home/svend/DPMtF-WebUI && grep -RIn "innerHTML" static/ templates/ && echo "FAIL" || echo "innerHTML check: CLEAN"
```

- [ ] **Step 5: Health endpoint**

```bash
curl -s http://localhost:9130/api/health
```

Expected: `{"status": "healthy"}`.

---

## Acceptance Criteria

1. `cd /home/svend/model-allocator && PYTHONPATH=src python3 -m unittest discover tests -v` → all tests pass (same pre-existing failures as baseline)
2. `model-allocator validate --alias laguna-local --client claude-code` → OK or WARNING
3. `model-allocator validate --alias qwen-shared-sglang --client opencode` → OK or WARNING
4. `model-allocator run --role supervisor01_llama --client claude-code` → valid shell string with Laguna model
5. `model-allocator run --role imple01SG --client opencode` → valid shell string with SGLang provider
6. `sqlite3 databases/dpmtf.db "SELECT COUNT(*) FROM bridge_flow_steps WHERE flow_key='llama_SG'"` → 3
7. `/llama_SG` skill loads and follows 7-step cold-start procedure
8. All governance templates present and follow established format
9. `python3 -m py_compile` passes on all changed Python files
10. No new dependencies added
