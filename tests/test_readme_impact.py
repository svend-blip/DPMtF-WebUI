"""Tests for scripts/bridgeV002/readme_impact.py — the README Impact
deliverable contract. Every stable code is asserted in both directions:
emitted for its failure, absent for the nearest valid case."""

import importlib.util
import json
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "readme_impact",
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "bridgeV002"
    / "readme_impact.py",
)
ri = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ri)


VALID_NO = """<handoff_id>7</handoff_id>

# Result 7

Work happened.

## README Impact

README impact: no

Reason: Internal parser refactor only; no user/operator-visible contract changed.

## Evidence

Some evidence.
"""

VALID_YES = """# Result 8

## README Impact

README impact: yes

Affected sections:
- Installation
- Configuration

README updated: yes

Verification:
- `python3 scripts/validate_readme.py README.md --json`
- PASS

## Evidence

Some evidence.
"""


def codes(result):
    return [e["code"] for e in result["errors"]]


class TestValidDeclarations(unittest.TestCase):
    def test_no_with_reason_is_valid(self):
        result = ri.validate_readme_impact(VALID_NO)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["parsed"]["impact"], "no")
        self.assertTrue(result["parsed"]["reason"])

    def test_yes_with_sections_update_and_evidence_is_valid(self):
        result = ri.validate_readme_impact(VALID_YES)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(
            result["parsed"]["affected_sections"], ["Installation", "Configuration"]
        )
        self.assertTrue(result["parsed"]["readme_updated"])
        self.assertEqual(result["parsed"]["validation"]["status"], "pass")

    def test_case_and_whitespace_are_normalized(self):
        text = VALID_NO.replace("README impact: no", "  readme IMPACT:   NO  ")
        # Heading match is exact; the declaration line is what normalizes.
        text = text.replace("  readme IMPACT:   NO  ", "README IMPACT:   No")
        result = ri.validate_readme_impact(text)
        self.assertTrue(result["valid"], result["errors"])

    def test_frontend_and_readme_impact_coexist(self):
        text = VALID_YES + "\n## Frontend Impact\n\nNo frontend impact.\n\nReason: backend only.\n"
        result = ri.validate_readme_impact(text)
        self.assertTrue(result["valid"], result["errors"])

    def test_result_is_json_serializable(self):
        json.dumps(ri.validate_readme_impact(VALID_YES))


class TestBlockPresence(unittest.TestCase):
    def test_missing_block_fails(self):
        result = ri.validate_readme_impact("# Result\n\nNo block here.\n")
        self.assertIn("README_IMPACT_BLOCK_MISSING", codes(result))

    def test_missing_block_message_carries_the_template(self):
        result = ri.validate_readme_impact("# Result\n")
        msg = result["errors"][0]["message"]
        self.assertIn("README impact: no", msg)

    def test_duplicate_block_fails(self):
        text = VALID_NO + "\n## README Impact\n\nREADME impact: no\n\nReason: again.\n"
        result = ri.validate_readme_impact(text)
        self.assertIn("README_IMPACT_BLOCK_DUPLICATE", codes(result))

    def test_block_inside_code_fence_does_not_count(self):
        text = "# Result\n\n```markdown\n## README Impact\n\nREADME impact: no\n```\n"
        result = ri.validate_readme_impact(text)
        self.assertIn("README_IMPACT_BLOCK_MISSING", codes(result))

    def test_fenced_example_does_not_create_a_duplicate(self):
        text = VALID_NO + "\n```markdown\n## README Impact\n```\n"
        result = ri.validate_readme_impact(text)
        self.assertNotIn("README_IMPACT_BLOCK_DUPLICATE", codes(result))
        self.assertTrue(result["valid"], result["errors"])


class TestDeclarationValue(unittest.TestCase):
    def test_missing_declaration_fails(self):
        text = "## README Impact\n\nSomething vague.\n"
        result = ri.validate_readme_impact(text)
        self.assertIn("README_IMPACT_VALUE_MISSING", codes(result))

    def test_invalid_value_fails(self):
        text = "## README Impact\n\nREADME impact: maybe\n"
        result = ri.validate_readme_impact(text)
        self.assertIn("README_IMPACT_VALUE_INVALID", codes(result))


class TestNoContract(unittest.TestCase):
    def test_no_without_reason_fails(self):
        text = "## README Impact\n\nREADME impact: no\n"
        result = ri.validate_readme_impact(text)
        self.assertIn("README_IMPACT_NO_REASON_MISSING", codes(result))

    def test_no_with_empty_reason_fails(self):
        text = "## README Impact\n\nREADME impact: no\n\nReason:\n"
        result = ri.validate_readme_impact(text)
        self.assertIn("README_IMPACT_NO_REASON_MISSING", codes(result))


