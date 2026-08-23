"""Tests for the gate's claim-resolution D1 fix.

Harness for the 085-shaped defect: a bare-name claim (e.g. ``config.py``)
that lives in a SUBDIRECTORY of the fence repo (e.g.
``harness-allocator/harness_allocator/config.py``) must NOT silently
fall back to a same-named root file in a foreign repo (e.g.
``DPMtF-WebUI/config.py``) — that turns the gate's own ambiguity into
an accusation of scope breach.

Hermetic fixtures: each test builds its own root tree under ``tmp_path``
and never touches the real filesystem under
``/home/svenv/home/svend/harness-allocator`` or
``/home/svend/DPMtF-WebUI``. The gate is imported exactly the way the
existing ``tests/test_gate_deliverable_evidence.py`` imports it
(importlib.util spec_from_file_location).

Every test name below contains the substring ``fence_candidate`` — that
is TG1's ``-k`` filter contract; no matching name = pytest exit 5 = red.
"""

import importlib.util
from pathlib import Path

import pytest


_GATE = (Path(__file__).resolve().parent.parent
         / "scripts" / "bridgeV002" / "gate-deliverable-evidence.py")
_spec = importlib.util.spec_from_file_location("gate_evidence_d1", _GATE)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


# ── Hermetic fixture helpers ──────────────────────────────────────────


def _make_repo(tmp_path, name, files):
    """Build a repo at ``tmp_path / name`` with the given files.

    Returns the absolute path of the repo root (a string, the shape
    ``locate()`` expects). ``files`` is ``{rel_path: content}``;
    parent directories are created as needed.
    """
    repo = tmp_path / name
    repo.mkdir()
    for rel_path, content in files.items():
        target = repo / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return str(repo)


@pytest.fixture
def two_roots_with_subdir_fence_candidate(tmp_path):
    """The 085 shape: fence repo has config.py in a subdir; foreign repo
    has config.py at its root.

    Returns ``(root_a, root_b, root_a_fence_path)`` where:
      - root_a = path of the fence repo (has ``pkg/config.py``)
      - root_b = path of the foreign repo (has ``config.py``)
      - root_a_fence_path = absolute path of ``pkg/config.py`` inside root_a
    """
    root_a = _make_repo(tmp_path, "fence_repo", {
        "pkg/config.py": "# fence config (in subdir)\n",
    })
    root_b = _make_repo(tmp_path, "foreign_repo", {
        "config.py": "# foreign config (at root)\n",
    })
    root_a_fence_path = str(Path(root_a) / "pkg" / "config.py")
    return root_a, root_b, root_a_fence_path


@pytest.fixture
def two_roots_with_ambiguous_fence_candidates(tmp_path):
    """Fence repo has TWO files named config.py in different subdirs;
    foreign repo has config.py at its root. The basename match is
    ambiguous — must report UNRESOLVED.

    Returns ``(root_a, root_b, fence_candidates_set)``.
    """
    root_a = _make_repo(tmp_path, "fence_repo", {
        "pkg1/config.py": "# pkg1 config\n",
        "pkg2/config.py": "# pkg2 config\n",
    })
    root_b = _make_repo(tmp_path, "foreign_repo", {
        "config.py": "# foreign config\n",
    })
    candidates = {
        str(Path(root_a) / "pkg1" / "config.py"),
        str(Path(root_a) / "pkg2" / "config.py"),
    }
    return root_a, root_b, candidates


@pytest.fixture
def two_roots_no_fence_candidate(tmp_path):
    """Fence prefer set contains a DIFFERENT basename (some_other.py);
    foreign repo has config.py at its root. The bare claim ``config.py``
    has no fence candidate but DOES exist outside the fence → UNRESOLVED.

    Returns ``(root_a, root_b, root_a_fence_path)``.
    """
    root_a = _make_repo(tmp_path, "fence_repo", {
        "some_other.py": "# fence has some_other.py\n",
    })
    root_b = _make_repo(tmp_path, "foreign_repo", {
        "config.py": "# foreign config\n",
    })
    root_a_fence_path = str(Path(root_a) / "some_other.py")
    return root_a, root_b, root_a_fence_path


@pytest.fixture
def root_only_no_such_file(tmp_path):
    """Fence prefer contains some_other.py; no root has config.py.
    Bare claim ``config.py`` names no existing file anywhere → non-claim.

    Returns ``(root_a, root_a_fence_path)``.
    """
    root_a = _make_repo(tmp_path, "fence_repo", {
        "some_other.py": "# only some_other\n",
    })
    root_a_fence_path = str(Path(root_a) / "some_other.py")
    return root_a, root_a_fence_path


# ── A. unique-fence-candidate resolves into the fence (the 085 fix) ──


