"""Tests for `patcher.engines.LibCSTEngine` and the public facade's
dispatch to it (Phase 1B + 1C — all seven §37 operations).

Mirrors the style of `test_patcher_git_engine.py`: tiny git repositories
are seeded in `tmp_path`. The Father repo is never used as a mutation
target.

Coverage (handoff Step 5):

  Phase 1B (B2 handoff):
    * `add_import` adds the import; running the same request again
      yields a no-change outcome and no duplicate import line.
    * `replace_function` replaces only the named function; other
      functions in the file remain byte-identical.
    * `add_function` appends the function; a same-named existing
      function fails with PATCH_TARGET_AMBIGUOUS.

  Phase 1C (this handoff):
    * `remove_import` removes an import; absent import yields the
      no-change outcome; multi-name imports keep their other names.
    * `replace_method` replaces only the named method in the named
      class; missing class or method → PATCH_TARGET_NOT_FOUND; two
      same-named classes or methods → PATCH_TARGET_AMBIGUOUS.
    * `add_method` appends; identical existing → no-change; different
      same-named → PATCH_CONFLICT; missing `class` parameter →
      PATCH_INVALID.
    * `replace_assignment` replaces the module-level assignment;
      duplicates → PATCH_TARGET_AMBIGUOUS; absent → PATCH_TARGET_NOT_FOUND;
      class-body-only → PATCH_TARGET_NOT_FOUND.
    * Multi-file atomicity: a request with operations on TWO files
      where the last op fails leaves BOTH files byte-identical.
    * `check()` on each new operation produces a proposed diff while
      writing nothing.

  Cross-cutting:
    * Ambiguous target → PATCH_TARGET_AMBIGUOUS, tree byte-identical.
    * Missing target → PATCH_TARGET_NOT_FOUND, tree byte-identical.
    * Unparseable source / invalid fragment → deterministic §11 error,
      tree byte-identical.
    * Unsupported operation name → PATCH_UNSUPPORTED_OPERATION.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Tuple

import pytest

from patcher import DeterministicPatcher, PatchRequest
from patcher.errors import (
    PATCH_APPLIED,
    PATCH_CONFLICT,
    PATCH_FILE_NOT_FOUND,
    PATCH_INVALID,
    PATCH_PATH_REJECTED,
    PATCH_TARGET_AMBIGUOUS,
    PATCH_TARGET_NOT_FOUND,
    PATCH_UNSUPPORTED_OPERATION,
)
from patcher.engines import LibCSTEngine


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture()
def git_repo(tmp_path: Path) -> Tuple[str, str]:
    """Return (repo_path, base_revision) for a tiny seeded repo.

    The seeded repo contains `lib.py` with two module-level functions
    (`alpha`, `beta`) and no imports. The structure is intentional —
    it gives every replace_function test a baseline with at least one
    "other" function to verify non-interference.
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
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    (repo / "lib.py").write_text(
        "def alpha():\n"
        "    return 1\n"
        "\n"
        "\n"
        "def beta():\n"
        "    return 2\n",
        encoding="utf-8",
    )
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    base = git("rev-parse", "HEAD").stdout.strip()
    return str(repo), base


def _tree_sha(repo_path: str) -> str:
    """Hash every file's contents into a stable tree fingerprint.

    Used to verify byte-identity before/after a call. We deliberately
    avoid `git write-tree` because that requires a clean index.
    """
    out = []
    for root, _dirs, files in os.walk(repo_path):
        if ".git" in root.split(os.sep):
            continue
        for fn in sorted(files):
            p = Path(root) / fn
            rel = p.relative_to(repo_path).as_posix()
            with open(p, "rb") as f:
                data = f.read()
            out.append(f"{rel}={data!r}")
    return "|".join(out)


# ── add_import ──────────────────────────────────────────────────────────


