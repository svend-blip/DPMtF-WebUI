# CLAUDE.md — DPMtF-WebUI

> **Principle-based reference for Claude Code.**
> Authoritative governance: `docs/governance-templates-v2/` — this file summarizes;
> governance files rule in case of conflict.
> Script, endpoint, role, and flow details are handled by BridgeV002 and mcp-light.

## 1. Project Identity

DPMtF-WebUI is the **Father project** in the DPMtF ecosystem — it owns the
authoritative governance templates and serves as the Prompt Compiler for all
projects (including itself).

| Field | Value |
|------|-------|
| **Port** | 9130 |
| **Database** | `databases/dpmtf.db` (SQLite) |
| **Runtime** | `uvicorn app:app --host 0.0.0.0 --port 9130 --reload` |

## 2. Language Policy

- **en-US is mandatory** for all code, comments, docstrings, commit messages,
  and inter-role bridge communication.
- **Human may use Danish** — but prompts forwarded to other roles MUST be
  translated to English.

## 3. Config System (Mandatory)

`config.py` is the **single source of truth** for all configurable values.
Hardcoded `/home/svend/...` paths are an **auto-fail** in validation.

- Always use `config.get_*()` methods — never hardcode paths, ports, or model names.
- `.env` holds secrets and infrastructure variables (never committed).
- `dpmtf.ini` holds app-config defaults (committed).

## 4. Coding Standards

Full rules: `docs/governance-templates-v2/12_CODING_STANDARD.md`

### Python
- `python3 -m py_compile <file>` MUST pass before signaling completion.
- **Parameterized SQL only** — `?` placeholders, never f-strings/concatenation in SQL.
- **No hardcoded paths** — use `config.py` getters.
- PEP 8, f-strings preferred, type hints where practical.

### JavaScript
- **NO `innerHTML` for dynamic content** — auto-fail.
  Use `createElement()` / `textContent` / `appendChild()` / `replaceChildren()`.
- **ALL user-facing text MUST use `lbl(key, fallback)`** — no hardcoded English strings.
- `const` by default, `let` only when reassignment needed. Never `var`.
- Event delegation on container elements, not individual listeners.

### CSS
- Class-based selectors (not ID selectors for styling).
- No inline `style=""` attributes for layout.
- Dark theme (GitHub-dark palette). No light-theme colors.

### Shell
- `bash -n <file>` MUST pass before signaling completion.
- Every script MUST start with `set -euo pipefail`.

### Auto-Fail Patterns
1. `innerHTML` for dynamic content
2. Hardcoded English strings in frontend — use `lbl()`
3. Hardcoded `/home/svend/...` paths — use `config.py`
4. Guesswork on ports, paths, model names — MUST be explicit
5. Silent failures — catch blocks MUST log or report errors
6. New dependencies without Human approval
7. More than 2 failed patching attempts — stop, document, escalate

## 5. Git Policy

Full rules: `docs/governance-templates-v2/15_GIT_POLICY.md`

- **Only the Human may commit or push.** All changes remain unstaged until
  Human approval.
- Commit messages in English, format: `[phase] description`.
- One logical change per commit. Stage selectively (`git add <files>`), not `git add -A`.
- Never commit: `__pycache__/`, `.env`, secrets, generated artifacts.
- Never amend published commits or force-push to `master`.

## 6. Validation Checklist

Before considering any change complete, run these 8 checks:

| # | Check | Command |
|---|-------|---------|
| 1 | Backend syntax | `python3 -m py_compile app.py` |
| 2 | Frontend syntax | `node --check static/js/*.js` |
| 3 | Shell syntax | `bash -n <file>` (if shell scripts changed) |
| 4 | Diff scope | `git diff --stat` — only expected files changed |
| 5 | Dependencies | `git diff requirements.txt` — no new deps without approval |
| 6 | Schema changes | Review diff for `ALTER TABLE` / `CREATE TABLE` |
| 7 | innerHTML | `grep -RIn "innerHTML" static/ templates/` — must be empty |
| 8 | i18n | Verify all user-facing text uses `lbl()` — no hardcoded English |

### Additional Checks
- `grep -n '"/home/svend' app.py scripts/` — must return NO results.
- `python3 scripts/init_db.py` — must run without errors (idempotent).
- `curl -s http://localhost:9130/api/health` — must return `{"status": "healthy"}`.

## 7. Governance Precedence

Governance files in `docs/governance-templates-v2/` are authoritative.
CLAUDE.md summarizes; in case of conflict, the governance file rules.

Flow-specific 400-series files take precedence over general 01-04 files
for that role when operating within a BridgeV002 flow.

Active flows: `strict_review` (40x), `cloud_llm` (41x), `cloud_pay` (42x),
`trade_cockpit_*` (43x-44x), `supervised_review` (45x), `llama_SG` (46x),
`supervisor` (50x).

## 8. BridgeV002 — Principles

BridgeV002 is the **database-driven dispatch system**. It replaces `claude-bridge/` entirely.

### Core Principles
1. **Fully database-driven** — zero INI dependencies, zero hardcoded paths
2. **No-kill mode** — post-dispatch `ollama stop`, no tmux kill/new-session
3. **Convention-driven** — content templates govern injected prompts per step type
4. **Human skip** — `role_type=human` → dispatch skips tmux injection

### Signals
```bash
python3 scripts/bridgeV002/dispatch.py --db-flow {flow} --signal-send --from-role {from} --to-role {to}
python3 scripts/bridgeV002/dispatch.py --db-flow {flow} --signal-complete --from-role {from}
python3 scripts/bridgeV002/dispatch.py --db-flow {flow} --signal-escalation --from-role {from} --to-role {to}
python3 scripts/bridgeV002/dispatch.py --db-flow {flow} --signal-answer --from-role {from} --to-role {to}
```

