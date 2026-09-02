"""enqueue/materialize refuse an explicit --db-path that does not exist.

Measured 2026-09-02 on 9000-02-ELOOP: the decomposer invented
`--db-path /home/svend/flows/9000/dispatch.sqlite3`; the broker created a
fresh queue database there, the daemon never saw the row, and the chain
stalled on a signal the role believed it had sent.
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

import bridge_broker  # noqa: E402


def test_enqueue_refuses_a_db_path_that_does_not_exist(tmp_path, monkeypatch):
    real = tmp_path / "real.db"
    monkeypatch.setattr(bridge_broker, "_get_db_path", lambda: str(real))
    phantom = tmp_path / "flows" / "9000" / "dispatch.sqlite3"
    phantom.parent.mkdir(parents=True)
    rc = bridge_broker.main([
        "enqueue", "--flow", "9000-02-ELOOP",
        "--from-role", "9000-execution-decomposer", "--to-role", "9000-implementer",
        "--id", "19", "--action", "signal-send", "--db-path", str(phantom),
    ])
    assert rc != 0
    assert not phantom.exists(), "a refused --db-path must not be created"


def test_materialize_refuses_a_db_path_that_does_not_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge_broker, "_get_db_path", lambda: str(tmp_path / "real.db"))
    phantom = tmp_path / "phantom.sqlite3"
    rc = bridge_broker.main([
        "materialize", "--flow", "9000-02-ELOOP", "--type", "run-ledger",
        "--run-id", "9", "--content", "x", "--db-path", str(phantom),
    ])
    assert rc != 0
    assert not phantom.exists()


def test_existing_db_path_is_still_accepted(tmp_path, monkeypatch):
    import sqlite3
    db = tmp_path / "queue.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(bridge_broker._SCHEMA_DISPATCH_SQL)
    conn.executescript(bridge_broker._SCHEMA_MATERIALIZE_SQL)
    conn.commit()
    conn.close()
    monkeypatch.setattr(bridge_broker, "_get_db_path", lambda: str(tmp_path / "unused.db"))
    monkeypatch.setattr(bridge_broker, "_get_bridge_dir", lambda: str(tmp_path))
    rc = bridge_broker.main([
        "enqueue", "--flow", "9000-02-ELOOP",
        "--from-role", "9000-execution-decomposer", "--to-role", "9000-implementer",
        "--id", "19", "--action", "signal-send", "--db-path", str(db),
    ])
    assert rc == 0
    conn = sqlite3.connect(str(db))
    assert conn.execute("SELECT count(*) FROM bridge_dispatch_queue").fetchone()[0] == 1
