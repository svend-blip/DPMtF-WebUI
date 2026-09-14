#!/usr/bin/env python3
"""Derive FlowRunner run metrics from session logs and write <run dir>/metrics.json.

Read-only CLI. For each ``--run`` directory it reads the run's RUN-LEDGER.md
to find the FlowRunner run ids, reads each ``<runtime-root>/runs/<id>/run.json``
to find the harness session ids, and reads each session's ``events.jsonl`` to
count ``tool_call`` events, sum ``prompt_tokens + completion_tokens +
reasoning_tokens`` over ``usage`` events, and count ``tool_call`` events whose
``tool`` is ``knowledge_search``. It then adds the database's
``knowledge_retrieval_log`` rows that name one of the run's handoffs and
writes ``<run dir>/metrics.json``. It never writes to the database, never
runs a chain/harness/model, and writes nothing but ``metrics.json`` (or, under
``--dry-run``, prints the JSON and writes nothing at all).
"""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

# Ensure the project root is on sys.path so ``import config`` works no matter
# where the process is started (same pattern as scripts/knowledge_eval.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config


_FLOWRUNNER_RUN_RE = re.compile(r"FlowRunner run ([0-9A-Za-z]+)")
_HANDOFF_NUM_RE = re.compile(r"^(\d+)")


def _note(message):
    """Report a non-fatal source problem on stderr without stopping."""
    print(f"knowledge_run_metrics: {message}", file=sys.stderr)