See `docs/governance-templates-v2/100_BRIDGE.md` for the full protocol.

## 9. i18n — 4-Layer Architecture

```
ui_text_slots → ui_text_slot_labels → ui_labels → ui_label_translations
```

- API MUST traverse all 4 layers and return `{slot_key: text}`.
- Frontend uses `data-slot` attributes and `lbl(slot_key, fallback)`.
- Each label MUST have seed data in both `da-DK` and `en-US` locales.

## 10. File Access

Full rules: `docs/governance-templates-v2/16_FILE_ACCESS.md`

- **Free write:** `templates/`, `static/`, `docs/`
- **Human approval required:** `app.py`, `config.py`, `scripts/init_db.py`, `dpmtf.ini`, governance role definition files
- **Forbidden:** `.git/`, `__pycache__/`, `.env`, secrets, other projects' directories
- **Append-only:** `25_DECISIONS.md`, `26_CHANGELOG.md`

## 11. Supervising An Autonomous Flow

Rules for whoever watches a BridgeV002 run from outside it — not for the roles
inside. Every one was paid for.

### Do not touch the working tree while a run is active

Not commits, not edits, not new files outside the run's scope fence. The
evidence gate compares the **working tree**, not git history, so an
uncommitted edit is attributed to the role. On 2026-08-05 an edit to
`.claude/skills/LLAMASG/SKILL.md` had the gate reject handoff 011 and blame
the implementer, which had done its work correctly the whole time.

Committing does not help — it removes the file from `git status`, which is a
*different* mismatch against a contract that described the tree as it was.

`databases/dpmtf.db` is the standing exception: the flow writes to it on every
dispatch. Say so in GOAL.md or a supervisor will spend twenty minutes proving
it harmless, as one did.

**If something genuinely blocks the chain**, fix it, commit immediately so the
tree is clean, and append a RUN-LEDGER entry. The ledger is the only durable
channel into a stateless supervisor.

### Arm the watchers before the run, and cover run closure

A monitor that writes to a file is not a monitor. Background tasks notify on
**exit**, so a poll loop with a four-hour budget says nothing for four hours,
however faithfully it records events.

Arm three things at the start of every run:

1. **Chain progress** — the trace-log signals, so each dispatch and callback
   is visible.
2. **Run closure** — a watcher that exits when `END-REPORT.md` appears in the
   active run directory. **The supervisor's closing turn produces no signal
   and no gate event**: it writes a file and stops. On 2026-08-06 run 001
   closed and nothing told me; the Human did. Everything else was watched.
3. **The opposite of closure** — the supervisor idle for a long stretch with
   no END-REPORT. That is the state that actually needs a person, and it is
   the one most easily mistaken for progress.

Re-arm after each fires. A watcher that has completed is not watching, and the
gap after a verdict lands is exactly where a run finishes.

### Intervene on blockage, never on slowness

A role thinking for thirty minutes is not a blockage. These are:

- a verdict written but undeliverable
- a signal the role reported sent that never landed
- a model that cannot start
- a permission dialog nobody will answer

Everything else runs. A guard that acts on the wrong signal is worse than no
guard: one written here stopped a working implementer's model four seconds
after its handoff was dispatched, on the theory that a blocked supervisor
meant a failed swap. It meant the ordinary state after every dispatch.

### Stop and ask

- a scope-fence breach
- a gate rejection that repeats on the same handoff
- a decision the specification left open — never guess one into code
- two consecutive failed nudges
- tokens burning with no forward motion, which on a cloud flow is money

### Measure intermediate states as intermediate

A dispatch lands in five steps: the file is written, the counter advances, the
model swaps, the prompt is injected, `trace.log` records it. **Only the last
means delivered.** Reporting from any earlier one produced three wrong
statements in a single run.

Two traps underneath that:

- **Trace log is UTC; file mtimes are local.** Convert before comparing, or a
  two-hour offset invents a causal link that is not there. It did.
- **Compare fields, not substrings.** `signal_complete_failed` contains
  `signal_complete`; `" 009 "` matches a 2026-06-14 entry from a bridge era
  that no longer exists; `"review01SG" in "imple01SG->review01SG"` charges a
  rejection to the wrong role. Three instances of one bug in one day. Split
  the line and compare the field.

### A criterion is code, and deserves the same suspicion

A green testgoal proves the criterion passed, not that the work is right.
Three in one week measured the wrong thing while the work was sound:

- `pytest -q | tail -1` looking for `passed` — with everything green the last
  line is the progress dots. Measure the exit code.
- "the cron examples no longer name a literal path" — satisfied by
  `$PROJECT_ROOT/scripts/…`, which is undefined inside a crontab.
- counting occurrences of a word to decide whether prose says something.
  **A count cannot read.** Where the question is what the text means, the
  contract must hand that to the reviewer explicitly.

Write the criterion so it cannot pass on an empty repository, and check it
red before the run starts.

**But red before the run proves only that it is not trivially green.** On
2026-08-06 a criterion feeding a config loader a `paths:`-only fixture was
measured red before the run, as this rule requires — red with
`ModuleNotFoundError`, because the module did not exist yet. The import error
masked the real defect: the loader validates the whole config structure and
rightly rejects a fragment. It stayed red after correct work landed.

**An import error masks every other defect in a criterion that imports the
module it tests.** So when a fixture stubs a structure the code will validate,
check the criterion against a *complete* fixture as well — otherwise its red
tells you nothing about what it will measure once the module exists.

The run cost nothing that time, because the supervisor parked instead of
rejecting and the evidence was already in the ledger. The failure mode it
came close to is worse than a wasted handoff: an implementer "fixing" a red
criterion by loosening the validation that made it red, leaving weaker code
behind a green tick.
