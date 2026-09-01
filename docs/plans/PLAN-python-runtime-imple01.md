# DPMtF Python Runtime for imple01 — Minimal Viable Loop (Decision-Gate Spike)

> **For agentic workers:** Execute tasks in order. Steps use checkbox (`- [ ]`) syntax for tracking. Do not skip verification steps. This plan is a **spike**: its purpose is to produce a go/no-go decision, not a production runtime. Read the "Decision Gate" section before writing any code.

**Goal:** Prove — or disprove — that a local Ollama model can drive a code edit end-to-end through a tiny frontend-free Python runtime, reliably enough to justify replacing the OpenCode/Claude Code frontend for the `imple01` role in the `strict_review` flow.

**Architecture:** A single ~180-line Python module runs a bounded action loop against Ollama's `/api/chat`. The model returns one JSON action per turn (`READ_FILE` / `WRITE_FILE` / `FINISH`); the runtime enforces safe paths, runs controller-owned validation, writes a fact-based result file, and signals completion via the existing BridgeV002 `dispatch.py`. No shell, no tool schemas, no MCP, no multi-module framework — those come only if the spike passes.

**Tech Stack:** Python 3 stdlib only (`urllib`, `json`, `subprocess`, `argparse`, `pathlib`) — no new pip dependencies. Ollama HTTP API. Existing BridgeV002 dispatch.py for the completion signal.

## Cold-Start Context

- **DPMtF-WebUI** ("Father") is a FastAPI + SQLite governance/orchestration project on port 9130. It owns the **BridgeV002** multi-agent dispatch system in `scripts/bridgeV002/` (roles run in tmux sessions; `dispatch.py` injects prompts and routes completion signals).
- The **`strict_review`** flow runs `archi01` → `imple01` → `review01`. Today `imple01` runs inside a code frontend (OpenCode or Claude Code). This spike tests a Python runtime as an alternative backend **for `imple01` only**.
- The runtime operates on a **child project** (e.g. `/home/svend/trade-ui`), never on Father itself.
- **This spike lives at** `scripts/python-runtime/` in DPMtF-WebUI. It is standalone — it does not import app.py, does not touch the DB, does not change any flow definition.
- Completion signal contract (from CLAUDE.md §8): `python3 scripts/bridgeV002/dispatch.py --db-flow strict_review --signal-complete --from-role imple01`.
- **Only the Human commits.** Every task ends by staging files and stopping.
- Reusable prior art (read, do not import across repos — copy the ~30 lines): `local-trade-engine`'s `app/ollama/validation.py::_extract_json` (robust JSON extraction from model output with think-tags/preamble/fences) and `app/ollama/client.py` (Ollama HTTP shape). The trade engine's `role_runner.py` is a **single-shot** generator, NOT a multi-turn edit loop — its control flow is not reusable here; the loop is net-new.

## Decision Gate — read before coding

This plan exists because of an unresolved question: **is a bespoke runtime worth building, or is OpenCode already the right tool?**

Honest framing, so the spike is judged correctly:

- **If the goal is reduced context overhead / simplicity:** a bespoke runtime is *probably overkill*. OpenCode already has a battle-tested multi-turn edit loop with reliable file editing (the single hardest part), already runs local models via Model Allocator, and `opencode --bare` already strips hooks/plugins/LSP — which addresses most of the context-overhead motivation. Rebuilding the edit loop to save ~10-15% context on a 96-131k model is a poor trade.
- **The runtime is only justified if the real goal is hard, deterministic, action-level governance** that OpenCode structurally cannot provide: a whitelisted action set, no arbitrary shell, per-action scope enforcement, and an auditable fact-based result. `review01` already catches mistakes afterward, so even this is a "belt-and-braces" argument — but it is a *real* capability OpenCode lacks.

