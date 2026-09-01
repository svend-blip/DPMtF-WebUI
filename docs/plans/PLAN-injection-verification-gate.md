# Tmux Injection Verification Gate Implementation Plan

> **For agentic workers:** Execute tasks in order. Steps use checkbox (`- [ ]`) syntax for tracking. Do not skip verification steps.

**Goal:** Make tmux prompt-injection verification a provable hard gate (structured failure + non-zero exit + trace event) and deduplicate the pane-inspection logic shared by `dispatch.py` and `chain_watchdog.py`.

**Architecture:** A new shared module `scripts/bridgeV002/tmux_pane.py` owns the activity-marker constants, pane-tail capture, and a PURE decision function (`classify_pane_state`) that is unit-testable without tmux. `dispatch.py`'s `verify_injection_submitted` becomes hash-aware and returns a structured result; `inject_prompt` gains a bounded retry ladder (2× Enter resend → 1× paste-buffer re-injection → hard fail). Signal functions propagate failure, and `main()` finally stops swallowing failures with `sys.exit(0)`.

**Tech Stack:** Python 3.12 stdlib (`subprocess`, `hashlib`), tmux (`capture-pane`, `send-keys`, `paste-buffer`), pytest.

## Cold-Start Context

- Project: **DPMtF-WebUI** ("Father"), FastAPI app on port **9130**, SQLite DB at `databases/dpmtf.db`.
- Start app: `uvicorn app:app --host 0.0.0.0 --port 9130 --reload` from `/home/svend/DPMtF-WebUI`.
- Run tests: `python3 -m pytest -q` (config: `pytest.ini`; fixtures: `tests/conftest.py`).
- Governance: `docs/governance-templates-v2/`.
- Key files: `scripts/bridgeV002/dispatch.py` (2137 lines — injection at `inject_via_send_keys` ~322, `inject_via_paste_buffer` ~383, `inject_prompt` ~466, markers `_ACTIVITY_MARKERS`/`_PASTE_STUCK_MARKER` ~500–501, `_pane_tail` ~504, `verify_injection_submitted` ~514) and `scripts/bridgeV002/chain_watchdog.py` (duplicate marker tuple `ACTIVITY_MARKERS` at line 84, `pane_active` at 145–153).
- Roles run in persistent tmux sessions (Claude Code, OpenCode, or a plain REPL). `dispatch.py` injects prompts via tmux buffers and verifies acceptance heuristically. Known failure mode: prompt pasted but never submitted (flows 062/064), or `dispatch.py` prints "injected into <session>" without the prompt actually landing (memory: "injection not reliable").

## Global Constraints

- `python3 -m py_compile <file>` MUST pass on every touched `.py` file.
- Parameterized SQL only (`?` placeholders) — this plan runs no SQL.
- No hardcoded `/home/svend/...` paths — use `config.py` getters / relative derivation.
- Schema changes ONLY via new `scripts/db/00X_*.sql` + `python3 scripts/migrate.py` (none needed here).
- No new pip dependencies.
- Frontend rules (no `innerHTML`, `lbl()`) — not applicable, no frontend files touched.
- `bash -n scripts/trade-cronjob.sh` must pass after the shell edit; the script keeps `set -euo pipefail`.
- `curl -s http://localhost:9130/api/health` returns `{"status":"healthy"}` after changes (app.py imports dispatch.py).
- Git: **Only the Human may commit.** Stage and STOP.

## Edge Cases a Weaker Model Would Miss

