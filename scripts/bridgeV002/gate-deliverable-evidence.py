#!/usr/bin/env python3
"""Evidence gate — refuse deliverables that claim changes which never happened.

Governance forbids fabricating an implementation report or a verdict, but a
prohibition cannot stop a model from asserting it did the work. On
2026-08-05 an implementer reported three file changes in convincing detail,
including a pasted grep output reading "Returns ZERO results after changes",
having touched nothing. The reviewer read that report instead of the
repository and returned APPROVED. Both roles agreed, and both were wrong.

This script is the part that does not depend on a model telling the truth.
It runs as a pre-dispatch gate, so it sees the deliverable the previous role
just wrote before the next role is ever told about it, and it fails closed:
a deliverable whose claims do not survive contact with the working tree does
not get to move down the chain.

Two checks, both deterministic:

1. Every file the deliverable claims to have changed must show evidence of
   having been changed during this handoff — named by `git status` (with
   untracked files expanded, never collapsed to a directory), or modified
   after this step began. A file that exists and is untouched is the exact
   signature of a fabricated report.
2. A verdict must carry real evidence: an Evidence section, or command
   output. A verdict that only asserts is not a verdict.

Exit 0 = pass, exit 1 = blocked. In `--mode warn` it reports and exits 0,
for rolling the gate out on a flow before trusting it to stop the chain.
"""

import argparse
import calendar
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = os.environ.get(
    "DPMTF_PROJECT_ROOT",
    str(Path(__file__).resolve().parent.parent.parent),
)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bridge_lib  # noqa: E402  — the ONE artifact-root resolver (two-flow spec §2)

from scripts.testing.git_changes import changed_files  # noqa: E402  — D1 shared change detector

# Extensions worth checking. A claim about a file we cannot classify as
# source or documentation is not worth a false positive.
CODE_SUFFIXES = {
    ".py", ".js", ".css", ".html", ".md", ".yaml", ".yml", ".json",
    ".sh", ".sql", ".ini", ".txt", ".toml", ".cfg",
}

# Headings under which a report lists what it changed. Claims found here are
# the ones the gate holds the deliverable to.
CHANGE_HEADING = re.compile(
    r"^#{1,6}\s*.*\bfiles?\b.*\b(chang|modif|edit|updat|touch)", re.I)
ANY_HEADING = re.compile(r"^#{1,6}\s")

# ...unless the heading denies the change it names. preferred_cloud run 007
# blocked a verdict whose heading read "Scope compliance — no file outside the
# fence was edited": it contains `file` and `edited`, so every path named in
# prose beneath it became a claim, and the gate then found — correctly — that
# none of them had changed. The word "no" was invisible to the pattern above.
#
# This is `_is_denial` one level up. That taught the gate that a *sentence*
# saying a file is untouched is not a claim; nothing said the same of a
# *heading*. The report being punished was proving `app.py`'s mtime predated
# the run, which was the whole safety property that run existed to establish —
# a gate must never make naming a file to prove it did not change the risky
# thing to do.
_HEADING_DENIAL = re.compile(
    r"\b(no|none|not|never|without|un(chang|modif|touch|edit)ed)\b", re.I)


def _heading_denies(line):
    """True when a heading names a change only to deny it."""
    return bool(_HEADING_DENIAL.search(line))

# A path-like token: at least one slash or a bare filename with a suffix.
PATH_TOKEN = re.compile(r"[A-Za-z0-9._/\-]+")

EVIDENCE_MARKERS = (
    re.compile(r"^#{1,6}\s*.*\bevidence\b", re.I),
    re.compile(r"^\s*\$\s+\S"),          # a shell command line
    re.compile(r"^\s*```(?:bash|sh|console)?\s*$"),
)


def _db_path():
    import config as _cfg
    p = _cfg.get_db_path()
    if not os.path.isabs(p):
        p = os.path.join(PROJECT_ROOT, p)
    return p


def target_projects(flow_key):
    """Repositories a claim may legitimately refer to.

    A flow's configured target plus Father: cross-repo handoffs are normal
    (llama_SG changes both DPMtF-WebUI and model-allocator), so a claim is
    checked against whichever repo actually contains the file. Repositories
    the handoff additionally governs are added separately by
    `declared_scope_roots`. This function must NOT sweep every sibling git
    repository: doing so attributed unrelated human work in
    AI-Genealogy-Research-Assistant to preferred_cloud_harness merely because
    it shared the home directory.
    """
    roots = []
    try:
        import sqlite3
        conn = sqlite3.connect(_db_path())
        row = conn.execute(
            "SELECT target_project_path FROM bridge_flows WHERE flow_key = ?",
            (flow_key,),
        ).fetchone()
        conn.close()
        if row and row[0]:
            roots.append(row[0])
    except Exception:
        pass
    if PROJECT_ROOT not in roots:
        roots.append(PROJECT_ROOT)
    return roots


def git_dirty_files(repo_root):
    """Return a dict of relative_path → git_status_code.

    Delegates to D1's ``changed_files()`` and maps the five-label vocabulary
    back to git's two-character ``--name-status`` codes so that the gate's
    existing verification logic (which checks codes, not labels) works
    unchanged.

    Mapping:
        "modified"   → " M"
        "added"      → "A "
        "deleted"    → "D "
        "renamed"    → " R"
        "untracked"  → "??"
    """
    code_map = {
        "modified":   " M",
        "added":      "A ",
        "deleted":    "D ",
        "renamed":    " R",
        "untracked":  "??",
    }
    labels = changed_files(repo_root, include_untracked=True)
    return {path: code_map[label] for path, label in labels.items()}


