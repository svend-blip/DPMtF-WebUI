"""HarnessTerminal — a persistent, harness-neutral terminal for one-shot harnesses.

Runs inside a role's tmux session. It prints a role/harness/model banner, then
loops: read one atomic framed request from stdin, execute it through the
resolved harness (one-shot), show operational progress, and return to READY.

Atomic dispatch: a request is a length-delimited frame (``transport``), so ONE
complete semantic task = EXACTLY ONE harness invocation and embedded newlines
never define the request boundary. Progress is operational metadata only
(request id, pid, elapsed, process-alive) — never chain-of-thought.

Harness-neutral by construction: it knows only a resolved harness key plus a
role/harness/model-target identity — never any flow, verdict, sequencing or
governance semantics. The caller composes the task and sends it here; this
process only runs it through the allocator's ``execute``.

Duplicate-request protection: once a request completes, its
``(request_id, payload_sha256)`` identity is recorded for this terminal
session. A later frame with the same completed identity is NOT executed again;
it reports ``[DUPLICATE_REQUEST]`` and returns to READY. The only way to
re-run a completed identity is an explicit ``retry`` frame
(``encode_request(..., retry=True)``), which re-executes and re-records it.
"""

from __future__ import annotations

import argparse
import os
import sys

from .definition import model_target_identity
from .invoke import execute
from .status import DUPLICATE_REQUEST, ERROR, READY, RUNNING, SUCCESS
from .transport import FrameReader, compute_identity

#: Human labels for known harnesses — display only, never routing.
HARNESS_LABELS = {
    "dsh": "DeepSeek Harness",
    "codex": "Codex",
    "claude-code": "Claude Code",
    "opencode": "OpenCode",
}

#: Human labels for known model targets — display only, never routing.
MODEL_LABELS = {
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "MiniMax-M3": "MiniMax M3",
    "sonnet5": "Claude Sonnet 5",
}


def _label(labels, key):
    return labels.get(key, key)


def _fmt_elapsed(seconds):
    return f"{float(seconds):.2f}s"


def render_banner(role, harness_key, model_target, cwd, flow=""):
    """The startup identity block, before the first READY prompt."""
    lines = [
        "Harness Allocator Terminal",
        "",
    ]
    if flow:
        lines.append(f"Flow:    {flow}")
    lines += [
        f"Role:    {role}",
        f"Harness: {_label(HARNESS_LABELS, harness_key)}",
        f"Model target: {_label(MODEL_LABELS, model_target_identity(model_target))}",
        f"Mode:    headless / one-shot",
        f"Cwd:     {cwd}",
    ]
    return "\n".join(lines)


def _ready_line(role):
    return f"\nStatus: {READY}\n\n{role}> "


def run_terminal(*, role, harness, model_target, cwd, flow="", reader, writer,
                 runner=None, heartbeat_interval=15.0, timeout=None) -> int:
    """The persistent READY -> request -> execute -> READY loop.

    ``reader`` is a :class:`~harness_allocator.transport.FrameReader` over a byte
    stream; ``writer`` is a text stream with ``write``/``flush``. ``runner``
    defaults to :func:`~harness_allocator.invoke.execute` and is injectable for
    tests. Returns 0 on clean EOF shutdown.

    A completed request identity (``request_id`` + payload ``sha256``) is
    recorded after each execution and never executed twice: a repeat without an
    explicit ``retry`` flag reports ``DUPLICATE_REQUEST`` and returns to READY.
    """
    if runner is None:
        runner = execute

    harness_label = _label(HARNESS_LABELS, harness)
    model_label = _label(MODEL_LABELS, model_target_identity(model_target))
    completed = set()  # (request_id, payload_sha256) identities already run

    def on_event(kind, payload):
        if kind == RUNNING:
            writer.write(f"\n[{RUNNING}] {harness_label} / {model_label}\n")
            writer.write(f"pid: {payload.get('pid')}\n")
            writer.write(f"elapsed: {_fmt_elapsed(payload.get('elapsed', 0.0))}\n")
        elif kind == "HEARTBEAT":
            writer.write("[HEARTBEAT]\n")
            writer.write(f"request_id: {payload.get('request_id')}\n")
            writer.write(f"process_alive: {str(payload.get('process_alive', True)).lower()}\n")
            writer.write(f"elapsed: {_fmt_elapsed(payload.get('elapsed', 0.0))}\n")
        writer.flush()

    writer.write(render_banner(role, harness, model_target, cwd, flow))
    writer.write(_ready_line(role))
    writer.flush()

    while True:
        frame = reader.read_frame()
        if frame is None:
            # EOF: the tmux session was closed — clean shutdown.
            break

        task = frame.payload
        if not task.strip():
            # Blank request (e.g. a stray Enter) — stay ready without re-printing
            # the whole READY block.
            writer.write(f"{role}> ")
            writer.flush()
            continue

        ident = compute_identity(frame.request_id, task)
        key = (ident.request_id, ident.sha256)

        if key in completed and not frame.retry:
            # A completed identity must not execute twice. Report the duplicate
            # and return to READY without invoking the harness.
            writer.write("\n[DUPLICATE_REQUEST]\n")
            writer.write(f"request_id: {ident.request_id}\n")
            writer.write(f"sha256: {ident.sha256}\n")
            writer.write(_ready_line(role))
            writer.flush()
            continue

        writer.write("\n[DISPATCH]\n")
        writer.write(f"request_id: {ident.request_id}\n")
        writer.write(f"chars: {ident.chars}\n")
        writer.write(f"lines: {ident.lines}\n")
        writer.write(f"sha256: {ident.sha256}\n")
        writer.write(f"harness: {harness_label}\n")
        writer.write(f"role: {role}\n")
        writer.write(f"model_target: {model_label}\n")
        if frame.retry:
            writer.write("retry: true\n")
        writer.flush()

        result = runner(
            role=role,
            harness=harness,
            model_target=model_target,
            cwd=cwd,
            task=task,
            request_id=frame.request_id,
            heartbeat_interval=heartbeat_interval,
            timeout=timeout,
            on_event=on_event,
        )
        completed.add(key)

        status = result["status"]
        writer.write(f"\n[{status}]\n")
        writer.write(f"request_id: {frame.request_id}\n")
        writer.write(f"duration: {_fmt_elapsed(result.get('elapsed', 0.0))}\n")
        out = (result.get("output") or "").strip()
        err = (result.get("error") or "").strip()
        if out:
            writer.write(out + "\n")
        if err:
            writer.write(f"[stderr] {err}\n")
        writer.write(_ready_line(role))
        writer.flush()

    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Persistent harness-neutral terminal for one-shot harnesses."
    )
    parser.add_argument("--role", required=True, help="Role key (display identity)")
    parser.add_argument("--harness", required=True, help="Harness key (dsh/codex/...)")
    parser.add_argument("--model-target", default="", help="Already-resolved model target (identity)")
    parser.add_argument("--flow", default="", help="Optional opaque context label")
    parser.add_argument("--cwd", default=None, help="Working directory for invocations")
    parser.add_argument("--heartbeat-interval", type=float, default=15.0,
                        help="Seconds between heartbeats while a harness runs")
    args = parser.parse_args(argv)

    cwd = args.cwd or os.getcwd()
    reader = FrameReader(sys.stdin.buffer)
    return run_terminal(
        role=args.role,
        harness=args.harness,
        model_target=args.model_target,
        cwd=cwd,
        flow=args.flow,
        reader=reader,
        writer=sys.stdout,
        heartbeat_interval=args.heartbeat_interval,
    )


if __name__ == "__main__":
    sys.exit(main())
