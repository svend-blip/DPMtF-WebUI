# Post-Dispatch Model-Stop Hang — Root Cause & Fix Implementation Plan

> **For agentic workers:** Execute tasks in order. Steps use checkbox (`- [ ]`) syntax for tracking. Do not skip verification steps.

**Goal:** Make the post-dispatch model stop (`ollama stop` / `model-allocator stop`) incapable of delaying or killing the signal path, and instrument it so we finally see WHAT hangs.

**Architecture:** BridgeV002's `dispatch.py` stops the predecessor role's model after injecting the callback prompt into the next role's tmux session. `ollama stop` is executed via `subprocess.run` with NO timeout, so a hang eats the `timeout 60` budget that roles wrap around the dispatch command, killing the process before trailing work. The fix: (1) instrument every synchronous stop with a hard timeout + structured JSONL logging, (2) move the chain-path stop into a detached background process fired only AFTER all trace writes and chain-advance work complete.

**Tech Stack:** Python 3.12 stdlib only (`subprocess`, `json`, `os`), SQLite, tmux, Ollama, pytest.

## Cold-Start Context

- Project: **DPMtF-WebUI** (the "Father" project), FastAPI app on port **9130**, SQLite DB at `databases/dpmtf.db`.
- Start app: `uvicorn app:app --host 0.0.0.0 --port 9130 --reload` (from repo root `/home/svend/DPMtF-WebUI`).
- Run tests: `python3 -m pytest -q` (pytest configured in `pytest.ini`, fixtures in `tests/conftest.py`).
- Governance lives in `docs/governance-templates-v2/`; CLAUDE.md summarizes it.
- Key file for this plan: `scripts/bridgeV002/dispatch.py` (2137 lines). Supporting: `scripts/bridgeV002/bridge_lib.py`, `scripts/bridgeV002/chain_watchdog.py`, `scripts/seed_bridge.py`, `config.py`.
- Roles run in persistent tmux sessions; `dispatch.py --signal-complete` injects the next role's prompt and then stops the previous role's model to free VRAM.
- The bridge working dir is `$DPMTF_BRIDGE_DIR` (set to `/home/svend/flows` in `.env`, loaded by `config.py` at import); the trace log is `<bridge_dir>/trace.log`.

## Global Constraints

- `python3 -m py_compile <file>` MUST pass on every touched `.py` file before completion.
- Parameterized SQL only (`?` placeholders) — never f-strings/concatenation in SQL values.
- No hardcoded `/home/svend/...` paths — use `config.py` getters or `PROJECT_ROOT` derivation.
- Schema changes ONLY via a new `scripts/db/00X_*.sql` migration + `python3 scripts/migrate.py` — NEVER by editing `init_db.py` schema. (This plan needs NO schema change.)
- No new pip dependencies.
- Frontend rules (no `innerHTML`, `lbl()` for user-facing text) — not applicable; this plan touches no frontend files.
- After changes: `curl -s http://localhost:9130/api/health` must return `{"status":"healthy"}` (app imports `dispatch.py`, so a broken dispatch module breaks the app).
- Git: **Only the Human may commit.** Stage files and STOP.

## Edge Cases a Weaker Model Would Miss

