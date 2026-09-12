"""Read-only metric collector for a FlowRunner run directory.

The evaluation harness needs durable signals from a completed run: total
execution time and time-to-first-implementation are measured from the
``RUN-LEDGER.md`` timestamps, rejected verdicts are counted from
``verdicts/*.md``, and tool-call / token numbers are only reported when a
run directory carries an explicit ``metrics.json``. This module opens
nothing for writing and never creates files, directories, caches, or
database connections.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

# ISO-8601 UTC timestamps as they appear in RUN-LEDGER.md prose. The offset
# accepts both ``Z`` and ``+HH:MM`` / ``+HHMM`` forms.
_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:?\d{2})"
)

_CYCLE1_MARKER = "cycle 1: result written"

# A whole-line REJECTED status declaration. Verdict files use markdown bold
# (``**Status:** REJECTED``), so markdown asterisks are removed from each
# line before this pattern is applied.
_REJECTED_LINE_RE = re.compile(r"^Status:\s*REJECTED$")


def _parse_timestamp(text: str) -> datetime:
    """Parse one ISO-8601 timestamp match into an aware datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _read_ledger_text(run_path: Path) -> str:
    """Return RUN-LEDGER.md text, or ``""`` when it is missing/unreadable."""
    try:
        return run_path.joinpath("RUN-LEDGER.md").read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return ""


def _ledger_timestamps(ledger_text: str) -> list[datetime]:
    """Return every parseable ISO-8601 timestamp in ledger document order."""
    timestamps: list[datetime] = []
    for match in _TIMESTAMP_RE.finditer(ledger_text):
        try:
            timestamps.append(_parse_timestamp(match.group(0)))
        except ValueError:
            continue
    return timestamps


def _first_cycle1_timestamp(ledger_text: str) -> datetime | None:
    """Return the timestamp of the first ``cycle 1: result written`` line."""
    for line in ledger_text.splitlines():
        if _CYCLE1_MARKER in line:
            match = _TIMESTAMP_RE.search(line)
            if match is None:
                return None
            try:
                return _parse_timestamp(match.group(0))
            except ValueError:
                return None
    return None


def _line_declares_rejected(line: str) -> bool:
    """Return True when line is a REJECTED status declaration.

    Verdict files in this repository use ``**Status:** REJECTED`` (markdown
    bold), so the bare literal ``Status: REJECTED`` never occurs on a real
    status line. This normalizer removes ``*`` characters and trims the line,
    then requires the whole remaining line to be a status declaration; an
    inline quote inside evidence prose does not match.
    """
    normalized = line.replace("*", "").strip()
    return _REJECTED_LINE_RE.match(normalized) is not None


def _count_rejected_verdicts(run_path: Path) -> int:
    """Count verdict files in ``verdicts/`` whose text contains a REJECTED
    status line (markdown bold tolerated), not any inline mention.
    """
    verdicts_dir = run_path.joinpath("verdicts")
    try:
        verdict_files = list(verdicts_dir.glob("*.md"))
    except OSError:
        return 0

    rejected = 0
    for verdict_file in verdict_files:
        try:
            text = verdict_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(_line_declares_rejected(line) for line in text.splitlines()):
            rejected += 1
    return rejected


def _metrics_payload(run_path: Path) -> dict:
    """Return metrics.json as a dict, or ``{}`` when absent/invalid."""
    metrics_path = run_path.joinpath("metrics.json")
    try:
        raw = metrics_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    try:
        payload = json.loads(raw)
    except ValueError:
        return {}

    if not isinstance(payload, dict):
        return {}
    return payload


def _non_negative_int(payload: dict, key: str) -> int:
    """Return ``payload[key]`` when it is a non-negative integer, else 0."""
    value = payload.get(key, 0)
    if type(value) is int and value >= 0:
        return value
    return 0


def collect_run_metrics(run_dir) -> dict[str, int]:
    """Collect the six canonical metrics from a run directory.

    ``run_dir`` is a path-like or string naming a FlowRunner run directory.
    Every returned value is an ``int``; any missing or unreadable source is
    the zero state rather than a crash. The function only reads files and
    never writes into the run directory it measures. Both duration values
    are clamped to ``0`` when the parsed timestamps would produce a negative
    interval.
    """
    run_path = Path(run_dir)
    ledger_text = _read_ledger_text(run_path)
    timestamps = _ledger_timestamps(ledger_text)

    total_execution_time = 0
    if len(timestamps) >= 2:
        first_ts = timestamps[0]
        last_ts = timestamps[-1]
        total_execution_time = max(0, int((last_ts - first_ts).total_seconds()))

    time_to_first_implementation = 0
    cycle1_ts = _first_cycle1_timestamp(ledger_text)
    if timestamps and cycle1_ts is not None:
        first_ts = timestamps[0]
        time_to_first_implementation = max(
            0, int((cycle1_ts - first_ts).total_seconds())
        )

    rejected = _count_rejected_verdicts(run_path)
    payload = _metrics_payload(run_path)

    return {
        "tool_calls": _non_negative_int(payload, "tool_calls"),
        "tokens": _non_negative_int(payload, "tokens"),
        "time_to_first_implementation": time_to_first_implementation,
        "total_execution_time": total_execution_time,
        "review_failures": rejected,
        "rework": rejected,
    }
