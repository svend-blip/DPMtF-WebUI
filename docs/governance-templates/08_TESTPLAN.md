# Test Plan

## Purpose

This governance document defines the test cases, verification steps, and pass/fail criteria for the current phase. It ensures that validation is systematic and repeatable across sessions, especially after `/clear` when chat memory is unavailable.

## When to Use

- **Validator step**: Execute all test cases listed in this document.
- **Before sign-off**: All tests must pass before changes are committed.
- **After `/clear`**: Read to reconstruct what needs to be verified without relying on chat history.

## Required Inputs

| Input | Description |
|-------|-------------|
| Phase scope | Defined in `02_SCOPE.md`. |
| Implementation report | From `12_IMPLEMENTATION_REPORT.md`. |
| Changed files list | From `git diff --stat`. |

## Required Outputs

- Completed test plan with pass/fail status for each case.
- Manual verification checklist with all items checked.
- Pass/fail verdict for the phase.

---

## Scope of Testing

[Describe what is being tested in this phase. Reference the phase key and title from `00_PROJECT.md` or `NEXT_CONTEXT.md`.]

## Test Cases

| ID | Description | Expected Result | Status |
|----|-------------|----------------|--------|
| TC-01 | Application starts without errors | Server binds to port, health endpoint returns 200. | Pending |
| TC-02 | Database connectivity | Health check shows database exists and is readable. | Pending |
| TC-03 | Governance templates exist | All template files present in `docs/governance-templates/`. | Pending |
| TC-04 | Hidden panels are invisible in UI | Panels not rendered in browser but accessible via API. | Pending |

## Manual Verification Steps

1. [ ] Start the application (`python3 app.py`).
2. [ ] Open the main page and verify layout matches expected state.
3. [ ] Check that hidden sections do not appear in the frontend.
4. [ ] Verify backend endpoints still work for hidden sections (curl or fetch test).
5. [ ] Confirm no new console errors appear in the browser developer tools.

## Automated Verification Commands

```bash
# Backend syntax check
python3 -m py_compile app.py

# Frontend syntax check (if JS changed)
node --check static/js/*.js

# Diff scope review
git diff --stat

# Health endpoint test
curl -s http://localhost:9130/api/health
```

## Pass / Fail Criteria

- All automated checks pass.
- All manual verification steps are completed and checked.
- All test cases show "Pass" status.
- Any failed case blocks sign-off — the Validator must document failures in `13_VALIDATION_REPORT.md` and return changes to the Implementer.

## Test Case Template (Add New Cases Below)

```markdown
| TC-XX | [Test description] | [Expected result] | Pending |
```

---
