"""Tests for the evidence gate's claim extraction.

Every case here is a real deliverable shape from llama_SG runs 002-005. The
gate rejected three honest ones in a single day before the extraction rule
was narrowed, so the false-positive cases matter as much as the fabrication
case: a gate that punishes a role for doing what the contract asked is worse
than no gate, because it also teaches the role to write less.
"""

import importlib.util
import unittest
from pathlib import Path

_GATE = (Path(__file__).resolve().parent.parent
         / "scripts" / "bridgeV002" / "gate-deliverable-evidence.py")
_spec = importlib.util.spec_from_file_location("gate_evidence", _GATE)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


class ClaimExtraction(unittest.TestCase):

    def test_files_changed_section_yields_claims(self):
        """The one place a deliverable says "these are mine"."""
        text = """## Implementation Report

### Files Changed
1. **model-allocator/README.md** — added the SETUP.md reference
"""
        self.assertEqual(gate.claimed_paths(text), ["model-allocator/README.md"])

    def test_only_first_path_on_a_line_is_the_claim(self):
        """A row names the file changed, then describes the change.

        "README.md | Modified — added SETUP.md reference" changes one file
        and mentions another. Treating both as claims rejected a report that
        said, in the same table, "No other files were modified".
        """
        text = """### Files Changed
| `/home/svend/model-allocator/README.md` | Modified — added SETUP.md reference |
"""
        self.assertEqual(gate.claimed_paths(text),
                         ["/home/svend/model-allocator/README.md"])

    def test_verification_commands_are_not_claims(self):
        """A verdict's Test Results section lists what it ran.

        The contract requires the reviewer to run these. Reading the files
        named inside the commands as changes accused it of modifying app.py
        and every file node --check had validated.
        """
        text = """## Test Results

- `python3 -m py_compile app.py config.py` -> EXIT: 0
- `node --check static/js/*.js` -> EXIT: 0
"""
        self.assertEqual(gate.claimed_paths(text), [])

    def test_file_references_in_prose_are_not_claims(self):
        """Naming where a variable is read is documentation, not a change."""
        text = """## Findings

- `DPMTF_MODEL_START_TIMEOUT` is read by `scripts/job_queue/model_lease.py`
- `DPMTF_VRAM_RELEASE_TIMEOUT` is read by `scripts/bridgeV002/dispatch.py`
"""
        self.assertEqual(gate.claimed_paths(text), [])

    def test_fenced_output_is_evidence_not_claims(self):
        """Pasted git status is what the gate asked for, not a confession."""
        text = """### Files Changed
Based on actual git status --short:
```
 M config.py
 M scripts/bridgeV002/dispatch.py
```
"""
        self.assertEqual(gate.claimed_paths(text), [])

    def test_fabricated_report_still_yields_its_claims(self):
        """The case the gate exists for — run 002's handoff 005."""
        text = """## Implementation Report

### Files Changed

1. **model-allocator/README.md**
   - Added reference to DPMtF-WebUI SETUP.md
2. **DPMtF-WebUI/scripts/bridgeV002/pre-dispatch-import.py**
   - Replaced hardcoded path in argparse help string
"""
        self.assertEqual(
            gate.claimed_paths(text),
            ["model-allocator/README.md",
             "DPMtF-WebUI/scripts/bridgeV002/pre-dispatch-import.py"])


class PathResolution(unittest.TestCase):

    def setUp(self):
        self.roots = ["/home/svend/DPMtF-WebUI", "/home/svend/model-allocator"]

    def test_repo_name_prefix_selects_that_repo(self):
        """Both repos hold a README.md; the prefix says which one."""
        root, rel = gate.locate("model-allocator/README.md", self.roots)
        self.assertEqual(root, "/home/svend/model-allocator")
        self.assertEqual(rel, "README.md")

    def test_scope_fence_breaks_ties_for_a_bare_name(self):
        """A bare name means the file the handoff asked about.

        Resolving to whichever repo sorts first turned the gate's own
        ambiguity into an accusation of scope breach.
        """
        allowed = {"/home/svend/model-allocator/README.md"}
        root, _ = gate.locate("README.md", self.roots, prefer=allowed)
        self.assertEqual(root, "/home/svend/model-allocator")

    def test_unknown_prefix_does_not_reach_into_another_project(self):
        """`new-webui-skeleton/static/js/app.js` is not some other repo's app.js.

        Stripping an unrecognised leading directory and searching every root
        again resolved this to an unrelated project and accused a verdict of
        changing a file in a repository the flow has never touched.
        """
        root, rel = gate.locate(
            "new-webui-skeleton/static/js/app.js", self.roots)
        self.assertIsNone(root)
        self.assertIsNone(rel)


