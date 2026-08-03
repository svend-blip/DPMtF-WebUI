# llama_SG Flow — Design Document

> **Status:** Approved 2026-08-03
> **Flow key:** `llama_SG`
> **Type:** Autonomous supervisor-driven review chain with dual-runtime model switching

## 1. Architecture Overview

```
Laguna (llama.cpp) loaded
    ↓
supervisor01_llama (Claude Code, autonom)
    ↓ handoff persisted (402 XML format)
Laguna unloaded (post_dispatch_script)
    ↓
Qwen/SGLang loaded (pre_dispatch_script)
    ↓
imple01SG → review01SG (OpenCode, shared SGLang server)
    ↓ verdict
supervisor01_llama (next wake-up, loop)
```

**Key difference from existing flows:** This flow uses **two different runtimes** —
llama.cpp (Laguna, large model for architecture) and SGLang (shared Qwen, smaller
model for implementation/review). Model switching happens between supervisor
handoff and imple01SG via `pre_dispatch_script` / `post_dispatch_script` on flow
steps.

**Roles (3):** supervisor01_llama → imple01SG → review01SG → (loop)
**Flow type:** Autonomous (like supervised_review)
**Handoff format:** 402 XML (same as strict_review/supervised_review)
**Governance decade:** 46x

## 2. Model Allocator Changes

### 2.1 Laguna alias (llama.cpp — existing adapter)

New alias in `models.yaml`:

```yaml
laguna-local:
  runtime_profile: local_llamacpp_laguna
  real_model: Laguna-S-2.1-IQ4_XS
  context: 147456
  lifecycle_policy: stop_after_step
  clients:
    claude-code: true
```

New runtime profile in `runtime_profiles.yaml`:

```yaml
local_llamacpp_laguna:
  backend: llama_cpp
  server_bin_env: LLAMA_SERVER_BIN
  model_root_env: MODEL_ROOT_GGUF
  default_port: 8080
  default_host: 127.0.0.1
  gpu: cuda0
  # Laguna-specific overrides
  extra_args:
    - "--n-cpu-moe 31"
    - "-c 147456"
    - "-ctk q8_0"
    - "-ctv q8_0"
    - "-ngl 99"
    - "--load-mode none"
    - "--jinja"
    - "--reasoning on"
    - "--reasoning-budget 2048"
    - "--parallel 1"
```

Uses the **existing** `llama_cpp` adapter — Laguna is a GGUF model served via
llama-server. No new adapter code required for this part.

### 2.2 SGLang adapter (new)

New file: `src/model_allocator/adapters/sglang.py`

Follows the same pattern as `llama_cpp.py` (server-based, start/stop/health):

- **start:** `python -m sglang.launch_server` with model path, port, context-length,
  mem-fraction-static, max-running-requests, tool-call-parser
- **stop:** `kill -TERM <PID>` → `kill -KILL <PID>` after timeout
- **status:** health check via `GET /health` + `GET /v1/models` + process inspection
- **lifecycle:** `persistent` (remains loaded between roles)
- **protocol:** OpenAI-compatible (`/v1/chat/completions`)

New runtime profile:

```yaml
local_sglang_cuda0:
  backend: sglang
  venv: /home/svend/venvs/sglang
  default_port: 30000
  default_host: 127.0.0.1
  gpu: cuda0
```

New alias:

```yaml
qwen-shared-sglang:
  runtime_profile: local_sglang_cuda0
  served_model_name: qwen-shared
  model_path: /home/svend/models/sglang/<VERIFIED-MODEL-DIRECTORY>
  context: 32768
  lifecycle_policy: persistent
  max_output_tokens: 8192
  clients:
    opencode: true
```

### 2.3 Role configuration

New entries in `roles.yaml`:

```yaml
supervisor01_llama:
  default_alias: laguna-local
  config_dir: supervisor01_llama
  client_aliases:
    claude-code: laguna-local

imple01SG:
  default_alias: qwen-shared-sglang
  config_dir: imple01SG
  client_aliases:
    opencode: qwen-shared-sglang

review01SG:
  default_alias: qwen-shared-sglang
  config_dir: review01SG
  client_aliases:
    opencode: qwen-shared-sglang
```

