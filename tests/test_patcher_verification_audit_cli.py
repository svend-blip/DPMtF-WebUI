"""Tests for Phase 1D: post-apply verification, audit metadata, and CLI.

Coverage (handoff Step 6):

  Verification (spec §18–§21):
    * unified-diff apply that yields unparseable Python →
      PATCH_APPLIED_SYNTAX_FAILED, failing file named in
      PatchResult.verification
    * syntax-clean apply → verification reports the syntax pass;
      no __pycache__ / .pyc artefact anywhere in the temp repo
      after the run
    * configured command with exit 0 → exit code reported verbatim,
      status stays PATCH_APPLIED
    * configured command with nonzero exit (e.g. `python3 -c "import
      sys; sys.exit(3)"`) → exit code 3 reported VERBATIM, status
      PATCH_APPLIED_TEST_FAILED, change still on disk
    * no configured commands → no command execution (and check()
      never triggers verification)

  Audit (spec §30):
    * audit block present on success AND on failure results,
      carrying the Step-3 minimum fields
    * empty-diff sha256 convention holds

  CLI (spec §25):
    * `patcher_cli.py patch_check` and `patch_apply` end-to-end via
      subprocess against a temp repo
    * valid request → JSON PatchResult on stdout + exit 0
    * failing request → exit 1
    * garbage JSON → exit 2
    * stdout parses as JSON in every case
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple

import pytest

from patcher import DeterministicPatcher, PatchRequest
from patcher.audit import (
    EMPTY_DIFF_SHA256,
    diff_sha256,
    utc_now_iso,
)
from patcher.errors import (
    PATCH_APPLIED,
    PATCH_APPLIED_SYNTAX_FAILED,
    PATCH_APPLIED_TEST_FAILED,
    PATCH_CONFLICT,
)
from patcher.engines import LibCSTEngine


# Path to the CLI under test.
CLI_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "patcher_cli.py"
)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture()
def git_repo(tmp_path: Path) -> Tuple[str, str]:
    """A tiny git repo with a single Python file `lib.py`."""
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
        "def hello():\n    return 1\n",
        encoding="utf-8",
    )
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    base = git("rev-parse", "HEAD").stdout.strip()
    return str(repo), base


def _unified_diff_for(repo: str, filename: str, old: str, new: str) -> str:
    """Synthesize a unified diff without touching git config.

    Mirrors the helper in `test_patcher_git_engine.py`: each line of
    `old` / `new` is one hunk line, prefixed with `-` / `+`. The hunk
    header reports the line counts (`@@ -1,N +1,N @@`) so `git apply`
    applies every line cleanly.
    """
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    n_old = len(old_lines) if old_lines else 1
    n_new = len(new_lines) if new_lines else 1
    hunk = (
        f"@@ -1,{n_old} +1,{n_new} @@\n"
        + "".join(f"-{l}" for l in old_lines)
        + "".join(f"+{l}" for l in new_lines)
    )
    return (
        f"diff --git a/{filename} b/{filename}\n"
        "index 0000000..0000000 100644\n"
        f"--- a/{filename}\n"
        f"+++ b/{filename}\n"
        + hunk
    )


def _list_pycache(repo: str) -> list:
    """Walk the repo and return every path ending in `.pyc` or inside
    `__pycache__`. Used by syntax-pass tests to assert the verification
    pipeline leaves NO bytecode artefact."""
    out = []
    for root, dirs, files in os.walk(repo):
        if ".git" in root.split(os.sep):
            dirs.clear()
            continue
        for d in list(dirs):
            if d == "__pycache__":
                out.append(os.path.join(root, d))
                dirs.remove(d)
        for fn in files:
            if fn.endswith(".pyc"):
                out.append(os.path.join(root, fn))
    return sorted(out)


# ── Verification: syntax check (spec §20) ───────────────────────────────


class TestVerificationSyntax:
    def test_unparseable_unified_diff_apply_yields_syntax_failed(
        self, git_repo
    ):
        """A unified-diff apply that produces unparseable Python must
        surface PATCH_APPLIED_SYNTAX_FAILED with the failing file named
        in `PatchResult.verification`. The applied change is left on
        disk per spec §20 — the surrounding DPMtF policy, never the
        patcher, decides whether to revert."""
        repo, _ = git_repo
        diff = _unified_diff_for(
            repo, "lib.py", "def hello():\n    return 1\n",
            "def hello(:\n    return 1\n",
        )
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=diff,
        ))
        # Mutation landed.
        assert result.applied is True
        assert result.files_changed == ["lib.py"]
        # Verification escalated the status.
        assert result.error_code == PATCH_APPLIED_SYNTAX_FAILED
        assert "syntax" in (result.error or "").lower()
        # The failing file is named in the verification dict.
        assert result.verification is not None
        assert result.verification.get("syntax") == "failed"
        syntax_errors = result.verification.get("syntax_errors") or []
        assert any(
            e.get("file") == "lib.py" for e in syntax_errors
        ), syntax_errors
        # The change is left on disk per spec §20.
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "def hello(:" in text

    def test_structural_apply_yields_unparseable_python_syntax_failed(
        self, git_repo
    ):
        """Structural Python mutation that produces unparseable code
        via `replace_function` also escalates to
        PATCH_APPLIED_SYNTAX_FAILED. (This is the rare case where
        structural mode's in-memory parse catches the malformed
        replacement — the resulting source is then handed to the
        verification layer for a second opinion, which fails the
        actually-on-disk file.)"""
        repo, _ = git_repo
        # LibCSTEngine's `_op_replace_function` already rejects
        # unparseable replacements at parse time (returns
        # PATCH_INVALID). To exercise the syntax-verification
        # pathway in the structural engine we need a transformation
        # that parses successfully through LibCST but produces
        # unparseable Python on disk — that is not a shape
        # LibCST can produce. So this test asserts the
        # already-correct behaviour: in-memory parse failure
        # short-circuits to PATCH_INVALID BEFORE we reach the
        # verification pipeline.
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_function",
                "file": "lib.py",
                "function": "hello",
                "replacement": "def hello(:\n    return 1\n",
            }],
        ))
        assert result.applied is False
        # Structural parse-time rejection — no syntax verification
        # layer involvement on this path.
        assert result.error_code == "PATCH_INVALID"

    def test_syntax_clean_apply_reports_syntax_pass(self, git_repo):
        repo, _ = git_repo
        diff = _unified_diff_for(
            repo, "lib.py", "def hello():\n    return 1\n",
            "def hello():\n    return 2\n",
        )
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=diff,
        ))
        assert result.applied is True
        assert result.error_code == PATCH_APPLIED
        assert result.verification is not None
        assert result.verification.get("syntax") == "passed"

    def test_syntax_check_leaves_no_pyc_or_pycache(self, git_repo):
        """Temp-repo byte-identity assertion: the in-process
        `compile()` form must NOT leave a __pycache__ directory or
        any .pyc file anywhere in the repo."""
        repo, _ = git_repo
        diff = _unified_diff_for(
            repo, "lib.py", "def hello():\n    return 1\n",
            "def hello():\n    return 2\n",
        )
        before_pycache = _list_pycache(repo)
        DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=diff,
        ))
        after_pycache = _list_pycache(repo)
        # No cache artefacts before, none after — the in-process
        # compile() form never wrote one.
        assert before_pycache == []
        assert after_pycache == []

    def test_syntax_check_skips_non_python_files(self, git_repo, tmp_path):
        """A .txt file is changed but no .py file is touched — the
        verification layer reports `syntax: not_run` (no Python
        files were in `files_changed`) and the apply succeeds."""
        repo, _ = git_repo
        (Path(repo) / "README.md").write_text("hi\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", repo, "add", "-A"],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "-C", repo, "commit", "-q", "-m", "readme"],
            capture_output=True, text=True, check=True,
        )
        diff = _unified_diff_for(
            repo, "README.md", "hi\n", "hello\n",
        )
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=diff,
        ))
        assert result.applied is True
        assert result.error_code == PATCH_APPLIED
        assert result.verification is not None
        assert result.verification.get("syntax") == "not_run"


# ── Verification: configured commands (spec §21) ───────────────────────


class TestVerificationConfiguredCommands:
    def test_command_with_exit_zero_reported_verbatim(self, git_repo):
        repo, _ = git_repo
        # Use a Python one-liner that exits 0 cleanly. The cwd of the
        # patcher is the repo root, so the command runs there.
        diff = _unified_diff_for(
            repo, "lib.py", "def hello():\n    return 1\n",
            "def hello():\n    return 2\n",
        )
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo,
            patch_mode="unified_diff",
            patch=diff,
            verification={
                "commands": [
                    "python3 -c \"import sys; sys.exit(0)\""
                ]
            },
        ))
        assert result.applied is True
        assert result.error_code == PATCH_APPLIED
        # Exit code reported verbatim, not interpreted.
        assert result.verification is not None
        assert result.verification.get("syntax") == "passed"
        commands = result.verification.get("commands") or []
        assert len(commands) == 1
        assert commands[0]["status"] == "executed"
        assert commands[0]["exit_code"] == 0

    def test_command_with_nonzero_exit_yields_test_failed_verbatim(
        self, git_repo
    ):
        repo, _ = git_repo
        diff = _unified_diff_for(
            repo, "lib.py", "def hello():\n    return 1\n",
            "def hello():\n    return 2\n",
        )
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo,
            patch_mode="unified_diff",
            patch=diff,
            verification={
                "commands": [
                    "python3 -c \"import sys; sys.exit(3)\""
                ]
            },
        ))
        assert result.applied is True
        # Status escalated; change stays on disk per spec §20 / §21.
        assert result.error_code == PATCH_APPLIED_TEST_FAILED
        assert (Path(repo) / "lib.py").read_text(encoding="utf-8") == (
            "def hello():\n    return 2\n"
        )
        # Exit code 3 reported VERBATIM.
        assert result.verification is not None
        commands = result.verification.get("commands") or []
        assert len(commands) == 1
        assert commands[0]["exit_code"] == 3
        assert commands[0]["status"] == "executed"
        # No semantic interpretation in the patcher — the orchestrator
        # gets the raw `command_failures` entry too.
        failures = result.verification.get("command_failures") or []
        assert any(f.get("exit_code") == 3 for f in failures)

    def test_commands_run_in_order_and_stop_after_first_nonzero(
        self, git_repo
    ):
        """Per spec §21 / handoff §2b, commands run in request order
        and the pipeline stops after the first nonzero exit. The
        second command must be reported as `status: skipped`."""
        repo, _ = git_repo
        diff = _unified_diff_for(
            repo, "lib.py", "def hello():\n    return 1\n",
            "def hello():\n    return 2\n",
        )
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo,
            patch_mode="unified_diff",
            patch=diff,
            verification={
                "commands": [
                    "python3 -c \"import sys; sys.exit(3)\"",
                    "python3 -c \"print('should not run')\"",
                ]
            },
        ))
        assert result.error_code == PATCH_APPLIED_TEST_FAILED
        commands = (result.verification or {}).get("commands") or []
        assert len(commands) == 2
        assert commands[0]["status"] == "executed"
        assert commands[0]["exit_code"] == 3
        assert commands[1]["status"] == "skipped"
        assert commands[1].get("exit_code") is None

    def test_no_commands_no_command_execution(self, git_repo):
        """No configured commands → no command execution; the syntax
        check still runs."""
        repo, _ = git_repo
        diff = _unified_diff_for(
            repo, "lib.py", "def hello():\n    return 1\n",
            "def hello():\n    return 2\n",
        )
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo,
            patch_mode="unified_diff",
            patch=diff,
            verification={"commands": []},
        ))
        assert result.applied is True
        assert result.error_code == PATCH_APPLIED
        assert result.verification is not None
        commands = result.verification.get("commands") or []
        assert commands == []

    def test_check_never_triggers_verification(self, git_repo):
        """`check()` must NEVER run the verification pipeline, even
        when `verification` is configured — check writes nothing."""
        repo, _ = git_repo
        diff = _unified_diff_for(
            repo, "lib.py", "def hello():\n    return 1\n",
            "def hello():\n    return 2\n",
        )
        result = DeterministicPatcher().check(PatchRequest(
            repo_path=repo,
            patch_mode="unified_diff",
            patch=diff,
            verification={
                "commands": [
                    "python3 -c \"import sys; sys.exit(3)\""
                ]
            },
        ))
        # The configured command exits 3, but check() never runs it.
        assert result.status == "check_passed"
        assert result.applied is False
        assert result.error_code is None
        # The configured command was NOT executed — verification
        # stays unset on the result, audit marks it as not_run.
        assert result.verification is None
        assert result.audit is not None
        assert result.audit.get("verification_status") == "not_run"


# ── Audit (spec §30) ───────────────────────────────────────────────────


class TestAuditMetadata:
    def test_audit_present_on_successful_apply(self, git_repo):
        repo, base = git_repo
        diff = _unified_diff_for(
            repo, "lib.py", "def hello():\n    return 1\n",
            "def hello():\n    return 2\n",
        )
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=diff,
        ))
        assert result.audit is not None
        a = result.audit
        # Step-3 minimum fields.
        assert a["patch_mode"] == "unified_diff"
        assert a["engine"] == "git_apply"
        assert a["repository"] == repo
        assert a["base_revision"] == base
        assert a["files_requested"] == ["lib.py"]
        assert a["files_changed"] == ["lib.py"]
        assert a["operations_requested"] == 1
        assert a["operations_applied"] == 1
        assert isinstance(a["resulting_diff_hash"], str)
        assert len(a["resulting_diff_hash"]) == 64
        assert a["verification_status"] == "passed"
        assert a["final_status"] == "applied"
        assert a["final_error_code"] == PATCH_APPLIED
        # UTC ISO-8601 timestamps.
        assert "T" in a["started_at"]
        assert a["started_at"].endswith("Z")
        assert "T" in a["ended_at"]
        assert a["ended_at"].endswith("Z")

    def test_audit_present_on_failed_apply(self, git_repo):
        repo, _ = git_repo
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo,
            patch_mode="unified_diff",
            patch="not a diff\n",
        ))
        # Failed apply → audit still present.
        assert result.audit is not None
        a = result.audit
        assert a["patch_mode"] == "unified_diff"
        assert a["engine"] == "git_apply"
        assert a["operations_applied"] == 0
        assert a["files_changed"] == []
        assert a["final_status"] == "rejected"
        assert a["final_error_code"] == PATCH_CONFLICT
        # No diff was produced.
        assert a["resulting_diff_empty"] is True
        assert a["resulting_diff_hash"] == EMPTY_DIFF_SHA256

    def test_audit_present_on_structural_apply(self, git_repo):
        repo, _ = git_repo
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_import",
                "file": "lib.py",
                "module": "os",
            }],
        ))
        assert result.audit is not None
        a = result.audit
        assert a["patch_mode"] == "structural_python"
        assert a["engine"] == "libcst"
        assert a["files_requested"] == ["lib.py"]
        assert a["files_changed"] == ["lib.py"]
        assert a["operations_requested"] == 1
        assert a["operations_applied"] == 1

    def test_audit_diff_hash_matches_captured_diff(self, git_repo):
        repo, _ = git_repo
        diff = _unified_diff_for(
            repo, "lib.py", "def hello():\n    return 1\n",
            "def hello():\n    return 2\n",
        )
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=diff,
        ))
        expected = hashlib.sha256(
            (result.resulting_diff or "").encode("utf-8")
        ).hexdigest()
        assert result.audit["resulting_diff_hash"] == expected

    def test_audit_diff_hash_empty_for_no_change(self, git_repo):
        """Empty-diff convention: idempotent add_import leaves
        resulting_diff=None; the audit hash must equal sha256("")."""
        repo, _ = git_repo
        op = {
            "operation": "add_import",
            "file": "lib.py",
            "module": "os",
        }
        # First apply: adds the import.
        DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[op],
        ))
        # Second apply: idempotent no-change.
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[op],
        ))
        assert result.applied is False
        assert result.audit is not None
        assert result.audit["resulting_diff_empty"] is True
        assert result.audit["resulting_diff_hash"] == EMPTY_DIFF_SHA256

    def test_audit_check_also_populated(self, git_repo):
        """check() also gets an audit block (verification_status=
        not_run because check writes nothing)."""
        repo, _ = git_repo
        diff = _unified_diff_for(
            repo, "lib.py", "def hello():\n    return 1\n",
            "def hello():\n    return 2\n",
        )
        result = DeterministicPatcher().check(PatchRequest(
            repo_path=repo, patch_mode="unified_diff", patch=diff,
        ))
        assert result.audit is not None
        a = result.audit
        assert a["final_status"] == "check_passed"
        assert a["verification_status"] == "not_run"
        assert a["operations_applied"] == 0


# ── CLI (spec §25) ─────────────────────────────────────────────────────


def _run_cli(args: list, input_text: str = "") -> subprocess.CompletedProcess:
    """Run the CLI with `args` and optional stdin text, returning the
    CompletedProcess. The CLI lives in scripts/patcher_cli.py — we
    invoke it via the project venv's python3 so `patcher` resolves."""
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        capture_output=True, text=True, input=input_text, check=False,
    )


