# Current Research Model — Tools, Sources, Models and Data-Flow Audit

**Audited:** 2026-08-23 · **Target:** `/home/svend/AI-Genealogy-Research-Assistant` @ `0305c45` (run 051 closed; run 052 Phase B in flight)
**Live data measured against:** `~/Genealogy/research.db` (schema 0028), `~/Genealogy/archives.db` (22.5M rows), `~/Genealogy/pages/` (2 acquired pages)
**Authoritative product documents:** `DIRECTION.md` (north star), `docs/POST-V1-VISION-ROADMAP.md` (vision + Danish specialization), `docs/WORKING-VALIDATED-TREE-UI.md` (tree UI spec)

This audit answers three questions:

1. **What does the research model produce today** that can serve as canonical evidence now and supervised training data tomorrow?
2. **What is planned going forward?**
3. **Where does the vision layer fit** into the ten-stage research chain?

---

## 1. The Ten-Stage Chain — What Exists Today

Every stage below names its tools (modules + CLI), its sources, its models, its
persistence, and its live status. The chain is the organizing spine of the
whole system; the stages that exist were built by preferred_cloud runs 019–051.

### Stage 1 — Source discovery

| | |
|---|---|
| **Tools** | `sources/registry.py`, `sources/provider.py`, `sources/search.py` (`search-records` CLI), `sources/kip.py`, `sources/linklives.py`, `sources/archive_adapter.py` |
| **Sources** | **KIP censuses** (salldata.dk, 1769–1940, 22.5M rows in `archives.db`, non-commercial license, `kipdata.txt` as place authority), **Link-Lives** (linked life-courses), **Rigsarkivet** (`sources/rigsarkivet.py`, run 044 — live book location proven, bsid:172376 found live), **MyHeritage** (READ_ONLY browser capture, `capture-person`), **GEDCOM imports** (two family trees, run 035) |
| **Models** | None — deterministic search with Danish name-folding (æ/ø/å ⇄ ae/oe/aa, archive name tables, birth-year tolerance, the 1905 limit). Documented in `docs/SEARCH-MATCHING.md`. |
| **Persistence** | `archives.db` (independent shared corpus), `sources`, `import_sources`, `historical_sources` |
| **Status** | **LIVE.** "Not found" is trustworthy within documented bounds — that documented negative is itself evidence (DIRECTION §21). |

### Stage 2 — Archive/page retrieval

| | |
|---|---|
| **Tools** | `locate-book` CLI (Rigsarkivet adapter, run 044), `sources/local_archive.py` (run 031 — real Link-Lives/KIP headers) |
| **Sources** | Rigsarkivet church books (bsid-addressed); local archival corpora |
| **Status** | **LIVE** for Rigsarkivet church books; the run-031 lesson stands: readers are built against **real** corpus headers, never authored fixtures alone. |

### Stage 3 — Image acquisition

| | |
|---|---|
| **Tools** | `acquire-pages` CLI (`sources/page_acquisition.py`, run 047), documented in `docs/PAGE-ACQUISITION.md` |
| **Persistence** | `page_acquisitions`, `source_pages`, page store `~/Genealogy/pages/{provider}/{book}/{page}.jpg` — **every page sha256-pinned at acquisition**, rights policy recorded, per-invocation cap |
| **Status** | **LIVE**, 2 real church-book pages acquired and hash-verified. Hash discipline means every downstream reading is traceable to an immutable image. |

### Stage 4 — Vision/OCR transcription  ← **the vision layer** (see §3 below)

| | |
|---|---|
| **Tools** | `agents/vision.py` (`VisionClient`, schema validation, `read-page` — run 048 blind pass), `read-region` + `page_regions` (run 049 region extraction), `read-page-contextual` (run 050 contextual pass), `agents/vision_compare.py` + `compare-observations` (run 050 — blind vs contextual comparison, PROBABLE-confidence computation) |
| **Models** | Vision-capable local models via configurable backend (`config/settings.yaml` `vision:` block — fake / OpenAI-compatible / **ollama-native with `think:` control**). Run-048 lesson: gemma4-thinking loops on real pages; `think:false` requires the native `/api/chat` path. |
| **Persistence** | `vision_observations` (raw AND normalized values kept separate — roadmap §16), `page_regions` (pixel boxes), `observation_comparisons`, `uncertain_readings` (§14 escapes) |
| **Status** | **BUILT, chain-proven; live-throughput pending.** Run 050's G50.e measured 0/61 on real pages — that is honest §14 evidence (bracket-escapes + uncertain readings), feeding the planned §11 no-think region-extraction contract. |

