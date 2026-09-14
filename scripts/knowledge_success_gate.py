"""Deterministic success gate for the knowledge client path.

DPMtF is a client of the standalone knowledge service; this gate re-measures
the six measurable success criteria against the current tree and prints
exactly one ``criterion_N PASS`` or ``criterion_N FAIL`` line per criterion
to stdout, then exits 0 only when all six passed.

Every criterion drives ``knowledge.service_client._http`` with a fake
service — a callable returning ``(status, payload)`` — so no criterion ever
touches a provider, the local filesystem, or the network. When ``main`` is
run as ``__main__`` it installs the built-in fake service only if the seam
still points at the real urllib-backed ``_http``; a caller that has already
replaced ``_http`` owns the seam and the gate leaves it in place.

The gate is read-only toward the repository. Every write it performs goes to
a directory created with ``tempfile.mkdtemp()``, and that directory is
removed in a ``finally:`` block. No component under test is modified.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import sys
import tempfile
import traceback
from pathlib import Path
from unittest.mock import patch

# The gate lives in scripts/, but its imports (app, config, knowledge) live at
# the project root. Resolve the project root from this file's location and put
# it on sys.path, exactly like scripts/bridgeV002/check_testgoals.py does.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import app  # noqa: F401, E402  (mounts routers/knowledge, no DB write at import)
import config  # noqa: E402
from knowledge import retrieval  # noqa: E402
from knowledge import service_client  # noqa: E402

# Schema source for the throwaway databases. Read-only; never modified. The
# path is derived from config's own location so no absolute path is hardcoded.
_SCHEMA_PATH = (
    Path(config.__file__).resolve().parent
    / "scripts"
    / "db"
    / "107_knowledge_tables.sql"
)

# The real urllib-backed seam, captured at import time. ``main`` installs the
# built-in fake only while the seam still points here.
_REAL_HTTP = service_client._http

# One query marker per criterion, so a caller-supplied ``_http`` can serve the
# correct fake response per criterion.
_C1_QUERY = "gate-c1-disabled"
_C2_QUERY = "gate-c2-proxy"
_C3_QUERY = "gate-c3-paths"
_C4_QUERY = "gate-c4-fat"
_C5_QUERY = "gate-c5-denied"
_C6_QUERY = "gate-c6-down"


def _seed_schema_db(db_path: str) -> None:
    """Create the knowledge schema from the project's own migration file."""
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