1. **The stop must run exactly once per dispatch even if chain-advance work raises.** Today the stop at "Step 9" runs before the symlink update and `_update_cycle_state`; if we simply move it to the end, an exception in the symlink code would skip the stop and leak VRAM. Fix: resolve stop parameters early, fire the stop in a `finally:` block guarded by a `stop_fired` flag.
2. **The detached process must not inherit the caller's stdin/tty.** `dispatch.py` is often executed inside a role's tmux pane (the `chain_advancement` block). A child inheriting stdin could read from the pane or die with the pane. Use `subprocess.Popen(..., stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)` and redirect stdout/stderr to a log file.
3. **Allocator vs direct-Ollama path.** `get_effective_model_source(role_key, step_key, flow_key, db_path)` (bridge_lib.py, line 420) decides: `("model_allocator", alias)` → `model-allocator stop --alias <alias>`; otherwise if the role's `model_type == "ollama"` → `ollama stop <ollama_model>`. Both paths must go through the same new helper.
4. **Warm-after-stop race.** `signal_complete` warms the NEXT role's Ollama model (line 1371–1372, `warm_ollama_model`) BEFORE injection, and stops the PREVIOUS role's model after. When two adjacent roles use the SAME model, the detached stop would unload the model just warmed for the next role. Guard by model name: skip the stop when the predecessor's model equals the successor's warmed model (`protect_model` parameter).
5. **Logging must never use plain `print()` to stdout for the new structured events.** `dispatch.py` stdout is consumed line-by-line by `chain_watchdog.nudge()` (it logs the first 8 stdout lines) and captured by roles running the chain_advancement command. New diagnostics go to `logs/dispatch-stop.log` (JSONL) and warnings to `sys.stderr`. Existing human-readable success prints may stay on stdout (they already exist).
6. **`signal_send`'s stop is DIFFERENT and must stay synchronous.** In `signal_send` (Step 4, lines 1916–1926) the TARGET role's model is stopped *before* being re-warmed, to clear stale context. Detaching it would race the warm-up. It gets the timeout+logging instrumentation only.
7. **Keep the early trace write (Step 8b).** The `log(...)` call at lines 1379–1390 exists precisely because the hang used to kill the process before trailing trace writes. It stays as belt-and-braces even after the stop is detached — do not remove it; update its comment.
8. **Do not remove `timeout 60` from the chain_advancement content template until validated.** The template lives in the DB (`bridge_convention_rules.content_template` for `rule_key='json_output'`) and in `scripts/seed_bridge.py` (line ~372–387). It is the roles' safety net; relax the wording only after `logs/dispatch-stop.log` shows the dispatch process itself no longer blocks (Task 6).
9. **`unload_ollama_model` currently has NO timeout** (`subprocess.run(["ollama", "stop", model_name], capture_output=True, text=True)` at lines 559–562) — this is the actual hang site. `_run_allocator_stop` already has `timeout=45` (line 261). Instrument BOTH so the log shows which one hangs and for how long.
10. **`datetime`/`timezone` are already imported** at the top of dispatch.py (`from datetime import datetime, timezone`), as are `json`, `os`, `subprocess`, `sys`, `time`. Do not add duplicate imports.

---

### Task 1: Instrument synchronous stops (capture WHAT hangs)

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py` — add `_stop_log_path()` + `_log_stop_event()` immediately after the `_run_allocator_stop` function (which starts at line ~261); replace `unload_ollama_model` (lines ~550–575); extend `_run_allocator_stop`.

**Interfaces:**
- Produces: `logs/dispatch-stop.log` — one JSON object per line: `{"ts", "kind", "argv", "duration_s", "returncode", "timed_out", ...}`.
- `unload_ollama_model(model_name, timeout=90) -> bool` (signature gains an optional `timeout` param; all existing callers pass only `model_name` and keep working).

- [ ] Step 1: Add the log helpers to `dispatch.py` (place them after `_run_allocator_stop`, before `wait_session_ready`):

```python
def _stop_log_path():
    """Absolute path to the structured model-stop log (JSON Lines)."""
    import config as _cfg
    log_dir = os.path.join(PROJECT_ROOT, _cfg.get_log_dir())
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "dispatch-stop.log")


def _log_stop_event(event):
    """Append one JSON line to logs/dispatch-stop.log. Never raises.

    Structured diagnostics go to the log file (and warnings to stderr) —
    NEVER stdout: chain_watchdog.nudge() and roles running the
    chain_advancement command consume dispatch stdout line-by-line.
    """
    event = dict(event)
    event["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with open(_stop_log_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"  WARNING: could not write dispatch-stop.log: {exc}",
              file=sys.stderr)
