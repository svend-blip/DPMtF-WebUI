# 31 — README STANDARD

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines the repository-level README contract for projects created, extended,
or maintained through DPMtF. The objective is NOT identical README content
across repositories — a model allocator and a genealogy application should not
read alike. The objective is a predictable structure for the subjects every
repository shares: what it is, what it needs, how it is installed (by a human
and by an agent), how installation is proven, how it is configured, run,
tested, and operated, and where its security boundary lies.

Three mechanisms carry this contract together:

1. this governance — defines what a compliant README means;
2. the deterministic validator (`scripts/validate_readme.py`) — mechanically
   enforces the parts that need no interpretation;
3. the README Impact block — makes every applicable Run keep README.md
   synchronized instead of letting drift accumulate.

The DPMtF principle applies: **deterministic mechanisms enforce deterministic
rules; agents handle interpretation and project-specific reasoning.** A
Reviewer MUST NOT override a deterministic validator failure by judging the
README "acceptable" — the README is corrected, or this governance is
explicitly changed.

## When to Use

- **Implementor:** On any Run with README impact (see triggers below), update
  README.md in the SAME Run, run the validator, and include its output in the
  result. Never postpone documentation sync to an unspecified future Run.
- **Review:** Verify the README Impact declaration is truthful, verify changed
  behavior is reflected in README.md, and treat validator errors as blocking.
  The validator proves structure; the Reviewer proves the prose is TRUE
  (`## Running` existing is mechanical; whether the documented command still
  works is review).
- **Decomposer / Architect:** Carry the README Impact requirement into
  handoffs for Runs that touch any trigger surface.
- **Any role:** When creating a repository or a README.md, start from the
  canonical skeleton below.

This governance applies whenever a Run creates a repository or README, or
materially changes: dependencies, installation, configuration, environment
variables, ports or services, startup/shutdown commands, public CLI or API,
runtime lifecycle, database initialization, test procedures, security
boundaries, remote access, operator workflow, or externally meaningful
architecture.

README.md is **current-state operational documentation**. It describes what
the repository does after the Run. It is not an implementation diary; long
phase histories belong in `CHANGELOG.md` or `docs/HISTORY.md`.

---

## Core Principle

**Standardize the README skeleton, not project-specific content.**

Repositories MAY contain arbitrary project-specific sections. Mandatory
repository-level subjects MUST use the canonical headings — do not invent a
different heading for the same repository concept:

| Use | Not (as the repository-level section) |
|---|---|
| `## Requirements` | `## Prerequisites`, `## Dependencies`, `## Host Requirements` |
| `## Installation` | `## Setup` |
| `## Running` | runtime instructions scattered across unrelated headings |
| `## Testing` | `## Tests`, `## Running the Test Suite` alone |
| `## Configuration` | configuration mixed into Installation |

Subsections MAY use more specific project-specific names.

---

## Canonical Skeleton

```text
# <Project Name>

<short summary: what it is, what problem it addresses, its place in DPMtF>

## Overview

## Architecture

## Requirements

## Installation
### Install manually
### Install using an Agent
### Verify installation

## Configuration

## Running

## Testing

## Operations                 [conditional: persistent operational component]

## Security                   [conditional: meaningful security boundary]

## Project Structure          [conditional: recommended for non-trivial repos]

<project-specific sections>

## Known Limitations          [conditional]

## Status                     [conditional]
```

**The operational core ordering MUST NOT be reordered:**

```text
Requirements → Installation → Configuration → Running → Testing
```

Rules that hold across the skeleton:

- Exactly one H1, first, containing the project name, followed by the short
  summary — before any inventories or histories.
- Mandatory headings MUST NOT be duplicated.
- `## Quick Start` is allowed as a convenience but MUST NOT replace the
  canonical core; it may point into it.
- Do not force irrelevant conditional sections to exist with filler.
- A repository that is not yet installable still carries `## Installation`,
  stating explicitly that installation is not currently supported.
- Machine-specific paths (`/home/<user>/...`) appear only when clearly marked
  as examples; never as the universal location. Secrets NEVER appear —
  reference environment variable NAMES (`ANTHROPIC_API_KEY`), not values.
- `## Security` describes the IMPLEMENTED security model, never an
  aspirational one. If authentication is intentionally absent, or the
  effective boundary is loopback/Tailscale, say exactly that.
- Tests requiring paid APIs, external accounts, GPU hardware, network access,
  or mutable production state are clearly separated from the deterministic
  suite under `## Testing`. Avoid manually maintained volatile test counts.

---

## Install Using an Agent — Mandatory Contract

`### Install using an Agent` exists so a user can hand the repository to a
coding or terminal agent and ask it to install the project on the current
machine. The section MUST be harness-neutral: it names no specific frontend
(Claude Code, Codex CLI, OpenCode, Pi, …) unless that harness is genuinely a
project dependency.

The generic contract (projects MAY append specifics; additions MUST NOT
weaken the safety rules):

```text
Give your coding agent access to this repository and ask it to install the
project on the current machine.

The agent MUST:

1. Read README.md and relevant installation, dependency, configuration, and
   deployment files before making machine changes.
2. Inspect the current machine before installing anything.
3. Reuse compatible existing dependencies, runtimes, environments, services,
   and configuration when practical.
4. Follow the documented manual installation procedure unless repository
   evidence shows another documented project-supported path is required.
5. Never invent credentials, tokens, API keys, model paths, hostnames,
   addresses, or other machine-specific values.
6. Never place secrets in tracked repository files.
7. Preserve a working existing installation and avoid destructive changes.
8. Prefer project-local and reversible changes.
9. Ask the human only when a required secret, authorization, or genuinely
   machine-specific value cannot be safely derived from the repository or
   the current machine.
10. Execute the documented installation verification after installation.
11. Report: what was installed; what was changed; what existing components
    were reused; which human-supplied values are still required; which
    verification commands were executed; and the result of each.
```

