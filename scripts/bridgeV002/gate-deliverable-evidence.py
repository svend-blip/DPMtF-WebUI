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
   having been changed during this handoff — present in `git status --short`,
   or modified after the handoff file was written. A file that exists and is
   untouched is the exact signature of a fabricated report.
2. A verdict must carry real evidence: an Evidence section, or command
   output. A verdict that only asserts is not a verdict.

Exit 0 = pass, exit 1 = blocked. In `--mode warn` it reports and exits 0,
for rolling the gate out on a flow before trusting it to stop the chain.
"""

import argparse
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
    checked against whichever repo actually contains the file.
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
    # Sibling projects referenced by name in handoffs (model-allocator etc.)
    try:
        import config as _cfg
        base = _cfg.get_projects_base_dir()
        for entry in sorted(os.listdir(base)):
            full = os.path.join(base, entry)
            if os.path.isdir(os.path.join(full, ".git")) and full not in roots:
                roots.append(full)
    except Exception:
        pass
    return roots


def git_dirty_files(repo_root):
    """Paths git reports as changed, relative to the repo root."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_root, "status", "--short"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return set()
    except Exception:
        return set()
    dirty = set()
    for line in result.stdout.splitlines():
        if len(line) > 3:
            path = line[3:].strip().strip('"')
            if " -> " in path:            # renames
                path = path.split(" -> ", 1)[1]
            dirty.add(path)
    return dirty


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
            in_change_section = bool(CHANGE_HEADING.match(line))
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
        if in_change_section and not is_continuation:
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


def locate(path_claim, roots, prefer=None):
    """Resolve a claimed path to (repo_root, relative_path) if it exists.

    `prefer` is the set of absolute paths the handoff's scope fence allows.
    It only breaks ties for ambiguous relative names; it never invents a
    match that does not exist on disk.

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

    # 2. Path as given, relative to each repo. When the name is ambiguous —
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
    for root in roots:
        full = os.path.join(root, path_claim)
        if os.path.exists(full):
            return root, path_claim

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

    match = re.search(r"<scope>(.*?)</scope>", text, re.S | re.I)
    block = match.group(1) if match else None
    if block is None:
        match = re.search(r"^#{1,6}\s*scope\s+fence\s*$(.*?)(?=^#{1,6}\s|\Z)",
                          text, re.S | re.I | re.M)
        block = match.group(1) if match else None
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
        for token in PATH_TOKEN.findall(cleaned):
            token = token.strip("._-")
            if Path(token).suffix.lower() not in CODE_SUFFIXES:
                continue
            root, rel = locate(token, roots)
            if root:
                allowed.add(os.path.join(root, rel))

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


def handoff_mtime(bridge_dir, flow_key, handoff_id):
    """When this handoff was written — the clock a change must postdate."""
    if bridge_dir and flow_key and handoff_id:
        path = Path(bridge_dir) / flow_key / "handoffs" / f"{handoff_id}-handoff.md"
        try:
            return path.stat().st_mtime
        except OSError:
            pass
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

    roots = target_projects(args.flow_key)
    dirty_by_root = {root: git_dirty_files(root) for root in roots}
    since = handoff_mtime(bridge_dir, args.flow_key, args.handoff_id)

    handoff_path = os.path.join(
        bridge_dir, args.flow_key, "handoffs", f"{args.handoff_id}-handoff.md")
    allowed = scope_allowed(handoff_path, roots)

    unchanged = []
    out_of_scope = []
    checked = 0
    for claim in claimed_paths(text):
        root, rel = locate(claim, roots, prefer=allowed)
        if root is None:
            continue          # not a real path in any repo — not a file claim
        checked += 1
        full = os.path.join(root, rel)

        if allowed is not None and full not in allowed:
            out_of_scope.append((claim, full))

        if rel in dirty_by_root.get(root, set()):
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
    undeclared = undeclared_changes(roots, dirty_by_root, allowed, since)

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