# Phrases that turn a sentence naming files into a statement about what was
# NOT done. 03_IMPLEMENTOR and every flow's role file ask for exactly this —
# "doing nothing is a legitimate result, say so plainly" — so reading such a
# line as a claim punishes the behaviour the contract requires.
#
# preferred_cloud handoff 002, 2026-08-06: a report pasted real `git status`
# output showing one new file, then wrote "GOAL.md, README.md, pyproject.toml,
# .env.example, .gitignore are untouched." The gate took GOAL.md from that
# line, found it unchanged — which was the point — and rejected an honest
# report. Fourth false-positive shape in this function's history, and the
# first where the deliverable was penalised for being explicit.
_DENIAL = re.compile(
    r"\b(untouched|unchanged|not (?:modified|changed|touched|edited)|"
    r"never (?:written|modified|touched|changed)|no changes? to|"
    r"left alone|read but never written)\b",
    re.IGNORECASE,
)


def _is_denial(line):
    """True when the line says these files were NOT changed.

    Strips inline emphasis markup before matching the denial regex: a
    denial whose negation is wrapped in emphasis markers (double-asterisk
    bold, single-asterisk italic, underscore bold, underscore italic,
    or backticks) is still a denial. The strip runs on a COPY of the
    line used ONLY for the denial decision -- path extraction in
    claimed_paths() sees the ORIGINAL line and is unaffected, so
    underscores inside identifiers (e.g. test_qwen_adapter.py) survive
    in the path-extraction pass.

    D2 fix (run 023, handoff 089): the 085 shape was a denial line whose
    NOT was wrapped in emphasis (a doubled asterisk before, another after).
    The plain-text _DENIAL regex requires 'not' and its verb to be
    ADJACENT, and the emphasis wrapping breaks that adjacency. After
    emphasis stripping, that line reads as 'NOT touched' and the denial
    regex matches exactly as it does for plain-text forms the gate has
    always recognized.
    """
    stripped = re.sub(r"\*\*|\*|__|_|`", "", line)
    return bool(_DENIAL.search(stripped))


def claimed_paths(text):
    """File paths the deliverable says it changed.

    Prefers an explicit "Files Changed" section: a report that names its
    changes there is making a specific, checkable claim. Without such a
    section, list items elsewhere are scanned — but prose is left alone,
    because a path mentioned in passing is not a claim.
    """
    lines = text.splitlines()
    in_change_section = False
    saw_change_section = False
    in_fence = False
    candidates = []

    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            # Fenced blocks hold pasted command output — that is evidence,
            # not a claim. A report that pastes `git status` for context
            # would otherwise be read as claiming every line of it, which
            # is how an honest report gets accused of taking credit.
            continue
        if ANY_HEADING.match(line):
            in_change_section = (bool(CHANGE_HEADING.match(line))
                                 and not _heading_denies(line))
            saw_change_section = saw_change_section or in_change_section
            continue
        # Claims come from a "Files Changed" section and nowhere else. The
        # previous fallback — scan every list item when no such section
        # exists — produced three separate false rejections in one day, each
        # time on a deliverable doing exactly what the contract asked. It
        # read the commands a reviewer ran as files it had changed, then the
        # files where each environment variable is defined, then a filename
        # that happened to exist in an unrelated project.
        #
        # The distinction it kept getting wrong is not decidable from prose:
        # a filename in a sentence may be a claim, a reference, a command
        # argument or an example. Only a Files Changed section says "these
        # are mine". Absent one, there are no claims to check — and nothing
        # is lost, because undeclared_changes() still compares the working
        # tree against the scope fence, and a verdict must still carry real
        # evidence.
        # Inside the section, a claim is the line that names the file. An
        # indented continuation under it describes the change — "Added a
        # reference to SETUP.md" names the file the change points at, not a
        # second file that was edited.
        is_continuation = bool(re.match(r"^\s{2,}\S", line))
        if in_change_section and not is_continuation and not _is_denial(line):
            candidates.append(line)

    found = []
    for line in candidates:
        # An inline code span containing a space is a command, not a
        # filename: `node --check static/js/*.js` names the files it
        # checked. A claim is a bare path — `.env.example` — with no space
        # in it. Strip the commands before looking for paths, or a verdict
        # is accused of having changed everything it validated. That is
        # what the contract asks the reviewer to run, so the gate must not
        # punish it for running them.
        line = re.sub(r"`[^`]*\s[^`]*`", " ", line)
        cleaned = line.replace("`", " ").replace("*", " ").replace("**", " ")
        for token in PATH_TOKEN.findall(cleaned):
            token = token.strip("._-")
            if Path(token).suffix.lower() not in CODE_SUFFIXES:
                continue
            if token not in found:
                found.append(token)
            # Only the FIRST path on a line is the file being claimed. The
            # rest describe it: "README.md | Modified — added SETUP.md
            # reference" changes one file and mentions another. Treating
            # every path as a claim rejected an exemplary report that said,
            # in the same table, "No other files were modified" — and a gate
            # that punishes honest work is worse than no gate at all.
            break
    return found