def _read_text(path):
    """Return file text, or None when the file is missing/unreadable."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _json_from_file(path):
    """Return a parsed JSON object, or None when missing/invalid."""
    text = _read_text(path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _flowrunner_run_ids(ledger_text):
    """Extract FlowRunner run ids from a ledger, de-duplicated and in order."""
    run_ids = []
    for match in _FLOWRUNNER_RUN_RE.finditer(ledger_text):
        run_id = match.group(1)
        if run_id not in run_ids:
            run_ids.append(run_id)
    return run_ids


def _session_ids_from_run_json(payload):
    """Return the harness session ids named by a run.json payload."""
    if not isinstance(payload, dict):
        return []
    sessions = payload.get("harness_sessions")
    if not isinstance(sessions, list):
        return []
    session_ids = []
    for entry in sessions:
        if isinstance(entry, dict) and isinstance(entry.get("session_id"), str):
            session_ids.append(entry["session_id"])
    return session_ids


def _int_or_zero(value):
    """Return ``value`` when it is an int, else 0."""
    return value if type(value) is int else 0


def _read_session_events(events_path, stats):
    """Count a session's events into ``stats``. Return True when read.

    The discriminator key is ``event`` (not ``type``). ``tool_call`` events
    increment ``tool_calls`` and — when ``tool`` is exactly
    ``knowledge_search`` — ``retrieval_events``; ``usage`` events contribute
    their prompt/completion/reasoning token sums to ``tokens``. A missing
    session log or an unreadable file is reported and counted as zero for
    that session, never raised.
    """
    events_path = Path(events_path)
    if not events_path.exists():
        _note(f"missing session log {events_path}")
        return False
    try:
        with events_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    _note(f"skipping malformed JSON line in {events_path}")
                    continue
                if not isinstance(obj, dict):
                    continue
                event = obj.get("event")
                if event == "tool_call":
                    stats["tool_calls"] += 1
                    if obj.get("tool") == "knowledge_search":
                        stats["retrieval_events"] += 1
                elif event == "usage":
                    usage = obj.get("usage")
                    if isinstance(usage, dict):
                        stats["tokens"] += (
                            _int_or_zero(usage.get("prompt_tokens"))
                            + _int_or_zero(usage.get("completion_tokens"))
                            + _int_or_zero(usage.get("reasoning_tokens"))
                        )
    except OSError as exc:
        _note(f"unreadable session log {events_path}: {exc}")
        return False
    return True


def _handoff_tokens(run_dir):
    """Return ``(run_num, stems, handoff_nums)`` for the DB matching rule."""
    run_path = Path(run_dir)
    run_num = run_path.name
    stems = []
    handoff_nums = []
    handoffs_dir = run_path / "handoffs"
    try:
        handoff_files = sorted(handoffs_dir.glob("*.md"))
    except OSError:
        handoff_files = []
    for handoff_file in handoff_files:
        stem = handoff_file.stem
        stems.append(stem.casefold())
        match = _HANDOFF_NUM_RE.match(stem)
        if match is not None:
            handoff_nums.append(match.group(1))
    return run_num, stems, handoff_nums


def _matching_db_row_count(handoff_ids, run_num, stems, handoff_nums):
    """Count retrieval-log rows whose handoff_id names a run handoff.

    A row counts when its ``handoff_id``, case-folded, either contains one of
    the run's handoff file stems verbatim, or contains both the run number and
    one of the run's zero-padded handoff numbers. Rows are counted, not
    distinct ids.
    """
    count = 0
    for handoff_id in handoff_ids:
        if not handoff_id:
            continue
        folded = handoff_id.casefold()
        if any(stem in folded for stem in stems):
            count += 1
            continue
        if any(run_num in folded and num in folded for num in handoff_nums):
            count += 1
    return count


def _count_db_retrieval_events(db_path, run_num, stems, handoff_nums):
    """Count matching retrieval-log rows; any SQLite problem is 0 + a note."""
    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT handoff_id FROM knowledge_retrieval_log "
            "WHERE handoff_id IS NOT NULL"
        ).fetchall()
    except (sqlite3.Error, ValueError) as exc:
        _note(f"database read skipped ({db_path}): {exc}")
        return 0
    finally:
        if conn is not None:
            conn.close()
    return _matching_db_row_count([row[0] for row in rows], run_num, stems, handoff_nums)


def _collect_run(run_dir, runtime_root, sessions_dir):
    """Derive the five metrics.json fields for one run directory."""
    run_path = Path(run_dir)
    runtime_root = Path(runtime_root)
    sessions_dir = Path(sessions_dir)

    sources = []
    stats = {"tool_calls": 0, "tokens": 0, "retrieval_events": 0}
    used_sessions = []

    ledger_path = run_path / "RUN-LEDGER.md"
    sources.append(str(ledger_path))
    ledger_text = _read_text(ledger_path)
    if ledger_text is None:
        _note(f"missing ledger {ledger_path}")
        ledger_text = ""

    run_ids = _flowrunner_run_ids(ledger_text)
    if not run_ids:
        _note(f"no FlowRunner run ids found in {ledger_path}")

    run_num, stems, handoff_nums = _handoff_tokens(run_path)

    for run_id in run_ids:
        run_json_path = runtime_root / "runs" / run_id / "run.json"
        sources.append(str(run_json_path))
        payload = _json_from_file(run_json_path)
        if payload is None:
            _note(f"missing or unreadable run state {run_json_path}")
            continue
        for session_id in _session_ids_from_run_json(payload):
            events_path = sessions_dir / session_id / "events.jsonl"
            sources.append(str(events_path))
            if _read_session_events(events_path, stats):
                used_sessions.append(session_id)

    db_path = config.get_db_path()
    sources.append(db_path)
    stats["retrieval_events"] += _count_db_retrieval_events(
        db_path, run_num, stems, handoff_nums
    )

    return {
        "tool_calls": stats["tool_calls"],
        "tokens": stats["tokens"],
        "retrieval_events": stats["retrieval_events"],
        "sessions": used_sessions,
        "sources": sources,
    }


def main(argv=None):
    """Entry point. Returns 0 on success (missing sources are never fatal)."""
    parser = argparse.ArgumentParser(
        description="Derive FlowRunner run metrics from session logs."
    )
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        type=Path,
        help="Run directory to measure (repeatable).",
    )
    parser.add_argument(
        "--runtime-root",
        required=True,
        type=Path,
        help="FlowRunner runtime root containing runs/<id>/run.json.",
    )
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=Path.home() / ".simple-harness" / "sessions",
        help="simple-harness sessions directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the JSON that would be written and write nothing.",
    )
    args = parser.parse_args([] if argv is None else argv)

    payloads = []
    for run_dir in args.run:
        payload = _collect_run(run_dir, args.runtime_root, args.sessions_dir)
        payloads.append(payload)
        if not args.dry_run:
            metrics_path = Path(run_dir) / "metrics.json"
            metrics_path.write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )

    if args.dry_run:
        for payload in payloads:
            print(json.dumps(payload, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