### Stage 5 — Structured record extraction

| | |
|---|---|
| **Tools** | `import-archive` CLI, `sources/local_archive.py` readers; vision-side: the §15 structured vision schema enforced by `agents/vision.py::validate_observation` |
| **Persistence** | `archive_records`, `vision_observations` (schema-validated entries with relations) |
| **Status** | **LIVE** for text corpora (60,851 real rows loaded in run 031); vision-side schema enforced, throughput follows the vision track. |

### Stage 6 — Entity/person matching

| | |
|---|---|
| **Tools** | `reconcile` CLI (tree A × tree B scoring, run 035), `propose-archive-candidates` (runs 036–037), matcher identity rules (run 032 — ties-as-facts eliminated, run 034 — name-equivalence æ/ø/å) |
| **Persistence** | `tree_matches` (324 rows), `archive_candidates` (208), `external_identities` (688), `name_standardisations`, `candidates` |
| **Status** | **LIVE.** Human-pinned Danish name-equivalence rules apply (Kristian≠Christian without archive mapping). Known open item: R7 (Christen/Christian fold) and year-only matching for KIP 1860/1880. |

### Stage 7 — Evidence assessment

| | |
|---|---|
| **Tools** | `rate-candidates` (run 042 — mechanical, deterministic rating), evidence ranking (run 038 — **evidence keeps its rank**; archive sources are rank 6–7 and can never reach VERIFIED on their own), source provenance (run 043 — `ArchiveAdapter`, citation columns) |
| **Persistence** | `claims` (23), `evidence` (26, with `source_rank`), `sources` (26 with human-readable KIP citations), `archive_candidate_ratings` (208), `conflicts` (34), `archive_ambiguities` (156) |
| **Status** | **LIVE.** Deterministic authority holds (DIRECTION §22): scores are not statistical probabilities; rank policy is code, not model output. |

### Stage 8 — Candidate relationship update

| | |
|---|---|
| **Tools** | `propose-merges` / `decide-merge` / `apply-merges` / `undo-merge` (runs 027, 045), `decide-archive-candidate` |
| **Persistence** | `merge_proposals` (55), `merge_applications` (18), decided candidate rows |
| **Status** | **LIVE**, merge loop closed in run 045 (bulk apply proven; intra-tree duplicate 119/130 backlogged). |

### Stage 9 — Research decision

| | |
|---|---|
| **Tools** | **Adjudication surface** on port 9180 (`web/app.py` + `adjudication.js`, runs 039/041/046 — column filters, citations rendered, 4-locale i18n), running durably as user unit `genealogy-adjudication.service` |
| **Models** | Human is the deciding authority today. The LLM orchestrator (`research-person`, run 022) runs **four semantic roles** — `researcher`, `document_reader`, `genealogist`, `reviewer` (`agents/roles.py`) — provider-agnostic (`agents/llm_client.py`; fake / OpenAI-compatible backends; JCL live acceptance passed with gemma4:12b), persisting every call in `llm_calls`/`llm_campaigns`. |
| **Persistence** | `audit_log` (43 rows — every decision audited), adjudicated candidate/merge rows |
| **Status** | **LIVE.** 208-candidate queue rated mechanically (26/90/2/90); Human adjudication ongoing. |

### Stage 10 — Working Tree / Validated Tree

| | |
|---|---|
| **Tools** | `GET /api/tree/working`, `GET /api/tree/validated`, `/tree` page (run 051 Phase A — read-only projections, threshold as pure view filter); Phase B drill-down drawers **in flight** (run 052); `database/repositories/tree.py`, `drilldown.py` |
| **Persistence** | Projections only — no new stores. Policy string `VERIFIED+PROBABLE` owned by the backend. |
| **Status** | **LIVE** (Phase A accepted against the real DB 2026-08-23). |