**Therefore this spike measures exactly one thing: edit reliability of local models through the whitelisted-action loop.** Task 2 produces the number that decides everything. If local models cannot reliably drive whole-file writes through this loop, the OpenCode path wins and the multi-module build (the 21-section proposal) is cancelled — cheaply.

**Go / No-Go rule (applied after Task 2):**
- **GO** (continue to a modular V1 + SEARCH/READ/REPLACE): ≥ 9/10 spike runs produce a correct edit with clean validation and a valid completion signal.
- **NO-GO** (use `opencode --bare` via Model Allocator for `imple01` instead): < 9/10, OR the failures are in edit application (malformed content, wrong file, escaped scope) rather than task difficulty.

## Global Constraints

- Python 3 stdlib only — **no new pip dependencies**.
- **No hardcoded `/home/svend/...` paths.** Derive the dispatch.py path from `__file__`. The child project root arrives as a CLI argument.
- `python3 -m py_compile` MUST pass on the module before it is considered done.
- The runtime **never commits, never pushes, never stages** in the target project.
- The runtime **never writes outside the child project root** and never writes into Father, even read-only governance files are read-only.
- Model output is **never trusted for validation** — the runtime runs the actual checks and records exit codes.
- Parameterized/argument-driven config only; the model name is an explicit CLI argument, never hardcoded.

## Edge Cases a Weaker Model Would Miss

