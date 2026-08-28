"""Tests for scripts/validate_readme.py — the deterministic README validator.

Each test states which governance rule from 31_README_STANDARD.md it pins.
Codes are asserted, not messages: the codes are the stable contract.
"""

import importlib.util
import json
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "validate_readme",
    Path(__file__).resolve().parent.parent / "scripts" / "validate_readme.py",
)
vr = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(vr)


def compliant_readme() -> str:
    return """# demo-project

A short summary of what the project is.

## Overview

What it provides.

## Architecture

How it hangs together.

## Requirements

- Python 3.10+

## Installation

### Install manually

```bash
git clone <repository-url>
cd <repository>
python3 -m venv .venv
.venv/bin/pip install -e .
```

### Install using an Agent

Give your coding agent access to this repository and ask it to install the
project on the current machine.

### Verify installation

```bash
demo --help
```

## Configuration

Copy `config.example.yaml` and set `DEMO_API_KEY` in the environment.

## Running

```bash
demo serve
```

## Testing

```bash
python3 -m pytest tests -q
```
"""


def codes(result, kind):
    return [item["code"] for item in result[kind]]


class TestCompliantReadme(unittest.TestCase):
    def test_a_compliant_readme_passes_with_all_sections_true(self):
        result = vr.validate(compliant_readme())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["errors"], [])
        self.assertTrue(all(result["sections"].values()), result["sections"])

    def test_env_var_names_are_not_flagged_as_secrets(self):
        # DEMO_API_KEY appears by NAME in the compliant README; a name is
        # not a value and must never trip the secret check.
        result = vr.validate(compliant_readme())
        self.assertNotIn("README_SECRET_MATERIAL", codes(result, "errors"))


class TestH1(unittest.TestCase):
    def test_missing_h1_is_an_error(self):
        text = compliant_readme().replace("# demo-project\n", "")
        result = vr.validate(text)
        self.assertIn("README_H1_MISSING", codes(result, "errors"))

    def test_multiple_h1_is_an_error(self):
        text = compliant_readme() + "\n# second-title\n"
        result = vr.validate(text)
        self.assertIn("README_H1_MULTIPLE", codes(result, "errors"))


class TestMandatorySections(unittest.TestCase):
    def test_each_missing_core_section_yields_its_own_code(self):
        for name in ["Requirements", "Configuration", "Running", "Testing"]:
            text = compliant_readme().replace(f"## {name}\n", f"## Renamed {name}\n")
            result = vr.validate(text)
            self.assertIn(
                f"README_{name.upper()}_MISSING", codes(result, "errors"), name
            )

    def test_missing_installation_is_an_error(self):
        text = compliant_readme().replace("## Installation\n", "## Getting it\n")
        result = vr.validate(text)
        self.assertIn("README_INSTALLATION_MISSING", codes(result, "errors"))

    def test_missing_overview_and_architecture_are_warnings_not_errors(self):
        text = (
            compliant_readme()
            .replace("## Overview\n", "## About\n")
            .replace("## Architecture\n", "## Design\n")
        )
        result = vr.validate(text)
        self.assertIn("README_OVERVIEW_MISSING", codes(result, "warnings"))
        self.assertIn("README_ARCHITECTURE_MISSING", codes(result, "warnings"))
        self.assertEqual(result["status"], "pass")


class TestInstallationSubsections(unittest.TestCase):
    def test_missing_agent_install_is_an_error(self):
        text = compliant_readme().replace("### Install using an Agent\n", "")
        result = vr.validate(text)
        self.assertIn("README_AGENT_INSTALL_MISSING", codes(result, "errors"))

    def test_missing_manual_install_is_an_error(self):
        text = compliant_readme().replace("### Install manually\n", "")
        result = vr.validate(text)
        self.assertIn("README_INSTALL_MANUAL_MISSING", codes(result, "errors"))

    def test_missing_verification_is_an_error(self):
        text = compliant_readme().replace("### Verify installation\n", "")
        result = vr.validate(text)
        self.assertIn("README_INSTALL_VERIFY_MISSING", codes(result, "errors"))

    def test_subsection_outside_installation_does_not_count(self):
        # Move the agent subsection under Running: Installation loses it.
        text = compliant_readme().replace("### Install using an Agent\n", "")
        text = text.replace("## Running\n", "## Running\n\n### Install using an Agent\n")
        result = vr.validate(text)
        self.assertIn("README_AGENT_INSTALL_MISSING", codes(result, "errors"))


