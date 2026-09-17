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

# Attribution fields carried by each knowledge_retrieval_log row, and the
# number of most-recent rows the attribution section reads. These are module
# literals so the tests can reference the same values the harness uses.
ATTRIBUTION_FIELDS = ("run_id", "handoff_id", "agent_role")
ATTRIBUTION_WINDOW = 500

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


def _count_run_retrieval_events(conn, run_dir):
    """Return the number of knowledge_retrieval_log rows for a run directory.

    The run directory's basename is used as the ``run_id``. The query is
    read-only and parameterized; a missing connection, table, or database is
    the zero state rather than a crash or a created file.
    """
    if conn is None:
        return 0
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM knowledge_retrieval_log WHERE run_id = ?",
            (Path(run_dir).name,),
        ).fetchone()
        return int(row[0])
    except sqlite3.OperationalError:
        return 0


def _read_attribution_rows(conn):
    """Return the most recent knowledge_retrieval_log rows for attribution.

    The read stays on the caller's existing read-only connection and selects
    only the columns the attribution section reports. A missing database
    file, missing table, missing column, or any other sqlite3 error returns
    None so the caller can render the degraded section instead of crashing.
    """
    if conn is None:
        return None
    try:
        return conn.execute(
            "SELECT id, run_id, handoff_id, agent_role "
            "FROM knowledge_retrieval_log ORDER BY id DESC LIMIT ?",
            (ATTRIBUTION_WINDOW,),
        ).fetchall()
    except sqlite3.OperationalError:
        return None


def _attribution_field_count(rows, field):
    """Count rows where ``field`` is present and not empty.

    The row layout is fixed by ``_read_attribution_rows``:
    ``(id, run_id, handoff_id, agent_role)``. ``(value or "").strip()``
    treats NULL, the empty string, and whitespace-only strings as not
    carrying the field.
    """
    field_index = ATTRIBUTION_FIELDS.index(field) + 1
    count = 0
    for row in rows:
        value = row[field_index]
        if (value or "").strip():
            count += 1
    return count


def _percentage(count, total):
    """Return ``count`` as a whole-number percentage of ``total``.

    Division by zero is the zero state, never an exception.
    """
    return int(count * 100 / total) if total else 0


def _attribution_counts(rows):
    """Return per-field attribution counts over all rows and the newest 30.

    ``rows`` is the result of ``_read_attribution_rows`` (already ordered by
    id descending). When it is None the returned structure carries
    ``unavailable: True`` so the formatters render the degraded section.
    """
    if rows is None:
        return {
            "unavailable": True,
            "rows_considered": 0,
            "newest_considered": 0,
            "all": {field: 0 for field in ATTRIBUTION_FIELDS},
            "newest": {field: 0 for field in ATTRIBUTION_FIELDS},
        }

    rows_considered = len(rows)
    newest_rows = rows[:30]
    newest_considered = len(newest_rows)
    return {
        "unavailable": False,
        "rows_considered": rows_considered,
        "newest_considered": newest_considered,
        "all": {
            field: _attribution_field_count(rows, field)
            for field in ATTRIBUTION_FIELDS
        },
        "newest": {
            field: _attribution_field_count(newest_rows, field)
            for field in ATTRIBUTION_FIELDS
        },
    }


def _render_attribution(counts):
    """Return the flat attribution lines for ``counts`` (pure formatter)."""
    if counts["unavailable"]:
        return (
            "attribution\n"
            "attribution unavailable: could not read the retrieval log"
        )

    total = counts["rows_considered"]
    newest_total = counts["newest_considered"]
    lines = ["attribution", f"rows_considered {total}"]
    for field in ATTRIBUTION_FIELDS:
        count = counts["all"][field]
        lines.append(
            f"{field} {count} of {total} ({_percentage(count, total)}%)"
        )
    lines.append("newest_30")
    for field in ATTRIBUTION_FIELDS:
        count = counts["newest"][field]
        lines.append(
            f"{field} {count} of {newest_total} "
            f"({_percentage(count, newest_total)}%)"
        )
    return "\n".join(lines)


def _render_attribution_markdown(counts):
    """Return the attribution table with its heading (pure formatter)."""
    if counts["unavailable"]:
        return (
            "## Attribution\n\n"
            "attribution unavailable: could not read the retrieval log"
        )

    total = counts["rows_considered"]
    newest_total = counts["newest_considered"]
    lines = [
        "## Attribution",
        "",
        "| field | rows carrying | rows considered | percent |",
        "| --- | --- | --- | --- |",
    ]
    for field in ATTRIBUTION_FIELDS:
        count = counts["all"][field]
        lines.append(
            f"| {field} (all rows) | {count} | {total} | "
            f"{_percentage(count, total)}% |"
        )
    for field in ATTRIBUTION_FIELDS:
        count = counts["newest"][field]
        lines.append(
            f"| {field} (newest 30) | {count} | {newest_total} | "
            f"{_percentage(count, newest_total)}% |"
        )
    return "\n".join(lines)


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
    """Return only the §8 comparison metrics present in ``available_columns``.

    A metric is reported from an execution record only when a usable column
    exists AND the commissioned comparison defines how to aggregate and
    attribute it. In this checkout neither condition holds for any of the six,
    so every returned value is 0. ``available_columns`` is the evidence for
    that absence: it is computed from PRAGMA table_info over the
    execution-ish tables and contains none of the six metric names here.
    Columns absent from ``available_columns`` are omitted from the returned
    dict so callers can tell presence from a zero measurement.
    """
    return {metric: 0 for metric in METRIC_HEADINGS if metric in available_columns}


