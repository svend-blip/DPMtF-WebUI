"""C-3 migration: drop zero-row dead tables from databases/dpmtf.db.

Handoff 46 audit verdict (2026-07-04): 8 zero-row tables audited.
ALL 8 tables are kept — none are safe to drop under the handoff's
3-check criteria (a: 0 rows, b: not referenced by code, c: no FK
dependents). This script is therefore a no-op that documents the
audit verdict. It is still useful as a future reference: re-running
the same audit on a different DB state could yield drops.

DB-safety (rule #7 in 12_CODING_STANDARD.md): the only destructive
operation in this script is `DROP TABLE IF EXISTS`, gated by an
explicit list of table names that PASS the audit. If the list is
empty, no DROP is executed. Backup at `databases/dpmtf.db.pre-c3.bak`.

Audit verdict (see handoff 46 result file for full details):
  Table                    | Check (a) 0 rows | Check (b) no ref | Check (c) no FK | Verdict
  -------------------------|----------------|----------------|----------------|---------
  frontend_panels          | PASS (0)        | FAIL (10 hits) | FAIL (1 FK)   | KEEP
  generated_prompts        | PASS (0)        | FAIL (10 hits) | PASS (0)      | KEEP
  panel_classifications    | PASS (0)        | FAIL (5 hits)  | PASS (0)      | KEEP
  project_plans            | PASS (0)        | FAIL (6 hits)  | PASS (0)      | KEEP
  projects                 | PASS (0)        | FAIL (17 hits) | PASS (0)      | KEEP
  prompt_sequence_steps    | PASS (0)        | FAIL (19 hits) | PASS (0)      | KEEP
  prompt_sequences        | PASS (0)        | FAIL (20 hits) | PASS (0)      | KEEP
  reference_projects       | PASS (0)        | FAIL (3 hits)  | PASS (0)      | KEEP
"""

import sqlite3

DB_PATH = "databases/dpmtf.db"

# Tables that PASSED all 3 audit checks (a: 0 rows, b: not referenced,
# c: no FK dependents) — currently EMPTY. If a future audit identifies
# any, append the table name here and the script will drop it.
SAFE_TO_DROP = []


def main():
    if not SAFE_TO_DROP:
        print("C-3 audit: no tables safe to drop.")
        print("  All 8 zero-row candidate tables are KEPT — see handoff 46")
        print("  result file for the full verdict + rationale per table.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for table in SAFE_TO_DROP:
        print(f"DROP TABLE IF EXISTS {table}")
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    conn.close()
    print(f"Dropped {len(SAFE_TO_DROP)} table(s).")


if __name__ == "__main__":
    main()
