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
    ):
        self.components = components or {}
        self.test_mappings = test_mappings or {}
        self.component_dependencies = component_dependencies or {}
        self.mandatory_smoke_tests = mandatory_smoke_tests or []
        self.high_fanout_files = high_fanout_files or []
        self.full_regression_triggers = full_regression_triggers or []
        self.policy_hash = policy_hash

    def component_for(self, path):
        """Return the component name whose source globs match path, or None."""
        import fnmatch
        for comp, globs in self.components.items():
            for glob in globs:
                if fnmatch.fnmatch(path, glob):
                    return comp
        return None


class TestPlanner(unittest.TestCase):
    """Test cases for the planner test-plan engine."""

    def plan(self, repo_root, policy, changes, requested_scope=None):
        return plan_tests(repo_root, policy, changes, requested_scope)

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


if __name__ == '__main__':
    unittest.main()