if __name__ == "__main__":
    unittest.main()


class DenialsAreNotClaims(unittest.TestCase):
    """Saying what was NOT changed is what the contract asks for.

    03_IMPLEMENTOR and every flow's role file require it: "doing nothing is a
    legitimate result — say so plainly". Reading such a line as a claim
    punishes the behaviour the contract requires, and did: preferred_cloud
    handoff 002 was rejected for writing that GOAL.md was untouched, which was
    both true and the point.
    """

    def test_untouched_line_is_not_a_claim(self):
        text = """## Files changed

The only thing this handoff created is `docs/phase0-findings.md`.
`GOAL.md`, `README.md`, `pyproject.toml` are untouched.
"""
        self.assertEqual(gate.claimed_paths(text), ["docs/phase0-findings.md"])

    def test_read_but_never_written_is_not_a_claim(self):
        text = """## Files changed

* `/home/svend/DPMtF-WebUI/`, `/home/svend/model-allocator/` were read but
  never written.
"""
        self.assertEqual(gate.claimed_paths(text), [])

    def test_the_real_claim_beside_a_denial_still_counts(self):
        """A denial must not swallow the section it sits in."""
        text = """## Files changed

1. **src/dpmtf_lightworker/models.py** — added the envelope
2. `tests/` is unchanged
"""
        self.assertEqual(gate.claimed_paths(text), ["src/dpmtf_lightworker/models.py"])

    def test_negations_covered(self):
        for phrase in ("is untouched", "was not modified", "were not changed",
                       "is unchanged", "never written", "no changes to"):
            with self.subTest(phrase=phrase):
                text = f"## Files changed\n\n`GOAL.md` {phrase}.\n"
                self.assertEqual(gate.claimed_paths(text), [])


class ScopeFenceExtraction(unittest.TestCase):
    """The fence must come from the real block, not from a prose mention.

    preferred_cloud run 004: handoff 005 wrote "the model-allocator repo will
    be tempting -- see `<scope>`" inside its governance block, 170 lines above
    the actual fence. The old regex took the first `<scope>` anywhere in the
    file, so it captured from that sentence and enforced the handoff's Step 1
    *read* list as if it were the write list. Three files the fence expressly
    allowed were rejected as out of scope, and the implementer could not have
    fixed it.

    Paths here are real files in a real repo because `locate()` resolves
    against the filesystem.
    """

    ROOT = "/home/svend/DPMtF-LightWorker"
    WRITTEN = "src/dpmtf_lightworker/allocator.py"
    READ_ONLY = "src/dpmtf_lightworker/father_client.py"

    def _fence(self, text):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(text)
            path = fh.name
        return gate.scope_allowed(path, [self.ROOT])

    def test_prose_mention_does_not_win_over_the_real_block(self):
        text = (
            "<governance>\n"
            "The other repository will be tempting -- see `<scope>`.\n"
            "</governance>\n"
            "\n"
            "<task>\n"
            f"Read first: `{self.READ_ONLY}`\n"
            "</task>\n"
            "\n"
            "<scope>\n"
            f"- `{self.WRITTEN}`\n"
            "</scope>\n"
        )
        allowed = self._fence(text)
        self.assertIn(f"{self.ROOT}/{self.WRITTEN}", allowed)
        self.assertNotIn(f"{self.ROOT}/{self.READ_ONLY}", allowed)

    def test_an_ordinary_handoff_still_resolves(self):
        text = f"<scope>\n- `{self.WRITTEN}`\n</scope>\n"
        self.assertIn(f"{self.ROOT}/{self.WRITTEN}", self._fence(text))

    def test_no_fence_is_none_not_an_empty_set(self):
        """An unreadable fence must not be mistaken for 'nothing is allowed'."""
        self.assertIsNone(self._fence("no fence here at all\n"))

    def test_indented_tags_are_still_a_fence(self):
        text = f"  <scope>\n  - `{self.WRITTEN}`\n  </scope>\n"
        self.assertIn(f"{self.ROOT}/{self.WRITTEN}", self._fence(text))
