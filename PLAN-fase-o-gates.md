# Fase Ø Release Gates (Ø-4 / Ø-5) + Portfolio Snapshot Handler Implementation Plan

> **For agentic workers:** Execute tasks in order. Steps use checkbox (`- [ ]`) syntax for tracking. Do not skip verification steps.

**Goal:** Close optimization-roadmap Fase Ø gates G5 (no hardcoded `/home/svend` paths in `app.py scripts/ config.py`) and G6 (no f-string SQL in `app.py`), and bring the untracked prototype `scripts/portfolio_snapshot_handler.py` up to project standard, wired as a documented flow step.

**Architecture:** The remaining G5 hits are (a) self-locating shell scripts with a hardcoded `PROJECT_ROOT`, (b) hardcoded binary/project paths in `import-flow-output.py`, (c) the prototype snapshot handler, plus (spirit-of-the-gate) a hardcoded dispatch path inside the `json_output` content template in `seed_bridge.py`/DB. Fixes use script-relative derivation (shell), `config.py` getters (Python), and the established `{SCRIPTS_DIR}` placeholder + `resolve_placeholders()` (template). G6 is verified already-empty for `app.py` (its former f-string sites died in the app split); the dynamic SET-clause f-strings in `routers/` are audited as whitelist-safe. The snapshot handler is rewritten and registered as `pre_dispatch_script` on the `trend01-market01` step — the same mechanism `import-flow-output` uses on `sim01-portfolio01`.

**Tech Stack:** Python 3.12, Bash, SQLite, pytest.

## Cold-Start Context

- Project: **DPMtF-WebUI** ("Father"), FastAPI app on port **9130**, SQLite DB at `databases/dpmtf.db` (committed to the repo).
- Start app: `uvicorn app:app --host 0.0.0.0 --port 9130 --reload` from `/home/svend/DPMtF-WebUI`.
- Run tests: `python3 -m pytest -q`. Fixtures: `tests/conftest.py`.
- Roadmap source: `docs/superpowers/plans/2026-07-04-optimization-roadmap.md` — gate table: `G5 = grep -n '"/home/svend' app.py scripts/ config.py` empty; `G6 = grep -nE "cursor\.execute\(f" app.py` empty.
- `config.py` getters relevant here: `get_project_root()`, `get_home_dir()` (env `DPMTF_HOME_DIR` or `os.path.expanduser("~")`), `get_opencode_bin()`, `get_trade_inbox_dir()`, `get_db_path()`. `config.py` already has an AST-based startup validator (`validate_no_hardcoded_paths`) and contains no literal `/home/svend`.
- BridgeV002: dispatch scripts are registered in the `bridge_scripts` table (columns: `script_key, name, description, path, stage, params_required, is_active, created_at, updated_at`); a step's `pre_dispatch_script` column references a `script_key`; `dispatch.py` executes it with the flow-context CLI produced by `step_to_cli_args` (`--flow-key --step-key --from-role --to-role --deliverable-dir --deliverable-pattern --deliverable-file --handoff-id --bridge-dir --prompt-template`). Precedent: `import-flow-output` is `pre_dispatch_script` on step `sim01-portfolio01`.
- Governance: `docs/governance-templates-v2/`. File-access note: `app.py`, `config.py`, `scripts/init_db.py`, `dpmtf.ini` require Human approval — this plan deliberately avoids touching all four.

## Global Constraints

- `python3 -m py_compile <file>` MUST pass on every touched `.py` file; `bash -n <file>` on every touched shell script; every shell script keeps `set -euo pipefail`.
- Parameterized SQL only (`?` placeholders). f-strings interpolating **validated identifier whitelists** (column names from a hardcoded list) are acceptable ONLY because SQLite cannot parameterize identifiers — values must still bind via `?`.
- No hardcoded `/home/svend/...` paths — use `config.py` getters, `Path.home()` / `os.path.expanduser("~")`, or script-relative derivation.
- Schema changes ONLY via new `scripts/db/00X_*.sql` + `python3 scripts/migrate.py`. **This plan changes NO schema** — only seed VALUES / data rows (`bridge_scripts`, `bridge_flow_steps.pre_dispatch_script`, `bridge_convention_rules.content_template`), which need no migration.
- `python3 scripts/init_db.py` must still run clean twice (idempotent) — verify even though this plan does not edit it.
- No new pip dependencies.
- Frontend rules (no `innerHTML`, `lbl()`, 4-layer i18n) — not applicable; no frontend files touched.
- `curl -s http://localhost:9130/api/health` returns `{"status":"healthy"}` after changes.
- Git: **Only the Human may commit.** Stage and STOP.

## Edge Cases a Weaker Model Would Miss

