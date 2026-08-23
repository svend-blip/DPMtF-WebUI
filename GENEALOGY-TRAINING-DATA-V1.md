# Genealogy Training Data Architecture V1

**Status:** Design, Human-commissioned 2026-08-23 · **Corrections applied:** 2026-08-23 (Human review, 12 points) · **Companion audit:** `CURRENTRESEARCH.md`
**Designed against:** `AI-Genealogy-Research-Assistant` @ `0305c45`, `research.db` schema 0028, `archives.db` (22.5M KIP rows), `~/Genealogy/pages/` page store
**Binding product documents:** `DIRECTION.md` §§18–25, `docs/POST-V1-VISION-ROADMAP.md` §§14–16, 22, 27, 34–36, 43–51

---

## 0. Position and Prime Directive

The operational genealogy databases (`research.db`, `archives.db`, the page
store) **remain the only sources of truth**. This architecture adds exactly one
new kind of component: a **deterministic dataset builder** that produces
training datasets as **reproducible, disposable projections** of canonical,
provenance-carrying research records — the same read-only-projection pattern
already proven by `database/repositories/tree.py`.

Nothing in this design replaces, duplicates, or migrates the evidence-first
persistence model. A generated dataset can always be deleted and rebuilt
byte-identically from the operational databases plus a manifest.

### Architectural invariants (inherited, non-negotiable)

1. **Raw is never overwritten by normalized** (roadmap §16 — both are kept;
   the builder exports both, never merges them).
2. **Blind vision observations stay separate from contextual observations**
   (roadmap §14 — `pass_type` is preserved into every exported record; a
   contextual reading never masquerades as a blind one).
3. **Deterministic evidence/source ranking stays authoritative** (run 038 —
   `evidence.source_rank` is exported verbatim; no model output re-ranks it).
4. **LLM output cannot promote evidence into validated genealogy** — and by
   extension: model-generated labels can never enter gold training or any
   evaluation split (see §6, label provenance).
5. **Documented negative searches are first-class evidence** (DIRECTION §21)
   — and first-class training data (Family D).
6. **Every training example is traceable to canonical source records** — each
   exported record carries a `provenance` block of table+id references that
   resolve in the operational databases.
7. **Generated datasets are disposable/rebuildable artifacts, never sources
   of truth** — no research code may read a generated dataset; the builder
   only reads operational stores and only writes to the export area.
8. **The assistant must remain fully functional without any project-specific
   LoRA.** Fine-tuning is an optional specialization layer, not a dependency
   of the canonical genealogy architecture. The project always supports
   *generic capable model + canonical evidence model + deterministic
   genealogy policy* without requiring AGRA-Linkage-LoRA,
   AGRA-DK-Research-LoRA or AGRA-DK-HTR-LoRA. This preserves model
   replaceability: future base models can be evaluated without retraining
   the genealogy system.

### The adapter family (naming, bound here)

Three separately named, separately benchmarkable specializations — two on a
text/reasoning base, one on a vision base. They never share weights across
branches; if the branches must exchange information, they do it through the
canonical evidence model, not by combining LoRA weights.

```
General text/reasoning base model
    |
    +-- AGRA-DK-Research-LoRA   (Family A primary; genealogy research/policy reasoning)
    |
    +-- AGRA-Linkage-LoRA       (Family B; record linkage / entity matching)

Vision-capable base model
    |
    +-- AGRA-DK-HTR-LoRA        (Family C; Danish church-book handwriting)
```

The text/reasoning and HTR branches are **not** required to share a base
model.

---

## 1. The Dataset Builder (component definition)

| | |
|---|---|
| **Home** | `training/` package in the genealogy repo (new; future runs TD-1…TD-4, §9) |
| **Reads** | `research.db`, `archives.db`, `~/Genealogy/pages/**` — read-only; canonical-safety bound the same way the tree endpoints are (db file byte-identical after a build) |
| **Writes** | `~/Genealogy/training/{family}/{dataset_id}/vN/` — JSONL shards + `manifest.json` + `MANIFEST.sha256` |
| **CLI** | `python -m app.main build-dataset --family {A\|B\|C\|D} --config <yaml> [--dry-run]` (extends the existing CLI surface; same pattern as `migrate`/`rate-candidates`) |
| **Determinism** | identical inputs (db fingerprints), identical builder version (git sha), identical config (hash) ⇒ **byte-identical output**. Records are sorted by stable key; no wall-clock, no RNG outside the recorded split salt. |

### The manifest (dataset versioning + deterministic regeneration)

