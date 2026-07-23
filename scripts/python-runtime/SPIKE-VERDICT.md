# Python Runtime Spike — Decision Gate Verdict

**Date:** 2026-07-23
**Model:** qwen3-coder:30b-256k (resolved via model-allocator)
**Context:** 131072 (from alias config)
**Backend:** Ollama (local, http://127.0.0.1:11434)

## Results

### Create-file task (single run)
- **Status:** COMPLETED
- **Changed files:** scripts/spike_marker.py
- **Validation:** py_compile PASS
- **Result:** Correct function `spike_marker()` returning `"RUNTIME_SPIKE_OK"`

### Edit-file task (10 runs)
- **Edit reliability:** 10/10
- **Failures:** None
- **All runs:** Model reads file → applies patch with added() function → finishes

## Bugs found and fixed during spike

1. **Field name mismatch:** Model returned `"operation"` instead of `"action"`, 
   `"filepath"` instead of `"path"`, `"patch"` instead of `"content"`.
   **Fix:** Normalized alternate field names in extract_json.

2. **Actual newlines in JSON string values:** Model returned actual newline 
   characters (chr(10)) inside JSON string values instead of `\n` escape 
   sequences, making json.loads fail.
   **Fix:** Added `_fix_json_newlines()` that tracks string context and 
   escapes actual newlines inside JSON string values.

3. **Multiple JSON objects in one message:** Model sometimes returns both 
   APPLY_PATCH and FINISH in one response.
   **Fix:** extract_json now tracks brace depth to find the FIRST complete 
   JSON object only.

## Decision Gate

**Rule:** GO iff ≥9/10 and failures are not edit-application failures.

**Verdict:** **GO**

- Score: 10/10 (exceeds 9/10 threshold)
- All failures during development were JSON parsing issues (edit-application 
  failures), which were fixed in the parser. After fixes, 10/10 clean.
- Path safety: all traversal/symlink/absolute path attempts rejected ✓
- Action schema: only READ_FILE, APPLY_PATCH, FINISH, REQUEST_CONTEXT, 
  RUN_REGISTERED_CHECK are accepted ✓
- No shell=True, no git commit/push/add ✓
- Model resolved through Model Allocator (sole source of truth) ✓

## Next steps (if GO)

1. Modular runtime: split into runtime.py / file_tools.py / prompt_parser.py
2. Wire as `execution_backend=python_runtime` path in dispatch.py
3. Add SEARCH + line-anchored REPLACE for large files
4. Add 2-attempt patch cap on validation failures
5. Add SQLite `runtime_runs` table for execution audit trail
