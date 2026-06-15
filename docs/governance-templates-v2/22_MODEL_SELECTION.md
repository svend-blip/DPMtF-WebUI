# 22 — MODEL SELECTION

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines the decision tree for selecting which model should execute a given
task. Consolidates the legacy `superpowertemplates/localmodel.md` and
`superpowertemplates/superpowers.md` Section 3 (Model Selection Decision Tree).

## When to Use

- **Architect:** Select the appropriate model when generating prompts.
- **Review:** Verify model choice during validation.
- **Human:** Approve model selection via GATE-MODEL.

---

## Available Models

| Model | Type | Use Case |
|-------|------|----------|
| **deepseek-v4-pro:cloud** | Cloud (capable) | Complex tasks (tier ≥4), architecture, multi-file integration, design decisions. |
| **deepseek-v4-flash:cloud** | Cloud (cheaper) | Mechanical tasks, 1-2 files, trivial changes. |
| **qwen36-27b-q4km:latest** | Local (Ollama) | Offline mode, medium-high or lower complexity (≤5 files). 0 EUR cost. ~55s thinking overhead. 9/9 first-try success rate documented. |

## Model Selection Decision Tree

```
START: Task received
│
├─ Is the environment offline?
│   └─ USE: Local model (qwen36-27b-q4km). See [[19_OFFLINE_MODE]].
│
├─ Is the task mechanical/trivial?
│   Characteristics: 1-2 files, well-defined spec, no design decisions
│   └─ USE: deepseek-v4-flash:cloud (cheaper tokens)
│      → Trigger GATE-MODEL to confirm with Human
│
├─ Is the task complex? (complexity_tier ≥ 4)
│   Characteristics: multi-file integration, architecture/design,
│   debugging, schema changes
│   └─ USE: deepseek-v4-pro:cloud
│
├─ Is the task medium-high or lower? (complexity_tier ≤ 3)
│   Characteristics: ≤5 files, well-defined pattern, documentation,
│   mechanical migration
│   └─ USE: Local model (qwen36-27b-q4km)
│      Evidence (2O, 2026-06-14): 9/9 first-try across low (1 file),
│      medium (1-3 files), and medium-high (5 files) tasks.
│      Cost: 0 EUR vs ~0.02 EUR for cloud.
│
├─ Does a prompt template have better historical performance
│   with a specific model?
│   └─ USE: Model with highest rolling_success_rate for this template
│
└─ EVERY TIME a major topic changes:
   1. Ask: "Can a cheaper model handle this task?"
   2. If yes → suggest model switch to Human (GATE-MODEL)
   3. Update this decision tree if new models are added
```

## Role-to-Model Mapping

| Role | Default Model | Rationale |
|------|--------------|-----------|
| **Architect** | deepseek-v4-pro:cloud | Requires cross-project overview, architectural reasoning, design decisions. |
| **Implementor** | qwen36-27b-q4km (local) | Executes well-defined prompts. 0 EUR cost. Proven first-try success. |
| **Review** | deepseek-v4-flash:cloud | Validation is systematic — follows checklists. Cheaper tokens than pro. |

## Prompt Compiler Integration

When the DPMtF prompt compiler is used:

1. Query `/api/prompt-templates` with `complexity_tier` and `suitable_for` filters.
2. Check per-model hitrate via `/api/prompt-templates/{key}/hitrate`.
3. Select template with best historical performance for the task type.
4. Compile prompt via `POST /api/prompt-templates/{key}/compile`.
5. Execute against the selected model.
6. Register result via `POST /api/prompt-runs` with mandatory outcome fields.

## Adding New Models

When a new model is added:

1. Download via appropriate package manager (requires internet + Human approval).
2. Test with simple prompts.
3. Add to this file with model info.
4. Update prompt templates' `suitable_for` flags.
5. Document in [[26_CHANGELOG]].

---
