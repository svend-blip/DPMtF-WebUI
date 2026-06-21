# Convention Rule Auto-Fill Condition Plan

**Date:** 2026-06-21  
**Bug:** `_autoFillFromConvention` fills Deliverable Dir, Pattern, and Error Msg fields even when editing an existing step. Should only auto-fill on new steps.  
**Approach:** A — flag-baseret: pass `isNewStep` flag through to guard the auto-fill behavior.  
**Files modified:** `static/js/dpmtf-app.js` (only file)

---

## Implementation Steps

### Step 1: Guard `_autoFillFromConvention` with a fourth parameter

**File:** `/home/svend/DPMtF-WebUI/static/js/dpmtf-app.js`  
**Line:** 2418

Change the function signature and add the guard at the top:

```diff
- function _autoFillFromConvention(ruleKey, form, conventions) {
+ function _autoFillFromConvention(ruleKey, form, conventions, isNewStep) {
    if (!ruleKey || !conventions) return;
+   if (!isNewStep) return;
```

This ensures the auto-fill logic is skipped whenever `isNewStep` is falsy — which covers both the "editing existing step" case (`_bridgeEditingStepId` is non-null → `isNewStep = false`) and the "no rule selected" edge case.

---

### Step 2: Add `isNewStep` flag in form-building code

**File:** `/home/svend/DPMtF-WebUI/static/js/dpmtf-app.js`  
**Location:** Inside `_showStepForm()`, right after line 2295 (`form.id = "bridge-step-form";`)

Insert the flag variable declaration:

```diff
   var form = el("div", "dpmtf-card");
   form.id = "bridge-step-form";
+
+  var isNewStep = !_bridgeEditingStepId;
```

`_bridgeEditingStepId` is `null` when opening the form fresh (new step) and set to a numeric ID in `_editBridgeStep()` when editing an existing step. So `!_bridgeEditingStepId` gives us `true` for new steps and `false` for edit mode — exactly what we need.

---

### Step 3: Pass `isNewStep` through the onchange handler

**File:** `/home/svend/DPMtF-WebUI/static/js/dpmtf-app.js`  
**Line:** 2381

Change the onchange assignment to pass the flag as the 4th argument:

```diff
- rkSelect.onchange = function () { _autoFillFromConvention(this.value, form, meta.available_conventions); };
+ rkSelect.onchange = function () { _autoFillFromConvention(this.value, form, meta.available_conventions, isNewStep); };
```

The closure over `isNewStep` works because the flag is a `var` declared in the same function scope as this assignment — it's captured by the anonymous function at call time.

---

## Validation Checklist

| # | Check | Command |
|---|-------|---------|
| 1 | Backend syntax | `python3 -m py_compile app.py` |
| 2 | Frontend syntax | `node --check static/js/dpmtf-app.js` |
| 3 | No innerHTML | `grep -n "innerHTML" static/js/dpmtf-app.js` — must be empty |
| 4 | No hardcoded paths | `grep -n '/home/svend' static/js/dpmtf-app.js app.py scripts/` — must return NO results |
| 5 | Diff scope | `git diff --stat` — only `static/js/dpmtf-app.js` changed |

---

## Summary of Changes

| Line(s) | Change | Purpose |
|---------|--------|---------|
| ~2296 | `var isNewStep = !_bridgeEditingStepId;` | Capture whether this is a new step or an edit |
| 2381 | Pass `isNewStep` to `_autoFillFromConvention` | Propagate the flag through the closure |
| 2418-2420 | Add `isNewStep` param + `if (!isNewStep) return;` guard | Skip auto-fill for edit mode |

Total: 3 edits, ~5 lines changed in one file.