### 2.4 Schema update

Add SGLang backend fields to `schema.py`:
- `backend: sglang`
- Profile fields: `venv`, `default_port`, `default_host`, `gpu`
- Alias fields: `served_model_name`, `model_path`, `context`, `max_output_tokens`,
  `mem_fraction_static`, `max_running_requests`, `tool_call_parser`

## 3. Database Changes

### 3.1 New flow

```sql
INSERT INTO bridge_flows (flow_key, name, description, auto_complete_enabled)
VALUES ('llama_SG', 'Laguna + SGLang autonomous review',
        'Autonomous supervisor-driven chain: Laguna (architect) → SGLang/Qwen (imple+review)',
        0);
```

### 3.2 New roles

| role_key | tmux_session | role_type | governance_file | model_source | model_alias | allocator_client | workdir_mode |
|---|---|---|---|---|---|---|---|
| supervisor01_llama | supervisor01_llama | agent | 461_LLAMA_SG_SUPERVISOR.md | model_allocator | laguna-local | claude-code | father |
| imple01SG | imple01SG | agent | 462_LLAMA_SG_IMPLE01.md | model_allocator | qwen-shared-sglang | opencode | target_project |
| review01SG | review01SG | agent | 463_LLAMA_SG_REVIEW01.md | model_allocator | qwen-shared-sglang | opencode | target_project |

### 3.3 Flow steps

| step_key | from_role | to_role | sort | auto_chain | pre_dispatch_script | post_dispatch_script |
|---|---|---|---|---|---|---|
| supervisor-imple01 | supervisor01_llama | imple01SG | 1 | 1 | `model-allocator start --alias qwen-shared-sglang` | `model-allocator stop --alias laguna-local` |
| imple01-review01 | imple01SG | review01SG | 2 | 1 | — | — |
| review01-supervisor | review01SG | supervisor01_llama | 3 | 1 | `model-allocator start --alias laguna-local` | `model-allocator stop --alias qwen-shared-sglang` |

**Model switching mechanism:**

- **Step 1 (forward, supervisor→imple01):** post_dispatch stops Laguna after
  supervisor completes; pre_dispatch starts SGLang before imple01SG is dispatched.
- **Step 2 (forward, imple01→review01):** No scripts — SGLang remains loaded
  (persistent lifecycle).
- **Step 3 (loop, review01→supervisor):** pre_dispatch starts Laguna before
  supervisor wake-up; post_dispatch stops SGLang after review completes.

Each step has exactly one set of scripts that run in one direction — no ambiguity.

## 4. Governance Templates

Three new files in `docs/governance-templates-v2/`:

### 4.1 `461_LLAMA_SG_SUPERVISOR.md`

- Extends `500_SUPERVISOR.md` (same pattern as 451 extends 500)
- Autonomous wake-up protocol: rebuild from GOAL.md/RUN-LEDGER.md/BACKLOG.md →
  act → persist → stop
- Uses Laguna (llama.cpp, large model) for architecture handoffs in 402 XML format
- Responsible for: writing handoffs, evaluating verdicts, escalating to Human on
  budget exhaustion
- Run artifacts under `{bridge_dir}/llama_SG/runs/{run_id}/`
- Stateless per wake-up (same design as supervisor_auto in 451)

### 4.2 `462_LLAMA_SG_IMPLE01.md`

- Extends `03_IMPLEMENTOR.md`
- Uses shared Qwen via SGLang (OpenCode, openai_compatible provider)
- Receives handoff from supervisor01_llama, implements, produces result
- Same implementation rules as 403/452

### 4.3 `463_LLAMA_SG_REVIEW01.md`

- Extends `04_REVIEW.md`
- Uses same shared Qwen via SGLang
- Single review layer (not two like strict_review)
- Reviews implementation against handoff, produces verdict

## 5. Skill — LLAMASG

