"""§40 integration test for the Deterministic Patcher.

Models the spec §40 flow shape on tmp_path fixtures (spec phases 1E-1F):
an implementer-authored PatchRequest routes through the Deterministic
Patcher, mutates a temp-repo, and produces a non-empty resulting diff
that the review side can consume verbatim. The same scenario under the
default `direct` mode verifies the flow shape is unchanged.

The file is deliberately self-contained:

  * its own scratch-gitrepo fixture (same idiom the existing patcher
    tests use — `tests/test_patcher_git_engine.py:git_repo` and the
    LibCST counterpart — but duplicated here so the two frozen test
    files are not imported);
  * its own scratch-SQLite fixture built from the same base-schema
    skeleton used by the frozen B1/B2 test files, also duplicated here
    for the same reason.

The Father repository is never used as a mutation target and is never
opened for read by these tests; the suite works entirely against
tmp_path.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

from patch_mode import (  # noqa: E402
    PATCH_MODE_BLOCK,
    apply_mode_block,
    resolve_implementation_mode,
)
from patcher import DeterministicPatcher, PatchRequest  # noqa: E402
from patcher.errors import PATCH_APPLIED, PATCH_PATH_REJECTED  # noqa: E402
from patcher.models import request_from_dict  # noqa: E402


_MIGRATION_PATH = (
    PROJECT_ROOT / "scripts" / "db" / "052_implementation_mode.sql"
)

_ODD_PROMPT = (
    "Read and execute /tmp/flows/preferred_cloud/handoffs/051-handoff.md \n"
    "\n"
    "  trailing whitespace line above  \t \n"
    "\n"
    "## Final line with CRLF-style content."
)


# ── Scratch git-repo fixture ────────────────────────────────────────────


@pytest.fixture()
def git_repo(tmp_path: Path) -> str:
    """Return the path to a tiny seeded scratch git repo.

    One Python file committed under `lib.py`, no imports. This is the
    fixture the §40 integration test mutates with an `add_import`
    structural operation.
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, check=check,
        )

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (repo / "lib.py").write_text(
        "def hello() -> str:\n"
        "    return \"world\"\n",
        encoding="utf-8",
    )
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    return str(repo)


def _write_seed_repo(parent: Path, name: str) -> str:
    """Initialise `parent / name` as a git repo with the standard seed.

    Returns the repo path as a string for the request's repo_path field.
    """
    repo = parent / name
    repo.mkdir()

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, check=True,
        )

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (repo / "lib.py").write_text(
        "def hello() -> str:\n"
        "    return \"world\"\n",
        encoding="utf-8",
    )
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    return str(repo)


# ── Scratch SQLite fixture (mirrors the B1/B2 file skeleton) ───────────


_BASE_SCHEMA = """
CREATE TABLE bridge_flows (
    flow_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    step_order TEXT,
    is_default INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    auto_complete_enabled INTEGER DEFAULT 0,
    use_machine_profile INTEGER DEFAULT 0,
    target_project_path TEXT DEFAULT NULL
);
CREATE TABLE bridge_flow_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_key TEXT NOT NULL,
    step_key TEXT NOT NULL,
    from_role TEXT NOT NULL,
    to_role TEXT NOT NULL,
    deliverable_dir TEXT,
    deliverable_pattern TEXT,
    pre_dispatch_script TEXT,
    post_dispatch_script TEXT,
    error_msg TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    rule_key TEXT,
    auto_chain_to_next INTEGER DEFAULT 0,
    validation_required INTEGER DEFAULT 0,
    model_source TEXT,
    model_alias TEXT,
    UNIQUE(flow_key, step_key)
);
CREATE TABLE bridge_roles (
    role_key TEXT PRIMARY KEY,
    tmux_session TEXT NOT NULL,
    setup_script TEXT,
    teardown_script TEXT,
    deliver_error_msg TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    restart_policy TEXT DEFAULT 'none',
    governance_file TEXT,
    role_type TEXT DEFAULT 'agent',
    enter_command TEXT DEFAULT 'default',
    config_dir TEXT,
    primary_output_type TEXT,
    default_model_source TEXT,
    default_model_alias TEXT,
    trade_mcp_push_mode TEXT,
    max_output_tokens INTEGER,
    allocator_client TEXT DEFAULT 'opencode',
    fresh_session_command TEXT,
    workdir_mode TEXT NOT NULL DEFAULT 'target_project',
    execution_target TEXT
);
"""