1. **The two marker tuples MUST stay in lockstep.** `_ACTIVITY_MARKERS` in dispatch.py:500 and `ACTIVITY_MARKERS` in chain_watchdog.py:84 are today identical (`("esc interrupt", "esc to interrupt", "↓")`) but only by discipline. Any drift makes the watchdog and the verifier disagree about "role is working". That is WHY extraction into one module is the core of this plan, not a style nicety.
2. **Long prompts are NOT visible verbatim in the pane.** Claude Code renders large multi-line pastes as a placeholder chip ("Pasted text #1 +N lines"), and the pane tail only shows the last ~25 lines. Therefore prompt-tail matching is a *positive* signal only — its ABSENCE must never be treated as failure. The primary signals remain: activity markers, stuck-paste marker, pane-content change (hash).
3. **A stray Enter can submit an empty second message.** After a successfully submitted prompt, blindly resending Enter posts an empty message that derails small local models. The verifier must only resend Enter when the pane shows `stuck_paste` or is `unchanged` vs. the pre-injection hash — never when it is `active` or has visibly changed (`pending`).
4. **Roles use different submit keys.** `bridge_roles.enter_command` supports `default`/`c-m`/`c-j`/`c-d` (see `inject_via_send_keys`, dispatch.py:322–374). Resends must use the role's key, not always `Enter` (the current code always resends `Enter` — a latent bug for c-m/c-j/c-d roles).
5. **Different clients show different activity markers.** Claude Code shows "esc to interrupt"; OpenCode shows "esc interrupt"; the `↓` token-download counter covers model-pull phases. A plain `ollama run` REPL shows NONE of these — for such sessions verification can only rely on pane-content change. `classify_pane_state` therefore treats "changed but no marker" as `pending` (not failure).
6. **`main()` currently exits 0 unconditionally.** Every signal function returns `True`/`False`, but `main()` (dispatch.py:2078–2133) calls `sys.exit(0)` regardless. Fixing exit codes is REQUIRED for the gate to be visible to the watchdog/cron — but it changes caller behavior:
   - `scripts/trade-cronjob.sh` runs `set -euo pipefail` and calls dispatch directly at step [6/6]; a non-zero exit would abort the cron script BEFORE the watchdog starts. The call site must be wrapped (Task 6).
   - `chain_watchdog.nudge()` checks `result.returncode == 0` — it becomes honest for free.
   - The roles' `chain_advancement` command wraps dispatch in `timeout 60`; exit 124 means killed-by-timeout, distinct from our new exit 3.
7. **Exit-code semantics must be documented** (they become an interface): `0` = signal delivered and injection confirmed; `1` = usage/config error (already used for missing `--db-flow`/`--to-role`); `3` = signal NOT confirmed (session dead, deliverable missing, validation failed, or injection unconfirmed after retries); `124` = killed by the callers' outer `timeout 60`.
8. **The paste-buffer fallback may duplicate text.** If the first injection actually landed in the input box but unsubmitted (and 2 Enter resends did not help), re-injecting appends the prompt a second time before submitting. Accepted trade-off (one message containing the prompt twice is recoverable; a never-submitted prompt is a stalled chain) — documented in code.
9. **`inject_via_send_keys` despite its name uses `load-buffer`+`paste-buffer` too** (dispatch.py:322–380) — tmux `paste-buffer` passes text verbatim, so prompts containing `;`, `$`, quotes, or send-keys key-names are already safe in transit. The characters-that-tmux-interprets risk exists only for the SUBMIT key sequence, which sends `""` + `C-m`-style keys — no prompt text travels through `send-keys`. Do not "fix" injection to use raw send-keys for text; that would INTRODUCE the interpretation problem.
10. **`_PASTE_STUCK_MARKER` handling must be preserved** ("paste again to expand") — it is the one directly observed stuck state (flows 062/064).
11. **`verify_injection_submitted` is also called for OpenCode's combined soft-clear prompt** — the verified text must be the text actually pasted (`combined`), not the original `text` argument, or the prompt-tail token would be wrong.

---

### Task 1: Create `tmux_pane.py` with a pure, testable decision core (TDD)

**Files:**
- Create: `/home/svend/DPMtF-WebUI/tests/test_tmux_pane.py`
- Create: `/home/svend/DPMtF-WebUI/scripts/bridgeV002/tmux_pane.py`

**Interfaces (produced):**
```python
ACTIVITY_MARKERS: tuple[str, ...]          # ("esc interrupt", "esc to interrupt", "↓")
PASTE_STUCK_MARKER: str                    # "paste again to expand"
RESEND_KEYS: dict[str, str]                # enter_command -> tmux key name
pane_tail(session: str, lines: int = 25) -> str        # lowercased tail, "" on error
pane_hash(session: str, lines: int = 25) -> str        # sha256 of pane_tail
is_pane_active(session: str) -> bool
prompt_tail_token(prompt_text: str, length: int = 80) -> str
classify_pane_state(tail: str, before_hash: str, prompt_token: str = "") -> str
    # returns 'active' | 'stuck_paste' | 'unchanged' | 'pending'
```

