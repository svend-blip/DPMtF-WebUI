#!/usr/bin/env python3
"""Command-line tool exposure for the Deterministic Patcher.

Spec §25 — callable from any coding frontend or runtime DPMtF uses.
The CLI exposes two subcommands:

  patch_check    — dry-run validation, writes nothing
  patch_apply    — full apply with post-apply verification

The request is read from a file argument or from stdin (when the
argument is `-` or absent). The full PatchResult is written as JSON
to stdout; diagnostic / status messages go to stderr. Exit codes
mirror the PatchResult status:

  0  successful outcome (PATCH_APPLIED, a successful check, or a
     no-change outcome)
  1  any PATCH_* failure status (including PATCH_APPLIED_SYNTAX_FAILED
     and PATCH_APPLIED_TEST_FAILED — the change is on disk, the patcher
     reports verbatim)
  2  invalid invocation (unreadable / invalid JSON, unknown subcommand,
     missing repo_path)

The CLI does NOT import config.py, does NOT hardcode any path, and
takes its `repo_path` exclusively from the request payload — this is
explicitly required by the handoff constraint and is the same
discipline the rest of the patcher package follows (CLAUDE.md
auto-fail #3).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import NoReturn, Optional, Tuple


# Ensure the project root is on sys.path so the patcher package is
# importable when the CLI is invoked from anywhere. We deliberately do
# NOT hardcode a /home/svend/... path (CLAUDE.md auto-fail #3) — the
# project root is the parent of the `scripts/` directory this file
# lives in, regardless of where that lives on disk.
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent.parent
_PROJECT_ROOT_STR = str(_PROJECT_ROOT)
if _PROJECT_ROOT_STR not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_STR)

from patcher import DeterministicPatcher, PatchRequest  # noqa: E402
from patcher.errors import (  # noqa: E402
    PATCH_APPLIED,
    PATCH_APPLIED_SYNTAX_FAILED,
    PATCH_APPLIED_TEST_FAILED,
    PATCH_APPLIED_LINT_FAILED,
    PATCH_INVALID,
    PATCH_UNSUPPORTED_OPERATION,
    PATCH_FILE_NOT_FOUND,
    PATCH_PATH_REJECTED,
    PATCH_BASE_MISMATCH,
    PATCH_TARGET_AMBIGUOUS,
    PATCH_TARGET_NOT_FOUND,
    PATCH_CONFLICT,
    PATCH_APPLY_FAILED,
    PATCH_INTERNAL_ERROR,
)
from patcher.models import request_from_dict  # noqa: E402


# Statuses that count as "success" (exit code 0) for the CLI mapping.
_SUCCESS_STATUSES = frozenset({
    PATCH_APPLIED,
})

_SUCCESS_FINAL_STATUSES = frozenset({
    "applied",
    "no_change",
    "check_passed",
})


# ── I/O helpers ─────────────────────────────────────────────────────────


def _read_request(path_arg: Optional[str]) -> dict:
    """Read the request payload from a file argument, `-` (stdin), or
    stdin when the argument is absent.

    Returns the parsed JSON object. Raises ValueError on parse errors
    or read failures (the caller maps that to exit code 2).
    """
    if path_arg is None or path_arg == "-":
        # stdin
        try:
            raw = sys.stdin.read()
        except OSError as exc:
            raise ValueError(f"cannot read request from stdin: {exc}")
        source = "<stdin>"
    else:
        try:
            with open(path_arg, "r", encoding="utf-8") as f:
                raw = f.read()
        except OSError as exc:
            raise ValueError(f"cannot read request from {path_arg!r}: {exc}")
        source = path_arg

    if not raw.strip():
        raise ValueError(f"request payload is empty (source: {source})")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in request ({source}): {exc}")

    if not isinstance(data, dict):
        raise ValueError(
            f"request payload must be a JSON object (source: {source}); "
            f"got {type(data).__name__}"
        )
    return data


def _die(message: str, code: int = 2) -> NoReturn:
    """Write `message` to stderr and exit with `code`."""
    print(f"patcher_cli: {message}", file=sys.stderr)
    sys.exit(code)


def _emit_result(result_dict: dict) -> None:
    """Write the full PatchResult to stdout as JSON.

    Nothing else is written to stdout — diagnostics go to stderr. This
    is what makes the CLI machine-readable: callers can pipe stdout
    straight into `json.loads`.
    """
    json.dump(result_dict, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def _exit_for(result) -> int:
    """Map a PatchResult to the documented CLI exit code.

    The mapping follows the handoff / spec §25 contract:

      0 — successful outcome (applied / no_change / check_passed /
          error_code == PATCH_APPLIED)
      1 — any PATCH_* failure status, INCLUDING
          PATCH_APPLIED_SYNTAX_FAILED and PATCH_APPLIED_TEST_FAILED
          (the patcher's job ends at "report verbatim"; the orchestrator
          decides what to do next)
      2 — never reached here (that's the "invalid invocation" class
          and is handled by the caller before we get a PatchResult)
    """
    # error_code is the canonical signal; fall back to status only for
    # legacy check_passed / no_change cases that have error_code None.
    if result.error_code == PATCH_APPLIED:
        return 0
    if result.status in _SUCCESS_FINAL_STATUSES and result.error_code is None:
        return 0
    # Anything else is a failure that the orchestrator must see.
    return 1


# ── Subcommand handlers ────────────────────────────────────────────────


def _cmd_check(args: argparse.Namespace) -> int:
    data = _read_request(args.request)
    try:
        req = request_from_dict(data)
    except ValueError as exc:
        _die(f"invalid PatchRequest: {exc}", code=2)

    if not req.repo_path:
        _die("repo_path is required in the request payload", code=2)

    patcher = DeterministicPatcher()
    result = patcher.check(req)
    _emit_result(result.to_dict())
    return _exit_for(result)


def _cmd_apply(args: argparse.Namespace) -> int:
    data = _read_request(args.request)
    try:
        req = request_from_dict(data)
    except ValueError as exc:
        _die(f"invalid PatchRequest: {exc}", code=2)

    if not req.repo_path:
        _die("repo_path is required in the request payload", code=2)

    patcher = DeterministicPatcher()
    result = patcher.apply(req)
    _emit_result(result.to_dict())
    return _exit_for(result)


# ── Argparse ────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patcher_cli",
        description=(
            "Deterministic Patcher CLI — execute PatchRequests "
            "without direct repository mutation by the LLM. "
            "See docs/specs/DETERMINISTIC_PATCHER_USAGE.md."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:\n"
            "  0  successful outcome (applied, no_change, check_passed)\n"
            "  1  any PATCH_* failure status — including\n"
            "       PATCH_APPLIED_SYNTAX_FAILED,\n"
            "       PATCH_APPLIED_TEST_FAILED, PATCH_CONFLICT,\n"
            "       PATCH_PATH_REJECTED, etc.\n"
            "  2  invalid invocation (unreadable/invalid JSON, unknown\n"
            "       subcommand, missing repo_path in the request).\n"
            "\n"
            "stdout: full PatchResult as JSON. Nothing else.\n"
            "stderr: diagnostics."
        ),
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    check_p = sub.add_parser(
        "patch_check",
        help="Dry-run a PatchRequest without mutating the repository.",
        description=(
            "Reads a PatchRequest (JSON object) from REQUEST or stdin "
            "and writes the PatchResult to stdout. NEVER mutates the "
            "repository."
        ),
    )
    check_p.add_argument(
        "request",
        nargs="?",
        default=None,
        help=(
            "Path to a JSON file containing the PatchRequest, or "
            "'-' / omitted to read from stdin."
        ),
    )
    check_p.set_defaults(func=_cmd_check)

    apply_p = sub.add_parser(
        "patch_apply",
        help="Apply a PatchRequest, running the verification pipeline.",
        description=(
            "Reads a PatchRequest (JSON object) from REQUEST or stdin, "
            "applies it, runs the post-apply verification pipeline "
            "(syntax check + configured commands), and writes the "
            "PatchResult to stdout."
        ),
    )
    apply_p.add_argument(
        "request",
        nargs="?",
        default=None,
        help=(
            "Path to a JSON file containing the PatchRequest, or "
            "'-' / omitted to read from stdin."
        ),
    )
    apply_p.set_defaults(func=_cmd_apply)

    return parser


# ── Entry point ────────────────────────────────────────────────────────


def main(argv: Optional[Tuple[str, ...]] = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse already printed the error and called sys.exit; mirror
        # its code into our exit-code mapping (SystemExit.code is the
        # argparse default — 2 — for usage errors, which matches our
        # "invalid invocation" exit code).
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        return int(args.func(args))
    except ValueError as exc:
        _die(str(exc), code=2)
    except KeyboardInterrupt:
        _die("interrupted", code=2)
    except BrokenPipeError:
        # Downstream pipe closed (e.g. `| head`); exit cleanly.
        return 1

    # Unreachable: every code path above either returns or sys.exits.
    return 2  # pragma: no cover - defensive


if __name__ == "__main__":
    sys.exit(main())