def test_bare_name_fence_candidate_resolves_into_the_fence_repo(
        two_roots_with_subdir_fence_candidate):
    """Bare ``config.py`` with one fence candidate in a subdir → fence.

    This is the exact 085 shape. Before the fix, locate() would skip the
    prefer step (the literal ``root_a/config.py`` doesn't exist), then
    fall back to ``root_b/config.py`` (the foreign repo's root file),
    turning the gate's own ambiguity into a scope-breach accusation.
    After the fix, locate() matches the bare claim's basename against
    the prefer set BEFORE the cross-root fallback and resolves to the
    fence candidate.
    """
    root_a, root_b, fence_path = two_roots_with_subdir_fence_candidate
    roots = [root_a, root_b]
    prefer = {fence_path}

    result = gate.locate("config.py", roots, prefer=prefer)

    # Resolved into the fence repo, with the subdirectory preserved.
    assert result == (root_a, "pkg/config.py"), (
        f"bare 'config.py' with one fence candidate in a subdir must "
        f"resolve to the fence repo, not the foreign repo; got {result!r}"
    )


# ── B. multiple fence candidates → UNRESOLVED ─────────────────────────


def test_multiple_fence_candidate_matches_is_unresolved(
        two_roots_with_ambiguous_fence_candidates):
    """Bare ``config.py`` with two fence candidates → UNRESOLVED.

    The fence has ``pkg1/config.py`` and ``pkg2/config.py`` — both
    match the bare basename. The gate cannot silently pick either; the
    rejection text must name both candidates. Today's behavior (before
    the fix) silently resolves to whichever repo happens to sort
    first — the same wrong-repository pathology as item A.
    """
    root_a, root_b, candidates = two_roots_with_ambiguous_fence_candidates
    roots = [root_a, root_b]
    prefer = set(candidates)

    result = gate.locate("config.py", roots, prefer=prefer)

    # Resolved as UNRESOLVED — gate.UNRESOLVED sentinel + the candidate
    # set the rejection text must name.
    assert result[0] is gate.UNRESOLVED, (
        f"bare 'config.py' with two fence candidates must be UNRESOLVED; "
        f"got root={result[0]!r}"
    )
    assert set(result[1]) == candidates, (
        f"UNRESOLVED candidate set must be {candidates!r}; got {set(result[1])!r}"
    )


# ── C. no fence candidate + foreign-repo file → UNRESOLVED ───────────


def test_no_fence_candidate_existing_elsewhere_is_unresolved(
        two_roots_no_fence_candidate):
    """Bare ``config.py`` with no fence candidate but a foreign-repo file.

    The fence prefer set does NOT contain any file named config.py (it
    has some_other.py only). The bare claim names a file that EXISTS
    outside the fence (foreign_repo/config.py). Today's behavior
    silently falls back to the foreign repo — the same scope-breach
    accusation. After the fix, locate() reports UNRESOLVED rather than
    silently resolving into the foreign repo.
    """
    root_a, root_b, fence_path = two_roots_no_fence_candidate
    roots = [root_a, root_b]
    prefer = {fence_path}

    result = gate.locate("config.py", roots, prefer=prefer)

    # Resolved as UNRESOLVED — not silently resolved to the foreign
    # repo's config.py.
    assert result[0] is gate.UNRESOLVED, (
        f"bare 'config.py' that exists only outside the fence must be "
        f"UNRESOLVED, not silently resolved to the foreign repo; "
        f"got root={result[0]!r}"
    )
    # The candidate set must contain the foreign-repo file (the one the
    # OLD code would have silently picked) — the rejection text names it.
    foreign = str(Path(root_b) / "config.py")
    assert foreign in result[1], (
        f"UNRESOLVED candidate set must contain the foreign-repo file "
        f"{foreign!r}; got {set(result[1])!r}"
    )


# ── D. no fence candidate + no file anywhere → non-claim (preserved) ─


def test_no_fence_candidate_nonexistent_stays_non_claim(
        root_only_no_such_file):
    """Bare ``config.py`` that names NO existing file anywhere stays a
    non-claim (today's behavior, protected by the nothing-that-passes-
    today-may-start-failing rule).

    The fix must preserve today's ``(None, None)`` return for a claim
    that resolves to nothing — past failure modes (e.g. the
    new-webui-skeleton misresolution) relied on this restraint.
    """
    root_a, fence_path = root_only_no_such_file
    roots = [root_a]
    prefer = {fence_path}

    result = gate.locate("config.py", roots, prefer=prefer)

    # Today's behavior preserved: (None, None) — the bare name doesn't
    # name a real file in any repo, so it's not a claim.
    assert result == (None, None), (
        f"bare 'config.py' naming no existing file must stay a "
        f"non-claim ((None, None)); got {result!r}"
    )
