"""Anchor-invariant tests for start_coding (Run 031 D1).

Run 030's live release aborted with the message:
  codex-context-release: REFUSED stop (survivor: 1510133)
The defect is DATA, not logic. The live anchor row recorded
pid 1510133 — the tmux pane's interactive login shell (-bash,
SIGTERM-ignored) — when the anchor must be the harness CHILD pid
forked by the pane shell after DPMtF's send-keys. start_coding
already resolves and records the child (2026-08-21 fix, the same
hazard named by pid 1510133 in its docstring), so the change is to
PIN that contract in a test that survives future edits.

This suite pins the four binding rules GOAL.md §1 D1 names:

  (T1) pane_shell — name the test so `-k "pane_shell"` selects it
       (the same selector TG3 uses). With pane pid P and children
       [C1, C2], `_harness_child_pid` returns min(C1, C2) and NOT P.
       AND with NO children, `_harness_child_pid` returns None and
       NOT P. This is the m1 guard: a `_harness_child_pid` that
       returned the pane shell would be caught here.

  (T2) earliest-child — with children returned OUT of order (e.g.
       "4090\\n4123\\n"), `_harness_child_pid` returns the smallest
       (4090), never the newest. This is the m3 guard.

  (T3) record-success — when `_harness_child_pid` returns C,
       `_record_harness_ownership` calls
       `runtime_owner.record(flow, "harness_process", session, pid=C)`.

  (T4) record-failure — when `_harness_child_pid` RAISES,
       `_record_harness_ownership` calls
       `runtime_owner.record(..., pid=None)` — NOT the pane pid.
       This is the m2 guard: an exception path that recorded the
       pane pid would be caught here.

HERMETIC by construction. The test injects seams for `_pane_pid`,
`subprocess.run` (the `ps --ppid` call), and `runtime_owner.record`;
no live tmux, no live /proc, no live `flow_runtime_resources`. The
captured pid is asserted on int values (the helper returns
int(pids) via `min(pids)`); where a test path touches a path string,
str() is used explicitly per the project's coding standard.

Reference: /home/svenv/flows/preferred_cloud_harness/runs/031/GOAL.md
   (§1 D1, §4 TG2/TG3, §5 m1/m2/m3).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

# Ensure the harness-allocator package is locatable. start_coding delegates
# to runtime_owner and config reads config.get_project_path('harness-allocator').
import os  # noqa: E402
os.environ.setdefault(
    "HARNESS_ALLOCATOR_PATH",
    str(PROJECT_ROOT.parent / "harness-allocator"),
)

import config  # noqa: E402
import runtime_owner  # noqa: E402
import start_coding as sc  # noqa: E402


# ---------------------------------------------------------------------------
# Recording stubs — capture each call so tests can assert on the pid kwarg.
# ---------------------------------------------------------------------------
class _RecordRecorder:
    """Drop-in for `runtime_owner.record` that captures every call.

    `runtime_owner.record` is the seam `_record_harness_ownership` uses to
    persist the harness_process anchor row. Replacing it with this recorder
    means no test ever touches `databases/dpmtf.db` or the live
    `flow_runtime_resources` table — the entire `runtime_owner` write path
    is short-circuited.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, flow_key, resource_type, resource_id, pid=None, db_path=None):
        self.calls.append(
            {
                "flow_key": flow_key,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "pid": pid,
                "db_path": db_path,
            }
        )
        return None


class _PsRunResult:
    """A `subprocess.run` return value with `stdout` carrying child pids.

    `_harness_child_pid` reads `ps --ppid <pane> -o pid=` output and parses
    it line-by-line. The contract it parses is "digit lines"; we feed it
    whatever digit lines the test wants (in the order the test wants), so
    the helper's real parsing path is exercised rather than a fake parser.
    """

    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


# ---------------------------------------------------------------------------
# Seams fixture — every outbound touchpoint is replaced.
# ---------------------------------------------------------------------------
@pytest.fixture
def seams(monkeypatch):
    """Stub every dependency of _harness_child_pid and _record_harness_ownership.

    Returns a namespace with the recorder, the configurable ps output, and
    the pane pid the test wants. Tests set `seams.pane_pid` and `seams.ps_stdout`
    to drive `_harness_child_pid`, then assert on `seams.recorder.calls`.
    """
    recorder = _RecordRecorder()
    state = {"pane_pid": 1510133, "ps_stdout": "", "raise_in_child": False}

    monkeypatch.setattr(sc, "_pane_pid", lambda session_name: state["pane_pid"])
    monkeypatch.setattr(sc, "runtime_owner", SimpleNamespaceFromRecorder(recorder))

    def fake_run(args, **kwargs):
        if state["raise_in_child"]:
            raise OSError("simulated ps failure")
        return _PsRunResult(stdout=state["ps_stdout"])

    monkeypatch.setattr(sc, "subprocess", SimpleNamespace(run=fake_run))

    return SimpleNamespace(
        recorder=recorder,
        state=state,
        pane_pid=1510133,
    )


class SimpleNamespaceFromRecorder:
    """Build a SimpleNamespace that exposes `record` from the recorder.

    `_record_harness_ownership` reads `start_coding.runtime_owner.record`,
    so we replace `runtime_owner` on the `start_coding` module with a
    namespace whose `record` attribute is the recorder itself. All
    other attributes `runtime_owner` exposes are pass-through or
    irrelevant for these tests.
    """

    def __init__(self, recorder: _RecordRecorder) -> None:
        self._recorder = recorder
        self.record = recorder
        # Pass-through any other attributes the module exposes; the
        # tests never touch them but start_coding may import them
        # transitively.
        self.__dict__.setdefault("stop_owned_harness_processes", lambda *a, **k: [])