1. **Whole-file writes, not diffs — on purpose.** Local models are unreliable at exact-match `OLD/NEW` replace (whitespace drift, paraphrased anchors, 0-or-2 matches, custom delimiters colliding with code). The spike uses `WRITE_FILE` with complete file content because it is the *most reliable* edit primitive for local models. Do not "improve" it into a surgical-replace format — that is precisely the risk being measured, and it belongs in a later task only if the spike passes.
2. **The model emits prose/think-tags around its JSON.** `qwen3.6` does not support Ollama `format: json`. You MUST extract the JSON (strip `<think>`/`<thinking>`, strip ``` fences, take the outermost `{…}`). A bare `json.loads` will fail on turn 1 — this exact bug killed 11/14 runs in `local-trade-engine` before it was fixed.
3. **Path safety must resolve symlinks and reject `..` and absolute paths** *before* touching the filesystem. Use `target.relative_to(root)` on the **resolved** path, and reject any symlinked path component. A naive `startswith` check is bypassable via symlinks.
4. **A model with no `FINISH` will loop forever.** Enforce a hard turn cap (`MAX_TURNS`). The patch-attempt limit is a separate concept; this cap is the anti-infinite-loop backstop and must exist from turn 1.
5. **`FINISH` is a request, not a completion.** After the model says FINISH, the runtime must still run validation, downgrade `COMPLETED`→`BLOCKED` on validation failure, write the result file, and only then signal. The model cannot self-declare success.
6. **Write the result file and collect git state BEFORE signalling completion.** BridgeV002 wraps signal dispatch in a timeout and has a known post-dispatch hang; if the signal is fired first and the process is then killed, the durable artifact is lost.
7. **Multi-turn needs `/api/chat`, not `/api/generate`.** The model must see its own prior actions and the observations. Use a `messages` array; appending to a single prompt string loses turn structure.
8. **`node --check` may be absent** on a machine validating a pure-Python change. Only validate file types that were actually written, and treat a missing validator for an unwritten type as "nothing to check", not an error.

---

### Task 1: Build the minimal loop and prove one WRITE_FILE end-to-end

**Files:**
- Create: `scripts/python-runtime/runtime_spike.py`
- Create (test input): `scripts/python-runtime/spike_task_create.txt`
- Produces (at runtime, in the target project): a new file + a result file

**Interfaces:**
- Produces CLI: `python3 runtime_spike.py --prompt-file <f> --project-root <dir> --handoff-id <id> --result-path <f> --model <name> [--flow strict_review] [--role imple01] [--ollama-url URL] [--num-ctx N] [--temperature T] [--no-signal]`
- Consumes: Ollama `/api/chat`; BridgeV002 `dispatch.py` (only when `--no-signal` is absent and status is COMPLETED).

- [ ] **Step 1: Create the runtime module**

Create `scripts/python-runtime/runtime_spike.py` with exactly this content:

```python
#!/usr/bin/env python3
"""DPMtF Python Runtime — minimal viable loop (SPIKE).

Proves one code edit end-to-end through a local Ollama model with NO code
frontend. Decision-gate spike, not the production runtime.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

MAX_TURNS = 8
MAX_FILE_BYTES = 200_000
FENCE = chr(96) * 3  # three backticks, without embedding them literally
DISPATCH = Path(__file__).resolve().parent.parent / "bridgeV002" / "dispatch.py"

SYSTEM_INSTRUCTION = (
    "You are imple01, a code implementer with NO shell and NO direct file "
    "access. You act ONLY by returning exactly ONE JSON object per message, "
    "nothing else — no prose, no markdown fences. Allowed actions:\n"
    '  {"action": "READ_FILE", "path": "<relative path>"}\n'
    '  {"action": "WRITE_FILE", "path": "<relative path>", "content": "<full file content>"}\n'
    '  {"action": "FINISH", "summary": "<what you did>"}\n'
    "WRITE_FILE always contains the COMPLETE new file content, never a diff or "
    "partial. Return one action, wait for the OBSERVATION, then continue. Call "
    "FINISH when the task is done."
)


def call_model(url, model, messages, num_ctx, temperature):
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_ctx": num_ctx, "temperature": temperature},
    }).encode()
    req = urllib.request.Request(
        url.rstrip("/") + "/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    return data["message"]["content"]


def extract_json(text):
    if not text or not text.strip():
        return None
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()
    if cleaned.startswith(FENCE):
        lines = cleaned.split("\n")
        if lines[0].startswith(FENCE):
            lines = lines[1:]
        if lines and lines[-1].startswith(FENCE):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def safe_resolve(project_root, rel_path):
    if os.path.isabs(rel_path):
        raise ValueError(f"absolute paths not allowed: {rel_path}")
    root = Path(project_root).resolve()
    if ".." in Path(rel_path).parts:
        raise ValueError(f"'..' not allowed: {rel_path}")
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(f"path escapes project root: {rel_path}")
    p = root
    for part in Path(rel_path).parts:
        p = p / part
        if p.is_symlink():
            raise ValueError(f"symlink component not allowed: {rel_path}")
    return target


def execute_action(action, project_root, changed):
    kind = action.get("action")
    if kind == "READ_FILE":
        target = safe_resolve(project_root, action["path"])
        if not target.is_file():
            return f"OBSERVATION: file not found: {action['path']}"
        if target.stat().st_size > MAX_FILE_BYTES:
            return f"OBSERVATION: file too large: {action['path']}"
        return (f"OBSERVATION: contents of {action['path']}:\n"
                + target.read_text())
    if kind == "WRITE_FILE":
        target = safe_resolve(project_root, action["path"])
        content = action.get("content", "")
        if len(content.encode()) > MAX_FILE_BYTES:
            return f"OBSERVATION: content too large for {action['path']}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        changed.add(action["path"])
        return f"OBSERVATION: wrote {len(content)} chars to {action['path']}"
    return f"OBSERVATION: unknown action: {kind}"


def run_validation(changed, project_root):
    results, ok = [], True
    for rel in sorted(changed):
        path = str(Path(project_root) / rel)
        if rel.endswith(".py"):
            r = subprocess.run([sys.executable, "-m", "py_compile", path],
                               capture_output=True, text=True)
            passed = r.returncode == 0
            results.append(
                f"py_compile {rel}: "
                + ("PASS" if passed else "FAIL " + r.stderr.strip()))
            ok = ok and passed
        elif rel.endswith(".js"):
            r = subprocess.run(["node", "--check", path],
                               capture_output=True, text=True)
            passed = r.returncode == 0
            results.append(
                f"node --check {rel}: "
                + ("PASS" if passed else "FAIL " + r.stderr.strip()))
            ok = ok and passed
    return ok, results


def git_diff_stat(project_root):
    r = subprocess.run(["git", "-C", project_root, "diff", "--stat"],
                       capture_output=True, text=True)
    return r.stdout.strip() or "(no diff)"


def write_result(result_path, handoff_id, model, status, summary,
                 changed, validation, project_root):
    blocks = [
        "# imple01 Result",
        f"## Handoff ID\n{handoff_id}",
        f"## Runtime\n- Backend: python_runtime (spike)\n- Model: {model}",
        f"## Status\n{status}",
        f"## Implementation Summary\n{summary}",
        "## Changed Files\n"
        + ("\n".join(f"- {c}" for c in sorted(changed)) or "(none)"),
        "## Validation\n"
        + ("\n".join(f"- {v}" for v in validation) or "(none)"),
        "## Git State\n- No commit created\n- Changes unstaged\n"
        + git_diff_stat(project_root),
    ]
    out = Path(result_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(blocks) + "\n")


def signal_complete(flow, role):
    subprocess.run(
        [sys.executable, str(DISPATCH), "--db-flow", flow,
         "--signal-complete", "--from-role", role],
        timeout=120,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--handoff-id", required=True)
    ap.add_argument("--result-path", required=True)
    ap.add_argument("--flow", default="strict_review")
    ap.add_argument("--role", default="imple01")
    ap.add_argument("--model", required=True)
    ap.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    ap.add_argument("--num-ctx", type=int, default=131072)
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--no-signal", action="store_true")
    args = ap.parse_args()

    task = Path(args.prompt_file).read_text()
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": task},
    ]
    changed = set()
    status, summary = "BLOCKED", "no FINISH within turn budget"

    for turn in range(1, MAX_TURNS + 1):
        raw = call_model(args.ollama_url, args.model, messages,
                         args.num_ctx, args.temperature)
        print(f"[turn {turn}] {raw[:200]!r}")
        action = extract_json(raw)
        if action is None:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                "OBSERVATION: could not parse a JSON action. "
                "Return exactly one JSON object, no prose."})
            continue
        if action.get("action") == "FINISH":
            summary = action.get("summary", "")
            status = "COMPLETED"
            break
        try:
            obs = execute_action(action, args.project_root, changed)
        except (ValueError, KeyError) as e:
            obs = f"OBSERVATION: rejected: {e}"
        messages.append({"role": "assistant", "content": json.dumps(action)})
        messages.append({"role": "user", "content": obs})

    ok, validation = run_validation(changed, args.project_root)
    if status == "COMPLETED" and not ok:
        status = "BLOCKED"
    write_result(args.result_path, args.handoff_id, args.model, status,
                 summary, changed, validation, args.project_root)
    print(f"STATUS: {status}; changed={sorted(changed)}; validation_ok={ok}")

    if not args.no_signal and status == "COMPLETED":
        signal_complete(args.flow, args.role)
    return 0 if status == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Syntax-check the module**

Run: `python3 -m py_compile scripts/python-runtime/runtime_spike.py`
Expected: exit 0, no output.

- [ ] **Step 3: Write the create-file task prompt**

Create `scripts/python-runtime/spike_task_create.txt` with exactly this content:

```
TASK: Create a new file at the relative path `scripts/spike_marker.py`.
The file must contain exactly one function:

def spike_marker():
    return "RUNTIME_SPIKE_OK"

Do not read or modify any other file. Use WRITE_FILE with the complete file
content, then FINISH.
```

- [ ] **Step 4: Confirm Ollama is reachable and the model is present**

Run: `curl -s http://127.0.0.1:11434/api/tags | python3 -c "import sys,json; print([m['name'] for m in json.load(sys.stdin)['models']])"`
Expected: a list of installed models. Pick one present here (e.g. `qwen3-coder:30b` or the `qwen36-27b-q4km:latest` from the proposal) and use it as `--model` below. If none installed, stop and pull one first.

- [ ] **Step 5: Run the spike against a real child project (dry, no signal)**

Run (substitute an installed model name):
```bash
python3 scripts/python-runtime/runtime_spike.py \
  --prompt-file scripts/python-runtime/spike_task_create.txt \
  --project-root /home/svend/trade-ui \
  --handoff-id SPIKE-1 \
  --result-path /home/svend/trade-ui/inbox/spike/imple01_result.md \
  --model qwen3-coder:30b \
  --num-ctx 131072 --temperature 0.1 \
  --no-signal
```
Expected: prints per-turn output, ends with `STATUS: COMPLETED; changed=['scripts/spike_marker.py']; validation_ok=True`.

- [ ] **Step 6: Verify the file was created correctly and safely**

Run: `python3 -c "import sys; sys.path.insert(0,'/home/svend/trade-ui/scripts'); import spike_marker; print(spike_marker.spike_marker())"`
Expected: prints `RUNTIME_SPIKE_OK`.

Run: `cat /home/svend/trade-ui/inbox/spike/imple01_result.md`
Expected: a result file with Status COMPLETED, the changed file listed, and `py_compile scripts/spike_marker.py: PASS`.

- [ ] **Step 7: Verify path safety rejects an escape attempt**

Run:
```bash
python3 -c "
import sys; sys.path.insert(0,'scripts/python-runtime')
from runtime_spike import safe_resolve
for bad in ['../DPMtF-WebUI/app.py', '/etc/passwd', 'a/../../x']:
    try:
        safe_resolve('/home/svend/trade-ui', bad); print('FAIL allowed', bad)
    except ValueError as e:
        print('OK rejected:', bad)
"
```
Expected: all three print `OK rejected`.

- [ ] **Step 8: Clean up the spike artifact and stage**

Run: `rm -f /home/svend/trade-ui/scripts/spike_marker.py; rm -rf /home/svend/trade-ui/inbox/spike`
Then stage only the runtime spike files in DPMtF-WebUI:
Run: `git add scripts/python-runtime/runtime_spike.py scripts/python-runtime/spike_task_create.txt`
**STOP — await Human commit approval.** Suggested message: `[spike] python-runtime imple01 minimal loop (WRITE_FILE/READ_FILE/FINISH)`

---

### Task 2: Measure edit reliability — the go/no-go data

**Files:**
- Create (test input): `scripts/python-runtime/spike_task_edit.txt`
- Create (harness): `scripts/python-runtime/spike_measure.sh`

**Interfaces:**
- Consumes: `runtime_spike.py` from Task 1.
- Produces: a printed success count out of 10 — the number the Decision Gate rule consumes.

- [ ] **Step 1: Create a fixed, verifiable edit task**

Create `scripts/python-runtime/spike_task_edit.txt` with exactly this content:

```
TASK: In the file `scripts/spike_edit_target.py`, add a second function
named `added()` that returns the integer 42, WITHOUT changing or removing
the existing `original()` function. First READ_FILE the target, then
WRITE_FILE the complete new file content, then FINISH.
```

- [ ] **Step 2: Create the measurement harness**

Create `scripts/python-runtime/spike_measure.sh` with exactly this content:

```bash
#!/usr/bin/env bash
set -euo pipefail
MODEL="${1:?usage: spike_measure.sh <model-name>}"
PROJ=/home/svend/trade-ui
TARGET="$PROJ/scripts/spike_edit_target.py"
RT="$(dirname "$0")/runtime_spike.py"
PASS=0
for i in $(seq 1 10); do
  printf 'def original():\n    return 1\n' > "$TARGET"
  python3 "$RT" \
    --prompt-file "$(dirname "$0")/spike_task_edit.txt" \
    --project-root "$PROJ" \
    --handoff-id "SPIKE-EDIT-$i" \
    --result-path "$PROJ/inbox/spike/edit_$i.md" \
    --model "$MODEL" --num-ctx 131072 --temperature 0.1 \
    --no-signal >/dev/null 2>&1 || true
  if python3 - "$TARGET" <<'PY'
import sys, importlib.util
spec = importlib.util.spec_from_file_location("t", sys.argv[1])
m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
    ok = m.original() == 1 and hasattr(m, "added") and m.added() == 42
except Exception:
    ok = False
sys.exit(0 if ok else 1)
PY
  then PASS=$((PASS+1)); echo "run $i: PASS"; else echo "run $i: FAIL"; fi
done
echo "EDIT RELIABILITY: $PASS/10"
rm -f "$TARGET"; rm -rf "$PROJ/inbox/spike"
```

- [ ] **Step 3: Syntax-check the harness**

Run: `bash -n scripts/python-runtime/spike_measure.sh`
Expected: exit 0, no output.

- [ ] **Step 4: Run the measurement**

Run: `bash scripts/python-runtime/spike_measure.sh qwen3-coder:30b`
Expected: 10 lines of `run N: PASS/FAIL`, then `EDIT RELIABILITY: X/10`. Record X.

- [ ] **Step 5: Apply the Decision Gate and write the verdict**

Create `scripts/python-runtime/SPIKE-VERDICT.md` recording: the model used, the `X/10` score, whether failures were task-difficulty or edit-application (malformed content, wrong file, scope escape), and the GO/NO-GO decision per the rule in the Decision Gate section. Do not proceed to build SEARCH / surgical-REPLACE / the modular split unless the verdict is GO.

- [ ] **Step 6: Stage**

Run: `git add scripts/python-runtime/spike_task_edit.txt scripts/python-runtime/spike_measure.sh scripts/python-runtime/SPIKE-VERDICT.md`
**STOP — await Human commit approval.** Suggested message: `[spike] python-runtime edit-reliability measurement + verdict`

## Acceptance Criteria

1. `python3 -m py_compile scripts/python-runtime/runtime_spike.py` — exit 0.
2. `bash -n scripts/python-runtime/spike_measure.sh` — exit 0.
3. Task 1 Step 5 prints `STATUS: COMPLETED; changed=['scripts/spike_marker.py']; validation_ok=True`.
4. Task 1 Step 6 prints `RUNTIME_SPIKE_OK`; the result file shows Status COMPLETED and `py_compile … PASS`.
5. Task 1 Step 7 rejects all three path-escape attempts.
6. Task 2 Step 4 prints an `EDIT RELIABILITY: X/10` line.
7. `SPIKE-VERDICT.md` exists and records a GO or NO-GO decision consistent with the Decision Gate rule (GO iff X ≥ 9 and failures are not edit-application failures).
8. No file was written outside `/home/svend/trade-ui` during the spike; no commit or push was made in the target project (`git -C /home/svend/trade-ui status` shows a clean tree after cleanup, or only intended artifacts before cleanup).
9. `grep -n '"/home/svend' scripts/python-runtime/runtime_spike.py` returns nothing (the dispatch path is derived from `__file__`; the target root arrives as an argument).

## If GO — what comes next (not part of this spike)

Only after a GO verdict, in this order: (1) file-based prompt handoff wired into a `execution_backend=python_runtime` path in dispatch.py (no tmux keystroke injection); (2) `SEARCH` + line-anchored `REPLACE` for large files; (3) the 2-attempt patch cap on validation failures; (4) Model Allocator as the model source (resolve alias → model/num_ctx/temperature) instead of a forked runtime-profile schema; (5) the modular split (runtime.py / prompt_parser.py / file_tools.py / …) and SQLite `runtime_runs`. Each is its own plan.
