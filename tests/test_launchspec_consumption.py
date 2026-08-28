"""LaunchSpec/StopSpec consumption tests — the code READS the spec.

start-path half (Run 041 handoff 154, GOAL.md §1 D5(i)): prove that
start_coding's terminal-vs-resident / initial-prompt / ownership decision
FOLLOWS the spec, including a fictional harness name the real spec does
not register (no name test anywhere).

stop-path half (Run 041 handoff 156, GOAL.md §1 D5(ii)): prove that
runtime_owners stop_spec_for reads the allocator declaration, falls back
to today's literal on an unregistered harness, and that the spec-driven
stop path actually applies the spec's signals ladder rather than a
hardcoded SIGTERM.
"""
import signal
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import chain_watchdog  # noqa: E402
import runtime_owner  # noqa: E402
import start_coding  # noqa: E402


def test_decisions_follow_spec_terminal_wrapped(monkeypatch):
    spec = {"mode": "terminal_wrapped", "needs_initial_prompt": True, "anchor": "none"}
    monkeypatch.setattr(start_coding.harness, "launch_spec", lambda role: spec)
    terminal, prompt, ownership = start_coding._launch_decisions_for("dsh")
    assert (terminal, prompt, ownership) == (True, True, False)


def test_decisions_follow_spec_resident_tui(monkeypatch):
    spec = {"mode": "resident_tui", "needs_initial_prompt": False, "anchor": "child"}
    monkeypatch.setattr(start_coding.harness, "launch_spec", lambda role: spec)
    terminal, prompt, ownership = start_coding._launch_decisions_for("codex")
    assert (terminal, prompt, ownership) == (False, False, True)


def test_fictional_harness_takes_resident_path_with_no_name_test(monkeypatch):
    # A harness the real spec does NOT register still follows the patched
    # spec — proving the fork has no harness-name test anywhere.
    spec = {"mode": "resident_tui", "needs_initial_prompt": True, "anchor": "child"}
    monkeypatch.setattr(start_coding.harness, "launch_spec", lambda role: spec)
    terminal, prompt, ownership = start_coding._launch_decisions_for("fictional")
    assert (terminal, prompt, ownership) == (False, True, True)

# ---------------------------------------------------------------------------
# stop-path half (handoff 156, GOAL.md §1 D5(ii))
# ---------------------------------------------------------------------------


def _warmup_allocator_path():
    """Make ``harness_allocator.*`` importable from this test file.

    Reuses ``harness._standalone()`` — the same resolver runtime_owner uses —
    so the test never hardcodes the allocator's on-disk location. Cached
    on the harness module, so subsequent calls are no-ops.
    """
    import harness  # noqa: F401 — same scripts/bridgeV002 directory as runtime_owner
    harness._standalone()


def test_stop_spec_for_returns_allocator_declaration(monkeypatch):
    """stop_spec_for returns the allocator's declared StopSpec for a known harness.

    Proves the delegate is THIN — no transcription of the per-harness
    values into runtime_owner.py literals.
    """
    _warmup_allocator_path()
    import harness_allocator.launchspec as halaunchspec
    sentinel = {"signals": ["SIGINT", "SIGTERM", "SIGKILL"],
                "grace_seconds": 1, "verify": "pid_gone"}
    monkeypatch.setattr(halaunchspec, "get_stop_spec", lambda harness: dict(sentinel))
    spec = runtime_owner.stop_spec_for("dsh")
    assert spec == sentinel
    assert spec["signals"] == ["SIGINT", "SIGTERM", "SIGKILL"]
    assert spec["grace_seconds"] == 1
    assert spec["verify"] == "pid_gone"


def test_stop_spec_for_falls_back_on_unknown_harness(monkeypatch):
    """stop_spec_for returns today's fallback when the allocator raises UnknownHarnessError.

    UnknownHarnessError is a ValueError subclass; the delegate catches it
    and returns the literal _DEFAULT_STOP_SPEC (byte-identical to today's
    _default_kill: SIGTERM-only, 3.0 s verify, pid_gone).
    """
    _warmup_allocator_path()
    import harness_allocator.launchspec as halaunchspec
    def boom(harness):
        raise ValueError(f"unknown harness: {harness!r}")
    monkeypatch.setattr(halaunchspec, "get_stop_spec", boom)
    spec = runtime_owner.stop_spec_for("fictional")
    assert spec == {"signals": ["SIGTERM"], "grace_seconds": 3.0,
                    "verify": "pid_gone"}