Every dataset version ships `manifest.json`:

```json
{
  "dataset_id": "linkage-pairs",
  "family": "B",
  "version": "1.2.0",
  "builder_git_sha": "…",
  "builder_config_sha256": "…",
  "inputs": {
    "research_db_md5": "…",
    "research_db_schema": "0029_drilldown_labels",
    "archives_db_stat": "10994511872:1787064217",
    "page_store_root_sha256": "…"
  },
  "split": {"strategy": "person_cluster", "salt": "…", "ratios": [80, 10, 10]},
  "exclusion_list_version": "…",
  "license_classes_present": ["kip-noncommercial", "private-family"],
  "counts": {"train": 0, "val": 0, "test": 0,
             "by_class": {"positive": 0, "negative": 0, "ambiguous": 0, "rejected": 0}},
  "revokes": ["<dataset_id>@<version> superseded because …"],
  "created_at": "…"
}
```

`inputs` makes regeneration checkable; `revokes` makes revocation auditable
(§7); `license_classes_present` makes the licensing gate mechanical (§6).

### The canonical record envelope (all families)

Every exported record is JSONL with this envelope; family-specific payloads
live under `payload`:

```json
{
  "record_id": "sha256(family + stable-key)",
  "family": "A|B|C|D",
  "class": "positive|negative|ambiguous|rejected",
  "label_provenance": "human_verified|mechanical_deterministic|model_generated|model_generated_human_reviewed",
  "split": "train|val|test",
  "license_class": "kip-noncommercial|rigsarkivet-<policy>|private-family|open",
  "provenance": [{"table": "…", "id": 0}, {"file": "pages/…", "sha256": "…"}],
  "models": [{"model_id": "…", "role": "…", "params": {}}],
  "payload": {}
}
```

- `provenance` entries must resolve in the operational stores at build time —
  a dangling reference fails the build.
- `models` is present whenever a model touched the record's content
  (model/version provenance requirement); empty for purely human/deterministic
  records.
- Where a payload carries **two supervision targets with different
  provenance** (Family A: decision vs rationale, §2), the envelope's
  `label_provenance` reflects the **decision**; the rationale carries its own
  provenance inside the payload.

---

## 2. Family A — Genealogy Reasoning / Research-Policy SFT

Teaches a model **how this project reasons**: the verification vocabulary, the
rank policy, evidence-first argumentation, when to stop (DIRECTION §24).

> **Family A is the primary supervised-data family for the future
> `AGRA-DK-Research-LoRA`.** Family B may contribute auxiliary entity-linkage
> examples, but Family B alone does not constitute genealogy research-policy
> training. The research model's target behaviors are substantially broader
> than linkage: evidence-first reasoning; the distinction between fact,
> inference, candidate, conflict and unresolved state; handling competing
> hypotheses; correct *use* of deterministic source-rank results without
> redefining them; accept/reject/defer/abstain behavior; identifying
> insufficient evidence; stop-versus-continue decisions; selecting the next
> useful research action; explaining why further research is or is not
> justified; and respect for the Working Tree / Validated Tree boundary.

