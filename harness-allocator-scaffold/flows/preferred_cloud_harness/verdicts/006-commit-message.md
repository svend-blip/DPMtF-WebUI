[preferred_cloud_harness run002] Repair TG1 test fixture and remove shadowed duplicate test block

Human-authorized scope expansion confined to tests/test_preferred_cloud_harness.py:

- Repair test_seam_idle_reader_handles_eintr to model a finite, realistic
  EINTR + idle-input condition: the fake stream now raises EINTR exactly once,
  serves the data exactly once, then idles/EOFs, instead of re-serving the same
  bytes forever. The test's original intent (interrupted sentinel -> clear() ->
  one real frame) is unchanged.
- Remove the shadowed duplicate copy of the five Run 002 seam tests (the first
  copy was dead due to module-level redefinition; only the second was collected).
  Each seam test and helper now appears exactly once.

No production source changed; no assertion weakened. TG1 now passes without
deselection (74 passed). TG2-TG9 remain green; TG10 remains the already-obtained
Human-observed live acceptance.

No commits, pushes, stages, stashes or reverts were performed by any autonomous
role (GOAL.md §14) — this message is prepared for the Human to commit.
