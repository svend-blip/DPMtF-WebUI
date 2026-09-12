"""In-process tests for ``scripts/knowledge_success_gate.py`` (WORK 2, GOAL-DRAFT-011).

These tests pin the gate's two contracts: ``main()`` returns an ``int`` (it
never raises ``SystemExit`` from pytest's ``sys.argv``) and prints exactly the
six ``criterion_N PASS``/``FAIL`` lines, and each criterion is non-vacuous —
every one can be driven RED by a wrong input, not just green-path exercised.

Loading the gate via ``importlib.util`` from its absolute path keeps the import
independent of ``sys.path`` ordering and avoids creating a ``__pycache__``
file. One import side effect remains: the gate's ``import app`` appends a few
bytes to the gitignored ``logs/app.log`` (an ``app.py`` FileHandler side
effect), which is not a repository mutation by this test file.

Every write these tests perform goes to pytest's ``tmp_path`` (throwaway
SQLite DBs and the empty manifest for criterion 1). No test writes to the
repository, and the production ``databases/dpmtf.db`` is never opened.
"""

import sys

sys.dont_write_bytecode = True

import importlib.util
import sqlite3
from pathlib import Path

import pytest

_GATE_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "knowledge_success_gate.py"
)


@pytest.fixture(scope="session")
def gate_module():
    """Load the gate as a module without depending on sys.path or pycache."""
    spec = importlib.util.spec_from_file_location("knowledge_success_gate", _GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def tmp_db(tmp_path, gate_module):
    """Function-scoped throwaway DB carrying the full 107 knowledge schema.

    The gate's criterion functions patch ``config.get_db_path`` themselves;
    this fixture only supplies the isolated path to keep C2/C3/C4 off the
    production database.
    """
    db_path = tmp_path / "knowledge_gate_test.db"
    gate_module._seed_schema_db(str(db_path))
    return str(db_path)


def _insert_one_retrieval_row(db_path: str) -> None:
    """Insert exactly one ``knowledge_retrieval_log`` row, parameterized SQL."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO knowledge_retrieval_log "
            "(provider, scope, query, result_count, sources, "
            "retrieved_token_count, retrieval_duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("test_provider", "test_scope", "test query", 1, "[]", 1, 1),
        )
        conn.commit()
    finally:
        conn.close()


def _fat_document(index: int) -> dict:
    """One document whose rendered token count is far over the default budget."""
    content = " ".join(["token"] * 2000)
    return {"path": f"fat-{index}.md", "content": content}


def test_gate_main_prints_six_pass_lines_and_returns_zero(gate_module, capsys):
    result = gate_module.main()
    captured = capsys.readouterr()

    assert isinstance(result, int)
    assert result == 0
    assert captured.out == (
        "criterion_1 PASS\n"
        "criterion_2 PASS\n"
        "criterion_3 PASS\n"
        "criterion_4 PASS\n"
        "criterion_5 PASS\n"
        "criterion_6 PASS\n"
    )


def test_gate_main_returns_nonzero_when_a_criterion_fails(gate_module, monkeypatch, capsys):
    monkeypatch.setattr(
        gate_module, "criterion_1", lambda: ("criterion_1", False)
    )

    result = gate_module.main()
    captured = capsys.readouterr()

    assert result == 1
    assert "criterion_1 FAIL" in captured.out


def test_criterion_1_fails_when_indexer_produces_no_documents(gate_module, monkeypatch):
    # An indexer that produces zero documents writes an empty manifest (the
    # empty-repository shape) and returns success. The gate must reject it.
    # The real indexer always writes the manifest before returning 0, so this
    # is the honest RED shape for criterion 1.
    def _empty_manifest_indexer(argv):
        out_index = argv.index("--out") + 1
        Path(argv[out_index]).write_text("", encoding="utf-8")
        return 0

    monkeypatch.setattr(gate_module.knowledge_indexer, "main", _empty_manifest_indexer)

    name, ok = gate_module.criterion_1()

    assert name == "criterion_1"
    assert ok is False


def test_criterion_2_fails_on_empty_results(gate_module, monkeypatch, tmp_db):
    class _EmptyStub(gate_module._TemporaryStubProvider):
        def __init__(self):
            super().__init__(results=[])

    monkeypatch.setattr(gate_module, "_TemporaryStubProvider", _EmptyStub)

    name, ok = gate_module.criterion_2(tmp_db)

    assert name == "criterion_2"
    assert ok is False


def test_criterion_3_fails_on_blank_path(gate_module, monkeypatch, tmp_db):
    class _BlankPathStub(gate_module._TemporaryStubProvider):
        def __init__(self):
            super().__init__(results=[{"path": "", "content": "x"}])

    monkeypatch.setattr(gate_module, "_TemporaryStubProvider", _BlankPathStub)

    name, ok = gate_module.criterion_3(tmp_db)

    assert name == "criterion_3"
    assert ok is False


def test_criterion_4_fails_on_over_budget_results(gate_module, monkeypatch, tmp_db):
    class _FatStub(gate_module._TemporaryStubProvider):
        def __init__(self):
            super().__init__(results=[_fat_document(i) for i in range(8)])

    # Sanity: 8 docs x 2000 words must exceed the configured token budget
    # (12000 by default), so the token half of criterion 4 actually bites.
    max_tokens = gate_module.config.get_knowledge_max_context_tokens()
    assert max_tokens < 8 * 2000

    monkeypatch.setattr(gate_module, "_TemporaryStubProvider", _FatStub)

    name, ok = gate_module.criterion_4(tmp_db)

    assert name == "criterion_4"
    assert ok is False


def test_criterion_5_fails_when_a_log_row_preexists(gate_module, monkeypatch):
    def _seeded_create_temp_db(tmp_dir):
        db_path = tmp_dir / "gate.db"
        gate_module._seed_schema_db(str(db_path))
        _insert_one_retrieval_row(str(db_path))
        return str(db_path)

    monkeypatch.setattr(gate_module, "_create_temp_db", _seeded_create_temp_db)

    name, ok = gate_module.criterion_5()

    assert name == "criterion_5"
    assert ok is False


def test_criterion_6_fails_when_stub_is_a_none_provider(gate_module, monkeypatch):
    class _NoneStub(gate_module.NoneProvider):
        pass

    monkeypatch.setattr(gate_module, "_TemporaryStubProvider", _NoneStub)

    name, ok = gate_module.criterion_6()

    assert name == "criterion_6"
    assert ok is False
