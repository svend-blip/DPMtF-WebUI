# RUN-LEDGER — preferred_cloud_harness Run 003

Append-only run memory. Rebuild context on every supervisor wake-up from:
GOAL.md -> RUN-LEDGER.md tail -> BACKLOG.md.

First handoff id: 007.

---

## Wake-up 2026-08-20T10:30:34Z — Run opened

- Human-approved Mission Contract exists at
  `/home/svend/flows/preferred_cloud_harness/runs/003/GOAL.md` (status APPROVED,
  title "Permissions, authentication, sandbox-boundary, and autonomous-chain
  hardening").
- First handoff id is **007**; flow counter was **7** at run opening (next_id=7,
  confirmed directly against `bridge_id_counters` in `databases/dpmtf.db`).
- Run opened with no implementation handoff dispatched yet (chain not started).
- Chain: `super-deep-deep4` -> `imple-codex-minimaxM3` ->
  `review-claude-sonnet5` -> `super-deep-deep4` (DeepSeek Harness / Codex CLI /
  Claude Code; DeepSeek V4 Pro / MiniMax M3 / Sonnet 5).
- Target project: `/home/svend/harness-allocator`
  (`bridge_flows.target_project_path` — confirmed present in DB; the cold-start
  skill's "this flow sets none" note is stale).
- Budget: **max 4 governed handoffs** (GOAL.md §11). No wall-clock budget is
  stated in Run 003.
- Run type: permissions, authentication, sandbox-boundary and autonomous-chain
  hardening. Run 003 SHALL NOT add another major Harness Allocator feature.

### Direct-write attempt — FAILED, and this is the finding that matters

The Human instruction was explicit: *first attempt to write the authoritative
bookkeeping directly under `/home/svend/flows/preferred_cloud_harness/runs/003/`,
and do not default to the scaffold merely because Runs 001/002 used it.* That
attempt was made first, and it failed at the filesystem, live:

```text
touch /home/svend/flows/preferred_cloud_harness/runs/003/.write_probe
  -> Read-only file system (Errno 30)
echo > .../.probe2
  -> Read-only file system (Errno 30)
```

This is Objective 3's symptom, reproduced in the very first action of the run:
the DeepSeek Harness supervisor sandbox cannot write `/home/svend/flows`. The
authoritative bookkeeping is therefore staged under the documented fallback
(`/home/svend/DPMtF-WebUI/harness-allocator-scaffold/`) for one final host-side
materialization; fixing this is exactly what handoff 007's investigation and the
follow-on bridge/tmux handoff are for.

### Live sandbox boundary — measured this wake-up (not assumed)

| Path / object | State | Evidence |
|---|---|---|
| `/home/svend/DPMtF-WebUI` (session workspace) | **writable** | `touch` probe succeeded |
| `/tmp` | **writable** | `touch` probe succeeded |
| `/home/svend/flows` | **read-only** | `touch` -> Errno 30 |
| `/home/svend/harness-allocator` | **read-only** | `touch` -> Errno 30 |
| `/tmp/tmux-1000` | **absent** | `ls` -> no such file |
| `tmux ls` | **unreachable** | "error connecting to /tmp/tmux-1000/default" |
| `databases/dpmtf.db` | **writable** | under session workspace; counter read OK |
| `bridge_id_counters` | `next_id = 7` | direct DB read |

Consequence (unchanged from Runs 001/002, re-confirmed here): `dispatch.py
--signal-send` run from THIS sandbox would bump the counter in the DB (which is
writable) and then fail on the read-only `trace.log` write / invisible tmux
socket — leaving partial state. **I did not run it.** The dispatch is a host-side
action until handoff 007 + the bridge/tmux handoff land.

### Launch-path ownership — supervisor investigation (feeds handoff 007)

Investigated read-only before authoring the handoff, so the handoff points at
the real owners instead of guesses. Independent verification is still required
of the implementer (GOAL.md §7):

1. **Codex command construction** — `start_coding.py` (native-harness branch)
   -> DPMtF `harness.py::build_launch_command("codex", role)` ->
   `harness_allocator/adapter.py::_codex_argv` (standalone package at
   `/home/svend/harness-allocator`).
2. **Codex `--sandbox` / `--ask-for-approval` / `--add-dir` / `-C`** — all from
   `config.py` getters (`get_codex_sandbox`, `get_codex_ask_for_approval`,
   `get_codex_add_dirs`, `get_codex_workdir`) delegating to
   `harness_allocator/config.py`. Current defaults: sandbox `workspace-write`,
   approval `never`, add_dirs `[bridge_dir, project_root, tempdir]` =
   `/home/svend/flows`, `/home/svend/DPMtF-WebUI`, `/tmp`; workdir empty (cwd set
   by `cd {target_cwd}` in `start_coding.py`; target = `/home/svend/harness-allocator`).
   This **appears already correct on intent** (matches GOAL Objective 1 boundary),
   but TG1/TG2 require live proof, not config inspection.
3. **Claude Code launch** — `start_coding.py` (model_allocator branch) calls
   `model-allocator run --role review-claude-sonnet5 --client claude-code`, sends
   the shell string to the tmux session. Command shape built by
   `/home/svend/model-allocator/src/model_allocator/adapters/claude_code.py`.
4. **ANTHROPIC_API_KEY check** — lives in the model-allocator, not in
   `scripts/bridgeV002`. `validator.py::_validate_anthropic` and
   `claude_code.py::build_claude_code_command` branch on
   `resolved["credentials"]`; for `subscription` they check
   `~/.claude/.credentials.json` and **unset** `ANTHROPIC_API_KEY` (they do NOT
   require it); for `api_key` they require `api_key_env` (default
   `ANTHROPIC_API_KEY`). `sonnet5` alias -> `cloud_anthropic` profile ->
   `credentials: subscription` (runtime_profiles.yaml). **The subscription path
   appears already implemented**; TG4's residual risk is any OTHER stale check,
   which must be found by live verification, not assumed away.
5. **Reviewer key inheritance** — subscription mode adds `ANTHROPIC_API_KEY`/
   `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` to the adapter's `unset_env`, so
   the launch env should carry none; the actual host/tmux environment is what
   must be measured (TG3/TG4).
6–10. **DeepSeek sandbox, bridge-write, tmux, trace.log, policy owner** — the
   supervisor's own sandbox is the DSH `workspace-write` mount rooted at
   `/home/svend/DPMtF-WebUI` (this is what makes `/home/svend/flows` read-only and
   the host tmux socket invisible, items 6/7/8); `dispatch.py` needs trace.log
   write + tmux injection + a (writable) DB counter bump, of which only the DB is
   reachable from here (item 9). The owner of the permission policy is split
   today: DPMtF `config.py` + `harness_allocator/config.py` (Codex/dsh flags),
   `model-allocator` (Claude env/credentials), and the harness sandbox mount
   itself. This split ownership is the architectural question handoff 007 must
   answer for Objectives 3/4/5/6 (item 10).

### Staging + host-side materialization + dispatch (Run 003 handoff 007)

Staged under `/home/svend/DPMtF-WebUI/harness-allocator-scaffold/flows/preferred_cloud_harness/`:

1. `runs/003/BACKLOG.md`           -> `/home/svend/flows/preferred_cloud_harness/runs/003/BACKLOG.md`
2. `runs/003/RUN-LEDGER.md`        -> `/home/svend/flows/preferred_cloud_harness/runs/003/RUN-LEDGER.md`
3. `handoffs/007-handoff.md`       -> `/home/svend/flows/preferred_cloud_harness/handoffs/007-handoff.md`

Then dispatch (host-side, one final time — the run exists to remove this step):

```bash
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  --db-flow preferred_cloud_harness \
  --signal-send \
  --from-role super-deep-deep4 \
  --to-role imple-codex-minimaxM3 \
  --id 007
```

The explicit `--id 007` makes the staged file provably the file that goes out.
Before that dispatch, the target tmux session `imple-codex-minimaxM3` must
actually be running on the host — from this sandbox `supervisor_state` reports it
"NOT RUNNING", but that only proves the socket is invisible here (Runs 001/002
established this; the host operator must confirm session liveness).

### Next wake-up

When verdict 007 lands: validate the §7 investigation and the Codex/Claude
findings by hand against GOAL.md, then per 511 Event Handling dispatch handoff
008 (bridge/tmux autonomy implementation + regression) — or park if the
investigation surfaces a scope-fence or security-boundary ambiguity.
