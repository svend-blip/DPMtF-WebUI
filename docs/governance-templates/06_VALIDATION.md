# Validation

## Pre-Commit Checks
1. `python3 -m py_compile app.py` — backend syntax check passes.
2. `node --check static/js/*.js` — frontend syntax check passes (if JS changed).
3. `git diff --stat` — review scope of changes.
4. Verify page loads in browser and no console errors.

## Functional Validation
- Each modified endpoint returns expected response shape.
- UI panels render without layout breakage.
- Database queries return correct data.

## Regression Checks
- Previously completed phases still function.
- No hidden console errors after changes.
- Hidden panels remain accessible via backend API (not deleted).

## Sign-Off Criteria
All pre-commit checks pass + at least one manual verification of the affected feature area.
