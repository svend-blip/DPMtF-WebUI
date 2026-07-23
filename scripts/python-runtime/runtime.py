#!/usr/bin/env python3
"""DPMtF Secure Execution Runtime — production modular version.

Bounded action loop: model proposes → runtime validates → runtime executes.
Actions: READ_FILE, REQUEST_CONTEXT, APPLY_PATCH, RUN_REGISTERED_CHECK, FINISH.

Model resolved through Model Allocator (sole source of truth).
Produces structured checkpoint + result file.
No shell execution, no version control mutations.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Setup paths
MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent.parent
sys.path.insert(0, str(MODULE_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from file_tools import safe_resolve, read_file, apply_patch
from prompt_parser import extract_json
from checks import run_check, run_checks_for_files, CheckResult
from result import write_result, write_checkpoint

MAX_TURNS = 8

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


def resolve_model_via_allocator(role: str, client: str) -> dict:
    """Resolve model + API base + context via Model Allocator."""
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
        "alias": data.get("alias", ""),
        "backend": data.get("backend", ""),
    }


def call_model(url: str, model: str, messages: list, num_ctx: int, temperature: float) -> str:
    """Call Ollama /api/chat and return the model's response."""
    import urllib.request
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


def execute_action(action: dict, project_root: str, changed: set) -> str:
    """Execute a model-proposed action. Returns observation string."""
    kind = action.get("action")

    if kind == "READ_FILE":
        path = action["path"]
        try:
            content = read_file(project_root, path)
            return f"OBSERVATION: contents of {path}:\n{content}"
        except FileNotFoundError:
            return f"OBSERVATION: file not found: {path}"
        except (ValueError, PermissionError) as e:
            return f"OBSERVATION: rejected: {e}"

    if kind == "REQUEST_CONTEXT":
        return f"OBSERVATION: context request acknowledged: {action.get('query', '?')}"

    if kind == "APPLY_PATCH":
        path = action["path"]
        content = action.get("content", "")
        try:
            n = apply_patch(project_root, path, content)
            changed.add(path)
            return f"OBSERVATION: wrote {n} chars to {path}"
        except (ValueError, PermissionError) as e:
            return f"OBSERVATION: rejected: {e}"

    if kind == "RUN_REGISTERED_CHECK":
        check_name = action.get("check", "")
        # Run check on all changed files matching the check type
        results = run_checks_for_files(sorted(changed), project_root)
        if not results:
            return "OBSERVATION: no files to check"
        return "OBSERVATION: " + "; ".join(f"{r.check} {r.file}: {r.status}" for r in results)

    return f"OBSERVATION: unknown action: {kind}"


def run(project_root: str, prompt_file: str, handoff_id: str,
        result_path: str, allocator_role: str = "imple01",
        allocator_client: str = "opencode", flow: str = "strict_review",
        role: str = "imple01", step_key: str = "", no_signal: bool = False,
        temperature: float = 0.1) -> dict:
    """Run the execution runtime. Returns summary dict."""
    # Resolve model via allocator
    model_info = resolve_model_via_allocator(allocator_role, allocator_client)
    model = model_info["real_model"]
    ollama_url = model_info["api_base"]
    num_ctx = model_info["context"]

    # Read task
    task = Path(prompt_file).read_text()
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": task},
    ]
    changed: set[str] = set()
    status, summary = "BLOCKED", "no FINISH within turn budget"

    # Main loop
    for turn in range(1, MAX_TURNS + 1):
        raw = call_model(ollama_url, model, messages, num_ctx, temperature)
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

        obs = execute_action(action, project_root, changed)
        messages.append({"role": "assistant", "content": json.dumps(action)})
        messages.append({"role": "user", "content": obs})

    # Run verification checks
    check_results = run_checks_for_files(sorted(changed), project_root)
    all_pass = all(r.status == "PASS" for r in check_results) if check_results else True

    if status == "COMPLETED" and not all_pass:
        status = "BLOCKED"

    # Write result file
    write_result(result_path, handoff_id, model, status, summary,
                 sorted(changed), check_results, project_root)

    # Write checkpoint
    checkpoint_dir = str(PROJECT_ROOT / "jobs" / "checkpoints")
    checkpoint_path = write_checkpoint(
        checkpoint_dir, handoff_id, flow, step_key, role,
        sorted(changed), check_results, summary,
        model_info["alias"], model_info["backend"], model,
    )

    print(f"STATUS: {status}; changed={sorted(changed)}; checks_pass={all_pass}")
    print(f"Checkpoint: {checkpoint_path}")

    # Signal completion via dispatch.py
    if not no_signal and status == "COMPLETED":
        dispatch_script = str(PROJECT_ROOT / "scripts" / "bridgeV002" / "dispatch.py")
        subprocess.run(
            [sys.executable, dispatch_script, "--db-flow", flow,
             "--signal-complete", "--from-role", role],
            timeout=120,
        )

    return {
        "status": status,
        "changed_files": sorted(changed),
        "check_results": [{"check": r.check, "file": r.file, "status": r.status} for r in check_results],
        "model": model,
        "checkpoint_path": checkpoint_path,
    }


def main():
    ap = argparse.ArgumentParser(description="DPMtF Secure Execution Runtime")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--handoff-id", required=True)
    ap.add_argument("--result-path", required=True)
    ap.add_argument("--allocator-role", default="imple01")
    ap.add_argument("--allocator-client", default="opencode")
    ap.add_argument("--flow", default="strict_review")
    ap.add_argument("--role", default="imple01")
    ap.add_argument("--step-key", default="")
    ap.add_argument("--no-signal", action="store_true")
    ap.add_argument("--temperature", type=float, default=0.1)
    args = ap.parse_args()

    result = run(
        project_root=args.project_root,
        prompt_file=args.prompt_file,
        handoff_id=args.handoff_id,
        result_path=args.result_path,
        allocator_role=args.allocator_role,
        allocator_client=args.allocator_client,
        flow=args.flow,
        role=args.role,
        step_key=args.step_key,
        no_signal=args.no_signal,
        temperature=args.temperature,
    )
    return 0 if result["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
