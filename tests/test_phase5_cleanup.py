"""Phase-5 cleanup invariants (Run 017).

Run 017 retired the absorbed governance originals (D1 repoint via
migration 068, D3 git rm of 35 files). This test pins the post-run
invariants so a regression in the repoint OR a re-introduction of a
deleted file is caught immediately:

  -k snapshot    : the resolution snapshot over all 46 active steps
                    equals the pre-068 baseline (count, md5, JSON values).
  -k file_exists : every active step's resolved governance_file AND
                    every active role's governance_file points at a
                    file that exists on disk.
  -k no_dangling : no active role references a retired/retired-stale
                    filename; the two D2 code fixes hold (scheduler.py
                    no longer carries the literal 451 fallback; dispatch.py
                    line 3462's comment no longer names a 4xx/5xx filename).

Reference: /home/svend/flows/preferred_cloud_harness/runs/017/GOAL.md
(section 1 D4 and D2; section 4 testgoals TG4, TG5, TG6, snapshot TG).
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOV_DIR = PROJECT_ROOT / "docs" / "governance-templates-v2"
DB_PATH = PROJECT_ROOT / "databases" / "dpmtf.db"

# Mirror the runtime resolver's sys.path layout
# (scripts/bridgeV002/execution_config.py:23-39).
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "bridgeV002"))

# ---------------------------------------------------------------------------
# Embedded PRE-068 snapshot fixture (verbatim from 066-result.md).
# ---------------------------------------------------------------------------
# Recorded at migration state 067 (068 NOT yet applied), using the SAME
# resolver the runtime uses. The values must NOT move after D1+D3:
# step-level shadows role-level everywhere it matters, so the snapshot is
# identical PRE-068 and POST-068+deletion (Run 017 §1 D4 / §5 reference).
#
# Serialization rule (must match when recomputing):
#   json.dumps(mapping, sort_keys=True, separators=(",", ":"))
#   md5 over canonical.encode("utf-8")
#   length: 2504 bytes
#   md5:    5b325af5d94e7b54da029ac901be277f
#   count:  46 active steps
_PRE_068_SNAPSHOT_JSON = (
    '{"cloud_llm/archi01-imple01":"ARCHITECT.md",'
    '"cloud_llm/imple01-review01":"IMPLEMENTOR.md",'
    '"cloud_llm/review01-review02":"TECHNICAL_REVIEW.md",'
    '"cloud_llm/review02-human":"GOVERNANCE_REVIEW.md",'
    '"cloud_pay/archi01-imple01":"ARCHITECT.md",'
    '"cloud_pay/imple01-review01":"IMPLEMENTOR.md",'
    '"cloud_pay/review01-review02":"TECHNICAL_REVIEW.md",'
    '"cloud_pay/review02-human":"GOVERNANCE_REVIEW.md",'
    '"lightworker/human-imple01LW":"HUMAN.md",'
    '"lightworker/imple01LW-review01LW":"IMPLEMENTOR_REMOTE_WORKER.md",'
    '"lightworker/review01LW-human":"REVIEW_REMOTE_WORKER.md",'
    '"llama_SG/imple01-review01":"IMPLEMENTOR.md",'
    '"llama_SG/review01-supervisor":"REVIEW.md",'
    '"llama_SG/supervisor-imple01":"SUPERVISOR_AUTONOMOUS.md",'
    '"pi_test/human-oc_imple01":"HUMAN.md",'
    '"pi_test/human-pi_imple01":"HUMAN.md",'
    '"pi_test/oc_imple01-human":"IMPLEMENTOR.md",'
    '"pi_test/pi_imple01-human":"IMPLEMENTOR.md",'
    '"preferred_cloud/imple01-review01":"IMPLEMENTOR.md",'
    '"preferred_cloud/review01-supervisor":"REVIEW.md",'
    '"preferred_cloud/supervisor-imple01":"SUPERVISOR_AUTONOMOUS.md",'
    '"preferred_cloud_harness/imple01-review01":"IMPLEMENTOR.md",'
    '"preferred_cloud_harness/review01-supervisor":"REVIEW.md",'
    '"preferred_cloud_harness/supervisor-imple01":"SUPERVISOR_AUTONOMOUS.md",'
    '"reveng/imple-review":"IMPLEMENTOR.md",'
    '"reveng/review-supervisor":"REVERSE_ENGINEERING_REVIEW.md",'
    '"reveng/supervisor-imple":"SUPERVISOR_AUTONOMOUS.md",'
    '"strict_review/archi01-imple01":"ARCHITECT.md",'
    '"strict_review/imple01-review01":"IMPLEMENTOR.md",'
    '"strict_review/review01-review02":"TECHNICAL_REVIEW.md",'
    '"strict_review/review02-human":"GOVERNANCE_REVIEW.md",'
    '"supervised_review/imple01-review01":"IMPLEMENTOR.md",'
    '"supervised_review/review01-review02":"TECHNICAL_REVIEW.md",'
    '"supervised_review/review02-supervisor":"GOVERNANCE_REVIEW.md",'
    '"supervised_review/supervisor-imple01":"SUPERVISOR_AUTONOMOUS.md",'
    '"supervisor/human-supervisor":"HUMAN.md",'
    '"supervisor/supervisor-human":"500_SUPERVISOR.md",'
    '"trade_cockpit_scoring_v001/human-score01":null,'
    '"trade_cockpit_scoring_v001/score01-learn01":"437_TRADE_SCORE01.md",'
    '"trade_cockpit_simulation_v001/analyst01-risk01":"433_TRADE_ANALYST01.md",'
    '"trade_cockpit_simulation_v001/human-trend01":null,'
    '"trade_cockpit_simulation_v001/market01-analyst01":"432_TRADE_MARKET01.md",'
    '"trade_cockpit_simulation_v001/review01-sim01":"435_TRADE_REVIEW01.md",'
    '"trade_cockpit_simulation_v001/risk01-review01":"434_TRADE_RISK01.md",'
    '"trade_cockpit_simulation_v001/sim01-portfolio01":"436_TRADE_SIM01.md",'
    '"trade_cockpit_simulation_v001/trend01-market01":"431_TRADE_TREND01.md"}'
)

PRE_068_SNAPSHOT = json.loads(_PRE_068_SNAPSHOT_JSON)

# ---------------------------------------------------------------------------
# Retired/dead governance filenames (the 35 deleted by D3 + the predicate
# migration 068's guard uses to detect dangling references). Used by
# -k no_dangling to assert no active role still points at one of these.
# ---------------------------------------------------------------------------
_RETIRED_GOVERNANCE_FILES = frozenset({
    # 30 absorbed originals (the ones the role-level repoint covered)
    "401_STRICT_REVIEW_HUMAN.md",
    "402_STRICT_REVIEW_ARCHI01.md",
    "403_STRICT_REVIEW_IMPLE01.md",
    "404_STRICT_REVIEW_REVIEW01.md",
    "405_STRICT_REVIEW_REVIEW02.md",
    "411_CLOUD_LLM_HUMANCLOUD.md",
    "412_CLOUD_LLM_ARCHI01CLOUD.md",
    "413_CLOUD_LLM_IMPLE01CLOUD.md",
    "414_CLOUD_LLM_REVIEW01CLOUD.md",
    "415_CLOUD_LLM_REVIEW02CLOUD.md",
    "421_CLOUD_PAY_HUMANPAY.md",
    "422_CLOUD_PAY_ARCHI01PAY.md",
    "423_CLOUD_PAY_IMPLE01PAY.md",
    "424_CLOUD_PAY_REVIEW01PAY.md",
    "425_CLOUD_PAY_REVIEW02PAY.md",
    "451_SUPERVISED_REVIEW_SUPERVISOR.md",
    "452_SUPERVISED_REVIEW_IMPLE01.md",
    "453_SUPERVISED_REVIEW_REVIEW01.md",
    "454_SUPERVISED_REVIEW_REVIEW02.md",
    "461_LLAMA_SG_SUPERVISOR.md",
    "462_LLAMA_SG_IMPLE01.md",
    "463_LLAMA_SG_REVIEW01.md",
    "471_PREFERRED_CLOUD_SUPERVISOR.md",
    "472_PREFERRED_CLOUD_IMPLE01.md",
    "473_PREFERRED_CLOUD_REVIEW01.md",
    "491_REVENG_SUPERVISOR.md",
    "492_REVENG_IMPLE.md",
    "511_PREFERRED_CLOUD_HARNESS_SUPERVISOR.md",
    "512_PREFERRED_CLOUD_HARNESS_IMPLE01.md",
    "513_PREFERRED_CLOUD_HARNESS_REVIEW01.md",
    # 4 stale pre-generation skeletons (zero DB references; never existed
    # in the bridge_roles table to begin with)
    "01_HUMAN.md",
    "02_ARCHITECT.md",
    "03_IMPLEMENTOR.md",
    "04_REVIEW.md",
    # 1 dead trade-role file (zero references)
    "439_TRADE_HUMAN.md",
})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _active_steps(conn):
    """Yield (flow_key, step_key) for every active step, in stable order."""
    return list(conn.execute(
        "SELECT flow_key, step_key FROM bridge_flow_steps "
        "WHERE is_active = 1 ORDER BY flow_key, step_key",
    ).fetchall())

def _recompute_snapshot():
    """Recompute the resolution snapshot using the live resolver.

    Mirrors 066-result.md STEP 1: use resolve_execution_config with the
    (flow_key, step_key) pair from bridge_flow_steps, return only the
    governance_file value, serialize with sort_keys=True and compact
    separators."""
    from execution_config import resolve_execution_config

    mapping = {}
    conn = sqlite3.connect(str(DB_PATH))
    try:
        for flow_key, step_key in _active_steps(conn):
            cfg = resolve_execution_config(flow_key, step_key)
            mapping[f"{flow_key}/{step_key}"] = cfg.get("governance_file")
    finally:
        conn.close()
    return mapping

def _canonical_bytes(mapping):
    return json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode("utf-8")

# ---------------------------------------------------------------------------
# -k snapshot : the resolution snapshot is unchanged from the recorded one.
# ---------------------------------------------------------------------------
def test_snapshot_count_matches_recorded():
    """The recorded snapshot has exactly 46 entries."""
    assert len(PRE_068_SNAPSHOT) == 46, (
        f"fixture drift: PRE_068_SNAPSHOT has {len(PRE_068_SNAPSHOT)} entries, "
        f"the bound count is 46"
    )

def test_snapshot_md5_matches_recorded():
    """The fixture's canonical md5 is the bound value."""
    md5 = hashlib.md5(_canonical_bytes(PRE_068_SNAPSHOT)).hexdigest()
    assert md5 == "5b325af5d94e7b54da029ac901be277f", (
        f"fixture drift: fixture md5 is {md5!r}, "
        f"the bound md5 is '5b325af5d94e7b54da029ac901be277f'"
    )

