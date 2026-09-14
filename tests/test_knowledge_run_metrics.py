import sys

sys.dont_write_bytecode = True

import json

from knowledge.run_metrics import collect_run_metrics

CANONICAL_KEYS = {
    "tool_calls",
    "tokens",
    "time_to_first_implementation",
    "total_execution_time",
    "review_failures",
    "rework",
}


def test_exactly_six_canonical_keys_all_int(tmp_path):
    metrics = collect_run_metrics(tmp_path)
    assert set(metrics) == CANONICAL_KEYS
    for value in metrics.values():
        assert type(value) is int


def test_missing_run_dir_all_zero(tmp_path):
    metrics = collect_run_metrics(tmp_path / "does-not-exist")
    assert metrics == {key: 0 for key in CANONICAL_KEYS}


def test_total_execution_time_from_ledger_timestamps(tmp_path):
    (tmp_path / "RUN-LEDGER.md").write_text(
        "## 2026-09-12T00:00:00Z — run started\n"
        "## 2026-09-12T00:10:00Z — run closed\n",
        encoding="utf-8",
    )
    metrics = collect_run_metrics(tmp_path)
    assert metrics["total_execution_time"] == 600


def test_time_to_first_implementation_from_cycle1_marker(tmp_path):
    (tmp_path / "RUN-LEDGER.md").write_text(
        "## 2026-09-12T00:00:00Z — run started\n"
        "## 2026-09-12T00:03:00Z — cycle 1: result written\n"
        "## 2026-09-12T00:10:00Z — run closed\n",
        encoding="utf-8",
    )
    metrics = collect_run_metrics(tmp_path)
    assert metrics["time_to_first_implementation"] == 180
    assert metrics["total_execution_time"] == 600


def test_unparsable_ledger_yields_zero_not_crash(tmp_path):
    (tmp_path / "RUN-LEDGER.md").write_text(
        "no timestamps in this ledger\n", encoding="utf-8"
    )
    metrics = collect_run_metrics(tmp_path)
    assert metrics["total_execution_time"] == 0
    assert metrics["time_to_first_implementation"] == 0


def test_rejected_verdict_real_bold_format_counted(tmp_path):
    verdicts = tmp_path / "verdicts"
    verdicts.mkdir()
    (verdicts / "001.md").write_text("**Status:** REJECTED\n", encoding="utf-8")
    metrics = collect_run_metrics(tmp_path)
    assert metrics["review_failures"] == 1
    assert metrics["rework"] == 0


def test_bare_status_rejected_still_counted(tmp_path):
    verdicts = tmp_path / "verdicts"
    verdicts.mkdir()
    (verdicts / "001.md").write_text("Status: REJECTED\n", encoding="utf-8")
    metrics = collect_run_metrics(tmp_path)
    assert metrics["review_failures"] == 1
    assert metrics["rework"] == 0


def test_quoted_status_rejected_in_evidence_not_counted(tmp_path):
    verdicts = tmp_path / "verdicts"
    verdicts.mkdir()
    (verdicts / "001.md").write_text(
        "Evidence: the string Status: REJECTED appeared only in prose.\n",
        encoding="utf-8",
    )
    metrics = collect_run_metrics(tmp_path)
    assert metrics["review_failures"] == 0
    assert metrics["rework"] == 0


def test_rejected_counted_once_per_file_not_per_occurrence(tmp_path):
    verdicts = tmp_path / "verdicts"
    verdicts.mkdir()
    (verdicts / "001.md").write_text(
        "**Status:** REJECTED\n**Status:** REJECTED\n", encoding="utf-8"
    )
    (tmp_path / "notes.txt").write_text("**Status:** REJECTED\n", encoding="utf-8")
    metrics = collect_run_metrics(tmp_path)
    assert metrics["review_failures"] == 1
    assert metrics["rework"] == 0


def test_approved_verdict_with_fenced_rejected_quote_counts_zero(tmp_path):
    verdicts = tmp_path / "verdicts"
    verdicts.mkdir()
    (verdicts / "001.md").write_text(
        "**Status:** APPROVED\n"
        "\n"
        "```\n"
        "**Status:** REJECTED\n"
        "```\n",
        encoding="utf-8",
    )
    metrics = collect_run_metrics(tmp_path)
    assert metrics["review_failures"] == 0
    assert metrics["rework"] == 0


def test_metrics_json_supplies_tool_calls_and_tokens(tmp_path):
    (tmp_path / "metrics.json").write_text(
        json.dumps({"tool_calls": 7, "tokens": 1234}), encoding="utf-8"
    )
    metrics = collect_run_metrics(tmp_path)
    assert metrics["tool_calls"] == 7
    assert metrics["tokens"] == 1234