**The section must remain executable, not decorative.** The repository SHOULD
carry the machine-neutral artifacts the procedure needs (`.env.example`,
`config.example.yaml`, `requirements.txt`/`pyproject.toml`, `deploy/*.service`,
`scripts/preflight.sh`, …). A command the README tells the agent to run MUST
exist. A verification dependency that cannot be auto-configured MUST be named.

`### Verify installation` MUST give an objective proof of the installed
surface — `<command> --help`, a `status`/`preflight` command, a health
endpoint, a minimal pytest target, `systemctl --user is-active <service>`. A
successful `pip install` alone is usually insufficient. Where a deterministic
preflight exists, it is the canonical proof.

---

## README Impact — Mandatory Output

Every implementation Run's result MUST include exactly ONE of the following
blocks (mirroring the Frontend Impact mechanism in `30_FRONTEND_GOVERNANCE.md`):

### README impact

```markdown
## README Impact

- README impact: yes
- Affected sections: <canonical headings touched>
- Reason: <which trigger surface changed and how>
- Validator: <verbatim summary line or JSON from scripts/validate_readme.py>
```

### No README impact

```markdown
## README Impact

No README impact.

Reason: <why no trigger surface is affected>
```

**Presumed-impact triggers** — a Run touching any of these declares impact
`yes`, or defends `no` explicitly: dependencies; requirements; installation;
configuration; environment variables; ports; service units; startup/shutdown
commands; health checks; public CLI; public API; external integrations;
filesystem locations; runtime lifecycle; database initialization; test
commands; security boundaries; authentication; remote access; operator
workflow; architectural responsibility visible to users or operators.

Implementor duties on impact `yes`: inspect README.md; update the affected
canonical sections in the same Run; preserve unrelated correct content; keep
`### Install using an Agent` correct; ensure referenced commands and files
still exist; run the validator; include its evidence.

Reviewer duties: check the declaration's truthfulness both ways (an incorrect
`no` is a rejection); verify semantic accuracy of what changed; never approve
past a validator error.

---

## Deterministic Validator

```bash
python3 scripts/validate_readme.py <path-to>/README.md          # human output
python3 scripts/validate_readme.py --json <path-to>/README.md   # machine output
```

Central implementation, stdlib-only, no DPMtF imports — callable unchanged by
LightWorkers and against foreign repositories. Exit 0 = pass (warnings
allowed), exit 1 = fail, exit 2 = usage/IO error. Stable error codes; gates
and tests assert codes, not messages.

**Errors (blocking):** missing/duplicated H1; missing `## Requirements`,
`## Installation`, `## Configuration`, `## Running`, `## Testing`; missing
`### Install manually` / `### Install using an Agent` /
`### Verify installation`; core ordering violated; duplicated mandatory
heading; secret-like material.

**Warnings (advisory, review decides):** missing `## Overview` /
`## Architecture`; legacy alias headings where the canonical is absent;
personal absolute paths (`/home/<user>/...`).

Headings inside fenced code blocks are ignored. Environment-variable NAMES
are never flagged as secrets; literal values are.

---

## README AUTO-FAIL (review)

- `## Installation`, `### Install using an Agent`, or
  `### Verify installation` missing.
- `## Testing` missing from an active code repository.
- README references files or commands that do not exist.
- Secrets embedded in README.
- Mandatory headings duplicated, or core ordering violated.
- A Run materially changes user/operator behavior and README is not updated.
- A deterministic validator error waved through by reviewer opinion.

Initially reviewer-warnings, not auto-fail: excessive implementation history;
oversized file inventories; duplicated Quick Start content; excessive
machine-specific examples; blurred Configuration/Installation separation;
debatable absence of Operations/Security.

---

## Migration of Existing Repositories

Migration reorganizes; it does not rewrite. Never replace a README with a bare
template at the cost of valid architecture, integration, operational, or test
documentation.

Per repository: (1) inventory existing headings and map them to canonical ones
(`Setup → Installation`, `Running the Test Suite → Testing`, …); (2) add
missing core sections; (3) add `### Install using an Agent` starting from the
generic contract; (4) add `### Verify installation` with an objective proof;
(5) move existing material under the canonical headings without unnecessary
rewriting; (6) move long histories to `CHANGELOG.md`/`docs/HISTORY.md`;
(7) run the validator and resolve errors.

Migration may be incremental across Runs. Once a repository is migrated,
every subsequent Run MUST preserve compliance — the README Impact block is
what prevents re-drift.

---

## Placement and Genericity

This governance hardcodes no repository names, flow keys, role keys, model
aliases, harness profiles, usernames, or local paths. It is cross-cutting
governance, not a role: it augments Implementor, Review, and (where relevant)
Supervisor via the normal governance resolution, and changes nothing about
model selection, harness selection, implementation mode, step ownership, or
flow topology.

An MCP tool surface for README validation is deliberately deferred: direct
deterministic execution of `scripts/validate_readme.py` is sufficient, and a
tool wrapper can be added later without changing this contract.