class TestAddImport:
    def test_add_import_appends_import_line(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        req = PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_import",
                "file": "lib.py",
                "module": "os",
            }],
        )
        result = DeterministicPatcher().apply(req)
        assert result.applied is True
        assert result.engine == "libcst"
        assert result.error_code == PATCH_APPLIED
        assert result.files_changed == ["lib.py"]
        assert result.status == "applied"

        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "import os" in text
        # The two existing functions are still present, byte-identical
        # modulo a single `import os\n` insertion before them.
        assert "def alpha" in text
        assert "def beta" in text
        # Tree changed from `before`.
        assert _tree_sha(repo) != before

    def test_add_import_is_idempotent(self, git_repo):
        """Running the same add_import twice yields a no-change outcome
        on the second call and does not duplicate the import line.
        """
        repo, _ = git_repo
        op = {
            "operation": "add_import",
            "file": "lib.py",
            "module": "os",
        }
        first = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[op],
        ))
        assert first.applied is True
        assert first.status == "applied"
        assert first.operations_applied == 1
        text_after_first = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert text_after_first.count("import os") == 1

        before_second = _tree_sha(repo)
        second = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[op],
        ))
        # Spec §27–§28: idempotent — same request again is a no-change.
        # `applied` is False because the working tree was not mutated;
        # status is no_change; operations_applied is 0.
        assert second.applied is False
        assert second.status == "no_change"
        assert second.operations_applied == 0
        assert second.files_changed == []
        assert second.resulting_diff in (None, "")
        # Tree is byte-identical after the second call.
        assert _tree_sha(repo) == before_second
        # And the import is still exactly one line.
        text_after_second = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert text_after_second.count("import os") == 1

    def test_add_import_from_module_import_name_idempotent(self, git_repo):
        """`from X import Y` form is also idempotent."""
        repo, _ = git_repo
        op = {
            "operation": "add_import",
            "file": "lib.py",
            "module": "pathlib",
            "name": "Path",
        }
        first = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[op],
        ))
        assert first.applied is True
        text_after_first = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "from pathlib import Path" in text_after_first
        assert text_after_first.count("from pathlib import Path") == 1

        before_second = _tree_sha(repo)
        second = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[op],
        ))
        assert second.status == "no_change"
        assert second.operations_applied == 0
        assert _tree_sha(repo) == before_second

    def test_add_import_inserted_after_docstring(self, git_repo):
        """When the file has a leading docstring, the import goes after
        the docstring and after any existing import block, matching the
        PEP 8 / isort convention.
        """
        repo, _ = git_repo
        # Replace lib.py with a docstring-bearing version and commit it
        # so the apply path does not see the file as pre-existing dirty
        # work (spec §32 — that case returns PATCH_CONFLICT, by design).
        (Path(repo) / "lib.py").write_text(
            '"""Module docstring."""\n'
            "\n"
            "def alpha():\n"
            "    return 1\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", repo, "add", "-A"],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "-C", repo, "commit", "-q", "-m", "with docstring"],
            capture_output=True, text=True, check=True,
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_import",
                "file": "lib.py",
                "module": "os",
            }],
        ))
        assert result.applied is True
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        # Docstring stays first, import goes after it, alpha stays last.
        lines = text.splitlines()
        idx_doc = lines.index('"""Module docstring."""')
        idx_imp = next(
            i for i, line in enumerate(lines) if line.startswith("import os")
        )
        idx_alpha = lines.index("def alpha():")
        assert idx_doc < idx_imp < idx_alpha
        assert _tree_sha(repo) != before


# ── replace_function ────────────────────────────────────────────────────


