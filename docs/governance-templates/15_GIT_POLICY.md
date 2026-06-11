# Git Policy

## Branch Strategy
- `master` is the default and primary branch.
- Use worktrees for experimental changes.
- Do not push directly to `master` without local verification.

## Commit Conventions
- One logical change per commit.
- Commit messages describe what changed and why.
- Include `Co-Authored-By: Claude ...` when AI-assisted.
- Do not commit hidden files or generated artifacts.

## Before Committing
1. Run syntax checks (`py_compile`, `node --check`).
2. Review `git diff --stat` for scope.
3. Verify the application still loads.
4. Ensure no secrets, credentials, or API keys are in the diff.

## Hidden vs Deleted Code
- Code that is temporarily hidden gets a CSS class or conditional guard and an inline comment.
- Do not delete code unless it is confirmed dead (no references, no tests depend on it).
- Hidden code must be reversible with a single change.

## File Staging
- Stage related changes together.
- Do not mix unrelated fixes in one commit.