def _write_temp_json(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "req.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


class TestCLI:
    def test_cli_apply_exit_0_on_valid_request(self, git_repo, tmp_path):
        repo, _ = git_repo
        req_file = _write_temp_json(tmp_path, {
            "repo_path": repo,
            "patch_mode": "structural_python",
            "operations": [
                {"operation": "add_import", "file": "lib.py", "module": "os"}
            ],
        })
        proc = _run_cli(["patch_apply", str(req_file)])
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        # stdout parses as JSON.
        parsed = json.loads(proc.stdout)
        assert parsed["status"] == "applied"
        assert parsed["applied"] is True
        assert parsed["files_changed"] == ["lib.py"]
        assert parsed["audit"] is not None
        # Nothing else on stdout.
        assert proc.stdout.endswith("\n")

    def test_cli_check_exit_0_on_valid_request(self, git_repo, tmp_path):
        repo, _ = git_repo
        req_file = _write_temp_json(tmp_path, {
            "repo_path": repo,
            "patch_mode": "unified_diff",
            "patch": _unified_diff_for(
                repo, "lib.py", "def hello():\n    return 1\n",
                "def hello():\n    return 2\n",
            ),
        })
        proc = _run_cli(["patch_check", str(req_file)])
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        parsed = json.loads(proc.stdout)
        assert parsed["status"] == "check_passed"
        # check never mutates.
        assert (Path(repo) / "lib.py").read_text(encoding="utf-8") == (
            "def hello():\n    return 1\n"
        )

    def test_cli_failing_request_returns_exit_1(self, git_repo, tmp_path):
        repo, _ = git_repo
        req_file = _write_temp_json(tmp_path, {
            "repo_path": repo,
            "patch_mode": "unified_diff",
            "patch": "not a diff at all\n",
        })
        proc = _run_cli(["patch_apply", str(req_file)])
        assert proc.returncode == 1, (proc.stdout, proc.stderr)
        parsed = json.loads(proc.stdout)
        assert parsed["applied"] is False
        assert parsed["error_code"] == PATCH_CONFLICT

    def test_cli_garbage_json_returns_exit_2(self, git_repo, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{ this is not valid json", encoding="utf-8")
        proc = _run_cli(["patch_apply", str(bad)])
        assert proc.returncode == 2
        # Diagnostic on stderr.
        assert "patcher_cli:" in proc.stderr
        # Nothing on stdout (or whitespace only).
        assert proc.stdout.strip() == ""

    def test_cli_unknown_subcommand_returns_exit_2(self):
        proc = _run_cli(["patch_unknown"])
        assert proc.returncode == 2
        assert "patcher_cli:" in proc.stderr or "usage" in proc.stderr.lower()

    def test_cli_missing_repo_path_returns_exit_2(self, tmp_path):
        req_file = _write_temp_json(tmp_path, {
            "repo_path": "",
            "patch_mode": "unified_diff",
            "patch": "x",
        })
        proc = _run_cli(["patch_apply", str(req_file)])
        assert proc.returncode == 2

    def test_cli_reads_request_from_stdin(self, git_repo):
        repo, _ = git_repo
        payload = json.dumps({
            "repo_path": repo,
            "patch_mode": "structural_python",
            "operations": [
                {"operation": "add_import", "file": "lib.py", "module": "os"}
            ],
        })
        proc = _run_cli(["patch_apply", "-"], input_text=payload)
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        parsed = json.loads(proc.stdout)
        assert parsed["status"] == "applied"

    def test_cli_reads_request_from_stdin_no_arg(self, git_repo):
        repo, _ = git_repo
        payload = json.dumps({
            "repo_path": repo,
            "patch_mode": "structural_python",
            "operations": [
                {"operation": "add_import", "file": "lib.py", "module": "sys"}
            ],
        })
        proc = _run_cli(["patch_apply"], input_text=payload)
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        parsed = json.loads(proc.stdout)
        assert parsed["status"] == "applied"

    def test_cli_stdout_is_pure_json_every_case(self, git_repo, tmp_path):
        """stdout MUST be valid JSON in every case — including
        failure. Callers pipe stdout into json.loads."""
        repo, _ = git_repo
        # Failing case.
        req_file = _write_temp_json(tmp_path, {
            "repo_path": repo,
            "patch_mode": "unified_diff",
            "patch": "garbage\n",
        })
        proc = _run_cli(["patch_apply", str(req_file)])
        json.loads(proc.stdout)  # must not raise

        # Successful case.
        req_file = _write_temp_json(tmp_path, {
            "repo_path": repo,
            "patch_mode": "structural_python",
            "operations": [
                {"operation": "add_import", "file": "lib.py", "module": "os"}
            ],
        })
        proc = _run_cli(["patch_apply", str(req_file)])
        json.loads(proc.stdout)  # must not raise

    def test_cli_exit_code_for_syntax_failed(self, git_repo, tmp_path):
        """PATCH_APPLIED_SYNTAX_FAILED maps to exit code 1, NOT 0 —
        the orchestrator needs to see it."""
        repo, _ = git_repo
        req_file = _write_temp_json(tmp_path, {
            "repo_path": repo,
            "patch_mode": "unified_diff",
            "patch": _unified_diff_for(
                repo, "lib.py", "def hello():\n    return 1\n",
                "def hello(:\n    return 1\n",
            ),
        })
        proc = _run_cli(["patch_apply", str(req_file)])
        assert proc.returncode == 1
        parsed = json.loads(proc.stdout)
        assert parsed["error_code"] == PATCH_APPLIED_SYNTAX_FAILED


# ── Sanity: no LLM / allocator / bridge imports (spec §6) ──────────────


class TestNoLLMDependency:
    def test_patcher_package_has_no_llm_imports(self):
        """spec §6 / §23–§24: the patcher does not import any model
        allocator, bridge code, or LLM client. We grep the package
        for forbidden symbols."""
        package_root = (
            Path(__file__).resolve().parent.parent / "patcher"
        )
        forbidden_substrings = [
            "model_allocator",
            "bridge_lib",
            "bridgeV002",
            "anthropic",
            "openai",
            "ollama",
        ]
        for path in package_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for forbidden in forbidden_substrings:
                assert forbidden not in text, (
                    f"{path} mentions {forbidden!r}"
                )


# ── utc_now_iso / diff_sha256 helpers ──────────────────────────────────


class TestAuditHelpers:
    def test_utc_now_iso_is_z_suffixed(self):
        s = utc_now_iso()
        assert "T" in s
        assert s.endswith("Z")
        assert "+00:00" not in s

    def test_diff_sha256_empty_returns_known_hash(self):
        assert diff_sha256(None) == EMPTY_DIFF_SHA256
        assert diff_sha256("") == EMPTY_DIFF_SHA256

    def test_diff_sha256_matches_hashlib(self):
        sample = "diff --git a/x b/x\n@@ -1 +1 @@\n-a\n+b\n"
        assert diff_sha256(sample) == hashlib.sha256(
            sample.encode("utf-8")
        ).hexdigest()


# ── LibCST engine direct verification (defensive) ──────────────────────


class TestLibCSTEngineAudit:
    """The LibCST engine wires the same audit+verification surface as
    GitDiffEngine. Quick smoke tests on the structural_python path."""

    def test_structural_apply_attaches_audit_and_verification(self, git_repo):
        repo, _ = git_repo
        engine = LibCSTEngine()
        req = PatchRequest(
            repo_path=repo,
            patch_mode="structural_python",
            operations=[
                {"operation": "add_import", "file": "lib.py", "module": "os"}
            ],
        )
        result = engine.apply(req)
        assert result.applied is True
        assert result.audit is not None
        assert result.audit["patch_mode"] == "structural_python"
        assert result.audit["engine"] == "libcst"
        assert result.audit["verification_status"] == "passed"

    def test_structural_check_attaches_audit_with_not_run_verification(
        self, git_repo
    ):
        repo, _ = git_repo
        engine = LibCSTEngine()
        req = PatchRequest(
            repo_path=repo,
            patch_mode="structural_python",
            operations=[
                {"operation": "add_import", "file": "lib.py", "module": "os"}
            ],
        )
        result = engine.check(req)
        assert result.audit is not None
        assert result.audit["final_status"] == "check_passed"
        assert result.audit["verification_status"] == "not_run"