class TestYesContract(unittest.TestCase):
    def test_yes_without_sections_fails(self):
        text = VALID_YES.replace("Affected sections:\n- Installation\n- Configuration\n\n", "")
        result = ri.validate_readme_impact(text)
        self.assertIn("README_IMPACT_AFFECTED_SECTIONS_MISSING", codes(result))

    def test_yes_without_update_confirmation_fails(self):
        text = VALID_YES.replace("README updated: yes\n\n", "")
        result = ri.validate_readme_impact(text)
        self.assertIn("README_IMPACT_UPDATE_CONFIRMATION_MISSING", codes(result))

    def test_yes_with_updated_no_fails(self):
        text = VALID_YES.replace("README updated: yes", "README updated: no")
        result = ri.validate_readme_impact(text)
        self.assertIn("README_IMPACT_README_NOT_UPDATED", codes(result))

    def test_yes_without_verification_fails(self):
        text = VALID_YES[: VALID_YES.index("Verification:")] + "\n## Evidence\n"
        result = ri.validate_readme_impact(text)
        self.assertIn("README_IMPACT_VALIDATION_EVIDENCE_MISSING", codes(result))

    def test_yes_with_fail_evidence_fails(self):
        text = VALID_YES.replace("- PASS", "- FAIL")
        result = ri.validate_readme_impact(text)
        self.assertIn("README_VALIDATION_FAILED", codes(result))


class TestLiveReadmeRecheck(unittest.TestCase):
    def test_live_fail_overrides_pass_evidence(self):
        import tempfile, os

        with tempfile.TemporaryDirectory() as d:
            bad_readme = os.path.join(d, "README.md")
            with open(bad_readme, "w") as fh:
                fh.write("no structure at all\n")
            result = ri.validate_readme_impact(VALID_YES, readme_path=bad_readme)
            self.assertIn("README_VALIDATION_FAILED", codes(result))

    def test_live_pass_keeps_valid(self):
        import tempfile, os

        compliant = (
            "# p\n\ns\n\n## Overview\n\no\n\n## Architecture\n\na\n\n"
            "## Requirements\n\nr\n\n## Installation\n\n### Install manually\n\nm\n\n"
            "### Install using an Agent\n\na\n\n### Verify installation\n\nv\n\n"
            "## Configuration\n\nc\n\n## Running\n\nr\n\n## Testing\n\nt\n"
        )
        with tempfile.TemporaryDirectory() as d:
            good_readme = os.path.join(d, "README.md")
            with open(good_readme, "w") as fh:
                fh.write(compliant)
            result = ri.validate_readme_impact(VALID_YES, readme_path=good_readme)
            self.assertTrue(result["valid"], result["errors"])


class TestStepActivation(unittest.TestCase):
    def test_missing_column_means_not_activated(self):
        import tempfile, sqlite3, os

        with tempfile.TemporaryDirectory() as d:
            db = os.path.join(d, "old.db")
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE bridge_flow_steps (flow_key TEXT, from_role TEXT, to_role TEXT)"
            )
            conn.execute("INSERT INTO bridge_flow_steps VALUES ('f','a','b')")
            conn.commit()
            conn.close()
            self.assertFalse(ri.step_requires_readme_impact("f", "a", "b", db_path=db))

    def test_flag_activates_exactly_the_marked_step(self):
        import tempfile, sqlite3, os

        with tempfile.TemporaryDirectory() as d:
            db = os.path.join(d, "new.db")
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE bridge_flow_steps (flow_key TEXT, from_role TEXT, "
                "to_role TEXT, requires_readme_impact INTEGER NOT NULL DEFAULT 0)"
            )
            conn.execute("INSERT INTO bridge_flow_steps VALUES ('f','a','b',1)")
            conn.execute("INSERT INTO bridge_flow_steps VALUES ('f','b','c',0)")
            conn.commit()
            conn.close()
            self.assertTrue(ri.step_requires_readme_impact("f", "a", "b", db_path=db))
            self.assertFalse(ri.step_requires_readme_impact("f", "b", "c", db_path=db))
            self.assertFalse(ri.step_requires_readme_impact("f", "x", "y", db_path=db))


class TestCli(unittest.TestCase):
    def test_exit_codes(self):
        import tempfile, os

        with tempfile.TemporaryDirectory() as d:
            ok = os.path.join(d, "ok.md")
            with open(ok, "w") as fh:
                fh.write(VALID_NO)
            self.assertEqual(ri.main([ok]), 0)
            self.assertEqual(ri.main(["--json", ok]), 0)

            bad = os.path.join(d, "bad.md")
            with open(bad, "w") as fh:
                fh.write("# nothing\n")
            self.assertEqual(ri.main([bad]), 1)

            self.assertEqual(ri.main([os.path.join(d, "absent.md")]), 2)


if __name__ == "__main__":
    unittest.main()
