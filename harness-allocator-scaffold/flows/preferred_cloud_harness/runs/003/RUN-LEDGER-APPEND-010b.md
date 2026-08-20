## Wake-up 2026-08-20T13:52:28Z (Human ruling — Option A APPROVED)

- Event: Human ruling received. **Option A is approved**: the governed handoff
  budget for Run 003 is amended from 4 to 5. Handoff 010 is reserved for the
  narrow governed broker artifact-materialization capability required for
  Objective 3; handoff 011 is reserved for the full end-to-end autonomous-chain
  acceptance required by TG6-TG8 and TG13. No other scope, permission, standing
  approval, or security boundary is expanded.
- Action: un-parked the run. Re-ran `supervisor_state.py --flow
  preferred_cloud_harness` (active run 003, first handoff 007, counter 10, current
  009 with handoff/result/verdict present). Confirmed the GOAL.md amendment is
  materialized at lines 1008-1042. Authored + staged handoff 010 (broker
  materialization extension) for host-side materialization + dispatch. Did NOT
  hand-edit the flow counter (still next_id = 10 -> 010 is the next id).
- Budget: handoffs **3 used / 5 max** (007 APPROVED, 008 declined + REJECTED, 009
  APPROVED). 010 = materialization (staged, next). 011 = e2e acceptance (reserved).
  No wall-clock budget stated in Run 003.
- Testgoals: unchanged from the 13:34Z park. 8/13 green (TG1-TG4 static/inherited
  from 007; TG9-TG12 design/unit + live seam from 009). RED/DEFERRED: TG5
  (supervisor authoritative write — 010 delivers it), TG6-TG8 + TG13 (011 live
  acceptance).

### Binding materialization constraints (from the amendment, carried verbatim into 010)

- The materialization capability MUST NOT accept arbitrary host paths.
- Canonical destinations MUST be derived from flow/run/handoff identity and an
  enumerated artifact type.
- Preserved and re-asserted: no `danger-full-access`; no unrestricted
  `/home/svend/flows` access for the DSH role; no Model Allocator changes; no
  MCP-Light work; no `/skill` work; evidence gate + scope governance remain
  active; manual recovery paths remain available.

### Bootstrap note (why 010's own dispatch is still one manual step)

010's dispatch requires `010-handoff.md` to already exist at the canonical
`/home/svend/flows/preferred_cloud_harness/handoffs/` path — which is exactly the
write the materialization capability (delivered BY 010) does not yet provide.
010's own dispatch is therefore the LAST manual Human materialization; 010's
deliverable removes this step for 011, so 011 can satisfy TG6-TG8/TG13 with no
manual cp/dispatch/tmux steps.

### Notes (state re-verified this wake-up)

- Supervisor sandbox re-probe unchanged: `/home/svend/flows` READ-ONLY
  (touch -> Errno 30); `/home/svend/DPMtF-WebUI` writable; `/tmp` writable;
  `databases/dpmtf.db` writable. This read-only mount is the Objective 3/TG5
  symptom itself and is why this ledger append, the updated BACKLOG, and
  010-handoff.md are staged under `harness-allocator-scaffold/` for one final
  Human materialization.
- Broker daemon still RUNNING on the host (pid 2187005). Queue rows: id=2
  (preferred_cloud_harness, review01 signal_complete for 009, completed 13:08:39Z)
  and id=3 (a different `preferred_cloud` flow, not this run). No pending rows.
- Flow counter re-read: next_id = 10 (unchanged) -> 010 is the next id; dispatch
  must use the explicit `--id 010`. No counter hand-edit.
- Working tree re-verified matches the 009-verdict E.8 baseline (broker code
  present and uncommitted as delivered by 009; no stray 010 changes yet).
- No new handoff id allocated beyond 010; no dispatch run from this sandbox (the
  sandbox cannot complete a signal_send — read-only /home/svend/flows + invisible
  host tmux — so dispatch remains a host-side step until 010 lands).

### Staging + host-side materialization + dispatch (Run 003 handoff 010)

Materialize in this order (scaffold -> /home/svend/flows):

1. `handoffs/010-handoff.md`    -> `/home/svend/flows/preferred_cloud_harness/handoffs/010-handoff.md`
2. `runs/003/RUN-LEDGER-APPEND-010b.md` -> append to `/home/svend/flows/preferred_cloud_harness/runs/003/RUN-LEDGER.md`
3. `runs/003/BACKLOG.md`        -> replace `/home/svend/flows/preferred_cloud_harness/runs/003/BACKLOG.md`

Then dispatch (host-side, one final manual step — 010's deliverable removes it for 011):

```bash
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  --db-flow preferred_cloud_harness \
  --signal-send \
  --from-role super-deep-deep4 \
  --to-role imple-codex-minimaxM3 \
  --id 010
```

The explicit `--id 010` makes the staged file provably the file that goes out.
Before dispatch, confirm the target tmux session `imple-codex-minimaxM3` is alive
on the host (from this sandbox `tmux ls` reports the socket invisible — that
proves only the sandbox boundary, not session liveness).

NEXT WAKE-UP (verdict 010): validate by hand against the working tree, then per
511 dispatch handoff 011 (end-to-end autonomous-chain acceptance, TG5 live +
TG6-TG8 + TG13) — or park if 010 surfaces a scope-fence or security-boundary
ambiguity.
