# Roles

## Role Definitions

| Role | Responsibility | Who |
|------|---------------|-----|
| Analyst | Analyze requirements, scope, and constraints. | [Name] |
| Prompt Engineer | Generate prompts from governance files. | [Name / AI agent] |
| Implementer | Execute prompts and produce code changes. | [Name / AI agent] |
| Validator | Verify changes against coding standards and validation rules. | [Name / AI agent] |
| Human Approver | Final approval before commit when required. | [Name] |

## Role Handoff Rules
- Each role reads the governance files before acting.
- Analyst output feeds into prompt engineer input.
- Validator must pass before human approval is requested.
- `/clear` between roles to reset context windows.

## Local Agent Roles (ROLELOCAL)
When running locally with offline models, the same role pipeline applies but all execution happens on-machine:
- Use local LLM for each role step.
- Use local git for version control.
- No external API calls unless explicitly authorized per-run.
