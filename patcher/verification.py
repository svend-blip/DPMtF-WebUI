"""Post-apply verification pipeline (spec §18–§21).

The verification pipeline runs ONLY after a SUCCESSFUL apply() — check()
never triggers verification, because check() writes nothing (spec §15).

Two layers, engine-agnostic:

  1. Syntax check (spec §20, handoff §2a) — always available. Every
     changed file whose name ends in ".py" is compiled in-process via
     `compile(source, path, "exec")`. The in-process form leaves no
     .pyc / __pycache__ artefacts in the target repository (temp-repo
     fixtures assert byte-identical trees; a stray cache directory
     would be a real-world tree mutation too). Non-Python files are
     skipped. A failure produces a structured
     `{"syntax": "failed", "errors": [...]}` entry in
     `PatchResult.verification` AND escalates the result's `error_code`
     to `PATCH_APPLIED_SYNTAX_FAILED`. The applied change is LEFT IN
     PLACE — the surrounding DPMtF policy (not the patcher) decides
     whether to revert (spec §20).

  2. Configured commands (spec §21, handoff §2b) — opt-in. When the
     request's `verification` dict carries a `commands` list, each
     command is executed verbatim with `shell=True`, `cwd=repo_path`,
     and the exit code / stdout tail / stderr tail are reported
     EXACTLY as measured. The patcher never interprets a failure
     semantically. A nonzero exit code escalates the result to
     `PATCH_APPLIED_TEST_FAILED`. Commands run in request order; the
     pipeline stops after the first nonzero exit (commands that did
     not run are reported as `skipped`). No configured commands → no
     command execution; syntax check still runs.

Nothing in this module is hardcoded as mandatory (spec §18): pytest
and Ruff are never invoked unless they arrive as configured command
strings in the request.

The verification pipeline is engine-agnostic by design: engines call
`run_verification(repo_path, files_changed, verification)` after a
successful apply and merge the returned `VerificationOutcome` into
their `PatchResult`. The outcome carries:

  * `verdict`: one of `"passed"`, `"failed"`, `"not_run"`.
  * `verification_dict`: the structured dict to merge into
    `PatchResult.verification` (`{"syntax": ..., "commands": [...]}`).
  * `failure_files`: list of file paths that failed syntax check (for
    the verifier's own diagnostics; surfaced in `error`).
  * `commands_run`: list of per-command outcome dicts.
  * `new_error_code`: when the verdict is "failed", this is the
    `PATCH_APPLIED_*` constant the caller should write into
    `PatchResult.error_code`. `None` when verdict == "passed".
  * `failure_message`: a single human-readable line describing the
    first failure, suitable for `PatchResult.error`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from patcher.errors import (
    PATCH_APPLIED_SYNTAX_FAILED,
    PATCH_APPLIED_TEST_FAILED,
)


# Maximum number of bytes of stdout / stderr we retain per command.
# Large test-suite output is not interesting for the patcher; we keep
# the tail only so the report stays machine-readable.
_STDOUT_TAIL_BYTES = 4096
_STDERR_TAIL_BYTES = 4096


# ── Outcome type ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CommandOutcome:
    """Per-command measurement, reported VERBATIM.

    `exit_code` is the integer subprocess returned (negative on signal,
    positive on normal exit, 0 on success). `stdout_tail` /
    `stderr_tail` are the LAST `_STDOUT_TAIL_BYTES` bytes of the
    stream, decoded with `errors="replace"`. `status` is `"executed"`
    when the command ran or `"skipped"` when an earlier command failed
    and the pipeline stopped.
    """

    command: str
    status: str  # "executed" or "skipped"
    exit_code: Optional[int] = None
    stdout_tail: str = ""
    stderr_tail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "command": self.command,
            "status": self.status,
        }
        if self.status == "executed":
            out["exit_code"] = self.exit_code
            out["stdout_tail"] = self.stdout_tail
            out["stderr_tail"] = self.stderr_tail
        return out


@dataclass(frozen=True)
class VerificationOutcome:
    """The merged outcome of running the verification pipeline.

    The patcher engines merge this into their PatchResult:

      * `verdict == "passed"` → status stays "applied" /
        "no_change"; error_code stays PATCH_APPLIED.
      * `verdict == "failed"` → PatchResult.error_code is overridden
        with `new_error_code`; PatchResult.error is overridden with
        `failure_message`.
      * `verdict == "not_run"` → PatchResult.verification is left as
        None (no commands, no changed Python files → no point in
        advertising "syntax not_run").

    The `verification_dict` field is what the engine should write into
    `PatchResult.verification` — its shape is stable for the CLI's
    downstream consumers.
    """

    verdict: str  # "passed" | "failed" | "not_run"
    verification_dict: Dict[str, Any] = field(default_factory=dict)
    failure_files: List[str] = field(default_factory=list)
    commands_run: List[CommandOutcome] = field(default_factory=list)
    new_error_code: Optional[str] = None
    failure_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "verdict": self.verdict,
            "verification_dict": dict(self.verification_dict),
            "failure_files": list(self.failure_files),
            "commands_run": [c.to_dict() for c in self.commands_run],
        }
        if self.new_error_code is not None:
            out["new_error_code"] = self.new_error_code
        if self.failure_message is not None:
            out["failure_message"] = self.failure_message
        return out


# ── Public entry point ──────────────────────────────────────────────────


def run_verification(
    repo_path: str,
    files_changed: Sequence[str],
    verification: Optional[Dict[str, Any]],
) -> VerificationOutcome:
    """Run the post-apply verification pipeline.

    Args:
        repo_path: absolute path to the repository root. Configured
            commands run with `cwd=repo_path`.
        files_changed: list of repo-relative paths the patch mutated.
            Syntax check runs on each `.py` file in this list. Non-Python
            files are skipped.
        verification: the `verification` field of the PatchRequest, or
            None. When None or empty, no command execution happens; only
            the always-on syntax check runs against `files_changed`.

    Returns:
        VerificationOutcome — see the dataclass docstring for the
        merge contract. The pipeline ALWAYS returns a value; it never
        raises for caller mistakes (an invalid `verification` shape
        becomes a verdict of "not_run" with a note in the verification
        dict).
    """
    # ── Layer 1: syntax check (always) ────────────────────────────────
    syntax_files = [f for f in files_changed if f.endswith(".py")]
    syntax_failures: List[Dict[str, str]] = []
    for rel in syntax_files:
        full = Path(repo_path) / rel
        if not full.exists():
            # The patch should have created / mutated the file, but be
            # defensive: a missing file means we cannot syntax-check.
            syntax_failures.append({
                "file": rel,
                "error": "file does not exist after patch",
            })
            continue
        try:
            source = full.read_text(encoding="utf-8")
        except OSError as exc:
            syntax_failures.append({
                "file": rel,
                "error": f"cannot read file: {exc}",
            })
            continue
        try:
            compile(source, str(full), "exec")
        except SyntaxError as exc:
            syntax_failures.append({
                "file": rel,
                "error": (
                    f"line {exc.lineno}: {exc.msg} "
                    f"({exc.filename or rel})"
                ),
            })
        except ValueError as exc:
            # `compile()` raises ValueError for null bytes / other
            # source-encoding edge cases. Treat as a syntax failure.
            syntax_failures.append({
                "file": rel,
                "error": f"compile error: {exc}",
            })

    # ── Layer 2: configured commands (opt-in) ────────────────────────
    commands_run: List[CommandOutcome] = []
    command_failures: List[Dict[str, Any]] = []

    configured = _extract_commands(verification)
    if configured is None:
        # verification dict was malformed (not a dict, or "commands"
        # not a list of strings). Record nothing and skip the layer.
        configured = []

    first_command_failure: Optional[Dict[str, Any]] = None
    for cmd in configured:
        if first_command_failure is not None:
            # Earlier command failed; per spec §21 / handoff §2b we
            # stop and report the remaining commands as skipped.
            commands_run.append(CommandOutcome(
                command=cmd,
                status="skipped",
            ))
            continue

        outcome = _run_configured_command(repo_path, cmd)
        commands_run.append(outcome)
        if outcome.exit_code != 0:
            first_command_failure = {
                "command": cmd,
                "exit_code": outcome.exit_code,
                "stderr_tail": outcome.stderr_tail,
            }
            command_failures.append({
                "command": cmd,
                "exit_code": outcome.exit_code,
                "stderr_tail": outcome.stderr_tail,
            })

    # ── Build the outcome ────────────────────────────────────────────
    # Verdict precedence: configured command failure > syntax failure >
    # passed > not_run. `not_run` only fires when nothing was actually
    # checked (no Python files changed AND no commands configured).
    if first_command_failure is not None:
        failure_files = [f["file"] for f in syntax_failures]
        msg = (
            f"configured command {first_command_failure['command']!r} "
            f"exited with code {first_command_failure['exit_code']}"
        )
        return VerificationOutcome(
            verdict="failed",
            verification_dict={
                "syntax": "failed" if syntax_failures else "passed",
                "syntax_errors": syntax_failures,
                "commands": [c.to_dict() for c in commands_run],
                "command_failures": command_failures,
            },
            failure_files=failure_files,
            commands_run=commands_run,
            new_error_code=PATCH_APPLIED_TEST_FAILED,
            failure_message=msg,
        )

    if syntax_failures:
        return VerificationOutcome(
            verdict="failed",
            verification_dict={
                "syntax": "failed",
                "syntax_errors": syntax_failures,
                "commands": [c.to_dict() for c in commands_run],
            },
            failure_files=[f["file"] for f in syntax_failures],
            commands_run=commands_run,
            new_error_code=PATCH_APPLIED_SYNTAX_FAILED,
            failure_message=(
                f"syntax verification failed for {len(syntax_failures)} "
                f"file(s): {', '.join(f['file'] for f in syntax_failures)}"
            ),
        )

    # No failure. Decide whether to advertise verification at all.
    has_work = bool(syntax_files) or bool(commands_run)
    if not has_work:
        return VerificationOutcome(
            verdict="not_run",
            verification_dict={
                "syntax": "not_run",
                "commands": [],
            },
            failure_files=[],
            commands_run=commands_run,
            new_error_code=None,
            failure_message=None,
        )

    return VerificationOutcome(
        verdict="passed",
        verification_dict={
            "syntax": "passed" if syntax_files else "not_run",
            "commands": [c.to_dict() for c in commands_run],
        },
        failure_files=[],
        commands_run=commands_run,
        new_error_code=None,
        failure_message=None,
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _extract_commands(
    verification: Optional[Dict[str, Any]],
) -> Optional[List[str]]:
    """Return the list of configured commands, or None if the input was
    malformed.

    The patcher treats a malformed `verification` dict as "no commands
    configured" rather than failing the whole apply — the syntax check
    still runs, and the orchestrator can decide what to do with the
    malformed metadata. This matches the spec's principle that the
    patcher reports rather than interprets.
    """
    if verification is None:
        return None
    if not isinstance(verification, dict):
        return None
    cmds = verification.get("commands")
    if cmds is None:
        return None
    if not isinstance(cmds, list):
        return None
    out: List[str] = []
    for c in cmds:
        if not isinstance(c, str) or not c:
            continue
        out.append(c)
    return out


def _run_configured_command(repo_path: str, command: str) -> CommandOutcome:
    """Execute `command` verbatim with `shell=True` and `cwd=repo_path`.

    Per spec §21 / handoff §2b: exit code + stdout tail + stderr tail
    are captured VERBATIM. The patcher never interprets the command's
    semantics — the orchestrator decides what a failure means.
    """
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=repo_path,
            capture_output=True,
            text=True,
            # The patcher must report exit codes verbatim; do NOT pass
            # `check=True` (that would raise CalledProcessError on a
            # nonzero exit and lose the exit code).
            check=False,
        )
    except OSError as exc:
        # The shell could not be invoked at all (e.g. /bin/sh missing).
        # We report this as a failed execution with no exit code rather
        # than crashing the whole pipeline.
        return CommandOutcome(
            command=command,
            status="executed",
            exit_code=None,
            stdout_tail="",
            stderr_tail=f"command could not be launched: {exc}",
        )

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    stdout_tail = _tail_text(stdout, _STDOUT_TAIL_BYTES)
    stderr_tail = _tail_text(stderr, _STDERR_TAIL_BYTES)

    return CommandOutcome(
        command=command,
        status="executed",
        exit_code=proc.returncode,
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
    )


def _tail_text(text: str, max_bytes: int) -> str:
    """Return the LAST `max_bytes` bytes of `text`, decoded safely.

    Slicing by bytes (not characters) keeps the implementation
    predictable across encodings; for multi-byte tails we may split a
    codepoint, but the patcher only feeds this back through JSON, so
    a few broken characters at the boundary are harmless.
    """
    if len(text.encode("utf-8", errors="replace")) <= max_bytes:
        return text
    # Encode, slice, decode. `errors="replace"` keeps the contract
    # strict — we never raise from a tail operation.
    encoded = text.encode("utf-8", errors="replace")
    return encoded[-max_bytes:].decode("utf-8", errors="replace")


__all__ = [
    "CommandOutcome",
    "VerificationOutcome",
    "run_verification",
]