| Dimension | Definition |
|---|---|
| **Source entities** | `claims` + `evidence` (+`source_rank`) + `sources`, `conflicts`, `archive_candidates` + `archive_candidate_ratings` (+ `reviewer_decision`, `decided_by`), `merge_proposals`/`merge_applications`, `audit_log`, `research_tasks` (once populated), the policy texts themselves (`DIRECTION.md` §§18–25 excerpts as system-prompt material), `llm_calls`/`llm_campaigns` (drafts only — see label rules) |
| **Eligibility** | A decision record is eligible when it is **final** (`reviewer_decision` set, or rating verdict in `auto_accept`/`auto_reject` with no later human override), its subject persons pass the privacy filter (§6), and it is not on the exclusion list (§7) |
| **Canonical record schema** | `payload = {"task": "assess_candidate\|assess_claim\|decide_merge\|explain_rank\|stop_or_continue", "context": {evidence bundle: claims with status+confidence separate, evidence rows with supports_claim and source_rank verbatim, source citations}, "instruction": "<policy question>", "target": {"decision": "…", "decision_provenance": "human_verified\|mechanical_deterministic", "rationale": "…", "rationale_provenance": "human_verified\|model_generated\|model_generated_human_reviewed"}}` |
| **Decision vs explanation (two supervision targets)** | The correct **decision** and the quality of its **explanation** are separately traceable, always. A human-verified or mechanically deterministic decision is never downgraded because its explanatory text was model-generated; a polished rationale never upgrades a weak or model-generated decision into gold. The builder preserves both provenance fields verbatim; gold eligibility is judged on `decision_provenance`, rationale usability on `rationale_provenance`. |
| **Human vs model labels** | `decision` from human adjudication ⇒ `human_verified`; from the deterministic rater ⇒ `mechanical_deterministic` (policy is code — counts as gold). Deterministic decisions do **not** invent natural-language rationales. An LLM may generate a rationale from an *already-final* decision ⇒ `rationale_provenance: model_generated`; it becomes `model_generated_human_reviewed` only after explicit Human review; a generated rationale never changes the underlying canonical decision. Role outputs in `llm_calls` are drafts, never targets. |
| **Positive / negative / ambiguous / rejected** | positive = accept/merge decisions; negative = reject/ignore decisions; ambiguous = `tie_parked`, `defer`, `AMBIGUOUS_MATCH` left open — exported with target "escalate/park" (parking IS the policy-correct answer); rejected = decisions later reversed (undo_merge, changed decision) — exported only into Family D as hard cases, never as A-gold |
| **Split strategy** | by **person cluster** (canonical person uuid after merge resolution): every example whose provenance touches a cluster hashes with the cluster key; `sha256(cluster_uuid + salt) mod 100` → 80/10/10 |
| **Leakage prevention** | cluster-level split (a person's accept in train and reject in test is a leak — same cluster, same bucket); policy-text excerpts allowed in every split (they are the constitution, not data); no example may quote another cluster's records |
| **Licensing metadata** | inherited from the evidence rows' sources: KIP-derived ⇒ `kip-noncommercial`; GEDCOM/personal ⇒ `private-family` (local training only, never redistributed) |
| **Model/version provenance** | `models[]` filled from `llm_calls.model`/`backend` for any generated rationale; empty for pure human/mechanical records |
| **Versioning / regeneration** | manifest per §1; rebuild is the only mutation |
| **Unsloth export** | chat-format JSONL: `{"messages": [{"role": "system", "content": <policy excerpt>}, {"role": "user", "content": <context+instruction>}, {"role": "assistant", "content": <decision+rationale>}]}` — direct Unsloth SFT/QLoRA input |
| **Benchmark generation** | held-out test bucket becomes `bench-policy-vN`: decision accuracy + park-when-ambiguous rate (the §24 stop discipline is a scored behavior, not just accuracy) |
| **Revocation** | reversal of any provenance-referenced decision puts the cluster on the exclusion list; next build drops it; manifest `revokes` names the superseded version |

**Today's yield:** small but real — 23 claims / 26 evidence / 26 cited sources,
208 rated candidates, 55 merge proposals with 20+ human decisions, 43 audit
rows. The families grow automatically as adjudication continues.

---

## 3. Family B — Historical Record Linkage / Entity Matching

Teaches (and benchmarks) **same-person / different-person** over Danish
historical records: archive-record matching, ambiguous-match abstention,
spelling/name-variant handling, household and place evidence, deterministic
matcher behavior.

> Family B feeds **`AGRA-Linkage-LoRA`** — the linkage/matching
> specialization. It may additionally contribute compatible auxiliary
> examples to `AGRA-DK-Research-LoRA` training mixes, but it is not, by
> itself, research-policy training (§2). The two adapters remain separately
> benchmarkable even if later experiments investigate multi-task training.

| Dimension | Definition |
|---|---|
| **Source entities** | `archive_candidates` (features: `person_name`, `birth_year`, `parish`/`herred`/`amt`, `score`, `evidence_rank`, `match_kind`, `tie_size`, `distinct_parishes`, `source_release`) + `archive_candidate_ratings` (features: `parent_match`, `spouse_match`, `position_child`, `birth_place_match`, `household_json`) + decisions; `tree_matches` (5-way classification + score + reason); `merge_proposals`/`merge_applications` (incl. `undone_at`); `name_standardisations` + the Human-pinned equivalence rules; `external_identities`; the matched `archives.db` rows (person context) |
| **Eligibility** | pair has a final label: human `reviewer_decision`, or mechanical verdict `auto_accept`/`auto_reject` (deterministic gold), or an applied-and-not-undone merge; both sides pass privacy + license filters; not excluded |
| **Canonical record schema** | `payload = {"left": {tree person: canonical_name, birth/death, places, parents/spouse names}, "right": {archive record: name, year, parish, herred, amt, household}, "features": {mechanical features verbatim}, "label": "match\|non_match\|ambiguous", "label_detail": "exact\|spelling_variant\|census_household\|name_year\|…"}` |
| **Human vs model labels** | human adjudications ⇒ `human_verified`; rater verdicts ⇒ `mechanical_deterministic`; **no model-generated labels exist in this family** (the matcher is deterministic by design — run 042) |
| **Positive / negative / ambiguous / rejected** | positive = accept / merge-applied / `EXACT_MATCH`; negative = reject / ignore / `UNIQUE_PERSON`; ambiguous = `tie_parked` + `archive_ambiguities` (156 rows — exported with tie context, label `ambiguous`); rejected = undone merges + reversed decisions → Family D hard negatives |
| **Split strategy** | by person cluster (tree side) — **and** a secondary `parish-holdout` split variant for out-of-district generalization testing (both recorded in manifest) |
| **Leakage prevention** | cluster split as in A; additionally: the same `archives.db` row (`provider`+`external_id`) never appears in more than one bucket; `household_json` is checked for cross-bucket person mentions |
| **Licensing metadata** | KIP rows ⇒ `kip-noncommercial` (local training only, no redistribution — the salldata license binds); Link-Lives per its terms; tree side ⇒ `private-family` |
| **Model/version provenance** | `models[]` empty (deterministic); `source_release` (corpus version) exported so a KIP re-release can be detected |
| **Versioning / regeneration** | per §1; `source_release` in provenance makes corpus drift visible |
| **Unsloth export** | two formats: (a) chat JSONL ("Do these two records describe the same person? …" → label+reason) for SFT/QLoRA; (b) plain feature JSONL for classical baselines (the roadmap §48 benchmark needs a non-LLM baseline) |
| **Benchmark generation** | `bench-linkage-vN` from held-out clusters: precision/recall per `match_kind`, with the ambiguous class scored on **abstention** (calling a tie is correct; picking a side is the error — run 032's lesson encoded as metric) |
| **Revocation** | undo-merge / changed decision ⇒ cluster excluded + pair moved to Family D; automatic at next build |

**Today's yield:** the strongest family — 208 labeled candidates (26/90/2/90),
324 tree_matches, 55 merge pairs, 156 documented ties, all deterministic or
human-labeled.

---

## 4. Family C — Danish Church-Book Vision / HTR

Teaches transcription of Gothic-hand Danish church records (roadmap §45).

> Family C feeds **`AGRA-DK-HTR-LoRA`** — a **separate vision-branch
> specialization** on a vision-capable base model. Danish church-book
> handwriting recognition is *not* trained into the same LoRA as genealogy
> reasoning, and the HTR branch is not required to share a base model with
> the text/reasoning branch (§0). Its responsibilities: Danish historical
> handwriting recognition, church-book transcription, region-level reading,
> uncertain-character handling, blind transcription, and correction against
> Human-verified transcription. The branches exchange structured information
> through the canonical evidence model, never by combining LoRA weights.

| Dimension | Definition |
|---|---|
| **Source entities** | page store images (sha256-pinned) + `page_acquisitions` (`rights_policy`, `image_hash`, `source_url`) + `source_pages` + `source_representations` + `historical_sources` (`source_identity`, parish, period); `page_regions` (pixel boxes, `kind`, `proposed_by`); `vision_observations` (`pass_type` blind/contextual, `model_id`, `raw_transcription` AND `structured_json` — both, never merged, `schema_version`, `context_of`/`context_text`); `observation_comparisons` (agreement JSON); `uncertain_readings` inside the §15 schema; **`transcription_verifications` (new — §10)** once it exists |
| **Eligibility** | image hash verifies against the store (the run-047 hash discipline is the eligibility gate); region has ≥1 observation; **gold** records additionally require a human verification row (§10) — until that table has rows, Family C exports *silver* only (see labels) |
| **Canonical record schema** | `payload = {"image": "pages/…", "image_sha256": "…", "region": {px box, kind}, "blind": {"raw": "…", "structured": {…}, "model_id": "…"}, "contextual": {"raw": "…", "structured": {…}, "context_text": "…"} or null, "agreement": <comparison_json summary> or null, "target": <human-verified transcription> or null, "uncertain_readings": […], "outcome": "ok\|misread\|empty_extraction\|schema_invalid\|thinking_loop\|unreadable\|disagreement"}` — blind and contextual are separate keys by construction (invariant 2); raw and structured/normalized are separate keys by construction (invariant 1) |
| **Failed attempts are first-class lineage** | Failed model readings and failed configurations are **retained, not discarded**, whenever image, region, model identity, parameters and outcome are known: incorrect transcriptions, empty extractions, schema-invalid responses, thinking-loop behavior (the run-048/050 evidence), unresolved blind/contextual disagreement, unreadable regions, Human-corrected misreadings. They are preserved as lineage and *classified into use* — HTR **correction pairs** (model text + human correction: the most valuable HTR signal), hard negatives, regression tests, model-comparison cases, and prompt/configuration evaluation data — through Family C or Family D. Not every failed or superseded observation is a suitable training *target*; lineage first, use classification second. |
| **Human vs model labels** | `target` from `transcription_verifications` ⇒ `human_verified` (gold, the only class eligible for eval); records with only model transcriptions ⇒ `model_generated` (**silver pool**: usable for self-training experiments, clearly flagged, never eval, never mixed into a gold shard) |
| **Positive / negative / ambiguous / rejected** | positive = verified-correct transcription; negative = verified-as-misread (correction pairs); ambiguous = `uncertain_readings` present or blind/contextual disagreement unresolved; rejected = observation superseded by a re-read (roadmap §§26–27 — the old observation is never deleted; it exports as `rejected` lineage per the failed-attempts rule above, not as gold) |
| **Split strategy** | by **source book** (`source_representations.id` / Rigsarkivet bsid): all regions of a book share a bucket. Never split by page or region — same scribe's hand in train and test is leakage |
| **Leakage prevention** | book-level split; additionally parish+period overlap check between buckets (two books by the same parish/priest land in the same bucket); `context_text` is stripped from blind-pass training targets (context must not leak into blind training) |
| **Licensing metadata** | `rights_policy` from `page_acquisitions` exported verbatim per record; Rigsarkivet images: local-training-only unless the recorded policy says otherwise; no image is copied out of the page store — exports reference store paths + hashes |
| **Model/version provenance** | `model_id` per observation (already captured); `params_json`/`prompt_version` once §10 lands; `proposed_by` on regions |
| **Versioning / regeneration** | per §1; page-store root hash in manifest inputs |
| **Unsloth export** | vision chat JSONL (Unsloth VLM format): `{"messages": [{"role": "user", "content": [{"type": "image", "image": "<store path>"}, {"type": "text", "text": "<transcribe instruction>"}]}, {"role": "assistant", "content": "<target>"}]}` — plus plain `{image, box, text}` TSV for classical HTR toolchains (TrOCR/Kraken) |
| **Benchmark generation** | `bench-htr-vN` from held-out books: CER/WER on gold; plus a **§35 critical-negative section** — pages known to NOT contain the sought person, scored on the model saying so |
| **Revocation** | a reversed verification (human downgrades a previous "correct") excludes the record from gold; §25 source revalidation that supersedes an observation moves the old record to `rejected` lineage automatically |

**Today's yield:** 2 pages, 6 regions, 2 observations, 0 verifications — the
smallest family, by design: it grows exactly as fast as the vision track (§11
no-think run) and the Phase-D verification UI produce. The schema is ready
before the volume arrives, which is the point.

---

## 5. Family D — Evaluation and Hard-Negative Datasets

The measurement layer (roadmap §§35–36, 44, 48).

> **Family D is evaluation-only and MUST NOT be included in LoRA/SFT
> training — including through convenience merges, curriculum mixtures,
> replay buffers or synthetic augmentation pipelines.** This applies even
> when a Family-D case originally came from a training family before being
> revoked. Once a specific record/version is part of an evaluation release,
> its provenance cluster/book stays protected from training-data leakage
> under the split rules, permanently.

| Dimension | Definition |
|---|---|
| **Source entities** | documented negative searches (search bounds from `docs/SEARCH-MATCHING.md` + audit rows for "not found within bounds"); `archive_ambiguities` (156); `conflicts` (34); REJECTED claims; reversed decisions from A/B (undo_merge, changed adjudications); `tree_matches` `CONFLICT` class; §35 critical-negative pages; §36 source-upgrade pairs (old reading vs better-source reading); failed vision attempts classified for evaluation (§4) |
| **Eligibility** | the negative/ambiguity is **documented** (a bound, a tie size, a conflict row — never an absence of data); privacy + license filters as elsewhere |
| **Canonical record schema** | `payload = {"kind": "negative_search\|hard_negative_pair\|ambiguity\|conflict\|critical_negative_page\|upgrade_pair\|failed_reading", "context": {…}, "expected": {"answer": "not_found\|abstain\|conflict_exists\|…", "bound": "<the documented search bound>"}}` |
| **Human vs model labels** | all `human_verified` or `mechanical_deterministic` — model output never defines an eval expectation |
| **Positive / negative / ambiguous / rejected** | this family IS the negative/ambiguous/rejected side of A–C, plus true negatives (searches). `class` reused accordingly |
| **Split strategy** | 100% test — no train/val; drawn only from clusters/books held out of A–C's train buckets |
| **Leakage prevention** | build-time cross-check: no Family-D provenance id may appear in any A/B/C train or val shard of the same release (the builder fails the release otherwise); once in an evaluation release, the cluster/book is protected permanently (see the binding rule above) |
| **Licensing / provenance / versioning** | as §1; benchmarks version independently (`bench-*-vN`) so a model card can pin them |
| **Unsloth export** | eval JSONL + a scoring-spec file per benchmark (metric, abstention rules) — consumed by evaluation harnesses, not by trainers |
| **Benchmark generation** | this family *is* the benchmark generator: `bench-policy`, `bench-linkage`, `bench-htr`, `bench-negatives` — together the **Danish Genealogy Benchmark** (roadmap §44) |
| **Revocation** | a reversed upstream decision can *add* records here (a revoked positive becomes a hard negative) — the one place revocation grows a dataset instead of shrinking it |

---

## 6. Cross-Cutting Rules

**Label provenance ladder** (applies everywhere):
`human_verified` > `mechanical_deterministic` (deterministic policy code —
gold) > `model_generated_human_reviewed` > `model_generated` (aux only).
Eval sets accept only the top two. Invariant 4 in dataset terms: nothing a
model produced can define what correct means. Family A additionally splits
this per target: decision and rationale carry separate provenance (§2), and
neither can borrow the other's grade.

**Deterministic policy stays outside the LoRA.** QLoRA training must not turn
deterministic genealogy governance into learned model behavior that replaces
the authoritative implementation. The following remain code/policy authority,
never model authority: source ranking; evidence-rank ceilings; deterministic
candidate-rating rules; canonical relationship-status promotion requirements;
privacy rules; license gates; dataset eligibility; Working Tree / Validated
Tree policy. The model may learn to *interpret and explain* these results; it
may not become their implementation. The operating pattern is fixed:

```
Model reasoning        →  structured proposal
Deterministic engine   →  policy/rank/validation checks
Canonical state
```

Training examples therefore expose authoritative policy *outcomes* — they do
not teach the model that it is free to recreate or modify the policy.

**Rationales are optional, always** (workflow-neutrality rule): *research
workflow produces training data as a side effect; training-data requirements
must not distort the research workflow.* Concretely: `decision_reason` stays
nullable; existing decisions without rationale remain valid; deterministic
decisions never invent natural-language rationales; an LLM may generate a
rationale from an already-final decision (`model_generated`, upgradable only
by explicit Human review); a generated rationale never changes the underlying
canonical decision.

**Privacy filter:** records referencing persons with no death evidence and
birth after (build year − 100) are excluded from every export; the KIP
born-before-1905 search rule already bounds most of the corpus. The filter is
config, recorded in the manifest.

**Licensing gate:** every record carries `license_class`; the builder refuses
to write a shard mixing incompatible classes, and refuses `--export-for-upload`
(future flag) for any non-redistributable class. KIP (`kip-noncommercial`) and
family data (`private-family`) train **locally only** — which matches the
Unsloth/QLoRA-on-own-hardware target exactly.

**Split determinism:** bucket = `sha256(cluster_key + salt) mod 100`; salt
fixed per dataset lineage and recorded; changing the salt is a new dataset id,
not a new version.

---

## 7. Exclusion / Revocation Mechanism

One new operational table (additive migration — the single new store this
architecture introduces, and it is bookkeeping, not genealogy):

```sql
CREATE TABLE training_exclusions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_table TEXT NOT NULL,      -- e.g. 'merge_applications'
    entity_id INTEGER NOT NULL,
    scope TEXT NOT NULL,             -- 'record' | 'cluster' | 'book'
    reason TEXT NOT NULL,            -- e.g. 'undo_merge', 'decision_reversed',
                                     -- 'verification_downgraded', 'privacy', 'license'
    source_audit_id INTEGER REFERENCES audit_log(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- Populated **automatically** by the operations that already exist:
  `undo-merge`, a changed `reviewer_decision`, a claim moving to REJECTED, a
  verification downgrade. No new workflow — the hooks ride the existing
  commands and write one row.
- The builder subtracts exclusions at generation time; exports record the
  exclusion-list version in the manifest.
- Already-shipped dataset versions are **not** mutated (they are immutable
  artifacts); the next version's manifest `revokes` names them, and because
  datasets are disposable, "revoke" operationally means *regenerate and
  retrain from the new version*.
- A revoked positive flows into Family D as a hard negative where applicable
  (§5) — reversals are signal, not just subtraction. Once it enters an
  evaluation release it is permanently barred from training (§5's binding
  rule).

---

## 8. Model Lineage — the Training Manifest

Dataset manifests (§1) make datasets reproducible. **Every trained LoRA/model
artifact additionally receives a training manifest** so a later comparison can
answer exactly which canonical evidence, dataset release and training
configuration produced the adapter. Minimum contents:

```
base_model_id                    LoRA rank
base_model_revision/hash         LoRA alpha
adapter_name                     target modules
adapter_version                  quantization mode
training_framework               context length
training_framework_version       effective batch size
training_dataset_id              optimizer
training_dataset_version         learning rate
training_dataset_manifest_sha256 epochs/steps
training_config_sha256           seed
evaluation_benchmark_ids         adapter artifact sha256
evaluation_results               created_from_git_sha
```

The traceability chain is end-to-end and mandatory:

```
canonical research records
    → dataset manifest
    → training configuration
    → base model
    → LoRA artifact
    → benchmark result
```

### Two acceptance levels for every training experiment

**Technical acceptance** proves the pipeline: the dataset exports correctly;
Unsloth consumes it; QLoRA completes; the adapter loads; inference works
locally; training is reproducible within the documented constraints.

**Capability acceptance** proves improvement: `base model` vs `base model +
adapter` on the relevant **untouched** benchmark. For
`AGRA-Linkage-LoRA-v0`: improvement on `bench-linkage-v1` **without
unacceptable degradation of abstention behavior**. For
`AGRA-DK-Research-LoRA-v1`: improvement on `bench-policy-vN`, particularly
correct accept/reject decisions, correct defer/park behavior, correct conflict
recognition, correct stop/continue behavior, policy compliance, and
resistance to unsupported relationship promotion.

> An adapter that trains successfully but fails to improve the benchmark is
> an **experimental result, not a model upgrade.**

---

## 9. Implementation Plan (fits the existing run pipeline)

**TD-0 is an early data-preservation requirement, not preparation for a later
experiment.** Its purpose is to prevent future high-value research activity —
Human adjudication, merge decisions, vision throughput, transcription
verification, autonomous research-task generation — from producing incomplete
training provenance. The binding rule (which does not delay the approved Tree
UI or vision work):

> Whenever an upcoming run already touches a relevant table or UI surface,
> include the TD-0 capture field where doing so remains additive, nullable,
> backward-compatible and workflow-neutral.

| Step | Content | When |
|---|---|---|
| **TD-0 — capture fields** (§10) | additive, nullable, workflow-neutral provenance capture | **earliest safe additive-migration opportunity** — standing rider on every upcoming run per the rule above; any remainder as a small dedicated run before substantial new adjudication/vision volume |
| **TD-1 — builder core** | `training/` package: envelope, manifest, split engine, exclusion subtraction, license gate, determinism testgoals (byte-identical rebuild is a TG) | after run 056 closes |
| **TD-2 — Family B + D(linkage)** | richest data today; benchmark `bench-linkage-v1` | after TD-1 |
| **AGRA-Linkage-LoRA-v0** | First Unsloth QLoRA experiment using the Family B chat export. Purpose: validate the training, export and evaluation pipeline (`canonical operational data → deterministic dataset builder → Unsloth export → QLoRA training → held-out benchmark → model comparison`) using the largest and cleanest currently available labeled dataset. **Not** the general Danish genealogy reasoning model. Run only after TD-2 and `bench-linkage-v1` exist. Both acceptance levels (§8) apply. | after TD-2 |
| **TD-3 — Family A + D(policy)** | policy SFT export + `bench-policy-v1` | after TD-2 |
| **AGRA-DK-Research-LoRA-v1** | the genealogy research/policy specialization: Family A primary + selected compatible Family B auxiliary examples; validated on the policy/research benchmark. Separately benchmarkable from the linkage adapter, always. | after TD-3 + the linkage proof |
| **TD-4 — Family C + D(htr)** | vision export; depends on the §11 no-think run for volume and Phase D verification UI for gold | after the vision-§11 run |
| **AGRA-DK-HTR-LoRA-v0** | separate Danish historical-handwriting specialization on a vision-capable base (own branch, §0/§4) | after TD-4 |

### Revised high-level training sequence

```
TD-0  capture missing provenance fields early
  ↓
TD-1  deterministic dataset builder
  ↓
TD-2  Family B + linkage benchmark
  ↓
AGRA-Linkage-LoRA-v0     — technical + capability proof of concept
  ↓
TD-3  Family A + policy benchmark
  ↓
AGRA-DK-Research-LoRA-v1 — genealogy reasoning / research-policy specialization

Vision §11 + verification accumulation
  ↓
TD-4  Family C + HTR benchmark
  ↓
AGRA-DK-HTR-LoRA-v0      — separate Danish historical handwriting specialization
```

The architecture stays modular throughout: canonical research data first,
deterministic dataset generation second, model specialization third. Each TD
run follows the standing contract method (reference implementation, rehearsed
testgoals, mutation testing). Canonical-safety testgoal for every TD run: a
full build leaves `research.db`, `archives.db` and the page store
byte-identical.

---

## 10. Capture These Fields NOW (additive, workflow-neutral)

The audit found exactly where today's schema under-records what tomorrow's
datasets need. Additive capture (proposed `0030_training_capture`, or spread
across upcoming runs per §9's rider rule), no behavior change — every field
nullable, populated when the information is already in hand at write time.
**Priority order:**

| Table | New field(s) | Why (which family starves without it) |
|---|---|---|
| `archive_candidates` | `decision_reason TEXT` | A/B: the rationale behind accept/reject is the SFT target text; today only the verdict survives. One **optional** line at `decide-archive-candidate` time — never mandatory (§6). |
| `merge_proposals` | `decided_by TEXT`, `decision_reason TEXT` | A/B: same, plus label-provenance (human vs mechanical) is currently inferrable only indirectly. |
| `llm_calls` | `prompt_sha256 TEXT`, `response_sha256 TEXT`, `params_json TEXT` | A: without content linkage, role calls are unusable as drafts. Hashes in the DB; full payloads content-addressed under `~/Genealogy/llm_payloads/<sha256>.txt` (operational DB stays small, payloads remain provenance-resolvable). |
| `vision_observations` | `params_json TEXT`, `prompt_version TEXT` | C: `model_id` alone cannot reproduce a reading (think flag, temperature, num_ctx, prompt revision). The run-048 think-loop lesson is exactly a params-provenance lesson — and failed configurations are lineage (§4). |
| `sources`, `historical_sources` | `license_class TEXT` | all: today the license is implicit in `provider`; make it a recorded fact at registration (`register-source` already has the information). |
| **new table** `transcription_verifications` | `(id, observation_id → vision_observations, verdict CHECK IN ('correct','corrected','unreadable'), corrected_text TEXT, verified_by TEXT, verified_at TEXT)` | C: the §22 human-verification step has no landing place today; the Tree-UI Phase D evidence panel is its natural UI, and the table existing first means even ad-hoc verifications accumulate from day one. |
| **new table** `training_exclusions` | (§7) | all: revocation must be a row, not a memory. |

**Explicitly not captured** (rejected as workflow-changing or duplicative):
no mandatory rationale prompts (optional fields only — §6's
workflow-neutrality rule is binding), no denormalized "training views" inside
`research.db` (the builder projects at build time), no image copies outside
the page store.

---

## 11. Summary of What This Buys

- **Today:** 208+324+55 labeled linkage decisions, 23 evidence-first claim
  chains and every future adjudication become reproducible, license-clean,
  leakage-controlled SFT/QLoRA and benchmark material — with zero change to
  how research is done.
- **Tomorrow:** the vision track's blind/contextual pairs plus Phase-D
  verifications feed the first Danish church-book HTR gold set
  (`AGRA-DK-HTR-LoRA`'s branch); the Danish Genealogy Benchmark (roadmap
  §44) falls out of Family D mechanically; `AGRA-Linkage-LoRA-v0` proves the
  pipeline before `AGRA-DK-Research-LoRA` attempts the reasoning model.
- **Always:** the operational databases stay the only truth; every dataset is
  a projection you can delete; every adapter carries its full lineage back to
  canonical rows; and the assistant runs fully without any adapter at all
  (invariant 8).

---

*Prepared by the preferred_cloud supervisor (Pre-super-cl) on Human request,
2026-08-23, against the live schemas (0028) and `CURRENTRESEARCH.md`; Human
corrections (12 points) applied same day. Run 052 (Tree UI Phase B) was
mid-flight at the time of writing.*