---

## 2. What the Chain Produces Today — Canonical Evidence Now, Training Data Tomorrow

Everything below is **already persisted, provenance-carrying, and audit-logged** —
which is exactly what makes it usable as supervised training data later
(roadmap §§43–51 make this explicit for the Danish specialization).

| Artifact (today) | Canonical-evidence value | Supervised-training value tomorrow |
|---|---|---|
| **Claim → evidence → source chains** (23 claims, 26 evidence rows with `source_rank`, 26 KIP citations) | The evidence-first spine (DIRECTION §20); every claim separates status from confidence (§19/§11) | Labeled examples of "this archive row supports this genealogical claim at this strength" — record-linkage training pairs (roadmap §48) |
| **sha256-pinned page images + acquisition metadata** (page store, rights policy) | Immutable source identity (§23–24) — a reading is always re-checkable against the exact image | The raw-image half of every future OCR/HTR training pair (§45) |
| **`page_regions` pixel boxes** (6 rows) | Region-level source anchoring for evidence display (Tree UI Phase D) | Layout/segmentation labels for Danish church-book pages |
| **Blind + contextual vision passes over the same page** (`vision_observations`, raw AND normalized kept separate per §16; `observation_comparisons`; `uncertain_readings`) | §14's honesty mechanism: context never overwrites the blind reading | **The single richest future dataset**: (image region → blind transcription → contextual transcription → eventual human-verified truth) quadruples — direct HTR fine-tuning data (§45, AGRA-DK-LoRA §49) |
| **Mechanical candidate ratings + Human adjudications** (208 ratings; decided rows; `audit_log`) | Deterministic rating is reproducible; every human decision is audited | Gold labels for matcher training: features (name fold, year distance, place) → human accept/reject (§48 benchmarking) |
| **Merge proposals + decisions** (55 proposals → 17 applied / 24 ignored / 14 open) | Canonical person identity maintenance with undo | Same-person/different-person labeled pairs |
| **`tree_matches`** (324 cross-tree classifications) | Cross-project identity comparison (DIRECTION §15) | Additional record-linkage labels |
| **Danish name-fold decisions** (`name_standardisations`, Human-pinned equivalence rules) | Deterministic, documented folding | Seed lexicon for historical Danish name normalization (§46) |
| **Documented negatives** ("not found" within bounds, `archive_ambiguities`, `conflicts`) | Negative evidence is recorded, not discarded (DIRECTION §21, roadmap §35) | Hard negatives — the class most training sets lack |
| **`llm_calls` / `llm_campaigns`** (schema ready, 0 rows live) | Full prompt/response provenance for every model involvement | Distillation and evaluation traces once live throughput starts |

**The principle that makes this reusable:** nothing overwrites prior evidence
(roadmap §27), raw is kept beside normalized (§16), and every mutation lands in
`audit_log`. Today's operational exhaust *is* tomorrow's dataset because it was
designed to be — provenance-first, append-only, deterministic where possible.

---

## 3. Where the Vision Layer Fits

The vision layer **is stages 3→5** of the chain, implemented by runs 047–050 as
four CLI-driven steps, each persisting before the next begins:

```
Source discovery              search-records (KIP / Link-Lives / Rigsarkivet)   LIVE
    ↓
Archive/page retrieval        locate-book (Rigsarkivet bsid)                    LIVE
    ↓
Image acquisition             acquire-pages → sha256-pinned page store          LIVE      ┐
    ↓                                                                                     │
Vision/OCR transcription      read-page (blind, §14) · read-region (§11)                  │ THE
                              read-page-contextual (§14) ·                     BUILT      │ VISION
                              compare-observations (blind vs contextual)                  │ LAYER
    ↓                                                                                     │
Structured record extraction  §15 schema validation → vision_observations      BUILT      ┘
    ↓
Entity/person matching        reconcile · propose-archive-candidates           LIVE
    ↓
Evidence assessment           rate-candidates · rank policy (rank 6-7)         LIVE
    ↓
Candidate relationship update propose/decide/apply-merges                      LIVE
    ↓
Research decision             adjudication surface (port 9180) + 4 LLM roles   LIVE (Human decides)
    ↓
Working / Validated Tree      /api/tree/working · /api/tree/validated          LIVE (Phase A; B in flight)
```