def test_metrics_json_absent_is_zero(tmp_path):
    metrics = collect_run_metrics(tmp_path)
    assert metrics["tool_calls"] == 0
    assert metrics["tokens"] == 0


def test_metrics_json_invalid_or_wrong_types_are_zero(tmp_path):
    metrics_path = tmp_path / "metrics.json"

    metrics_path.write_text("{not json", encoding="utf-8")
    metrics = collect_run_metrics(tmp_path)
    assert metrics["tool_calls"] == 0
    assert metrics["tokens"] == 0

    metrics_path.write_text("[]", encoding="utf-8")
    metrics = collect_run_metrics(tmp_path)
    assert metrics["tool_calls"] == 0
    assert metrics["tokens"] == 0

    for bad_value in (-1, 1.5, True, "7"):
        metrics_path.write_text(
            json.dumps({"tool_calls": bad_value, "tokens": bad_value}),
            encoding="utf-8",
        )
        metrics = collect_run_metrics(tmp_path)
        assert metrics["tool_calls"] == 0
        assert metrics["tokens"] == 0


def test_negative_total_execution_time_clamped_to_zero(tmp_path):
    (tmp_path / "RUN-LEDGER.md").write_text(
        "## 2026-09-12T00:10:00Z — started\n"
        "## 2026-09-12T00:00:00Z — closed\n",
        encoding="utf-8",
    )
    metrics = collect_run_metrics(tmp_path)
    assert metrics["total_execution_time"] == 0


def test_negative_time_to_first_implementation_clamped_to_zero(tmp_path):
    (tmp_path / "RUN-LEDGER.md").write_text(
        "## 2026-09-12T00:10:00Z — started\n"
        "## 2026-09-12T00:00:00Z — cycle 1: result written\n",
        encoding="utf-8",
    )
    metrics = collect_run_metrics(tmp_path)
    assert metrics["time_to_first_implementation"] == 0


def test_collector_never_writes_to_run_dir(tmp_path):
    (tmp_path / "RUN-LEDGER.md").write_text(
        "## 2026-09-12T00:00:00Z — started\n"
        "## 2026-09-12T00:10:00Z — closed\n",
        encoding="utf-8",
    )
    verdicts = tmp_path / "verdicts"
    verdicts.mkdir()
    (verdicts / "001.md").write_text("**Status:** REJECTED\n", encoding="utf-8")
    (tmp_path / "metrics.json").write_text(
        '{"tool_calls": 3, "tokens": 100}\n', encoding="utf-8"
    )

    def snapshot():
        entries = {}
        for path in sorted(tmp_path.rglob("*")):
            if path.is_file():
                stat = path.stat()
                entries[str(path.relative_to(tmp_path))] = (
                    stat.st_mtime_ns,
                    stat.st_size,
                )
        return entries

    before = snapshot()
    collect_run_metrics(tmp_path)
    collect_run_metrics(tmp_path)
    after = snapshot()
    assert after == before


def test_harness_main_returns_zero_under_pytest_argv(capsys):
    import importlib.util

    from pathlib import Path

    script_path = (
        Path(__file__).resolve().parent.parent / "scripts" / "knowledge_eval.py"
    )
    spec = importlib.util.spec_from_file_location(
        "knowledge_eval_harness", script_path
    )
    knowledge_eval_harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(knowledge_eval_harness)

    saved_argv = sys.argv
    sys.argv = ["pytest", "tests/test_knowledge_eval.py", "-q"]
    try:
        assert knowledge_eval_harness.main() == 0
    finally:
        sys.argv = saved_argv


def test_run_start_is_the_started_line_not_the_promoted_line(tmp_path):
    run_name = tmp_path.name
    (tmp_path / "RUN-LEDGER.md").write_text(
        "## 2026-09-12T00:00:00Z — promoted from GOAL-DRAFT-017.md by cli\n"
        f"## 2026-09-12T00:05:00Z — run {run_name} started (FlowRunner run x), cycle 1\n"
        "## 2026-09-12T00:08:00Z — cycle 1: result written by implementer-reviewer\n"
        "## 2026-09-12T00:15:00Z — run closed\n",
        encoding="utf-8",
    )
    metrics = collect_run_metrics(tmp_path)
    assert metrics["total_execution_time"] == 600      # 00:05 -> 00:15
    assert metrics["time_to_first_implementation"] == 180  # 00:05 -> 00:08


