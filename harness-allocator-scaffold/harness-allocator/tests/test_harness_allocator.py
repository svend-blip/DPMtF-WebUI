"""Tests for the standalone ``harness_allocator`` package.

Covers the corrected architecture:

- Harness Allocator owns harness identity/command/execution only; the model is
  a passed-through, already-resolved ``model_target`` (no ``resolve_model``).
- Atomic framed task transport: ONE semantic task = EXACTLY ONE invocation, with
  20k+ character multi-line regression coverage.
- Request identity / payload verification metadata (request_id, chars, lines,
  sha256, harness, role, model target).
- Heartbeat / progress visibility (RUNNING + pid + elapsed, periodic HEARTBEAT,
  SUCCESS/ERROR + final duration, return to READY).
- READY lifecycle reliability across repeated turns and handled ERROR -> READY.
- Duplicate-request protection: a completed (request_id, payload sha256) is
  never executed twice — it reports DUPLICATE_REQUEST and returns to READY —
  unless the frame carries an explicit ``retry`` flag, which re-executes it.
"""

import hashlib
import io
import sys
from pathlib import Path

import pytest

# Import the package from the project root (sibling of tests/).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import harness_allocator as ha  # noqa: E402
from harness_allocator import (  # noqa: E402
    DUPLICATE_REQUEST,
    ERROR,
    SUCCESS,
    FrameReader,
    TransportError,
    build_dsh_invocation,
    build_launch_command,
    build_task_invocation,
    compute_identity,
    describe_missing,
    encode_request,
    execute,
    extract_frame,
    missing_env,
    model_target_identity,
    render_banner,
    resolve_harness,
    run_command,
    run_terminal,
)


class _FakeCfg:
    def get_codex_bin(self):
        return "codex"

    def get_dsh_bin(self):
        return "npx @deepseek-ai/dsh"

    def get_dsh_profile(self):
        return "headless"

    def get_dsh_patch_path(self):
        return "/tmp/dsh-v4-pro.patch.yml"


# ── identity resolution — model boundary ─────────────────────────────

def test_resolve_harness_explicit_and_no_silent_fallback():
    # No silent harness substitution: an absent/unknown harness yields "".
    assert resolve_harness({}) == ""
    assert resolve_harness("   ") == ""
    assert resolve_harness({"allocator_client": "codex"}) == "codex"
    assert resolve_harness({"harness": "dsh"}) == "dsh"
    assert resolve_harness("claude-code") == "claude-code"


def test_no_resolve_model_in_api():
    # The corrected boundary removes model resolution entirely.
    assert not hasattr(ha, "resolve_model")


def test_model_target_identity_is_passthrough_only():
    assert model_target_identity("deepseek-v4-pro") == "deepseek-v4-pro"
    assert model_target_identity({"model": "MiniMax-M3"}) == "MiniMax-M3"
    assert model_target_identity({"identity": "x"}) == "x"
    assert model_target_identity("") == ""
    assert model_target_identity(None) == ""


def test_harness_definition_has_no_model():
    d = ha.HarnessDefinition.from_role(
        {"role_key": "super-deep-deep4", "allocator_client": "dsh",
         "default_model_alias": "deepseek-v4-pro"}
    )
    assert d.role == "super-deep-deep4"
    assert d.harness == "dsh"
    assert not hasattr(d, "model")


# ── command building — model_target passthrough ──────────────────────

def test_dsh_invocation_carries_task():
    cmd = build_dsh_invocation(
        model_target="deepseek-v4-pro",
        task="Reply with exactly: OK",
        cfg=_FakeCfg(),
    )
    assert cmd == (
        "npx @deepseek-ai/dsh --profile headless "
        "--patch /tmp/dsh-v4-pro.patch.yml 'Reply with exactly: OK'"
    )


def test_dsh_invocation_does_not_render_model_target():
    # dsh model is pinned by profile/patch — the target must not be re-selected.
    cmd = build_dsh_invocation(model_target="some-other-model", cfg=_FakeCfg())
    assert "some-other-model" not in cmd


def test_dsh_invocation_without_patch():
    class Cfg(_FakeCfg):
        def get_dsh_patch_path(self):
            return ""

    cmd = build_dsh_invocation(model_target="x", cfg=Cfg())
    assert cmd == "npx @deepseek-ai/dsh --profile headless"


def test_codex_launch_command_uses_model_target():
    cmd = build_launch_command("codex", model_target="MiniMax-M3", cfg=_FakeCfg())
    assert cmd == "codex -m MiniMax-M3"