def _print_report(retrieval_events, metric_values):
    """Print the fixed comparison report to stdout."""
    lines = []
    for arm in ("with_retrieval", "without_retrieval"):
        lines.append(arm)
        arm_events = retrieval_events if arm == "with_retrieval" else 0
        lines.append(f"retrieval_events {arm_events}")
        for metric in METRIC_HEADINGS:
            lines.append(f"{metric} {metric_values.get(metric, 0)}")
    lines.append("commissioning_procedure")
    lines.append(COMMISSIONING_PROCEDURE)
    print("\n".join(lines))


def _print_run_report(with_metrics, without_metrics, with_events, without_events):
    """Print the comparison report from two measured run directories."""
    lines = []
    for arm, metrics, events in (
        ("with_retrieval", with_metrics, with_events),
        ("without_retrieval", without_metrics, without_events),
    ):
        lines.append(arm)
        lines.append(f"retrieval_events {events}")
        for metric in METRIC_HEADINGS:
            lines.append(f"{metric} {metrics[metric]}")
    lines.append("commissioning_procedure")
    lines.append(COMMISSIONING_PROCEDURE)
    print("\n".join(lines))


def render_markdown(report) -> str:
    """Render the with-vs-without comparison as one Markdown table.

    ``report`` is arm-keyed by the two bound column headers; each arm value
    maps the six ``METRIC_HEADINGS`` keys plus ``"retrieval events"`` to an
    integer. A metric absent from an arm renders as 0. This is a pure
    formatter: it never prints, reads files, or opens the database.
    """
    arms = ("without retrieval", "with retrieval")
    lines = [
        "| | " + " | ".join(arms) + " |",
        "| --- | " + " | ".join("---:" for _ in arms) + " |",
    ]
    for metric in METRIC_HEADINGS + ("retrieval events",):
        values = [str(report[arm].get(metric, 0)) for arm in arms]
        lines.append("| " + metric + " | " + " | ".join(values) + " |")
    return "\n".join(lines)


def main(argv=None):
    """Entry point. Returns 0 on success.

    With no options the default empty-state DB report is printed exactly as
    before. With --with-run/--without-run the two arms are rendered from
    collect_run_metrics for the supplied run directories. With --markdown the
    comparison is printed as one Markdown table instead of the flat report.
    """
    parser = argparse.ArgumentParser(description="Knowledge evaluation harness.")
    parser.add_argument("--with-run", type=Path, default=None)
    parser.add_argument("--without-run", type=Path, default=None)
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args([] if argv is None else argv)

    if args.with_run is None and args.without_run is None:
        db_path = config.get_db_path()
        conn = _open_readonly(db_path)
        try:
            retrieval_events = _count_retrieval_events(conn)
            available_columns = _available_execution_columns(conn)
            attribution_rows = _read_attribution_rows(conn)
        finally:
            if conn is not None:
                conn.close()
        metric_values = _metric_values(available_columns)
        attribution_counts = _attribution_counts(attribution_rows)
        if args.markdown:
            report = {
                "without retrieval": {
                    **{metric: 0 for metric in METRIC_HEADINGS},
                    "retrieval events": 0,
                },
                "with retrieval": {
                    **{
                        metric: metric_values.get(metric, 0)
                        for metric in METRIC_HEADINGS
                    },
                    "retrieval events": retrieval_events,
                },
            }
            print(render_markdown(report))
            print(_render_attribution_markdown(attribution_counts))
        else:
            _print_report(retrieval_events, metric_values)
            print(_render_attribution(attribution_counts))
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
    conn = _open_readonly(config.get_db_path())
    try:
        with_events = (
            _count_run_retrieval_events(conn, args.with_run)
            if args.with_run is not None
            else 0
        )
        without_events = (
            _count_run_retrieval_events(conn, args.without_run)
            if args.without_run is not None
            else 0
        )
        attribution_rows = _read_attribution_rows(conn)
    finally:
        if conn is not None:
            conn.close()
    attribution_counts = _attribution_counts(attribution_rows)
    if args.markdown:
        report = {
            "without retrieval": {
                **{
                    metric: without_metrics.get(metric, 0)
                    for metric in METRIC_HEADINGS
                },
                "retrieval events": without_events,
            },
            "with retrieval": {
                **{
                    metric: with_metrics.get(metric, 0)
                    for metric in METRIC_HEADINGS
                },
                "retrieval events": with_events,
            },
        }
        print(render_markdown(report))
        print(_render_attribution_markdown(attribution_counts))
    else:
        _print_run_report(
            with_metrics, without_metrics, with_events, without_events
        )
        print(_render_attribution(attribution_counts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