def test_snapshot_canonical_byte_length_matches_recorded():
    """The fixture's canonical byte length is the bound value."""
    assert len(_canonical_bytes(PRE_068_SNAPSHOT)) == 2504, (
        f"fixture drift: canonical bytes are "
        f"{len(_canonical_bytes(PRE_068_SNAPSHOT))}, bound is 2504"
    )

def test_snapshot_recomputed_equals_recorded():
    """The 46 pre-068 steps still resolve exactly as the baseline records.

    The invariant Run 017 proved is that D1 (migration 068 role-level
    repoint) and D3 (deletion of the 35 absorbed-original files) moved
    NOTHING for the steps that existed then. Flows added since (9000,
    escalation steps) legitimately grow the mapping, so the guard is a
    subset equality over the baseline's entries — a whole-mapping pin
    would go red on every new flow while the invariant held (it did,
    2026-08-31, at 64 steps)."""
    mapping = _recompute_snapshot()
    assert len(mapping) >= 46, (
        f"active step count shrank below the baseline: {len(mapping)}"
    )
    drifted = {
        k: (mapping.get(k), v)
        for k, v in PRE_068_SNAPSHOT.items()
        if mapping.get(k) != v
    }
    assert not drifted, (
        f"pre-068 steps no longer resolve as the baseline records: "
        f"{dict(list(drifted.items())[:3])}"
    )

