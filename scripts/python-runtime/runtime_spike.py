#!/usr/bin/env python3
"""DPMtF Python Runtime — minimal viable loop (SPIKE).

Proves one code edit end-to-end through a local Ollama model with NO code
frontend. Decision-gate spike, not the production runtime.

Actions: READ_FILE, REQUEST_CONTEXT, APPLY_PATCH, RUN_REGISTERED_CHECK, FINISH.
Model resolved through Model Allocator (unified model selection).
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
DISPATCH = Path(__file__).resolve().parent.parent / "bridgeV002" / "dispatch.py"

SYSTEM_INSTRUCTION = (
    "You are imple01, a code implementer with NO shell and NO direct file "
    "access. You act ONLY by returning exactly ONE JSON object per message, "
    "nothing else — no prose, no markdown fences, no code blocks. "
    "The JSON MUST use these exact field names:\n"
    '  {"action": "READ_FILE", "path": "<relative path>"}\n'
    '  {"action": "APPLY_PATCH", "path": "<relative path>", "content": "<full new file content>"}\n'
    '  {"action": "FINISH", "summary": "<what you did>"}\n'
    "Rules:\n"
    "- The field is \"action\" (not \"operation\" or \"type\")\n"
    "- The field is \"path\" (not \"filepath\" or \"file\")\n"
    "- The field is \"content\" (not \"patch\" or \"code\")\n"
    "- APPLY_PATCH content is the COMPLETE new file, never a diff\n"
    "- Return ONE JSON object, then STOP and wait for OBSERVATION\n"
    "- Do NOT return multiple JSON objects in one message\n"
)


def resolve_model_via_allocator(role, client):
    """Resolve model + API base + context via Model Allocator."""
    import sys as _sys
    from pathlib import Path as _Path
    _project_root = _Path(__file__).resolve().parent.parent.parent
    _sys.path.insert(0, str(_project_root))
    import config
    allocator_path = os.path.join(
        config.get_project_path("model-allocator"), "scripts", "model-allocator"
    )
    result = subprocess.run(
        [allocator_path, "resolve", "--role", role, "--client", client],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Allocator resolve failed: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    return {
        "real_model": data.get("real_model", ""),
        "api_base": data.get("default_api_base", "http://127.0.0.1:11434"),
        "context": data.get("context", 131072),
    }


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


def _fix_json_newlines(text):
    """Fix actual newlines inside JSON string values by escaping them."""
    result = []
    in_string = False
    escape = False
    for c in text:
        if escape:
            result.append(c)
            escape = False
            continue
        if c == '\\':
            result.append(c)
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            result.append(c)
            continue
        if c == '\n' and in_string:
            result.append('\\n')
            continue
        if c == '\r' and in_string:
            result.append('\\r')
            continue
        result.append(c)
    return ''.join(result)


def extract_json(text):
    if not text or not text.strip():
        return None
    cleaned = re.sub(r"embroil.*?notified", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()
    fence = chr(96) * 3
    if cleaned.startswith(fence):
        lines = cleaned.split("\n")
        if lines[0].startswith(fence):
            lines = lines[1:]
        if lines and lines[-1].startswith(fence):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    # Find the FIRST JSON object (model may return multiple)
    start = cleaned.find("{")
    if start < 0:
        return None
    # Track brace depth to find the end of the first JSON object
    depth = 0
    in_str = False
    esc = False
    end = -1
    for i, c in enumerate(cleaned[start:]):
        if esc:
            esc = False
            continue
        if c == '\\':
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = start + i
                break
    if end < 0 or end <= start:
        return None
    json_str = cleaned[start:end + 1]
    # Fix actual newlines inside string values
    json_str = _fix_json_newlines(json_str)
    try:
        data = json.loads(json_str)
        # Normalize alternate field names
        if "operation" in data and "action" not in data:
            data["action"] = data.pop("operation")
        if "filepath" in data and "path" not in data:
            data["path"] = data.pop("filepath")
        if "file" in data and "path" not in data:
            data["path"] = data.pop("file")
        if "patch" in data and "content" not in data:
            data["content"] = data.pop("patch")
        if "code" in data and "content" not in data:
            data["content"] = data.pop("code")
        return data
    except json.JSONDecodeError:
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
        return f"OBSERVATION: contents of {action['path']}:\n" + target.read_text()
    if kind == "REQUEST_CONTEXT":
        return f"OBSERVATION: context request acknowledged: {action.get('query', '?')}"
    if kind == "APPLY_PATCH":
        target = safe_resolve(project_root, action["path"])
        content = action.get("content", "")
        if len(content.encode()) > MAX_FILE_BYTES:
            return f"OBSERVATION: content too large for {action['path']}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        changed.add(action["path"])
        return f"OBSERVATION: wrote {len(content)} chars to {action['path']}"
    if kind == "RUN_REGISTERED_CHECK":
        check = action.get("check", "")
        if check == "py_compile":
            results = []
            for rel in sorted(changed):
                if rel.endswith(".py"):
                    path = str(Path(project_root) / rel)
                    r = subprocess.run([sys.executable, "-m", "py_compile", path],
                                       capture_output=True, text=True)
                    results.append(f"py_compile {rel}: {'PASS' if r.returncode == 0 else 'FAIL ' + r.stderr.strip()}")
            return "OBSERVATION: " + "; ".join(results) if results else "OBSERVATION: no .py files to check"
        return f"OBSERVATION: unknown check: {check}"
    return f"OBSERVATION: unknown action: {kind}"


def run_validation(changed, project_root):
    results, ok = [], True
    for rel in sorted(changed):
        path = str(Path(project_root) / rel)
        if rel.endswith(".py"):
            r = subprocess.run([sys.executable, "-m", "py_compile", path],
                               capture_output=True, text=True)
            passed = r.returncode == 0
            results.append(f"py_compile {rel}: {'PASS' if passed else 'FAIL ' + r.stderr.strip()}")
            ok = ok and passed
        elif rel.endswith(".js"):
            r = subprocess.run(["node", "--check", path],
                               capture_output=True, text=True)
            passed = r.returncode == 0
            results.append(f"node --check {rel}: {'PASS' if passed else 'FAIL ' + r.stderr.strip()}")
            ok = ok and passed
    return ok, results


def write_result(result_path, handoff_id, model, status, summary,
                 changed, validation, project_root):
    blocks = [
        "# imple01 Result",
        f"## Handoff ID\n{handoff_id}",
        f"## Runtime\n- Backend: python_runtime (spike)\n- Model: {model}",
        f"## Status\n{status}",
        f"## Implementation Summary\n{summary}",
        "## Changed Files\n" + ("\n".join(f"- {c}" for c in sorted(changed)) or "(none)"),
        "## Validation\n" + ("\n".join(f"- {v}" for v in validation) or "(none)"),
        "## Git State\n- No commit created\n- Changes unstaged\n" +
            subprocess.run(["git", "-C", project_root, "diff", "--stat"],
                          capture_output=True, text=True).stdout.strip() or "(no diff)",
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
    ap.add_argument("--allocator-role", default="imple01")
    ap.add_argument("--allocator-client", default="opencode")
    ap.add_argument("--ollama-url", default=None)
    ap.add_argument("--num-ctx", type=int, default=None)
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--no-signal", action="store_true")
    args = ap.parse_args()

    # Resolve model via allocator
    model_info = resolve_model_via_allocator(args.allocator_role, args.allocator_client)
    model = model_info["real_model"]
    ollama_url = args.ollama_url or model_info["api_base"]
    num_ctx = args.num_ctx or model_info["context"]

    print(f"Runtime spike: model={model}, url={ollama_url}, ctx={num_ctx}")

    task = Path(args.prompt_file).read_text()
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": task},
    ]
    changed = set()
    status, summary = "BLOCKED", "no FINISH within turn budget"

    for turn in range(1, MAX_TURNS + 1):
        raw = call_model(ollama_url, model, messages, num_ctx, args.temperature)
        print(f"[turn {turn}] {raw[:200]!r}")
        action = extract_json(raw)
        if action is None:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                "OBSERVATION: could not parse a JSON action. Return exactly one JSON object."})
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
    write_result(args.result_path, args.handoff_id, model, status,
                 summary, changed, validation, args.project_root)
    print(f"STATUS: {status}; changed={sorted(changed)}; validation_ok={ok}")

    if not args.no_signal and status == "COMPLETED":
        signal_complete(args.flow, args.role)
    return 0 if status == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
