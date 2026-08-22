"""Tests for the 103_FLOW_STARTUP.md cold-start contract.

These tests pin the wiring of the flow startup contract:

  * the document itself contains the five required section anchors;
  * every repo-relative path the document references resolves in the tree;
  * the document is referenced from start_coding.py's supervisor prompt and
    from each of the nine cold-start skills.

The link-extraction contract is deterministic: skip fenced code blocks
(``` ... ```), then take every backtick-quoted span in the remaining
text, strip ONE trailing 's / , / . / ) / : if present, and keep the
span only if it matches a repo-relative path under (scripts|docs|tests|
databases). The parser-sanity assertion prevents an empty extraction
from passing vacuously.
"""
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DOC_PATH = PROJECT_ROOT / "docs" / "governance-templates-v2" / "103_FLOW_STARTUP.md"

REQUIRED_ANCHORS = (
    "## Supervisor-Driven Flows",
    "## Architect-Driven Flows",
    "## Bare Flows",
    "## Cold Start From Nothing",
    "## Binding Rules",
)

# Repos the parser-sanity check requires the document to reference. A
# failure here means the document does not actually exercise the wiring
# the tests are supposed to protect, and the gate must not go green.
REQUIRED_REFERENCES = frozenset({
    "scripts/bridgeV002/execution_config.py",
    "scripts/bridgeV002/bridge-broker.service",
})

PATH_PREFIXES = ("scripts/", "docs/", "tests/", "databases/")
PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_./\-]+")
BACKTICK_RE = re.compile(r"`([^`]+)`")
FENCE_RE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
TRAILING_CHARS = ("s", ",", ".", ")", ":")


def _strip_trailing(token: str) -> str:
    """Strip ONE trailing punctuation mark from a quoted token.

    A span like `bridge-broker.service` keeps its suffix (a real path
    component); a span like `the supervisor_state.py).` strips the
    trailing ')' / '.'. Only one character is stripped — the contract
    specifies ONE trailing character, never a sequence.
    """
    if token and token[-1] in TRAILING_CHARS:
        return token[:-1]
    return token


def _strip_fences(text: str) -> str:
    """Replace fenced code blocks with whitespace of equal length.

    Fenced blocks hold pasted command output — that is evidence, not a
    claim. A report that pastes `git status` for context would otherwise
    be read as claiming every line of it, which is how an honest report
    gets accused of taking credit.
    """
    def _blank(match):
        return re.sub(r"[^\n]", " ", match.group(0))
    return FENCE_RE.sub(_blank, text)


def _extract_referenced_paths(text: str) -> set:
    """The deterministic link-extraction contract.

    See module docstring for the rules. Returns the set of repo-relative
    paths the document references via backtick-quoted spans in non-fenced
    text.
    """
    cleaned = _strip_fences(text)
    found = set()
    for raw in BACKTICK_RE.findall(cleaned):
        token = _strip_trailing(raw.strip())
        if not token.startswith(PATH_PREFIXES):
            continue
        if not PATH_TOKEN_RE.fullmatch(token):
            continue
        found.add(token)
    return found


# ── (1) anchors ───────────────────────────────────────────────────


def test_doc_flow_startup_doc_file_exists():
    """The flow startup contract document exists at the canonical path."""
    assert DOC_PATH.exists(), f"missing: {DOC_PATH}"


@pytest.mark.parametrize("anchor", REQUIRED_ANCHORS)
def test_doc_has_required_anchors(anchor):
    """Each required section anchors appears as its own line in the doc."""
    text = DOC_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert anchor in lines, f"missing anchor: {anchor!r}"


# ── (2) links ─────────────────────────────────────────────────────


def test_links_extraction_is_nonempty():
    """Parser-sanity: the extraction must yield paths, not nothing.

    An empty extraction means the document does not actually name any
    repo path — the gate must not go green in that case.
    """
    text = DOC_PATH.read_text(encoding="utf-8")
    paths = _extract_referenced_paths(text)
    assert paths, "no repo-relative paths extracted from the document"


def test_links_extraction_contains_required_anchors():
    """Parser-sanity: the extraction must hit known anchors."""
    text = DOC_PATH.read_text(encoding="utf-8")
    paths = _extract_referenced_paths(text)
    missing = REQUIRED_REFERENCES - paths
    assert not missing, f"missing required references: {sorted(missing)}"


def test_links_referenced_paths_resolve_in_tree():
    """Every repo-relative path the document references must exist."""
    text = DOC_PATH.read_text(encoding="utf-8")
    paths = _extract_referenced_paths(text)
    missing = [p for p in sorted(paths) if not (PROJECT_ROOT / p).exists()]
    assert not missing, f"missing files: {missing}"


# ── (3) references ────────────────────────────────────────────────


def test_start_coding_banner_references_doc():
    """start_coding.py's composed supervisor prompt names the document."""
    start_coding_path = PROJECT_ROOT / "scripts" / "bridgeV002" / "start_coding.py"
    text = start_coding_path.read_text(encoding="utf-8")
    assert "103_FLOW_STARTUP" in text, (
        f"{start_coding_path} does not reference 103_FLOW_STARTUP"
    )


SKILL_DIR = PROJECT_ROOT / ".claude" / "skills"
SKILL_NAMES = (
    "CLOUDLLM",
    "CLOUDPAY",
    "dpmtf-cold-start",
    "LLAMASG",
    "PRECLOUD",
    "PRECLOUDHARNESS",
    "REVENG",
    "STRICTREVIEW",
    "SUPERVISEDREVIEW",
)


@pytest.mark.parametrize("skill_name", SKILL_NAMES)
def test_each_skill_references_doc(skill_name):
    """Each of the nine cold-start skills carries the pointer line."""
    skill_path = SKILL_DIR / skill_name / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    assert "103_FLOW_STARTUP" in text, (
        f"{skill_path} does not reference 103_FLOW_STARTUP"
    )


def test_exactly_nine_skills_references_doc():
    """All nine cold-start skills (no fewer, no more) reference the doc."""
    matching = []
    for skill_name in SKILL_NAMES:
        skill_path = SKILL_DIR / skill_name / "SKILL.md"
        text = skill_path.read_text(encoding="utf-8")
        if "103_FLOW_STARTUP" in text:
            matching.append(skill_name)
    assert len(matching) == 9, (
        f"expected 9 skills to reference the doc, got {len(matching)}: "
        f"{matching}"
    )
