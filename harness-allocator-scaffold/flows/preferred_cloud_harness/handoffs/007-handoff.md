<role>You are imple-codex-minimaxM3 (Implementor) in the DPMtF preferred_cloud_harness flow. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md before proceeding.</role>

<handoff_id>007</handoff_id>

<project>/home/svend/harness-allocator</project>

<context>
This is the first governed handoff of Run 003. Its purpose is investigation
plus the smallest clearly-safe permission/authentication fixes — NOT a
redesign, NOT the full tmux-autonomy implementation (that is a later handoff).

The authoritative Mission Contract is:
/home/svend/flows/preferred_cloud_harness/runs/003/GOAL.md — read it in full
before proceeding. (That is the run's Mission Contract. The product
specification is a separate /home/svend/harness-allocator/GOAL.md — do not
confuse the two.)

Run 003's mission is to make the preferred_cloud_harness chain
(super-deep-deep4 -> imple-codex-minimaxM3 -> review-claude-sonnet5 ->
super-deep-deep4) complete its governed handoff cycle without routine Human
host-side intervention. This handoff establishes the facts and fixes only what
is clearly safe. GOAL.md §7 requires investigation BEFORE modification; the
supervisor has done a read-only first pass (see the run's RUN-LEDGER.md), but
you must verify each point independently and report file:line evidence.

Three live facts the supervisor already measured and you should re-confirm from
your own session before trusting them: (a) the supervisor's DeepSeek Harness
sandbox cannot write /home/svend/flows (Errno 30); (b) the host tmux socket
/tmp/tmux-1000 is invisible from that sandbox; (c) the Codex permission getters
in config.py / harness_allocator/config.py already default to sandbox
workspace-write, approval never, add-dirs flows+DPMtF-WebUI+/tmp, cwd = the
target project. Your job is to find out which layer owns each of these and
whether the intended boundary is actually in force at runtime.
</context>

<governance>
1. Read 512_PREFERRED_CLOUD_HARNESS_IMPLE01.md and the Mission Contract
   GOAL.md (/home/svend/flows/preferred_cloud_harness/runs/003/GOAL.md) in full
   before acting.
2. DO NOT COMMIT, PUSH, STAGE, STASH or REVERT. Leave changes unstaged for the
   Human (GOAL.md §14).
3. This handoff authorizes INVESTIGATION plus the smallest clearly-safe
   permission/authentication fixes. It does NOT authorize the full tmux/dispatch
   autonomy implementation, and it does NOT authorize any of the §4 non-goals
   (MCP-Light, /skill, new allocator architecture, danger-full-access,
   unrelated repositories).
4. Do NOT modify /home/svend/model-allocator or any repository not listed in
   <scope>. If you find a real defect whose only fix lives outside the scope
   fence (for example a residual ANTHROPIC_API_KEY requirement inside the
   model-allocator), STOP and report it as a scope-fence finding — do not edit it.
5. Do NOT weaken any existing assertion or production behavior merely to obtain
   green tests.
6. Report only measured results. Never invent command output.
7. Stop after two failed patch attempts against the same problem; document the
   actual failure and return it rather than guessing (GOAL.md §10 rework
   discipline, and 511 stop conditions).
8. Do not use danger-full-access or --dangerously-bypass-approvals-and-sandbox
   under any reading of this handoff (GOAL.md §4.4).
</governance>

<task>
Three parts, in order. Part A gates Part B and Part C: complete and document the
investigation before changing anything.

PART A — INVESTIGATION (GOAL.md §7, all ten items). Inspect the current launch
path read-only and document, with exact file:line references, the real owner of
each of the following:

 1. Where preferred_cloud_harness constructs the Codex command. (Start at
    /home/svend/DPMtF-WebUI/scripts/bridgeV002/start_coding.py native-harness
    branch, then follow the call into scripts/bridgeV002/harness.py and the
    standalone /home/svend/harness-allocator/harness_allocator/adapter.py.)
 2. Where Codex receives --sandbox, --ask-for-approval, --add-dir, and -C/cwd.
    (config.py getters get_codex_sandbox / get_codex_ask_for_approval /
    get_codex_add_dirs / get_codex_workdir, and their counterparts in
    harness_allocator/config.py.)
 3. Where Claude Code is launched. (start_coding.py model_allocator branch ->
    `model-allocator run --role review-claude-sonnet5 --client claude-code`.)
 4. Why the launcher/model allocator checks for ANTHROPIC_API_KEY — or whether it
    still does. (Inspect /home/svend/model-allocator/src/model_allocator/
    validator.py and adapters/claude_code.py; note the `credentials` field and
    the subscription-vs-api_key branches. READ ONLY — model-allocator is out of
    the modification fence.)
 5. Whether the Claude reviewer process inherits ANTHROPIC_API_KEY. (Follow the
    subscription branch of adapters/claude_code.py `unset_env`.)
 6. How DeepSeek Harness is sandboxed. (How is `npx @deepseek-ai/dsh` /
    `harness_terminal.py` launched, and what sandbox does the DSH runtime apply?
    The supervisor measured workspace-write rooted at /home/svend/DPMtF-WebUI.)
 7. Why /home/svend/flows is read-only inside DeepSeek Harness.
 8. Why the DeepSeek sandbox cannot access the host tmux socket /tmp/tmux-1000.
 9. Whether scripts/bridgeV002/dispatch.py itself needs direct tmux access or can
    use a narrow broker. (Read dispatch.py's signal-send path: what it writes to
    trace.log, what tmux commands it runs, and where the counter is bumped.)
 10. Which component should own the permission policy (DPMtF config.py vs
    harness_allocator/config.py vs model-allocator vs the harness sandbox mount),
    and why the split matters for Objectives 3/4/5/6.

PART B — CODEX PERMISSION PROFILE (in-fence, safe). Make the fresh-start Codex
permission profile deterministic and prove it live. The intended boundary is:
cwd /home/svend/harness-allocator, sandbox workspace-write, approval never,
additional writable /home/svend/flows + /home/svend/DPMtF-WebUI + /tmp. If the
config already produces this (the supervisor's read-only pass suggests it does),
say so with the evidence and change nothing; if there is a gap, fix only the
smallest in-fence file that closes it. Then run the TG1/TG2 acceptance commands
in <validation> and paste the real output.

PART C — CLAUDE SUBSCRIPTION AUTH + ARCHITECTURE RECOMMENDATION. (a) Confirm,
from the static launch path, whether the reviewer's `sonnet5` alias resolves to
subscription auth with ANTHROPIC_API_KEY unset (models.yaml/runtime_profiles.yaml
in /home/svend/model-allocator — read only). If you find any residual
ANTHROPIC_API_KEY requirement that would break subscription mode, record its
exact file:line and state whether its fix is in-fence (DPMtF seam) or out-of-fence
(model-allocator). Do NOT modify model-allocator. (b) For the supervisor
bridge-write + tmux/dispatch boundary (Objectives 3/4/5/6), document which layer
owns the read-only /home/svend/flows and the invisible tmux socket, and recommend
the smallest robust architecture (narrow writable bridge capability, narrow
tmux/dispatch broker, or another deterministic boundary). Recommend — do NOT
implement the full autonomy in this handoff, and do NOT propose
danger-full-access or unrestricted host tmux.
</task>

<scope>
MAY modify (only these, and only the smallest change that satisfies Part B):
- /home/svend/harness-allocator/harness-allocator.ini
- /home/svend/harness-allocator/harness_allocator/config.py
- /home/svend/harness-allocator/harness_allocator/adapter.py
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/start_coding.py
- /home/svend/DPMtF-WebUI/scripts/bridgeV002/harness.py
- /home/svend/DPMtF-WebUI/config.py (only if strictly necessary to establish the
  Codex boundary; prefer ini/env over this file — CLAUDE.md §10)

MUST NOT modify:
- /home/svend/model-allocator (any path) — read-only investigation only
- app.py, scripts/init_db.py, dpmtf.ini, .env, databases/
- governance files under docs/governance-templates-v2/
- .git/ internals
- scripts/bridgeV002/dispatch.py, harness_terminal.py, gate-deliverable-evidence.py
  (Part A reads them; they are NOT to be modified in this handoff — report a
  blocker instead if a fix there appears necessary)
- /home/svend/AI-Genealogy-Research-Assistant (any path) — forbidden
- any other repository or any path outside the fence

Do not commit or push.
</scope>

<validation>
Run and paste the real output of every applicable check before signalling
completion. Keep all commands POSIX (no $'...', no arrays, no [[ ]]).

TG1 — Codex permission smoke test. From this session prove create/delete succeeds
in the four intended-writable locations and FAILS in an unrelated location, and
that no artifact remains afterward:

```sh
for d in /home/svend/harness-allocator /home/svend/flows /home/svend/DPMtF-WebUI /tmp; do
  f="$d/.run003_tg1_probe_$$"
  if (umask 077 && : > "$f" 2>/dev/null && rm -f "$f"); then echo "WRITABLE  $d"; else echo "BLOCKED   $d"; fi
done
f=/home/svend/model-allocator/.run003_tg1_neg_$$
if (umask 077 && : > "$f" 2>/dev/null); then echo "NEGATIVE  unexpected write succeeded"; rm -f "$f"; else echo "NEGATIVE  correctly blocked /home/svend/model-allocator"; fi
```

If /home/svend/model-allocator is not writable for you, also try one genuinely
unrelated location outside the four approved dirs (e.g. /home/svend/AI-Genealogy-Research-Assistant)
and record the result. Paste the exact output; do not hand-transcribe.

TG2 — live Codex runtime configuration. Report the effective launch configuration
this session actually runs with: the resolved cwd, the --sandbox value, the
--ask-for-approval value, and the full --add-dir list. Prove it by resolving the
same getters the launcher uses (do not infer from comments):

```sh
cd /home/svend/DPMtF-WebUI && python3 -c "import config; print('sandbox=', config.get_codex_sandbox()); print('approval=', config.get_codex_ask_for_approval()); print('add_dirs=', config.get_codex_add_dirs()); print('workdir=', repr(config.get_codex_workdir()))"
```

TG12 — relevant regression suites must stay green:
```sh
cd /home/svend/DPMtF-WebUI && python3 -m pytest tests/test_preferred_cloud_harness.py -q
cd /home/svend/harness-allocator && python3 -m pytest tests -q
```

Syntax for any in-fence file you change:
```sh
python3 -m py_compile <changed file>
```

Paste the real outputs into 007-result.md. Never fabricate output. If two patch
attempts fail against the same problem, stop and report the actual failure.
</validation>

<constraint>
- Investigation (Part A) before modification (GOAL.md §7); no symptom patching
  before the owning layer is identified.
- Only the smallest in-fence Codex fix (Part B); no redesign, no full tmux/dispatch
  autonomy, no MCP-Light, no /skill.
- No model-allocator modification; report out-of-fence findings instead.
- No danger-full-access / --dangerously-bypass-approvals-and-sandbox (GOAL.md §4.4).
- Do not weaken existing assertions (GOAL.md §9).
- No new runtime dependencies, daemons, databases or protocols.
- Do not commit/push/stage/stash/revert.
- Report only measured results; if two patch attempts fail against the same
  problem, stop and report the actual failure.
</constraint>

<deliverable>
/home/svend/flows/preferred_cloud_harness/results/007-result.md containing:
- the in-scope working-tree baseline you recorded at handoff start
  (git status --short in /home/svend/DPMtF-WebUI and /home/svend/harness-allocator)
- Part A: the ten §7 findings, each with file:line evidence
- Part B: the Codex fix (or the "no change needed" determination) + the TG1/TG2
  real output
- Part C: the Claude subscription-auth determination (including any residual
  ANTHROPIC_API_KEY requirement and its file:line), and the recommended smallest
  architecture for the supervisor bridge-write + tmux/dispatch boundary
- the regression suite output and py_compile result

Then signal completion exactly once:

```bash
python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
  --db-flow preferred_cloud_harness \
  --signal-complete \
  --from-role imple-codex-minimaxM3 \
  --id 007
```

Read the command's output. If it reports `signal_complete_failed`, your result
is not at the path dispatch looked for — fix the path and signal again. Do not
fabricate completion.
</deliverable>
