"""Refresh the knowledge index for every repository a flow targets.

Provider-neutral by construction: this script never names a concrete
provider. It discovers every distinct non-empty
``bridge_flows.target_project_path`` from the configured database, adds
Father (``config.get_project_root()``), derives each target's scope through
``knowledge.scopes.scope_for_target`` (Father keeps its configured scope),
skips targets that no longer exist on disk, and calls
``knowledge.maintenance.refresh_scope`` for each existing target.

Output is one tab-separated line per existing target
(``<scope>\\t<status>\\t<documents>``); missing targets and per-target
failures go to stderr. ``--dry-run`` lists targets and scopes without
touching the indexer, provider, index directory, or database. The exit code
is 0 only when every existing target refreshed or was a noop.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sqlite3
import sys
from pathlib import Path

# The script lives in scripts/, but config and knowledge live at the project
# root. Resolve the root from this file's location so the script runs from
# any working directory and under pytest importlib loading.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Never write bytecode caches while running; the scanned repository may be
# this project itself.
sys.dont_write_bytecode = True

import config  # noqa: E402
from knowledge import maintenance as knowledge_maintenance  # noqa: E402
from knowledge import scopes as knowledge_scopes  # noqa: E402

# Rebind so tests can tripwire the routine without touching the module object.
refresh_scope = knowledge_maintenance.refresh_scope


def _discover_db_targets(db_path: str) -> list[str]:
    """Return distinct non-empty ``bridge_flows.target_project_path`` rows.

    Opens the database read-only. A missing database, a missing
    ``bridge_flows`` table, or a missing ``target_project_path`` column all
    resolve to an empty list; the script then still refreshes Father.
    """
    try:
        conn = sqlite3.connect(Path(db_path).as_uri() + "?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT target_project_path FROM bridge_flows "
            "WHERE target_project_path IS NOT NULL "
            "AND TRIM(target_project_path) <> ''"
        )
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

    targets: list[str] = []
    for (value,) in rows:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            targets.append(text)
    return targets


def _scope_for(resolved: Path, father: Path) -> str:
    """Derive the scope for a resolved target path."""
    if resolved == father:
        return config.get_knowledge_scope()
    return knowledge_scopes.scope_for_target(str(resolved))


def collect_targets(db_path: str | None = None) -> list[tuple[str, str]]:
    """Return the ordered ``(scope, target_path)`` pairs to refresh.

    Father is inserted first so its configured scope wins when a flow target
    resolves to the same scope. Deduplication is by resolved target path
    first, then by derived scope first-wins.
    """
    if db_path is None:
        db_path = config.get_db_path()

    father = Path(config.get_project_root()).resolve()
    raw_targets = [str(father)] + _discover_db_targets(db_path)

    targets: list[tuple[str, str]] = []
    seen_paths: set[str] = set()
    seen_scopes: set[str] = set()
    for raw_path in raw_targets:
        resolved = Path(raw_path).expanduser().resolve()
        key = str(resolved)
        if key in seen_paths:
            continue
        seen_paths.add(key)

        scope = _scope_for(resolved, father)
        if scope in seen_scopes:
            continue
        seen_scopes.add(scope)
        targets.append((scope, key))
    return targets


def _refresh_one(scope: str, target_path: str) -> tuple[bool, object]:
    """Call ``refresh_scope`` with stderr captured.

    Returns ``(True, result_dict)`` on success and ``(False, message)`` on
    failure. For a ``SystemExit`` the message is the captured ``_fail``
    stderr; for any other exception it is ``str(exc)``.
    """
    stream = io.StringIO()
    with contextlib.redirect_stderr(stream):
        try:
            result = refresh_scope(scope, target_path)
        except SystemExit as exc:
            captured = stream.getvalue().strip()
            if captured:
                return False, captured
            message = str(exc)
            if not message:
                message = "operation failed"
            return False, message
        except Exception as exc:
            message = str(exc)
            if not message:
                message = type(exc).__name__
            return False, message
    return True, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the knowledge index for every flow target repository."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list targets and scopes without refreshing anything",
    )
    args = parser.parse_args(argv)

    db_path = config.get_db_path()
    targets = collect_targets(db_path)

    if args.dry_run:
        for scope, target_path in targets:
            if Path(target_path).exists():
                print(f"{scope}\t{target_path}")
            else:
                print(
                    "knowledge_refresh_ecosystem: skipping missing target "
                    f"{target_path}",
                    file=sys.stderr,
                )
        return 0

    failed = False
    for scope, target_path in targets:
        if not Path(target_path).exists():
            print(
                "knowledge_refresh_ecosystem: skipping missing target "
                f"{target_path}",
                file=sys.stderr,
            )
            continue

        ok, result = _refresh_one(scope, target_path)
        if not ok:
            print(
                f"knowledge_refresh_ecosystem: error: {scope}: {result}",
                file=sys.stderr,
            )
            failed = True
            continue

        if isinstance(result, dict):
            status = result.get("status", "unknown")
            documents = result.get("documents")
        else:
            status = "unknown"
            documents = None

        if status == "noop":
            documents = "-"
        elif documents is None:
            documents = "-"
        print(f"{scope}\t{status}\t{documents}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
