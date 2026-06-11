# Test Plan

## Scope of Testing
[Describe what is being tested in this phase.]

## Test Cases

| ID | Description | Expected Result | Status |
|----|-------------|----------------|--------|
| TC-01 | Application starts without errors | Server binds to port, health endpoint returns 200. | Pending |
| TC-02 | Database connectivity | Health check shows database exists. | Pending |
| TC-03 | Governance templates exist | All template files present in `docs/governance-templates/`. | Pending |
| TC-04 | Hidden panels are invisible in UI | Panels not rendered in browser but accessible via API. | Pending |

## Manual Verification Steps
1. [ ] Start the application.
2. [ ] Open the main page and verify layout.
3. [ ] Check that hidden sections do not appear.
4. [ ] Verify backend endpoints still work for hidden sections.

## Pass / Fail Criteria
All test cases must pass. Any failed case blocks sign-off.
