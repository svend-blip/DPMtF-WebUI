## Wake-up 2026-08-19T20:14:20Z (human-proceed-directive)

- Event: Human directive (this session): "Proceed according to the approved Run
  001 governance. Do not modify /home/svend/AI-Genealogy-Research-Assistant.1,
  then stop." This resolves the close-vs-004 decision left open in APPEND-005.
- Action: Re-validated the run state (`check_testgoals.py` → 8/8 green, exit 0;
  TG1 56 passed, standalone package 51 passed, TG7 `resolve_harness` → `'dsh'`).
  Verdict 003 is APPROVED (re-evaluated) and the backlog is non-empty (handoff
  004 pending), so per 511 Event Handling ("If all green and the backlog is
  empty, write the END-REPORT and park. Otherwise dispatch the next handoff") I
  authored and dispatched handoff **004** — the final review/remediation pass →
  END-REPORT. Staged `handoffs/004-handoff.md`, updated BACKLOG.md (004 →
  DISPATCHED), and wrote this ledger append. I did NOT run `dispatch.py` from
  this sandbox (a read-only `trace.log` would crash mid-dispatch and leave a
  partial counter state — established stage-and-document convention); the host
  dispatch command is documented below.
- Budget: handoffs 4/4 (001, 002, 003 APPROVED; 004 dispatched — at the max
  handoff cap of 4). Active ~224 min from trace.log (first signal 16:30:20Z →
  this wake-up 20:14:20Z), within the 300 min cap.
- Testgoals: 8/8 green — verified mechanically this wake-up with
  `check_testgoals.py` → exit 0.
- Notes:
  - The Human directive names `/home/svend/AI-Genealogy-Research-Assistant.1`.
    No such path exists in this sandbox (`ls` → no such file); the real
    repository is `/home/svend/AI-Genealogy-Research-Assistant` (no `.1`). I
    interpreted the fence as: do not modify the genealogy project in any form.
    Handoff 004's `<scope>`, `<governance>` and `<constraint>` all explicitly
    forbid touching `/home/svend/AI-Genealogy-Research-Assistant`.
  - The out-of-fence finding from verdict 003 (seven files in that repository)
    remains cleared by the Human as legitimate out-of-run work (APPEND-005). I
    made no change to it this wake-up, and handoff 004 instructs the implementer
    to leave it untouched.
  - Handoff 004 content: a confirmation-and-closure pass — re-verify TG1–TG8,
    confirm the standalone package is unchanged, confirm working-tree scope,
    remediate ONLY if a real in-scope defect is found (none expected), then
    report for END-REPORT. It explicitly states "if nothing is broken, change
    nothing".
  - Sandbox: `/home/svend/flows`, `/home/svend/harness-allocator` and
    `/home/svend/AI-Genealogy-Research-Assistant` are all read-only to THIS
    session (re-confirmed this wake-up: `touch` on the flows runs dir →
    read-only FS). The handoff, the BACKLOG update and this ledger append are
    therefore staged under
    `/home/svend/DPMtF-WebUI/harness-allocator-scaffold/flows/preferred_cloud_harness/`
    for host-side materialization into the authoritative
    `/home/svend/flows/preferred_cloud_harness/` (established staging
    convention — see opening entry).
  - Host-side materialization + dispatch (to run after staging):
    1. Copy `handoffs/004-handoff.md` →
       `/home/svend/flows/preferred_cloud_harness/handoffs/004-handoff.md`
    2. Append this entry →
       `/home/svend/flows/preferred_cloud_harness/runs/001/RUN-LEDGER.md`
    3. Replace BACKLOG.md with the updated staged copy
    4. Dispatch:
       `python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py --db-flow preferred_cloud_harness --signal-send --from-role super-deep-deep4 --to-role imple-codex-minimaxM3 --id 004`
       (explicit `--id 004` makes the staged file provably the file that goes
       out; `bump_id_counter_past` advances the counter 4 → 5.)
  - Next wake-up: when verdict 004 lands. If APPROVED: validate the testgoals,
    then the backlog is empty and testgoals are green → write `END-REPORT.md` to
    the authoritative run directory and prove it with `ls -la` on the exact
    path. If REJECTED: read the reason — in-scope fix → rework within budget;
    out-of-scope → park.
