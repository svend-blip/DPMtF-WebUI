# Scope

## Purpose

This governance document defines what is included and excluded in the current phase or task. It acts as the boundary for the role-based prompt loop — all roles must operate within these limits unless scope is explicitly changed through the documented process.

## When to Use

- **Project initializer**: Fill in scope before starting a new phase.
- **Analyst step**: First file reviewed to understand boundaries.
- **Validator step**: Changes are checked against this document to detect scope violations.
- **After `/clear`**: Read to reconstruct what is and isn't allowed in the current session.

---

## Phase

**2O — Parallel-kørsel test (cloud vs lokal)**

## In Scope Now

- Design og implementering af sammenlignings-infrastruktur til parallel prompt-eksekvering.
- Kørsel af samme prompt på cloud-model (deepseek-v4-pro:cloud) og lokal model (qwen36-27b-q4km:latest).
- Sammenligning af: execution success, duration, token usage, cost, output quality.
- Brug af eksisterende infrastruktur: prompt_templates, prompt_runs, workflow_runs, template_model_hitrates.
- Frontend-visning af sammenlignings-resultater (tabel, farvekoder, diff-visning).
- Registrering af alle kørsler i prompt_runs med korrekte outcome-felter.
- Opdatering af template_model_hitrates for begge modeller.
- Produktion af baseline performance-data til model selection decision tree.

## Out of Scope Now

- Ændringer i ENO eller ai-pc-resource-webui-v3.
- Nye eksterne dependencies uden Human Approval Gate.
- Database schema-ændringer uden forudgående godkendelse.
- Ændringer i prompt_templates struktur (den er stabil efter 2H redesign).
- Automatisk model-routing baseret på test-resultater (det er en fremtidig fase).
- Performance-optimering af lokal model eller Ollama konfiguration.

## Key Principle

**Data-drevet model selection.** 2O etablerer det empiriske grundlag for model decision tree i superpowers.md. I stedet for at gætte hvilken model der er bedst til en given opgavetype, producerer vi faktiske sammenlignings-data fra parallelle kørsler. Resultaterne føder direkte ind i template_model_hitrates og fremtidig automatisk model-routing.

## Constraints

- Do NOT modify ENO or ai-pc-resource-webui-v3.
- Do NOT modify prompt_templates struktur (tilføjelse af nye templates er OK).
- Do NOT introduce new dependencies without Human Approval Gate.
- Do NOT modify database schema without prior approval (nye tabeller via CREATE TABLE IF NOT EXISTS er OK).
- Do NOT restart Ollama service without human approval.
- Do NOT commit until explicitly instructed.
- All frontend text MUST use `lbl(key, fallback)` — no hardcoded English strings.
- No `innerHTML` for dynamic content — use `createElement()`/`textContent`/`appendChild()`.
- Python: `py_compile` before commit, PEP 8, parameterized SQL queries.
- Shell: `bash -n` before commit, `set -euo pipefail`.

## Success Criteria

- Mindst 3 parallel-kørsler gennemført (samme prompt, forskellige modeller).
- Alle kørsler registreret i prompt_runs med execution_status, first_try_success, validation_passed, template_key.
- template_model_hitrates opdateret for begge modeller (deepseek-v4-pro:cloud og qwen36-27b-q4km:latest).
- Frontend-visning der sammenligner: success, duration, tokens, cost, output quality per kørsel.
- Baseline-data der kan bruges til at informere model selection decision tree.
- Alle 8 pre-commit validation checks passerer.
- Governance-dokumentation opdateret (CHANGELOG, NEXT_CONTEXT, IMPLEMENTATION_REPORT).

## Scope Change Process

If scope must change during a session:

1. Document the proposed change and reason in `09_DECISIONS.md`.
2. Obtain Human Approval Gate sign-off if the change adds work or removes constraints.
3. Update this document with the new scope boundary.
4. Log the change date and decision reference in the Scope Change Log below.

## Scope Change Log

| Date | Change | Reason | Decision Reference |
|------|--------|--------|-------------------|
| 2026-06-11 | Initial scope for phase 3C-3 | Governance initialization phase | — |
| 2026-06-13 | Scope updated to phase 2O | 3C-3 was stale (v3 governance init). Actual project state: Blok 6 faser 2H-2N completed, 2O is next. | Governance update 2026-06-13 |

---