# Sentinel for an unresolved bare-name claim: the bare name matches
# multiple fence candidates (ambiguous), or a same-named file exists
# outside the fence (foreign-repo shape). The rejection text must name
# the candidate set so the implementer can resolve the ambiguity — an
# actionable refusal. The D1 fix (run 023) introduces this; before,
# locate() silently picked whichever repo happened to sort first,
# turning the gate's own ambiguity into a scope-breach accusation
# (the exact 085 misresolution).
class _UnresolvedSentinel:
    def __repr__(self):
        return "<UNRESOLVED>"


UNRESOLVED = _UnresolvedSentinel()
def locate(path_claim, roots, prefer=None):
    """Resolve a claimed path to (repo_root, relative_path) if it exists.

    `prefer` is the set of absolute paths the handoff's scope fence allows.
    It only breaks ties for ambiguous relative names; it never invents a
    match that does not exist on disk.

    For a BARE claim (no "/" in it) and a non-empty `prefer`, the gate
    matches the claim's BASENAME against `prefer` BEFORE the cross-root
    fallback (the D1 fix from run 023 — the 085 misresolution): a bare
    name that lives in a SUBDIRECTORY of the fence repo (e.g.
    `harness_allocator/config.py` inside `harness-allocator/`) must
    resolve into the fence repo, not silently fall back to a same-named
    root file in a foreign repo. A unique basename match in `prefer`
    resolves THERE; multiple matches → UNRESOLVED (with the candidate
    set, so the rejection text is actionable); no match → fall through
    to today's logic with the foreign-repo fallback downgraded to
    UNRESOLVED (so the gate never silently picks a foreign-repo file).

    Order matters. A claim often carries the repo name as its first segment
    ("model-allocator/README.md"), and several repos hold files with the
    same relative name — every one of them has a README.md. Matching the
    repo name first stops the gate from checking the wrong repository's
    file and reporting a mtime that belongs to somebody else.
    """
    if os.path.isabs(path_claim):
        for root in roots:
            if path_claim.startswith(root.rstrip("/") + "/"):
                if os.path.exists(path_claim):
                    return root, os.path.relpath(path_claim, root)
        return (None, None)

    segments = path_claim.split("/")
    # 1. First segment names a repo -> resolve inside exactly that repo.
    if len(segments) > 1:
        remainder = "/".join(segments[1:])
        for root in roots:
            if os.path.basename(root.rstrip("/")) == segments[0]:
                full = os.path.join(root, remainder)
                return (root, remainder) if os.path.exists(full) else (None, None)

    is_bare = "/" not in path_claim

    # 2. Bare-name basename match against the scope fence (D1 fix).
    #    A bare claim's basename is matched against `prefer` BEFORE the
    #    cross-root fallback. Unique match → resolve into the fence
    #    (preserving its subdirectory). Multiple matches → UNRESOLVED.
    if prefer and is_bare:
        basename = os.path.basename(path_claim)
        fence_matches = [p for p in prefer if os.path.basename(p) == basename]
        if len(fence_matches) == 1:
            full = fence_matches[0]
            fence_root = next(
                (r for r in roots
                 if full.startswith(r.rstrip("/") + "/")),
                None,
            )
            if fence_root is not None:
                return fence_root, os.path.relpath(full, fence_root)
        if len(fence_matches) > 1:
            return (UNRESOLVED, sorted(fence_matches))

    # 3. Path as given, relative to each repo. When the name is ambiguous —
    #    every repo here has a README.md, a config.py, a tests/ — let the
    #    scope fence break the tie. A report that writes the bare name means
    #    the file the handoff asked about, and resolving to whichever repo
    #    happens to sort first turns the gate's own ambiguity into an
    #    accusation of scope breach.
    if prefer:
        for root in roots:
            full = os.path.join(root, path_claim)
            if os.path.exists(full) and full in prefer:
                return root, path_claim

    # 4. Cross-root fallback. When `prefer` is empty/None, today's behavior
    #    is preserved: silently pick the first repo whose root has the
    #    bare-name file. When `prefer` is non-empty AND no fence candidate
    #    matched, a foreign-repo match is reported as UNRESOLVED rather
    #    than silently picked (the 085 pathology). A bare claim naming NO
    #    existing file anywhere stays (None, None) — today's behavior,
    #    protected by the nothing-that-passes-today-may-start-failing rule.
    if not prefer:
        for root in roots:
            full = os.path.join(root, path_claim)
            if os.path.exists(full):
                return root, path_claim
        return (None, None)

    # prefer is non-empty and bare: collect foreign-repo matches as
    # UNRESOLVED candidates; report them in the rejection text.
    if is_bare:
        foreign = sorted(
            os.path.join(root, path_claim)
            for root in roots
            if os.path.exists(os.path.join(root, path_claim))
        )
        if foreign:
            return (UNRESOLVED, foreign)

    # Deliberately no third attempt. Stripping a leading directory that
    # named no known repository and searching every root again is guesswork:
    # it resolved `new-webui-skeleton/static/js/app.js` to an unrelated
    # project's `static/js/app.js` and accused a verdict of changing a file
    # in a repository the flow has never touched. A path that resolves
    # neither as given nor under a named repo is not a file claim, and the
    # safe reading of "I cannot tell what this is" is to say nothing.
    return (None, None)