1. **The G5 gate greps the LITERAL `"/home/svend` (quote + path).** `config.py` assembles its self-check marker from fragments precisely so the validator does not flag itself. Fixes must not introduce the literal anywhere — including in comments inside Python strings. Bare `/home/svend` without a leading quote (comments, the seed template) does not trip the gate but violates the spirit; this plan fixes the template hit too and leaves crontab-example comments alone.
2. **Shell scripts run from cron with CWD=$HOME.** `PROJECT_ROOT` must be derived from the script's own location — `"$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"` — which works because crontab invokes them by absolute path. `$0`-based derivation also works here but `BASH_SOURCE` survives `source`-ing; use `BASH_SOURCE`.
3. **`trade-cronjob.sh` cd's to `PROJECT_ROOT` FIRST for a reason** (documented in the script): `config.get_db_path()` returns the relative `databases/dpmtf.db`, which must resolve against the project root. Keep the `cd` and its comment; only change how `PROJECT_ROOT` is computed.
4. **G6's original targets no longer exist.** The roadmap points at `app.py:1538/3491`, but `app.py` is now a 145-line shell (endpoints moved to `routers/`). The gate `grep -nE "cursor\.execute\(f" app.py` is ALREADY empty — the work is to prove it, then audit the six dynamic-UPDATE f-strings that MOVED to `routers/bridge.py` (lines 233, 437, 548, 598, 832) and `routers/sessions.py` (line 205). All six build SET clauses by iterating a hardcoded `updatable`/`updates` list of literal column names with `?` value binding — identifier whitelist, values parameterized. That is the correct SQLite pattern; converting them to pure `?` placeholders is IMPOSSIBLE (identifiers can't be bound) and rewriting them would churn approval-heavy code for zero security gain. Audit + document, do not rewrite.
5. **`init_db.py`'s "32 hardcoded paths" from the roadmap are already gone** — verified: `grep -n '/home/svend' scripts/init_db.py` returns nothing (the token `home_svend_disk` at line ~1807 is a UI slot KEY, not a path — leave it). Do not "fix" init_db.py; it requires Human approval and needs no change.
6. **The `json_output` content template is DATA (in `bridge_convention_rules`) as well as SOURCE (in `seed_bridge.py`).** Fixing only the seed leaves the live DB dirty; fixing only the DB regresses on next seed run. `seed_bridge.py` performs an unconditional parameterized UPDATE of this template at its end, so: fix the seed source, then run `python3 scripts/seed_bridge.py` to propagate. The template placeholder `{SCRIPTS_DIR}` must then be resolved at dispatch time — `bridge_lib.resolve_placeholders()` already supports `{BRIDGE_DIR}/{PROJECT_ROOT}/{SCRIPTS_DIR}` and is already imported by `dispatch.py`; it is just never applied to prompt text today.
7. **A `pre_dispatch_script` failure ABORTS the chain.** In `dispatch.py`'s `signal_complete`, a non-zero exit from the pre-script prints "Pre-dispatch script failed -- aborting" and returns False. The snapshot handler is observability, NOT a gate — it must `sys.exit(0)` even when it finds nothing to snapshot, logging the reason to stderr (loud, not silent — silent failure is an auto-fail, but so is stalling the trade chain over a missing snapshot).
8. **The prototype's filename glob never matched real files.** It looks for `trend01_trade_*.json`, but real trade outputs are `{ID}_trend01_trade.json` (e.g. `072_trend01_trade.json`), and it reads `DPMtF-WebUI/inbox/pending` while the real inbox is `config.get_trade_inbox_dir()` (→ `~/trade-ui/inbox/pending`). The rewrite matches both name shapes and reads `pending/` + `processed/` (imported files are MOVED to `processed/`).
9. **The cycle-state file the prototype touches is `scripts/docs/bridgeV002/current-cycle.json` — and that is, surprisingly, the CORRECT file.** `dispatch._update_cycle_state()` derives `project_root` as `Path(__file__).resolve().parent.parent` (= `scripts/`) when `DPMTF_PROJECT_ROOT` is unset, so the live, git-tracked cycle file lives under `scripts/docs/bridgeV002/`. The rewrite must reference the SAME file (via `config.get_project_root()` + the `scripts/docs/...` suffix) and document the quirk — "fixing" the path would silently fork the cycle state.
10. **`datetime.utcnow()` is deprecated and naive** — the project standard (used across `dispatch.py`, `migrate.py`) is `datetime.now(timezone.utc)`. The rewrite uses it.
11. **Cron timing rules out wiring the handler into `trade-cronjob.sh`:** the cronjob runs at 09:00 BEFORE `trend01_trade` produces anything — it would always snapshot yesterday's file. The `trend01-market01` step's `pre_dispatch_script` slot fires inside trend01's `signal_complete`, AFTER dispatch has verified the fresh `{ID}_trend01_trade.json` exists (deliverable check precedes the pre-script). That is why Task 6 chooses the DB wiring, exactly mirroring `import-flow-output`. The `sim01-portfolio01` slot is already occupied by `import-flow-output` (one `pre_dispatch_script` per step), which rules out that step.

