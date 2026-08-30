"""Tests for scripts/testing/planner.py — using MockPolicy, no real policy imports."""

from __future__ import annotations

import unittest
from scripts.testing.planner import plan_tests, _scope_index, _match_glob


class MockPolicy:
    def __init__(
        self,
        components=None,
        test_mappings=None,
        component_dependencies=None,
        mandatory_smoke_tests=None,
        high_fanout_files=None,
        full_regression_triggers=None,
        policy_hash="test-hash",
        is_empty_val=False,
    ):
        self.components = components or {}
        self.test_mappings = test_mappings or {}
        self.component_dependencies = component_dependencies or {}
        self.mandatory_smoke_tests = mandatory_smoke_tests or []
        self.high_fanout_files = high_fanout_files or []
        self.full_regression_triggers = full_regression_triggers or []
        self.policy_hash = policy_hash
        self.is_empty = is_empty_val

    def component_for(self, path):
        """Return the component name whose source globs match path, or None."""
        import fnmatch
        for comp, globs in self.components.items():
            for glob in globs:
                if fnmatch.fnmatch(path, glob):
                    return comp
        return None


class MockClosure:
    def __init__(self, is_safe=True):
        self.is_safe = is_safe


class TestPlanner(unittest.TestCase):
    """Test cases for the planner test-plan engine."""

    def plan(self, repo_root, policy, changes, requested_scope=None, symbols=None, closure=None):
        return plan_tests(repo_root, policy, changes, requested_scope, symbols, closure)

    # ---- Contract-bound test names (TG7) ----

    def test_an_empty_policy_forces_full_regression(self):
        """An empty policy must escalate to full regression."""
        mp = MockPolicy(components={}, test_mappings={},
                        component_dependencies={}, mandatory_smoke_tests=[],
                        high_fanout_files=[], full_regression_triggers=[],
                        policy_hash='')
        r = self.plan('/repo', mp, {'a.py': 'modified'})
        self.assertEqual(r.resolved_scope, 'full',
                         f"Expected 'full', got '{r.resolved_scope}'")
        self.assertTrue(r.is_exhaustive,
                        f"is_exhaustive should be True for full scope")
        self.assertTrue(len(r.escalation_reason) > 0,
                        "escalation_reason must be non-empty")

    def test_a_requested_scope_can_never_narrow_the_resolution(self):
        """requested_scope hint cannot narrow the deterministic resolution."""
        mp = MockPolicy(
            components={'x': ['x/*.py']},
            test_mappings={'x': ['tests/test_x.py']},
            component_dependencies={},
            mandatory_smoke_tests=[],
            high_fanout_files=[],
            full_regression_triggers=[],
            policy_hash='',
        )
        r = self.plan('/repo', mp, {'x/a.py': 'modified'}, requested_scope='file')
        self.assertEqual(r.resolved_scope, 'component',
                         f"requested_scope='file' should not narrow; got '{r.resolved_scope}'")

    def test_adding_a_changed_file_never_lowers_the_resolved_scope(self):
        """Monotonicity: adding a changed file never lowers the resolved scope."""
        from scripts.testing.planner import _scope_index as si

        # Combo 1: classified path -> broad escalation via high_fanout
        mp1 = MockPolicy(
            components={'x': ['x/*.py']},
            test_mappings={'x': ['tests/test_x.py']},
            component_dependencies={},
            mandatory_smoke_tests=[],
            high_fanout_files=['broad/*.py'],
            full_regression_triggers=[],
            policy_hash='',
        )
        subset1 = {'x/a.py': 'modified'}
        superset1 = {'x/a.py': 'modified', 'broad/z.py': 'modified'}
        r_sub1 = self.plan('/repo', mp1, subset1)
        r_super1 = self.plan('/repo', mp1, superset1)
        self.assertGreaterEqual(si(r_super1.resolved_scope),
                                si(r_sub1.resolved_scope))

        # Combo 2: classified path -> full escalation via regression trigger
        mp2 = MockPolicy(
            components={'x': ['x/*.py']},
            test_mappings={'x': ['tests/test_x.py']},
            component_dependencies={},
            mandatory_smoke_tests=[],
            high_fanout_files=[],
            full_regression_triggers=['**/deploy/**'],
            policy_hash='',
        )
        subset2 = {'x/a.py': 'modified'}
        superset2 = {'x/a.py': 'modified', 'deploy/z.sh': 'modified'}
        r_sub2 = self.plan('/repo', mp2, subset2)
        r_super2 = self.plan('/repo', mp2, superset2)
        self.assertGreaterEqual(si(r_super2.resolved_scope),
                                si(r_sub2.resolved_scope))

        # Combo 3: empty -> component (nothing moves leftward)
        mp3 = MockPolicy(
            components={'x': ['x/*.py']},
            test_mappings={'x': ['tests/test_x.py']},
            component_dependencies={},
            mandatory_smoke_tests=[],
            high_fanout_files=[],
            full_regression_triggers=[],
            policy_hash='',
        )
        subset3 = {}
        superset3 = {'x/a.py': 'modified'}
        r_sub3 = self.plan('/repo', mp3, subset3)
        r_super3 = self.plan('/repo', mp3, superset3)
        self.assertGreaterEqual(si(r_super3.resolved_scope),
                                si(r_sub3.resolved_scope))

        # Combo 4: two classified -> broad via unclassified addition
        mp4 = MockPolicy(
            components={'x': ['x/*.py']},
            test_mappings={'x': ['tests/test_x.py']},
            component_dependencies={},
            mandatory_smoke_tests=[],
            high_fanout_files=[],
            full_regression_triggers=[],
            policy_hash='',
        )
        subset4 = {'x/a.py': 'modified', 'x/b.py': 'modified'}
        superset4 = {'x/a.py': 'modified', 'x/b.py': 'modified', 'y/c.py': 'modified'}
        r_sub4 = self.plan('/repo', mp4, subset4)
        r_super4 = self.plan('/repo', mp4, superset4)
        self.assertGreaterEqual(si(r_super4.resolved_scope),
                                si(r_sub4.resolved_scope))

    def test_smoke_tests_are_present_at_every_scope(self):
        """Smoke tests are unioned into every plan at every scope."""
        mp_comp = MockPolicy(
            components={'x': ['x/*.py']},
            test_mappings={'x': ['tests/test_x.py']},
            component_dependencies={},
            mandatory_smoke_tests=['tests/smoke.py'],
            high_fanout_files=[],
            full_regression_triggers=[],
            policy_hash='',
        )
        r_comp = self.plan('/repo', mp_comp, {'x/a.py': 'modified'})
        self.assertEqual(r_comp.resolved_scope, 'component')
        self.assertIn('tests/smoke.py', r_comp.selected_tests,
                      f"Smoke test missing at component scope: {r_comp.selected_tests}")

        mp_broad = MockPolicy(
            components={'x': ['x/*.py']},
            test_mappings={'x': ['tests/test_x.py']},
            component_dependencies={},
            mandatory_smoke_tests=['tests/smoke.py'],
            high_fanout_files=[],
            full_regression_triggers=[],
            policy_hash='',
        )
        r_broad = self.plan('/repo', mp_broad, {'unclassified/z.py': 'modified'})
        self.assertEqual(r_broad.resolved_scope, 'broad')
        self.assertIn('tests/smoke.py', r_broad.selected_tests,
                      f"Smoke test missing at broad scope: {r_broad.selected_tests}")

        mp_full = MockPolicy(
            components={'x': ['x/*.py'], 'd': ['deploy/**']},
            test_mappings={'x': ['tests/test_x.py'], 'd': ['tests/test_deploy.py']},
            component_dependencies={},
            mandatory_smoke_tests=['tests/smoke.py'],
            high_fanout_files=[],
            full_regression_triggers=['deploy/**'],
            policy_hash='',
        )
        r_full = self.plan('/repo', mp_full, {'deploy/z.sh': 'modified'})
        self.assertEqual(r_full.resolved_scope, 'full')
        self.assertIn('tests/smoke.py', r_full.selected_tests,
                      f"Smoke test missing at full scope: {r_full.selected_tests}")

    def test_the_planner_never_resolves_below_component_in_this_run(self):
        """Across every fixture, no resolution is ever symbol or file."""
        unreachable_scopes = {'symbol', 'file'}
        fixtures = [
            (MockPolicy(components={}, test_mappings={},
                        component_dependencies={}, mandatory_smoke_tests=[],
                        high_fanout_files=[], full_regression_triggers=[],
                        policy_hash=''),
             {'a.py': 'modified'}),
            (MockPolicy(components={'x': ['x/*.py']},
                        test_mappings={'x': ['tests/test_x.py']},
                        component_dependencies={}, mandatory_smoke_tests=[],
                        high_fanout_files=[], full_regression_triggers=[],
                        policy_hash=''),
             {'x/a.py': 'modified'}),
            (MockPolicy(components={'x': ['x/*.py']},
                        test_mappings={'x': ['tests/test_x.py']},
                        component_dependencies={}, mandatory_smoke_tests=[],
                        high_fanout_files=['broad/*.py'],
                        full_regression_triggers=[], policy_hash=''),
             {'broad/z.py': 'modified'}),
            (MockPolicy(components={}, test_mappings={},
                        component_dependencies={}, mandatory_smoke_tests=[],
                        high_fanout_files=[], full_regression_triggers=[],
                        policy_hash=''),
             {}),
        ]
        for mp, changes in fixtures:
            r = self.plan('/repo', mp, changes)
            self.assertNotIn(r.resolved_scope, unreachable_scopes,
                             f"Resolution {r.resolved_scope} is below component "
                             f"scope for fixture changes={changes}")

    # ---- Additional tests ----

    def test_high_fanout_file_with_dependents(self):
        """High fanout escalates to broad and includes dependent component tests."""
        mp = MockPolicy(
            components={'x': ['x/*.py'], 'y': ['y/*.py']},
            test_mappings={'x': ['tests/test_x.py'], 'y': ['tests/test_y.py']},
            component_dependencies={'y': ['x']},
            mandatory_smoke_tests=['tests/smoke.py'],
            high_fanout_files=['x/*.py'],
            full_regression_triggers=[],
            policy_hash='',
        )
        r = self.plan('/repo', mp, {'x/a.py': 'modified'})
        self.assertEqual(r.resolved_scope, 'broad',
                         f"Expected 'broad' for high fanout, got '{r.resolved_scope}'")
        self.assertIn('tests/test_y.py', r.selected_tests,
                      f"Dependent component test missing: {r.selected_tests}")
        self.assertIn('tests/test_x.py', r.selected_tests,
                      f"Source component test missing: {r.selected_tests}")
        self.assertIn('tests/smoke.py', r.selected_tests,
                      f"Smoke test missing: {r.selected_tests}")

    def test_broad_scope_includes_dependent_component_tests(self):
        """Unclassified change at broad scope includes all component tests."""
        mp = MockPolicy(
            components={'x': ['x/*.py'], 'y': ['y/*.py']},
            test_mappings={'x': ['tests/test_x.py'], 'y': ['tests/test_y.py']},
            component_dependencies={'y': ['x']},
            mandatory_smoke_tests=[],
            high_fanout_files=[],
            full_regression_triggers=[],
            policy_hash='',
        )
        r = self.plan('/repo', mp, {'z/c.py': 'modified'})
        self.assertEqual(r.resolved_scope, 'broad')
        self.assertIn('tests/test_x.py', r.selected_tests)
        self.assertIn('tests/test_y.py', r.selected_tests)

    def test_component_scope_selects_component_tests_and_reverse_deps(self):
        """Component scope selects tests for the component and its reverse deps."""
        mp = MockPolicy(
            components={'x': ['x/*.py'], 'y': ['y/*.py']},
            test_mappings={'x': ['tests/test_x.py'], 'y': ['tests/test_y.py']},
            component_dependencies={'y': ['x']},
            mandatory_smoke_tests=['tests/smoke.py'],
            high_fanout_files=[],
            full_regression_triggers=[],
            policy_hash='',
        )
        r = self.plan('/repo', mp, {'x/a.py': 'modified'})
        self.assertEqual(r.resolved_scope, 'component',
                         f"Expected 'component', got '{r.resolved_scope}'")
        self.assertIn('tests/test_x.py', r.selected_tests)
        self.assertIn('tests/test_y.py', r.selected_tests)
        self.assertIn('tests/smoke.py', r.selected_tests)

    def test_component_no_test_mapping_escalates_to_broad(self):
        """Component with no test mappings escalates to broad scope."""
        mp = MockPolicy(
            components={'x': ['x/*.py'], 'x_legacy': ['legacy/*.py']},
            test_mappings={'x': ['tests/test_x.py']},
            component_dependencies={},
            mandatory_smoke_tests=['tests/smoke.py'],
            high_fanout_files=[],
            full_regression_triggers=[],
            policy_hash='',
        )
        r = self.plan('/repo', mp, {'legacy/b.py': 'modified'})
        self.assertEqual(r.resolved_scope, 'broad',
                         f"Expected 'broad' for no test mapping, got '{r.resolved_scope}'")
        self.assertIn('tests/smoke.py', r.selected_tests)

    def test_full_regression_trigger_runs_full_suite(self):
        """Full regression trigger produces full scope with all tests."""
        mp = MockPolicy(
            components={'x': ['x/*.py']},
            test_mappings={'x': ['tests/test_x.py']},
            component_dependencies={},
            mandatory_smoke_tests=['tests/smoke.py'],
            high_fanout_files=[],
            full_regression_triggers=['**/deploy/**'],
            policy_hash='',
        )
        r = self.plan('/repo', mp, {'deploy/z.sh': 'modified'})
        self.assertEqual(r.resolved_scope, 'full')
        self.assertTrue(r.is_exhaustive)
        self.assertIn('tests/test_x.py', r.selected_tests)
        self.assertIn('tests/smoke.py', r.selected_tests)

    def test_glob_matching_asterisk(self):
        """Verify * matches within a single path component."""
        self.assertTrue(_match_glob('src/utils.py', 'src/*.py'))
        self.assertFalse(_match_glob('src/sub/utils.py', 'src/*.py'))
        self.assertFalse(_match_glob('deploy/run.sh', '*.sh'))
        self.assertTrue(_match_glob('a.py', '*.py'))
        self.assertFalse(_match_glob('dir/a.py', '*.py'))

    def test_glob_matching_double_star(self):
        """Verify ** matches zero or more directory components."""
        self.assertTrue(_match_glob('a/b/c/d', 'a/**/c/**'))
        self.assertTrue(_match_glob('a/b/c', 'a/**/c'))
        self.assertTrue(_match_glob('a/c', 'a/**/c'))
        self.assertTrue(_match_glob('deploy/script.sh', '**/deploy/**'))
        self.assertTrue(_match_glob('deploy', '**/deploy/**'))

    def test_empty_changes_resolves_to_symbol(self):
        """Empty changes produce symbol scope with no tests."""
        mp = MockPolicy(
            components={'x': ['x/*.py']},
            test_mappings={'x': ['tests/test_x.py']},
            component_dependencies={},
            mandatory_smoke_tests=['tests/smoke.py'],
            high_fanout_files=[],
            full_regression_triggers=[],
            policy_hash='',
        )
        r = self.plan('/repo', mp, {})
        self.assertEqual(r.resolved_scope, 'symbol',
                         f"Expected 'symbol' for empty changes, got '{r.resolved_scope}'")
        self.assertEqual(r.selected_tests, ['tests/smoke.py'])

    def test_unclassified_change_esculates_to_at_least_broad(self):
        """Unclassified change escalates to at least broad scope."""
        mp = MockPolicy(
            components={'x': ['x/*.py']},
            test_mappings={'x': ['tests/test_x.py']},
            component_dependencies={},
            mandatory_smoke_tests=[],
            high_fanout_files=[],
            full_regression_triggers=[],
            policy_hash='',
        )
        r = self.plan('/repo', mp, {'somewhere/else.py': 'modified'})
        self.assertEqual(r.resolved_scope, 'broad',
                         f"Expected 'broad' for unclassified change, "
                         f"got '{r.resolved_scope}'")

    def test_determinism(self):
        """Same inputs always produce the same plan_hash."""
        mp = MockPolicy(
            components={'x': ['x/*.py']},
            test_mappings={'x': ['tests/test_x.py']},
            component_dependencies={},
            mandatory_smoke_tests=[],
            high_fanout_files=[],
            full_regression_triggers=[],
            policy_hash='abc123',
        )
        r1 = self.plan('/repo', mp, {'x/a.py': 'modified'})
        r2 = self.plan('/repo', mp, {'x/a.py': 'modified'})
        self.assertEqual(r1.plan_hash, r2.plan_hash,
                          f"Non-deterministic: {r1.plan_hash} != {r2.plan_hash}")

    # ---- Additional tests for symbol/file narrowing (symbols+closure args) ----

    def test_symbol_scope_with_safe_closure_and_mapped_symbols(self):
        """Symbol-level scope: safe closure + mapped symbols + no triggers -> symbol."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_a.py").write_text("from x import foo\n")
            (tests_dir / "test_b.py").write_text("from x import bar\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\ndef bar(): pass\n")
            mp = MockPolicy(
                components={'x': ['x/*.py']},
                test_mappings={'x': ['tests/test_a.py', 'tests/test_b.py']},
                component_dependencies={},
                mandatory_smoke_tests=[],
                high_fanout_files=[],
                full_regression_triggers=[],
                policy_hash='',
            )
            r = self.plan(
                tmpdir, mp,
                {'x/a.py': 'modified'},
                symbols={'x/a.py': {'foo'}},
                closure=MockClosure(is_safe=True),
            )
            self.assertEqual(r.resolved_scope, 'symbol',
                              f"Expected 'symbol', got '{r.resolved_scope}'")

    def test_file_scope_when_condition_c_fails(self):
        """Symbol unmapped but closure safe + classified file -> file scope, not symbol."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_a.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            mp = MockPolicy(
                components={'x': ['x/*.py']},
                test_mappings={'x': ['tests/test_a.py']},
                component_dependencies={},
                mandatory_smoke_tests=[],
                high_fanout_files=[],
                full_regression_triggers=[],
                policy_hash='',
            )
            # 'nonexistent' not in symbol_to_tests -> condition (c) fails -> file scope
            r = self.plan(
                tmpdir, mp,
                {'x.py': 'modified'},
                symbols={'x.py': {'nonexistent_symbol'}},
                closure=MockClosure(is_safe=True),
            )
            self.assertEqual(r.resolved_scope, 'file',
                              f"Expected 'file', got '{r.resolved_scope}'")

    def test_symbol_resolution_with_safe_closure_unmapped_symbol_escalates(self):
        """Symbol resolution with safe closure and unmapped symbol -> scope escalates above symbol."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_a.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            mp = MockPolicy(
                components={'x': ['x/*.py']},
                test_mappings={'x': ['tests/test_a.py']},
                component_dependencies={},
                mandatory_smoke_tests=['tests/smoke.py'],
                high_fanout_files=[],
                full_regression_triggers=[],
                policy_hash='',
            )
            r = self.plan(
                tmpdir, mp,
                {'x.py': 'modified'},
                symbols={'x.py': {'nonexistent'}},
                closure=MockClosure(is_safe=True),
            )
            # Should NOT be symbol scope since 'nonexistent' is unmapped
            self.assertNotEqual(r.resolved_scope, 'symbol')
            # Should have smoke tests
            self.assertIn('tests/smoke.py', r.selected_tests)

    def test_file_resolution_with_no_symbol_data_but_classified_file(self):
        """File resolution with no symbol data but classified file -> file scope."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_a.py").write_text("import x\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            mp = MockPolicy(
                components={'x': ['x/*.py']},
                test_mappings={'x': ['tests/test_a.py']},
                component_dependencies={},
                mandatory_smoke_tests=[],
                high_fanout_files=[],
                full_regression_triggers=[],
                policy_hash='',
            )
            # Empty symbols set for the path -> condition (a) fails -> file scope
            r = self.plan(
                tmpdir, mp,
                {'x.py': 'modified'},
                symbols={'x.py': set()},
                closure=MockClosure(is_safe=True),
            )
            self.assertEqual(r.resolved_scope, 'file',
                              f"Expected 'file', got '{r.resolved_scope}'")

    def test_smoke_tests_present_at_symbol_scope(self):
        """Smoke tests are included even at symbol scope."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_a.py").write_text("from x import foo\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            mp = MockPolicy(
                components={'x': ['x/*.py']},
                test_mappings={'x': ['tests/test_a.py']},
                component_dependencies={},
                mandatory_smoke_tests=['tests/smoke.py'],
                high_fanout_files=[],
                full_regression_triggers=[],
                policy_hash='',
            )
            r = self.plan(
                tmpdir, mp,
                {'x.py': 'modified'},
                symbols={'x.py': {'foo'}},
                closure=MockClosure(is_safe=True),
            )
            self.assertEqual(r.resolved_scope, 'symbol')
            self.assertIn('tests/smoke.py', r.selected_tests,
                           f"Smoke test missing at symbol scope: {r.selected_tests}")

    def test_monotonicity_adding_more_classified_files_doesnt_narrow(self):
        """Monotonicity: adding more classified files doesn't narrow scope."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_a.py").write_text("from x import foo\nfrom y import bar\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            Path(tmpdir, "y.py").write_text("def bar(): pass\n")
            mp = MockPolicy(
                components={'x': ['x/*.py'], 'y': ['y/*.py']},
                test_mappings={'x': ['tests/test_a.py'], 'y': ['tests/test_a.py']},
                component_dependencies={},
                mandatory_smoke_tests=[],
                high_fanout_files=[],
                full_regression_triggers=[],
                policy_hash='',
            )
            r_single = self.plan(
                tmpdir, mp,
                {'x.py': 'modified'},
                symbols={'x.py': {'foo'}},
                closure=MockClosure(is_safe=True),
            )
            r_dual = self.plan(
                tmpdir, mp,
                {'x.py': 'modified', 'y.py': 'modified'},
                symbols={'x.py': {'foo'}, 'y.py': {'bar'}},
                closure=MockClosure(is_safe=True),
            )
            self.assertGreaterEqual(
                _scope_index(r_dual.resolved_scope),
                _scope_index(r_single.resolved_scope),
            )

    def test_escalation_reason_names_blocker_when_narrowing_refused(self):
        """The escalation_reason names the blocker when narrowing is refused."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_a.py").write_text("from x import foo\n")
            Path(tmpdir, "x.py").write_text("def foo(): pass\n")
            mp = MockPolicy(
                components={'x': ['x/*.py']},
                test_mappings={'x': ['tests/test_a.py']},
                component_dependencies={},
                mandatory_smoke_tests=[],
                high_fanout_files=[],
                full_regression_triggers=[],
                policy_hash='',
            )
            r = self.plan(
                tmpdir, mp,
                {'x.py': 'modified'},
                symbols={'x.py': {'nonexistent'}},
                closure=MockClosure(is_safe=True),
            )
            self.assertIn('nonexistent', r.escalation_reason,
                           f"escalation_reason should mention blocker: {r.escalation_reason}")

    def test_symbol_scope_with_coverage_data_included(self):
        """Symbol-level scope with coverage data included should work correctly."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir, "tests")
            tests_dir.mkdir()
            (tests_dir / "test_a.py").write_text("from x import foo\n")
            (tests_dir / "test_b.py").write_text("from x import bar\n")
            (tests_dir / "test_c.py").write_text("from x import baz\n")
            Path(tmpdir, "x.py").write_text(
                "def foo(): pass\ndef bar(): pass\ndef baz(): pass\n"
            )
            mp = MockPolicy(
                components={'x': ['x/*.py']},
                test_mappings={'x': ['tests/test_a.py', 'tests/test_b.py', 'tests/test_c.py']},
                component_dependencies={},
                mandatory_smoke_tests=[],
                high_fanout_files=[],
                full_regression_triggers=[],
                policy_hash='',
            )
            # Only 'foo' and 'bar' are changed
            r = self.plan(
                tmpdir, mp,
                {'x.py': 'modified'},
                symbols={'x.py': {'foo', 'bar'}},
                closure=MockClosure(is_safe=True),
            )
            self.assertEqual(r.resolved_scope, 'symbol',
                              f"Expected 'symbol', got '{r.resolved_scope}'")
            # Should include tests for foo and bar but not baz
            self.assertIn('tests/test_a.py', r.selected_tests)
            self.assertIn('tests/test_b.py', r.selected_tests)


if __name__ == '__main__':
    unittest.main()
