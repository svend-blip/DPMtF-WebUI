"""materialize --type end-report refuses a body that is not a report.

Measured 2026-09-02 on 9000 run 013: a closing session left a 4-byte
"test" probe as END-REPORT.md; every reader took the Run as closed while
its rework was still owed. The floor is a heading and an outcome line.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import bridge_broker  # noqa: E402


def test_stub_is_not_a_report():
    assert bridge_broker._end_report_problem("test") is not None
    assert bridge_broker._end_report_problem("# END-REPORT — Run 013\n\nwork in progress\n") is not None
    assert bridge_broker._end_report_problem("Outcome: SUCCESS\n") is not None


def test_real_reports_pass():
    assert bridge_broker._end_report_problem("# END-REPORT — 9000 Run 002\n\n**Outcome: SUCCESS.** The loader landed.\n") is None
    assert bridge_broker._end_report_problem("# END-REPORT — Run 012\n\n**Status:** SUCCESS — CLOSED\n\n## Outcome\n") is None
    assert bridge_broker._end_report_problem("# END REPORT — 014 (PARKED)\n\nStatus: PARKED\n") is None


def _fresh_db(tmp_path, monkeypatch):
    import sqlite3
    db = tmp_path / "queue.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(bridge_broker._SCHEMA_DISPATCH_SQL)
    conn.executescript(bridge_broker._SCHEMA_MATERIALIZE_SQL)
    conn.execute("CREATE TABLE bridge_flows (flow_key TEXT PRIMARY KEY, artifact_root TEXT)")
    conn.execute("INSERT INTO bridge_flows VALUES ('9000-02-ELOOP', '9000')")
    conn.commit()
    conn.close()
    (tmp_path / "9000" / "runs" / "013").mkdir(parents=True)
    monkeypatch.setattr(bridge_broker, "_get_db_path", lambda: str(db))
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir", lambda: str(tmp_path))
    return str(db)


def test_materialize_cli_refuses_a_stub_end_report(monkeypatch, tmp_path):
    tmp_db = _fresh_db(tmp_path, monkeypatch)
    rc = bridge_broker.main([
        "materialize", "--flow", "9000-02-ELOOP", "--type", "end-report",
        "--run-id", "13", "--content", "test",
    ])
    assert rc != 0
    import sqlite3
    conn = sqlite3.connect(tmp_db)
    assert conn.execute("SELECT count(*) FROM bridge_materialize_queue").fetchone()[0] == 0


def test_materialize_cli_accepts_a_real_end_report(monkeypatch, tmp_path):
    _fresh_db(tmp_path, monkeypatch)
    rc = bridge_broker.main([
        "materialize", "--flow", "9000-02-ELOOP", "--type", "end-report",
        "--run-id", "13", "--content", "# END-REPORT — Run 013\n\n**Outcome: SUCCESS.** Done.\n",
    ])
    assert rc == 0
