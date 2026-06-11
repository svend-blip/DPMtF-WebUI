#!/usr/bin/env python3
"""
initialize_target_project_governance.py

Copy the DPMtF governance-template package into a target project at
<target>/docs/dpmtf/ so that every project starts with a shared
governance baseline.

Usage:
    python3 scripts/initialize_target_project_governance.py <target-path> [--dry-run] [--overwrite]
"""

import argparse
import datetime
import os
import shutil
import sys


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TEMPLATE_SOURCE = os.path.join(PROJECT_ROOT, "docs", "governance-templates")

ALLOWED_ROOTS = [
    "/home/svend/",
    "/mnt/projectarchive/",
]

DANGEROUS_PATHS = {"/", "/home/svend", "/mnt"}

DEST_SUBDIR = "docs/dpmtf"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validate_target_path(path: str) -> list[str]:
    """Return a list of error messages (empty if valid)."""
    errors: list[str] = []

    if not os.path.isabs(path):
        errors.append(f"Path must be absolute: {path}")
        return errors  # no point checking further

    if not os.path.exists(path):
        errors.append(f"Path does not exist: {path}")

    if not os.path.isdir(path):
        errors.append(f"Path is not a directory: {path}")

    resolved = os.path.realpath(path)
    if resolved in DANGEROUS_PATHS:
        errors.append(f"Target path is too broad / dangerous: {resolved}")

    # Check allowed roots
    if not any(resolved.startswith(root) for root in ALLOWED_ROOTS):
        errors.append(
            f"Target path {resolved} is outside allowed roots. "
            f"Allowed: {', '.join(ALLOWED_ROOTS)}"
        )

    return errors


def format_path(path: str) -> str:
    """Shorten long paths for terminal output."""
    if len(path) > 80:
        return "..." + path[-77:]
    return path


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def initialize_governance(
    target_path: str,
    dry_run: bool = False,
    overwrite: bool = False,
) -> dict:
    """
    Copy governance templates into <target>/docs/dpmtf/.

    Returns a summary dict with keys: copied, skipped, backed_up, errors.
    """
    resolved = os.path.realpath(target_path)
    dest_dir = os.path.join(resolved, DEST_SUBDIR)

    summary = {
        "target": resolved,
        "dest_dir": dest_dir,
        "copied": [],
        "skipped": [],
        "backed_up": [],
        "errors": [],
    }

    # Validate source
    if not os.path.isdir(TEMPLATE_SOURCE):
        summary["errors"].append(f"Template source not found: {TEMPLATE_SOURCE}")
        return summary

    # Gather source files (non-hidden, regular files only)
    try:
        source_files = [
            f for f in os.listdir(TEMPLATE_SOURCE)
            if not f.startswith(".")
            and os.path.isfile(os.path.join(TEMPLATE_SOURCE, f))
        ]
    except OSError as exc:
        summary["errors"].append(f"Cannot read template source: {exc}")
        return summary

    if not source_files:
        summary["errors"].append("No template files found in source directory.")
        return summary

    # Ensure destination exists (skip in dry-run — write nothing)
    if not dry_run:
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except OSError as exc:
            summary["errors"].append(f"Cannot create destination directory: {exc}")
            return summary

    timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")

    for filename in sorted(source_files):
        src_path = os.path.join(TEMPLATE_SOURCE, filename)
        dst_path = os.path.join(dest_dir, filename)

        if os.path.exists(dst_path) and not overwrite:
            summary["skipped"].append(filename)
            continue

        if os.path.exists(dst_path) and overwrite:
            # Backup before overwriting
            backup_dir = os.path.join(dest_dir, "backups", timestamp)
            try:
                os.makedirs(backup_dir, exist_ok=True)
                backup_path = os.path.join(backup_dir, filename)
                shutil.copy2(dst_path, backup_path)  # backup existing dest file
                summary["backed_up"].append(filename)
            except OSError as exc:
                summary["errors"].append(
                    f"Backup failed for {filename}: {exc}"
                )
                continue

        try:
            if dry_run:
                # In dry-run mode we just record the intent
                summary["copied"].append(filename)
            else:
                shutil.copy2(src_path, dst_path)
                summary["copied"].append(filename)
        except OSError as exc:
            summary["errors"].append(f"Failed to copy {filename}: {exc}")

    return summary


def print_summary(summary: dict, dry_run: bool) -> None:
    """Print a human-readable summary to stdout."""
    prefix = "[DRY RUN] " if dry_run else ""

    print()
    print("=" * 60)
    print(f"{prefix}Governance Initializer Summary")
    print("=" * 60)
    print(f"Target path   : {summary['target']}")
    print(f"Destination   : {summary['dest_dir']}")
    print()

    if summary["copied"]:
        print(f"Files copied  : {len(summary['copied'])}")
        for f in summary["copied"]:
            print(f"  + {f}")

    if summary["skipped"]:
        print(f"Files skipped : {len(summary['skipped'])} (SKIPPED_EXISTING)")
        for f in summary["skipped"]:
            print(f"  ~ {f}")

    if summary["backed_up"]:
        print(f"Files backed up: {len(summary['backed_up'])}")
        for f in summary["backed_up"]:
            print(f"  < {f}")

    if summary["errors"]:
        print(f"Errors        : {len(summary['errors'])}")
        for e in summary["errors"]:
            print(f"  ! {e}")
    else:
        print("Errors        : 0")

    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="initialize_target_project_governance",
        description=(
            "Initialize a target project with the DPMtF governance-template "
            "package by copying templates from docs/governance-templates/ "
            "into <target>/docs/dpmtf/."
        ),
    )
    parser.add_argument(
        "target_path",
        help="Absolute path to the target project directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be copied/skipped/backed up without writing files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help=(
            "Overwrite existing files. Before overwriting, a backup is written "
            "to <target>/docs/dpmtf/backups/<timestamp/>."
        ),
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    target = os.path.realpath(args.target_path)

    # Validate
    errors = validate_target_path(target)
    if errors:
        print("ERROR: Target path validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    summary = initialize_governance(
        target_path=target,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
    )

    print_summary(summary, dry_run=args.dry_run)

    if summary["errors"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
