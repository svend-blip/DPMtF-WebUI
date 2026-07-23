# Handoff Context-Fit Spike — Verdict

**Date:** 2026-07-23

## Question
Can DPMtF determine whether a handoff is safely executable by the selected
local model before queueing it?

## Results (9 tests, all green)

### Fit evaluation
- Small handoff (1 file, 131072 ctx) → FITS ✓
- Large handoff (20 files, 32768 ctx) → SPLIT_REQUIRED ✓
- Medium handoff (3 files, 32768 ctx) → FITS_WITH_LOW_MARGIN or CONTEXT_REDUCTION_REQUIRED ✓
- Continuation splitting works — oversized handoffs are split into chunks that fit ✓

### Budget model
- Components: system_instruction + governance_overhead + handoff_prompt +
  required_file_context + expected_tool_output + expected_model_reasoning +
  output_reserve + recovery_reserve
- Margin = model_context_window - total_with_reserves
- Only FITS and FITS_WITH_LOW_MARGIN may enter the executable queue

### Fit states (6)
- FITS — safe to execute
- FITS_WITH_LOW_MARGIN — executable but watch
- CONTEXT_REDUCTION_REQUIRED — reduce file reads, simplify governance
- SPLIT_REQUIRED — split into continuation jobs
- LARGER_MODEL_REQUIRED — need bigger context window
- HUMAN_REDESIGN_REQUIRED — too complex for any single model

## Verdict: GO

The context-fit spike proves that DPMtF can estimate context budget before
queueing and reject/split oversized handoffs. The allocator supplies the
model context window; DPMtF estimates the handoff's context needs.

Production implementation should add:
- Actual file-size measurement (not estimates) for required_file_context
- Integration with Job Queue — fit check before QUEUED → RUNNING transition
- Automatic continuation job creation when SPLIT_REQUIRED
- Per-role governance overhead measurement (not flat 2000 tokens/file)
