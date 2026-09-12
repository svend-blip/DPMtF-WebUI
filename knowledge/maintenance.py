"""Provider-neutral index maintenance.

Compares a repository tree against the last JSONL manifest emitted by
``knowledge.indexer`` and reports whether the scope needs re-indexing:

* ``noop``    — nothing changed: same paths, same content.
* ``changed`` — files were added, modified, or removed.
* ``missing`` — no manifest exists yet.

The module also records one ``knowledge_indexes`` row per successful index
and probes a provider's change-detection/update capability through the
provider-neutral interface only. It never imports, names, or otherwise
depends on a concrete provider; a concrete provider is resolved at runtime
through ``knowledge.search.resolve_provider``.

Read-only toward the scanned repository: the only writes are the caller's
database (``knowledge_indexes`` upsert) and temp files the capability probe
creates and deletes under ``tempfile.mkdtemp()``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# The scanned repository may be this project itself. Never let Python write
# bytecode caches while the maintenance scan runs, or a scan of the project
# checkout would violate the read-only guarantee.
sys.dont_write_bytecode = True

import config  # noqa: E402
import knowledge.indexer as indexer  # noqa: E402
import knowledge.search as search  # noqa: E402


def _fail(message: str) -> None:
    """Print a clear en-US error and exit nonzero."""
    print(f"knowledge.maintenance: error: {message}", file=sys.stderr)
    raise SystemExit(1)


@dataclass
class MaintenancePlan:
    """Outcome of comparing a repository tree against a manifest."""

    status: str  # one of "noop" | "changed" | "missing"
    changed_paths: list[str]
    removed_paths: list[str]


def _read_manifest_mapping(manifest_path: Path, scope: str) -> dict[str, str]:
    """Read a JSONL manifest into a ``path -> content`` mapping.

    Records whose ``scope`` field is present and differs from the requested
    ``scope`` are skipped. On a duplicate ``path``, the last record wins. A
    malformed line is a hard error.
    """
    mapping: dict[str, str] = {}
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                _fail(
                    f"invalid JSON on line {line_number} of "
                    f"{manifest_path}: {exc}"
                )
            if not isinstance(record, dict):
                _fail(
                    f"manifest record on line {line_number} of "
                    f"{manifest_path} is not a JSON object"
                )
            if "scope" in record and record["scope"] != scope:
                continue
            if "path" not in record or "content" not in record:
                _fail(
                    f"manifest record on line {line_number} of "
                    f"{manifest_path} is missing required keys: path, content"
                )
            mapping[str(record["path"])] = str(record["content"])
    return mapping


def detect_changes(repo, scope, manifest_path) -> MaintenancePlan:
    """Compare ``repo`` against the manifest at ``manifest_path``.

    Reuses ``knowledge.indexer``'s exclusion loading and document walk so the
    maintenance scan sees exactly the files a fresh index would see. A missing
    manifest reports ``missing``; otherwise the plan reports ``noop`` or
    ``changed`` with the sorted path lists.
    """
    repo_path = Path(repo).expanduser().resolve()
    if not repo_path.exists():
        _fail(f"--repo does not exist: {repo_path}")
    if not repo_path.is_dir():
        _fail(f"--repo is not a directory: {repo_path}")

    manifest = Path(manifest_path).expanduser()
    if not manifest.exists() or not manifest.is_file():
        return MaintenancePlan(status="missing", changed_paths=[], removed_paths=[])
    try:
        manifest.resolve()
    except OSError as exc:
        _fail(f"cannot resolve manifest path {manifest}: {exc}")

    previous = _read_manifest_mapping(manifest, scope)

    exclusions = indexer._load_repo_exclusions(scope)
    current: dict[str, str] = {}
    for rel_path, content, _size_bytes in indexer._iter_documents(
        repo_path, exclusions
    ):
        current[rel_path] = content

    previous_paths = set(previous)
    current_paths = set(current)

    removed_paths = sorted(previous_paths - current_paths)
    changed_paths = sorted(
        (current_paths - previous_paths)
        | {path for path in previous_paths & current_paths if previous[path] != current[path]}
    )

    if not changed_paths and not removed_paths:
        return MaintenancePlan(status="noop", changed_paths=[], removed_paths=[])
    return MaintenancePlan(
        status="changed",
        changed_paths=changed_paths,
        removed_paths=removed_paths,
    )


def record_index(scope, provider, location, document_count, status) -> None:
    """Upsert one ``knowledge_indexes`` row for ``scope``.

    The schema is owned by migrations: this function verifies the table exists
    but never creates it. SQL is parameterized only, and ``scope``'s UNIQUE
    constraint makes a repeated call an update instead of a duplicate row.
    """
    if isinstance(document_count, bool) or not isinstance(document_count, int):
        _fail("document_count must be an integer")
    if document_count < 0:
        _fail("document_count must be >= 0")

    db_path = config.get_db_path()
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.Error as exc:
        _fail(f"cannot open knowledge database at {db_path}: {exc}")

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name = 'knowledge_indexes'"
        )
        if cur.fetchone() is None:
            _fail(
                "knowledge_indexes table is missing from "
                f"{db_path}; refusing to record an index without schema"
            )
        cur.execute(
            "INSERT INTO knowledge_indexes "
            "(scope, provider, location, document_count, status) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(scope) DO UPDATE SET "
            "provider = excluded.provider, "
            "location = excluded.location, "
            "document_count = excluded.document_count, "
            "status = excluded.status, "
            "updated_at = datetime('now')",
            (scope, provider, location, document_count, status),
        )
        conn.commit()
    finally:
        conn.close()


def probe_provider_capabilities(provider_key, db_path=None) -> dict:
    """Probe a provider's index/update/remove support through the interface.

    ``db_path`` is accepted for interface stability and intentionally unused.
    The provider class is resolved only through
    ``knowledge.search.resolve_provider`` and instantiated with no
    constructor arguments. A method is supported when it returns without
    raising ``NotImplementedError``; any other exception propagates because a
    broken provider must not be reported as supported.
    """
    provider_cls = search.resolve_provider(provider_key)
    provider = provider_cls()

    tmp_dir = Path(tempfile.mkdtemp(prefix="knowledge-maintenance-probe-"))
    manifest_path = tmp_dir / "probe-manifest.jsonl"
    try:
        record = {
            "scope": "probe",
            "path": "probe.txt",
            "content": "probe",
            "size_bytes": 5,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path.write_text(
            json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        manifest = str(manifest_path)

        def _supports(method_name: str) -> bool:
            method = getattr(provider, method_name)
            try:
                method(manifest)
            except NotImplementedError:
                return False
            return True

        return {
            "index_supported": _supports("index"),
            "update_supported": _supports("update"),
            "remove_supported": _supports("remove"),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare a repository tree against its last index manifest and "
            "report noop, changed, or missing."
        )
    )
    parser.add_argument("--repo", help="repository path to scan")
    parser.add_argument("--scope", help="scope recorded on every document")
    parser.add_argument("--manifest", help="existing JSONL manifest to compare against")
    parser.add_argument(
        "--record-index",
        action="store_true",
        help="record an index state row in knowledge_indexes",
    )
    parser.add_argument("--provider", help="provider label recorded with the index")
    parser.add_argument("--location", help="provider-chosen index location")
    parser.add_argument("--document-count", help="number of documents indexed")
    parser.add_argument(
        "--probe-provider",
        help="probe a provider's update/remove support and exit",
    )
    args = parser.parse_args(argv)

    if args.probe_provider is not None:
        if args.repo or args.scope or args.manifest or args.record_index:
            _fail(
                "--probe-provider cannot be combined with "
                "--repo/--scope/--manifest/--record-index"
            )
        capabilities = probe_provider_capabilities(args.probe_provider)
        print(f"update_supported {str(capabilities['update_supported']).lower()}")
        print(f"remove_supported {str(capabilities['remove_supported']).lower()}")
        return 0

    missing = [
        name
        for name, value in (
            ("--repo", args.repo),
            ("--scope", args.scope),
            ("--manifest", args.manifest),
        )
        if value is None
    ]
    if missing:
        _fail("missing required argument(s): " + ", ".join(missing))

    plan = detect_changes(args.repo, args.scope, args.manifest)

    if args.record_index:
        if (
            args.provider is None
            or args.location is None
            or args.document_count is None
        ):
            _fail(
                "--record-index requires --provider, --location, and "
                "--document-count"
            )
        try:
            document_count = int(args.document_count)
        except ValueError:
            _fail("--document-count must be an integer")
        record_index(
            args.scope,
            args.provider,
            args.location,
            document_count,
            plan.status,
        )

    if plan.status == "noop":
        print("noop")
    elif plan.status == "missing":
        print("missing")
    else:
        print(f"changed {len(plan.changed_paths)} removed {len(plan.removed_paths)}")
    return 0


if __name__ == "__main__":
    main()
