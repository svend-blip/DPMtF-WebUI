"""Registered checks — verification commands for post-edit validation.

Each check runs a specific validator (py_compile, node --check, etc.)
and returns a structured result.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass


@dataclass
class CheckResult:
    check: str
    file: str
    status: str  # PASS | FAIL
    detail: str = ""


def py_compile_check(file_path: str) -> CheckResult:
    """Run python3 -m py_compile on a file."""
    rel = Path(file_path).name
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", file_path],
            capture_output=True, text=True, timeout=30,
        )
        passed = result.returncode == 0
        return CheckResult(
            check="py_compile",
            file=rel,
            status="PASS" if passed else "FAIL",
            detail="" if passed else result.stderr.strip(),
        )
    except Exception as e:
        return CheckResult(check="py_compile", file=rel, status="FAIL", detail=str(e))


def node_check(file_path: str) -> CheckResult:
    """Run node --check on a JavaScript file."""
    rel = Path(file_path).name
    try:
        result = subprocess.run(
            ["node", "--check", file_path],
            capture_output=True, text=True, timeout=30,
        )
        passed = result.returncode == 0
        return CheckResult(
            check="node_check",
            file=rel,
            status="PASS" if passed else "FAIL",
            detail="" if passed else result.stderr.strip(),
        )
    except FileNotFoundError:
        return CheckResult(check="node_check", file=rel, status="FAIL", detail="node not found")
    except Exception as e:
        return CheckResult(check="node_check", file=rel, status="FAIL", detail=str(e))


def bash_syntax_check(file_path: str) -> CheckResult:
    """Run bash -n on a shell script."""
    rel = Path(file_path).name
    try:
        result = subprocess.run(
            ["bash", "-n", file_path],
            capture_output=True, text=True, timeout=30,
        )
        passed = result.returncode == 0
        return CheckResult(
            check="bash_syntax",
            file=rel,
            status="PASS" if passed else "FAIL",
            detail="" if passed else result.stderr.strip(),
        )
    except Exception as e:
        return CheckResult(check="bash_syntax", file=rel, status="FAIL", detail=str(e))


# Registry of available checks
CHECKS = {
    "py_compile": py_compile_check,
    "node_check": node_check,
    "bash_syntax": bash_syntax_check,
}


def run_check(check_name: str, file_path: str) -> CheckResult:
    """Run a registered check by name."""
    fn = CHECKS.get(check_name)
    if not fn:
        return CheckResult(check=check_name, file=Path(file_path).name, status="FAIL",
                          detail=f"unknown check: {check_name}")
    return fn(file_path)


def run_checks_for_files(changed: list[str], project_root: str) -> list[CheckResult]:
    """Run appropriate checks for each changed file based on extension."""
    results = []
    for rel in sorted(changed):
        abs_path = str(Path(project_root) / rel)
        if rel.endswith(".py"):
            results.append(py_compile_check(abs_path))
        elif rel.endswith(".js"):
            results.append(node_check(abs_path))
        elif rel.endswith(".sh"):
            results.append(bash_syntax_check(abs_path))
    return results