- [ ] Step 1 (failing tests first): create `tests/test_tmux_pane.py`:

```python
"""Unit tests for the shared tmux pane inspection module.

Pure logic only — no tmux. Pane text goes in, a decision comes out.
"""

import hashlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import tmux_pane  # noqa: E402


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_markers_are_the_canonical_tuple():
    assert tmux_pane.ACTIVITY_MARKERS == ("esc interrupt",
                                          "esc to interrupt", "↓")
    assert tmux_pane.PASTE_STUCK_MARKER == "paste again to expand"


def test_classify_active_claude_code():
    tail = "some output\n... esc to interrupt\n"
    assert tmux_pane.classify_pane_state(tail, _h("idle")) == "active"


def test_classify_active_opencode():
    tail = "working  esc interrupt"
    assert tmux_pane.classify_pane_state(tail, _h("idle")) == "active"


def test_classify_stuck_paste_wins_over_everything():
    tail = "[paste again to expand]  esc to interrupt"
    assert tmux_pane.classify_pane_state(tail, _h("idle")) == "stuck_paste"


def test_classify_unchanged_pane():
    tail = "idle footer  · ← for agents"
    assert tmux_pane.classify_pane_state(tail, _h(tail)) == "unchanged"


def test_classify_pending_changed_but_no_marker():
    """Plain ollama REPL / model-loading phase: pane changed, no marker."""
    before = _h("old content")
    tail = "new content without any marker"
    assert tmux_pane.classify_pane_state(tail, before) == "pending"


def test_idle_footer_glyphs_do_not_count_as_activity():
    """The idle footer contains generic glyphs; only genuine in-progress
    markers count (deliberately narrow marker tuple)."""
    tail = "  · ← for agents   tokens: 1234"
    assert tmux_pane.classify_pane_state(tail, _h("something else")) == "pending"


def test_prompt_tail_token_bounded_and_normalized():
    prompt = "Line one\n  Line   two\t\nRead and execute /some/path/42-handoff.md"
    token = tmux_pane.prompt_tail_token(prompt, length=30)
    assert token == "d execute /some/path/42-handoff.md"[-30:]
    assert len(token) <= 30
    assert "\n" not in token and "\t" not in token
    assert token == token.lower()


def test_prompt_tail_token_empty_prompt():
    assert tmux_pane.prompt_tail_token("") == ""


def test_resend_keys_cover_all_enter_commands():
    assert tmux_pane.RESEND_KEYS == {
        "default": "Enter", "c-m": "C-m", "c-j": "C-j", "c-d": "C-d",
    }
```

- [ ] Step 2: Run `python3 -m pytest tests/test_tmux_pane.py -q` — expected: `ModuleNotFoundError: No module named 'tmux_pane'` (red).
- [ ] Step 3: Create `scripts/bridgeV002/tmux_pane.py`:

```python
#!/usr/bin/env python3
"""Shared tmux pane inspection for BridgeV002.

Single source of truth for pane activity markers, pane-tail capture, and
the injection-state decision logic. dispatch.py and chain_watchdog.py BOTH
import from here — the marker tuples were previously duplicated in the two
files (dispatch.py ~500, chain_watchdog.py ~84) and had to stay in lockstep
by discipline alone.

Design rule: everything that decides is PURE (text in, decision out) so it
is unit-testable without tmux; everything that touches tmux is a thin
subprocess wrapper.
"""

import hashlib
import subprocess

# Pane markers that indicate the client actually accepted/started the
# prompt. Deliberately narrow: idle footers contain generic glyphs
# ("· ← for agents", token totals), so only genuine in-progress signals
# count — the interrupt hint (Claude Code: "esc to interrupt", OpenCode:
# "esc interrupt") and the live download counter ("↓").
ACTIVITY_MARKERS = ("esc interrupt", "esc to interrupt", "↓")

# Claude Code's stuck-paste state (observed flows 062/064): the paste
# landed in the input box but was never submitted.
PASTE_STUCK_MARKER = "paste again to expand"

# Per-role submit keys (bridge_roles.enter_command -> tmux key name).
# Resends during verification MUST use the role's key, not always Enter.
RESEND_KEYS = {
    "default": "Enter",
    "c-m": "C-m",
    "c-j": "C-j",
    "c-d": "C-d",
}


def pane_tail(session, lines=25):
    """Last `lines` lines of the session's active pane, lowercased.

    Returns "" when the session does not exist or capture fails —
    callers treat "" as 'nothing observable'.
    """
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", "=" + session, "-p"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return ""
    return "\n".join(result.stdout.splitlines()[-lines:]).lower()


def pane_hash(session, lines=25):
    """Stable digest of the pane tail — detects 'pane content changed'."""
    return hashlib.sha256(pane_tail(session, lines).encode("utf-8")).hexdigest()


def is_pane_active(session):
    """True when the pane shows a genuine in-progress marker."""
    tail = pane_tail(session)
    return any(m in tail for m in ACTIVITY_MARKERS)


def prompt_tail_token(prompt_text, length=80):
    """Bounded distinctive substring of a prompt for pane matching.

    Last `length` chars with ALL whitespace collapsed to single spaces,
    lowercased. Positive signal only: long prompts are truncated in the
    pane and Claude Code renders multi-line pastes as a placeholder chip,
    so absence of this token is NOT proof of a failed injection.
    """
    collapsed = " ".join(prompt_text.split()).lower()
    return collapsed[-length:]


def classify_pane_state(tail, before_hash, prompt_token=""):
    """PURE decision: what state is the pane in after an injection?

    Args:
        tail: current pane tail (already lowercased, e.g. from pane_tail()).
        before_hash: pane_hash() captured BEFORE the injection.
        prompt_token: optional prompt_tail_token() of the injected text.

    Returns one of:
        'active'      — client accepted the prompt and is working
        'stuck_paste' — paste sitting unsubmitted ("paste again to expand")
        'unchanged'   — pane identical to before injection (likely lost)
        'pending'     — pane changed but no activity marker yet (model
                        loading, plain-REPL session, or echo of the prompt
                        awaiting processing) — wait, do NOT resend keys
    """
    if PASTE_STUCK_MARKER in tail:
        return "stuck_paste"
    if any(m in tail for m in ACTIVITY_MARKERS):
        return "active"
    after_hash = hashlib.sha256(tail.encode("utf-8")).hexdigest()
    if after_hash == before_hash:
        return "unchanged"
    # prompt_token visible in an otherwise idle-looking pane means the text
    # arrived; classification stays 'pending' (submitted-but-quiet or
    # unsubmitted-without-hint are indistinguishable here — the caller's
    # retry ladder resolves it without risking a stray Enter on 'pending').
    return "pending"
```

- [ ] Step 4: Run `python3 -m pytest tests/test_tmux_pane.py -q` — expected: all pass (`11 passed`).
- [ ] Step 5: `python3 -m py_compile scripts/bridgeV002/tmux_pane.py` — exit 0.

---

### Task 2: Point `chain_watchdog.py` at the shared module

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/bridgeV002/chain_watchdog.py`

- [ ] Step 1: Add the import (after `import config` at line 29 — the directory is already on `sys.path` via line 27's `sys.path.insert(0, str(Path(__file__).parent))`):

```python
from tmux_pane import ACTIVITY_MARKERS, is_pane_active  # shared pane logic
```

- [ ] Step 2: Delete the duplicate constant at line 84:

```python
ACTIVITY_MARKERS = ("esc interrupt", "esc to interrupt", "↓")
```

(the name now comes from the import; keep the surrounding `_WD`-derived constants untouched).
- [ ] Step 3: Replace `pane_active` (lines 145–153):

```python
def pane_active(session):
    return is_pane_active(session)