class TestReplaceFunction:
    def test_replace_function_replaces_only_target(self, git_repo):
        repo, _ = git_repo
        replacement = "def alpha():\n    return 42\n"
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_function",
                "file": "lib.py",
                "function": "alpha",
                "replacement": replacement,
            }],
        ))
        assert result.applied is True
        assert result.engine == "libcst"
        assert result.files_changed == ["lib.py"]

        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "def alpha():\n    return 42\n" in text
        # beta is byte-identical — same body, same indentation.
        assert "def beta():\n    return 2" in text

        # The file should contain exactly one `def alpha(` definition,
        # not two — LibCST rewrote the AST node, it did not append.
        assert text.count("def alpha(") == 1

    def test_replace_function_missing_target_returns_not_found(
        self, git_repo
    ):
        repo, _ = git_repo
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_function",
                "file": "lib.py",
                "function": "gamma",
                "replacement": "def gamma():\n    return 0\n",
            }],
        ))
        assert result.applied is False
        assert result.engine == "libcst"
        assert result.error_code == PATCH_TARGET_NOT_FOUND
        assert result.files_changed == []
        # Tree is byte-identical — no write occurred.
        assert _tree_sha(repo) == before

    def test_replace_function_ambiguous_target_returns_ambiguous(
        self, git_repo
    ):
        """Two module-level functions with the same name → AMBIGUOUS."""
        repo, _ = git_repo
        (Path(repo) / "lib.py").write_text(
            "def alpha():\n"
            "    return 1\n"
            "\n"
            "\n"
            "def alpha():\n"
            "    return 2\n",
            encoding="utf-8",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_function",
                "file": "lib.py",
                "function": "alpha",
                "replacement": "def alpha():\n    return 99\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_AMBIGUOUS
        assert result.files_changed == []
        assert _tree_sha(repo) == before

    def test_replace_function_rejects_replacement_with_wrong_name(
        self, git_repo
    ):
        """If the replacement defines a function with a different name
        than the target, refuse — the LLM gave us a mismatched payload.
        """
        repo, _ = git_repo
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_function",
                "file": "lib.py",
                "function": "alpha",
                "replacement": "def gamma():\n    return 0\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_INVALID
        assert _tree_sha(repo) == before

    def test_replace_function_invalid_fragment_returns_invalid(
        self, git_repo
    ):
        repo, _ = git_repo
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_function",
                "file": "lib.py",
                "function": "alpha",
                "replacement": "def alpha(:\n    return 0\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_INVALID
        assert _tree_sha(repo) == before


# ── add_function ────────────────────────────────────────────────────────


class TestAddFunction:
    def test_add_function_appends(self, git_repo):
        repo, _ = git_repo
        code = "def gamma():\n    return 3\n"
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_function",
                "file": "lib.py",
                "code": code,
            }],
        ))
        assert result.applied is True
        assert result.engine == "libcst"
        assert result.files_changed == ["lib.py"]

        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "def alpha" in text
        assert "def beta" in text
        assert "def gamma" in text
        # `gamma` was appended, not inserted at top — alpha and beta
        # remain in their original order before it.
        idx_alpha = text.index("def alpha")
        idx_beta = text.index("def beta")
        idx_gamma = text.index("def gamma")
        assert idx_alpha < idx_beta < idx_gamma

    def test_add_function_duplicate_name_returns_ambiguous(self, git_repo):
        """Adding a function whose name already exists must fail —
        adding is not replacing (spec §28 / handoff §3e)."""
        repo, _ = git_repo
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_function",
                "file": "lib.py",
                "code": "def alpha():\n    return 99\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_AMBIGUOUS
        assert result.files_changed == []
        assert _tree_sha(repo) == before

    def test_add_function_invalid_code_returns_invalid(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_function",
                "file": "lib.py",
                "code": "def gamma(:\n    return 0\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_INVALID
        assert _tree_sha(repo) == before


# ── Target identification negative paths ───────────────────────────────


class TestTargetIdentification:
    def test_replace_function_two_matches_is_ambiguous(self, git_repo):
        """Two module-level functions named the same — never guess."""
        repo, _ = git_repo
        (Path(repo) / "lib.py").write_text(
            "def alpha():\n"
            "    return 1\n"
            "\n"
            "\n"
            "def alpha():\n"
            "    return 2\n",
            encoding="utf-8",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_function",
                "file": "lib.py",
                "function": "alpha",
                "replacement": "def alpha():\n    return 99\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_AMBIGUOUS
        assert _tree_sha(repo) == before

    def test_replace_function_missing_returns_not_found(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_function",
                "file": "lib.py",
                "function": "no_such_function",
                "replacement": "def no_such_function():\n    return 0\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_NOT_FOUND
        assert _tree_sha(repo) == before


# ── Unparseable / invalid input ─────────────────────────────────────────


class TestUnparseableInput:
    def test_unparseable_target_file_returns_invalid(self, git_repo):
        repo, _ = git_repo
        # Deliberately broken Python — a SyntaxError at module level.
        (Path(repo) / "lib.py").write_text(
            "def alpha(:\n    return 1\n",
            encoding="utf-8",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_import",
                "file": "lib.py",
                "module": "os",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_INVALID
        assert result.files_changed == []
        assert _tree_sha(repo) == before

    def test_missing_target_file_returns_file_not_found(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_import",
                "file": "missing.py",
                "module": "os",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_FILE_NOT_FOUND
        assert result.files_changed == []
        assert _tree_sha(repo) == before

    def test_operation_missing_file_field_returns_invalid(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_import",
                "module": "os",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_INVALID
        assert _tree_sha(repo) == before


# ── check() never writes ────────────────────────────────────────────────


class TestCheckWritesNothing:
    def test_check_on_valid_request_produces_proposed_diff(
        self, git_repo
    ):
        """check() must produce a proposed diff while leaving the tree
        byte-identical (spec §15).
        """
        repo, _ = git_repo
        before = _tree_sha(repo)
        req = PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_import",
                "file": "lib.py",
                "module": "os",
            }],
        )
        result = DeterministicPatcher().check(req)
        assert result.applied is False
        assert result.engine == "libcst"
        assert result.status == "check_passed"
        assert result.files_changed == ["lib.py"]
        # The proposed diff is present and well-formed.
        assert result.resulting_diff is not None
        assert "import os" in result.resulting_diff
        assert "a/lib.py" in result.resulting_diff
        assert "b/lib.py" in result.resulting_diff
        # No write occurred.
        assert _tree_sha(repo) == before
        # And the file on disk does NOT contain the new import.
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "import os" not in text

    def test_check_on_replace_function_produces_diff(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        req = PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_function",
                "file": "lib.py",
                "function": "alpha",
                "replacement": "def alpha():\n    return 42\n",
            }],
        )
        result = DeterministicPatcher().check(req)
        assert result.applied is False
        assert result.status == "check_passed"
        assert result.resulting_diff is not None
        assert "return 42" in result.resulting_diff
        # No write.
        assert _tree_sha(repo) == before
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "return 42" not in text

    def test_check_on_failing_request_does_not_write(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        req = PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_function",
                "file": "lib.py",
                "function": "no_such_function",
                "replacement": "def no_such_function():\n    return 0\n",
            }],
        )
        result = DeterministicPatcher().check(req)
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_NOT_FOUND
        assert _tree_sha(repo) == before


# ── Unsupported operation names ─────────────────────────────────────────


