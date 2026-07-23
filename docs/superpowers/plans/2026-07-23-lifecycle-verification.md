# Lifecycle Verification Results — 2026-07-23

## Ollama backends

| Alias | Model | Start | Stop | Unload |
|---|---|---|---|---|
| archi-local | qwen3.6:35b-a3b-64k | ✓ | ✓ | ✓ |
| imple01-local | qwen3-coder:30b-256k | ✓ | ✓ | ✓ |
| review01-local | ornith35b-q5-64k | ✓ | ✓ | ✓ |
| review02-local | qwen3.6:27b-q4_K_M | ✓ | ✓ | ✓ |
| review-cloud | qwen3.6:35b-a3b | ✓ | ✓ | ✓ |
| trend-local | qwen3.6-35b-48k | ✓ | ✓ | ✓ |
| coder-96k-local | qwen3-coder-30b-96k | ✓ | ✓ | ✓ |
| coder-48k-local | qwen3-coder-30b-48k | ✓ | ✓ | ✓ |
| learn-local | qwen3.6-27b-32k | ✓ | ✓ | ✓ |

All 9 Ollama aliases verified: model loads via `model-allocator start`,
unloads via `model-allocator stop`, VRAM freed between steps.

## Cloud backends (cloud_noop — no start/stop)

| Alias | Model | Backend | Validate |
|---|---|---|---|
| archi-pay | z-ai/glm-5.2 | openai_compatible (OpenRouter) | WARNING (credentials) |
| imple-pay | moonshotai/kimi-k2.7-code | openai_compatible (OpenRouter) | WARNING (credentials) |

Cloud aliases use cloud_noop lifecycle — no local start/stop needed.
WARNING is expected (API keys are in env vars, not checked at validate time).

## Conclusion

Model Allocator lifecycle management is verified for all active backends.
The unified allocator is the sole source of truth for:
- Model alias resolution
- Model startup (warmup)
- Model shutdown (unload)
- Context limits
- Backend selection
