"""Documentation-fence tests for the single knowledge-layer overview.

These tests encode the naming rule the handoff's testgoal greps for: the
new overview exists, the two old overviews are gone, and the overview must
not name a deleted in-process knowledge module as present in this
repository. The alternation below is the same alternation TG2 greps for,
anchored on the ``knowledge/`` prefix so a prose-only mention of a
component (e.g. "the scope guard") cannot make the test pass by accident.
"""

import re
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"

# Same alternation as TG2, anchored on the knowledge/ prefix.
_DELETED_MODULE_PATH = re.compile(
    r"knowledge/(leann_provider|scope_guard|search|maintenance|indexer|provider)\.py"
)


def test_overview_names_no_deleted_module_and_the_old_overviews_are_gone():
    overview = DOCS_DIR / "knowledge_layer_overview.md"
    with_retrieval = DOCS_DIR / "knowledge_layer_overview_with_retrieval.md"
    without_retrieval = DOCS_DIR / "knowledge_layer_overview_without_retrieval.md"

    assert overview.is_file(), "docs/knowledge_layer_overview.md must exist"
    assert not with_retrieval.exists(), (
        "docs/knowledge_layer_overview_with_retrieval.md must be gone"
    )
    assert not without_retrieval.exists(), (
        "docs/knowledge_layer_overview_without_retrieval.md must be gone"
    )

    text = overview.read_text(encoding="utf-8")
    assert not _DELETED_MODULE_PATH.search(text), (
        "the overview must not name a deleted in-process knowledge module "
        "as present in this repository"
    )
