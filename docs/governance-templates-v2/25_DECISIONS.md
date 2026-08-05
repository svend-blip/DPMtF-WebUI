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