class TestUnsupportedOperations:
    @pytest.mark.parametrize(
        "op_name",
        # Spec §37 ships seven operations, all of which are now
        # supported by LibCSTEngine. The remaining names below are
        # the spec §12 entries that are NOT in §37 (replace_import,
        # modify_call_argument) and the §37 candidates deliberately
        # left for Phase 2 (remove_function). Each must still
        # surface PATCH_UNSUPPORTED_OPERATION — this is the §37-vs-
        # §12 contract boundary.
        ["modify_call_argument", "remove_function", "replace_import"],
    )
    def test_unsupported_operation_returns_unsupported(
        self, git_repo, op_name
    ):
        """Operation names outside the §37 list (or above §37 in the
        §12 ladder) must return PATCH_UNSUPPORTED_OPERATION (handoff
        Step 4). The four operations now supported
        (remove_import, replace_method, add_method,
        replace_assignment) are exercised by their own tests.
        """
        repo, _ = git_repo
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": op_name,
                "file": "lib.py",
            }],
        ))
        assert result.applied is False
        assert result.engine == "libcst"
        assert result.error_code == PATCH_UNSUPPORTED_OPERATION
        assert result.files_changed == []
        # Tree is byte-identical.
        assert _tree_sha(repo) == before


# ── Atomicity across multiple operations ────────────────────────────────


class TestAtomicity:
    def test_multi_operation_atomic_on_partial_failure(self, git_repo):
        """Two ops on the same file, second one invalid: the first op
        must NOT have been persisted either — atomicity (spec §17).
        """
        repo, _ = git_repo
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[
                {
                    "operation": "add_import",
                    "file": "lib.py",
                    "module": "os",
                },
                {
                    "operation": "replace_function",
                    "file": "lib.py",
                    "function": "no_such_function",
                    "replacement": "def no_such_function():\n    return 0\n",
                },
            ],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_NOT_FOUND
        assert result.files_changed == []
        # The first op's import must NOT have landed in the file.
        assert _tree_sha(repo) == before
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "import os" not in text


# ── remove_import ───────────────────────────────────────────────────────


class TestRemoveImport:
    """Spec §37 `remove_import` — mirrors `add_import`'s matching
    rules. Absent import is the idempotent no-change outcome
    (handoff §3a / spec §28).
    """

    def _seed_repo_with_imports(self, tmp_path: Path) -> str:
        """Create a one-file repo whose `lib.py` exercises every shape
        the `remove_import` matcher handles: single `import X`,
        multi-name `import X, Y`, single-name `from M import N`,
        and multi-name `from M import N, P`.
        """
        repo = tmp_path / "ri_repo"
        repo.mkdir()
        lib = repo / "lib.py"
        lib.write_text(
            "import os\n"
            "import sys, json\n"
            "from collections import OrderedDict\n"
            "from pathlib import Path, PurePosixPath\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", str(repo), "init", "-q"],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "t@t"],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "t"],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "add", "-A"],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-q", "-m", "seed"],
            capture_output=True, text=True, check=True,
        )
        return str(repo)

    def test_remove_import_single_line(self, tmp_path):
        repo = self._seed_repo_with_imports(tmp_path)
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "remove_import",
                "file": "lib.py",
                "module": "os",
            }],
        ))
        assert result.applied is True
        assert result.engine == "libcst"
        assert result.error_code == PATCH_APPLIED
        assert result.files_changed == ["lib.py"]
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "import os" not in text
        # The other imports remain untouched.
        assert "import sys, json" in text
        assert "from collections import OrderedDict" in text
        assert "from pathlib import Path, PurePosixPath" in text
        assert _tree_sha(repo) != before

    def test_remove_import_from_module_one_name_keeps_other(
        self, tmp_path
    ):
        """Removing one name from `from M import N, P` must leave the
        other name on the same import line.
        """
        repo = self._seed_repo_with_imports(tmp_path)
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "remove_import",
                "file": "lib.py",
                "module": "pathlib",
                "name": "PurePosixPath",
            }],
        ))
        assert result.applied is True
        assert result.error_code == PATCH_APPLIED
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        # `Path` survives; `PurePosixPath` is gone.
        assert "from pathlib import Path" in text
        assert "PurePosixPath" not in text
        # Other imports untouched.
        assert "import os" in text
        assert "import sys, json" in text
        assert _tree_sha(repo) != before

    def test_remove_import_multi_name_alias_keeps_other(
        self, tmp_path
    ):
        """Removing one alias from `import sys, json` must leave
        `sys` on the same line, without producing `import sys,` or
        any other LibCST-validation-breaking trailing-comma shape.
        """
        repo = self._seed_repo_with_imports(tmp_path)
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "remove_import",
                "file": "lib.py",
                "module": "json",
            }],
        ))
        assert result.applied is True
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        # `sys` survives; `json` is gone — and the line is a clean
        # `import sys` (no trailing comma) so LibCST validation
        # passes on the round trip.
        assert "import sys\n" in text
        assert "json" not in text
        assert _tree_sha(repo) != before

    def test_remove_import_absent_is_idempotent_no_change(
        self, tmp_path
    ):
        """Requesting an import that is not present yields the same
        no-change outcome that `add_import` uses (handoff §3a).
        """
        repo = self._seed_repo_with_imports(tmp_path)
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "remove_import",
                "file": "lib.py",
                "module": "nonexistent_module",
            }],
        ))
        assert result.applied is False
        assert result.status == "no_change"
        assert result.operations_applied == 0
        assert result.files_changed == []
        assert result.resulting_diff in (None, "")
        assert _tree_sha(repo) == before

    def test_remove_import_absent_name_is_idempotent_no_change(
        self, tmp_path
    ):
        """Same for a missing name under a present module — the
        matching is identical to `add_import`'s `_import_already_present`.
        """
        repo = self._seed_repo_with_imports(tmp_path)
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "remove_import",
                "file": "lib.py",
                "module": "pathlib",
                "name": "PureWindowsPath",
            }],
        ))
        assert result.applied is False
        assert result.status == "no_change"
        assert result.operations_applied == 0
        assert _tree_sha(repo) == before

    def test_check_remove_import_writes_nothing(self, tmp_path):
        """check() on a valid remove_import request produces a diff
        while writing nothing to disk (spec §15).
        """
        repo = self._seed_repo_with_imports(tmp_path)
        before = _tree_sha(repo)
        req = PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "remove_import",
                "file": "lib.py",
                "module": "os",
            }],
        )
        result = DeterministicPatcher().check(req)
        assert result.applied is False
        assert result.status == "check_passed"
        assert result.resulting_diff is not None
        assert "import os" in result.resulting_diff
        assert "a/lib.py" in result.resulting_diff
        assert "b/lib.py" in result.resulting_diff
        assert _tree_sha(repo) == before
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "import os" in text  # unchanged