# ---------------------------------------------------------------------------
# T1 — pane_shell: _harness_child_pid returns the child, NEVER the pane shell.
# ---------------------------------------------------------------------------
def test_harness_child_is_never_the_pane_shell(seams):
    """m1 guard. With pane pid P and children [C1, C2], the helper returns
    min(C1, C2) and never P. With NO children, the helper returns None and
    never P. The test name contains "pane_shell" so `-k "pane_shell"` selects
    it (TG3).
    """
    pane = seams.pane_pid
    # (a) Children present: helper returns the smallest child, not the pane.
    seams.state["ps_stdout"] = "4123\n4090\n"
    child = sc._harness_child_pid("imple-codex-minimaxM3", max_wait_s=0.5)
    assert child is not None, "helper returned None with children present"
    assert int(child) == 4090, (
        f"helper returned {child!r}; expected the smallest child 4090, "
        f"never the pane shell {pane}"
    )
    assert int(child) != int(pane), (
        f"helper returned the pane shell pid {pane}; the pane shell is "
        f"TERM-immune and must never be the anchor"
    )

    # (b) No children: helper returns None, NOT the pane shell.
    seams.state["ps_stdout"] = ""
    child = sc._harness_child_pid("imple-codex-minimaxM3", max_wait_s=0.2)
    assert child is None, (
        f"helper returned {child!r} with no children; expected None, "
        f"never the pane shell {pane}"
    )


# ---------------------------------------------------------------------------
# T2 — earliest-child: the helper returns the smallest pid, never the newest.
# ---------------------------------------------------------------------------
def test_harness_child_returns_earliest_child_not_newest(seams):
    """m3 guard. With children returned OUT of order ("4090\\n4123\\n"),
    the helper returns 4090 (the smallest), never 4123 (the newest).
    """
    pane = seams.pane_pid
    seams.state["ps_stdout"] = "4090\n4123\n"
    child = sc._harness_child_pid("imple-codex-minimaxM3", max_wait_s=0.5)
    assert child is not None
    assert int(child) == 4090, (
        f"helper returned {child!r}; expected the earliest child 4090, "
        f"not the newest 4123"
    )
    assert int(child) != 4123, (
        f"helper returned the newest child 4123; the anchor must be the "
        f"first-forked harness, not a helper"
    )
    assert int(child) != int(pane), (
        f"helper returned the pane shell {pane}; the pane shell is "
        f"TERM-immune and must never be the anchor"
    )


# ---------------------------------------------------------------------------
# T3 — record-success: _record_harness_ownership records the child pid.
# ---------------------------------------------------------------------------
def test_record_harness_ownership_records_child_pid(seams):
    """When _harness_child_pid resolves a child C, _record_harness_ownership
    calls runtime_owner.record(flow, "harness_process", session, pid=C).
    """
    pane = seams.pane_pid
    seams.state["ps_stdout"] = "4090\n4123\n"
    sc._record_harness_ownership("preferred_cloud_harness", "imple-codex-minimaxM3")

    assert len(seams.recorder.calls) == 1, (
        f"expected exactly one record() call, got {len(seams.recorder.calls)}: "
        f"{seams.recorder.calls!r}"
    )
    call = seams.recorder.calls[0]
    assert call["flow_key"] == "preferred_cloud_harness"
    assert call["resource_type"] == "harness_process"
    assert call["resource_id"] == "imple-codex-minimaxM3"
    assert call["pid"] is not None, (
        f"recorded pid is None; expected the child (smallest of 4090, 4123)"
    )
    assert int(call["pid"]) == 4090, (
        f"recorded pid is {call['pid']!r}; expected the smallest child 4090"
    )
    assert int(call["pid"]) != int(pane), (
        f"recorded pid is the pane shell {pane}; the pane shell is "
        f"TERM-immune and must never be the anchor"
    )


# ---------------------------------------------------------------------------
# T4 — record-failure: _record_harness_ownership records pid=None on exception.
# ---------------------------------------------------------------------------
def test_record_harness_ownership_records_none_on_failure(seams):
    """m2 guard. When _harness_child_pid raises (e.g. ps times out, OSError),
    _record_harness_ownership calls runtime_owner.record(..., pid=None) —
    NOT the pane pid. Recording the pane pid as a fallback would resurrect
    exactly the 2026-08-20 row shape.
    """
    pane = seams.pane_pid
    seams.state["raise_in_child"] = True

    sc._record_harness_ownership("preferred_cloud_harness", "imple-codex-minimaxM3")

    assert len(seams.recorder.calls) == 1, (
        f"expected exactly one record() call, got {len(seams.recorder.calls)}: "
        f"{seams.recorder.calls!r}"
    )
    call = seams.recorder.calls[0]
    assert call["flow_key"] == "preferred_cloud_harness"
    assert call["resource_type"] == "harness_process"
    assert call["resource_id"] == "imple-codex-minimaxM3"
    assert call["pid"] is None, (
        f"recorded pid is {call['pid']!r}; expected None on the exception "
        f"path, NEVER the pane shell {pane}"
    )
    assert call["pid"] != pane, (
        f"recorded pid is the pane shell {pane}; an exception path that "
        f"recorded the pane pid would resurrect the 2026-08-20 row shape"
    )