def test_rework_counts_corrective_handoffs_independently_of_rejections(tmp_path):
    (tmp_path / "RUN-LEDGER.md").write_text(
        "## 2026-09-12T00:00:00Z — run started\n"
        "## 2026-09-12T00:01:00Z — cycle 1: handoff 001 written by decomposer-implementer\n"
        "## 2026-09-12T00:02:00Z — cycle 2: handoff 002 written by decomposer-implementer\n"
        "## 2026-09-12T00:03:00Z — cycle 3: handoff 003 written by decomposer-implementer\n"
        "## 2026-09-12T00:05:00Z — run closed\n",
        encoding="utf-8",
    )
    verdicts = tmp_path / "verdicts"
    verdicts.mkdir()
    (verdicts / "001.md").write_text("**Status:** REJECTED\n", encoding="utf-8")
    metrics = collect_run_metrics(tmp_path)
    assert metrics["review_failures"] == 1
    assert metrics["rework"] == 2


def _load_script():
    """Load scripts/knowledge_run_metrics.py without making scripts a package."""
    import importlib.util

    from pathlib import Path

    script_path = (
        Path(__file__).resolve().parent.parent
        / "scripts"
        / "knowledge_run_metrics.py"
    )
    spec = importlib.util.spec_from_file_location(
        "knowledge_run_metrics_under_test", script_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _empty_db(db_path):
    import sqlite3

    sqlite3.connect(db_path).close()


def _patch_db_path(monkeypatch, db_path):
    import config

    monkeypatch.setattr(config, "get_db_path", lambda: str(db_path))


def _session_event(event_name, session_id, tool=None, usage=None):
    obj = {
        "protocol_version": "1",
        "event": event_name,
        "session_id": session_id,
    }
    if tool is not None:
        obj["tool"] = tool
    if usage is not None:
        obj["usage"] = usage
    return json.dumps(obj)


def test_script_derives_tool_calls_and_tokens_from_session_events(
    tmp_path, monkeypatch
):
    script = _load_script()
    db_path = tmp_path / "metrics.db"
    _empty_db(db_path)
    _patch_db_path(monkeypatch, db_path)

    run_dir = tmp_path / "037"
    run_dir.mkdir()
    (run_dir / "RUN-LEDGER.md").write_text(
        "- 2026-09-14T15:21:49Z run 037 started "
        "(FlowRunner run 6cc9ba5be6749482), cycle 1\n",
        encoding="utf-8",
    )

    runtime_root = tmp_path / "runtime"
    run_state_dir = runtime_root / "runs" / "6cc9ba5be6749482"
    run_state_dir.mkdir(parents=True)
    (run_state_dir / "run.json").write_text(
        json.dumps(
            {
                "harness_sessions": [
                    {
                        "session_id": "s1",
                        "step": "decomposer-implementer",
                        "started_at": "2026-09-14T00:00:00Z",
                        "ended_at": "2026-09-14T00:01:00Z",
                    },
                    {
                        "session_id": "s2",
                        "step": "implementer-reviewer",
                        "started_at": "2026-09-14T00:01:00Z",
                        "ended_at": "2026-09-14T00:02:00Z",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    sessions_dir = tmp_path / "sessions"
    (sessions_dir / "s1").mkdir(parents=True)
    (sessions_dir / "s2").mkdir(parents=True)
    (sessions_dir / "s1" / "events.jsonl").write_text(
        "\n".join(
            [
                _session_event("tool_call", "s1", tool="read_file"),
                _session_event("tool_call", "s1", tool="grep"),
                _session_event(
                    "usage",
                    "s1",
                    usage={
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "reasoning_tokens": 5,
                    },
                ),
                _session_event(
                    "usage",
                    "s1",
                    usage={
                        "prompt_tokens": 1,
                        "completion_tokens": 2,
                        "reasoning_tokens": 3,
                    },
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (sessions_dir / "s2" / "events.jsonl").write_text(
        "\n".join(
            [
                _session_event("tool_call", "s2", tool="write_file"),
                _session_event(
                    "usage",
                    "s2",
                    usage={
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                        "reasoning_tokens": 25,
                    },
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        script.main(
            [
                "--run",
                str(run_dir),
                "--runtime-root",
                str(runtime_root),
                "--sessions-dir",
                str(sessions_dir),
            ]
        )
        == 0
    )
    payload = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert payload["tool_calls"] == 3
    assert payload["tokens"] == 216
    assert sorted(payload["sessions"]) == ["s1", "s2"]


def test_script_counts_knowledge_search_calls_as_retrieval_events(
    tmp_path, monkeypatch
):
    import sqlite3

    script = _load_script()
    db_path = tmp_path / "retrieval.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE knowledge_retrieval_log (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                provider              TEXT NOT NULL,
                scope                 TEXT NOT NULL,
                query                 TEXT NOT NULL,
                result_count          INTEGER NOT NULL DEFAULT 0,
                sources               TEXT NOT NULL DEFAULT '[]',
                retrieved_token_count INTEGER NOT NULL DEFAULT 0,
                retrieval_duration_ms INTEGER NOT NULL DEFAULT 0,
                agent_role            TEXT,
                run_id                TEXT,
                handoff_id            TEXT,
                created_at            TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.execute(
            "INSERT INTO knowledge_retrieval_log "
            "(provider, scope, query, handoff_id) VALUES (?, ?, ?, ?)",
            ("p", "s", "q", "001-decomposer-implementer"),
        )
        conn.execute(
            "INSERT INTO knowledge_retrieval_log "
            "(provider, scope, query, handoff_id) VALUES (?, ?, ?, ?)",
            ("p", "s", "q", "tg3-038"),
        )
        conn.commit()
    finally:
        conn.close()
    _patch_db_path(monkeypatch, db_path)

    run_dir = tmp_path / "037"
    (run_dir / "handoffs").mkdir(parents=True)
    (run_dir / "handoffs" / "001-decomposer-implementer.md").write_text(
        "handoff\n", encoding="utf-8"
    )
    (run_dir / "RUN-LEDGER.md").write_text(
        "- 2026-09-14T15:21:49Z run 037 started "
        "(FlowRunner run 6cc9ba5be6749482), cycle 1\n",
        encoding="utf-8",
    )

    runtime_root = tmp_path / "runtime"
    run_state_dir = runtime_root / "runs" / "6cc9ba5be6749482"
    run_state_dir.mkdir(parents=True)
    (run_state_dir / "run.json").write_text(
        json.dumps(
            {
                "harness_sessions": [
                    {
                        "session_id": "s1",
                        "step": "decomposer-implementer",
                        "started_at": "2026-09-14T00:00:00Z",
                        "ended_at": "2026-09-14T00:01:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    sessions_dir = tmp_path / "sessions"
    (sessions_dir / "s1").mkdir(parents=True)
    (sessions_dir / "s1" / "events.jsonl").write_text(
        "\n".join(
            [
                _session_event("tool_call", "s1", tool="knowledge_search"),
                _session_event("tool_call", "s1", tool="grep"),
                _session_event(
                    "usage",
                    "s1",
                    usage={
                        "prompt_tokens": 7,
                        "completion_tokens": 8,
                        "reasoning_tokens": 9,
                    },
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        script.main(
            [
                "--run",
                str(run_dir),
                "--runtime-root",
                str(runtime_root),
                "--sessions-dir",
                str(sessions_dir),
            ]
        )
        == 0
    )
    payload = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert payload["tool_calls"] == 2
    assert payload["retrieval_events"] == 2


def test_script_reports_missing_state_and_writes_nothing_on_dry_run(
    tmp_path, monkeypatch, capsys
):
    script = _load_script()
    db_path = tmp_path / "empty.db"
    _empty_db(db_path)
    _patch_db_path(monkeypatch, db_path)

    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    sessions_dir = tmp_path / "sessions"

    missing_dir = tmp_path / "040"
    missing_dir.mkdir()
    (missing_dir / "RUN-LEDGER.md").write_text(
        "- 2026-09-14T00:00:00Z run 040 started "
        "(FlowRunner run nope), cycle 1\n",
        encoding="utf-8",
    )
    missing_argv = [
        "--run",
        str(missing_dir),
        "--runtime-root",
        str(runtime_root),
        "--sessions-dir",
        str(sessions_dir),
    ]

    assert script.main(missing_argv + ["--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["tool_calls"] == 0
    assert not (missing_dir / "metrics.json").exists()

    assert script.main(missing_argv) == 0
    err = capsys.readouterr().err
    assert "nope" in err
    payload = json.loads((missing_dir / "metrics.json").read_text(encoding="utf-8"))
    assert payload["tool_calls"] == 0
    assert payload["sessions"] == []

    formed_dir = tmp_path / "041"
    formed_dir.mkdir()
    (formed_dir / "RUN-LEDGER.md").write_text(
        "- 2026-09-14T00:00:00Z run 041 started "
        "(FlowRunner run goodrun), cycle 1\n",
        encoding="utf-8",
    )
    run_state_dir = runtime_root / "runs" / "goodrun"
    run_state_dir.mkdir(parents=True)
    (run_state_dir / "run.json").write_text(
        json.dumps({"harness_sessions": []}), encoding="utf-8"
    )
    formed_argv = [
        "--run",
        str(formed_dir),
        "--runtime-root",
        str(runtime_root),
        "--sessions-dir",
        str(sessions_dir),
    ]

    assert script.main(formed_argv + ["--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["tool_calls"] == 0
    assert not (formed_dir / "metrics.json").exists()
