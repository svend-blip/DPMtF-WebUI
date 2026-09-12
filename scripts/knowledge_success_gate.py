"""Deterministic success gate for the knowledge layer (addendum §10, criteria 1–6).

This gate re-measures the six measurable success criteria against the current
tree and prints exactly one ``criterion_N PASS`` or ``criterion_N FAIL`` line
per criterion to stdout, then exits 0 only when all six passed.

Criterion 7 (at least one representative RUN) is intentionally not measured
here; it is an evidence gate with its own contract (GOAL-DRAFT-012). This
script never prints a line for criterion 7 and never claims the representative
RUN has been demonstrated.

The gate is read-only toward the repository. Every write it performs goes to a
directory created with ``tempfile.mkdtemp()``, and that directory is removed in
a ``finally:`` block. No component under test is modified, and the provider
registry is only ever patched in memory and restored afterwards.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import traceback
from contextlib import contextmanager
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
from knowledge import indexer as knowledge_indexer  # noqa: E402
from knowledge import search as knowledge_search  # noqa: E402
from knowledge.provider import KnowledgeProvider, NoneProvider  # noqa: E402

# Schema source for the throwaway databases. Read-only; never modified. The
# path is derived from config's own location so no absolute path is hardcoded.
_SCHEMA_PATH = (
    Path(config.__file__).resolve().parent
    / "scripts"
    / "db"
    / "107_knowledge_tables.sql"
)


class _TemporaryStubProvider(KnowledgeProvider):
    """In-memory provider used only by the gate (criteria 2–4).

    ``results`` defaults to a single usable document so the router can
    instantiate the class with no constructor arguments, exactly as
    ``routers/knowledge.py`` does with every resolved provider.
    """

    def __init__(self, results=None):
        self._results = (
            list(results)
            if results is not None
            else [{"path": "a.md", "content": "gate stub result"}]
        )

    def index(self, source: str) -> None:
        return None

    def update(self, source: str) -> None:
        return None

    def remove(self, source: str) -> None:
        return None

    def search(self, query, *, scope=None, filters=None, top_k=None, token_budget=None):
        return list(self._results)


def _seed_schema_db(db_path: str) -> None:
    """Create the knowledge schema from the project's own migration file."""
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


def _create_temp_db(tmp_dir: Path) -> str:
    """Create a throwaway DB seeded with the full 107 knowledge schema."""
    db_path = tmp_dir / "gate.db"
    _seed_schema_db(str(db_path))
    return str(db_path)


@contextmanager
def _temporary_stub_registry():
    """Temporarily register the gate's stub provider, then restore the registry."""
    previous = knowledge_search.PROVIDER_LOADERS.get("gate_stub")
    knowledge_search.PROVIDER_LOADERS["gate_stub"] = lambda: _TemporaryStubProvider
    try:
        yield
    finally:
        if previous is None:
            knowledge_search.PROVIDER_LOADERS.pop("gate_stub", None)
        else:
            knowledge_search.PROVIDER_LOADERS["gate_stub"] = previous