def test_snapshot_recomputed_md5_equals_recorded_md5():
    """The baseline subset of the recomputed snapshot matches the bound
    md5, end-to-end — same canonical serialization, restricted to the
    46 pre-068 keys so legitimate new flows cannot move it."""
    mapping = _recompute_snapshot()
    subset = {k: mapping[k] for k in PRE_068_SNAPSHOT if k in mapping}
    md5 = hashlib.md5(_canonical_bytes(subset)).hexdigest()
    assert md5 == "5b325af5d94e7b54da029ac901be277f", (
        f"recomputed baseline-subset md5 {md5!r} != bound "
        f"'5b325af5d94e7b54da029ac901be277f'"
    )

def _diff_first_n(actual, expected, n):
    """Render the first N differing entries as a short human-readable string."""
    diffs = []
    keys = sorted(set(actual) | set(expected))
    for k in keys:
        if actual.get(k) != expected.get(k):
            diffs.append(f"{k}: actual={actual.get(k)!r} expected={expected.get(k)!r}")
            if len(diffs) >= n:
                break
    return diffs

# ---------------------------------------------------------------------------
# -k file_exists : every resolved governance_file points at an existing file.
# ---------------------------------------------------------------------------
def test_file_exists_step_governance_resolves():
    """For every active step's resolved governance_file, the file must
    exist under docs/governance-templates-v2/. (Null entries — e.g. the
    human-supervisor handoffs whose governance is resolved as None by
    the precedence walk — are accepted as 'no file required'.)"""
    from execution_config import resolve_execution_config

    conn = sqlite3.connect(str(DB_PATH))
    try:
        steps = _active_steps(conn)
    finally:
        conn.close()

    missing = []
    for flow_key, step_key in steps:
        cfg = resolve_execution_config(flow_key, step_key)
        gov = cfg.get("governance_file")
        if gov is None or gov == "":
            continue
        path = GOV_DIR / gov
        if not path.is_file():
            missing.append((f"{flow_key}/{step_key}", gov, str(path)))
    assert not missing, (
        f"step-level governance_file points at missing file(s): "
        f"{missing}"
    )

