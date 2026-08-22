"""Tests for the README.md doc-link and definition contract.

These tests pin the wiring of the README against the current repository:

  * the five required section anchors are present as their own lines;
  * every repo-relative path the README references resolves in the tree;
  * the definition sentence and the name line are present verbatim.

The link-extraction contract mirrors tests/test_flow_startup_doc.py:
skip fenced code blocks (``` ... ```), take every backtick-quoted span
in the remaining text, strip ONE trailing 's / , / . / ) / :' if
present, and keep the span only if it matches a repo-relative path under
(scripts|docs|tests|databases|routers). The parser-sanity assertion
prevents an empty extraction from passing vacuously — a README that
references no repo path must FAIL.

Each of the three tests below is selected by exactly one -k selector:
  -k anchors    → test_anchors_present
  -k links      → test_links_resolve
  -k definition → test_definition_verbatim
"""
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DOC_PATH = PROJECT_ROOT / "README.md"

REQUIRED_ANCHORS = (
    "## Place in the DPMtF Ecosystem",
    "## The Three-Layer Bridge",
    "## Flow Types",
    "## Runtime Services",
    "## Validation",
)

NAME_LINE = "DPMtF — Deterministic Process Management to Finalisation."

DEFINITION_SENTENCE = (
    "DPMtF is a deterministic multi-agent process orchestration framework "
    "for taking defined work from intent to verified finalisation through "
    "governed flows, steps, roles, harnesses, models, gates, and artifacts."
)

# Repos the parser-sanity check requires the README to reference. A
# failure here means the README does not actually exercise the wiring
# the tests are supposed to protect, and the gate must not go green.
REQUIRED_REFERENCES = frozenset({
    "scripts/bridgeV002/bridge-broker.service",
    "scripts/bridgeV002/chain-watchdog.service",
    "docs/governance-templates-v2/100_BRIDGE.md",
    "docs/governance-templates-v2/103_FLOW_STARTUP.md",
    "scripts/bridgeV002/execution_config.py",
})

PATH_PREFIXES = ("scripts/", "docs/", "tests/", "databases/", "routers/")
PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_./\-]+")
BACKTICK_RE = re.compile(r"`([^`]+)`")
FENCE_RE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
TRAILING_CHARS = ("s", ",", ".", ")", ":")


def _strip_trailing(token: str) -> str:
    """Strip ONE trailing punctuation mark from a quoted token."""
    if token and token[-1] in TRAILING_CHARS:
        return token[:-1]
    return token


def _strip_fences(text: str) -> str:
    """Replace fenced code blocks with whitespace of equal length.

    Fenced blocks hold pasted command output — that is evidence, not a
    claim. A report that pastes a code block for context would otherwise
    be read as claiming every line of it.
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


def _normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace/newlines to single spaces."""
    return re.sub(r"\s+", " ", text).strip()


# ── (1) anchors ───────────────────────────────────────────────────


def test_anchors_present():
    """The five bound section anchors each appear as their own line."""
    text = DOC_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    missing = [anchor for anchor in REQUIRED_ANCHORS if anchor not in lines]
    assert not missing, f"missing anchors: {missing}"


# ── (2) links ─────────────────────────────────────────────────────


def test_links_resolve():
    """Every repo-relative path the README references exists in the tree.

    Combined into a single test (rather than split) so that `-k links`
    selects exactly one node. The two sanity assertions (extraction must
    yield paths; required references must appear) plus the existence
    check are all part of the same contract.
    """
    text = DOC_PATH.read_text(encoding="utf-8")
    paths = _extract_referenced_paths(text)

    # Parser-sanity: the extraction must yield paths, not nothing.
    # An empty extraction means the document does not actually name any
    # repo path — the gate must not go green in that case.
    assert paths, "no repo-relative paths extracted from README.md"

    # Parser-sanity: the extraction must hit known anchors.
    missing_required = REQUIRED_REFERENCES - paths
    assert not missing_required, (
        f"missing required references: {sorted(missing_required)}"
    )

    # Every referenced path must exist in the repo tree.
    missing_files = [p for p in sorted(paths) if not (PROJECT_ROOT / p).exists()]
    assert not missing_files, f"missing files: {missing_files}"


# ── (3) definition ────────────────────────────────────────────────


def test_definition_verbatim():
    """The definition sentence and the name line are PRESENT VERBATIM.

    Whitespace is normalized before comparison because the README wraps
    the definition sentence across lines. A reworded sentence or name
    line MUST fail; line-wrapping must NOT fail.
    """
    text = DOC_PATH.read_text(encoding="utf-8")
    normalized = _normalize_whitespace(text)
    expected_normalized = _normalize_whitespace(DEFINITION_SENTENCE)

    assert NAME_LINE in normalized, (
        f"name line missing: {NAME_LINE!r}"
    )
    assert expected_normalized in normalized, (
        f"definition sentence missing or reworded: {expected_normalized!r}"
    )