def criterion_1() -> tuple[str, bool]:
    """Build a temp repository, index it, require >= 1 manifest document."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="knowledge-gate-c1-"))
    try:
        repo_dir = tmp_dir / "repo"
        repo_dir.mkdir()
        (repo_dir / "README.md").write_text(
            "knowledge gate fixture\n", encoding="utf-8"
        )

        manifest_path = tmp_dir / "manifest.jsonl"
        db_path = _create_temp_db(tmp_dir)

        with patch("config.get_db_path", return_value=db_path):
            try:
                exit_code = knowledge_indexer.main(
                    [
                        "--repo",
                        str(repo_dir),
                        "--scope",
                        "gate-tmp",
                        "--out",
                        str(manifest_path),
                    ]
                )
            except SystemExit:
                return ("criterion_1", False)

        if exit_code != 0:
            return ("criterion_1", False)

        documents = []
        with open(manifest_path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                documents.append(json.loads(line))

        return (
            "criterion_1",
            any(str(doc.get("content", "")).strip() != "" for doc in documents),
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def criterion_2(tmp_db: str) -> tuple[str, bool]:
    """GET /api/knowledge/search through TestClient with the stub provider."""
    with _temporary_stub_registry(), patch(
        "routers.knowledge.scope_guard.require_scope_access",
        lambda *args, **kwargs: None,
    ), patch("config.get_knowledge_enabled", return_value=True), patch(
        "config.get_knowledge_provider", return_value="gate_stub"
    ), patch(
        "config.get_db_path", return_value=tmp_db
    ):
        client = TestClient(app.app)
        response = client.get("/api/knowledge/search", params={"q": "anything"})

    ok = response.status_code == 200 and bool(response.json().get("results"))
    return ("criterion_2", ok)


def criterion_3(tmp_db: str) -> tuple[str, bool]:
    """Every returned result carries a usable 'path' source reference."""
    with _temporary_stub_registry(), patch(
        "routers.knowledge.scope_guard.require_scope_access",
        lambda *args, **kwargs: None,
    ), patch("config.get_knowledge_enabled", return_value=True), patch(
        "config.get_knowledge_provider", return_value="gate_stub"
    ), patch(
        "config.get_db_path", return_value=tmp_db
    ):
        client = TestClient(app.app)
        response = client.get("/api/knowledge/search", params={"q": "anything"})

    if response.status_code != 200:
        return ("criterion_3", False)

    results = response.json().get("results", [])
    ok = bool(results) and all(
        isinstance(item, dict) and str(item.get("path", "")).strip() != ""
        for item in results
    )
    return ("criterion_3", ok)


def criterion_4(tmp_db: str) -> tuple[str, bool]:
    """Result count <= top_k and rendered token count <= max_context_tokens."""
    top_k = config.get_knowledge_top_k()
    max_context_tokens = config.get_knowledge_max_context_tokens()

    with _temporary_stub_registry(), patch(
        "routers.knowledge.scope_guard.require_scope_access",
        lambda *args, **kwargs: None,
    ), patch("config.get_knowledge_enabled", return_value=True), patch(
        "config.get_knowledge_provider", return_value="gate_stub"
    ), patch(
        "config.get_db_path", return_value=tmp_db
    ):
        client = TestClient(app.app)
        response = client.get("/api/knowledge/search", params={"q": "anything"})

    if response.status_code != 200:
        return ("criterion_4", False)

    results = response.json().get("results", [])
    token_count = sum(
        len(str(item.get("content", "")).split()) for item in results
    )
    ok = len(results) <= top_k and token_count <= max_context_tokens
    return ("criterion_4", ok)


def criterion_5() -> tuple[str, bool]:
    """Disabled envelope byte-identical and no retrieval-log row written."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="knowledge-gate-c5-"))
    try:
        db_path = _create_temp_db(tmp_dir)

        with patch("config.get_db_path", return_value=db_path), patch(
            "config.get_knowledge_enabled", return_value=False
        ):
            client = TestClient(app.app)
            response = client.get("/api/knowledge/search", params={"q": "anything"})

        expected = json.dumps(
            {
                "enabled": False,
                "provider": config.get_knowledge_provider(),
                "results": [],
                "bounded": True,
            },
            sort_keys=True,
        )
        actual = json.dumps(response.json(), sort_keys=True)
        envelope_ok = expected == actual

        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM knowledge_retrieval_log WHERE 1 = ?",
                (1,),
            ).fetchone()
            rows = row[0]
        finally:
            conn.close()

        return ("criterion_5", envelope_ok and rows == 0)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def criterion_6() -> tuple[str, bool]:
    """PROVIDER_LOADERS maps both 'none' and a temp replacement through the
    KnowledgeProvider interface."""
    ok = "none" in knowledge_search.PROVIDER_LOADERS
    with _temporary_stub_registry():
        for key in ("none", "gate_stub"):
            loader = knowledge_search.PROVIDER_LOADERS.get(key)
            if not callable(loader):
                ok = False
                continue
            provider_cls = loader()
            is_class = isinstance(provider_cls, type)
            if not (is_class and issubclass(provider_cls, KnowledgeProvider)):
                ok = False
                continue
            if key == "gate_stub" and issubclass(provider_cls, NoneProvider):
                ok = False
    return ("criterion_6", ok)


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
    """Run criteria 1–6, print exactly one line per criterion, return 0/1."""
    del argv  # signature parity with the indexer's main(argv) shape

    tmp_dir = Path(tempfile.mkdtemp(prefix="knowledge-gate-main-"))
    results = []
    try:
        shared_db = _create_temp_db(tmp_dir)
        criteria = (
            ("criterion_1", criterion_1, ()),
            ("criterion_2", criterion_2, (shared_db,)),
            ("criterion_3", criterion_3, (shared_db,)),
            ("criterion_4", criterion_4, (shared_db,)),
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