def test_codex_launch_command_without_model_target_has_no_flag():
    cmd = build_launch_command("codex", model_target="", cfg=_FakeCfg())
    assert cmd == "codex"


def test_dsh_launch_command_is_headless_not_tui():
    cmd = build_launch_command("dsh", model_target="deepseek-v4-pro", cfg=_FakeCfg())
    assert "--profile headless" in cmd
    assert "--profile tui" not in cmd


def test_task_invocation_rejects_resident_harnesses():
    for resident in ("codex", "claude-code", "opencode"):
        with pytest.raises(ValueError):
            build_task_invocation(resident, model_target="x", task="task", cfg=_FakeCfg())


def test_launch_command_rejects_unknown_harness():
    with pytest.raises(ValueError):
        build_launch_command("bogus", model_target="x", cfg=_FakeCfg())


# ── environment requirements ────────────────────────────────────────

def test_missing_env_fails_safely(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    assert missing_env("dsh") == ["DEEPSEEK_API_KEY"]
    assert missing_env("codex") == ["MINIMAX_API_KEY"]
    assert missing_env("claude-code") == []


def test_missing_env_message_names_without_leaking_values(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    msg = describe_missing("dsh", ["DEEPSEEK_API_KEY"])
    assert "DEEPSEEK_API_KEY" in msg
    assert "DeepSeek" in msg
    assert "=" not in msg


def test_present_env_reports_nothing_missing(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")
    monkeypatch.setenv("MINIMAX_API_KEY", "test")
    assert missing_env("dsh") == []
    assert missing_env("codex") == []


# ── execute() contract + operational metadata ───────────────────────

def _patch_popen(monkeypatch, proc):
    import harness_allocator.invoke as inv

    monkeypatch.setattr(inv.subprocess, "Popen", lambda *a, **k: proc)
    monkeypatch.setattr(inv, "_time", _FakeClock())


def test_execute_returns_contract_shape_and_metadata(monkeypatch):
    proc = _FakeProc(poll_results=[0], stdout="ok\n", stderr="")
    _patch_popen(monkeypatch, proc)
    r = execute(role="probe", harness="dsh", model_target="deepseek-v4-pro",
                cwd=".", task="echo ok", request_id="ha-001")

    assert set(r) >= {"status", "output", "error", "elapsed"}
    assert r["status"] == SUCCESS
    assert r["output"] == "ok\n"
    assert r["error"] == ""
    assert isinstance(r["elapsed"], float)
    assert r["request_id"] == "ha-001"
    assert r["harness"] == "dsh"
    assert r["role"] == "probe"
    assert r["model_target"] == "deepseek-v4-pro"
    assert r["payload_chars"] == len("echo ok")
    assert r["payload_lines"] == 1
    assert r["payload_sha256"] == hashlib.sha256(b"echo ok").hexdigest()


def test_execute_reports_error_for_non_native_harness():
    r = execute(role="probe", harness="codex", model_target="MiniMax-M3", cwd=".", task="x")
    assert r["status"] == ERROR
    assert "no one-shot" in r["error"]
    assert set(r) >= {"status", "output", "error", "elapsed"}


def test_execute_reports_nonzero_exit_as_error(monkeypatch):
    proc = _FakeProc(poll_results=[2], stdout="", stderr="boom")
    _patch_popen(monkeypatch, proc)
    r = execute(role="probe", harness="dsh", model_target="m", cwd=".", task="x")
    assert r["status"] == ERROR
    assert r["error"] == "boom"


def test_execute_does_not_resolve_model_from_role(monkeypatch):
    # A role carrying a model alias must NOT silently supply the model target.
    proc = _FakeProc(poll_results=[0], stdout="ok", stderr="")
    _patch_popen(monkeypatch, proc)
    r = execute(role={"allocator_client": "dsh", "default_model_alias": "deepseek-v4-pro"},
                cwd=".", task="echo ok")
    assert r["model_target"] == ""


def test_execute_returns_request_metadata_even_on_error(monkeypatch):
    proc = _FakeProc(poll_results=[1], stdout="", stderr="x")
    _patch_popen(monkeypatch, proc)
    r = execute(role="probe", harness="dsh", model_target="m", cwd=".", task="t", request_id="ha-9")
    assert r["status"] == ERROR
    assert r["request_id"] == "ha-9"
    assert r["payload_chars"] == 1


# ── atomic transport ────────────────────────────────────────────────

def test_20k_multiline_task_roundtrips_as_single_frame():
    payload = "## 1. Project Objective\n\n" + ("Implement the atomic dispatch layer.\n" * 700)
    payload += "\n```\n" + ("x" * 300) + "\n```\nSupervisor\n" + ("partial sentence\n" * 100)
    assert len(payload) >= 20000
    assert payload.count("\n") > 500  # clearly multi-line, with many embedded newlines

    encoded = encode_request("ha-001", payload)
    frame, rest = extract_frame(encoded)

    assert frame is not None
    assert rest == b""
    assert frame.request_id == "ha-001"
    assert frame.payload == payload  # verbatim, one frame, not fragmented

    ident = compute_identity("ha-001", payload)
    assert ident.chars == len(payload)
    assert ident.lines == len(payload.splitlines())
    assert ident.sha256 == hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_multiple_frames_reassemble_in_order():
    p1 = "first\nmulti\nline\ntask"
    p2 = "second task"
    stream = io.BytesIO(encode_request("ha-1", p1) + encode_request("ha-2", p2))
    reader = FrameReader(stream)
    f1 = reader.read_frame()
    f2 = reader.read_frame()
    assert (f1.request_id, f1.payload) == ("ha-1", p1)
    assert (f2.request_id, f2.payload) == ("ha-2", p2)
    assert reader.read_frame() is None  # EOF


def test_frame_reader_skips_blank_legacy_lines():
    stream = io.BytesIO(b"\n  \n" + encode_request("ha-3", "real task") + b"\n")
    reader = FrameReader(stream)
    frame = reader.read_frame()
    assert frame is not None
    assert frame.request_id == "ha-3"
    assert frame.payload == "real task"


def test_frame_reader_accepts_legacy_single_line():
    reader = FrameReader(io.BytesIO(b"just one line\n"))
    frame = reader.read_frame()
    assert frame is not None
    assert frame.payload == "just one line"
    assert frame.request_id.startswith("ha-")


def test_utf8_multibyte_payload_roundtrip():
    payload = "æøå ünïcödé ✓ " * 500 + "\nnewline inside\n"
    encoded = encode_request("ha-u", payload)
    frame, rest = extract_frame(encoded)
    assert rest == b""
    assert frame.payload == payload


def test_frame_retry_flag_roundtrip():
    encoded = encode_request("ha-r", "run me again", retry=True)
    frame, rest = extract_frame(encoded)
    assert rest == b""
    assert frame.request_id == "ha-r"
    assert frame.payload == "run me again"
    assert frame.retry is True


def test_frame_default_is_not_retry():
    frame, _ = extract_frame(encode_request("ha-r", "first run"))
    assert frame.retry is False


def test_unknown_frame_flag_raises():
    with pytest.raises(TransportError):
        extract_frame(b"HAR-FRAME ha-1 3 bogus\nabc")


def test_malformed_header_raises():
    with pytest.raises(TransportError):
        extract_frame(b"HAR-FRAME only-two-tokens\npayload")


def test_invalid_request_id_raises():
    with pytest.raises(TransportError):
        encode_request("bad id with spaces", "payload")


def test_incomplete_frame_returns_none():
    frame, rest = extract_frame(b"HAR-FRAME ha-1 10\nshort")
    assert frame is None
    assert rest == b"HAR-FRAME ha-1 10\nshort"


def test_frame_reader_reassembles_split_frame():
    encoded = encode_request("ha-s", "a\nb\nc")
    reader = FrameReader(_Chunked(encoded, chunk=3))
    frame = reader.read_frame()
    assert frame is not None
    assert frame.payload == "a\nb\nc"


class _Chunked:
    """Wraps bytes to yield at most ``chunk`` bytes per read, simulating a pipe."""

    def __init__(self, data, chunk):
        self._data = data
        self._chunk = chunk
        self._pos = 0

    def read(self, n=-1):
        if self._pos >= len(self._data):
            return b""
        end = min(len(self._data), self._pos + self._chunk)
        out = self._data[self._pos:end]
        self._pos = end
        return out


# ── heartbeat / progress visibility ─────────────────────────────────

class _FakeProc:
    def __init__(self, poll_results, stdout="ok\n", stderr=""):
        self._poll_results = list(poll_results)
        self.pid = 4242
        self.returncode = None
        self._stdout = stdout
        self._stderr = stderr
        self.killed = False

    def poll(self):
        if self._poll_results:
            self.returncode = self._poll_results.pop(0)
        return self.returncode

    def communicate(self):
        return self._stdout, self._stderr

    def kill(self):
        self.killed = True
        self.returncode = -9


class _FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_run_command_emits_running_heartbeat_success(monkeypatch):
    import harness_allocator.invoke as inv

    proc = _FakeProc(poll_results=[None, None, None, 0])
    clock = _FakeClock()
    monkeypatch.setattr(inv.subprocess, "Popen",
                        lambda *a, **k: proc)
    monkeypatch.setattr(inv, "_time", clock)

    events = []
    result = run_command(
        "echo ok", cwd=".", heartbeat_interval=0.15,
        on_event=lambda kind, p: events.append((kind, dict(p))),
        event_context={"request_id": "ha-001"},
    )

    kinds = [k for k, _ in events]
    assert kinds[0] == "RUNNING"
    assert events[0][1]["pid"] == 4242
    assert "HEARTBEAT" in kinds
    hb = next(p for k, p in events if k == "HEARTBEAT")
    assert hb["process_alive"] is True
    assert hb["request_id"] == "ha-001"
    assert result["status"] == SUCCESS
    assert result["output"] == "ok\n"
    assert result["pid"] == 4242
    assert result["elapsed"] >= 0


def test_run_command_reports_error_on_nonzero(monkeypatch):
    import harness_allocator.invoke as inv

    proc = _FakeProc(poll_results=[2], stdout="", stderr="boom")
    clock = _FakeClock()
    monkeypatch.setattr(inv.subprocess, "Popen", lambda *a, **k: proc)
    monkeypatch.setattr(inv, "_time", clock)

    result = run_command("bad", cwd=".", heartbeat_interval=10.0)
    assert result["status"] == ERROR
    assert result["error"] == "boom"
    assert result["pid"] == 4242


# ── READY lifecycle reliability ─────────────────────────────────────

def _fake_success_runner(**kwargs):
    return {
        "status": SUCCESS, "output": "done", "error": "",
        "elapsed": 0.5, "pid": 100, "request_id": kwargs.get("request_id"),
    }


def _fake_error_runner(**kwargs):
    return {
        "status": ERROR, "output": "", "error": "handled failure",
        "elapsed": 0.2, "pid": 101, "request_id": kwargs.get("request_id"),
    }


def _drive_terminal(payloads, runner):
    """Encode payloads as frames, run the terminal, return (output, calls)."""
    frames = [encode_request(f"ha-{i}", p) for i, p in enumerate(payloads)]
    reader = FrameReader(io.BytesIO(b"".join(frames)))
    writer = io.StringIO()
    calls = []

    def recording_runner(**kwargs):
        calls.append(kwargs)
        return runner(**kwargs)

    run_terminal(
        role="probe", harness="dsh", model_target="deepseek-v4-pro", cwd=".",
        reader=reader, writer=writer, runner=recording_runner,
    )
    return writer.getvalue(), calls


def test_terminal_repeated_turns_return_to_ready():
    out, calls = _drive_terminal(["task one", "task two"], _fake_success_runner)
    assert calls[0]["task"] == "task one"
    assert calls[1]["task"] == "task two"
    assert out.count("Status: READY") == 3  # initial + after each of 2 turns
    assert out.count("[SUCCESS]") == 2
    # Sequence: READY -> DISPATCH -> SUCCESS -> READY -> DISPATCH -> SUCCESS -> READY
    stripped = out.replace("\n", " ")
    assert "Status: READY" in stripped
    assert "[DISPATCH]" in stripped
    assert "[SUCCESS]" in stripped
    assert "[READY]" not in out  # the exact token [READY] is not emitted; READY is "Status: READY"


def test_terminal_handled_error_returns_to_ready():
    out, calls = _drive_terminal(["failing task"], _fake_error_runner)
    assert calls[0]["task"] == "failing task"
    assert "[ERROR]" in out
    assert "handled failure" in out
    assert out.count("Status: READY") == 2  # initial + after handled ERROR


def test_terminal_duplicate_request_returns_to_ready_without_reexecution():
    # The same completed identity (request_id + payload sha256) must NOT run
    # twice: the second frame reports DUPLICATE_REQUEST and returns to READY.
    frames = [encode_request("ha-dup", "same task"),
              encode_request("ha-dup", "same task")]
    reader = FrameReader(io.BytesIO(b"".join(frames)))
    writer = io.StringIO()
    calls = []

    def recording_runner(**kwargs):
        calls.append(kwargs)
        return _fake_success_runner(**kwargs)

    run_terminal(role="probe", harness="dsh", model_target="deepseek-v4-pro",
                 cwd=".", reader=reader, writer=writer, runner=recording_runner)
    out = writer.getvalue()

    assert len(calls) == 1                       # executed exactly once
    assert calls[0]["request_id"] == "ha-dup"
    assert "[DUPLICATE_REQUEST]" in out
    assert out.count("[SUCCESS]") == 1
    assert out.count("Status: READY") == 3       # initial + SUCCESS + duplicate
    # Duplicate returns to READY; the harness was never invoked a second time.
    assert "[DISPATCH]" in out and out.count("[DISPATCH]") == 1


def test_terminal_explicit_retry_reexecutes_duplicate():
    frames = [encode_request("ha-dup", "same task"),
              encode_request("ha-dup", "same task", retry=True)]
    reader = FrameReader(io.BytesIO(b"".join(frames)))
    writer = io.StringIO()
    calls = []

    def recording_runner(**kwargs):
        calls.append(kwargs)
        return _fake_success_runner(**kwargs)

    run_terminal(role="probe", harness="dsh", model_target="deepseek-v4-pro",
                 cwd=".", reader=reader, writer=writer, runner=recording_runner)
    out = writer.getvalue()

    assert len(calls) == 2                       # retry re-executes
    assert "[DUPLICATE_REQUEST]" not in out
    assert "retry: true" in out
    assert out.count("[SUCCESS]") == 2


def test_terminal_same_payload_different_request_id_is_not_duplicate():
    # Dedup is keyed on (request_id, payload sha256): a fresh id with the same
    # text is a new request, not a duplicate.
    frames = [encode_request("ha-a", "shared text"),
              encode_request("ha-b", "shared text")]
    reader = FrameReader(io.BytesIO(b"".join(frames)))
    writer = io.StringIO()
    calls = []

    def recording_runner(**kwargs):
        calls.append(kwargs)
        return _fake_success_runner(**kwargs)

    run_terminal(role="probe", harness="dsh", model_target="deepseek-v4-pro",
                 cwd=".", reader=reader, writer=writer, runner=recording_runner)
    out = writer.getvalue()

    assert len(calls) == 2
    assert "[DUPLICATE_REQUEST]" not in out


def test_terminal_multiline_payload_is_one_invocation():
    payload = "line one\nline two\nline three\n## fragment\nSupervisor\n"
    out, calls = _drive_terminal([payload], _fake_success_runner)
    # ONE semantic task -> EXACTLY ONE invocation, with the whole payload.
    assert len(calls) == 1
    assert calls[0]["task"] == payload
    assert "lines: " in out
    assert f"lines: {len(payload.splitlines())}" in out


def test_terminal_prints_request_identity_metadata():
    payload = "hello\nworld"
    out, _ = _drive_terminal([payload], _fake_success_runner)
    ident = compute_identity("ha-0", payload)
    assert f"request_id: ha-0" in out
    assert f"chars: {ident.chars}" in out
    assert f"lines: {ident.lines}" in out
    assert f"sha256: {ident.sha256}" in out
    assert "harness: DeepSeek Harness" in out
    assert "role: probe" in out
    assert "model_target: DeepSeek V4 Pro" in out


def test_terminal_prints_running_and_heartbeat_from_events():
    frames = [encode_request("ha-0", "task")]

    def emitting_runner(**kwargs):
        kwargs["on_event"]("RUNNING", {"pid": 7, "elapsed": 0.0, "process_alive": True})
        kwargs["on_event"]("HEARTBEAT", {"request_id": "ha-0", "elapsed": 1.5,
                                         "process_alive": True})
        return _fake_success_runner(**kwargs)

    reader = FrameReader(io.BytesIO(b"".join(frames)))
    writer = io.StringIO()
    run_terminal(role="probe", harness="dsh", model_target="deepseek-v4-pro",
                 cwd=".", reader=reader, writer=writer, runner=emitting_runner)
    out = writer.getvalue()
    assert "[RUNNING]" in out
    assert "DeepSeek Harness / DeepSeek V4 Pro" in out
    assert "pid: 7" in out
    assert "[HEARTBEAT]" in out
    assert "process_alive: true" in out


# ── terminal surface ────────────────────────────────────────────────

def test_render_banner_is_neutral():
    banner = render_banner("super-deep-deep4", "dsh", "deepseek-v4-pro", "/x",
                           flow="preferred_cloud_harness")
    assert "Harness Allocator Terminal" in banner
    assert "super-deep-deep4" in banner
    assert "DeepSeek Harness" in banner
    assert "DeepSeek V4 Pro" in banner
    assert "Model target:" in banner
    assert "headless / one-shot" in banner
    assert "preferred_cloud_harness" in banner
    assert "DPMtF" not in banner


def test_render_banner_without_flow_omits_flow_line():
    banner = render_banner("r", "dsh", "m", "/x")
    assert "Flow:" not in banner