```

- [ ] Step 2: Replace the whole body of `unload_ollama_model` (currently lines 550–575, the version with NO timeout) with:

```python
def unload_ollama_model(model_name, timeout=90):
    """Stop an Ollama model to free VRAM and clear context.

    Hard timeout (post-dispatch-hang instrumentation): `ollama stop` has
    been observed to block indefinitely (flows 069/070 workarounds). Every
    call is logged to logs/dispatch-stop.log with argv/duration/returncode
    so the hang signature is finally observable.

    Returns True on success or if model was already unloaded.
    Returns False on timeout or actual failure.
    """
    if not model_name:
        return True  # nothing to unload — not an error

    argv = ["ollama", "stop", model_name]
    started = time.monotonic()
    timed_out = False
    returncode = None
    stderr_text = ""
    try:
        result = subprocess.run(argv, capture_output=True, text=True,
                                timeout=timeout)
        returncode = result.returncode
        stderr_text = (result.stderr or "").strip()
    except subprocess.TimeoutExpired:
        timed_out = True
    duration = round(time.monotonic() - started, 2)
    _log_stop_event({
        "kind": "ollama_stop_sync",
        "argv": argv,
        "duration_s": duration,
        "returncode": returncode,
        "timed_out": timed_out,
    })
    if timed_out:
        print(f"  WARNING: 'ollama stop {model_name}' timed out "
              f"after {timeout}s", file=sys.stderr)
        return False
    if returncode == 0:
        print(f"  Stopped Ollama model '{model_name}' ({duration}s)")
        return True
    stderr_lower = stderr_text.lower()
    if "not loaded" in stderr_lower or "not found" in stderr_lower:
        print(f"  Model '{model_name}' not currently loaded — VRAM already free")
        return True
    print(f"  WARNING: Failed to stop '{model_name}': {stderr_text}",
          file=sys.stderr)
    return False
