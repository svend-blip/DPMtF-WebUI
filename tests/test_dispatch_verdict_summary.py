"""Tests for dispatch.py verdict block rendering (handoff 130, WORK 2).

When a callback deliverable is a verdict (a ``**Status:** APPROVED|REJECTED``
line), dispatch.py must fill the callback content_template's
<verdict_summary> / <next_action> / <stop> blocks from it (migration 100).
Both fixtures render through the same function: _fill_verdict_blocks.
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "bridgeV002"))
sys.path.insert(0, ROOT)

import dispatch  # noqa: E402

DB_PATH = os.path.join(ROOT, "databases", "dpmtf.db")

APPROVED_FIXTURE = """<handoff_id>129</handoff_id>

# Verdict 129

**Status:** APPROVED

## Outcome
All evidence verified. Proceed to WORK 2 and WORK 3.
"""

REJECTED_FIXTURE = """<handoff_id>100</handoff_id>

# Verdict 100

**Status:** REJECTED

## Reason
The defect family remains unfixed in WORK 2.
The implementer must rework the same WORK item.
"""


def _callback_template():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT content_template FROM bridge_convention_rules "
            "WHERE rule_key='callback'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "callback rule missing"
    return row[0]


def _render(fixture_text, tmp_path):
    verdict_file = tmp_path / "fixture-verdict.md"
    verdict_file.write_text(fixture_text, encoding="utf-8")
    return dispatch._fill_verdict_blocks(_callback_template(),
                                           str(verdict_file))


def test_approved_verdict_fills_all_three_blocks(tmp_path):
    rendered = _render(APPROVED_FIXTURE, tmp_path)
    # <verdict_summary> block: status + approval text + work item
    assert "<verdict_summary>" in rendered
    assert "status: APPROVED" in rendered
    assert "approved" in rendered
    assert "work_item: WORK 2" in rendered
    # <next_action> block: APPROVED -> author the next handoff
    assert "<next_action>" in rendered
    assert "author the next handoff" in rendered
    # <stop> block present (static in the template)
    assert "<stop>" in rendered
    # No unfilled placeholders leak
    assert "{verdict_status}" not in rendered
    assert "{verdict_lines}" not in rendered
    assert "{next_action}" not in rendered
    assert "{work_item}" not in rendered


def test_rejected_verdict_fills_all_three_blocks(tmp_path):
    rendered = _render(REJECTED_FIXTURE, tmp_path)
    # <verdict_summary> block: status + rejection reason lines + work item
    assert "<verdict_summary>" in rendered
    assert "status: REJECTED" in rendered
    assert "The defect family remains unfixed in WORK 2." in rendered
    assert "work_item: WORK 2" in rendered
    # <next_action> block: REJECTED -> rework the same WORK item
    assert "<next_action>" in rendered
    assert "author a rework handoff for the same WORK item" in rendered
    # <stop> block present
    assert "<stop>" in rendered
    # No unfilled placeholders leak
    assert "{verdict_status}" not in rendered
    assert "{verdict_lines}" not in rendered
    assert "{next_action}" not in rendered
    assert "{work_item}" not in rendered