```

Keep the wrapper (call sites in `check_once` use `pane_active(role)`), do not rename call sites.
- [ ] Step 4: `python3 -m py_compile scripts/bridgeV002/chain_watchdog.py` — exit 0.
- [ ] Step 5: Guard against drift ever returning: `grep -n '"esc interrupt"' scripts/bridgeV002/*.py` — after Task 3 the ONLY hit must be in `tmux_pane.py`.

---

### Task 3: Rewire `dispatch.py` to the shared module and strengthen `verify_injection_submitted`

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py`

**Interfaces (changed):**
- `verify_injection_submitted(session_name, prompt_text="", before_hash="", enter_command="default", attempts=4, settle_seconds=8) -> dict` — returns `{"submitted": bool, "state": str, "attempts": int, "resends": int}`. Never raises.
- `inject_prompt(session_name, text, enter_command="default") -> dict` — same result shape, plus `"fallback_used": bool`.

- [ ] Step 1: Add the import near the other local imports (after the `from bridge_lib import (...)` block, dispatch.py ~line 34; `sys.path.insert(0, str(Path(__file__).parent))` at line 21 already makes it importable):

```python
import tmux_pane
```

- [ ] Step 2: Delete the now-duplicated block at lines ~496–511 (`_ACTIVITY_MARKERS`, `_PASTE_STUCK_MARKER`, `_pane_tail` and their comment). Then fix any straggling references: `grep -n "_ACTIVITY_MARKERS\|_PASTE_STUCK_MARKER\|_pane_tail" scripts/bridgeV002/dispatch.py` must return ONLY hits inside the new code you add below (i.e. none, after Step 3).
- [ ] Step 3: Replace `verify_injection_submitted` (currently lines ~514–547) with:

```python
def verify_injection_submitted(session_name, prompt_text="", before_hash="",
                               enter_command="default", attempts=4,
                               settle_seconds=8):
    """Verify the injected prompt was actually SUBMITTED, not left sitting
    in the client's input buffer (observed: 'paste again to expand',
    silent unsubmitted pastes — flows 062/064 required manual Enter).

    Hash-aware hard gate: the pane hash captured BEFORE injection lets us
    distinguish 'pane changed, model quiet' (pending — wait, no resend)
    from 'pane identical to pre-injection' (unchanged — resend submit key).
    Resend budget: the role's submit key at most 2 times. The paste-buffer
    re-injection fallback is the CALLER's job (inject_prompt).

    Returns a structured result and never raises:
        {"submitted": bool, "state": str, "attempts": int, "resends": int}
    """
    resend_key = tmux_pane.RESEND_KEYS.get(enter_command, "Enter")
    prompt_token = tmux_pane.prompt_tail_token(prompt_text) if prompt_text else ""
    resends = 0
    state = "pending"
    for attempt in range(1, attempts + 1):
        time.sleep(settle_seconds)
        tail = tmux_pane.pane_tail(session_name)
        state = tmux_pane.classify_pane_state(tail, before_hash, prompt_token)
        if state == "active":
            print(f"  Injection verify: '{session_name}' active "
                  f"(attempt {attempt})")
            return {"submitted": True, "state": state,
                    "attempts": attempt, "resends": resends}
        if state in ("stuck_paste", "unchanged") and resends < 2:
            print(f"  Injection verify: {state} in '{session_name}' "
                  f"(attempt {attempt}) — resending {resend_key}")
            subprocess.run(["tmux", "send-keys", "-t", "=" + session_name,
                            resend_key], capture_output=True)
            resends += 1
        else:
            # 'pending' (pane changed, no marker yet): a resend here could
            # submit an empty second message — wait instead.
            print(f"  Injection verify: {state} in '{session_name}' "
                  f"(attempt {attempt}) — waiting")
    tail = tmux_pane.pane_tail(session_name)
    state = tmux_pane.classify_pane_state(tail, before_hash, prompt_token)
    submitted = state == "active"
    print(f"  Injection verify: final state for '{session_name}': "
          f"{state if submitted else state + ' — UNCONFIRMED'}")
    return {"submitted": submitted, "state": state,
            "attempts": attempts, "resends": resends}
```

- [ ] Step 4: Replace `inject_prompt` (currently lines ~466–493) with:

```python
def inject_prompt(session_name, text, enter_command="default"):
    """Detect tool type, inject, and VERIFY — with a bounded retry ladder.

    Ladder: initial injection -> verify (which may resend the submit key
    up to 2 times) -> ONE paste-buffer re-injection -> verify again ->
    structured failure. The re-injection may duplicate the prompt text in
    the input box if the first paste silently landed; that trade-off is
    accepted (a doubled prompt in one message is recoverable, a stalled
    chain is not).

    Returns the verification dict:
        {"submitted", "state", "attempts", "resends", "fallback_used"}
    """
    tool = get_pane_command(session_name)
    # Observability: prompt size per dispatch (context-tuning data point).
    print(f"  Injection: {len(text)} chars (~{len(text) // 4} est. tokens) "
          f"-> '{session_name}' ({tool})")
    if tool == "opencode":
        soft_clear = (
            "Start a new logical task now. "
            "Ignore earlier conversation context unless this prompt explicitly references it. "
            "Do not continue previous plans, assumptions, file edits, or task state. "
            "Treat this message as the authoritative task."
        )
        injected_text = f"{soft_clear}\n\n{text}"
        before_hash = tmux_pane.pane_hash(session_name)
        inject_via_paste_buffer(session_name, injected_text, enter_command)
    else:
        injected_text = text
        before_hash = tmux_pane.pane_hash(session_name)
        inject_via_send_keys(session_name, injected_text, enter_command)

    result = verify_injection_submitted(
        session_name, prompt_text=injected_text, before_hash=before_hash,
        enter_command=enter_command)
    result["fallback_used"] = False
    if not result["submitted"]:
        print(f"  Injection verify: retrying '{session_name}' via "
              f"paste-buffer fallback", file=sys.stderr)
        before_hash = tmux_pane.pane_hash(session_name)
        inject_via_paste_buffer(session_name, injected_text, enter_command)
        result = verify_injection_submitted(
            session_name, prompt_text=injected_text,
            before_hash=before_hash, enter_command=enter_command,
            attempts=2)
        result["fallback_used"] = True
    return result
```

- [ ] Step 5: `python3 -m py_compile scripts/bridgeV002/dispatch.py` — exit 0.
- [ ] Step 6: Add verifier decision tests to `tests/test_tmux_pane.py` — a new test class exercising `verify_injection_submitted` with tmux mocked out:

```python
def test_verify_injection_submitted_sequences(monkeypatch):
    """Drive verify_injection_submitted through pane-state sequences."""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))
    import dispatch

    monkeypatch.setattr(dispatch.time, "sleep", lambda s: None)
    sent_keys = []
    monkeypatch.setattr(
        dispatch.subprocess, "run",
        lambda argv, **kw: sent_keys.append(argv) or
        type("R", (), {"returncode": 0, "stdout": ""})())

    # Sequence: stuck paste twice, then active.
    tails = iter(["[paste again to expand]",
                  "[paste again to expand]",
                  "thinking… esc to interrupt",
                  "thinking… esc to interrupt"])
    monkeypatch.setattr(dispatch.tmux_pane, "pane_tail",
                        lambda session, lines=25: next(tails))
    res = dispatch.verify_injection_submitted("sess", prompt_text="p",
                                              before_hash="x")
    assert res["submitted"] is True
    assert res["resends"] == 2
    # Resends used the role's submit key (default -> Enter)
    assert all(argv[:2] == ["tmux", "send-keys"] for argv in sent_keys)


def test_verify_injection_gives_structured_failure(monkeypatch):
    import dispatch

    monkeypatch.setattr(dispatch.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        dispatch.subprocess, "run",
        lambda argv, **kw: type("R", (), {"returncode": 0, "stdout": ""})())
    # Pane never changes, never shows activity.
    monkeypatch.setattr(dispatch.tmux_pane, "pane_tail",
                        lambda session, lines=25: "idle idle idle")
    before = hashlib.sha256(b"idle idle idle").hexdigest()
    res = dispatch.verify_injection_submitted("sess", prompt_text="p",
                                              before_hash=before,
                                              attempts=3)
    assert res["submitted"] is False
    assert res["state"] == "unchanged"
    assert res["resends"] == 2  # budget respected, not 3
```

- [ ] Step 7: Run `python3 -m pytest tests/test_tmux_pane.py -q` — all pass (`13 passed`).

---

### Task 4: Make the signal paths a hard gate (trace event + `return False`)

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py` — the five `inject_prompt(...)` call sites (currently lines ~1034, ~1375, ~1559, ~1703, ~1999).

- [ ] Step 1: `signal_send` (call site ~1999). Replace:

```python
    # Step 8: Inject prompt into target role's tmux session
    inject_prompt(tmux_session, prompt_text,
                  enter_command=to_role_data.get("enter_command", "default"))
    time.sleep(0.5)

    print(f"  Handoff dispatch prompt injected into '{tmux_session}'")
```

with:

```python
    # Step 8: Inject prompt into target role's tmux session — HARD GATE
    inj = inject_prompt(tmux_session, prompt_text,
                        enter_command=to_role_data.get("enter_command", "default"))
    time.sleep(0.5)
    if not inj["submitted"]:
        print(f"  ERROR: injection UNCONFIRMED in '{tmux_session}' "
              f"(state={inj['state']}, fallback_used={inj['fallback_used']})",
              file=sys.stderr)
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "signal_send_failed",
            f"Injection unconfirmed in {tmux_session} "
            f"(state={inj['state']}, resends={inj['resends']}, "
            f"fallback={inj['fallback_used']})",
        )
        return False

    print(f"  Handoff dispatch prompt injected into '{tmux_session}' "
          f"(verified: {inj['state']})")
```

- [ ] Step 2: `signal_complete` (call site ~1375). Replace:

```python
    # Step 8: Inject callback prompt into to_role's tmux session
    inject_prompt(tmux_session, prompt_text,
                  enter_command=to_role.get("enter_command", "default"))
    time.sleep(0.5)
```

with:

```python
    # Step 8: Inject callback prompt into to_role's tmux session — HARD GATE
    inj = inject_prompt(tmux_session, prompt_text,
                        enter_command=to_role.get("enter_command", "default"))
    time.sleep(0.5)
    if not inj["submitted"]:
        print(f"  ERROR: injection UNCONFIRMED in '{tmux_session}' "
              f"(state={inj['state']})", file=sys.stderr)
        log(
            f"{payload['from_role']}->{payload['to_role']}",
            handoff_id,
            "signal_complete_failed",
            f"Injection unconfirmed in {tmux_session} "
            f"(state={inj['state']}, resends={inj['resends']}, "
            f"fallback={inj['fallback_used']})",
        )
        return False
```

IMPORTANT: this failure log uses status `signal_complete_failed`, which does NOT match the watchdog's success needle `"| {role}->{next_role} | {run_id} | signal_complete |"` in `recent_signal_delivered` (chain_watchdog.py:217) — so the watchdog will correctly re-nudge a failed injection. The Step 8b success `log(..., "signal_complete", ...)` (which follows this gate) now only fires after a CONFIRMED injection, which is exactly what the duplicate-nudge guard should see. (If PLAN-postdispatch-stop-hang.md was applied first, this call site sits inside its `try:` block — keep the `return False` inside the `try`; the `finally:` still fires the detached model stop, which is correct: the predecessor is done regardless.)
- [ ] Step 3: `signal_escalation` (~1559) and `signal_answer` (~1703): apply the same pattern with statuses `escalation_failed` / `answer_failed` and their respective direction strings `f"{from_role_key}->{to_role_key}"`.
- [ ] Step 4: `run_flow_step_db` (~1034): same pattern with status `failed` and direction `f"{payload['from_role']}->{payload['to_role']}"`, returning `False`.
- [ ] Step 5: `python3 -m py_compile scripts/bridgeV002/dispatch.py` — exit 0.

---

### Task 5: Exit codes — stop swallowing failures in `main()`

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py`, `main()` (~2033–2133).

- [ ] Step 1: Add the exit-code contract as a comment right above `main()`:

```python
# ── Exit codes (interface for cron/watchdog/roles) ────────────────
#   0   signal delivered AND injection confirmed
#   1   usage/config error (missing --db-flow / --to-role)
#   3   signal NOT confirmed: session dead, deliverable missing,
#       validation failed, or injection unconfirmed after the retry
#       ladder (see verify_injection_submitted)
#   124 killed by the callers' outer `timeout 60` wrapper (the roles'
#       chain_advancement command) — the early trace write has already
#       recorded a delivered signal in that case
```

- [ ] Step 2: In `main()`, capture each signal function's boolean and exit accordingly. Replace the four blocks of the form:

```python
        signal_send(
            args.db_flow,
            args.from_role,
            args.to_role,
            handoff_id,
            bridge_dir,
        )
        sys.exit(0)
```

with (repeating for all four — `signal_send`, `signal_escalation`, `signal_answer`, `signal_complete`):

```python
        ok = signal_send(
            args.db_flow,
            args.from_role,
            args.to_role,
            handoff_id,
            bridge_dir,
        )
        sys.exit(0 if ok else 3)
```

and the final fallthrough:

```python
    # No signal flag but db-flow provided — run full flow step via DB dispatch
    ok = run_flow_step_db(args.db_flow, args.step_key, handoff_id, bridge_dir)
    sys.exit(0 if ok else 3)
```

- [ ] Step 3: `python3 -m py_compile scripts/bridgeV002/dispatch.py` — exit 0.
- [ ] Step 4: Behavioral check without tmux: `python3 scripts/bridgeV002/dispatch.py --db-flow no_such_flow --signal-complete --from-role nobody --id 1; echo "exit=$?"` — expected: an error line about the flow not found and `exit=3` (previously `exit=0`).

---

### Task 6: Keep the cron flow alive under `set -euo pipefail`

**Files:**
- Modify: `/home/svend/DPMtF-WebUI/scripts/trade-cronjob.sh` (dispatch call at step "[6/6]", lines ~110–114).

- [ ] Step 1: Replace:

```bash
python3 scripts/bridgeV002/dispatch.py \
    --db-flow "$FLOW_KEY" \
    --signal-send --from-role humantrade --to-role trend01_trade \
    --id "$FLOW_ID"
```

with:

```bash
# Exit 3 = injection unconfirmed (hard gate). Do NOT abort the cron run:
# the watchdog started below is exactly the recovery mechanism for this.
if ! python3 scripts/bridgeV002/dispatch.py \
    --db-flow "$FLOW_KEY" \
    --signal-send --from-role humantrade --to-role trend01_trade \
    --id "$FLOW_ID"; then
    echo "  WARNING: dispatch exited non-zero (injection unconfirmed?) — chain watchdog will monitor/retry"
fi
```

- [ ] Step 2: `bash -n scripts/trade-cronjob.sh` — exit 0.
- [ ] Step 3: Same pattern check in `scripts/scoring-cronjob.sh`: `grep -n "dispatch.py" scripts/scoring-cronjob.sh` — if it calls dispatch directly under `set -e`, apply the identical wrapper there and run `bash -n scripts/scoring-cronjob.sh`.

---

### Task 7: Stage and stop

- [ ] Step 1: `git diff --stat` — expected files only: `scripts/bridgeV002/tmux_pane.py` (new), `scripts/bridgeV002/dispatch.py`, `scripts/bridgeV002/chain_watchdog.py`, `scripts/trade-cronjob.sh`, possibly `scripts/scoring-cronjob.sh`, `tests/test_tmux_pane.py` (new).
- [ ] Step 2: Full suite: `python3 -m pytest -q` — no new failures (`tests/test_migrate.py` has 2 pre-existing failures unrelated to this plan).
- [ ] Step 3: Stage with `git add scripts/bridgeV002/tmux_pane.py scripts/bridgeV002/dispatch.py scripts/bridgeV002/chain_watchdog.py scripts/trade-cronjob.sh tests/test_tmux_pane.py` (add `scripts/scoring-cronjob.sh` if changed) and STOP — await Human commit approval. Suggested commit message: `[hardening] injection verification hard gate + shared tmux_pane module`.

## Acceptance Criteria

1. `python3 -m pytest tests/test_tmux_pane.py -q` — all pass (`13 passed`).
2. `grep -rn '"esc interrupt"' scripts/bridgeV002/*.py` — exactly ONE hit, in `tmux_pane.py` (marker tuple deduplicated).
3. `python3 scripts/bridgeV002/dispatch.py --db-flow no_such_flow --signal-complete --from-role nobody --id 1; echo "exit=$?"` — prints `exit=3`.
4. `bash -n scripts/trade-cronjob.sh` — exit 0; `grep -n "WARNING: dispatch exited non-zero" scripts/trade-cronjob.sh` — one hit.
5. `python3 -m py_compile scripts/bridgeV002/dispatch.py scripts/bridgeV002/chain_watchdog.py scripts/bridgeV002/tmux_pane.py` — exit 0.
6. Live gate proof (Human-run, next flow): after a `--signal-send` into a deliberately dead-input session, `$DPMTF_BRIDGE_DIR/trace.log` contains a `signal_send_failed` line and the dispatch exit code is 3 (`echo $?`).
7. `curl -s http://localhost:9130/api/health` returns `{"status":"healthy"}`.