Key architectural facts about the vision layer's position:

- **It feeds the same evidence model as the text corpora.** A vision reading
  becomes an evidence candidate (roadmap §17) with a source rank — it does not
  get a privileged path into the tree. Deterministic validation (§18) and
  cross-source verification (§19) sit between the model output and any claim.
- **Blind-before-contextual is mandatory** (§14): the blind pass reads without
  genealogical context; the contextual pass may resolve uncertainty but never
  replaces the blind record. `compare-observations` computes agreement and a
  PROBABLE-bounded confidence.
- **The current bottleneck is measured, not guessed:** run 050's live gate
  scored 0/61 on real pages with a thinking model — the documented fix path is
  the §11 region-extraction contract with native `think:false` (Human choice
  (a) at run 048's close). This is the next vision-track run after the tree-UI
  sequence.
- **Escalation, not automation** (§§21–22): low-agreement readings escalate to
  stronger models and ultimately the Human; source refresh must never become
  automatic truth replacement (§34).

---

## 4. What Is Planned Going Forward

Ordered per the approved pipeline and the Human-pinned roadmap:

1. **Tree UI Phases B–F** (runs 052–056, approved 2026-08-23, autonomous with
   rolling commit+push): B drill-down drawers (in flight, run 052) → C
   candidate groups + interactive threshold → D historical evidence (page
   images, region overlays, blind-beside-contextual display — the vision
   layer's data becomes visible in the tree) → E directed research (research
   commands writing `research_tasks` only — the first tree-UI mutation path)
   → F autonomous tree expansion (Working Tree grows autonomously; canonical
   policy independently controls the Validated Tree).
2. **The vision-track §11 run**: no-think region extraction against real
   church-book pages, closing the measured 0/61 gap; then §14 contextual
   throughput at scale.
3. **The relationship-status gap** (measured 2026-08-23 at run 051's live
   acceptance): all 2,060 real relationships carry status UNKNOWN — the
   Validated Tree is legitimately empty because **nothing yet promotes
   adjudication decisions into relationship statuses**. Phase E/F plus the
   §17 evidence-candidate model must close this loop; it is the single most
   important missing edge in the chain above.
4. **Source revalidation** (roadmap §§23–36): source versioning, refresh
   queues, re-reading with better models — never overwriting prior evidence,
   with the §35 critical negative test and §36 source-upgrade test as
   acceptance gates.
5. **Danish genealogy AI specialization** (Human-pinned, roadmap §§43–51):
   a Danish genealogy benchmark (§44) built from the audited decisions above;
   Danish historical handwriting recognition (§45) trained on the
   image/blind/contextual/verified quadruples; historical Danish language
   tools (§46); record-linkage benchmarking (§48); **AGRA-DK-LoRA** (§49,
   experimental) — with model/dataset upgradeability (§50) guaranteed by the
   provenance discipline audited in §2.
6. **Autonomy** (DIRECTION §§23–25 + Human-pinned 2026-08-21 goal): the tree
   is to grow **without human involvement in the loop** — review becomes
   escalation, not a gate. Termination rules (§24 of the tree-UI spec's Phase
   F expectations), expansion audit, and an autonomous-mode toggle are the
   binding conditions; run 056 concretizes them.

**The through-line:** today's model is a deterministic, evidence-first,
Human-adjudicated pipeline in which LLMs propose and code disposes. Every stage
already writes the provenance that the planned autonomous and Danish-specialized
versions will train on and be measured against. The research model is, by
design, generating its own future training corpus as a side effect of doing
honest genealogy today.

---

*Prepared by the preferred_cloud supervisor (Pre-super-cl) on Human request,
2026-08-23. Facts measured against the live databases and the repo at
`0305c45`; run 052 (Phase B) was mid-flight with handoff 143 dispatched at the
time of writing.*
