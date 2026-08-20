# Harness Allocator

A standalone, **harness-neutral** allocator for coding harnesses. It resolves a
role to a harness key, builds the invocation, runs one-shot turns over an atomic
framed task transport, and reports status — **independent of DPMtF** flows,
verdicts, roles, governance, dispatch, and the bridge database.

This is an **optional companion project** to DPMtF-WebUI. DPMtF keeps its own
dispatch, database, roles, verdicts and governance; it only ever needs to ask
this package for behaviour, not for command strings.

## Model boundary

Harness Allocator does **not** resolve, select, replace, or own the model.
Model Allocator resolves the model target first; DPMtF passes the already-resolved
`model_target` here, and the allocator only renders it into the harness's native
CLI. There is no `resolve_model()` and no silent model or harness substitution.

## What it owns

- **Identity resolution** — `resolve_harness`, `resolve_role_key`,
  `HarnessDefinition.from_role` (role → harness key). No model.
- **Command generation** — `build_launch_command`, `build_dsh_invocation`,
  `build_task_invocation` (the DeepSeek Harness and Codex launch surfaces),
  rendering a passed-through `model_target`.
- **Atomic task transport** — `transport.py` (`encode_request`, `extract_frame`,
  `FrameReader`): one length-delimited frame per semantic task, so embedded
  newlines never fragment a task into multiple turns.
- **Request identity / payload verification** — `compute_identity` returns
  `request_id`, `chars`, `lines`, `sha256` (execution metadata, never
  chain-of-thought).
- **One-shot execution** — `execute(role, harness, model_target, cwd, task)`
  returning `{ status, output, error, elapsed, pid, request_id, ... }`.
- **The persistent terminal loop** — `render_banner` + `run_terminal` + `main`
  (`python3 -m harness_allocator`): banner → atomic request → execute → READY,
  with RUNNING/HEARTBEAT/SUCCESS/ERROR progress and no private reasoning.
- **Duplicate-request protection** — a completed `(request_id, payload sha256)`
  is recorded and never executed twice: a repeat reports `DUPLICATE_REQUEST`
  and returns to READY, unless the frame carries an explicit `retry` flag.
- **Readiness/status state** — `READY` / `RUNNING` / `SUCCESS` / `ERROR` /
  `DUPLICATE_REQUEST`.
- **Environment requirements** — `REQUIRED_ENV`, `missing_env`,
  `describe_missing`.

## What it must never own

DPMtF flows, verdicts, roles, governance, dispatch, or any bridge database.
Nothing in this package imports or queries a database. It also never owns the
model: no resolution, no selection, no silent substitution.

## Interface

```python
from harness_allocator import execute

result = execute(role="probe", harness="dsh", model_target="deepseek-v4-pro",
                 cwd=".", task="Summarize this change.")
# -> {"status": "SUCCESS"|"ERROR", "output": str, "error": str,
#     "elapsed": float, "pid": int|None, "request_id": str,
#     "harness": str, "role": str, "model_target": str,
#     "payload_chars": int, "payload_lines": int, "payload_sha256": str}
```

`execute` always returns that shape — on failure the error is reported in
`error`, never raised. `model_target` is the caller's already-resolved target.

## Atomic task transport

The terminal's stdin is a byte stream. A naive `readline` loop fragments a
multi-line task into many turns. The framed protocol fixes that:

```
HAR-FRAME <request_id> <byte_length> [retry]\n
<exactly byte_length bytes of payload>
```

`encode_request(request_id, payload)` produces the frame bytes; the dispatcher
writes them atomically. `FrameReader` reassembles them, so ONE complete semantic
task = EXACTLY ONE invocation. A bare single line (no header) is still accepted
as a transitional legacy request.

The optional `retry` token (`encode_request(request_id, payload, retry=True)`)
is the only way to re-execute a completed request identity. Without it, a repeat
of a completed `request_id` + payload hash is reported as `DUPLICATE_REQUEST`
and returns to READY rather than running again.

## Layout

```
harness_allocator/
  __init__.py   public API
  config.py     own config surface (env vars + harness-allocator.ini)
  status.py     READY/RUNNING/SUCCESS/ERROR/DUPLICATE_REQUEST tokens
  definition.py harness identity + environment requirements (no model)
  adapter.py    command generation (model_target passthrough)
  transport.py  atomic framed transport + request identity
  invoke.py     execute() — one-shot run + capture + heartbeat
  terminal.py   persistent Harness Terminal loop + CLI
```

## Configuration

Reads, in priority order:

1. Environment variables — `CODEX_BIN`, `DSH_BIN`, `DSH_PROFILE`,
   `DSH_V4_PRO_PATCH`.
2. `harness-allocator.ini` (`[harness]` section) — committed defaults.
3. Hardcoded fallbacks (`codex`, `npx @deepseek-ai/dsh`, `headless`, empty patch).

There is no `.env` loader: credentials come from the process environment, so a
harness inherits them exactly as its own CLI expects.

## Requirements

Python 3.10+. **Zero runtime dependencies** — standard library only.

## Run the tests

```bash
python3 -m pytest tests -q
```

## Try it

```bash
# Run the persistent terminal (reads framed requests from stdin, Ctrl-D to quit).
python3 -m harness_allocator --role probe --harness dsh \
    --model-target deepseek-v4-pro --cwd .

# Or one-shot from Python.
python3 -c "from harness_allocator import execute; print(execute(role='probe', harness='dsh', model_target='deepseek-v4-pro', cwd='.', task='echo ok'))"

# Encode a frame for dispatch (atomic, multi-line safe).
python3 -c "from harness_allocator import encode_request; import sys; sys.stdout.buffer.write(encode_request('ha-1', 'line one\nline two\n'))"
```