def test_file_exists_role_governance_resolves():
    """For every active role's governance_file, the file must exist
    under docs/governance-templates-v2/. This is the role-level half of
    TG4 — covers the post-068 repoint contract."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT role_key, governance_file FROM bridge_roles "
            "WHERE is_active = 1 AND governance_file IS NOT NULL "
            "AND governance_file != ''",
        ).fetchall()
    finally:
        conn.close()

    missing = []
    for role_key, gov in rows:
        path = GOV_DIR / gov
        if not path.is_file():
            missing.append((role_key, gov, str(path)))
    assert not missing, (
        f"role-level governance_file points at missing file(s): {missing}"
    )

# ---------------------------------------------------------------------------
# -k no_dangling : no retired filename is referenced anywhere active, and
# the two D2 code fixes hold.
# ---------------------------------------------------------------------------
def test_no_dangling_no_role_references_retired_filename():
    """After Run 017, no active role's governance_file names any of the
    35 retired/deleted files (the same predicate migration 068's guard
    uses, plus the 5 dead/stale files)."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT role_key, governance_file FROM bridge_roles "
            "WHERE is_active = 1 AND governance_file IS NOT NULL",
        ).fetchall()
    finally:
        conn.close()

    dangling = [
        (role_key, gov)
        for role_key, gov in rows
        if gov in _RETIRED_GOVERNANCE_FILES
    ]
    assert not dangling, (
        f"active role(s) still reference a retired/deleted governance_file: "
        f"{dangling}"
    )