def test_stop_path_applies_patched_spec_ladder(monkeypatch, tmp_path):
    """The stop path APPLIES the spec's signals ladder rather than a hardcoded SIGTERM.

    Proves the consumption by recording every os.kill signal sent. The
    patched spec has signals=["SIGINT", "SIGKILL"] (deliberately NOT
    SIGTERM); after SIGINT raises ProcessLookupError the ladder
    short-circuits (mirroring _default_kill's "already dead -> True, stop"
    semantics), so the FIRST signal sent is SIGINT, not SIGTERM.
    """
    sent = []

    def fake_kill(pid, sig):
        sent.append((pid, sig))
        raise ProcessLookupError  # pid is already gone after this signal

    monkeypatch.setattr(runtime_owner.os, "kill", fake_kill)
    # Resolve the row to a known harness so the path consults stop_spec_for.
    monkeypatch.setattr(runtime_owner, "_harness_for_resource",
                        lambda resource_id, db_path=None: "dsh")
    monkeypatch.setattr(runtime_owner, "stop_spec_for",
                        lambda harness: {"signals": ["SIGINT", "SIGKILL"],
                                         "grace_seconds": 0.1,
                                         "verify": "pid_gone"})

    db = str(tmp_path / "ro.db")
    runtime_owner.record("f", "harness_process", "sess", pid=4242, db_path=db)
    stopped = runtime_owner.stop_owned_harness_processes("f", db_path=db)
    assert stopped == ["sess"]
    # The first ladder signal sent is SIGINT (from the patched spec), not
    # SIGTERM (the hardcoded default) — proving the path READ the spec.
    assert sent and sent[0] == (4242, signal.SIGINT)


# ---------------------------------------------------------------------------
# markers half (handoff 157, GOAL.md §1 D5(iii)) -- chain_watchdog's
# _derive_activity_markers consumes the LaunchSpec's activity_markers union.
# ---------------------------------------------------------------------------


def test_derive_activity_markers_unpatched_equals_today_set():
    """The derived union (unpatched) equals today's marker set.

    The three harnesses today all declare the SAME three markers, so the
    sorted union is the literal three-tuple. chain_watchdog.ACTIVITY_MARKERS
    is initialised from this function at module load; the identity holds.
    """
    _warmup_allocator_path()
    assert set(chain_watchdog._derive_activity_markers()) == {
        "esc interrupt", "esc to interrupt", "↓",
    }


def test_derive_activity_markers_follows_patched_spec(monkeypatch):
    """The union FOLLOWS the declared activity_markers, not a memory of the three-marker tuple.

    Patches get_launch_spec so every registered harness declares a fictional
    marker; the derived union MUST include "fictional-working", proving the
    function READS the spec rather than transcribing a hardcoded tuple.
    """
    _warmup_allocator_path()
    import harness_allocator.launchspec as halaunchspec

    def fake(harness):
        return {
            "mode": "resident_tui",
            "needs_initial_prompt": False,
            "anchor": "none",
            "required_env": [],
            "activity_markers": ["fictional-working"],
            "launch_owner": "model_allocator",
        }
    monkeypatch.setattr(halaunchspec, "get_launch_spec", fake)
    derived = set(chain_watchdog._derive_activity_markers())
    assert "fictional-working" in derived, (
        "the derived marker set missed the patched spec's marker; "
        "_derive_activity_markers is transcribing, not reading the spec"
    )


def test_derive_activity_markers_falls_back_on_import_error(monkeypatch):
    """Allocator absent -> the pre-D3 literal tuple (today's exact set).

    Monkeypatching harness._standalone to raise ImportError is the cleanest
    seam: _derive_activity_markers calls it inside its try block, so the
    ImportError is caught and the literal fallback tuple is returned.
    """
    import harness  # noqa: F401 -- already imported implicitly; explicit re-import is a no-op

    def boom():
        raise ImportError("harness_allocator unavailable")

    monkeypatch.setattr(harness, "_standalone", boom)
    assert set(chain_watchdog._derive_activity_markers()) == {
        "esc interrupt", "esc to interrupt", "↓",
    }, "ImportError fallback did not return the pre-D3 literal tuple"
