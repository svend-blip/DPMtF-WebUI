"""Tests for artifact root prompt changes — Run 015, GOAL §6.

These tests validate:
  Convention templates: artifact_root replaces flow_key in paths  (TG1–TG3)
  Dispatch mechanism:    artifact_root substitution at every site (TG4–TG6)
  Probe validation:      shared-root and fallback directions      (TG7–TG8)
  Test suite gate:       the suite runs green                     (TG9)
  Governance:            signal-verb rules in role files          (TG10–TG14)

Two of these (TG3, TG6) are regression fences — green before the
Run and required to stay green. They are not evidence of work; they
prevent the easy wrong fix (a blind search-and-replace that also
destroys the --flow arguments).

Rehearsal shell: /bin/sh (dash).  Commands match check_testgoals.py
subprocess.run(shell=True) exactly.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_OS = os.name


def _run(cmd, **kw):
    """Run a command under /bin/sh — same shell the harness will use.

    Returns the numeric exit code (0 / 1 / 2 …).
    """
    return subprocess.run(
        cmd,
        shell=True,
        executable="/bin/sh",
        capture_output=True,
        cwd=str(_ROOT),
        env={**os.environ, "PYTHONPATH": str(_ROOT)},
        **kw,
    )


# ────────────────────────────────────────────
# TG1 — No convention template uses the flow key as a path root
# TG2 — All 13 path occurrences now use the artifact root
# TG3 — FENCE: handoff and json_output keep their --flow arguments
# ────────────────────────────────────────────


class TestConventionTemplates(unittest.TestCase):
    """TG1 / TG2 / TG3: convention templates in the database."""

    def _count(self, template, needle):
        return template.count(needle)

    # ── TG1 ──────────────────────────────────────────────────

    def test_tg1_no_convention_template_uses_flow_key_as_path_root(self):
        """{bridge_dir}/{flow_key}/ must not appear in any rule template."""
        result = _run(
            'sqlite3 databases/dpmtf.db '
            '"SELECT content_template FROM bridge_convention_rules;" '
            "| grep -c '{bridge_dir}/{flow_key}/'"
        )
        # grep -c exits 1 when the count is 0 — the very state this test
        # wants. Only rc > 1 is a real grep/sqlite error.
        self.assertLessEqual(result.returncode, 1,
                             f"grep failed (rc={result.returncode}): "
                             f"{result.stderr.decode()}")
        self.assertEqual(result.stdout.strip(), b"0",
                         "TG1: convention templates still use {flow_key} "
                         "as a path root")

    # ── TG2 ──────────────────────────────────────────────────

    def test_tg2_all_path_occurrences_use_artifact_root(self):
        """Exactly 13 occurrences of {bridge_dir}/{artifact_root}/."""
        result = _run(
            'sqlite3 databases/dpmtf.db '
            '"SELECT content_template FROM bridge_convention_rules;" '
            "| grep -c '{bridge_dir}/{artifact_root}/'"
        )
        self.assertEqual(result.returncode, 0,
                         f"grep failed (rc={result.returncode}): "
                         f"{result.stderr.decode()}")
        self.assertEqual(result.stdout.strip(), b"13",
                         "TG2: expected 13 path occurrences, "
                         f"got {result.stdout.strip().decode()}")

    # ── TG3 ──────────────────────────────────────────────────

    def test_tg3_fence_handoff_and_json_output_keep_flow_argument(self):
        """Both handoff and json_output must still carry --flow {flow_key}."""
        result = _run(
            "sqlite3 databases/dpmtf.db "
            "\"SELECT content_template FROM bridge_convention_rules "
            "WHERE rule_key IN ('handoff', 'json_output');\" | "
            "grep -c -- '--flow {flow_key}'"
        )
        self.assertEqual(result.returncode, 0,
                         f"grep failed (rc={result.returncode}): "
                         f"{result.stderr.decode()}")
        self.assertEqual(result.stdout.strip(), b"2",
                         "TG3/FENCE: handoff or json_output lost --flow "
                         f"(got {result.stdout.strip().decode()})")


# ────────────────────────────────────────────────────────────
# TG4 — dispatch substitutes artifact_root at every site
# TG5 — dispatch resolves through the canonical resolver
# TG6 — FENCE: no inline reimplementation of the fallback
# ────────────────────────────────────────────────────────────


class TestDispatchMechanism(unittest.TestCase):
    """TG4 / TG5 / TG6: dispatch.py artifact_root substitution."""

    def _count_grep(self, needle, file="scripts/bridgeV002/dispatch.py"):
        """Return the count of lines matching *needle* in dispatch.py."""
        cmd = f"grep -c '{needle}' {file}"
        result = _run(cmd)
        if result.returncode == 0:
            return int(result.stdout.strip())
        return 0

    # ── TG4 ──────────────────────────────────────────────────

    def test_tg4_dispatch_substitutes_artifact_root_at_six_sites(self):
        """Six prompt_text.replace('{artifact_root}' ...) calls."""
        count = self._count_grep(
            'prompt_text.replace("{artifact_root}"')
        self.assertEqual(count, 6,
                         "TG4: expected 6 artifact_root substitution sites, "
                         f"got {count}")

    # ── TG5 ──────────────────────────────────────────────────

    def test_tg5_dispatch_resolves_through_canonical_resolver(self):
        """dispatch.py imports and calls get_effective_artifact_root."""
        count = self._count_grep("get_effective_artifact_root")
        self.assertGreaterEqual(count, 1,
                                "TG5: dispatch.py must call the canonical "
                                "resolver at least once")

    # ── TG6 ──────────────────────────────────────────────────

    def test_tg6_fence_no_inline_fallback_reimplementation(self):
        """No inline 'artifact_root or flow_key' pattern."""
        # Use a simple word-level grep — the regex pattern is POSIX-safe.
        cmd = (
            "grep -cE 'artifact_root[^)]*or[^)]*flow_key' "
            "scripts/bridgeV002/dispatch.py"
        )
        result = _run(cmd)
        if result.returncode == 0:
            count = int(result.stdout.strip())
        else:
            count = 0
        self.assertEqual(count, 0,
                         "TG6/FENCE: found inline artifact_root-or-flow_key "
                         f"fallback ({count} occurrence(s)); "
                         "must use get_effective_artifact_root")


# ────────────────────────────────────────────────────────────
# TG7 — A shared-root flow renders the shared root
# TG8 — A NULL-artifact-root flow still renders its flow key
# ────────────────────────────────────────────────────────────


class TestProbe(unittest.TestCase):
    """TG7 / TG8: probe_artifact_root.py validates both directions."""

    # ── TG7 ──────────────────────────────────────────────────

    def test_tg7_shared_root_flow_renders_shared_root(self):
        """Probe prints ELOOP_ROOT_OK for the 1000 flow."""
        result = _run("python3 scripts/probe_artifact_root.py")
        self.assertEqual(result.returncode, 0,
                         f"Probe exited {result.returncode}: "
                         f"{result.stderr.decode().rstrip()}")
        self.assertIn(b"ELOOP_ROOT_OK", result.stdout,
                      "TG7: probe did not print ELOOP_ROOT_OK")

    # ── TG8 ──────────────────────────────────────────────────

    def test_tg8_null_root_flow_renders_flow_key(self):
        """Probe prints FALLBACK_OK for a NULL-artifact-root flow."""
        result = _run("python3 scripts/probe_artifact_root.py")
        self.assertEqual(result.returncode, 0,
                         f"Probe exited {result.returncode}: "
                         f"{result.stderr.decode().rstrip()}")
        self.assertIn(b"FALLBACK_OK", result.stdout,
                      "TG8: probe did not print FALLBACK_OK")


# ────────────────────────────────────────────────────────────
# TG10 — REVIEW.md names --signal-send
# TG11 — FENCE: REVIEW.md still names --signal-complete
# TG12 — All three role files name auto_dispatch
# TG13 — All three role files name BOTH verbs
# TG14 — REVIEW.md names the manual-dispatch case
# ────────────────────────────────────────────────────────────


class TestGovernance(unittest.TestCase):
    """TG10–TG14: signal-verb governance in role files."""

    _DIR = Path("docs/governance-templates-v2")
    _FILES = ["REVIEW", "IMPLEMENTOR", "EXECUTION_DECOMPOSER"]

    # ── TG10 ─────────────────────────────────────────────────

    def test_tg10_review_names_signal_send(self):
        """REVIEW.md must mention --signal-send (the manual-dispatch verb)."""
        path = self._DIR / "REVIEW.md"
        text = path.read_text()
        self.assertIn("--signal-send", text,
                      "TG10: REVIEW.md must mention --signal-send")

    # ── TG11 ─────────────────────────────────────────────────

    def test_tg11_fence_review_still_names_signal_complete(self):
        """REVIEW.md must still mention --signal-complete (for other flows)."""
        path = self._DIR / "REVIEW.md"
        text = path.read_text()
        self.assertIn("--signal-complete", text,
                      "TG11/FENCE: REVIEW.md must still mention "
                      "--signal-complete")

    # ── TG12 ─────────────────────────────────────────────────

    def test_tg12_all_role_files_name_auto_dispatch(self):
        """All three role files must reference auto_dispatch."""
        found = 0
        for name in self._FILES:
            if (self._DIR / f"{name}.md").read_text().count(
                    "auto_dispatch") > 0:
                found += 1
        self.assertEqual(found, 3,
                         "TG12: expected all 3 role files to name "
                         "auto_dispatch, got %d" % found)

    # ── TG13 ─────────────────────────────────────────────────

    def test_tg13_all_role_files_name_both_verbs(self):
        """Every role file must mention both --signal-send and --signal-complete."""
        found = 0
        for name in self._FILES:
            text = (self._DIR / f"{name}.md").read_text()
            if "--signal-send" in text and "--signal-complete" in text:
                found += 1
        self.assertEqual(found, 3,
                         "TG13: all 3 role files must name both verbs, "
                         "got %d" % found)

    # ── TG14 ─────────────────────────────────────────────────

    def test_tg14_review_names_manual_dispatch_case(self):
        """REVIEW.md must mention the manual-dispatch case by name."""
        path = self._DIR / "REVIEW.md"
        text = path.read_text()
        self.assertIn("manual-dispatch", text,
                      "TG14: REVIEW.md must mention "
                      "'manual-dispatch'")


# ────────────────────────────────────────────────────────────
# Helpers for the Implementer — before/after test diff
# ────────────────────────────────────────────────────────────


class TestHelpers(unittest.TestCase):
    """Utility helpers the Implementer uses for the before/after capture.

    Not a testgoal itself, but useful for running the §7 capture command:
        python3 -m pytest -q -p no:cacheprovider 2>&1 | grep "^FAILED" | sort
    """

    def test_run_command_simple(self):
        """Verify _run works as expected."""
        result = _run("echo hello")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), b"hello")


if __name__ == "__main__":
    unittest.main()
