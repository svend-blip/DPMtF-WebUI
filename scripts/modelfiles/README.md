# Trade-chain model variants (context right-sizing, 2026-07-11)

The Ollama service default is `OLLAMA_CONTEXT_LENGTH=131072` — models
without an explicit num_ctx allocate 128k KV cache, spilling to CPU and
stalling roles. These variants pin measured-need context per role
(peak estimate + small margin; all fit GPU-only on the RTX 5090):

| Variant | FROM | num_ctx | Roles |
|---------|------|---------|-------|
| qwen3.6-35b-48k | qwen3.6:35b-a3b | 49152 | trend01 |
| qwen3.6-35b-32k | qwen3.6:35b-a3b | 32768 | risk01 |
| qwen3.6-27b-32k | qwen3.6:27b-q4_K_M | 32768 | sim01, portfolio01, score01, learn01 |
| ornith35b-q5-48k | ornith35b-q5-64k | 49152 | review01 (OpenCode + trade-mcp/onyx-mcp) |

market01 + analyst01 use the existing `qwen3.6:35b-a3b-64k` tag
(search-heavy roles, measured peaks ~50-61k).

Rebuild: `ollama create <name> -f <file>.Modelfile`