def _build_scratch_db_with_migration(tmp_path: Path) -> Path:
    """Build a scratch DB with the base schema + migration 052 applied.

    Mirrors the structure used by the frozen B1/B2 test files. The
    resolved mode for any (flow, step, role) against this DB is the
    global default `direct` — no row at any level is opted in.
    """
    db = tmp_path / "scratch.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(_BASE_SCHEMA)
        conn.commit()
        sql = _MIGRATION_PATH.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()
    return db


# ── §40 deterministic_patch leg ─────────────────────────────────────────


class TestDeterministicPatchLeg:
    """Spec §40: PatchRequest → Patcher → repo mutation → exact diff.

    The implementer authors a structural Python request via the same
    payload the role would hand to the patcher (a plain JSON-decoded
    dict, not kwargs). The patcher applies it, the resulting diff is a
    non-empty unified diff naming the target file and the changed line
    — that diff is what the review side receives verbatim.
    """

    def test_patchrequest_from_dict_applies_and_emits_diff(self, git_repo):
        repo_path = git_repo

        # Build the request via JSON round-trip — exactly the shape an
        # implementer role hands the patcher across the CLI / tool-call
        # boundary. This exercises `request_from_dict` (the loader the
        # patcher actually trusts at the public boundary) rather than
        # only kwarg construction.
        payload = {
            "repo_path": repo_path,
            "patch_mode": "structural_python",
            "operations": [
                {
                    "operation": "add_import",
                    "file": "lib.py",
                    "module": "os",
                    "name": None,
                }
            ],
        }
        # Plain JSON-decoded dict, NOT kwargs.
        payload = json.loads(json.dumps(payload))

        request = request_from_dict(payload)
        assert isinstance(request, PatchRequest)
        assert request.repo_path == repo_path
        assert request.patch_mode == "structural_python"

        # Run through the public facade — not the engine directly.
        patcher = DeterministicPatcher()
        result = patcher.apply(request)

        # ── Outcome assertions ────────────────────────────────────────
        assert result.applied is True, (
            f"patcher.apply did not mutate the repo: status={result.status!r} "
            f"error_code={result.error_code!r} error={result.error!r}"
        )
        assert result.error_code == PATCH_APPLIED, (
            f"expected PATCH_APPLIED, got error_code={result.error_code!r}"
        )
        assert result.files_changed == ["lib.py"]
        assert result.operations_applied == 1

        # ── On-disk mutation ──────────────────────────────────────────
        on_disk = (Path(repo_path) / "lib.py").read_text(encoding="utf-8")
        assert "import os" in on_disk, (
            f"add_import did not add 'import os' to lib.py:\n{on_disk}"
        )

        # ── Resulting diff (the review side's input) ──────────────────
        diff = result.resulting_diff
        assert diff is not None and diff.strip() != "", (
            "resulting_diff is empty — the review side would see nothing"
        )
        # The LibCST engine captures the diff via `git diff -- <file>`
        # (per engines/libcst_engine.py:_capture_diff_for_file). That
        # form omits the `diff --git` and `index` lines that a full
        # `git diff` would emit, but retains the per-file `--- a/` /
        # `+++ b/` headers and the unified-diff hunk. The file name
        # and the changed line must both be present.
        assert "--- a/lib.py" in diff and "+++ b/lib.py" in diff, (
            f"resulting_diff does not name lib.py in its per-file "
            f"headers:\n{diff}"
        )
        assert "+import os" in diff, (
            f"resulting_diff does not contain '+import os':\n{diff}"
        )
        # And a hunk header that pins the change site.
        assert "@@ -1,2 +1,3 @@" in diff, (
            f"resulting_diff does not contain the expected hunk header "
            f"(@@ -1,2 +1,3 @@):\n{diff}"
        )

        # ── Audit metadata present (spec §30) ─────────────────────────
        assert result.audit is not None, (
            "audit metadata missing — required by spec §30 for every apply"
        )
        assert result.audit.get("final_status") == "applied"
        assert result.audit.get("final_error_code") == PATCH_APPLIED
        assert result.audit.get("resulting_diff_empty") is False

    def test_resulting_diff_describes_the_actual_change(self, git_repo):
        """The patcher's resulting_diff, treated as a unified diff with
        the same per-file headers the LibCST engine emits (`--- a/` /
        `+++ b/`, no `diff --git` and no `index` lines), must describe
        the exact on-disk mutation.

        We assert three properties the §40 review side actually depends
        on:

        - the diff names the target file in its headers;
        - the diff contains the additive line `+import os`;
        - the diff's `@@` hunk pinpoints the line range that changed
          (one line added before the existing function body).

        The patcher builds this diff via `difflib.unified_diff` from the
        in-memory source before/after the LibCST pass (see
        `patcher/engines/libcst_engine.py:_unified_diff`), so byte-
        equality with `git diff` is not the contract — semantic
        equivalence is.
        """
        repo_path = git_repo

        payload = {
            "repo_path": repo_path,
            "patch_mode": "structural_python",
            "operations": [
                {"operation": "add_import", "file": "lib.py",
                 "module": "os", "name": None},
            ],
        }
        request = request_from_dict(json.loads(json.dumps(payload)))
        result = DeterministicPatcher().apply(request)

        assert result.applied is True
        assert result.error_code == PATCH_APPLIED
        diff = result.resulting_diff
        assert diff is not None and diff.strip() != ""

        # 1) The headers name lib.py on both sides.
        assert "--- a/lib.py" in diff
        assert "+++ b/lib.py" in diff
        # 2) The added line is present with its `+` prefix.
        assert "+import os" in diff
        # 3) The hunk pinpoints the change site: one line added before
        #    the existing function body (line 1 of old, line 1 of new),
        #    growing by exactly one line.
        assert "@@ -1 +1,2 @@" in diff or "@@ -1,2 +1,3 @@" in diff, (
            f"resulting_diff hunk header does not pinpoint the change "
            f"site:\n{diff}"
        )
        # 4) The diff is structurally honest: only one added content
        #    line, no spurious additions elsewhere. `difflib.unified_diff`
        #    prefixes ADDED lines with a single `+` (deletions with `-`,
        #    context with a space); the file headers `--- a/` and
        #    `+++ b/` also start with `+`/`-` but use three of them.
        #    Filter to lines whose first char is exactly one `+` /
        #    `-` followed by a content character.
        added = [
            ln for ln in diff.splitlines()
            if ln.startswith("+") and not ln.startswith("+++")
        ]
        assert added == ["+import os"], (
            f"resulting_diff introduces lines other than 'import os': "
            f"{added!r}"
        )

    def test_import_already_present_is_idempotent_no_change(self, git_repo):
        """Spec §28: structural operations should be idempotent.
        Running `add_import pathlib` twice must leave exactly ONE
        `import pathlib` line on disk — and the second run's result
        must honestly report `no_change` (status) with no actual
        diff produced. This pins the §40 review shape: idempotent
        runs do not accumulate drift, and the resulting_diff is
        honest about it.
        """
        repo_path = git_repo

        payload = {
            "repo_path": repo_path,
            "patch_mode": "structural_python",
            "operations": [
                {"operation": "add_import", "file": "lib.py",
                 "module": "pathlib", "name": None},
            ],
        }
        first = DeterministicPatcher().apply(
            request_from_dict(json.loads(json.dumps(payload)))
        )
        assert first.applied is True
        assert first.error_code == PATCH_APPLIED

        second = DeterministicPatcher().apply(
            request_from_dict(json.loads(json.dumps(payload)))
        )
        # Second call must not introduce a second `import pathlib`.
        on_disk = (Path(repo_path) / "lib.py").read_text(encoding="utf-8")
        assert on_disk.count("import pathlib") == 1, (
            "add_import was not idempotent — duplicated the import.\n"
            f"on-disk content:\n{on_disk}"
        )
        # Second call is honest about producing no diff: status is
        # `no_change`, operations_applied is 0, the audit reports
        # resulting_diff_empty=True. The patcher MUST NOT pretend a
        # second additive operation happened.
        assert second.status == "no_change", (
            f"second apply should report status='no_change' for an "
            f"already-present import, got {second.status!r}"
        )
        assert second.operations_applied == 0
        assert second.audit is not None
        assert second.audit.get("resulting_diff_empty") is True


