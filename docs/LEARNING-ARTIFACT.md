# LEARNING-ARTIFACT

> **en-US is the standard language for all governance-templates-v2 files.**

A validated learning artifact is one YAML document that records a single
experience from a closed run. DPMtF authors write the draft; the knowledge
service admits it. Admission is the service's act, never the author's.

## Required keys

The artifact carries exactly these fifteen keys, no more and no fewer:

`topic`, `scope`, `repository`, `family`, `run`, `problem`, `approach`,
`result`, `failed_approaches`, `important_files`,
`architecture_implications`, `validation`, `confidence`, `supersedes`,
`admitted_by`.

## Field rules

- `topic` — one sentence naming the lesson.
- `scope` — always `experience`. Learning artifacts record experience,
  never a hypothesis.
- `repository` — the repository the experience came from.
- `family` — a string, the run's family key (e.g. `"2000"`).
- `run` — a string, the run's number (e.g. `"029"`).
- `problem` — the defect or gap the run faced.
- `approach` — what the run changed to address it.
- `result` — what was measured at closure.
- `failed_approaches` — a list of approaches that were tried and did not
  work; empty when none are recorded.
- `important_files` — repository-relative paths with forward slashes.
- `architecture_implications` — what future work must keep true. Always a YAML list, one entry per implication, even when there is exactly one (a bare string is a schema violation).
- `validation` — the validation block described below.
- `confidence` — one of `high`, `medium`, `low`.
- `supersedes` — a list of earlier artifacts, each written as
  `"<family>/<run>"`; empty when none.
- `admitted_by` — `pending` as written by the decomposer; the supervisor
  replaces it at admission.

## Validation block

The `validation` block has exactly three keys:

- `evidence_level` — one of the five admissible levels below.
- `verdicts` — the run's verdict ids that carry the evidence.
- `testgoals` — one string of the form `"<n>/<m> green"` (criteria measured green over criteria in the GOAL), never a list of ids.

## Evidence levels

The five admissible evidence levels, in strength order: `tests`,
`measured_runtime`, `approved_architecture`, `reviewer_conclusion`,
`observation`.

`hypothesis` is never admitted — a draft whose strongest evidence is a
hypothesis is not an experience.

## Choosing the evidence level

Choose the strongest level the run's own evidence supports, never stronger.
A run with passing tests and a reviewer's independent measurement is
`tests`; a run whose only evidence is an observation is `observation`.

## Example — run 029, per-scope store binding

```yaml
topic: "Per-scope LEANN store binding"
scope: experience
repository: "DPMtF-WebUI"
family: "2000"
run: "029"
problem: "knowledge/search.py bound the LEANN index path to the configured scope regardless of the scope being indexed or searched, so foreign scopes had no LEANN store of their own and searches opened the wrong store."
approach: "Bind the index path to the requested scope at the single provider-resolution point and pass the acting scope from each caller, then rebuild the per-scope stores."
result: "resolve_provider binds <scope>.leann when a scope is given and falls back to the configured scope otherwise; all three callers pass scope=; the ecosystem rebuilt one LEANN store per scope."
failed_approaches: []
important_files:
  - "knowledge/search.py"
  - "knowledge/retrieval.py"
  - "knowledge/maintenance.py"
  - "routers/knowledge.py"
architecture_implications:
  - "One LEANN store per scope, named <scope>.leann, resolved at a single point in knowledge/search.py."
validation:
  evidence_level: tests
  verdicts:
    - "001"
    - "002"
  testgoals: "7/7 green"
confidence: high
supersedes: []
admitted_by: pending
```
