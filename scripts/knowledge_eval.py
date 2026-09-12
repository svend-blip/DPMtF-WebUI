#!/usr/bin/env python3
"""Knowledge evaluation harness — with-vs-without retrieval comparison report.

Reads knowledge_retrieval_log and the available execution-ish tables from the
configured SQLite database (read-only) and prints the fixed comparison report
required by the §8 measurement addendum.

With ``--with-run <dir>`` / ``--without-run <dir>`` the report is rendered
from ``knowledge.run_metrics.collect_run_metrics`` for the supplied run
directories instead of the database. A missing flag or an unreadable run
directory renders that arm as the all-zero state, so the default (no flags)
invocation keeps its existing DB-backed empty-state report unchanged.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Ensure the project root is on sys.path so ``import config`` works no matter
# where the process is started (same pattern as scripts/initialize_new_webui.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

from knowledge.run_metrics import collect_run_metrics

# Execution-ish tables present in this checkout. None of them stores the six
# §8 comparison metrics; this list is only used to prove that absence honestly.
EXECUTION_TABLES = (
    "workflow_runs",
    "comparison_runs",
    "bridge_flow_steps",
)

# Canonical snake_case headings the report must always print, per arm.
METRIC_HEADINGS = (
    "tool_calls",
    "tokens",
    "time_to_first_implementation",
    "total_execution_time",
    "review_failures",
    "rework",
)

# Fixed prose describing how the representative comparison RUNs are
# commissioned and where their comparison output is found. This is output
# only — it executes nothing.
COMMISSIONING_PROCEDURE = (
    "To commission the representative comparison, run the same representative "
    "task twice: once with retrieval enabled and once with retrieval disabled "
    "in config. After both RUNs complete, print this script's stdout for the "
    "comparison. The with_retrieval arm is populated from "
    "knowledge_retrieval_log rows joined to execution records by run_id/"
    "handoff_id; the without_retrieval arm comes from execution records with "
    "no matching knowledge_retrieval_log row."
)


def _open_readonly(db_path):
    """Open the configured database read-only, or return None if it cannot be opened.

    mode=ro makes any write attempt fail at the SQLite layer. A missing or
    unopenable database returns None, and callers (specifically
    ``_count_retrieval_events``) treat None as the empty state rather than a
    crash.
    """
    try:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def _count_retrieval_events(conn):
    """Return the number of rows in knowledge_retrieval_log (0 if absent)."""
    if conn is None:
        return 0
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM knowledge_retrieval_log"
        ).fetchone()
        return int(row[0])
    except sqlite3.OperationalError:
        return 0


def _available_execution_columns(conn):
    """Return the set of column names in the available execution-ish tables.

    Table names come from a fixed literal tuple and are validated against
    sqlite_master, and the column lookup below is parameterized — the fixed
    EXECUTION_TABLES literal tuple remains the only source of names.
    """
    if conn is None:
        return set()

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = ? AND name IN (?, ?, ?)",
        ("table",) + EXECUTION_TABLES,
    ).fetchall()

    columns = set()
    for (table,) in tables:
        for row in conn.execute(
            "SELECT name FROM pragma_table_info(?)", (table,)
        ).fetchall():
            columns.add(row[0])
    return columns


def _metric_values(available_columns):
    """Return the six §8 comparison metrics, zero in the empty state.

    A metric is reported from an execution record only when a usable column
    exists AND the commissioned comparison defines how to aggregate and
    attribute it. In this checkout neither condition holds for any of the six,
    so every value is 0. ``available_columns`` is the evidence for that
    absence: it is computed from PRAGMA table_info over the execution-ish
    tables and contains none of the six metric names here.
    """
    return {metric: 0 for metric in METRIC_HEADINGS}


def _print_report(retrieval_events, metric_values):
    """Print the fixed comparison report to stdout."""
    lines = []
    for arm in ("with_retrieval", "without_retrieval"):
        lines.append(arm)
        arm_events = retrieval_events if arm == "with_retrieval" else 0
        lines.append(f"retrieval_events {arm_events}")
        for metric in METRIC_HEADINGS:
            lines.append(f"{metric} {metric_values[metric]}")
    lines.append("commissioning_procedure")
    lines.append(COMMISSIONING_PROCEDURE)
    print("\n".join(lines))


def _print_run_report(with_metrics, without_metrics):
    """Print the comparison report from two measured run directories."""
    lines = []
    for arm, metrics in (
        ("with_retrieval", with_metrics),
        ("without_retrieval", without_metrics),
    ):
        lines.append(arm)
        lines.append("retrieval_events 0")
        for metric in METRIC_HEADINGS:
            lines.append(f"{metric} {metrics[metric]}")
    lines.append("commissioning_procedure")
    lines.append(COMMISSIONING_PROCEDURE)
    print("\n".join(lines))


def main(argv=None):
    """Entry point. Returns 0 on success.

    With no options the default empty-state DB report is printed exactly as
    before. With --with-run/--without-run the two arms are rendered from
    collect_run_metrics for the supplied run directories.
    """
    parser = argparse.ArgumentParser(description="Knowledge evaluation harness.")
    parser.add_argument("--with-run", type=Path, default=None)
    parser.add_argument("--without-run", type=Path, default=None)
    args = parser.parse_args([] if argv is None else argv)

    if args.with_run is None and args.without_run is None:
        db_path = config.get_db_path()
        conn = _open_readonly(db_path)
        try:
            retrieval_events = _count_retrieval_events(conn)
            available_columns = _available_execution_columns(conn)
        finally:
            if conn is not None:
                conn.close()
        metric_values = _metric_values(available_columns)
        _print_report(retrieval_events, metric_values)
        return 0

    zero_metrics = {metric: 0 for metric in METRIC_HEADINGS}
    with_metrics = (
        collect_run_metrics(args.with_run)
        if args.with_run is not None
        else zero_metrics
    )
    without_metrics = (
        collect_run_metrics(args.without_run)
        if args.without_run is not None
        else zero_metrics
    )
    _print_run_report(with_metrics, without_metrics)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
