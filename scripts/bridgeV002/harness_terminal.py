#!/usr/bin/env python3
"""Harness Terminal — a persistent, harness-neutral terminal for one-shot harnesses.

Runs inside a role's tmux session. It prints a role/harness/model banner, then
loops: read a complete submission from stdin (accumulating bytes until the
input stream goes idle, so raw tmux multiline pastes reach the harness as
ONE complete prompt), execute it through the resolved harness adapter
(one-shot), show the result, and return to READY.

Multiline atomicity: a 20k+ character paste containing hundreds of embedded
newlines is delivered to the harness runner as exactly one complete Python
string, producing exactly one harness invocation. The submission Enter and
the embedded newlines are separable: the reader treats the raw byte stream
as data until it goes idle (no new bytes for ``IDLE_FLUSH_SECONDS``), at
which point the accumulated text is submitted as one prompt. Newlines in
the paste are content, never request boundaries.

Harness-neutral by construction: it knows only a resolved harness key
(``dsh`` / ``codex`` / ``claude-code`` / ``opencode``) plus a role/harness/model
identity — never DPMtF flow, verdict, sequencing or governance semantics.
DPMtF composes the task and sends it here; this process only runs it.

Delegation: the package's command-building and identity logic live in the
standalone ``harness_allocator`` companion package (located via
``config.get_project_path`` / ``HARNESS_ALLOCATOR_PATH``). This module keeps
the consumer surface used by ``start_coding._harness_terminal_command`` and
the dispatch harness-wrap helper, plus the existing
``execute(harness_key, role_config, task, cwd)`` boundary that the
regression suite patches (``subprocess.run``). Subprocess invocation here
remains ``subprocess.run`` so the historical surface keeps working; the
underlying argv shape comes from the standalone's builders through the
``harness`` module, so there is exactly one command-builder source of
truth.

Operational visibility (objectives 5/6/7 of the run Mission Contract) is
delegated to ``harness_allocator.run_terminal``:

- Objective 5 (request identity): per-submission DISPATCH block with
  ``request_id``, ``chars``, ``lines``, ``sha256``, ``harness``, ``role``,
  ``model_target``.
- Objective 6 (lifecycle / heartbeat): ``[RUNNING]`` with pid + elapsed,
  periodic ``[HEARTBEAT]`` while the child process is alive (default
  cadence 15.0s, configurable), then ``[SUCCESS]``/``[ERROR]`` with final
  elapsed time, then a return to READY.
- Objective 7 (duplicate-request protection): a re-submitted completed
  ``(request_id, payload_sha256)`` identity reports ``[DUPLICATE_REQUEST]``
  and returns to READY without invoking the harness a second time.

The persistent loop bypasses ``ht.execute`` because its blocking
``subprocess.run`` cannot emit heartbeats. There is exactly one lifecycle
loop in the DPMtF-facing terminal — the standalone's ``run_terminal``,
parameterized with this module's idle-bounded reader and the
``_standalone_runner`` adapter. ``ht.execute`` is preserved for the
regression suite (which patches ``ht.subprocess.run`` directly) and any
older invoker that imports it.

No hardcoded ``/home/...`` paths. No new runtime dependencies.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import re
import select
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import harness  # noqa: E402

# Optional config import for ``_ensure_standalone_on_path``. The standalone
# loader uses ``config.get_project_path`` only when ``harness_allocator``
# isn't already importable, so a missing config module is acceptable here
# (the standalone may be installed with no project config).
try:  # noqa: E402
    import config  # type: ignore  # noqa: F401 — used lazily below
except ImportError:
    config = None  # type: ignore


def _ensure_standalone_on_path():
    """Make the standalone ``harness_allocator`` package importable.

    Delegates the location decision to the ``harness`` module, which uses
    ``config.get_project_path('harness-allocator')`` (or the
    ``HARNESS_ALLOCATOR_PATH`` env var). No hardcoded paths."""
    try:
        import harness_allocator  # noqa: F401 — presence check
        return
    except ImportError:
        pass
    if config is None:
        return
    pkg_dir = os.environ.get("HARNESS_ALLOCATOR_PATH") or \
        config.get_project_path("harness-allocator")
    pkg_parent = str(Path(pkg_dir).resolve())
    if pkg_parent not in sys.path:
        sys.path.insert(0, pkg_parent)


_ensure_standalone_on_path()
try:  # noqa: E402
    from harness_allocator.transport import (  # type: ignore
        RequestFrame,
        make_request_id,
    )
    from harness_allocator.status import (  # type: ignore
        NOT_CONFIGURED,
        UNKNOWN,
        status_value,
    )
except ImportError:
    # The standalone may not be available in the runtime environment. The
    # reader still works against plain bytes; it just won't be able to
    # return a structured RequestFrame. We fall back to a tiny shim so the
    # reader keeps its interface.
    class RequestFrame:  # type: ignore[no-redef]
        def __init__(self, request_id, payload, retry_flag=False):
            self.request_id = request_id
            self.payload = payload
            self.retry = retry_flag

    _counter = [0]

    def make_request_id(prefix="ha"):  # type: ignore[no-redef]
        _counter[0] += 1
        return f"{prefix}-{_counter[0]:06d}"

    NOT_CONFIGURED = "not configured"
    UNKNOWN = "unknown"

    def status_value(info, key, default=UNKNOWN, choices=()):  # type: ignore[no-redef]
        if not isinstance(info, dict):
            return default
        value = info.get(key)
        if value is None:
            return default
        text = " ".join(str(value).split())
        lowered = text.lower()
        if not text or any(marker in lowered for marker in
                           ("api_key", "token", "secret", "password", "credential")):
            return default
        if choices:
            allowed = {str(choice).lower() for choice in choices}
            if lowered not in allowed:
                return default
            return next(choice for choice in choices
                        if str(choice).lower() == lowered)
        return text[:512]


READY = "READY"
RUNNING = "RUNNING"
SUCCESS = "SUCCESS"
ERROR = "ERROR"
DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
CANCELLED = "CANCELLED"

#: Default heartbeat cadence (seconds) while a harness subprocess stays
#: alive. Matches the standalone's DEFAULT_HEARTBEAT_INTERVAL.
DEFAULT_HEARTBEAT_INTERVAL = 15.0

# Human labels for known harnesses/models — display only, never routing.
HARNESS_LABELS = {
    "dsh": "DeepSeek Harness",
    "codex": "Codex",
    "claude-code": "Claude Code",
    "opencode": "OpenCode",
}
MODEL_LABELS = {
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "MiniMax-M3": "MiniMax M3",
    "sonnet5": "Claude Sonnet 5",
}
MCP_LIGHT_STATES = ("connected", "available", "unavailable", "not configured")


def _runtime_info(status_info=None, runtime_info=None):
    source = status_info if status_info is not None else runtime_info
    return dict(source or {})


def _metadata_choice(environ, names, allowed, default=UNKNOWN):
    for name in names:
        raw = environ.get(name)
        if raw is None:
            continue
        text = " ".join(str(raw).split())
        lowered = text.lower()
        if not text or any(marker in lowered for marker in
                           ("api_key", "token", "secret", "password", "credential")):
            return default
        if lowered in allowed:
            return next(value for value in allowed if value == lowered)
    return default


def collect_runtime_status(harness_key=None, cwd=None):
    """Collect explicit, non-secret labels; bridge path comes from config.

    The configured bridge dir is reported ONLY when it was explicitly set:
    either via the ``DPMTF_BRIDGE_DIR`` environment variable, or via a
    non-default ``config.get_bridge_dir()`` value. The ``config`` getter
    falls back to ``<project_root>/flows`` when nothing is set, and we treat
    that literal default as "not configured" rather than fabricating one.
    See GOAL.md §8 for the requirement that values must come from real
    configuration/runtime information and not be guessed.
    """
    bridge_dir = os.environ.get("DPMTF_BRIDGE_DIR")
    if not bridge_dir and config is not None:
        try:
            configured = config.get_bridge_dir()
        except Exception:
            configured = ""
        if configured:
            # Disambiguate the config fallback from an explicit setting.
            try:
                default_bridge = str(Path(config.get_project_root()) / "flows")
            except Exception:
                default_bridge = ""
            if default_bridge and str(configured) == default_bridge:
                # Only the fallback path: nothing was actually configured.
                pass
            else:
                bridge_dir = str(configured)
    bridge_dir = bridge_dir or NOT_CONFIGURED

    bridge_access = _metadata_choice(
        os.environ,
        ("DPMTF_BRIDGE_ACCESS", "DPMTF_BRIDGE_DIR_ACCESS"),
        {"writable", "read-only", "unknown"},
        UNKNOWN,
    )
    if bridge_access == UNKNOWN and bridge_dir != NOT_CONFIGURED:
        try:
            bridge_access = "writable" if os.access(bridge_dir, os.W_OK) else "read-only"
        except (OSError, TypeError):
            bridge_access = UNKNOWN

    info = {
        "sandbox_mode": _metadata_choice(
            os.environ,
            ("DPMTF_SANDBOX_MODE", "DPMTF_SANDBOX"),
            {"workspace-write", "full-access", "read-only", "unknown"},
            UNKNOWN,
        ),
        "approval_policy": _metadata_choice(
            os.environ,
            ("DPMTF_APPROVAL_POLICY", "DPMTF_APPROVAL"),
            {"never", "on-request", "untrusted", "unknown"},
            UNKNOWN,
        ),
        "workspace_access_mode": _metadata_choice(
            os.environ,
            ("DPMTF_WORKSPACE_ACCESS_MODE", "DPMTF_WORKSPACE_ACCESS"),
            {"writable", "read-only", "unknown"},
            UNKNOWN,
        ),
        "bridge_dir": bridge_dir,
        "bridge_dir_access": bridge_access,
        "mcp_light": _metadata_choice(
            os.environ,
            ("DPMTF_MCP_LIGHT", "MCP_LIGHT_STATE", "MCP_LIGHT"),
            {"connected", "available", "unavailable", "not configured"},
            "not configured",
        ),
        "permission": _metadata_choice(
            os.environ,
            ("DPMTF_PERMISSION", "DPMTF_PERMISSION_MODE"),
            {"read-only", "workspace-write", "full-access", "unknown"},
            UNKNOWN,
        ),
    }
    # An explicit environment value always wins; what the harness's own
    # configuration can state fills only the fields that are still unknown.
    # The banner's rule stands — never guess — and these are not guesses:
    # they are read from the same configuration the launch is built from.
    if harness_key == "simple-harness":
        for key, value in _simple_harness_status(cwd or os.getcwd()).items():
            if info.get(key) in (UNKNOWN, NOT_CONFIGURED, None):
                info[key] = value
    return info


_SIMPLE_HARNESS_PERMISSION_LABELS = {
    "read_only": "read-only",
    "workspace_write": "workspace-write",
    "full_access": "full-access",
}


def _simple_harness_status(cwd):
    """Banner facts for a simple-harness role, from real configuration.

    Permission is the allocator's resolved ``--permission`` mode (env, then
    ini, then the harness default) — the very value the launch passes. The
    sandbox line is that mode; workspace access follows from it; approval
    is ``never`` because a headless one-shot harness has nobody to ask —
    the permission mode IS the whole policy. MCP-Light is read from the
    harness's own config files (``~/.simple-harness/config.json``, then
    ``.simple-harness/config.json`` searched upward from the workspace, the
    harness's own precedence) and probed once: ``available`` when the
    declared endpoint answers, ``unavailable`` when it does not, and
    ``not configured`` when no file declares it. The probe matters
    because the harness refuses to run at all when a configured server is
    unreachable (exit 2) — a pane that says ``unavailable`` at start is
    the warning before every dispatch fails.
    """
    facts = {}
    mode = ""
    try:
        mode = (harness._standalone().config.get_simple_harness_permission() or "").strip().lower()
    except Exception:  # noqa: BLE001 — a missing standalone leaves the field unknown
        mode = ""
    label = _SIMPLE_HARNESS_PERMISSION_LABELS.get(mode)
    if label:
        facts["permission"] = label
        facts["sandbox_mode"] = label
        facts["workspace_access_mode"] = "read-only" if mode == "read_only" else "writable"
    facts["approval_policy"] = "never"
    endpoint = _simple_harness_mcp_light_endpoint(cwd)
    if endpoint is None:
        facts["mcp_light"] = NOT_CONFIGURED
    else:
        facts["mcp_light"] = "available" if _probe_mcp_endpoint(endpoint) else "unavailable"
    return facts


def _simple_harness_mcp_light_endpoint(cwd):
    """The mcp-light endpoint the harness will connect to, or None.

    Later files override earlier ones field-wise in the harness, and
    ``mcp_servers`` is one field, so the LAST file that sets it wins.
    """
    candidates = [Path.home() / ".simple-harness" / "config.json"]
    node = Path(cwd).resolve()
    project = None
    for parent in [node, *node.parents]:
        probe = parent / ".simple-harness" / "config.json"
        if probe.is_file():
            project = probe
            break
    if project is not None:
        candidates.append(project)
    endpoint = None
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        servers = data.get("mcp_servers") if isinstance(data, dict) else None
        if not isinstance(servers, list):
            continue
        found = None
        for server in servers:
            if isinstance(server, dict) and server.get("name") == "mcp-light":
                found = server.get("endpoint") or ""
        endpoint = found  # this file sets the field: its answer replaces the earlier one
    return endpoint or None


def _probe_mcp_endpoint(endpoint, timeout=2.0):
    """One MCP initialize round trip; True when the server answers 2xx."""
    import urllib.request
    import urllib.error
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "dpmtf-harness-terminal", "version": "0"}},
    }).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False

#: How long the reader waits for new bytes before treating the accumulated
#: input as one complete submission. Tuned to comfortably outlast a normal
#: human Enter cadence while still feeling snappy on small inputs.
IDLE_FLUSH_SECONDS = 0.4
#: ANSI CSI / SS3 sequences (cursor keys, function keys, mode reports) that a
#: canonical-mode tty passes through into the input line.
_ANSI_CSI_RE = re.compile(r"\x1b(?:\[[0-9;?]*[ -/]*[@-~]|O[A-Za-z])")
IDLE_READ_INTERRUPTED = object()


def _label(labels, key):
    return labels.get(key, key)


def render_banner(flow, role, harness_key, model, cwd, status_info=None,
                  runtime_info=None):
    """The startup identity block, before the first READY prompt."""
    info = _runtime_info(status_info, runtime_info)
    if not flow:
        flow = status_value(info, "flow", "")
    lines = [
        "DPMtF Harness Terminal",
        "",
        f"Flow:    {flow}",
        f"Role:    {role}",
        f"Harness: {_label(HARNESS_LABELS, harness_key)}",
        f"Model:   {_label(MODEL_LABELS, model)}",
        f"Mode:    headless / one-shot",
        f"Cwd:     {cwd}",
        "",
        f"Sandbox: {status_value(info, 'sandbox_mode', UNKNOWN, ('workspace-write', 'full-access', 'read-only', UNKNOWN))}",
        f"Approval: {status_value(info, 'approval_policy', UNKNOWN, ('never', 'on-request', 'untrusted', UNKNOWN))}",
        f"Workspace: {status_value(info, 'workspace_access_mode', UNKNOWN, ('writable', 'read-only', UNKNOWN))}",
        f"Bridge/flows: {status_value(info, 'bridge_dir', NOT_CONFIGURED)} ({status_value(info, 'bridge_dir_access', UNKNOWN, ('writable', 'read-only', UNKNOWN))})",
        f"MCP-Light: {status_value(info, 'mcp_light', NOT_CONFIGURED, MCP_LIGHT_STATES)}",
    ]
    return "\n".join(lines)


def _ready_line(role):
    return f"\nStatus: {READY}\n\n{role}> "


class _IdleAccumulatingReader:
    """Read a byte stream and accumulate frames separated by input idle.

    A "frame" here is whatever bytes arrive at stdin until the stream goes
    idle (no new bytes for ``idle_seconds``) or reaches EOF. This is the
    minimum needed for raw tmux multiline paste to reach the harness as one
    complete submission: the paste lands as a chunk of bytes, embedded
    newlines are data, and the trailing idle window marks the submission
    Enter. A frame with no bytes is None (EOF / never-touched-input).

    The interface mirrors :class:`harness_allocator.transport.FrameReader`
    (``read_frame() -> RequestFrame | None``) so the persistent loop below
    is symmetric with the standalone's own terminal loop.
    """

    def __init__(self, stream, idle_seconds=IDLE_FLUSH_SECONDS):
        self._stream = stream
        self._idle = float(idle_seconds)
        self._buf = b""
        self._interrupted = False

    def clear(self):
        """Discard bytes accumulated for the interrupted READY submission."""
        self._buf = b""
        self._interrupted = False

    def read_frame(self):
        # Wait for at least one byte (or EOF) before doing anything else.
        while not self._buf:
            try:
                r, _, _ = select.select([self._stream], [], [], None)
            except InterruptedError:
                self._interrupted = True
                return IDLE_READ_INTERRUPTED
            if not r:
                if self._interrupted:
                    self._interrupted = False
                    return IDLE_READ_INTERRUPTED
                return None  # spurious wakeup
            try:
                chunk = self._stream.read1(65536)
            except OSError as exc:
                if getattr(exc, "errno", None) == errno.EINTR:
                    self._interrupted = True
                    return IDLE_READ_INTERRUPTED
                raise
            if not chunk:
                if self._interrupted:
                    self._interrupted = False
                    return IDLE_READ_INTERRUPTED
                return None  # EOF on an empty buffer
            self._buf = chunk

        # We already have bytes; drain until idle or EOF.
        # A bounded wall-clock cap protects the persistent loop against
        # stub streams that always satisfy ``select`` and always return the
        # same bytes: real terminals drain within milliseconds, so the cap
        # never fires in real use. It is a safety net, not a primary signal.
        import time as _time
        _drain_start = _time.monotonic()
        _drain_max_seconds = max(2.0, self._idle * 50)
        while True:
            if _time.monotonic() - _drain_start > _drain_max_seconds:
                break
            try:
                r, _, _ = select.select([self._stream], [], [], self._idle)
            except InterruptedError:
                self._interrupted = True
                return IDLE_READ_INTERRUPTED
            if not r:
                if self._interrupted:
                    self._interrupted = False
                    return IDLE_READ_INTERRUPTED
                break  # idle window expired -> emit frame
            try:
                more = self._stream.read1(65536)
            except OSError as exc:
                if getattr(exc, "errno", None) == errno.EINTR:
                    self._interrupted = True
                    return IDLE_READ_INTERRUPTED
                raise
            if not more:
                break  # EOF -> emit frame
            self._buf += more

        payload_bytes = self._buf
        self._buf = b""
        try:
            payload = payload_bytes.decode("utf-8")
        except UnicodeDecodeError:
            payload = payload_bytes.decode("utf-8", "replace")
        # The pane's tty is in canonical mode: an arrow key pressed while
        # typing (or while trying to scroll the transcript) is not handled
        # by anyone and lands in the line buffer as an escape sequence —
        # the Human saw a prompt line fill with ^[[A. Nothing in a role's
        # prompt is ever an ANSI control sequence, so strip them all.
        payload = _ANSI_CSI_RE.sub("", payload)
        # Strip a single trailing newline that the user pressed as Enter, so
        # the harness does not receive a phantom trailing blank line. The
        # submitted prompt is still "the whole paste": internal newlines are
        # preserved verbatim, only the final submission Enter is consumed.
        if payload.endswith("\n"):
            payload = payload[:-1]
        if payload.endswith("\r"):
            payload = payload[:-1]
        return RequestFrame(request_id=make_request_id(), payload=payload)


def execute(harness_key, role_config, task, cwd):
    """Run ``task`` through the harness and return the subprocess result.

    The command is built by the shared harness layer (which delegates the
    actual command shape to the standalone ``harness_allocator`` package)
    and then split back to argv so the task is passed as one argument, never
    re-parsed by a shell. The historical ``subprocess.run`` call site is
    preserved because the regression suite patches this module's subprocess
    reference directly; the argv list still arrives intact so the harness
    receives the complete task as a single argv element, preserving
    embedded newlines and producing exactly one harness invocation.
    """
    cmd = harness.build_task_invocation(harness_key, role_config, task)
    argv = shlex.split(cmd)
    return subprocess.run(argv, capture_output=True, text=True, cwd=cwd)


# ── runner adapter for the standalone's run_terminal loop ──────────


def _standalone_pkg():
    """Lazy import of the standalone package, via the harness module.

    Kept private — this is the seam-internal glue that lets the persistent
    loop delegate lifecycle visibility to the standalone without exposing
    the package import at module load (so the module remains importable in
    environments where the standalone is not yet on sys.path)."""
    return harness._standalone()


def _standalone_runner(*, role, harness, model_target, cwd, task,
                       request_id, heartbeat_interval, timeout, on_event,
                       cancel_event=None, cancel_grace_seconds=1.0):
    """Adapter invoked by ``harness_allocator.run_terminal``.

    Delegates to the standalone's ``execute`` so the heartbeat/threading
    logic in ``run_argv`` can fire ``on_event`` while the child process is
    alive (objective 6). The standalone's ``execute`` returns the
    ``{status, output, error, elapsed, pid, request_id, ...}`` dict shape
    that ``run_terminal`` writes after each turn.

    Note: this is the runner for the persistent loop. The historical
    ``ht.execute(...)`` boundary (which the regression suite patches via
    ``ht.subprocess.run``) is preserved separately for backward
    compatibility with the 41 original tests and the 11 seam tests added
    in handoff 002. The persistent loop bypasses ``ht.execute`` because
    ``ht.execute`` uses ``subprocess.run`` (blocking) — it cannot emit
    heartbeats. The standalone's ``execute`` uses ``subprocess.Popen``
    with a background drainer and a heartbeat loop, which is what the
    run_terminal loop relies on for lifecycle visibility.
    """
    ha = _standalone_pkg()
    return ha.execute(
        role=role,
        harness=harness,
        model_target=model_target,
        cwd=cwd,
        task=task,
        request_id=request_id,
        heartbeat_interval=heartbeat_interval,
        timeout=timeout,
        on_event=on_event,
        cancel_event=cancel_event,
        cancel_grace_seconds=cancel_grace_seconds,
    )


def main(argv=None):
    """The persistent terminal loop, delegating to the standalone's run_terminal.

    CLI shape unchanged from handoff 002 (``--role``, ``--harness``,
    ``--model``, ``--flow``, ``--cwd``). Adds one optional flag,
    ``--heartbeat-interval``, matching the standalone's flag and defaulting
    to 15.0s.

    The loop itself is the standalone's ``run_terminal``: it accepts this
    module's idle-bounded byte reader as the ``reader``, this process's
    stdout as the ``writer``, and the ``_standalone_runner`` adapter as the
    ``runner``. Identity / heartbeat / duplicate protection all flow from
    the standalone's run_terminal — there is exactly one lifecycle loop in
    the DPMtF-facing terminal now, not two.
    """
    parser = argparse.ArgumentParser(
        description="Persistent harness-neutral terminal for one-shot harnesses."
    )
    parser.add_argument("--role", required=True, help="Role key (e.g. super-deep-deep4)")
    parser.add_argument("--harness", required=True, help="Harness key (dsh/codex/...)")
    parser.add_argument("--model", default="", help="Model identity (alias)")
    parser.add_argument("--flow", default="", help="Flow key")
    parser.add_argument("--cwd", default=None, help="Working directory for invocations")
    parser.add_argument("--heartbeat-interval", type=float,
                        default=DEFAULT_HEARTBEAT_INTERVAL,
                        help="Seconds between heartbeats while a harness runs")
    args = parser.parse_args(argv)

    cwd = args.cwd or os.getcwd()

    ha = _standalone_pkg()
    reader = _IdleAccumulatingReader(sys.stdin.buffer)
    cancel_event = threading.Event()
    status_info = collect_runtime_status(harness_key=args.harness, cwd=cwd)
    status_info.update({
        "flow": args.flow,
        "model_target": args.model,
    })
    return ha.run_terminal(
        role=args.role,
        harness=args.harness,
        model_target=args.model,
        cwd=cwd,
        flow=args.flow,
        reader=reader,
        writer=sys.stdout,
        runner=_standalone_runner,
        heartbeat_interval=args.heartbeat_interval,
        status_info=status_info,
        cancel_event=cancel_event,
    )


if __name__ == "__main__":
    sys.exit(main())