# ── §40 direct leg, same scenario ───────────────────────────────────────


class TestDirectLegSameScenario:
    """Spec §40 second clause + governance guarantee: under the default
    `direct` mode the flow shape is provably unchanged.

    - `test_direct_edit_end_state_matches_patcher_end_state` proves
      that a direct editor and a patcher pass under the SAME request
      produce the same on-disk state on two parallel fixtures.
    - `test_default_mode_resolves_to_direct_and_prompt_is_unchanged`
      proves the dispatch-side property: against a scratch DB with
      migration 052 and nothing opted in, the resolver returns
      'direct' and apply_mode_block returns the prompt byte-identical.
    - `test_deterministic_patch_emits_block_direct_does_not` covers
      the mirror on each side of the opt-in switch.
    """

    def test_direct_edit_end_state_matches_patcher_end_state(self, tmp_path):
        # TWO identical fresh repos so neither leg inherits state from
        # the other. Both start with the same seed.
        repo_patched = _write_seed_repo(tmp_path, "patched")
        repo_direct = _write_seed_repo(tmp_path, "direct")

        # ── Deterministic_patch leg on `repo_patched` ────────────────
        patched = DeterministicPatcher().apply(
            request_from_dict(json.loads(json.dumps({
                "repo_path": repo_patched,
                "patch_mode": "structural_python",
                "operations": [
                    {"operation": "add_import", "file": "lib.py",
                     "module": "os", "name": None},
                ],
            })))
        )
        assert patched.applied is True
        assert patched.error_code == PATCH_APPLIED

        # ── Direct leg on `repo_direct` (what a direct-mode ──────────
        # implementer does today: edit the file in place).
        direct_path = Path(repo_direct) / "lib.py"
        original = direct_path.read_text(encoding="utf-8")
        # Insert "import os\n" at the top, preserve the original body.
        direct_path.write_text("import os\n" + original, encoding="utf-8")

        # Both legs end at byte-identical file content. This is what
        # "the flow shape is unchanged" means in this handoff.
        patched_content = (Path(repo_patched) / "lib.py").read_text(
            encoding="utf-8"
        )
        direct_content = direct_path.read_text(encoding="utf-8")
        assert patched_content == direct_content, (
            "deterministic_patch leg and direct leg ended at different "
            "file states — the §40 direct-leg claim is broken.\n"
            f"patched:\n{patched_content!r}\n"
            f"direct:\n{direct_content!r}"
        )

    def test_default_mode_resolves_to_direct_and_prompt_is_unchanged(
        self, tmp_path
    ):
        """On a scratch DB with migration 052 applied and NOTHING opted
        in, the resolver returns 'direct' and apply_mode_block returns
        the prompt byte-identical (same string object). This is the
        governance check that backs the direct leg: under the shipped
        default, the bridge injects nothing and the flow shape is
        exactly what it was before the patcher landed.
        """
        db = _build_scratch_db_with_migration(tmp_path)

        # Resolver walks all three levels and finds nothing — global
        # default is 'direct'.
        assert resolve_implementation_mode(
            db, "preferred_cloud",
            step_key="step_a", role_key="Pre-imple-cl",
        ) == "direct"
        # And without step/role — the walk shape the dispatch callback
        # path uses (the same call shape B2 fixed).
        assert resolve_implementation_mode(
            db, "preferred_cloud",
        ) == "direct"

        # apply_mode_block is byte-identical: SAME STRING OBJECT, no
        # normalization, no trailing newline added.
        result = apply_mode_block(
            _ODD_PROMPT, db, "preferred_cloud",
            step_key="step_a", role_key="Pre-imple-cl",
        )
        assert result is _ODD_PROMPT, (
            "apply_mode_block returned a different string object under "
            "the default 'direct' mode — this is the byte-identical "
            "passthrough spec §5 mandates, and it must remain true."
        )
        assert result == _ODD_PROMPT

    def test_direct_mode_does_not_emit_patch_mode_block(self, tmp_path):
        """A prompt that flowed through apply_mode_block under the
        default mode must not contain the §26 block. phrased in the
        dispatch language: under implementation_mode = 'direct',
        dispatched prompts are unchanged.
        """
        db = _build_scratch_db_with_migration(tmp_path)
        out = apply_mode_block(
            _ODD_PROMPT, db, "preferred_cloud",
            step_key="step_a", role_key="Pre-imple-cl",
        )
        assert PATCH_MODE_BLOCK not in out, (
            "PATCH_MODE_BLOCK leaked into a prompt whose resolved mode "
            "is 'direct' — the §26 block must only appear when the "
            "mode is 'deterministic_patch'."
        )

    def test_deterministic_patch_mode_emits_block(self, tmp_path):
        """The mirror: when migration 052 is applied and a flow-level
        row opts in, apply_mode_block must append the §26 block and
        the original prompt must remain the prefix. The block must
        also cite the governance file this handoff delivers.
        """
        db = _build_scratch_db_with_migration(tmp_path)
        conn = sqlite3.connect(str(db))
        try:
            conn.execute(
                "INSERT INTO bridge_flows "
                "(flow_key, name, implementation_mode) "
                "VALUES (?, ?, ?)",
                ("preferred_cloud", "Preferred Cloud",
                 "deterministic_patch"),
            )
            conn.commit()
        finally:
            conn.close()

        out = apply_mode_block(
            _ODD_PROMPT, db, "preferred_cloud",
            step_key="step_a", role_key="Pre-imple-cl",
        )
        assert out.startswith(_ODD_PROMPT), (
            "the §26 block must be appended, not inserted — the "
            "original prompt must remain the prefix of the result."
        )
        assert PATCH_MODE_BLOCK in out
        assert out.endswith(PATCH_MODE_BLOCK)
        # Block references the governance file this handoff delivers.
        assert (
            "docs/governance-templates-v2/102_DETERMINISTIC_PATCH_MODE.md"
            in out
        ), (
            "§26 block must reference the 102 governance file by path"
        )


