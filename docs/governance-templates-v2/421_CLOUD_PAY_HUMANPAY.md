# 421 — CLOUD_PAY_HUMANPAY

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **HumanPay** in the DPMtF `cloud_pay` flow — the final authority on scope
and commits. You receive the verdict from review02pay and decide whether the change
is approved for commit.

## When You Are Active

- At the end of a `cloud_pay` cycle, when review02pay has written a verdict and
  commit message.
- When an escalation reaches you via GATE-SCOPE or architectural deadlock.

## What You Receive

From review02pay, via the bridge directory:

```
{bridge_dir}/cloud_pay/verdicts/{ID}-verdict.md       ← final verdict
{bridge_dir}/cloud_pay/verdicts/{ID}-commit-message.md ← proposed commit message
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

The `cloud_pay` flow operates on the **Child project `/home/svend/trade-ui`**
(NOT the Father project). Commit there:

```bash
cd /home/svend/trade-ui    # cloud_pay target project (Child), NOT the Father project
git add <specific files from verdict>    # NEVER git add -A
git commit -m "<commit message from verdict>"
git push  # optional, only if you want to push immediately
```

If the verdict also touched Father governance files (e.g. `docs/governance-templates-v2/*`),
commit those separately in `/home/svend/DPMtF-WebUI`.

**Only you may commit.** No other role has commit authority.

## Scope Change

If the implementation exceeds the defined scope, do NOT approve. Either:
- Reject and request scope reduction.
- Formally expand scope in `docs/dpmtf/11_SCOPE.md` first, then approve.

## Constraints

- You are the only role authorized to execute `git commit` and `git push`.
- Never commit `.env`, `__pycache__/`, or generated artifacts.
- If in doubt about a change, reject and ask the Architect for clarification.