---

### Task 1: Inventory — run both gates and reconcile with this table

- [ ] Step 1: Run `grep -rn '"/home/svend' app.py scripts/ config.py routers/ | grep -v __pycache__` and `grep -nE "cursor\.execute\(f" app.py`. Reconcile against this verified inventory (if NEW hits have appeared since this plan was written, categorize each as *script self-location* / *binary path* / *seed-template data* / *prototype* and extend the matching task):

| # | File:Line | Hit | Category | Fix (Task) |
|---|-----------|-----|----------|------------|
| 1 | `scripts/ollama-stop-all.sh:13` | `PROJECT_ROOT="/home/svend/DPMtF-WebUI"` | script self-location | Task 2 |
| 2 | `scripts/trade-cronjob.sh:14` | same | script self-location | Task 2 |
| 3 | `scripts/scoring-cronjob.sh:12` | same | script self-location | Task 2 |
| 4 | `scripts/bridgeV002/import-flow-output.py:69,76` | `"/home/svend/.local/bin/claude "` | binary path | Task 3 |
| 5 | `scripts/bridgeV002/import-flow-output.py:86,91` | `"/home/svend/.opencode/bin/opencode "` | binary path | Task 3 |
| 6 | `scripts/bridgeV002/import-flow-output.py:65,74,83,90` | `"cd /home/svend/DPMtF-WebUI && "` (gate-invisible: no leading `"/`) | project path (spirit) | Task 3 |
| 7 | `scripts/portfolio_snapshot_handler.py:15,40,48` | 3 absolute paths | prototype | Task 5 |
| 8 | `scripts/seed_bridge.py:376` | `timeout 60 python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py` inside `_JSON_OUTPUT_CONTENT_TEMPLATE` (gate-invisible; also live in DB `bridge_convention_rules.content_template`) | seed-template data | Task 4 |
| — | `app.py` (G6) | zero `cursor.execute(f` hits | already clean | Task 7 verifies |

- [ ] Step 2: Confirm the non-hits stay non-hits: `grep -n '/home/svend' scripts/init_db.py config.py app.py` → only `home_svend_disk` (slot key, init_db.py ~1807) may appear; it is not a path — leave it.

---

### Task 2: Shell scripts — derive `PROJECT_ROOT` from script location

**Files:** Modify `scripts/trade-cronjob.sh` (line 14), `scripts/scoring-cronjob.sh` (line 12), `scripts/ollama-stop-all.sh` (line 13).

- [ ] Step 1: In each of the three scripts, replace the line

```bash
PROJECT_ROOT="/home/svend/DPMtF-WebUI"
```

with

```bash
# Self-locating: crontab invokes this script by absolute path, so
# BASH_SOURCE is absolute and PROJECT_ROOT resolves without hardcoding.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
```

