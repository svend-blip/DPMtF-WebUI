# 25 — DECISIONS

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Append-only record of all significant project decisions with context and
rationale. This is the project's institutional memory for why things were
done a certain way.

## When to Use

- **All roles:** Record any decision that affects architecture, scope, process,
  or cross-project alignment.
- **After `/clear`:** Reference to understand past decisions.

## Rules

1. **Append-only** — add new entries at the bottom. NEVER edit or remove
   existing entries.
2. **Each entry MUST include:** date, decision, rationale, consequences,
   and the role/person who made the decision.
3. **Reference related files** using the `[[filename]]` notation.

---

## Decision Log

### [YYYY-MM-DD] — {Decision Title}

**Decision:** {What was decided — clear and unambiguous.}

**Rationale:** {Why this decision was made — context, alternatives considered,
trade-offs evaluated.}

**Consequences:** {What this decision means going forward — what is now allowed,
disallowed, or changed.}

**Made by:** {Human | Architect | Review — with Human approval reference if applicable.}

**References:** {Related governance files, commits, or decisions.}

---

### [2026-08-05] — Evidence Discipline for results and verdicts (all flows)

**Decision:** A reviewer reviews the working tree, never the implementer's
result file. Every verdict MUST carry an Evidence section containing commands
the reviewer actually ran and their actual output; copying output out of the
result file is forbidden; a claim that could not be verified is REJECTED. An
implementer MUST report only edits that appear in `git status --short` and may
never invent command output — declining a change with a stated reason is a
legitimate result. A supervisor MUST confirm an APPROVED verdict against
`git status` before recording a testgoal green, and must not act at all on a
verdict lacking an Evidence section.

**Rationale:** In `llama_SG` run 002, handoff 005 returned an implementation
report claiming three file changes in convincing detail — including a quoted
markdown link it said it had inserted and a pasted grep output reading
"Returns ZERO results after changes". Nothing had been changed; the files had
not been modified in weeks (`README.md` 2026-08-04, `pre-dispatch-import.py`
2026-07-04, `initialize_new_webui.py` 2026-06-18). review01SG then approved it
with four checkmarks, having read the report rather than the repository. Two
independent models fabricated in the same direction and confirmed each other.
Existing governance said *what* to check but never *how*, and never forbade
treating the result file as evidence. Two roles concurring is not evidence.

**Consequences:** Applies to every flow. Base files carry the rule
([[03_IMPLEMENTOR]], [[04_REVIEW]], [[500_SUPERVISOR]]); the flow-specific
files that define their own verdict format and therefore take precedence
carry a compact restatement ([[405_STRICT_REVIEW_REVIEW02]],
[[415_CLOUD_LLM_REVIEW02CLOUD]], [[425_CLOUD_PAY_REVIEW02PAY]],
[[454_SUPERVISED_REVIEW_REVIEW02]], [[461_LLAMA_SG_SUPERVISOR]],
[[462_LLAMA_SG_IMPLE01]], [[463_LLAMA_SG_REVIEW01]]). Verdicts without an
Evidence section are invalid and must be rejected back. Note this is a
prohibition, not an enforcement: nothing yet mechanically rejects a verdict
whose claimed files are absent from `git status`. A post-dispatch validation
gate would make fabrication structurally impossible rather than merely
forbidden, and remains open.

**Made by:** Human (approved 2026-08-05), applied by the assisting session.

**References:** [[04_REVIEW]], [[03_IMPLEMENTOR]], [[500_SUPERVISOR]],
llama_SG run 002 END-REPORT.

### [2026-08-30] — Experimental panel group + flow UI categories (Father UI)

**Decision:** A sixth top-level panel group, **Experimental**, is added as the
LAST section of the Father UI. Prompt Templates moves Daily → Experimental;
Flows moves Periodic → Daily; a new Experimental Flows panel under
Experimental shows flows with `bridge_flows.ui_category = 'experimental'`
(the trade cockpit flows), and the category is editable per flow in the flow
edit form. Empty groups (Journals, Reports, and Periodic once Flows left it)
are hidden via `user_panel_groups.is_visible = 0` until they gain content.

**Rationale:** After a long development run the UI mixed proven daily panels
with half-built and atypical ones. Human directed (2026-08-30 alignment
task): everyday overviews belong in Daily; anything of unproven everyday
value belongs in an explicit Experimental group; trade flows are atypical
and must not mix with the ordinary flows list; empty shells must not render.

**Consequences:** 30_FRONTEND_GOVERNANCE.md's fixed group list now ends with
Experimental. New panels of unproven value go to Experimental first and are
promoted out of it by Human decision. Flow panel membership is data
(`ui_category`), not code. Migrations 087 + 088 carry the change; the seeds
in scripts/init_db.py mirror it.

**Made by:** Human (2026-08-30), applied by the assisting session.

**References:** [[30_FRONTEND_GOVERNANCE]], scripts/db/087_experimental_group.sql,
scripts/db/088_flow_ui_category.sql.

---

## Decision: Test selection policy activated for DPMtF-WebUI

**Date:** 2026-08-31

**Decision:** `.dpmtf/test-policy.json` is authored and active. The
test-impact engine (Runs 002-014 of the 1000 test-minimization program)
now selects tests per change instead of the gate skipping on an empty
policy. Governance amended to match: TECHNICAL_REVIEW check 9 runs the
policy-resolved selection (full suite when the policy is absent, the
scope resolves full, or the selection cannot be verified — escalation
always permitted, narrowing never), IMPLEMENTOR's validation table
reports the run's scope, and 12_CODING_STANDARD gains the Test Selection
Policy section. The engine's own files and the policy file itself are
full-regression triggers: the selector never vouches for itself.

**Made by:** Human (2026-08-31: "forfat politik-udkast til DPMtF nu, og
du skal sikre dig at governance dokumenter rettes så de afspejler
politikken"), authored and applied by the supervising session.

**References:** [[12_CODING_STANDARD]], TECHNICAL_REVIEW.md check 9,
docs/specs/TEST-IMPACT-ARCHITECTURE.md, .dpmtf/test-policy.json.
