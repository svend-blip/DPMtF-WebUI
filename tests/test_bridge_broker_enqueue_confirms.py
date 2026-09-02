"""enqueue prints one confirmation line; a suppressed duplicate says so.

Silence was read as failure: on 2026-09-02 a decomposer re-ran its
enqueue twice looking for a "dispatch line" that the command never
printed, and every duplicate signal of the night has that shape.
"""
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import bridge_broker  # noqa: E402


def _fresh(tmp_path, monkeypatch):
    db = tmp_path / "queue.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(bridge_broker._SCHEMA_DISPATCH_SQL)
    conn.executescript(bridge_broker._SCHEMA_MATERIALIZE_SQL)
    conn.commit()
    conn.close()
    monkeypatch.setattr(bridge_broker, "_get_db_path", lambda: str(db))
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir", lambda: str(tmp_path))
    return db


ARGS = ["enqueue", "--flow", "9000-02-ELOOP", "--from-role", "9000-execution-decomposer",
        "--to-role", "9000-implementer", "--id", "30", "--action", "signal-send"]


def test_enqueue_prints_the_row_it_wrote(tmp_path, monkeypatch, capsys):
    _fresh(tmp_path, monkeypatch)
    assert bridge_broker.main(list(ARGS)) == 0
    out = capsys.readouterr().out
    assert out.startswith("enqueued: row 1 9000-02-ELOOP 9000-execution-decomposer->9000-implementer id=030 action=signal-send")
    assert "do not run this command again" in out


def test_second_enqueue_says_already_and_writes_nothing(tmp_path, monkeypatch, capsys):
    db = _fresh(tmp_path, monkeypatch)
    assert bridge_broker.main(list(ARGS)) == 0
    capsys.readouterr()
    assert bridge_broker.main(list(ARGS)) == 0
    out = capsys.readouterr().out
    assert out.startswith("already enqueued:")
    assert "do not run this command again" in out
    conn = sqlite3.connect(str(db))
    assert conn.execute("SELECT count(*) FROM bridge_dispatch_queue").fetchone()[0] == 1