def _make_temp_db() -> tuple[Path, str]:
    """Create a throwaway DB seeded with the full 107 knowledge schema."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="knowledge-gate-criterion-"))
    db_path = tmp_dir / "gate.db"
    _seed_schema_db(str(db_path))
    return tmp_dir, str(db_path)


def _log_rows(db_path: str) -> int:
    """Return the number of local knowledge_retrieval_log rows."""
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM knowledge_retrieval_log"
        ).fetchone()[0]
    finally:
        conn.close()


def _fake_service_http(method, url, params_or_body, timeout):
    """Built-in fake service used when the gate owns the seam.

    Search requests are served per criterion marker; anything else receives a
    plain 200 envelope. No criterion reaches the network.
    """
    del method, url, timeout
    if isinstance(params_or_body, dict):
        query = params_or_body.get("q")
        if query == _C1_QUERY:
            return (200, {
                "enabled": False,
                "provider": "service",
                "results": [],
                "bounded": True,
            })
        if query == _C5_QUERY:
            return (403, {"detail": "scope access denied"})
        if query == _C6_QUERY:
            return (0, {"detail": "connection refused"})
        if query == _C4_QUERY:
            return (200, {
                "enabled": True,
                "provider": "service",
                "results": [
                    {"path": f"fat-{index}.md",
                     "content": " ".join(["token"] * 2000)}
                    for index in range(8)
                ],
                "bounded": True,
            })
        return (200, {
            "enabled": True,
            "provider": "service",
            "results": [
                {"path": f"doc-{index}.md", "content": f"content number {index}"}
                for index in range(3)
            ],
            "bounded": True,
        })
    return (200, {"status": "ok"})


class _RecordingHandler(logging.Handler):
    """Collect log records so criterion 6 can count ERROR lines exactly."""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def criterion_1() -> tuple[str, bool]:
    """A disabled service envelope passes through unchanged and no log row is written."""
    tmp_dir, db_path = _make_temp_db()
    try:
        with patch("config.get_db_path", return_value=db_path):
            client = TestClient(app.app)
            response = client.get("/api/knowledge/search", params={"q": _C1_QUERY})

        expected = {
            "enabled": False,
            "provider": "service",
            "results": [],
            "bounded": True,
        }
        ok = (
            response.status_code == 200
            and response.json() == expected
            and _log_rows(db_path) == 0
        )
        return ("criterion_1", ok)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def criterion_2() -> tuple[str, bool]:
    """Results arrive through the proxy route."""
    client = TestClient(app.app)
    response = client.get("/api/knowledge/search", params={"q": _C2_QUERY})
    ok = response.status_code == 200 and bool(response.json().get("results"))
    return ("criterion_2", ok)


def criterion_3() -> tuple[str, bool]:
    """Every returned result carries a usable 'path' source reference."""
    client = TestClient(app.app)
    response = client.get("/api/knowledge/search", params={"q": _C3_QUERY})

    if response.status_code != 200:
        return ("criterion_3", False)

    results = response.json().get("results", [])
    ok = bool(results) and all(
        isinstance(item, dict) and str(item.get("path", "")).strip() != ""
        for item in results
    )
    return ("criterion_3", ok)


def criterion_4() -> tuple[str, bool]:
    """The block renderer respects top_k and the configured token budget."""
    top_k = config.get_knowledge_top_k()
    max_context_tokens = config.get_knowledge_max_context_tokens()

    tmp_dir, db_path = _make_temp_db()
    try:
        with patch("config.get_db_path", return_value=db_path):
            block = retrieval.retrieve_for_context(_C4_QUERY, "s", "a", "r", "h")

        count = block.count("source: ") if block else 0
        token_count = len(block.split()) if block else 0
        ok = (
            block is not None
            and block.startswith("<supplemental_knowledge>")
            and count <= top_k
            and token_count <= max_context_tokens
            and _log_rows(db_path) == 1
        )
        return ("criterion_4", ok)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def criterion_5() -> tuple[str, bool]:
    """A 403 leaves the prompt unchanged and writes no local log row."""
    tmp_dir, db_path = _make_temp_db()
    try:
        with patch("config.get_db_path", return_value=db_path):
            block = retrieval.retrieve_for_context(_C5_QUERY, "s", "a", "r", "h")

        ok = block is None and _log_rows(db_path) == 0
        return ("criterion_5", ok)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def criterion_6() -> tuple[str, bool]:
    """A transport failure is one ERROR log line and an unchanged prompt."""
    tmp_dir, db_path = _make_temp_db()
    handler = _RecordingHandler()
    logger = logging.getLogger("knowledge.retrieval")
    logger.addHandler(handler)
    try:
        with patch("config.get_db_path", return_value=db_path):
            block = retrieval.retrieve_for_context(_C6_QUERY, "s", "a", "r", "h")
    finally:
        logger.removeHandler(handler)

    errors = [record for record in handler.records if record.levelno >= logging.ERROR]
    try:
        ok = (
            block is None
            and len(errors) == 1
            and _log_rows(db_path) == 0
        )
        return ("criterion_6", ok)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


_CRITERION_NAMES = (
    "criterion_1",
    "criterion_2",
    "criterion_3",
    "criterion_4",
    "criterion_5",
    "criterion_6",
)


def _run_criterion(name: str, fn, *args) -> tuple[str, bool]:
    """Run one criterion and degrade an unexpected error to a FAIL line."""
    try:
        returned = fn(*args)
        return (str(returned[0]), bool(returned[1]))
    except Exception:
        print(f"{name}: unexpected error:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return (name, False)


def main(argv=None) -> int:
    """Run criteria 1-6, print exactly one line per criterion, return 0/1."""
    del argv  # signature parity with other scripts' main(argv) shape

    tmp_dir = Path(tempfile.mkdtemp(prefix="knowledge-gate-main-"))
    results = []

    # Own the service seam only when a caller has not already replaced it.
    owns_seam = service_client._http is _REAL_HTTP
    previous_http = service_client._http
    if owns_seam:
        service_client._http = _fake_service_http

    try:
        criteria = (
            ("criterion_1", criterion_1, ()),
            ("criterion_2", criterion_2, ()),
            ("criterion_3", criterion_3, ()),
            ("criterion_4", criterion_4, ()),
            ("criterion_5", criterion_5, ()),
            ("criterion_6", criterion_6, ()),
        )
        for name, fn, args in criteria:
            results.append(_run_criterion(name, fn, *args))
    except Exception:
        print(
            "gate setup failed; treating every criterion as FAIL",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
    finally:
        if owns_seam:
            service_client._http = previous_http
        shutil.rmtree(tmp_dir, ignore_errors=True)

    seen = {name for name, _ in results}
    for name in _CRITERION_NAMES:
        if name not in seen:
            results.append((name, False))

    all_ok = True
    for name, ok in results:
        print(f"{name} {'PASS' if ok else 'FAIL'}")
        all_ok = all_ok and ok
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