def test_no_dangling_no_step_resolves_retired_filename():
    """No active step's resolved governance_file (via the live resolver)
    names any of the 35 retired/deleted files."""
    from execution_config import resolve_execution_config

    conn = sqlite3.connect(str(DB_PATH))
    try:
        steps = _active_steps(conn)
    finally:
        conn.close()

    dangling = []
    for flow_key, step_key in steps:
        cfg = resolve_execution_config(flow_key, step_key)
        gov = cfg.get("governance_file")
        if gov in _RETIRED_GOVERNANCE_FILES:
            dangling.append((f"{flow_key}/{step_key}", gov))
    assert not dangling, (
        f"active step(s) resolve to a retired/deleted governance_file: "
        f"{dangling}"
    )

def test_no_dangling_scheduler_py_no_451_fallback_literal():
    """Run 017 D2 fix: scheduler.py no longer carries the literal
    "451_SUPERVISED_REVIEW_SUPERVISOR.md" fallback default."""
    path = PROJECT_ROOT / "scripts" / "job_queue" / "scheduler.py"
    text = path.read_text(encoding="utf-8")
    assert "451_SUPERVISED_REVIEW_SUPERVISOR.md" not in text, (
        f"scheduler.py still references '451_SUPERVISED_REVIEW_SUPERVISOR.md' "
        f"— D2 fix did not stick"
    )

def test_no_dangling_dispatch_py_line_3462_comment_no_retired_pattern():
    """Run 017 D2 fix: dispatch.py line 3462's example comment no longer
    names a 40x/41x/42x/45x/46x/47x/49x/51x absorbed-original filename."""
    path = PROJECT_ROOT / "scripts" / "bridgeV002" / "dispatch.py"
    lines = path.read_text(encoding="utf-8").splitlines()
    # Line numbers in the handoff are 1-based; Python lists are 0-based.
    target = lines[3462 - 1] if len(lines) >= 3462 else ""
    import re as _re
    # Match any absorbed-original name fragment, e.g. "402_...md", "Read 451_...md",
    # or an explicit 401/411/421/422/423/424/425/452/453/454/461/462/463/471/472/473/491/492/511/512/513 prefix.
    pattern = _re.compile(
        r"40[1-5]_STRICT|41[1-5]_CLOUD|42[1-5]_CLOUD|45[2-4]_SUPERVISED"
        r"|46[1-3]_LLAMA|47[1-3]_PREFERRED|49[12]_REVENG|51[1-3]_PREFERRED"
        r"|\b40[1-5]_|41[1-5]_|42[1-5]_|45[2-4]_|46[1-3]_|47[1-3]_|49[12]_|51[1-3]_",
    )
    assert not pattern.search(target), (
        f"dispatch.py line 3462 comment still references a retired pattern: "
        f"{target!r}"
    )

def test_no_dangling_invariants_summary():
    """Single-shot summary: count of dangling role references must be 0.

    This is the human-readable TL;DR for the no_dangling group."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT governance_file FROM bridge_roles "
            "WHERE is_active = 1 AND governance_file IS NOT NULL",
        ).fetchall()
    finally:
        conn.close()

    count = sum(
        1 for (gov,) in rows if gov in _RETIRED_GOVERNANCE_FILES
    )
    assert count == 0, (
        f"no_dangling summary: {count} active role(s) reference a retired file"
    )
