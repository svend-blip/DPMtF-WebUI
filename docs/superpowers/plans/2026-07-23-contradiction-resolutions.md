# Configuration Contradiction Resolutions — 2026-07-23

## 1. sim01_trade

**DB value:** `ollama_model = ornith35b-q5-48k`, `default_model = qwen3.6:35b-a3b-64k`

The DB has conflicting values: `ollama_model` says `ornith35b-q5-48k` but
`default_model` says `qwen3.6:35b-a3b-64k`. The git log shows commit `aee0bcf`
"sim01_trade model: ornith -> qwen3.6:35b-a3b-64k" — the model was changed.

**Resolution:** The git commit is authoritative — sim01_trade uses
`qwen3.6:35b-a3b-64k`. The `ollama_model` column is stale. The alias
`archi-local` (same model, same runtime claude, same provider local_ollama)
is correct for sim01_trade. No separate `sim-local` alias needed.

**Note:** `sim01_trade` has `config_dir: imple01` — this is likely wrong
(should be its own config_dir), but that's an OpenCode config issue, not
a model selection issue. Claude Code roles don't use config_dir.

## 2. Cloud naming

**archi01cloud:** `model_type=ollama`, `ollama_model=qwen3.6:35b-a3b-64k`,
`default_runtime=claude`, `default_provider=local_ollama`. Despite the name
"cloud", this role uses **local Ollama** — same as archi01. The "cloud" in
the name refers to the flow (cloud_llm), not the backend.

**review01cloud:** `model_type=ollama`, `ollama_model=qwen3.6:27b-q4_K_M`,
`default_runtime=opencode`, `default_provider=local_ollama`. Also local Ollama.

**review02cloud:** `model_type=ollama`, `ollama_model=qwen3.6:35b-a3b`,
`default_runtime=opencode`, `default_provider=local_ollama`. Also local Ollama.

**Resolution:** All "cloud" roles use local Ollama backends. Their names
reflect the flow they belong to, not the backend. They will get allocator
aliases on `local_ollama_cuda0` runtime profile, same as their non-cloud
counterparts.

## 3. Freebuff (imple01cloud)

**DB value:** `model_type=cloud`, `cloud_model=Freebuf`,
`default_runtime=freebuff`, `default_provider=""`, `default_model=freebuff-default`

**command_builder.py:** The Freebuff builder (`build_freebuff_command`) simply
resolves the binary and returns `{"env": {}, "argv": [freebuff_bin]}`. No
model selection, no provider, no API key. It's a standalone TUI/runtime,
not an OpenAI-compatible backend.

**machine.local.json:** `binaries.freebuff` = `/home/svend/.nvm/versions/node/v22.22.3/bin/freebuff`
`runtimes.freebuff` = `{"binary_ref": "freebuff"}`

**Resolution:** Freebuff is a **separate execution runtime**, not a model
backend. It does not fit the allocator's alias/backend model — there's no
model to resolve, no backend to start/stop, no API to validate. Freebuff
roles will NOT be migrated to the allocator. They remain on a direct path
(using a simplified command builder that only resolves the binary).

The allocator's `headless` client + `invoke` capability could potentially
wrap Freebuff in the future, but that requires verifying Freebuff's actual
protocol — which is out of scope for this migration.

**Action:** `imple01cloud` is excluded from migration. Document this in
the migration script.

## 4. Client-specific aliases — sharing rules

Roles may share an alias only when ALL of these match:
- Same concrete model
- Same backend (runtime_profile)
- Same context limit
- Same lifecycle policy
- Same client configuration (claude-code vs opencode)
- Same extra arguments (--bare etc.)
- Same output token policy

**Sharing analysis from inventory:**

| Model | Roles | Same client? | Can share? |
|---|---|---|---|
| qwen3.6:35b-a3b-64k | archi01, archi01cloud, analyst01_trade, sim01_trade | All claude | YES — `archi-local` |
| qwen3.6:27b-q4_K_M | review01cloud, review01pay, review02 | All opencode | YES — `review02-local` |
| qwen3.6:35b-a3b | review02cloud, review02pay | All opencode | YES — `review-cloud` |
| qwen3-coder-30b-48k | risk01_trade, score01_trade | Both claude | YES — `coder-48k-local` |
| qwen3-coder-30b-96k | market01_trade, portfolio01_trade | Both claude | YES — `coder-96k-local` |

**Note on max_output_tokens:** market01_trade and portfolio01_trade have
`max_output_tokens=81920` in the DB. This is a per-role override, not a
per-alias value. The allocator's `--max-output-tokens` CLI passthrough
(Phase 1, Task 1.3) handles this — the alias declares a default, and
start_coding.py passes the per-role DB value as an override.

## 5. Proposed alias mapping (final)

| Alias | Model | Backend | Client(s) | Roles |
|---|---|---|---|---|
| `imple01-local` (exists) | qwen3-coder:30b-256k | ollama | opencode | imple01 |
| `imple01-claude` (exists) | qwen3-coder:30b-256k | ollama | claude-code | (unused, keep) |
| `archi-local` | qwen3.6:35b-a3b-64k | ollama | claude-code | archi01, archi01cloud, analyst01_trade, sim01_trade |
| `trend-local` | qwen3.6-35b-48k | ollama | claude-code | trend01_trade |
| `coder-96k-local` | qwen3-coder-30b-96k | ollama | claude-code | market01_trade, portfolio01_trade |
| `coder-48k-local` | qwen3-coder-30b-48k | ollama | claude-code | risk01_trade, score01_trade |
| `learn-local` | qwen3.6-27b-32k | ollama | claude-code | learn01_trade |
| `review01-local` | ornith35b-q5-64k | ollama | opencode | review01 |
| `review02-local` | qwen3.6:27b-q4_K_M | ollama | opencode | review01cloud, review01pay, review02, review01_trade |
| `review-cloud` | qwen3.6:35b-a3b | ollama | opencode | review02cloud, review02pay |
| `archi-pay` | z-ai/glm-5.2 | openrouter | claude-code | archi01pay |
| `imple-pay` (exists as imple01-local) | moonshotai/kimi-k2.7-code | openrouter | opencode | imple01pay |

Wait — imple01pay currently has `default_model_alias = imple01-local` which
resolves to `qwen3-coder:30b-256k` on local Ollama. But the DB says
`default_model = moonshotai/kimi-k2.7-code` with `default_provider = openrouter`.
The allocator alias `imple01-local` has `clients.opencode = true` but uses
local Ollama, not OpenRouter. This is a contradiction — imple01pay is
configured to use the allocator but with an alias that points to the wrong
backend.

**Resolution for imple01pay:** Create a new alias `imple-pay` on the
`cloud_openrouter` runtime profile with `real_model = moonshotai/kimi-k2.7-code`.
Update the DB to use `default_model_alias = imple-pay` for imple01pay.

**Excluded from migration:**
- All human roles (human, humancloud, humanpay, humantrade)
- `imple01cloud` (Freebuff — separate execution runtime, not a model backend)