SCOPE_ALLOW_HEADING = re.compile(r"allowed\s+to\s+change", re.I)
SCOPE_DENY_HEADING = re.compile(
    r"must\s+not\s+change|forbidden|out\s+of\s+scope|do\s+not\s+change", re.I)

# A fence entry that names its files with a wildcard. PATH_TOKEN cannot see
# these: the emphasis-stripping below turns `patcher/engines/*.py` into
# `patcher/engines/ .py` before tokenizing, so the glob never reached
# matching. That is how run 018's result 051 was rejected twice for touching
# two files its fence expressly allowed — the literal paths on the same
# comma-separated line resolved, the glob's files did not, and the run
# parked on a false scope breach. Run 017 paid the same way.
GLOB_TOKEN = re.compile(r"[A-Za-z0-9._/\-*?]+")


def _expand_glob(pattern, roots):
    """Absolute paths of existing files a fence glob matches, per repo.

    Only files with a suffix the gate checks count, mirroring the literal
    entries. A pattern containing `..` is refused outright — a fence must
    not reach outside the repository it names.
    """
    found = set()
    if ".." in pattern.split("/"):
        return found
    for root in roots:
        rel = pattern
        if os.path.isabs(rel):
            if not rel.startswith(root.rstrip("/") + "/"):
                continue
            rel = os.path.relpath(rel, root)
        try:
            hits = list(Path(root).glob(rel))
        except (ValueError, NotImplementedError, OSError):
            continue
        for hit in hits:
            if hit.is_file() and hit.suffix.lower() in CODE_SUFFIXES:
                found.add(str(hit))
    return found


def _expand_dir(token, roots):
    """Absolute paths of existing files beneath a directory fence entry.

    A scope entry may name a directory, with or without a trailing slash
    (`tests/`, `harness_allocator/`). Such an entry authorizes every file
    beneath it — the directory itself is never a claim, but the files under
    it are. The old parser only kept tokens with a recognised filename
    suffix, so a directory entry was dropped and every file inside it was
    then reported as a scope breach. preferred_cloud_harness run 004 handoff
    017 paid for that: `/home/svend/harness-allocator/tests/` was invisible
    to the fence and the implementer's test file was rejected.

    Mirrors `_expand_glob`'s containment rules: `..` is refused, and only
    existing files with a checked suffix count.
    """
    found = set()
    if ".." in token.split("/"):
        return found
    for root in roots:
        rel = token
        if os.path.isabs(rel):
            if not rel.startswith(root.rstrip("/") + "/"):
                continue
            rel = os.path.relpath(rel, root)
        if not rel or rel == ".":
            continue            # a bare marker or "." must not mean the repo
        base = Path(root) / rel
        if not base.is_dir():
            continue
        try:
            for hit in base.rglob("*"):
                if hit.is_file() and hit.suffix.lower() in CODE_SUFFIXES:
                    found.add(str(hit))
        except (ValueError, OSError):
            continue
    return found


def _scope_block(text):
    """The handoff's `<scope>` fence body, or None.

    The tag must open a line. A handoff that mentions `<scope>` in prose —
    "the model-allocator repo will be tempting, see `<scope>`" — used to win
    this match 170 lines above the real block, and the gate then enforced the
    handoff's *read* list as if it were the write list. Falls back to a
    markdown `## Scope fence` heading block for handoffs written without the
    XML tag.
    """
    match = re.search(r"^[ \t]*<scope>(.*?)^[ \t]*</scope>", text,
                      re.S | re.I | re.M)
    if match:
        return match.group(1)
    match = re.search(r"^#{1,6}\s*scope\s+fence\s*$(.*?)(?=^#{1,6}\s|\Z)",
                      text, re.S | re.I | re.M)
    return match.group(1) if match else None


