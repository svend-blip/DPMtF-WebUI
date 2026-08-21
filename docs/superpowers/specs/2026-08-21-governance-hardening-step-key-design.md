# DPMtF Governance Hardening — Step-Key Governance and Unified Execution Resolution

> Human-provided task specification, 2026-08-21 (verbatim below the metadata).
> Destination: `docs/superpowers/specs/2026-08-21-governance-hardening-step-key-design.md`
> in DPMtF-WebUI, committed at the next safe boundary (run 007 closure — the
> tree is the active run's measured object until then).
> Pipeline mapping decided with the Human: see memory
> `governance-hardening-step-key` and the analysis in the conversation.

## Objective

Reduce the rapidly growing number of DPMtF governance files by decoupling governance policy from concrete role names and flow-specific role instances.

At the same time, establish one consistent resolution model for:

* Governance
* Model source
* Model alias/profile
* Harness source
* Harness profile/client

The core architectural principle is:

> **A Role defines defaults. A Step defines the concrete execution configuration. Step configuration overrides Role configuration.**

This must be implemented as an additive, backward-compatible hardening of the existing BridgeV002 architecture.

Do not redesign the bridge or break existing flows.

## 1. Current Problem

DPMtF currently associates governance primarily with `bridge_roles`
(`governance_file`, `default_model_source`, `default_model_alias`,
`allocator_client`), while `bridge_flow_steps` already supports
`model_source`, `model_alias`, `implementation_mode`. Model selection has
partially moved to step level; governance remains role-bound. Result:
near-identical per-instance governance files (403/413/423/452/462/472/492/512
IMPLE-variants) that embed concrete role/flow/next-role/filename identities.
A new flow+role+model+harness combination must NOT require another
almost-identical governance file.

## 2. Target Model

Governance describes a **behavioral role or policy** (SUPERVISOR / ARCHITECT /
IMPLEMENTOR / REVIEW — or the existing generic 02/03/04 files), not a runtime
role instance. Several Step Keys may reference the same governance file. Role
identity is runtime context, not governance content.

## 3. Step-Key Governance

Add optional `bridge_flow_steps.governance_file`. It governs the actor in
`bridge_flow_steps.from_role`. The governance file must not need to name the
role; the runtime knows flow_key/step_key/from_role/to_role and injects it.

## 4. Runtime Governance Context

Deliver a small deterministic RUNTIME CONTEXT block (flow_key, step_key,
from_role, to_role, governance_file) with the reusable policy. Optional
`{{var}}` templating may come later — prefer simple deterministic injection,
no templating engine.

## 5. Governance Resolution Precedence

`step.governance_file ?? role.governance_file ?? legacy_default`.
`bridge_roles.governance_file` is NOT removed — it becomes the role-level
default. Old flows keep working; new/migrated flows use step-level reuse.

## 6. Role Is the Default — Step Is the Override

Role: default_governance_file / default_model_source / default_model_alias /
default_harness_source. Step may override any; unoverridden values fall
through.

## 7. One Unified Precedence Rule

STEP → ROLE DEFAULT → SYSTEM/LEGACY DEFAULT — identically for
effective_governance, effective_model_source, effective_model_alias,
effective_harness_source, effective_harness_profile. One shared resolution
concept — never per-dimension variants.

## 8. Separate Model Source From Harness Source

Model = which inference backend. Harness = which coding/agent frontend.
Never one field. `default_model_source = harness` is legacy to migrate away
from. Do NOT add more semantics to model_source.

## 9. Harness Source Schema

Role: default_harness_source, default_harness_profile. Step: harness_source,
harness_profile. Naming may fit conventions; semantic separation is
mandatory. `allocator_client` performs part of this today — decide a clean
evolution/migration; no two competing long-term concepts. DPMtF continues to
work without Harness Allocator.

## 10. Governance Files Must Become Role-Name Agnostic

No hardcoded runtime identities ("You are Pre-imple-cl", "Send to
review01", flow names) unless genuinely part of governance semantics. Prefer
"You are the Implementor for the currently active DPMtF Step" + runtime
context. Bridge commands derive runtime values from the Step.

## 11. Do Not Over-Generalize Governance

Separate files where behavior genuinely differs (SUPERVISOR, ARCHITECT,
IMPLEMENTOR, TECHNICAL_REVIEW, GOVERNANCE_REVIEW, LIGHTWORKER,
REVERSE_ENGINEERING, TRADE_*). NOT justified merely by changed model,
harness, flow name, tmux session, role_key, or local-vs-cloud.

## 12. Governance Composition

Keep the modular concept: reusable role governance references shared policies
(12_CODING_STANDARD, 13_VALIDATION, 15_GIT_POLICY, 16_FILE_ACCESS, 20_GATES,
30_FRONTEND_GOVERNANCE, 100_BRIDGE, 101_CODE_FRONTENDS, 102_DETERMINISTIC_
PATCH_MODE). Effective governance = runtime context + behavioral-role file +
referenced common modules. No flattened per-combination files.

## 13-14. Examples

strict_review/preferred_cloud/preferred_cloud_harness Implementors (imple01 /
Pre-imple-cl / imple-codex-minimaxM3; different models and harnesses) can all
reference one IMPLEMENTOR governance. Step-key example (harness flow): each
step carries governance_file + model_source/alias + harness_source describing
its from_role.

## 15. Important Step Semantics

Step configuration describes **from_role** (the actor executing the step
before handing to to_role) — explicit, and covered by tests.

## 16. Branching Flows

The same role may be overridden per step (model_alias / harness_source /
governance_file) without a new Role record — Step is the strongest level.

## 17. Effective Execution Configuration

One deterministic resolver, e.g. `resolve_execution_config(flow_key,
step_key)`, returning flow/step/from/to + governance_file+source_level +
model_source/alias+source_level + harness_source/profile+source_level +
implementation_mode. Used by dispatch, startup, WebUI, validation,
diagnostics, future Harness Allocator integration. Precedence logic lives in
ONE place.

## 18. Explainability

Resolved configuration must be visible (diagnostic/API/UI): each dimension
with its value and source level (step / role default / system). The operator
never infers why a governance/model/harness was selected.

## 19. Migration Strategy

Phase 1 — schema + resolver (additive, no behavior change).
Phase 2 — runtime context injection; governance files stop needing concrete
identity.
Phase 3 — governance deduplication: group 400/500-series by behavior, strip
identities, create/reuse generic files, repoint Step Keys, keep specialized
files only where behavior differs; delete nothing until references migrated
and validated.
Phase 4 — model/harness cleanup: separate backend from frontend; migrate
`model_source = harness` legacy; preserve compatibility.
Phase 5 — remove obsolete files only after: no DB references, resolver tests
green, affected flows pass integration tests, runtime context verified.

## 20. Backward Compatibility

NULL step fields fall back to role fields, dimension by dimension. One flow
migrates at a time. No flag-day.

## 21. Validation Rules

Governance: referenced file exists; unlimited steps may share one file;
from_role never inferred from filename; NULL falls back to role. Model: step
wins; role default when NULL; alias valid for source. Harness: step wins;
role default; harness never alters model selection and vice versa. Step
identity: configuration applies to from_role, not to_role.

## 22. Required Tests

Step-over-role for governance/model/harness; role fallbacks; shared
governance across multiple steps; from_role injection; to_role not the
actor; model/harness independence; legacy role-only flow unchanged;
preferred_cloud unchanged after migration; preferred_cloud_harness uses
shared governance without harness-specific duplication. Integration test: two
or more concrete roles using the same governance file.

## 23. Non-Goals

No BridgeV002 redesign; keep bridge_roles; Harness Allocator stays optional;
model lifecycle stays in Model Allocator; no generic policy engine; no
governance inheritance trees; no dynamic governance generation; no complex
templating framework; no duplicated resolvers; no forced simultaneous
migration. Small and deterministic.

## 24. Desired Architectural Result

FLOW → STEP KEY → {Governance, Model, Harness} overrides → ROLE DEFAULTS →
runtime execution. Role = identity + defaults; Step = concrete execution
context; governance = reusable policy; model and harness independent.

## 25. Core Design Rule

> Do not create a new governance file merely because a new Role, Flow, Model,
> or Harness has been created — only when the behavioral governance itself is
> different.

> Step configuration overrides Role defaults, consistently for Governance,
> Model, and Harness.
