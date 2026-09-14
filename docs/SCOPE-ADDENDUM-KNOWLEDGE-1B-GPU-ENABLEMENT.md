# SCOPE Addendum — GPU Readiness and Enablement on DPMtF

This addendum extends `.flowrunner/2000/SCOPE.md` (Persistent Project and
Ecosystem Memory). It adds one operating requirement and one enablement
milestone. It does not widen the mission.

## 11. GPU Readiness

Measured 2026-09-13 on the DPMtF host: the LEANN backend stores a pruned
index and recomputes passage embeddings at search time through its
embedding server. When the GPU is held by a resident local model the build
of the DPMtF index does not finish (8 seconds on a free GPU, more than 10
minutes without one) and every search aborts the calling process on the
backend's compiled-in 30-second timeout.

Requirements:

1. The knowledge layer states this dependency in its configuration and
   documentation.
2. Every provider exposes a provider-neutral readiness check
   (`preflight`) that the callers run before any retrieval or indexing
   call. The LEANN provider's check requires a CUDA device with at least a
   configured amount of free memory.
3. A provider that is not ready never crashes a caller: the API answers
   503 with the reason, the Prompt Compiler logs the reason and injects
   nothing, the refresh endpoint scans and overwrites nothing.
4. Retrieval is never enabled while a resident local model holds the GPU.

## 12. Enablement on DPMtF

The layer is turned on for DPMtF's own repository:

1. Scope grants are data, seeded through the migration system for the
   triples the Human names.
2. `dpmtf.ini` sets `enabled = true` and `provider = leann`.
3. The index for scope `dpmtf-webui` is built under the configured index
   directory through the product's own indexer and provider.
4. Enablement is proven by one live retrieval through the Prompt Compiler's
   own path, in a fresh process, with its retrieval-log row.

Planning decomposition: GOAL-DRAFT-023 (§11) and GOAL-DRAFT-024 (§12).