# ── replace_method ──────────────────────────────────────────────────────


def _method_classes_repo(
    tmp_path: Path, lib_source: str, name: str = "rm_repo"
) -> str:
    """Helper: seed a one-file repo with arbitrary `lib.py` content."""
    repo = tmp_path / name
    repo.mkdir()
    (repo / "lib.py").write_text(lib_source, encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "init", "-q"],
        capture_output=True, text=True, check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "t@t"],
        capture_output=True, text=True, check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "t"],
        capture_output=True, text=True, check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "add", "-A"],
        capture_output=True, text=True, check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "seed"],
        capture_output=True, text=True, check=True,
    )
    return str(repo)


class TestReplaceMethod:
    """Spec §37 `replace_method` — method targets include class identity
    (§13). Missing class or method → PATCH_TARGET_NOT_FOUND; more than
    one matching class or method → PATCH_TARGET_AMBIGUOUS. A same-named
    module-level function must NOT satisfy a method target.
    """

    def test_replace_method_replaces_only_named_method(self, tmp_path):
        repo = _method_classes_repo(
            tmp_path,
            "class Foo:\n"
            "    def bar(self):\n"
            "        return 1\n"
            "\n"
            "    def baz(self):\n"
            "        return 2\n",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_method",
                "file": "lib.py",
                "class": "Foo",
                "method": "bar",
                "replacement": "def bar(self):\n    return 99\n",
            }],
        ))
        assert result.applied is True
        assert result.error_code == PATCH_APPLIED
        assert result.files_changed == ["lib.py"]
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "def bar(self):\n        return 99" in text
        # `baz` is untouched, byte-identical body.
        assert "def baz(self):\n        return 2" in text
        assert _tree_sha(repo) != before

    def test_replace_method_leaves_module_level_function_alone(
        self, tmp_path
    ):
        """A same-named module-level function must NOT satisfy a
        method target — `replace_method` only inspects the named
        class's body (handoff §3b, §13).
        """
        repo = _method_classes_repo(
            tmp_path,
            "def bar():\n"
            "    return 0\n"
            "\n"
            "class Foo:\n"
            "    pass\n",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_method",
                "file": "lib.py",
                "class": "Foo",
                "method": "bar",
                "replacement": "def bar(self):\n    return 99\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_NOT_FOUND
        assert _tree_sha(repo) == before
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        # The module-level `bar` is unchanged.
        assert "def bar():\n    return 0" in text

    def test_replace_method_missing_class_returns_not_found(
        self, tmp_path
    ):
        repo = _method_classes_repo(
            tmp_path,
            "class Foo:\n    def bar(self):\n        return 1\n",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_method",
                "file": "lib.py",
                "class": "Missing",
                "method": "bar",
                "replacement": "def bar(self):\n    return 99\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_NOT_FOUND
        assert result.files_changed == []
        assert _tree_sha(repo) == before

    def test_replace_method_missing_method_returns_not_found(
        self, tmp_path
    ):
        repo = _method_classes_repo(
            tmp_path,
            "class Foo:\n    def bar(self):\n        return 1\n",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_method",
                "file": "lib.py",
                "class": "Foo",
                "method": "no_such_method",
                "replacement": "def no_such_method(self):\n    return 0\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_NOT_FOUND
        assert _tree_sha(repo) == before

    def test_replace_method_two_same_named_classes_returns_ambiguous(
        self, tmp_path
    ):
        """Two module-level classes with the same name → PATCH_TARGET_AMBIGUOUS
        (spec §13, handoff §3b). Tree must be byte-identical.
        """
        repo = _method_classes_repo(
            tmp_path,
            "class Foo:\n"
            "    def bar(self):\n"
            "        return 1\n"
            "\n"
            "class Foo:\n"
            "    def bar(self):\n"
            "        return 2\n",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_method",
                "file": "lib.py",
                "class": "Foo",
                "method": "bar",
                "replacement": "def bar(self):\n    return 99\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_AMBIGUOUS
        assert result.files_changed == []
        assert _tree_sha(repo) == before

    def test_replace_method_two_same_named_methods_returns_ambiguous(
        self, tmp_path
    ):
        """Two methods with the same name inside the same class →
        PATCH_TARGET_AMBIGUOUS (spec §13, handoff §3b).
        """
        repo = _method_classes_repo(
            tmp_path,
            "class Foo:\n"
            "    def bar(self):\n"
            "        return 1\n"
            "\n"
            "    def bar(self):\n"
            "        return 2\n",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_method",
                "file": "lib.py",
                "class": "Foo",
                "method": "bar",
                "replacement": "def bar(self):\n    return 99\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_AMBIGUOUS
        assert _tree_sha(repo) == before

    def test_check_replace_method_produces_diff(self, tmp_path):
        """check() produces a proposed diff while writing nothing."""
        repo = _method_classes_repo(
            tmp_path,
            "class Foo:\n    def bar(self):\n        return 1\n",
        )
        before = _tree_sha(repo)
        req = PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_method",
                "file": "lib.py",
                "class": "Foo",
                "method": "bar",
                "replacement": "def bar(self):\n    return 99\n",
            }],
        )
        result = DeterministicPatcher().check(req)
        assert result.applied is False
        assert result.status == "check_passed"
        assert result.resulting_diff is not None
        assert "return 99" in result.resulting_diff
        assert _tree_sha(repo) == before
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "return 99" not in text


# ── add_method ──────────────────────────────────────────────────────────


class TestAddMethod:
    """Spec §37 `add_method` — requires `class`, idempotent on
    equivalent existing code, PATCH_CONFLICT on different same-named
    existing code (handoff §3c / Mission Contract O4).
    """

    def test_add_method_appends_to_named_class(self, tmp_path):
        repo = _method_classes_repo(
            tmp_path,
            "class Foo:\n    def bar(self):\n        return 1\n",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_method",
                "file": "lib.py",
                "class": "Foo",
                "code": "def baz(self):\n    return 2\n",
            }],
        ))
        assert result.applied is True
        assert result.error_code == PATCH_APPLIED
        assert result.files_changed == ["lib.py"]
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "def bar(self):\n        return 1" in text
        assert "def baz(self):\n        return 2" in text
        # `baz` is appended after `bar`.
        idx_bar = text.index("def bar(")
        idx_baz = text.index("def baz(")
        assert idx_bar < idx_baz
        assert _tree_sha(repo) != before

    def test_add_method_idempotent_on_equivalent_code(self, tmp_path):
        """Same `class` + same `code` + already-present method with
        the same body → no-change outcome, tree byte-identical.
        """
        repo = _method_classes_repo(
            tmp_path,
            "class Foo:\n"
            "    def bar(self):\n"
            "        return 1\n"
            "\n"
            "    def baz(self):\n"
            "        return 2\n",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_method",
                "file": "lib.py",
                "class": "Foo",
                "code": "def baz(self):\n    return 2\n",
            }],
        ))
        assert result.applied is False
        assert result.status == "no_change"
        assert result.operations_applied == 0
        assert result.files_changed == []
        assert _tree_sha(repo) == before

    def test_add_method_conflict_on_different_same_named_code(
        self, tmp_path
    ):
        """Same method name with DIFFERENT body → PATCH_CONFLICT,
        mutate nothing (handoff §3c / spec §28 / O4).
        """
        repo = _method_classes_repo(
            tmp_path,
            "class Foo:\n"
            "    def bar(self):\n"
            "        return 1\n"
            "\n"
            "    def baz(self):\n"
            "        return 2\n",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_method",
                "file": "lib.py",
                "class": "Foo",
                "code": "def baz(self):\n    return 999\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_CONFLICT
        assert result.files_changed == []
        # Tree is byte-identical — conflict does not mutate.
        assert _tree_sha(repo) == before
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "return 2" in text  # original code unchanged
        assert "return 999" not in text

    def test_add_method_missing_class_returns_invalid(self, tmp_path):
        """Missing `class` field → PATCH_INVALID (handoff §3c:
        "missing class parameter → deterministic §11 error").
        """
        repo = _method_classes_repo(
            tmp_path,
            "class Foo:\n    def bar(self):\n        return 1\n",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_method",
                "file": "lib.py",
                "code": "def baz(self):\n    return 2\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_INVALID
        assert _tree_sha(repo) == before

    def test_add_method_missing_class_field_returns_not_found(
        self, tmp_path
    ):
        """`class` is provided but no such class exists → PATCH_TARGET_NOT_FOUND."""
        repo = _method_classes_repo(
            tmp_path,
            "class Foo:\n    def bar(self):\n        return 1\n",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_method",
                "file": "lib.py",
                "class": "Missing",
                "code": "def baz(self):\n    return 2\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_NOT_FOUND
        assert _tree_sha(repo) == before

    def test_check_add_method_produces_diff(self, tmp_path):
        """check() on a valid add_method request produces a diff while
        writing nothing (spec §15).
        """
        repo = _method_classes_repo(
            tmp_path,
            "class Foo:\n    def bar(self):\n        return 1\n",
        )
        before = _tree_sha(repo)
        req = PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_method",
                "file": "lib.py",
                "class": "Foo",
                "code": "def baz(self):\n    return 2\n",
            }],
        )
        result = DeterministicPatcher().check(req)
        assert result.applied is False
        assert result.status == "check_passed"
        assert result.resulting_diff is not None
        assert "def baz" in result.resulting_diff
        assert _tree_sha(repo) == before
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "def baz" not in text


