import sys

sys.dont_write_bytecode = True

import importlib.util
import sqlite3
from pathlib import Path

import pytest

import config

_HARNESS_PATH = Path(__file__).resolve().parent.parent / "scripts" / "knowledge_eval.py"

METRIC_HEADINGS = (
    "tool_calls",
    "tokens",
    "time_to_first_implementation",
    "total_execution_time",
    "review_failures",
    "rework",
)

# Exact knowledge_retrieval_log schema from scripts/db/107_knowledge_tables.sql
# (table plus the two indexes it defines). The harness reads this table only;
# the fixture creates the real column set so the empty state is truthful.
_KNOWLEDGE_RETRIEVAL_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_retrieval_log (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    provider              TEXT NOT NULL,
    scope                 TEXT NOT NULL,
    query                 TEXT NOT NULL,
    result_count          INTEGER NOT NULL DEFAULT 0 CHECK (result_count >= 0),
    sources               TEXT NOT NULL DEFAULT '[]',
    retrieved_token_count INTEGER NOT NULL DEFAULT 0 CHECK (retrieved_token_count >= 0),
    retrieval_duration_ms INTEGER NOT NULL DEFAULT 0 CHECK (retrieval_duration_ms >= 0),
    agent_role            TEXT,
    run_id                TEXT,
    handoff_id            TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_knowledge_retrieval_log_scope_time
    ON knowledge_retrieval_log (scope, created_at);

CREATE INDEX IF NOT EXISTS idx_knowledge_retrieval_log_run
    ON knowledge_retrieval_log (run_id, handoff_id);
"""


def _load_harness():
    """Load scripts/knowledge_eval.py without making scripts a package."""
    spec = importlib.util.spec_from_file_location(
        "knowledge_eval_under_test", _HARNESS_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_schema(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_KNOWLEDGE_RETRIEVAL_LOG_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _seed_retrieval_rows(db_path, rows):
    """Insert `rows` retrieval-log rows using parameterized SQL only."""
    conn = sqlite3.connect(db_path)
    try:
        for i in range(1, rows + 1):
            conn.execute(
                "INSERT INTO knowledge_retrieval_log "
                "(provider, scope, query, result_count, sources, "
                " retrieved_token_count, retrieval_duration_ms, "
                " agent_role, run_id, handoff_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "test-provider",
                    "test-scope",
                    f"query {i}",
                    1,
                    "[]",
                    10,
                    5,
                    "implementer",
                    "run-007",
                    f"handoff-{i}",
                ),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Build a temp SQLite DB with the real knowledge_retrieval_log schema.

    The production DB is never opened: this fixture creates a brand-new file
    under pytest's tmp_path and monkeypatches config.get_db_path so the
    harness opens the temp file read-only. The monkeypatch is undone by
    pytest when the test tears down.
    """
    db_path = tmp_path / "knowledge_eval.db"
    _create_schema(db_path)
    monkeypatch.setattr(config, "get_db_path", lambda: str(db_path))
    return db_path


@pytest.fixture
def empty_db(tmp_path, monkeypatch):
    """Build a temp SQLite DB with no knowledge_retrieval_log table at all."""
    db_path = tmp_path / "knowledge_eval_empty.db"
    sqlite3.connect(db_path).close()
    monkeypatch.setattr(config, "get_db_path", lambda: str(db_path))
    return db_path


# Loaded after ``import config`` so the harness's own ``import config``
# reuses this already-imported (and later monkeypatched) module object.
knowledge_eval = _load_harness()


def test_report_prints_both_arms_and_required_metric_names(temp_db, capsys):
    assert knowledge_eval.main() == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines.count("with_retrieval") == 1
    assert lines.count("without_retrieval") == 1
    for metric in METRIC_HEADINGS:
        assert lines.count(f"{metric} 0") >= 2
    assert "commissioning_procedure" in lines


def test_with_arm_counts_seeded_retrieval_rows(temp_db, capsys):
    _seed_retrieval_rows(temp_db, 3)
    assert knowledge_eval.main() == 0
    out = capsys.readouterr().out
    assert "with_retrieval\nretrieval_events 3" in out
    assert "without_retrieval\nretrieval_events 0" in out


def test_commissioning_procedure_documents_arms_and_output_location(temp_db, capsys):
    assert knowledge_eval.main() == 0
    out = capsys.readouterr().out
    assert "with retrieval enabled" in out
    assert "with retrieval disabled" in out
    assert "print this script's stdout" in out
    assert "run_id" in out
    assert "handoff_id" in out
    assert (
        "without_retrieval arm comes from execution records with "
        "no matching knowledge_retrieval_log row"
    ) in out


def test_missing_table_yields_empty_report(empty_db, capsys):
    assert knowledge_eval.main() == 0
    out = capsys.readouterr().out
    assert "with_retrieval\nretrieval_events 0" in out
    assert "without_retrieval\nretrieval_events 0" in out
    for metric in METRIC_HEADINGS:
        assert f"{metric} 0" in out


def test_missing_db_file_yields_empty_report(tmp_path, monkeypatch, capsys):
    missing = tmp_path / "nope.db"
    monkeypatch.setattr(config, "get_db_path", lambda: str(missing))
    assert knowledge_eval.main() == 0
    out = capsys.readouterr().out
    assert "with_retrieval\nretrieval_events 0" in out
    assert "without_retrieval\nretrieval_events 0" in out
    for metric in METRIC_HEADINGS:
        assert f"{metric} 0" in out


def test_retrieval_events_are_counted_from_the_log_table(temp_db, tmp_path, capsys):
    with_dir = tmp_path / "014"
    without_dir = tmp_path / "013"
    with_dir.mkdir()
    without_dir.mkdir()

    conn = sqlite3.connect(temp_db)
    try:
        conn.execute(
            "INSERT INTO knowledge_retrieval_log "
            "(provider, scope, query, result_count, sources, "
            " retrieved_token_count, retrieval_duration_ms, "
            " agent_role, run_id, handoff_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "test-provider",
                "test-scope",
                "query 1",
                1,
                "[]",
                10,
                5,
                "implementer",
                "014",
                "handoff-1",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    assert (
        knowledge_eval.main(
            ["--with-run", str(with_dir), "--without-run", str(without_dir)]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "with_retrieval\nretrieval_events 1" in out
    assert "without_retrieval\nretrieval_events 0" in out


def test_metric_values_honor_available_columns():
    assert knowledge_eval._metric_values(set()) == {}
    assert knowledge_eval._metric_values({"tool_calls", "tokens"}) == {
        "tool_calls": 0,
        "tokens": 0,
    }
    assert knowledge_eval._metric_values(set(METRIC_HEADINGS)) == {
        metric: 0 for metric in METRIC_HEADINGS
    }
