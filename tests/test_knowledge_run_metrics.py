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
