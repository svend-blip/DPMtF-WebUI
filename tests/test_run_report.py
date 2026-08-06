"""Tests for the ledger and END-REPORT skeleton generator.

The generator exists because run 009's supervisor spent 1m53s reading two
closed runs to work out the END-REPORT format, then wrote the testgoal table
by hand from commands it had already run.

The property that matters is the split: facts filled in, judgement left as
TODO. A skeleton that quietly asserts a conclusion is worse than no skeleton,
because it reads like the supervisor's own words.
"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent.parent / "scripts" / "bridgeV002"
_spec = importlib.util.spec_from_file_location("run_report", _HERE / "run_report.py")
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)

FLOW = "llama_SG"
ROLES = ("supervisor01_llama", "imple01SG", "review01SG")

GOAL = """# GOAL.md — Run 009: The Context-Baking Rule

**First handoff id: 012**

```testgoals
id: TG1
what: The README explains the warm-up hint
run: echo 7
expect: at least 2

id: TG2
what: A criterion that is not met yet
run: echo 0
expect: at least 2
```
"""


@pytest.fixture
def bridge(tmp_path):
    root = tmp_path / "flows"
    for sub in ("handoffs", "results", "verdicts", "runs"):
        (root / FLOW / sub).mkdir(parents=True)
    run = root / FLOW / "runs" / "009"
    run.mkdir()
    (run / "GOAL.md").write_text(GOAL, encoding="utf-8")
    (root / FLOW / "handoffs" / "012-handoff.md").write_text("x", encoding="utf-8")
    (root / "trace.log").write_text(
        "2026-08-06T08:35:55Z | supervisor01_llama->imple01SG | 012 | dispatched | m | x\n"
        "2026-08-06T08:37:15Z | imple01SG->review01SG | 012 | signal_complete | m | x\n"
        "2026-08-06T08:40:17Z | review01SG->supervisor01_llama | 012 | signal_complete | m | x\n",
        encoding="utf-8")
    return root


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE bridge_flow_steps (flow_key TEXT, from_role TEXT, to_role TEXT);"
        "CREATE TABLE bridge_roles (role_key TEXT, tmux_session TEXT,"
        " default_model_alias TEXT);"
        "CREATE TABLE bridge_id_counters (flow_key TEXT PRIMARY KEY, next_id INTEGER);"
    )
    conn.executemany("INSERT INTO bridge_flow_steps VALUES (?,?,?)",
                     [(FLOW, ROLES[0], ROLES[1]), (FLOW, ROLES[1], ROLES[2]),
                      (FLOW, ROLES[2], ROLES[0])])
    conn.executemany("INSERT INTO bridge_roles VALUES (?,?,?)",
                     [(r, r, "laguna-local") for r in ROLES])
    conn.execute("INSERT INTO bridge_id_counters VALUES (?,?)", (FLOW, 13))
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture
def wired(bridge, db, tmp_path, monkeypatch):
    for module in (rr, rr._state, rr._testgoals):
        monkeypatch.setattr(module.config, "get_db_path", lambda: db, raising=False)
    monkeypatch.setattr(rr._state.config, "get_bridge_dir", lambda: str(bridge))
    monkeypatch.setattr(rr._state, "_probe", lambda *a, **k: True)
    monkeypatch.setattr(rr._state, "_tmux_sessions", lambda names: {n: True for n in names})
    monkeypatch.setattr(rr.config, "get_project_root", lambda: str(tmp_path))
    monkeypatch.setattr(rr._testgoals.config, "get_project_root", lambda: str(tmp_path))
    return bridge


class TestFactsAreFilledIn:

    def test_testgoal_results_come_from_running_them(self, wired):
        data = rr.gather(FLOW)
        assert [r["passed"] for r in data["results"]] == [True, False]
        assert data["results"][0]["detail"] == "got 7"

    def test_active_time_is_measured_from_trace(self, wired):
        """08:35:55 to 08:40:17 is 4.4 minutes — not the wall clock."""
        assert rr.gather(FLOW)["active_minutes"] == 4.4

    def test_title_comes_from_the_contract(self, wired):
        assert rr.gather(FLOW)["title"] == "Run 009: The Context-Baking Rule"

    def test_end_report_table_carries_the_evidence(self, wired):
        out = rr.render_end_report(rr.gather(FLOW))
        assert "| TG1 |" in out and "got 7" in out
        assert "**GREEN**" in out and "**RED**" in out


class TestJudgementIsLeftBlank:

    def test_ledger_asks_for_the_judgement(self, wired):
        out = rr.render_ledger(rr.gather(FLOW), "verdict-012-APPROVED")
        assert "TODO: the judgement" in out
        assert "TODO: what you did about it" in out

    def test_end_report_does_not_write_the_narrative(self, wired):
        out = rr.render_end_report(rr.gather(FLOW))
        assert "TODO: one paragraph per handoff" in out

    def test_a_red_testgoal_does_not_produce_a_closed_status(self, wired):
        """One RED means the run is not closed, whatever the skeleton says."""
        out = rr.render_end_report(rr.gather(FLOW))
        assert "**Status:** TODO" in out
        assert "CLOSED" not in out.split("## Testgoals")[0]


class TestHonestAboutWhatItCannotCheck:

    def test_no_testgoals_block_says_validate_by_hand(self, wired, bridge):
        (bridge / FLOW / "runs" / "009" / "GOAL.md").write_text(
            "# GOAL.md — Run 009: Prose only\n\nNo block here.\n", encoding="utf-8")
        out = rr.render_end_report(rr.gather(FLOW))
        assert "no ```testgoals block" in out
        assert "validate by hand" in out
        assert "**0 of 0 green.**" in out

    def test_no_active_run_refuses(self, wired, bridge):
        (bridge / FLOW / "runs" / "009" / "END-REPORT.md").write_text("closed")
        with pytest.raises(SystemExit, match="No active run"):
            rr.gather(FLOW)

    def test_reminds_the_human_not_to_commit_the_database(self, wired):
        out = rr.render_end_report(rr.gather(FLOW))
        assert "dpmtf.db" in out and "exhaust" in out