```

- [ ] Step 3: Instrument `_run_allocator_stop` (lines ~261–286). Keep its logic; add duration + JSONL logging. Replace the function with:

```python
def _run_allocator_stop(model_alias, timeout=45):
    """Stop an allocator-managed model without hanging.

    Runs `model-allocator stop --alias <model_alias>` with an outer timeout.
    Returns True on success/already-unloaded, False on real failure.
    Every call is logged to logs/dispatch-stop.log (hang instrumentation).
    """
    stop_cmd = [_model_allocator_path(), "stop", "--alias", model_alias]
    started = time.monotonic()
    timed_out = False
    returncode = None
    error_text = ""
    try:
        result = subprocess.run(
            stop_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        returncode = result.returncode
        error_text = (result.stderr or "").strip()
    except subprocess.TimeoutExpired:
        timed_out = True
    except Exception as exc:  # binary missing, permission error, ...
        error_text = str(exc)
    duration = round(time.monotonic() - started, 2)
    _log_stop_event({
        "kind": "allocator_stop_sync",
        "argv": stop_cmd,
        "duration_s": duration,
        "returncode": returncode,
        "timed_out": timed_out,
        "error": error_text or None,
    })
    if timed_out:
        print(f"  WARNING: model-allocator stop timed out for "
              f"'{model_alias}'", file=sys.stderr)
        return False
    if returncode == 0:
        print(f"  Stopped allocator model '{model_alias}' ({duration}s)")
        return True
    print(f"  WARNING: model-allocator stop failed for '{model_alias}': "
          f"{error_text or returncode}", file=sys.stderr)
    return False
```

NOTE: `_log_stop_event` is defined AFTER `_run_allocator_stop` in file order — that is fine (Python resolves names at call time), but if you prefer strict definition-before-use, place both helpers directly BEFORE `_run_allocator_stop` instead.

- [ ] Step 4: Run `python3 -m py_compile scripts/bridgeV002/dispatch.py` — expected output: nothing (exit 0).
- [ ] Step 5: Smoke-check the logger writes:
  `python3 -c "import sys; sys.path.insert(0,'scripts/bridgeV002'); import dispatch; dispatch._log_stop_event({'kind':'smoke'}); print(open(dispatch._stop_log_path()).readlines()[-1])"`
  Expected: a JSON line containing `"kind": "smoke"` and a `"ts"` field.

---

### Task 2: Add the detached stop helpers (TDD)

**Files:**
- Create: `/home/svend/DPMtF-WebUI/tests/test_dispatch_model_stop.py`
- Modify: `/home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py` — add `build_model_stop_argv()` and `schedule_detached_model_stop()` after `unload_ollama_model`.

**Interfaces:**
- `build_model_stop_argv(model_source, model_alias, model_type, ollama_model, protect_model=None) -> list[str] | None` — pure decision function.
- `schedule_detached_model_stop(model_source, model_alias, model_type, ollama_model, protect_model=None, context="") -> int | None` — spawns the detached process, returns PID or None. Never raises.

- [ ] Step 1 (TDD — write the failing test first): create `tests/test_dispatch_model_stop.py`:

```python
"""Unit tests for the detached post-dispatch model-stop helpers.

No tmux, no ollama: subprocess is monkeypatched. The helpers live in
scripts/bridgeV002/dispatch.py (import-safe: app.py imports it too).
"""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import dispatch  # noqa: E402


# ── build_model_stop_argv (pure) ─────────────────────────────────────

def test_argv_direct_ollama():
    argv = dispatch.build_model_stop_argv(
        None, None, "ollama", "qwen3-coder:30b-96k")
    assert argv == ["timeout", "120", "ollama", "stop", "qwen3-coder:30b-96k"]


def test_argv_allocator(monkeypatch):
    monkeypatch.setattr(dispatch, "_model_allocator_path",
                        lambda: "/opt/ma/scripts/model-allocator")
    argv = dispatch.build_model_stop_argv(
        "model_allocator", "imple01-local", "ollama", "ignored-model")
    assert argv == ["timeout", "120", "/opt/ma/scripts/model-allocator",
                    "stop", "--alias", "imple01-local"]


def test_argv_protect_same_ollama_model():
    """Warm-after-stop guard: never stop the model the next role just warmed."""
    argv = dispatch.build_model_stop_argv(
        None, None, "ollama", "qwen3.6:35b-a3b-64k",
        protect_model="qwen3.6:35b-a3b-64k")
    assert argv is None


def test_argv_protect_same_alias(monkeypatch):
    monkeypatch.setattr(dispatch, "_model_allocator_path", lambda: "ma")
    argv = dispatch.build_model_stop_argv(
        "model_allocator", "shared-alias", "ollama", "x",
        protect_model="shared-alias")
    assert argv is None


def test_argv_nothing_to_stop():
    assert dispatch.build_model_stop_argv(None, None, "cloud", "") is None
    assert dispatch.build_model_stop_argv(None, None, "ollama", None) is None


# ── schedule_detached_model_stop (spawn semantics) ───────────────────

class _FakeProc:
    pid = 4242


def test_schedule_detached_spawn_kwargs(monkeypatch, tmp_path):
    captured = {}

    def fake_popen(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return _FakeProc()

    monkeypatch.setattr(dispatch.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(dispatch, "_stop_log_path",
                        lambda: str(tmp_path / "dispatch-stop.log"))

    pid = dispatch.schedule_detached_model_stop(
        None, None, "ollama", "qwen-test:7b", context="unit-test")

    assert pid == 4242
    assert captured["argv"] == ["timeout", "120", "ollama", "stop",
                                "qwen-test:7b"]
    kw = captured["kwargs"]
    assert kw["stdin"] is subprocess.DEVNULL
    assert kw["start_new_session"] is True
    assert kw["close_fds"] is True
    # Structured events were appended (spawn event mentions the pid)
    log_text = (tmp_path / "dispatch-stop.log").read_text(encoding="utf-8")
    assert '"stop_detached"' in log_text
    assert "4242" in log_text


def test_schedule_detached_skip_is_logged(monkeypatch, tmp_path):
    monkeypatch.setattr(dispatch, "_stop_log_path",
                        lambda: str(tmp_path / "dispatch-stop.log"))
    pid = dispatch.schedule_detached_model_stop(
        None, None, "ollama", "same-model", protect_model="same-model",
        context="unit-test")
    assert pid is None
    log_text = (tmp_path / "dispatch-stop.log").read_text(encoding="utf-8")
    assert '"stop_skipped"' in log_text


def test_schedule_detached_never_raises(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise OSError("spawn failed")

    monkeypatch.setattr(dispatch.subprocess, "Popen", boom)
    monkeypatch.setattr(dispatch, "_stop_log_path",
                        lambda: str(tmp_path / "dispatch-stop.log"))
    pid = dispatch.schedule_detached_model_stop(
        None, None, "ollama", "qwen-test:7b", context="unit-test")
    assert pid is None
    log_text = (tmp_path / "dispatch-stop.log").read_text(encoding="utf-8")
    assert '"stop_spawn_failed"' in log_text
```

- [ ] Step 2: Run `python3 -m pytest tests/test_dispatch_model_stop.py -q` — expected: FAILED / AttributeError (functions do not exist yet).
- [ ] Step 3: Add the implementation to `dispatch.py`, directly after `unload_ollama_model`:

```python
def build_model_stop_argv(model_source, model_alias, model_type,
                          ollama_model, protect_model=None):
    """Decide the stop command for a predecessor role's model.

    Pure decision helper (unit-tested, no side effects). Returns an argv
    list, or None when no stop must run.

    `protect_model` guards the warm-after-stop race: when the predecessor's
    model (or allocator alias) equals the model just warmed for the NEXT
    role, stopping it would immediately unload the successor's model.
    """
    if model_source == "model_allocator" and model_alias:
        if protect_model and model_alias == protect_model:
            return None
        return ["timeout", "120", _model_allocator_path(), "stop",
                "--alias", model_alias]
    if model_type == "ollama" and ollama_model:
        if protect_model and ollama_model == protect_model:
            return None
        return ["timeout", "120", "ollama", "stop", ollama_model]
    return None


def schedule_detached_model_stop(model_source, model_alias, model_type,
                                 ollama_model, protect_model=None,
                                 context=""):
    """Fire-and-forget model stop that can NEVER delay the signal path.

    Runs the stop in a detached background process: its own session
    (start_new_session=True — no tmux/tty inheritance), stdin closed,
    stdout/stderr appended to logs/dispatch-stop.log, wrapped in
    `timeout 120` so a hung ollama-stop cannot linger forever.

    The dispatch process does not wait for it, so the hang that used to
    eat the roles' outer `timeout 60` budget can no longer do so.

    Returns the child PID, or None when nothing was scheduled.
    Never raises.
    """
    argv = build_model_stop_argv(model_source, model_alias, model_type,
                                 ollama_model, protect_model=protect_model)
    if argv is None:
        _log_stop_event({
            "kind": "stop_skipped", "context": context,
            "model_source": model_source, "model_alias": model_alias,
            "ollama_model": ollama_model, "protect_model": protect_model,
        })
        return None
    try:
        with open(_stop_log_path(), "ab") as fh:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=fh,
                stderr=fh,
                start_new_session=True,
                close_fds=True,
            )
        _log_stop_event({"kind": "stop_detached", "argv": argv,
                         "pid": proc.pid, "context": context})
        print(f"  Scheduled detached model stop (pid {proc.pid}): "
              f"{' '.join(argv)}")
        return proc.pid
    except OSError as exc:
        _log_stop_event({"kind": "stop_spawn_failed", "argv": argv,
                         "error": str(exc), "context": context})
        print(f"  WARNING: could not schedule model stop: {exc}",
              file=sys.stderr)
        return None
```

- [ ] Step 4: Run `python3 -m py_compile scripts/bridgeV002/dispatch.py` — exit 0.
- [ ] Step 5: Run `python3 -m pytest tests/test_dispatch_model_stop.py -q` — expected: all tests pass (e.g. `8 passed`).

---

### Task 3: Rewire `signal_complete` — stop AFTER all chain-advance work, exactly once

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py`, function `signal_complete` (currently lines ~1143–1433). Anchor by code content, not line number.

**Interfaces:** No signature change. Behavior change: Step 9's synchronous stop is replaced by a detached stop fired in a `finally:` after injection, early trace write, symlink update, and `_update_cycle_state`.

- [ ] Step 1: In `signal_complete`, find this block (currently just before `if to_role.get("model_type") == "ollama"` warm-up, i.e. the region spanning "Step 8: Inject callback prompt" through "Step 11"):

```python
    if to_role.get("model_type") == "ollama" and to_role.get("ollama_model"):
        warm_ollama_model(to_role["ollama_model"])

    # Step 8: Inject callback prompt into to_role's tmux session
    inject_prompt(tmux_session, prompt_text,
                  enter_command=to_role.get("enter_command", "default"))
    time.sleep(0.5)
```

and the later Step 9 block:

```python
    # Step 9: Post-dispatch - stop from_role's Ollama model (VRAM cleanup)
    try:
        from_role_data = load_role_from_db(payload["from_role"],
                                           db_path=_db_path())
        from_source, from_alias = get_effective_model_source(
            from_role_data["role_key"],
            step_key=current_step.get("step_key"),
            flow_key=flow_key,
            db_path=_db_path(),
        )
        if from_source == "model_allocator" and from_alias:
            _run_allocator_stop(from_alias)
        elif from_role_data.get("model_type") == "ollama" and from_role_data.get("ollama_model"):
            unload_ollama_model(from_role_data["ollama_model"])
    except ValueError:
        pass  # from_role not in DB - not an ollama role, skip
```

- [ ] Step 2: Replace the region from `if to_role.get("model_type") == "ollama" and to_role.get("ollama_model"):` (the warm-up) down to and including the final `return True` of `signal_complete` with:

```python
    # Resolve the predecessor's stop parameters BEFORE the chain-advance
    # work so the stop is attempted exactly once even if a later step
    # raises. The successor's warmed model is passed as protect_model
    # (warm-after-stop guard: adjacent roles sharing a model must not have
    # it unloaded right after warm-up).
    warmed_model = None
    if to_role.get("model_type") == "ollama" and to_role.get("ollama_model"):
        warmed_model = to_role["ollama_model"]
        warm_ollama_model(warmed_model)

    stop_params = None
    try:
        from_role_data = load_role_from_db(payload["from_role"],
                                           db_path=_db_path())
        from_source, from_alias = get_effective_model_source(
            from_role_data["role_key"],
            step_key=current_step.get("step_key"),
            flow_key=flow_key,
            db_path=_db_path(),
        )
        stop_params = {
            "model_source": from_source,
            "model_alias": from_alias,
            "model_type": from_role_data.get("model_type", ""),
            "ollama_model": from_role_data.get("ollama_model", ""),
        }
    except ValueError:
        stop_params = None  # from_role not in DB — nothing to stop

    stop_fired = False
    try:
        # Step 8: Inject callback prompt into to_role's tmux session
        inject_prompt(tmux_session, prompt_text,
                      enter_command=to_role.get("enter_command", "default"))
        time.sleep(0.5)

        # Step 8b: Log the completion event IMMEDIATELY after injection.
        # Belt-and-braces, kept deliberately even though the model stop is
        # now detached (Step 9): the roles' chain_advancement command wraps
        # dispatch.py in `timeout 60`, and ANY unexpected slow path after
        # injection must not leave a delivered signal invisible to the
        # watchdog's duplicate-nudge guard (flow 069 double-nudge, flow 070
        # missing review->sim line).
        log(
            f"{payload['from_role']}->{payload['to_role']}",
            handoff_id,
            "signal_complete",
            f"Callback dispatched to {tmux_session} (DB-driven)",
        )

        # Step 10: Update symlink
        deliverable_dir = payload["deliverable_dir"]
        if os.path.isabs(deliverable_dir):
            link_dir = deliverable_dir
        else:
            link_dir = os.path.join(bridge_dir, deliverable_dir)

        link_path = os.path.join(link_dir, "current.md")
        try:
            if os.path.islink(link_path) or os.path.exists(link_path):
                os.unlink(link_path)
        except FileNotFoundError:
            pass
        os.symlink(payload["deliverable_file"], link_path)

        # Step 11: Completion event already logged at Step 8b.
        print(f"  Callback injected into '{tmux_session}'")
        print(f"  Symlink updated in {link_dir}")
        print(f"  Logged signal_complete for handoff #{handoff_id}")

        # Update cycle state for Architect cold-start
        _update_cycle_state(handoff_id, flow_key, payload["to_role"])
    finally:
        # Step 9 (moved): detached post-dispatch model stop — fired AFTER
        # all trace writes and chain-advance work, in a background process
        # that can never delay or kill this dispatch. Exactly once, even
        # when the try-block raised.
        if stop_params and not stop_fired:
            stop_fired = True
            schedule_detached_model_stop(
                protect_model=warmed_model,
                context=f"signal_complete:{flow_key}:{handoff_id}",
                **stop_params,
            )

    return True
```

- [ ] Step 3: Run `python3 -m py_compile scripts/bridgeV002/dispatch.py` — exit 0.
- [ ] Step 4: Verify no orphaned duplicate remains: `grep -n "Step 9: Post-dispatch" scripts/bridgeV002/dispatch.py` must show NO hit inside `signal_complete` (the old synchronous block is gone). `grep -c "schedule_detached_model_stop" scripts/bridgeV002/dispatch.py` — expected at least 2 (definition + this call).

---

### Task 4: Rewire the remaining chain-path stops (`run_flow_step_db`, `signal_escalation`, `signal_answer`)

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py`

`signal_send` is intentionally NOT converted (edge case 6): its stop clears the TARGET's context before warm-up and must complete first; it now has the Task 1 timeout.

- [ ] Step 1: In `run_flow_step_db` (block currently at lines ~1038–1050) replace:

```python
    # Post-dispatch: offload predecessor's model to free VRAM
    from_role = load_role_from_db(payload["from_role"],
                                  db_path=_db_path())
    from_source, from_alias = get_effective_model_source(
        from_role["role_key"],
        step_key=target_step.get("step_key"),
        flow_key=flow_key,
        db_path=_db_path(),
    )
    if from_source == "model_allocator" and from_alias:
        _run_allocator_stop(from_alias)
    elif from_role.get("model_type") == "ollama" and from_role.get("ollama_model"):
        unload_ollama_model(from_role["ollama_model"])
```

with:

```python
    # Post-dispatch: offload predecessor's model to free VRAM — detached,
    # so it can never block the dispatch (post-dispatch-hang fix).
    from_role = load_role_from_db(payload["from_role"],
                                  db_path=_db_path())
    from_source, from_alias = get_effective_model_source(
        from_role["role_key"],
        step_key=target_step.get("step_key"),
        flow_key=flow_key,
        db_path=_db_path(),
    )
    schedule_detached_model_stop(
        from_source, from_alias,
        from_role.get("model_type", ""), from_role.get("ollama_model", ""),
        protect_model=(to_role.get("ollama_model")
                       if to_role.get("model_type") == "ollama" else None),
        context=f"run_flow_step_db:{flow_key}:{handoff_id}",
    )
```

- [ ] Step 2: In `signal_escalation` (Step 7 block, lines ~1563–1575) replace the body of the `try:` that stops the from-role model:

```python
    # Step 7: Post-dispatch — stop from_role's Ollama model (VRAM cleanup)
    try:
        from_source, from_alias = get_effective_model_source(
            from_role_key,
            flow_key=flow_key,
            db_path=_db_path(),
        )
        schedule_detached_model_stop(
            from_source, from_alias,
            from_role_data.get("model_type", ""),
            from_role_data.get("ollama_model", ""),
            context=f"signal_escalation:{flow_key}:{handoff_id}",
        )
    except Exception:
        pass  # Not an ollama role or model already stopped
```

- [ ] Step 3: Apply the identical replacement in `signal_answer` (Step 5 block, lines ~1707–1719), with `context=f"signal_answer:{flow_key}:{handoff_id}"`.
- [ ] Step 4: Run `python3 -m py_compile scripts/bridgeV002/dispatch.py` — exit 0.
- [ ] Step 5: Run the full test suite: `python3 -m pytest -q` — no new failures versus the pre-change baseline (note: `tests/test_migrate.py` has 2 pre-existing failures from missing 003/004 expectations — unrelated to this plan; do not "fix" them here).
- [ ] Step 6: Confirm the app still imports dispatch cleanly: `python3 -c "import app; print('APP_OK')"` — expected: `APP_OK` (plus logging init lines on stderr).

---

### Task 5: Watchdog interplay — trust the new fast exit, keep the safety net

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/bridgeV002/chain_watchdog.py` — `nudge()` (lines ~183–204), comment only + log line.

The watchdog wraps `dispatch.py --signal-complete` in `subprocess.run(..., timeout=120)` and treats `TimeoutExpired` as "known post-dispatch hang → signal likely delivered". With the stop detached, a timeout is no longer expected; but the safety net stays until validated. Only the wording/observability changes.

- [ ] Step 1: In `chain_watchdog.py`, replace the `except subprocess.TimeoutExpired:` handler in `nudge()`:

```python
    except subprocess.TimeoutExpired:
        log("  dispatch timed out after 120s — UNEXPECTED since the "
            "post-dispatch model stop is now detached "
            "(see logs/dispatch-stop.log); signal may still have been "
            "delivered, continuing")
        return True
```

- [ ] Step 2: `python3 -m py_compile scripts/bridgeV002/chain_watchdog.py` — exit 0.

---

### Task 6: Validation gate, then relax the `timeout 60` wording in the chain_advancement template

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/seed_bridge.py` (the `_JSON_OUTPUT_CONTENT_TEMPLATE` string, `<chain_advancement>` block, lines ~372–387)
- Data: `bridge_convention_rules.content_template WHERE rule_key='json_output'` in `databases/dpmtf.db` (updated by re-running `python3 scripts/seed_bridge.py`, which performs an unconditional parameterized UPDATE of this template — verified at the bottom of seed_bridge.py).

**Do NOT execute this task until the validation evidence exists.** This is a deliberate two-phase rollout.

- [ ] Step 1 (VALIDATION GATE — Human/operator step): after at least 2 full trade-cockpit runs (started via `scripts/trade-cronjob.sh`, per project convention), inspect the instrumentation log:
  `python3 -c "import json,sys; [print(l.strip()) for l in open('logs/dispatch-stop.log')]"`
  Pass criteria: every `ollama_stop_sync` / `allocator_stop_sync` event has `"timed_out": false`, and all `stop_detached` events exist for the chain steps. If any sync stop timed out, STOP — the hang is in `signal_send`'s synchronous path and needs separate diagnosis using the captured argv/duration.
- [ ] Step 2: In `scripts/seed_bridge.py`, inside `_JSON_OUTPUT_CONTENT_TEMPLATE`, replace the paragraph:

```
{flow_key}, {next_role}, and {flow_run_id} are already resolved for you —
substitute nothing. The `timeout 60` is required because dispatch.py's
post-dispatch step can hang; the signal lands before the timeout kills it.
```

with:

```
{flow_key}, {next_role}, and {flow_run_id} are already resolved for you —
substitute nothing. The `timeout 60` is a defensive outer bound only:
dispatch.py's post-dispatch model stop runs detached and no longer blocks,
so the command normally finishes in a few seconds. If it IS killed by the
timeout, the signal has already been logged (early trace write) — do not
re-run it.
```

Keep the `timeout 60` prefix in the command itself — it stays as belt-and-braces.
- [ ] Step 3: `python3 -m py_compile scripts/seed_bridge.py` — exit 0. Then propagate to the DB: `python3 scripts/seed_bridge.py` (idempotent; performs the parameterized UPDATE of `json_output`).
- [ ] Step 4: Verify the DB text: `sqlite3 databases/dpmtf.db "SELECT content_template LIKE '%defensive outer bound%' FROM bridge_convention_rules WHERE rule_key='json_output';"` — expected: `1`.

---

### Task 7: Stage and stop

- [ ] Step 1: Review scope: `git diff --stat` — expected files only: `scripts/bridgeV002/dispatch.py`, `scripts/bridgeV002/chain_watchdog.py`, `scripts/seed_bridge.py` (Task 6 only), `tests/test_dispatch_model_stop.py` (new), `databases/dpmtf.db` (Task 6 only).
- [ ] Step 2: Run the full validation set: `python3 -m pytest -q`, `python3 -m py_compile app.py`, `curl -s http://localhost:9130/api/health` → `{"status":"healthy"}` (if the app is running).
- [ ] Step 3: Stage the files with `git add scripts/bridgeV002/dispatch.py scripts/bridgeV002/chain_watchdog.py tests/test_dispatch_model_stop.py` (plus `scripts/seed_bridge.py databases/dpmtf.db` if Task 6 was executed) and STOP — await Human commit approval. Suggested commit message: `[hardening] detached post-dispatch model stop + hang instrumentation (dispatch-stop.log)`.

## Acceptance Criteria

1. `python3 -m py_compile scripts/bridgeV002/dispatch.py scripts/bridgeV002/chain_watchdog.py scripts/seed_bridge.py` — exits 0, no output.
2. `python3 -m pytest tests/test_dispatch_model_stop.py -q` — all tests pass (`8 passed`).
3. `grep -n "timeout=timeout" scripts/bridgeV002/dispatch.py | head -3` — shows the timeout is wired into `unload_ollama_model`'s `subprocess.run`; and `grep -n "start_new_session=True" scripts/bridgeV002/dispatch.py` shows the detached spawn.
4. `grep -c "schedule_detached_model_stop" scripts/bridgeV002/dispatch.py` — ≥ 5 (1 definition + calls in signal_complete, run_flow_step_db, signal_escalation, signal_answer).
5. `python3 -c "import sys; sys.path.insert(0,'scripts/bridgeV002'); import dispatch; dispatch._log_stop_event({'kind':'accept'})" && tail -1 logs/dispatch-stop.log` — prints a JSON line with `"kind": "accept"`.
6. After the next real flow run (Human-triggered via `scripts/trade-cronjob.sh`): `grep -c stop_detached logs/dispatch-stop.log` ≥ 1, and the run's signal-complete commands finish well inside their `timeout 60` (observable in `~/.bridge`-equivalent `$DPMTF_BRIDGE_DIR/trace.log`: every `signal_complete` line present, no watchdog "timed out" lines in `logs/chain-watchdog.log`).
7. `curl -s http://localhost:9130/api/health` returns `{"status":"healthy"}`.