def _repo_root_of(abs_path, known_roots):
    """The repository root an absolute fence path lives under, or None.

    Walks up from the path to the nearest directory that looks like a git
    repository (has a `.git` child) or one of the known roots. A directory
    whose `.git` is not a real repository still yields an empty dirty set in
    `git_dirty_files` (git fails closed), so no false attribution follows.
    """
    cur = abs_path.rstrip("/")
    while True:
        if cur in known_roots:
            return cur
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def declared_scope_roots(handoff_path, known_roots):
    """Repo roots the handoff's scope fence explicitly declares as governed.

    A cross-repo handoff names absolute paths in its "Allowed to change"
    fence (e.g. `/home/svend/model-allocator/README.md`). The repositories
    those paths live under are part of this handoff's evidence surface. The
    "MUST NOT change" entries are explicitly NOT governed, so they
    contribute nothing — including them would pull a forbidden sibling
    repo's dirty files back into the attribution the gate exists to prevent.
    """
    try:
        text = Path(handoff_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    block = _scope_block(text)
    if block is None:
        return []

    roots = []
    listing_allowed = True
    for line in block.splitlines():
        if SCOPE_ALLOW_HEADING.search(line):
            listing_allowed = True
            continue
        if SCOPE_DENY_HEADING.search(line):
            listing_allowed = False
            continue
        if not listing_allowed:
            continue
        if not re.match(r"^\s*(?:[-*+]|\d+\.)\s", line):
            continue
        cleaned = line.replace("`", " ").replace("*", " ")
        if SCOPE_DENY_HEADING.search(cleaned):
            continue
        for token in PATH_TOKEN.findall(cleaned):
            token = token.strip("._-")
            if not os.path.isabs(token):
                continue
            root = _repo_root_of(token, known_roots)
            if root and root not in roots:
                roots.append(root)
    return roots


def scope_allowed(handoff_path, roots):
    """Absolute paths the handoff permits changing, or None if unparseable.

    Returns None — not an empty set — when no scope fence can be read. An
    unreadable fence must not be mistaken for "nothing is allowed", or the
    gate would reject every deliverable in a flow whose handoffs are shaped
    differently.
    """
    try:
        text = Path(handoff_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    block = _scope_block(text)
    if block is None:
        return None

    allowed = set()
    listing_allowed = True      # entries before any subheading count as allowed
    saw_any_heading = False
    for line in block.splitlines():
        if SCOPE_ALLOW_HEADING.search(line):
            listing_allowed, saw_any_heading = True, True
            continue
        if SCOPE_DENY_HEADING.search(line):
            listing_allowed, saw_any_heading = False, True
            continue
        if not listing_allowed:
            continue
        if not re.match(r"^\s*(?:[-*+]|\d+\.)\s", line):
            continue
        cleaned = line.replace("`", " ").replace("*", " ")
        # An entry that excludes itself in its own text is not a permission.
        if SCOPE_DENY_HEADING.search(cleaned):
            continue
        # Glob pass, on the line BEFORE emphasis-stripping eats the `*`.
        # A token wrapped in asterisks on both ends is markdown emphasis
        # (**bold**, *italic*), not a glob — unwrap it and let the literal
        # pass below pick up what remains.
        line_has_glob = False
        for token in GLOB_TOKEN.findall(line.replace("`", " ")):
            token = token.strip("._-")
            while (len(token) > 1 and token.startswith("*")
                   and token.endswith("*")):
                token = token[1:-1]
            if "*" in token or "?" in token:
                line_has_glob = True
                allowed |= _expand_glob(token, roots)
        for token in PATH_TOKEN.findall(cleaned):
            token = token.strip("._-")
            if not token:
                continue        # a bare list marker ("-" → "") is not a path
            if Path(token).suffix.lower() in CODE_SUFFIXES:
                root, rel = locate(token, roots)
                if root:
                    allowed.add(os.path.join(root, rel))
            elif not line_has_glob and "/" in token:
                # A bare directory entry — `/home/svend/.../tests/` — has no
                # filename suffix, so the old suffix gate dropped it and then
                # reported every file beneath it as a scope breach. A fence
                # entry that names an existing directory authorizes the files
                # under it. A glob line already enumerated its matches above,
                # so do NOT also widen it to the whole directory. Only a
                # path-shaped token counts — a bare prose word such as "tests"
                # in "(new/extended tests)" must not expand every repo's
                # `tests/` directory.
                allowed |= _expand_dir(token, roots)

    if not allowed and not saw_any_heading:
        return None
    return allowed


def same_name_in_scope(full, allowed):
    """An in-scope file sharing this one's filename in a different directory.

    The signature of a wrong-repository edit. Handoff 006 named
    `/home/svend/model-allocator/README.md` in its project block, its scope
    fence and its working set — and then said "read the current README.md"
    in the instruction step. The implementer, sitting in DPMtF-WebUI, edited
    that repository's README instead. Saying which file it probably meant
    turns a generic refusal into something the role can act on.
    """
    if not allowed:
        return None
    base = os.path.basename(full)
    for candidate in sorted(allowed):
        if candidate != full and os.path.basename(candidate) == base:
            return candidate
    return None


def owns_the_fence(deliverable_pattern, deliverable_file):
    """True when this deliverable belongs to the role the handoff fenced.

    A handoff addresses one role and fences that role's files. Only that
    role's own deliverable can be held to the fence: every later step in the
    cycle inherits the same working tree and has no way to change what it
    finds there.
    """
    kind = (deliverable_pattern or deliverable_file or "").lower()
    return not ("verdict" in kind or "review" in kind)


def undeclared_changes(roots, dirty_by_root, allowed, since):
    """Files changed during this handoff that the scope fence does not allow.

    The claim checks ask "is what the report says true?". This asks the
    other question: "is what happened in the repository allowed?" A role
    that edits the wrong file and simply does not mention it passes every
    other check, because there is no claim to test.

    Only files touched *after* the handoff was written count, which is what
    keeps the Human's own in-flight work — always older — out of the
    result. `DPMTF_GATE_IGNORE_PATHS` takes a comma-separated list of path
    fragments to exclude when that is not enough.
    """
    if allowed is None:
        return []          # no fence to enforce
    ignore = [p.strip() for p in
              os.environ.get("DPMTF_GATE_IGNORE_PATHS", "").split(",")
              if p.strip()]
    # A tool cannot police its own source. This file is never inside a
    # role's scope fence, so a change to it is always the Human's — and
    # blocking the chain because the gate was being repaired mid-run helps
    # nobody. Every other path stays policed, including the rest of
    # scripts/bridgeV002/.
    ignore.append(os.path.abspath(__file__))
    found = []
    for root, dirty in dirty_by_root.items():
        for rel in sorted(dirty):
            if Path(rel).suffix.lower() not in CODE_SUFFIXES:
                continue          # databases, logs, pid files — not source
            full = os.path.join(root, rel)
            if full in allowed:
                continue
            if any(frag in full for frag in ignore):
                continue
            try:
                if os.stat(full).st_mtime < since:
                    continue      # predates the handoff — not this role's doing
            except OSError:
                continue
            found.append(full)
    return found


def dispatch_time(bridge_dir, handoff_id, to_role):
    """When `trace.log` recorded this handoff being dispatched TO *to_role*.

    Preferred over the handoff file's own mtime, because the dispatcher
    rewrites that file *after* dispatching it: `auto_prepend` supplies the
    XML sections a model omitted, and the rewrite advances the mtime.

    preferred_cloud run 024 paid for it. Handoff 073 was dispatched at
    18:35:22Z, the implementer wrote all four of its files by 18:36:32Z, and
    auto_prepend rewrote the handoff at 18:39:24Z. Every delivered file
    therefore predated a clock that is supposed to mark when the role
    STARTED, and the gate reported "no change during this handoff" about work
    done three minutes into the handoff. The role had done everything right.

    Fields are compared by position, never as substrings. `| 073 |` alone
    also matches another flow's handoff 073 from a different day — the log is
    flow-wide and the id counter is not — and the role pair is the only thing
    in a line that identifies the flow.
    """
    if not (bridge_dir and handoff_id and to_role):
        return None
    path = Path(bridge_dir, "trace.log")
    found = None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                fields = [f.strip() for f in line.split("|")]
                if len(fields) < 4:
                    continue
                if fields[2] != str(handoff_id) or fields[3] != "dispatched":
                    continue
                if "->" not in fields[1]:
                    continue
                if fields[1].split("->", 1)[1].strip() != to_role:
                    continue
                try:
                    # The log is UTC; st_mtime is epoch. timegm converts
                    # without going through local time, which is what makes
                    # the two comparable at all.
                    found = calendar.timegm(
                        time.strptime(fields[0], "%Y-%m-%dT%H:%M:%SZ"))
                except ValueError:
                    continue
    except OSError:
        return None
    return found


def handoff_mtime(bridge_dir, flow_key, handoff_id, gated_deliverable="",
                  to_role=""):
    """The clock a change must postdate: when THIS STEP started.

    This used to be the handoff's own mtime, for every step of the chain.
    preferred_cloud run 010 paid for that: the implementer edited a file,
    DECLARED it, and the gate accepted -- then blocked the reviewer's
    verdict two steps later, because the same edit still postdated the
    handoff and the verdict's fence did not allow the file. An mtime was
    read as authorship. The declared-and-accepted change bought exactly one
    step of peace.

    The comparison point is now the newest of the handoff and every earlier
    deliverable of the same chain id -- i.e. when the step being gated
    actually began. Work done before the previous role handed over cannot
    be this role's doing, whoever did it. The deliverable being gated is
    excluded from the scan, or it would always win.
    """
    times = []
    if bridge_dir and flow_key and handoff_id:
        gated = os.path.realpath(gated_deliverable) if gated_deliverable else ""
        # Effective artifact root, not the flow key (two-flow spec §2).
        root = bridge_lib.get_effective_artifact_root(flow_key)
        handoff_file = os.path.realpath(str(Path(
            bridge_dir, root, "handoffs", f"{handoff_id}-handoff.md")))
        dispatched = dispatch_time(bridge_dir, handoff_id, to_role)
        for path in Path(bridge_dir, root).glob(f"*/{handoff_id}-*.md"):
            real = os.path.realpath(str(path))
            if gated and real == gated:
                continue
            if path.name.endswith("-gate-rejection.md"):
                # This gate's own rejection notice, which it writes next to
                # the deliverable it refused. Counting it makes a first
                # rejection self-fulfilling: attempt 2 compares against the
                # timestamp of attempt 1's refusal, so any file the role does
                # not re-touch is guaranteed to fail again, and the run
                # escalates over a clock it set itself. run 024, handoff 073.
                continue
            if path.name.endswith("-notification.md"):
                # Written by the signalling role itself at signal time, so it
                # always postdates the work it announces. Counting it moves
                # the step-start cutoff past every file the role created, and
                # untracked files — which have only the mtime test — fail on
                # every attempt. Same self-fulfilling clock as the rejection
                # notice above. run 050, handoff 138.
                continue
            if real == handoff_file and dispatched is not None:
                # When this role was handed the work, per trace.log — not
                # when the dispatcher last rewrote the file. See dispatch_time.
                times.append(dispatched)
                continue
            try:
                times.append(path.stat().st_mtime)
            except OSError:
                pass
    if times:
        return max(times)
    return time.time() - 24 * 3600      # fall back to "today"


def has_real_evidence(text):
    for line in text.splitlines():
        for marker in EVIDENCE_MARKERS:
            if marker.match(line):
                return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deliverable-file", default="")
    parser.add_argument("--deliverable-dir", default="")
    parser.add_argument("--deliverable-pattern", default="")
    parser.add_argument("--handoff-id", default="")
    parser.add_argument("--flow-key", default="")
    parser.add_argument("--from-role", default="")
    parser.add_argument("--to-role", default="")
    parser.add_argument("--bridge-dir", default="")
    parser.add_argument("--step-key", default="")
    parser.add_argument("--prompt-template", default="")
    parser.add_argument("--mode", choices=("block", "warn"), default="block")
    args = parser.parse_args()

    # Per-flow enforcement is decided by wiring the hook into that flow's
    # steps. This is the global override — a kill switch for rolling the
    # gate out on a flow, or for standing it down without editing the
    # database mid-run.
    env_mode = os.environ.get("DPMTF_EVIDENCE_GATE_MODE", "").strip().lower()
    if env_mode in ("block", "warn"):
        args.mode = env_mode

    bridge_dir = args.bridge_dir or os.environ.get(
        "DPMTF_BRIDGE_DIR", os.path.expanduser("~/flows"))

    # dispatch passes deliverable_file as a BARE FILENAME ("005-result.md")
    # and deliverable_dir relative to the bridge root ("llama_SG/results").
    # Treating the filename as a path made the gate look in the caller's
    # working directory, find nothing, and pass everything — a gate that
    # fails open is worse than no gate, because it also reports success.
    base = args.deliverable_dir
    if base and not os.path.isabs(base):
        base = os.path.join(bridge_dir, base)

    name = args.deliverable_file
    if not name and args.deliverable_pattern:
        name = args.deliverable_pattern.replace("{ID}", args.handoff_id)

    if not name:
        path = ""
    elif os.path.isabs(name):
        path = name
    elif base:
        path = os.path.join(base, name)
    else:
        path = name

    if not path or not os.path.exists(path):
        # Nothing to gate. A missing deliverable is a different failure and
        # already has its own check in dispatch.
        print(f"  Evidence gate: no deliverable at {path or '(unresolved)'} — skipped")
        return 0

    text = Path(path).read_text(encoding="utf-8", errors="replace")
    kind = "verdict" if "verdict" in os.path.basename(path).lower() else "result"
    problems = []

    if kind == "verdict" and not has_real_evidence(text):
        problems.append(
            "verdict carries no Evidence section and no command output — "
            "it asserts without showing anything was checked")

    handoff_path = os.path.join(
        bridge_dir, bridge_lib.get_effective_artifact_root(args.flow_key),
        "handoffs", f"{args.handoff_id}-handoff.md")

    roots = target_projects(args.flow_key)
    # A cross-repo handoff declares the extra repositories it governs in its
    # scope fence. Add those — and only those — to the evidence surface. This
    # is the replacement for the old sibling-repo sweep, which took every git
    # repo under the home directory and attributed unrelated work to the flow.
    for extra in declared_scope_roots(handoff_path, roots):
        if extra not in roots:
            roots.append(extra)

    dirty_by_root = {root: git_dirty_files(root) for root in roots}
    since = handoff_mtime(bridge_dir, args.flow_key, args.handoff_id,
                          gated_deliverable=path, to_role=args.from_role)

    allowed = scope_allowed(handoff_path, roots)

    unchanged = []
    out_of_scope = []
    unresolved = []
    checked = 0
    for claim in claimed_paths(text):
        result = locate(claim, roots, prefer=allowed)
        # UNRESOLVED (D1 fix — run 023): the bare-name basename matched
        # multiple fence candidates, or a foreign-repo file matched when
        # the fence had no candidate. Report as an actionable refusal
        # naming the candidate set, not silently skip.
        if isinstance(result, tuple) and len(result) == 2                 and result[0] is UNRESOLVED:
            unresolved.append((claim, result[1]))
            continue
        root, rel = result
        if root is None:
            continue          # not a real path in any repo — not a file claim
        checked += 1
        full = os.path.join(root, rel)

        if allowed is not None and full not in allowed:
            out_of_scope.append((claim, full))

        # A tracked modification is proof the file changed. An untracked one
        # is not: `??` means "not in git", which a file created three
        # handoffs ago wears just as well as one created a minute ago. Since
        # expanding the untracked listing above made every such file visible
        # here, taking `??` as proof would let a role claim a change to any
        # untracked file in the repository and pass. Untracked files fall
        # through to the mtime test, which — measured from when this step
        # actually began — is a real authorship signal for them.
        code = dirty_by_root.get(root, {}).get(rel, "")
        if code and not code.startswith("??"):
            continue
        try:
            if os.stat(full).st_mtime >= since:
                continue
        except OSError:
            continue
        unchanged.append((claim, full, os.stat(full).st_mtime))

    # The checks above hold the report to the repository. This one holds the
    # repository to the handoff: a file changed during this handoff that the
    # fence does not allow, and that the report never mentions, is invisible
    # to every other check. It happened on 2026-08-05 — an implementer edited
    # DPMtF-WebUI's README instead of model-allocator's, said nothing, and
    # neither the gate, the reviewer nor the supervisor noticed.
    # ...but only against the role the fence belongs to. preferred_cloud run
    # 010 paid for the difference. An implementer temporarily reverted a file
    # under its handoff's explicit authorisation, restored it, declared it,
    # and passed. Four minutes later the same file blocked the REVIEWER's
    # verdict — and the second thing that had advanced its mtime was the
    # reviewer re-running the implementer's demonstration during review, which
    # is exactly what 473 asks of it. The gate punished independent
    # verification.
    #
    # Worse, the remedy it prints is unavailable to a reviewer: a verdict
    # cannot carry a "Files changed" heading without stating a falsehood, and
    # claimed_paths() reads declarations from nothing else. The reviewer wrote
    # an honest "Note on <file>'s mtime" section and the gate could not see it.
    if owns_the_fence(args.deliverable_pattern, args.deliverable_file):
        undeclared = undeclared_changes(roots, dirty_by_root, allowed, since)
    else:
        undeclared = []

    if unresolved:
        # Actionable refusal (D1 fix — run 023): name the claim and its
        # candidate set so the implementer can resolve the ambiguity.
        details = "; ".join(
            f"{claim!r} matches {candidates!r}"
            for claim, candidates in unresolved
        )
        problems.append(
            f"{len(unresolved)} claimed file(s) are unresolved (bare-name "
            f"ambiguity — no fence candidate or multiple fence candidates): "
            f"{details}")
    if unchanged:
        problems.append(
            f"{len(unchanged)} of {checked} claimed file(s) show no change "
            f"during this handoff")
    if out_of_scope:
        problems.append(
            f"{len(out_of_scope)} claimed file(s) lie outside the handoff's "
            f"scope fence — either a scope breach, or the report is taking "
            f"credit for changes it did not make")
    if undeclared:
        problems.append(
            f"{len(undeclared)} file(s) outside the scope fence were changed "
            f"during this handoff without being reported")

    if not problems:
        print(f"  Evidence gate: {kind} {args.handoff_id} OK "
              f"({checked} file claim(s) verified against the working tree)")
        return 0

    print(f"  EVIDENCE GATE FAILED — {kind} {args.handoff_id} "
          f"from {args.from_role}")
    for problem in problems:
        print(f"    - {problem}")
    for claim, full, mtime in unchanged:
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
        print(f"      claimed changed: {claim}")
        print(f"        {full} last modified {stamp} — before this handoff")
    for claim, full in out_of_scope:
        print(f"      outside scope fence: {claim} -> {full}")
    for full in undeclared:
        print(f"      changed but not reported, and not in scope: {full}")
        twin = same_name_in_scope(full, allowed)
        if twin:
            print(f"        the scope allows {twin} — wrong repository?")

    note = Path(path).with_name(f"{args.handoff_id}-gate-rejection.md")
    lines = [
        f"# Evidence gate rejection — {kind} {args.handoff_id}",
        "",
        f"Deliverable: `{path}`",
        f"From role: `{args.from_role}` → `{args.to_role}`",
        "",
        "## Why this was blocked",
        "",
    ]
    lines += [f"- {p}" for p in problems]
    if unchanged:
        lines += ["", "## Claimed changes not present in the working tree", ""]
        for claim, full, mtime in unchanged:
            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
            lines.append(f"- `{claim}` → `{full}` last modified {stamp}")
    if undeclared:
        lines += ["", "## Changed during this handoff, outside the scope fence", ""]
        wrong_repo = False
        for full in undeclared:
            lines.append(f"- `{full}`")
            twin = same_name_in_scope(full, allowed)
            if twin:
                wrong_repo = True
                lines.append(f"  - the scope allows `{twin}` — same filename, "
                             f"different repository")
        lines += ["",
                  "These were modified after the handoff was written but the",
                  "fence does not allow them and the report does not mention",
                  "them. Either revert them, or say what you changed and why",
                  "— an edit nobody declared is the one nobody can review."]
        if wrong_repo:
            lines += ["",
                      "**A same-named file in another repository is almost",
                      "always a wrong-repository edit.** Your working directory",
                      "is not the only repository this handoff spans. Use the",
                      "absolute path from the scope fence for every edit, and",
                      "revert the one you made in the wrong place."]
    if out_of_scope:
        lines += ["", "## Claimed changes outside the handoff's scope fence", ""]
        for claim, full in out_of_scope:
            lines.append(f"- `{claim}` → `{full}`")
        lines += ["",
                  "Only the files the handoff's `<scope>` block permits may",
                  "be reported as changed. Pasted command output belongs in a",
                  "fenced code block, where it reads as evidence rather than",
                  "as a claim."]
    if kind == "verdict":
        lines += [
            "",
            "## What to do",
            "",
            "Review the working tree, not the result file. Run the checks",
            "yourself and paste their real output into an Evidence section:",
            "",
            "```bash",
            "cd <target project>",
            "git status --short",
            "git diff --stat",
            "# then one command per claim you are accepting",
            "```",
            "",
            "Then state APPROVED or REJECTED and mark each claim VERIFIED,",
            "FALSE or UNVERIFIED. A claim you could not check is REJECTED —",
            "absence of evidence is never approval.",
            "",
        ]
    else:
        lines += [
            "",
            "## What to do",
            "",
            "Either make the changes and rewrite the deliverable to match the",
            "working tree, or rewrite it to state honestly what was done and",
            "why the rest was not. Declining a change with a reason is a",
            "legitimate result; claiming a change that did not happen is not.",
            "",
        ]
    try:
        note.write_text("\n".join(lines), encoding="utf-8")
        print(f"    Rejection written to {note}")
    except OSError as exc:
        print(f"    WARNING: could not write rejection note: {exc}")

    if args.mode == "warn":
        print("    Mode is 'warn' — chain continues.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
