# Harness Terminal Extraction Notes

`Harness Terminal` is a harness-neutral, persistent interactive terminal that
runs inside a role's tmux session and drives one-shot harnesses (today: the
DeepSeek Harness `--profile headless`). It is being built inside DPMtF because
`preferred_cloud_harness` is the working reference implementation, but it is
**not intended to remain permanently owned by DPMtF**. This note records the
seam so it can later be carved into a standalone `harness-allocator`
repository.

## 1. What is harness-generic

These parts know about *harnesses* (how to resolve one, how to build an
invocation, how to run a one-shot turn, how to present a terminal), never about
DPMtF flows, verdicts, roles or governance:

- `scripts/bridgeV002/harness.py`
  - `resolve_harness` / `is_native` / `missing_env` / `describe_missing`
  - `build_launch_command`, `build_dsh_invocation`, `build_task_invocation`
  - `NATIVE_HARNESSES`, `REQUIRED_ENV`
- `scripts/bridgeV002/harness_terminal.py`
  - `render_banner`, `_ready_line`, `execute`, `main`
  - `HARNESS_LABELS`, `MODEL_LABELS`

These import only `config` (for `get_dsh_bin/profile/patch` and
`get_codex_bin`) and the Python standard library. They speak no DPMtF DB,
frontend, flow, or governance code.

## 2. What is DPMtF-specific

- `scripts/bridgeV002/start_coding.py`
  - `_harness_terminal_command` — decides *when* to launch the terminal for a
    role, and passes the role/harness/model/flow/cwd identity it read from
    `bridge_roles`.
  - `_compose_initial_supervisor_prompt` — composes the supervisor cold-start
    context (governance path + `supervisor_state.py` + target project). This is
    DPMtF's own prompt/context builder and stays in DPMtF.
- `scripts/bridgeV002/dispatch.py`
  - `_wrap_prompt_for_harness` — decides how to frame a wakeup for a role: for
    `dsh` it flattens the prompt to a single request line and lets the terminal
    wrap it; for other roles it passes the prompt through unchanged. The
    framing choice is dispatch logic; the wrapping itself lives in `harness.py`.
- `scripts/bridgeV002/runtime_owner.py`, `scripts/db/*.sql` — DPMtF ownership
  and schema, not harness concerns.
- The governance files (`511/512/513`) and the cold-start skill — DPMtF
  semantics.

## 3. What should later move to `harness-allocator`

The whole generic surface:

- `HarnessTerminal` (the persistent terminal loop: banner → read request →
  execute → display → READY).
- `HarnessDefinition` / identity resolution (role → harness key → model).
- `HarnessAdapter` / command generation (`build_launch_command`,
  `build_dsh_invocation`, `build_task_invocation`).
- `invoke`/`execute` (run the one-shot command, capture output).
- readiness/status state (`READY`/`RUNNING`/`SUCCESS`/`ERROR`).
- environment requirements (`REQUIRED_ENV`, `missing_env`, `describe_missing`).
- process lifecycle and session interaction (the terminal ↔ tmux/session
  boundary, once it stops reading role identity out of DPMtF's DB).

## 4. DPMtF dependencies that currently prevent direct extraction

- `harness.py` imports `config` for `get_dsh_bin/get_dsh_profile/get_dsh_patch/
  get_codex_bin`. A future `harness-allocator` needs its own config surface;
  the getters are the seam (today they are DPMtF `config.py` getters).
- `harness_terminal.py` imports `harness` only — but `harness` itself imports
  DPMtF `config`. Extraction means moving those getters into the allocator's
  own config first.
- `start_coding.py` reads role identity from `bridge_roles` (DPMtF DB). The
  allocator must instead receive that identity from DPMtF over a clean
  interface, rather than querying the DB.
- No other coupling: the terminal does not import `dispatch`, `bridge_lib`, or
  any router.

## 5. Expected future interface between DPMtF and Harness Allocator

DPMtF should eventually ask for behaviour, not build commands:

```
DPMtF → Harness Allocator:
    execute(role=<role>, harness=<harness>, model=<model>,
            cwd=<cwd>, task=<semantic task/context>)

Harness Allocator → DPMtF:
    { status, output, error, elapsed }
```

Today's `build_task_invocation(harness, role_config, task)` is the in-repo
precursor of that `execute` boundary: DPMtF already no longer needs to know
`dsh` CLI syntax — it sends the semantic task to the terminal, and the terminal
builds the command.

## 6. Design decisions made to keep extraction easy

- **The terminal is a dumb executor.** It never interprets verdicts, sequences,
  or governs. DPMtF composes the task (including governance/cold-start context)
  and sends it; the terminal only runs it through the harness.
- **One command builder.** `harness.py` owns `build_dsh_invocation` /
  `build_task_invocation`; `harness_terminal.py` and `dispatch.py` reuse it and
  do not re-derive CLI syntax.
- **Transport is stdin.** V1 uses the existing tmux paste/send transport and a
  single-line request protocol, so there is no new IPC/network dependency to
  unwind later.
- **Identity is passed in, not looked up.** The terminal receives role/harness/
  model/flow/cwd as CLI arguments, so it has no DPMtF database dependency.
- **Lifecycle separation is explicit.** tmux lifecycle (Stop tmux) ≠ Harness
  Terminal lifecycle (the persistent process) ≠ one-shot harness invocation
  (per wakeup) ≠ model lifecycle (Model Allocator). The terminal is torn down
  by Stop tmux and is not registered in `Stop servers`.
