"""Tests for the mechanical testgoal checker.

The checker exists because validating a verdict cost 17-42 minutes per run and
consists of running commands and comparing output to a stated criterion. The
cases below are the criteria actually used in llama_SG runs 006-008, plus the
one piece of garbled evidence the checker is meant to settle instantly.
"""

import importlib.util
from pathlib import Path

import pytest

_MODULE = (Path(__file__).resolve().parent.parent
           / "scripts" / "bridgeV002" / "check_testgoals.py")
_spec = importlib.util.spec_from_file_location("check_testgoals", _MODULE)
ctg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ctg)


def _goal(tmp_path, body):
    path = tmp_path / "GOAL.md"
    path.write_text(f"# contract\n\n```testgoals\n{body}\n```\n", encoding="utf-8")
    return path


class TestParsing:

    def test_reads_records_separated_by_blank_lines(self, tmp_path):
        path = _goal(tmp_path, "id: TG1\nrun: true\nexpect: exit 0\n\n"
                               "id: TG2\nrun: true\nexpect: exit 0")
        records = ctg.parse_block(path.read_text())
        assert [r["id"] for r in records] == ["TG1", "TG2"]

    def test_run_takes_the_rest_of_the_line_verbatim(self, tmp_path):
        """Commands contain pipes and quotes; the parser must not split on them."""
        cmd = """grep -c '^# Example: /home/svend' .env.example | head -1"""
        path = _goal(tmp_path, f"id: TG1\nrun: {cmd}\nexpect: equals 4")
        assert ctg.parse_block(path.read_text())[0]["run"] == cmd

    def test_no_block_is_not_an_error(self, tmp_path):
        """An older GOAL.md simply cannot be checked mechanically."""
        path = tmp_path / "GOAL.md"
        path.write_text("# contract with prose testgoals only", encoding="utf-8")
        assert ctg.parse_block(path.read_text()) == []

    def test_missing_required_field_is_rejected(self, tmp_path):
        path = _goal(tmp_path, "id: TG1\nwhat: no run line")
        with pytest.raises(ctg.CriterionError, match="run"):
            ctg.parse_block(path.read_text())

    def test_stray_line_is_rejected_rather_than_ignored(self, tmp_path):
        path = _goal(tmp_path, "id: TG1\nthis is not a field\nrun: true\nexpect: exit 0")
        with pytest.raises(ctg.CriterionError):
            ctg.parse_block(path.read_text())


class TestEvaluate:

    @pytest.mark.parametrize("expect,stdout,rc,passed", [
        ("empty", "", 1, True),
        ("empty", "43:# Default: /home/svend/...", 0, False),
        ("equals 4", "4\n", 0, True),
        ("equals 4", "3\n", 0, False),
        ("at least 3", "5\n", 0, True),
        ("at least 3", "0\n", 0, False),
        ("at most 1", "1\n", 0, True),
        ("at most 1", "2\n", 0, False),
        ("contains SETUP.md", "see SETUP.md for details", 0, True),
        ("contains SETUP.md", "nothing here", 0, False),
        ("exit 0", "anything at all", 0, True),
        ("exit 0", "", 1, False),
    ])
    def test_forms(self, expect, stdout, rc, passed):
        assert ctg.evaluate(expect, stdout, rc)[0] is passed

    def test_non_numeric_output_fails_a_numeric_criterion(self):
        ok, detail = ctg.evaluate("at least 3", "not a number", 0)
        assert ok is False and "expected a number" in detail

    def test_unsupported_form_is_rejected(self):
        with pytest.raises(ctg.CriterionError, match="unsupported"):
            ctg.evaluate("roughly 3", "3", 0)


class TestAgainstRealIncidents:

    def test_catches_run_007_garbled_evidence(self, tmp_path):
        """Run 007's verdict cited `grep -icE "VRAM\\|GPU"`.

        Under extended regex `\\|` is a literal pipe, so the command searches
        for the string "VRAM|GPU" and returns 0 — while the contract's form,
        `grep -icE "VRAM|GPU"`, returns 5. The claim was true and the evidence
        was garbled, and the supervisor spent a re-derivation finding that out.
        """
        target = tmp_path / "SETUP.md"
        target.write_text("VRAM required\nGPU required\nvram again\n", encoding="utf-8")

        contract_form = ctg.run_criterion(
            {"id": "TG1", "run": 'grep -icE "VRAM|GPU" SETUP.md',
             "expect": "at least 3"}, cwd=str(tmp_path))
        as_cited = ctg.run_criterion(
            {"id": "TG1", "run": 'grep -icE "VRAM\\|GPU" SETUP.md',
             "expect": "at least 3"}, cwd=str(tmp_path))

        assert contract_form["passed"] is True
        assert as_cited["passed"] is False
        assert as_cited["detail"] == "got 0"

    def test_run_008_criteria_shape(self, tmp_path):
        """The two criteria that protected .env.example's Example lines."""
        env = tmp_path / ".env.example"
        env.write_text(
            "# Default: $HOME/trade-ui/inbox/pending\n"
            "# Example: /home/svend/llama.cpp/llama-server\n"
            "# Example: /home/svend/models/gguf\n",
            encoding="utf-8")

        no_literal = ctg.run_criterion(
            {"id": "TG1", "run": "grep -n '^# Default:' .env.example | grep '/home/'",
             "expect": "empty"}, cwd=str(tmp_path))
        examples_intact = ctg.run_criterion(
            {"id": "TG2", "run": "grep -c '^# Example: /home/svend' .env.example",
             "expect": "equals 2"}, cwd=str(tmp_path))

        assert no_literal["passed"] is True
        assert examples_intact["passed"] is True

    def test_a_blanket_replace_trips_the_guard(self, tmp_path):
        """Stripping every /home/svend would have destroyed the Example lines."""
        env = tmp_path / ".env.example"
        env.write_text(
            "# Default: $HOME/trade-ui/inbox/pending\n"
            "# Example: $HOME/llama.cpp/llama-server\n",
            encoding="utf-8")
        result = ctg.run_criterion(
            {"id": "TG2", "run": "grep -c '^# Example: /home/svend' .env.example",
             "expect": "equals 2"}, cwd=str(tmp_path))
        assert result["passed"] is False


class TestRender:

    def test_reports_which_failed(self, tmp_path):
        results = [
            {"id": "TG1", "what": "a", "run": "true", "expect": "exit 0",
             "detail": "exit 0", "passed": True, "stdout": "", "stderr": ""},
            {"id": "TG2", "what": "b", "run": "false", "expect": "exit 0",
             "detail": "exit 1", "passed": False, "stdout": "", "stderr": ""},
        ]
        out = ctg.render(results)
        assert "1/2 green" in out and "failing: TG2" in out

    def test_no_block_says_so_rather_than_claiming_green(self, tmp_path):
        assert "nothing to check" in ctg.render([])