# ── replace_assignment ──────────────────────────────────────────────────


class TestReplaceAssignment:
    """Spec §37 `replace_assignment` — module-level `NAME = <expr>`
    only (handoff §3d). Phase 2's `replace_class_attribute` is out of
    scope; class-body-only matches surface as PATCH_TARGET_NOT_FOUND.
    """

    def test_replace_assignment_module_level(self, tmp_path):
        repo = _method_classes_repo(
            tmp_path,
            "X = 1\nY = 2\nclass C:\n    Z = 3\n",
            name="ra_repo",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_assignment",
                "file": "lib.py",
                "name": "X",
                "replacement": "X = 42\n",
            }],
        ))
        assert result.applied is True
        assert result.error_code == PATCH_APPLIED
        assert result.files_changed == ["lib.py"]
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "X = 42" in text
        assert "X = 1" not in text
        # `Y` and the class body are untouched.
        assert "Y = 2" in text
        assert "    Z = 3" in text
        assert _tree_sha(repo) != before

    def test_replace_assignment_absent_returns_not_found(
        self, tmp_path
    ):
        repo = _method_classes_repo(
            tmp_path, "X = 1\n", name="ra_repo",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_assignment",
                "file": "lib.py",
                "name": "Missing",
                "replacement": "Missing = 42\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_NOT_FOUND
        assert _tree_sha(repo) == before

    def test_replace_assignment_duplicates_returns_ambiguous(
        self, tmp_path
    ):
        """Two module-level assignments to the same name →
        PATCH_TARGET_AMBIGUOUS (handoff §3d).
        """
        repo = _method_classes_repo(
            tmp_path, "X = 1\nX = 2\n", name="ra_repo",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_assignment",
                "file": "lib.py",
                "name": "X",
                "replacement": "X = 42\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_AMBIGUOUS
        assert _tree_sha(repo) == before

    def test_replace_assignment_class_body_only_returns_not_found(
        self, tmp_path
    ):
        """A name assigned only inside a class body is out of scope
        for §37 `replace_assignment` (Phase 2 `replace_class_attribute`).
        A request that only matches inside a class body therefore
        returns PATCH_TARGET_NOT_FOUND.
        """
        repo = _method_classes_repo(
            tmp_path,
            "class C:\n    Z = 3\n",
            name="ra_repo",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_assignment",
                "file": "lib.py",
                "name": "Z",
                "replacement": "Z = 42\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_NOT_FOUND
        assert _tree_sha(repo) == before

    def test_replace_assignment_wrong_replacement_target_name(
        self, tmp_path
    ):
        """The replacement must target the same Name; a mismatched
        payload is PATCH_INVALID (mirrors `replace_function`'s
        wrong-name check).
        """
        repo = _method_classes_repo(
            tmp_path, "X = 1\n", name="ra_repo",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_assignment",
                "file": "lib.py",
                "name": "X",
                "replacement": "Y = 42\n",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_INVALID
        assert _tree_sha(repo) == before

    def test_check_replace_assignment_produces_diff(self, tmp_path):
        """check() on a valid replace_assignment request produces a
        diff while writing nothing.
        """
        repo = _method_classes_repo(
            tmp_path, "X = 1\n", name="ra_repo",
        )
        before = _tree_sha(repo)
        req = PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "replace_assignment",
                "file": "lib.py",
                "name": "X",
                "replacement": "X = 42\n",
            }],
        )
        result = DeterministicPatcher().check(req)
        assert result.applied is False
        assert result.status == "check_passed"
        assert result.resulting_diff is not None
        assert "X = 42" in result.resulting_diff
        assert _tree_sha(repo) == before
        text = (Path(repo) / "lib.py").read_text(encoding="utf-8")
        assert "X = 42" not in text


# ── Multi-file atomicity ────────────────────────────────────────────────


class TestMultiFileAtomicity:
    """A request whose operations span SEVERAL files must apply all
    operations or none (handoff Step 3, spec §17 fail-all). The test
    exercises the realistic shape: two files, the second operation
    fails on a missing target, and BOTH files must remain
    byte-identical to the pre-call state.
    """

    def _seed_two_file_repo(
        self, tmp_path: Path, first: str, second: str
    ) -> str:
        repo = tmp_path / "multi_repo"
        repo.mkdir()
        (repo / "first.py").write_text(first, encoding="utf-8")
        (repo / "second.py").write_text(second, encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "init", "-q"],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "t@t"],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "t"],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "add", "-A"],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-q", "-m", "seed"],
            capture_output=True, text=True, check=True,
        )
        return str(repo)

    def test_two_files_last_op_fails_leaves_both_byte_identical(
        self, tmp_path
    ):
        repo = self._seed_two_file_repo(
            tmp_path,
            first="import sys\ndef foo(): return 1\n",
            second="class Foo:\n    def bar(self): return 1\n",
        )
        first_bytes = (Path(repo) / "first.py").read_bytes()
        second_bytes = (Path(repo) / "second.py").read_bytes()
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[
                {
                    # First op: real mutation on first.py.
                    "operation": "add_import",
                    "file": "first.py",
                    "module": "os",
                },
                {
                    # Second op: must fail on second.py because the
                    # method does not exist.
                    "operation": "replace_method",
                    "file": "second.py",
                    "class": "Foo",
                    "method": "no_such_method",
                    "replacement": (
                        "def no_such_method(self):\n    return 99\n"
                    ),
                },
            ],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_TARGET_NOT_FOUND
        assert result.files_changed == []
        # Both files are byte-identical to the pre-call state. The
        # first op's `import os` must NOT have landed on disk.
        assert (Path(repo) / "first.py").read_bytes() == first_bytes
        assert (Path(repo) / "second.py").read_bytes() == second_bytes
        assert _tree_sha(repo) == before
        text = (Path(repo) / "first.py").read_text(encoding="utf-8")
        assert "import os" not in text

    def test_two_files_success_applies_both(self, tmp_path):
        """Sanity-check the same shape with two successful operations:
        both files must change, and operations_applied reflects the
        total.
        """
        repo = self._seed_two_file_repo(
            tmp_path,
            first="import sys\ndef foo(): return 1\n",
            second="class Foo:\n    def bar(self): return 1\n",
        )
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[
                {
                    "operation": "add_import",
                    "file": "first.py",
                    "module": "os",
                },
                {
                    "operation": "replace_method",
                    "file": "second.py",
                    "class": "Foo",
                    "method": "bar",
                    "replacement": (
                        "def bar(self):\n    return 99\n"
                    ),
                },
            ],
        ))
        assert result.applied is True
        assert result.error_code == PATCH_APPLIED
        assert sorted(result.files_changed) == ["first.py", "second.py"]
        assert result.operations_applied == 2
        assert result.operations_requested == 2
        assert _tree_sha(repo) != before
        first_text = (Path(repo) / "first.py").read_text(encoding="utf-8")
        second_text = (Path(repo) / "second.py").read_text(encoding="utf-8")
        assert "import os" in first_text
        assert "return 99" in second_text


