#!/usr/bin/env python3
"""Probe: verify artifact_root resolution in convention template rendering."""

import sqlite3
import sys
from pathlib import Path

import config

DB_PATH = config.get_db_path()
BRIDGE_DIR = config.get_bridge_dir()


def get_effective_root(row):
    """Return the artifact_root if non-NULL, else the flow_key."""
    return row["artifact_root"] or row["flow_key"]


def render_template(template, artifact_root):
    """Substitute placeholders the way dispatch.py renders convention templates.

    Replaces {bridge_dir}, {flow_key}, and {artifact_root} with their values.
    """
    result = template.replace("{bridge_dir}", BRIDGE_DIR)
    result = result.replace("{flow_key}", artifact_root)
    result = result.replace("{artifact_root}", artifact_root)
    return result


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch agent_delivery template
    cur.execute(
        "SELECT content_template FROM bridge_convention_rules WHERE rule_key = 'agent_delivery'"
    )
    row = cur.fetchone()

    if not row:
        print("FATAL: agent_delivery template not found", file=sys.stderr)
        sys.exit(1)

    template = row["content_template"]

    # ── Test 1: ELOOP flow (artifact_root = '1000') ─────────────────
    eloop_root = "1000"  # known from 074_two_flow_ploop_eloop.sql
    eloop_rendered = render_template(template, eloop_root)

    expected_path = f"{BRIDGE_DIR}/1000/runs/"
    bad_path = f"{BRIDGE_DIR}/1000-02-ELOOP/runs/"

    assert expected_path in eloop_rendered, (
        f"ELOOP_ROOT_FAIL: rendered text does not contain {expected_path}"
    )
    assert bad_path not in eloop_rendered, (
        f"ELOOP_ROOT_FAIL: rendered text contains {bad_path}"
    )
    print("ELOOP_ROOT_OK")

    # ── Test 2: NULL-artifact_root flow ───────────────────────────
    cur = conn.cursor()
    cur.execute(
        "SELECT flow_key, artifact_root FROM bridge_flows "
        "WHERE artifact_root IS NULL LIMIT 1"
    )
    null_row = cur.fetchone()
    conn.close()

    if not null_row:
        print("FATAL: no NULL-artifact_root flow found for probe", file=sys.stderr)
        sys.exit(1)

    null_key = null_row["flow_key"]
    null_root = get_effective_root(null_row)
    null_rendered = render_template(template, null_root)

    null_path = f"{BRIDGE_DIR}/{null_root}/runs/"

    assert null_path in null_rendered, (
        f"FALLBACK_FAIL: rendered text does not contain {null_path}"
    )
    print("FALLBACK_OK")


if __name__ == "__main__":
    main()
