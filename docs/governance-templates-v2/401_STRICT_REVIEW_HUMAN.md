# 401 — STRICT_REVIEW_HUMAN

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **Human** in the DPMtF `strict_review` flow — the final authority on scope
and commits. You receive the verdict from review02 and decide whether the change
is approved for commit.

## When You Are Active

- At the end of a `strict_review` cycle, when review02 has written a verdict and
  commit message.
- When an escalation reaches you via GATE-SCOPE or architectural deadlock.

## What You Receive

From review02, via the bridge directory:

```
{bridge_dir}/implementertoreview/{ID}-verdict.md       ← final verdict
{bridge_dir}/implementertoreview/{ID}-commit-message.md ← proposed commit message
```

The verdict contains:
- **Status:** APPROVED or REJECTED
- **Validation results:** what checks passed/failed
- **Diff summary:** which files changed
- **Findings:** any issues found and their severity

## What You Decide

1. **Read the verdict file** — understand what was implemented and how it was validated.
2. **Review the diff** — `git diff --stat` and `git diff` in the target project.
3. **Decide:**
   - **APPROVE** → execute the commit (see below).
   - **REJECT** → communicate the reason back to the Architect for a new handoff.

## Commit Procedure (APPROVE only)

```bash
cd {project_path}
git add <specific files from verdict>    # NEVER git add -A
git commit -m "<commit message from verdict>"
git push  # optional, only if you want to push immediately
```

**Only you may commit.** No other role has commit authority.

## Scope Change

If the implementation exceeds the defined scope, do NOT approve. Either:
- Reject and request scope reduction.
- Formally expand scope in `docs/dpmtf/11_SCOPE.md` first, then approve.

## Constraints

- You are the only role authorized to execute `git commit` and `git push`.
- Never commit `.env`, `__pycache__/`, or generated artifacts.
- If in doubt about a change, reject and ask the Architect for clarification.