# ── O6 polish: PATCH_PATH_REJECTED carries files_rejected ──────────────


class TestPathRejectionFilesRejected:
    """Run 017's live acceptance noted that PATCH_PATH_REJECTED results
    carry `files_rejected=[]` while the error message names the
    rejected path. The O6 polish adds the offending repo-relative path
    to `PatchResult.files_rejected` so the review side can SEE which
    file was rejected, not only read about it in the error string.

    The fix is bounded to `patcher/policy.py` (carry `offending_path`
    on the exception), `patcher/engines/_rejected` builders (accept
    `files_rejected`), and the engine catch sites for
    `PatchPathRejected`. This test exercises the path-traversal case
    end-to-end against a scratch repo.
    """

    def test_path_traversal_rejection_populates_files_rejected(
        self, git_repo
    ):
        repo_path = git_repo

        # Build a diff that names `../escape.py` — `git apply` would
        # reject the path, but the validator must catch it FIRST so we
        # get PATCH_PATH_REJECTED, not PATCH_CONFLICT.
        evil_diff = (
            "diff --git a/../escape.py b/../escape.py\n"
            "@@ -0,0 +1 @@\n"
            "+evil\n"
        )
        request = request_from_dict(json.loads(json.dumps({
            "repo_path": repo_path,
            "patch_mode": "unified_diff",
            "patch": evil_diff,
        })))
        result = DeterministicPatcher().apply(request)

        # Outcome: rejected, path-rejected, no mutation.
        assert result.applied is False
        assert result.error_code == PATCH_PATH_REJECTED
        # The polish: `files_rejected` lists the offending repo-relative
        # candidate the validator surfaced. The exact spelling matches
        # what `git diff a/../escape.py` would report as the path the
        # diff tried to mutate — the reviewer has a single, exact
        # answer to the question "which file was rejected?".
        assert result.files_rejected == ["../escape.py"], (
            f"expected files_rejected=['../escape.py'], got "
            f"{result.files_rejected!r}"
        )
        # And the same path is named in the error message string,
        # so the polish is additive, not a replacement.
        assert "../escape.py" in (result.error or "")

    def test_allowed_paths_violation_populates_files_rejected(
        self, git_repo
    ):
        """The patcher also rejects targets outside `allowed_paths`.
        The polish should propagate that path the same way."""
        repo_path = git_repo

        evil_diff = (
            "diff --git a/forbidden.py b/forbidden.py\n"
            "@@ -0,0 +1 @@\n"
            "+x\n"
        )
        request = request_from_dict(json.loads(json.dumps({
            "repo_path": repo_path,
            "patch_mode": "unified_diff",
            "patch": evil_diff,
            "allowed_paths": ["lib.py"],
        })))
        result = DeterministicPatcher().apply(request)

        assert result.applied is False
        assert result.error_code == PATCH_PATH_REJECTED
        assert result.files_rejected == ["forbidden.py"], (
            f"expected files_rejected=['forbidden.py'], got "
            f"{result.files_rejected!r}"
        )

    def test_repository_root_rejection_does_not_claim_a_file(
        self, tmp_path
    ):
        """When the FAILURE is that `repo_path` itself doesn't exist or
        isn't a directory, NO repo-relative file is meaningful — the
        polish must not invent one. `files_rejected` stays empty in
        that case so the review side doesn't read a hallucinated path
        as a real file.
        """
        # `repo_path` points at a path that does not exist.
        request = request_from_dict(json.loads(json.dumps({
            "repo_path": str(tmp_path / "no_such_repo"),
            "patch_mode": "structural_python",
            "operations": [
                {"operation": "add_import", "file": "lib.py",
                 "module": "os", "name": None},
            ],
        })))
        result = DeterministicPatcher().apply(request)

        assert result.applied is False
        assert result.error_code == PATCH_PATH_REJECTED
        # Repository-root validation has no repo-relative path to
        # surface — `files_rejected` MUST be empty so the reviewer
        # doesn't read a synthesized path as evidence of a real file.
        assert result.files_rejected == [], (
            f"expected files_rejected=[] for a repository-root "
            f"validation failure, got {result.files_rejected!r}"
        )
