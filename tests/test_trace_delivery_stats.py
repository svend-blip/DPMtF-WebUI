"""Tests for the trace_delivery_stats instrument (D2, Run 016).

The instrument reads a BridgeV002 trace log, filters by date and flow
prefix, classifies each event, and prints per-delivery lines followed
by a summary line. The fixture at ``tests/fixtures/trace_sample.log``
encodes the TG4/TG5 expectations: 2 delivered, 5 attempted-but-failed
(3 wrong-signal, 1 deliverable, 1 recipient).
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest


_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "scripts" / "trace_delivery_stats.py"
_FIXTURE = _REPO / "tests" / "fixtures" / "trace_sample.log"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def test_tg4_exact_counts_on_fixture():
    """TG4 rehearsal: the summary line contains 'DELIVERED 2 ATTEMPTS 5'."""
    result = _run(
        "--log", str(_FIXTURE),
        "--date", "2026-01-01",
        "--flow-prefix", "zz-",
    )
    assert result.returncode == 0, (
        f"instrument exited {result.returncode}: stderr={result.stderr!r}"
    )
    normalized = _normalize(result.stdout)
    assert "DELIVERED 2 ATTEMPTS 5" in normalized, (
        f"summary missing 'DELIVERED 2 ATTEMPTS 5': {normalized!r}"
    )


def test_tg5_three_failure_classes_separated():
    """TG5 rehearsal: the summary line shows all three failure class counts."""
    result = _run(
        "--log", str(_FIXTURE),
        "--date", "2026-01-01",
        "--flow-prefix", "zz-",
    )
    assert result.returncode == 0, (
        f"instrument exited {result.returncode}: stderr={result.stderr!r}"
    )
    normalized = _normalize(result.stdout)
    assert "WRONG_SIGNAL 3" in normalized, (
        f"summary missing 'WRONG_SIGNAL 3': {normalized!r}"
    )
    assert "DELIVERABLE 1" in normalized, (
        f"summary missing 'DELIVERABLE 1': {normalized!r}"
    )
    assert "RECIPIENT 1" in normalized, (
        f"summary missing 'RECIPIENT 1': {normalized!r}"
    )


def test_tg6_zero_delivery_for_non_matching_date():
    """TG6 rehearsal: a date with no matching entries yields DELIVERED 0."""
    result = _run(
        "--log", str(_FIXTURE),
        "--date", "1999-12-31",
        "--flow-prefix", "zz-",
    )
    assert result.returncode == 0, (
        f"instrument exited {result.returncode}: stderr={result.stderr!r}"
    )
    normalized = _normalize(result.stdout)
    assert "DELIVERED 0" in normalized, (
        f"summary missing 'DELIVERED 0': {normalized!r}"
    )


def test_missing_log_file_exits_nonzero(tmp_path):
    """A non-existent log file must produce a non-zero exit and a stderr message."""
    missing = tmp_path / "does_not_exist.log"
    result = _run(
        "--log", str(missing),
        "--date", "2026-01-01",
        "--flow-prefix", "zz-",
    )
    assert result.returncode != 0, (
        f"instrument should fail on missing log: stdout={result.stdout!r}"
    )
    assert result.stderr.strip(), "instrument must report error on stderr"


def test_empty_log_file_handled(tmp_path):
    """An empty log file must produce 'DELIVERED 0 ATTEMPTS 0 ...' without crashing."""
    empty = tmp_path / "empty.log"
    empty.write_text("")
    result = _run(
        "--log", str(empty),
        "--date", "2026-01-01",
        "--flow-prefix", "zz-",
    )
    assert result.returncode == 0, (
        f"empty log should not error: stderr={result.stderr!r}"
    )
    normalized = _normalize(result.stdout)
    assert "DELIVERED 0" in normalized, normalized
    assert "ATTEMPTS 0" in normalized, normalized
    assert "WRONG_SIGNAL 0" in normalized, normalized
    assert "DELIVERABLE 0" in normalized, normalized
    assert "RECIPIENT 0" in normalized, normalized


def test_invalid_date_format_exits_nonzero(tmp_path):
    """An invalid --date value must produce a non-zero exit."""
    empty = tmp_path / "x.log"
    empty.write_text("")
    result = _run(
        "--log", str(empty),
        "--date", "not-a-date",
        "--flow-prefix", "zz-",
    )
    assert result.returncode != 0, (
        f"instrument should fail on invalid date: stdout={result.stdout!r}"
    )


def test_per_delivery_lines_have_correct_counts():
    """The per-delivery lines must carry the right count for each handoff."""
    result = _run(
        "--log", str(_FIXTURE),
        "--date", "2026-01-01",
        "--flow-prefix", "zz-",
    )
    assert result.returncode == 0, (
        f"instrument exited {result.returncode}: stderr={result.stderr!r}"
    )
    lines = [
        line for line in result.stdout.splitlines()
        if line.startswith("delivery ")
    ]
    assert len(lines) == 7, (
        f"expected 7 per-delivery lines (2 delivered + 5 failed), got {len(lines)}"
    )

    pattern = re.compile(
        r"delivery (?P<hid>\S+) attempts=(?P<a>\d+) "
        r"delivered=(?P<d>true|false) "
        r"wrong_signal=(?P<w>\d+) "
        r"deliverable=(?P<b>\d+) "
        r"recipient=(?P<c>\d+)"
    )
    by_id = {}
    for line in lines:
        m = pattern.fullmatch(line)
        assert m is not None, f"malformed per-delivery line: {line!r}"
        by_id[m.group("hid")] = {
            "attempts": int(m.group("a")),
            "delivered": m.group("d") == "true",
            "wrong_signal": int(m.group("w")),
            "deliverable": int(m.group("b")),
            "recipient": int(m.group("c")),
        }

    assert by_id["1"]["delivered"] is True
    assert by_id["1"]["wrong_signal"] == 0
    assert by_id["1"]["deliverable"] == 0
    assert by_id["1"]["recipient"] == 0
    assert by_id["1"]["attempts"] == 0

    assert by_id["2"]["delivered"] is True
    assert by_id["2"]["attempts"] == 0

    assert by_id["10"]["delivered"] is False
    assert by_id["10"]["wrong_signal"] == 1
    assert by_id["10"]["deliverable"] == 0
    assert by_id["10"]["recipient"] == 0

    assert by_id["11"]["delivered"] is False
    assert by_id["11"]["wrong_signal"] == 1

    assert by_id["12"]["delivered"] is False
    assert by_id["12"]["wrong_signal"] == 1

    assert by_id["20"]["delivered"] is False
    assert by_id["20"]["wrong_signal"] == 0
    assert by_id["20"]["deliverable"] == 1
    assert by_id["20"]["recipient"] == 0

    assert by_id["30"]["delivered"] is False
    assert by_id["30"]["wrong_signal"] == 0
    assert by_id["30"]["deliverable"] == 0
    assert by_id["30"]["recipient"] == 1


def test_flow_prefix_filters_entries():
    """A non-matching flow prefix must yield zero deliveries."""
    result = _run(
        "--log", str(_FIXTURE),
        "--date", "2026-01-01",
        "--flow-prefix", "zz-other-",
    )
    assert result.returncode == 0
    normalized = _normalize(result.stdout)
    assert "DELIVERED 0" in normalized
    assert "ATTEMPTS 0" in normalized


def test_summary_line_uses_two_space_separators():
    """The summary line must use exactly two spaces between label/value pairs."""
    result = _run(
        "--log", str(_FIXTURE),
        "--date", "2026-01-01",
        "--flow-prefix", "zz-",
    )
    assert result.returncode == 0
    summary = [
        line for line in result.stdout.splitlines()
        if line.startswith("DELIVERED ")
    ]
    assert len(summary) == 1, f"expected one summary line, got {len(summary)}"
    line = summary[-1]
    expected = (
        "DELIVERED 2  ATTEMPTS 5  WRONG_SIGNAL 3  "
        "DELIVERABLE 1  RECIPIENT 1"
    )
    assert line == expected, f"summary line mismatch:\n got: {line!r}\nwant: {expected!r}"