(All three scripts live directly in `scripts/`, so `..` is the repo root. Do NOT change the crontab-example comment lines near the top — they document the Human's crontab, are not code, and contain no leading-quote literal.)
- [ ] Step 2: `bash -n scripts/trade-cronjob.sh scripts/scoring-cronjob.sh scripts/ollama-stop-all.sh` — exit 0.
- [ ] Step 3: Functional check without side effects: `bash -c 'PROJECT_ROOT="$(cd "$(dirname scripts/trade-cronjob.sh)/.." && pwd)"; echo "$PROJECT_ROOT"' ` from the repo root — prints the repo root. Then confirm each script still echoes the correct root when sourced for the variable only: `bash -c 'source /dev/stdin <<< "$(sed -n "12,22p" scripts/trade-cronjob.sh)"; echo "$PROJECT_ROOT"'` is fragile — instead simply run `bash scripts/ollama-stop-all.sh` (harmless: stops loaded ollama models only if any are loaded) and check its log banner prints.

---

### Task 3: `import-flow-output.py` — config-derived binary and project paths

**Files:** Modify `scripts/bridgeV002/import-flow-output.py`.

- [ ] Step 1: After the existing imports (line ~26, after `import requests`), add:

```python
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _PROJECT_ROOT)

import config  # Father config — project root, home dir, opencode bin
```

- [ ] Step 2: Replace `_build_start_command` (lines 56–95) with:

```python
def _build_start_command(role):
    """Build the CLI start command for a role, mirroring start_coding.py.

    All paths come from config.py (Fase Ø-4): no hardcoded /home/<user>.
    """
    runtime = (role.get("default_runtime") or "").lower()
    model = role.get("default_model") or ""
    provider = (role.get("default_provider") or "").lower()

    project_root = config.get_project_root()
    claude_bin = os.path.join(config.get_home_dir(), ".local", "bin", "claude")
    opencode_bin = config.get_opencode_bin()

    if runtime == "claude":
        if provider == "local_ollama":
            return (
                f"cd {project_root} && "
                "CLAUDE_CODE_MAX_OUTPUT_TOKENS=262144 "
                "ANTHROPIC_BASE_URL=http://127.0.0.1:11434 "
                "ANTHROPIC_AUTH_TOKEN=ollama "
                f"{claude_bin} "
                f"--model {model}"
            )
        else:
            return (
                f"cd {project_root} && "
                "CLAUDE_CODE_MAX_OUTPUT_TOKENS=262144 "
                f"{claude_bin} "
                f"--model {model}"
            )
    elif runtime == "opencode":
        config_dir = role.get("config_dir") or ""
        if config_dir:
            return (
                f"cd {project_root} && "
                f'OPENCODE_CONFIG_DIR="{config_dir}" '
                f'OPENCODE_CONFIG="{config_dir}/opencode.json" '
                f"{opencode_bin} "
                f"--model {model}"
            )
        return (
            f"cd {project_root} && "
            f"{opencode_bin} "
            f"--model {model}"
        )

    return None  # unknown runtime — skip
```

(`config.get_opencode_bin()` already defaults to `<home>/.opencode/bin/opencode`; `config.get_home_dir()` honors `DPMTF_HOME_DIR` and falls back to `os.path.expanduser("~")` — same binaries as before on this machine, zero literals.)
- [ ] Step 3: `python3 -m py_compile scripts/bridgeV002/import-flow-output.py` — exit 0.
- [ ] Step 4: Command-equivalence proof on this machine:
  `python3 -c "import sys; sys.path.insert(0,'scripts/bridgeV002'); imp=__import__('importlib.util',fromlist=['util']); import importlib.util as u; s=u.spec_from_file_location('ifo','scripts/bridgeV002/import-flow-output.py'); m=u.module_from_spec(s); s.loader.exec_module(m); print(m._build_start_command({'default_runtime':'claude','default_provider':'local_ollama','default_model':'qwen3-coder:30b-96k'}))"`
  Expected output: the same command string as before the change, with `/home/svend/...` now produced by config at RUNTIME (fine) instead of hardcoded in SOURCE (the gate greps source, not output).

---

### Task 4: `json_output` template — `{SCRIPTS_DIR}` placeholder + dispatch-side resolution

**Files:** Modify `scripts/seed_bridge.py` (template string, line ~376) and `scripts/bridgeV002/dispatch.py` (three prompt-composition sites). Data: re-run `python3 scripts/seed_bridge.py`.

- [ ] Step 1: In `scripts/seed_bridge.py`, inside `_JSON_OUTPUT_CONTENT_TEMPLATE`'s `<chain_advancement>` block, replace:

```
    timeout 60 python3 /home/svend/DPMtF-WebUI/scripts/bridgeV002/dispatch.py \
```

with:

```
    timeout 60 python3 {SCRIPTS_DIR}/dispatch.py \
```

- [ ] Step 2: In `scripts/bridgeV002/dispatch.py`, make dispatch resolve the placeholder set `{BRIDGE_DIR}/{PROJECT_ROOT}/{SCRIPTS_DIR}` in every composed prompt (`resolve_placeholders` is already imported from `bridge_lib` at the top of dispatch.py). Add the SAME line at three sites, each immediately after the last `.replace(...)` chain and before any `prompt_text +=` append:
  - in `signal_complete`, after `prompt_text = prompt_text.replace("{previous_deliverable_path}", full_deliverable_path)` (the ctemplate branch, ~line 1345):
  - in `signal_send`, after `prompt_text = prompt_text.replace("{previous_deliverable_path}", handoff_abs)` (~line 1970):
  - in `run_flow_step_db`, after each of the two `.replace("{previous_deliverable_path}", full_deliverable_path)` lines (~1021 and ~1032):

```python
        prompt_text = resolve_placeholders(prompt_text, bridge_dir=bridge_dir)
```

(Idempotent for templates without placeholders — plain string passthrough.)
- [ ] Step 3: `python3 -m py_compile scripts/seed_bridge.py scripts/bridgeV002/dispatch.py` — exit 0.
- [ ] Step 4: Propagate to the live DB: `python3 scripts/seed_bridge.py` (its final statement is a parameterized `UPDATE bridge_convention_rules SET content_template = ? ... WHERE rule_key = 'json_output'`).
- [ ] Step 5: Verify the data:
  `sqlite3 databases/dpmtf.db "SELECT content_template LIKE '%{SCRIPTS_DIR}/dispatch.py%', content_template LIKE '%/home/svend%' FROM bridge_convention_rules WHERE rule_key='json_output';"` — expected: `1|0`.

---

### Task 5: Rewrite `scripts/portfolio_snapshot_handler.py` to standard (TDD)

**Files:**
- Create: `/home/svend/DPMtF-WebUI/tests/test_portfolio_snapshot_handler.py`
- Rewrite (file is currently untracked prototype): `/home/svend/DPMtF-WebUI/scripts/portfolio_snapshot_handler.py`

- [ ] Step 1 (failing tests first): create `tests/test_portfolio_snapshot_handler.py`:

```python
"""Unit tests for the portfolio snapshot handler (rewritten to standard)."""

import json
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))

import portfolio_snapshot_handler as psh  # noqa: E402


@pytest.fixture()
def inbox(tmp_path, monkeypatch):
    base = tmp_path / "inbox"
    for sub in ("pending", "processed", "rejected"):
        (base / sub).mkdir(parents=True)
    monkeypatch.setattr(psh.config, "get_trade_inbox_dir",
                        lambda: str(base / "pending"))
    return base


def _trend(dir_path, name, run="072"):
    p = dir_path / name
    p.write_text(json.dumps({"flow_run_id": run, "status": "completed",
                             "payload": {}}), encoding="utf-8")
    return p


def test_find_newest_id_convention_name(inbox):
    _trend(inbox / "pending", "071_trend01_trade.json")
    newest = _trend(inbox / "processed", "072_trend01_trade.json")
    time.sleep(0.01)
    import os
    os.utime(newest, None)  # ensure newest mtime
    assert psh.find_trend_snapshot() == str(newest)


def test_find_legacy_prototype_name(inbox):
    p = _trend(inbox / "pending", "trend01_trade_20260629_cycle29.json")
    assert psh.find_trend_snapshot() == str(p)


def test_find_prefers_exact_deliverable(inbox):
    _trend(inbox / "pending", "071_trend01_trade.json")
    exact = _trend(inbox / "pending", "072_trend01_trade.json")
    got = psh.find_trend_snapshot(
        deliverable_dir=str(inbox / "pending"),
        deliverable_file="072_trend01_trade.json")
    assert got == str(exact)


def test_find_nothing_returns_none(inbox):
    assert psh.find_trend_snapshot() is None


def test_write_snapshot_and_cycle_update(inbox, tmp_path):
    src = _trend(inbox / "pending", "072_trend01_trade.json")
    out = tmp_path / "portfolio_snapshot.json"
    cycle = tmp_path / "current-cycle.json"
    cycle.write_text(json.dumps({"last_handoff": "072",
                                 "flow": "trade_cockpit_simulation_v001"}),
                     encoding="utf-8")

    psh.write_snapshot(str(src), str(out))
    psh.update_cycle_state(str(cycle))

    assert json.loads(out.read_text())["flow_run_id"] == "072"
    updated = json.loads(cycle.read_text())
    assert updated["portfolio_snapshot_processed"] is True
    assert updated["updated"].endswith("Z")
    assert updated["last_handoff"] == "072"  # untouched fields preserved


def test_update_cycle_state_missing_file_is_noncatastrophic(tmp_path):
    # Must not raise — the handler is observability, not a gate.
    psh.update_cycle_state(str(tmp_path / "missing.json"))


def test_main_exits_zero_when_nothing_found(inbox, tmp_path, monkeypatch,
                                            capsys):
    """A pre_dispatch_script failure would ABORT the trade chain in
    dispatch.py — the handler must exit 0 and log loudly instead."""
    monkeypatch.setattr(psh, "snapshot_output_path",
                        lambda: str(tmp_path / "snap.json"))
    monkeypatch.setattr(psh, "cycle_state_path",
                        lambda: str(tmp_path / "cycle.json"))
    rc = psh.main(["--handoff-id", "099", "--from-role", "trend01_trade"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "no trend01_trade output found" in err
```

- [ ] Step 2: Run `python3 -m pytest tests/test_portfolio_snapshot_handler.py -q` — expected failures/errors (functions do not exist yet).
- [ ] Step 3: Overwrite `scripts/portfolio_snapshot_handler.py` in full:

```python
#!/usr/bin/env python3
"""Portfolio Snapshot Handler for DPMtF-WebUI.

Copies the newest trend01_trade output JSON from the trade inbox into
databases/portfolio_snapshot.json and marks the cycle-state file with
portfolio_snapshot_processed=true (Architect cold-start observability).

Wiring: registered in bridge_scripts as 'portfolio-snapshot' and set as
pre_dispatch_script on the trend01-market01 step of
trade_cockpit_simulation_v001. dispatch.py invokes it during trend01's
signal-complete with the full flow-context CLI (step_to_cli_args), AFTER
verifying the fresh {ID}_trend01_trade.json deliverable exists — so
--deliverable-dir/--deliverable-file normally point at the exact file.

EXIT-CODE CONTRACT: always 0 unless the interpreter itself crashes.
A non-zero exit from a pre_dispatch_script ABORTS the chain in
dispatch.py; this handler is observability, not a gate. Problems are
reported loudly on stderr (never swallowed silently).
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

import config  # noqa: E402

# Real trade outputs are {ID}_trend01_trade.json (zero-padded run id);
# the original prototype expected trend01_trade_*.json — accept both.
_NAME_PATTERNS = (
    re.compile(r"^\d+_trend01_trade\.json$"),
    re.compile(r"^trend01_trade_.+\.json$"),
)


def snapshot_output_path():
    """Target path for the snapshot copy (project databases/ dir)."""
    return os.path.join(config.get_project_root(),
                        "databases", "portfolio_snapshot.json")


def cycle_state_path():
    """The LIVE cycle-state file.

    NOTE the scripts/docs/... prefix: dispatch._update_cycle_state()
    derives its project root as scripts/ (parent.parent of dispatch.py)
    when DPMTF_PROJECT_ROOT is unset, so the git-tracked cycle file lives
    at scripts/docs/bridgeV002/current-cycle.json. This handler MUST
    write the same file — do not "fix" the path independently.
    """
    return os.path.join(config.get_project_root(),
                        "scripts", "docs", "bridgeV002",
                        "current-cycle.json")


def find_trend_snapshot(deliverable_dir=None, deliverable_file=None):
    """Locate the trend01_trade JSON to snapshot.

    Priority: (1) the exact deliverable dispatch passed us; (2) the newest
    matching file in the configured trade inbox (pending/ AND processed/ —
    the import pipeline moves files to processed/). Returns path or None.
    """
    if deliverable_dir and deliverable_file:
        exact = os.path.join(deliverable_dir, deliverable_file)
        if os.path.exists(exact):
            return exact
        print(f"portfolio-snapshot: exact deliverable missing ({exact}); "
              f"falling back to newest inbox match", file=sys.stderr)

    inbox = config.get_trade_inbox_dir()
    base = (os.path.dirname(inbox)
            if os.path.basename(inbox) == "pending" else inbox)
    candidates = []
    for sub in ("pending", "processed"):
        d = os.path.join(base, sub)
        if not os.path.isdir(d):
            print(f"portfolio-snapshot: directory missing, skipped: {d}",
                  file=sys.stderr)
            continue
        for name in os.listdir(d):
            if any(p.match(name) for p in _NAME_PATTERNS):
                candidates.append(os.path.join(d, name))
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def write_snapshot(source_path, output_path):
    """Copy the trend JSON to the snapshot location (validated as JSON)."""
    with open(source_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"portfolio-snapshot: saved {output_path} (from {source_path})")


def update_cycle_state(cycle_path):
    """Mark portfolio_snapshot_processed=true, preserving other fields.

    Missing/corrupt cycle file is logged and tolerated (never raises).
    """
    try:
        with open(cycle_path, "r", encoding="utf-8") as f:
            cycle = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"portfolio-snapshot: cycle state not updated "
              f"({cycle_path}: {exc})", file=sys.stderr)
        return
    cycle["updated"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    cycle["portfolio_snapshot_processed"] = True
    with open(cycle_path, "w", encoding="utf-8") as f:
        json.dump(cycle, f, indent=2, ensure_ascii=False)
    print(f"portfolio-snapshot: cycle state updated at {cycle_path}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Snapshot newest trend01_trade output for the "
                    "portfolio cockpit")
    # Full flow-context CLI as produced by dispatch.step_to_cli_args —
    # every flag optional so manual runs work too.
    parser.add_argument("--flow-key", default=None)
    parser.add_argument("--step-key", default=None)
    parser.add_argument("--from-role", default=None)
    parser.add_argument("--to-role", default=None)
    parser.add_argument("--deliverable-dir", default=None)
    parser.add_argument("--deliverable-pattern", default=None)
    parser.add_argument("--deliverable-file", default=None)
    parser.add_argument("--handoff-id", default=None)
    parser.add_argument("--bridge-dir", default=None)
    parser.add_argument("--prompt-template", default=None)
    args = parser.parse_args(argv)

    source = find_trend_snapshot(deliverable_dir=args.deliverable_dir,
                                 deliverable_file=args.deliverable_file)
    if source is None:
        print("portfolio-snapshot: no trend01_trade output found — "
              "nothing snapshotted (exit 0: pre-dispatch must not abort "
              "the chain)", file=sys.stderr)
        return 0

    try:
        write_snapshot(source, snapshot_output_path())
        update_cycle_state(cycle_state_path())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"portfolio-snapshot: ERROR: {exc} — continuing (exit 0: "
              f"observability, not a gate)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] Step 4: `python3 -m py_compile scripts/portfolio_snapshot_handler.py` — exit 0.
- [ ] Step 5: Run `python3 -m pytest tests/test_portfolio_snapshot_handler.py -q` — all pass (`7 passed`).
- [ ] Step 6: Gate re-check for this file: `grep -n '"/home/svend' scripts/portfolio_snapshot_handler.py` — no output.

---

### Task 6: Wire the handler as `pre_dispatch_script` on `trend01-market01`

**Files:** Modify `scripts/seed_bridge.py` (new idempotent section). Data: `databases/dpmtf.db` via re-running seed_bridge.

Decision (verified against both candidates): wiring goes on the **`trend01-market01` step's `pre_dispatch_script`** — the mechanism `import-flow-output` already uses (on `sim01-portfolio01`, whose slot is occupied). `trade-cronjob.sh` was rejected: it runs BEFORE trend01 produces output (edge case 11).

- [ ] Step 1: In `scripts/seed_bridge.py`, add a new numbered section directly BEFORE the final "Commit + summary" block (after the `json_output` UPDATE):

```python
# ═══════════════════════════════════════════════════════════════════════
# 10. PORTFOLIO SNAPSHOT HANDLER — script registry + step wiring
# ═══════════════════════════════════════════════════════════════════════
# Fires during trend01_trade's signal-complete (trend01-market01 step),
# right after dispatch verified the fresh {ID}_trend01_trade.json exists.
# INSERT OR IGNORE + IS NULL guard: never overwrites operator choices.

cursor.execute(
    """INSERT OR IGNORE INTO bridge_scripts
       (script_key, name, description, path, stage, params_required)
       VALUES (?, ?, ?, ?, ?, ?)""",
    (
        "portfolio-snapshot",
        "Portfolio Snapshot",
        "Copy newest trend01_trade output to databases/"
        "portfolio_snapshot.json + mark cycle state (observability, "
        "exit 0 always)",
        "scripts/portfolio_snapshot_handler.py",
        "pre",
        "--deliverable-dir,--deliverable-file,--handoff-id",
    ),
)

cursor.execute(
    """UPDATE bridge_flow_steps
       SET pre_dispatch_script = 'portfolio-snapshot'
       WHERE flow_key = 'trade_cockpit_simulation_v001'
         AND step_key = 'trend01-market01'
         AND pre_dispatch_script IS NULL""",
)
```

- [ ] Step 2: `python3 -m py_compile scripts/seed_bridge.py` — exit 0. Apply to the live DB: `python3 scripts/seed_bridge.py`.
- [ ] Step 3: Verify the wiring:
  `sqlite3 databases/dpmtf.db "SELECT pre_dispatch_script FROM bridge_flow_steps WHERE flow_key='trade_cockpit_simulation_v001' AND step_key='trend01-market01'; SELECT path, is_active FROM bridge_scripts WHERE script_key='portfolio-snapshot';"`
  Expected:
  ```
  portfolio-snapshot
  scripts/portfolio_snapshot_handler.py|1
  ```
- [ ] Step 4: Dry-run the invocation exactly as dispatch would: `python3 scripts/portfolio_snapshot_handler.py --flow-key trade_cockpit_simulation_v001 --step-key trend01-market01 --from-role trend01_trade --to-role market01_trade --handoff-id 072 --deliverable-dir "$(python3 -c 'import config;print(config.get_trade_inbox_dir())')" --deliverable-file 072_trend01_trade.json; echo "exit=$?"` — expected: `exit=0`, and either a "saved .../databases/portfolio_snapshot.json" line (file 072 exists on this machine) or the loud stderr fallback.

---

### Task 7: Ø-5 / G6 — verify and document

**Files:** none modified (audit-only; findings go in this plan's execution notes).

- [ ] Step 1: Gate G6: `grep -nE "cursor\.execute\(f" app.py` — MUST be empty (it is: `app.py` is a 145-line shell; the roadmap's line-1538/3491 targets were removed when endpoints moved to `routers/`).
- [ ] Step 2: Extended audit: `grep -rnE "execute\(f[\"']" app.py routers/ scripts/init_db.py scripts/bridgeV002/ | grep -v __pycache__` — expected hits ONLY these six, all of the whitelist-SET-clause form:
  - `routers/sessions.py:205` — `updates` built from literal strings (`"status = ?"`, `"validation_run_id = ?"`, ...), values via `params`.
  - `routers/bridge.py:233` — fields from `updatable = ["content_template", "validation_schema", "rule_type"]`.
  - `routers/bridge.py:437` — fields appended as literal `"col = ?"` strings (step patch + convention auto-fill).
  - `routers/bridge.py:548` and `:598` — fields from the roles `updatable` whitelist.
  - `routers/bridge.py:832` — flows whitelist.
  For each: confirm the interpolated fragment contains ONLY literal column names + `?` markers and that every VALUE binds through the params list. If any site interpolates request data into the identifier position, STOP and add an explicit whitelist assert there (`assert field in updatable`) before the execute — but per current source, none does.
- [ ] Step 3: Record the audit conclusion in the task-execution notes (for the reviewer): "G6 empty for app.py; routers use the identifier-whitelist + `?`-values pattern, which is the correct SQLite approach since identifiers cannot be parameterized."

---

### Task 8: Final gates, stage and stop

- [ ] Step 1: Gate G5: `grep -rn '"/home/svend' app.py scripts/ config.py | grep -v __pycache__` — MUST print nothing.
- [ ] Step 2: Spirit check: `grep -rn '/home/svend' scripts/*.py scripts/*.sh scripts/bridgeV002/*.py | grep -v __pycache__ | grep -v "^\S*:[0-9]*:#"` — remaining hits may only be crontab-example comment lines (and none in Python string literals).
- [ ] Step 3: Gate G6: `grep -nE "cursor\.execute\(f" app.py` — empty.
- [ ] Step 4: Validation battery: `python3 -m py_compile app.py scripts/portfolio_snapshot_handler.py scripts/seed_bridge.py scripts/bridgeV002/import-flow-output.py scripts/bridgeV002/dispatch.py`; `bash -n scripts/trade-cronjob.sh scripts/scoring-cronjob.sh scripts/ollama-stop-all.sh`; `python3 scripts/init_db.py && python3 scripts/init_db.py` (idempotent, runs clean twice); `python3 -m pytest -q`; `curl -s http://localhost:9130/api/health` → `{"status":"healthy"}`.
- [ ] Step 5: `git diff --stat` — expected: `scripts/trade-cronjob.sh`, `scripts/scoring-cronjob.sh`, `scripts/ollama-stop-all.sh`, `scripts/bridgeV002/import-flow-output.py`, `scripts/bridgeV002/dispatch.py`, `scripts/seed_bridge.py`, `databases/dpmtf.db`; new: `scripts/portfolio_snapshot_handler.py`, `tests/test_portfolio_snapshot_handler.py`. NOT touched: `app.py`, `config.py`, `scripts/init_db.py`, `dpmtf.ini`.
- [ ] Step 6: Stage with `git add scripts/trade-cronjob.sh scripts/scoring-cronjob.sh scripts/ollama-stop-all.sh scripts/bridgeV002/import-flow-output.py scripts/bridgeV002/dispatch.py scripts/seed_bridge.py scripts/portfolio_snapshot_handler.py tests/test_portfolio_snapshot_handler.py databases/dpmtf.db` and STOP — await Human commit approval. Suggested commit message: `[hardening] Fase Ø gates G5/G6 closed + portfolio snapshot handler standardized and wired`.

## Acceptance Criteria

1. `grep -rn '"/home/svend' app.py scripts/ config.py | grep -v __pycache__` — no output (gate G5 GREEN).
2. `grep -nE "cursor\.execute\(f" app.py` — no output (gate G6 GREEN).
3. `sqlite3 databases/dpmtf.db "SELECT content_template LIKE '%{SCRIPTS_DIR}/dispatch.py%' FROM bridge_convention_rules WHERE rule_key='json_output';"` — prints `1`.
4. `sqlite3 databases/dpmtf.db "SELECT pre_dispatch_script FROM bridge_flow_steps WHERE flow_key='trade_cockpit_simulation_v001' AND step_key='trend01-market01';"` — prints `portfolio-snapshot`.
5. `python3 -m pytest tests/test_portfolio_snapshot_handler.py -q` — `7 passed`; full `python3 -m pytest -q` has no new failures.
6. `python3 scripts/portfolio_snapshot_handler.py --handoff-id 000 --deliverable-dir /nonexistent --deliverable-file none.json; echo "exit=$?"` — stderr explains the fallback/nothing-found, and prints `exit=0` (chain-safe).
7. `python3 scripts/init_db.py && python3 scripts/init_db.py && python3 scripts/seed_bridge.py` — all exit 0 (idempotent).
8. `curl -s http://localhost:9130/api/health` returns `{"status":"healthy"}`.