# ── Engine-level path security ──────────────────────────────────────────


class TestEnginePathSecurity:
    def test_path_traversal_in_operation_rejected(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        result = DeterministicPatcher().apply(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_import",
                "file": "../escape.py",
                "module": "os",
            }],
        ))
        assert result.applied is False
        assert result.error_code == PATCH_PATH_REJECTED
        assert _tree_sha(repo) == before


# ── Direct engine invocation ────────────────────────────────────────────


class TestEngineDirect:
    def test_engine_check_does_not_write(self, git_repo):
        repo, _ = git_repo
        before = _tree_sha(repo)
        engine = LibCSTEngine()
        result = engine.check(PatchRequest(
            repo_path=repo, patch_mode="structural_python",
            operations=[{
                "operation": "add_import",
                "file": "lib.py",
                "module": "os",
            }],
        ))
        assert result.applied is False
        assert result.engine == "libcst"
        assert result.status == "check_passed"
        assert _tree_sha(repo) == before

    def test_engine_rejects_wrong_patch_mode(self, git_repo):
        repo, _ = git_repo
        engine = LibCSTEngine()
        result = engine.apply(PatchRequest(
            repo_path=repo, patch_mode="unified_diff",
            patch="x",
        ))
        assert result.applied is False
        assert result.error_code == PATCH_INVALID

    def test_engine_name_is_libcst(self):
        assert LibCSTEngine.name == "libcst"


# ── Determinism / no-LLM / no-bridge contract ───────────────────────────


class TestNoLLMDependency:
    def test_engine_module_has_no_model_allocator_import(self):
        """The engine must not depend on Model Allocator, bridge code,
        or any LLM client (spec §6, §23–§24). We assert by parsing the
        source file and inspecting its actual `import` statements only —
        a textual grep over the whole file would falsely match
        explanatory prose that mentions what the engine does NOT do.
        """
        import ast

        from patcher.engines import libcst_engine as mod
        src_path = Path(mod.__file__)
        text = src_path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        imported: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module)
                for alias in node.names:
                    imported.add(alias.name)
        for forbidden in (
            "model_allocator", "bridge", "bridgeV002", "anthropic",
            "openai", "ollama", "llm_client", "chat_completion",
        ):
            assert not any(forbidden in name for name in imported), (
                f"libcst_engine.py imports {forbidden!r} transitively or "
                f"directly: {sorted(imported)}"
            )