New file: `.claude/skills/LLAMASG/SKILL.md`

Cold-start procedure for supervisor01_llama. Follows the same 7-step pattern as
SUPERVISEDREVIEW, adapted for the llama_SG flow:

| Step | SUPERVISEDREVIEW | LLAMASG |
|---|---|---|
| 1 | Resolve bridge dir | Same |
| 2 | Read GOAL.md, RUN-LEDGER.md, BACKLOG.md | Same, from `{bridge_dir}/llama_SG/runs/{run_id}/` |
| 3 | Confirm flow counter | `flow_key='llama_SG'` |
| 4 | Read 451 | Read `461_LLAMA_SG_SUPERVISOR.md` |
| 5 | Verify environment (tmux sessions) | tmux: supervisor01_llama, imple01SG, review01SG |
| 6 | Determine chain position (watchdog) | `--flow llama_SG` |
| 7 | Report to Human | Same table format |

**Additional Step 5 checks (runtime health):**

```bash
# Verify Laguna is reachable (when supervisor is active)
curl -s http://127.0.0.1:8080/health

# Verify SGLang/Qwen is reachable (when chain is in imple/review phase)
curl -s http://127.0.0.1:30000/health
```

## 6. Shared-Runtime Isolation

The SGLang server is shared between imple01SG and review01SG. The following
MUST remain isolated per role:

- Conversation history
- OpenCode session
- Role prompt
- Handoff ID
- Tool results
- Working directory
- Repository state (except intentional filesystem sharing)

The following MAY be shared:

- Qwen model weights
- SGLang server process
- GPU memory pool
- Prefix-cache infrastructure
- API endpoint

**Session policy:**
- `shared_model: true`
- `shared_conversation: false`
- `separate_session_per_role: true`
- `new_session_per_handoff: true`

## 7. Implementation Phases

### Phase 1 — Model Allocator (no dependencies)
1. SGLang adapter (`adapters/sglang.py`) + tests
2. Laguna profile in `runtime_profiles.yaml` + `models.yaml`
3. SGLang profile + qwen-shared-sglang alias
4. Role configuration in `roles.yaml`
5. `schema.py` update with SGLang fields

### Phase 2 — Database (depends on Phase 1)
6. Migration: new flow + 3 roles + 3 steps
7. i18n labels for new roles

### Phase 3 — Governance (depends on Phase 2)
8. `461_LLAMA_SG_SUPERVISOR.md`
9. `462_LLAMA_SG_IMPLE01.md`
10. `463_LLAMA_SG_REVIEW01.md`

### Phase 4 — Skill (depends on Phase 3)
11. `.claude/skills/LLAMASG/SKILL.md`

### Phase 5 — Live Test
12. Install SGLang + download Qwen model
13. Start Laguna → start SGLang → manual chain test
14. Benchmark: tool-call rate, VRAM, tokens/s, review quality

## 8. Verification

- `model-allocator validate --alias laguna-local` → OK
- `model-allocator validate --alias qwen-shared-sglang` → OK
- `model-allocator start --alias qwen-shared-sglang` → health OK
- `model-allocator stop --alias qwen-shared-sglang` → VRAM released
- Flow counter in DB → `llama_SG` starts at 1
- `/llama_SG` skill → rebuilds supervisor context correctly
- All existing model-allocator tests stay green
- `python3 -m py_compile` passes on all changed files

## 9. SGLang Prerequisites (from user spec)

Before the SGLang adapter can be validated:

1. **Installation:** `python3 -m venv /home/svend/venvs/sglang` + `pip install "sglang[all]"`
2. **Model:** Download verified SGLang-compatible quantized Qwen3-Coder-30B-A3B
   to `/home/svend/models/sglang/<model-dir>/`
3. **Tool-call validation:** ≥20 test calls, record success rate
4. **VRAM measurement:** startup, idle, peak at 32k context
5. **Concurrency:** test 1→2→4 concurrent requests
6. **OpenCode compatibility:** repository inspection, file edits, test execution

The SGLang runtime may be marked validated only when all acceptance criteria pass.
