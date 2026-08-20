"""One-shot invocation: run a task through a harness and capture the result.

The primary interface::

    execute(role, harness, model_target, cwd, task) -> {status, output, error,
                                                        elapsed, pid,
                                                        request_id, ...}

``model_target`` is the ALREADY-RESOLVED model target supplied by Model
Allocator. This package never resolves or substitutes it — it only renders it
into the harness's native CLI and reports its identity. The result dict always
includes the original ``status``/``output``/``error``/``elapsed`` keys (for
backward compatibility) plus operational metadata: ``pid``, ``request_id``,
``harness``, ``role``, ``model_target``, ``payload_chars``, ``payload_lines``,
``payload_sha256``.

Progress (RUNNING / periodic HEARTBEAT) is surfaced through an optional
``on_event`` callback without exposing private reasoning. The final SUCCESS or
ERROR is reported by the terminal from the returned result, not by ``on_event``.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import threading
import time as _time

from .adapter import build_task_invocation
from .definition import model_target_identity, resolve_harness, resolve_role_key
from .status import ERROR, RUNNING, SUCCESS
from .transport import compute_identity, make_request_id

#: Time between heartbeat emissions while a harness subprocess stays alive.
DEFAULT_HEARTBEAT_INTERVAL = 15.0


def execute(role="", harness=None, model_target="", cwd=None, task="", cfg=None,
            timeout=None, request_id="", heartbeat_interval=None, on_event=None) -> dict:
    """Run ``task`` through ``harness`` and return the contract result.

    ``model_target`` is the already-resolved target; it is never resolved or
    substituted here. ``harness`` may be omitted when ``role`` already carries
    the harness key. ``cwd`` is the working directory (``None`` = inherit the
    caller's). ``timeout`` is an optional per-invocation cap in seconds.
    ``heartbeat_interval`` controls heartbeat cadence (default
    :data:`DEFAULT_HEARTBEAT_INTERVAL`). ``on_event``, when given, is called as
    ``on_event(kind, payload)`` with ``kind`` in ``{RUNNING, "HEARTBEAT"}``.
    ``cfg`` is injectable for tests.
    """
    start = _time.monotonic()
    if heartbeat_interval is None:
        heartbeat_interval = DEFAULT_HEARTBEAT_INTERVAL

    harness_key = (harness or "").strip() or resolve_harness(role)
    role_key = resolve_role_key(role)
    mt_identity = model_target_identity(model_target)
    rid = (request_id or "").strip() or make_request_id()
    ident = compute_identity(rid, task)

    base = {
        "request_id": rid,
        "harness": harness_key,
        "role": role_key,
        "model_target": mt_identity,
        "payload_chars": ident.chars,
        "payload_lines": ident.lines,
        "payload_sha256": ident.sha256,
    }

    try:
        command = build_task_invocation(harness_key, model_target=model_target, task=task, cfg=cfg)
        proc_result = run_command(
            command,
            cwd=cwd or os.getcwd(),
            timeout=timeout,
            heartbeat_interval=heartbeat_interval,
            on_event=on_event,
            event_context=dict(base),
        )
        return {**base, **proc_result}
    except Exception as exc:  # noqa: BLE001 — the contract reports, never raises
        elapsed = _time.monotonic() - start
        return {
            **base,
            "status": ERROR,
            "output": "",
            "error": str(exc),
            "elapsed": elapsed,
            "pid": None,
        }


def run_command(command, *, cwd, timeout=None, heartbeat_interval=15.0,
                on_event=None, event_context=None) -> dict:
    """Spawn ``command`` and return ``{status, output, error, elapsed, pid}``.

    Emits ``RUNNING`` (with pid) at start and ``HEARTBEAT`` (with elapsed and
    process-alive) while the subprocess stays alive, through ``on_event``.
    Output pipes are drained on a background thread so a large payload/output
    can never deadlock the heartbeat loop.
    """
    ctx = dict(event_context or {})
    argv = shlex.split(command)
    try:
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd
        )
    except Exception as exc:  # noqa: BLE001 — reported, not raised
        if on_event:
            on_event(ERROR, {**ctx, "pid": None, "elapsed": 0.0})
        return {"status": ERROR, "output": "", "error": str(exc), "elapsed": 0.0, "pid": None}

    start = _time.monotonic()
    pid = proc.pid
    if on_event:
        on_event(RUNNING, {**ctx, "pid": pid, "elapsed": 0.0, "process_alive": True})

    captured = {}

    def _capture():
        out, err = proc.communicate()
        captured["out"] = out or ""
        captured["err"] = err or ""

    drainer = threading.Thread(target=_capture, daemon=True)
    drainer.start()

    deadline = (start + timeout) if timeout else None
    last_hb = start
    while True:
        rc = proc.poll()
        if rc is not None:
            break
        now = _time.monotonic()
        if deadline is not None and now >= deadline:
            try:
                proc.kill()
            except Exception:  # noqa: BLE001 — best-effort kill on timeout
                pass
            break
        if now - last_hb >= heartbeat_interval:
            if on_event:
                on_event(
                    "HEARTBEAT",
                    {**ctx, "pid": pid, "elapsed": now - start, "process_alive": True},
                )
            last_hb = now
        _time.sleep(0.2)

    drainer.join()
    elapsed = _time.monotonic() - start
    rc = proc.returncode
    status = SUCCESS if rc == 0 else ERROR
    return {
        "status": status,
        "output": captured.get("out", ""),
        "error": captured.get("err", ""),
        "elapsed": elapsed,
        "pid": pid,
    }