class TestOrderingAndDuplicates(unittest.TestCase):
    def test_core_order_violation_is_an_error(self):
        text = compliant_readme()
        testing = text[text.index("## Testing") :]
        text = testing + "\n" + text[: text.index("## Testing")]
        result = vr.validate(text)
        self.assertIn("README_SECTION_ORDER", codes(result, "errors"))

    def test_duplicate_mandatory_heading_is_an_error(self):
        text = compliant_readme() + "\n## Installation\n\nAgain.\n"
        result = vr.validate(text)
        self.assertIn("README_DUPLICATE_HEADING", codes(result, "errors"))


class TestAdvisoryFindings(unittest.TestCase):
    def test_alias_warns_only_when_canonical_is_missing(self):
        with_alias_and_canonical = compliant_readme() + "\n## Setup\n\nExtra.\n"
        result = vr.validate(with_alias_and_canonical)
        self.assertNotIn("README_ALIAS_HEADING", codes(result, "warnings"))

        without_canonical = compliant_readme().replace(
            "## Installation\n", "## Setup\n"
        )
        result = vr.validate(without_canonical)
        self.assertIn("README_ALIAS_HEADING", codes(result, "warnings"))

    def test_personal_path_is_a_warning_not_an_error(self):
        text = compliant_readme() + "\nData lives in /home/alice/data/.\n"
        result = vr.validate(text)
        self.assertIn("README_PERSONAL_PATH", codes(result, "warnings"))
        self.assertEqual(result["status"], "pass")

    def test_symbolic_home_placeholder_is_not_flagged(self):
        text = compliant_readme() + "\nUse /home/<username>/ as an example root.\n"
        result = vr.validate(text)
        self.assertNotIn("README_PERSONAL_PATH", codes(result, "warnings"))


class TestSecrets(unittest.TestCase):
    def test_literal_secret_assignment_fails(self):
        text = compliant_readme() + "\nAPI_KEY=abcd1234efgh5678ijkl\n"
        result = vr.validate(text)
        self.assertIn("README_SECRET_MATERIAL", codes(result, "errors"))

    def test_bearer_token_fails(self):
        text = compliant_readme() + "\nAuthorization: Bearer abcdefghijklmnopqrstu123\n"
        result = vr.validate(text)
        self.assertIn("README_SECRET_MATERIAL", codes(result, "errors"))

    def test_placeholder_values_do_not_fail(self):
        text = compliant_readme() + "\nAPI_KEY=your-api-key-goes-here-example\n"
        result = vr.validate(text)
        self.assertNotIn("README_SECRET_MATERIAL", codes(result, "errors"))


class TestFencedBlocks(unittest.TestCase):
    def test_headings_inside_code_fences_are_ignored(self):
        # A markdown example showing '## Installation' inside a fence must not
        # count as a duplicate — nor rescue a missing section.
        text = compliant_readme() + "\n```text\n## Installation\n# fake-h1\n```\n"
        result = vr.validate(text)
        self.assertNotIn("README_DUPLICATE_HEADING", codes(result, "errors"))
        self.assertNotIn("README_H1_MULTIPLE", codes(result, "errors"))


class TestJsonContractAndExitCodes(unittest.TestCase):
    def test_sections_map_carries_the_contract_keys(self):
        result = vr.validate(compliant_readme())
        self.assertEqual(
            sorted(result["sections"].keys()),
            sorted(
                [
                    "overview",
                    "architecture",
                    "requirements",
                    "installation",
                    "install_manually",
                    "agent_installation",
                    "installation_verification",
                    "configuration",
                    "running",
                    "testing",
                ]
            ),
        )

    def test_result_is_json_serializable(self):
        json.dumps(vr.validate(compliant_readme()))

    def test_main_exit_codes(self):
        import tempfile, os

        with tempfile.TemporaryDirectory() as d:
            good = os.path.join(d, "README.md")
            with open(good, "w") as fh:
                fh.write(compliant_readme())
            self.assertEqual(vr.main([good]), 0)
            self.assertEqual(vr.main(["--json", good]), 0)

            bad = os.path.join(d, "BAD.md")
            with open(bad, "w") as fh:
                fh.write("no heading at all\n")
            self.assertEqual(vr.main([bad]), 1)

            self.assertEqual(vr.main([os.path.join(d, "absent.md")]), 2)


if __name__ == "__main__":
    unittest.main()
