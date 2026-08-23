#!/usr/bin/env python3
"""
BridgeV002 dispatcher — universal script for ALL role-to-role transitions.
Reads config dynamically from bridge_lib. No hardcoded roles, sessions, or paths.
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = os.environ.get(
    "DPMTF_PROJECT_ROOT", str(Path(__file__).resolve().parent.parent.parent)
)
sys.path.insert(0, str(Path(__file__).parent))

from worker_routing import EnvelopeIncomplete, offer_to_worker, worker_target
from bridge_lib import (
    load_role_from_db,
    load_flow_from_db,
    resolve_convention_from_db,
    resolve_content_template_from_db,
    validate_deliverable_against_schema,
    auto_prepend_xml_sections,
    get_next_id_for_flow,
    bump_id_counter_past,
    ensure_subdir,
    resolve_placeholders,
    list_scripts_from_db,
    get_effective_model_source,
    get_flow_target_project,
)
from patch_mode import apply_mode_block
import harness
from execution_config import resolve_for_receiver, runtime_context_block

# ── Constants ──────────────────────────────────────────────
_STARTUP_FILE = "docs/StartUpNextSession.md"


def escalation_role(flow_key):
    """The role an escalation in this flow goes to: the chain's first role.

    Two convention rules used to hardcode `--to-role archi01` in the
    escalation command they inject -- strict_review's architect, baked into
    step-TYPE templates shared by every flow. preferred_cloud run 010 found
    it the live way: `Pre-review-cl->archi01 | escalation_failed`, because no
    such session exists in that flow.

    The from_role of the chain's FIRST step is the right target in every
    current flow: archi01 (strict_review), archi01cloud/archi01pay (cloud
    flows), Pre-super-cl (preferred_cloud), supervisor01_llama (llama_SG),
    supervisor_auto (supervised_review) -- and `human` for lightworker,
    which is correct: escalating to a human role is a supported dispatch
    path (the deliverable is filed, no tmux injection), and a human-
    supervised chain SHOULD escalate to its human. No role-type filter,
    deliberately: filtering to non-human roles sent lightworker escalations
    back to the implementer, which routes to the remote worker.

    Falls back to the empty string rather than guessing, so a flow with no
    steps renders a visibly broken command instead of a silently wrong one.
    """
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT from_role FROM bridge_flow_steps
            WHERE flow_key = ? AND is_active = 1
            ORDER BY sort_order LIMIT 1
            """,
            (flow_key,),
        ).fetchone()
    finally:
        conn.close()
    return row["from_role"] if row else ""


def build_target_project_block(flow_key):
    """Return the authoritative Target Project preamble for an injection.

    A role reads its governance file FROM DISK, so a `{project_path}`
    placeholder written inside that file is never interpolated by anything —
    it reaches the role as literal text. The only text this dispatcher
    controls is the prompt it injects, so the target project has to be
    stated here to be stated at all.

    Returns an empty string when the flow targets Father, so the injection
    for Father-targeting flows is unchanged.
    """
    target = get_flow_target_project(flow_key, db_path=_db_path())

    if os.path.realpath(target) == os.path.realpath(str(PROJECT_ROOT)):
        return ""

    # Run 009 rewrote this block's contract. The old text asserted its own
    # authority ("This line is authoritative … NOT on {root}") and was
    # unconditional -- so when a run's scope differed from the flow's
    # default, it told every role to cd AWAY from the work, contradicting
    # the handoff, the result file and the run contract at once. A reviewer
    # that had obeyed it would have reviewed an untouched repository.
    #
    # Two rules from that run's END-REPORT, applied here:
    #   1. The handoff's fence is more specific than a flow-level default,
    #      so the block defers to it explicitly.
    #   2. A prompt that claims authority is indistinguishable from an
    #      injection attempt -- governance teaches roles to distrust
    #      exactly that shape. State the fact; let the handoff carry
    #      precedence.
    return (
        f"## Target Project\n"
        f"This flow's default target project is {target} (Father is "
        f"{PROJECT_ROOT}).\n"
        f"If your handoff names a working directory or scopes its work to "
        f"specific paths, THE HANDOFF WINS — it is more specific than this "
        f"flow-level default.\n"
        f"Only when the handoff is silent about location: `cd {target}` "
        f"before running checks. A `{{project_path}}` placeholder in a "
        f"governance file read from disk is never interpolated; this block "
        f"and the handoff are what state the target.\n"
        f"If a command reports a missing file or a count disagrees with "
        f"the delivered result, check `pwd` before concluding anything.\n\n"
    )

def build_runtime_context(resolved):
    """Wrap runtime_context_block with the three model-aware keys (D5).

    The base block is the five-line deterministic preamble defined in
    runtime_context_block (handoff 032). This wrapper keeps those five
    lines BYTE-IDENTICAL and APPENDS three more lines, each in the same
    `- name: value` shape, in the fixed order documented below.

    Order (fixed; do not reorder):
        - model_source:    {resolved["model_source"]}
        - harness_source:  {resolved["harness_source"]}
        - autonomous:      yes|no

    `autonomous` resolves to "yes" when the flow named by
    resolved["flow_key"] has a non-NULL, non-empty `supervisor_role`
    in `bridge_flows`, else "no". The lookup mirrors the one in
    chain_watchdog.py: rows where `is_active = 1` and the column is
    set point to an autonomous flow; rows where the column is NULL or
    empty point to a Human-paired one.

    Deterministic: same resolved dict + same DB state yields a
    byte-identical string on every call. The block still ends in the
    same `\n\n` seam runtime_context_block produces, so the
    surrounding prompt assembly in dispatch.py is unchanged.
    """
    base = runtime_context_block(resolved)
    # runtime_context_block ends with "\n\n". Strip ONE trailing "\n"
    # so the appended lines sit on their own with one blank-line gap
    # to the base block, then re-add the seam "\n\n" at the end.
    if base.endswith("\n\n"):
        base = base[:-1]  # now ends with single "\n"

    # None renders as the stable literal "None" (matches runtime_context_block).
    def _r(value):
        if value is None:
            return "None"
        return str(value)

    # Autonomous = the flow has a per-flow supervisor_role in bridge_flows.
    # Mirrors chain_watchdog.py: "WHERE flow_key = ? AND is_active = 1".
    conn = sqlite3.connect(str(_db_path()))
    try:
        row = conn.execute(
            "SELECT supervisor_role FROM bridge_flows "
            "WHERE flow_key = ? AND is_active = 1",
            (resolved["flow_key"],),
        ).fetchone()
    finally:
        conn.close()
    sup = row[0] if row else None
    autonomous = "yes" if (sup is not None and str(sup).strip() != "") else "no"

    return (
        f"{base}"
        f"\n- model_source: {_r(resolved['model_source'])}"
        f"\n- harness_source: {_r(resolved['harness_source'])}"
        f"\n- autonomous: {autonomous}\n\n"
    )


def _resolve_receiver_execution_config(flow_key, receiver_role, handoff_id):
    """Thin logged wrapper around execution_config.resolve_for_receiver.

    Selection + precedence live ENTIRELY in execution_config.py; this
    wrapper only adds dispatch's standard log() call so the resolved
    governance_file + governance_source_level show up in trace.log
    alongside the rest of the dispatch event (handoff 032, D3b step 4).
    It MUST NOT re-derive the step selection or any precedence -- that
    is the whole point of the "single resolver" architecture.

    db_path is sourced from dispatch's own _db_path() so test fixtures
    that monkeypatch dispatch._db_path to a temp DB continue to work
    (the resolver would otherwise fall through to config.get_db_path()
    and read the production DB, which is what the legacy direct-column
    read did NOT do -- so this matters for parity, not just for tests).
    """
    resolved = resolve_for_receiver(flow_key, receiver_role, db_path=_db_path())
    log(
        receiver_role,
        handoff_id,
        "receiver_execution_config",
        f"flow={flow_key} gov_file={resolved['governance_file']} "
        f"source_level={resolved['governance_source_level']}",
    )
    return resolved

# ── Trade-MCP push contexts (PILOT) ────────────────────────
# Deterministic pre-fetched contexts injected into selected trade-role
# prompts at dispatch time (architecture spec sections 14/16 push path).
# Graceful degradation: any failure dispatches WITHOUT the block and
# prints a warning — the flow never blocks on trade-mcp availability.
_TRADE_MCP_BASE_URL = os.environ.get(
    "TRADE_MCP_BASE_URL", "http://127.0.0.1:9145"
)
# Push-mode per rolle konfigureres i bridge_roles.trade_mcp_push_mode
# (migration 004) — redigerbar via frontend. Ingen hardcodede rolle-maps.


def _trade_mcp_get(path, timeout=30):
    """GET a trade-mcp REST endpoint, returning parsed JSON."""
    import urllib.request

    req = urllib.request.Request(
        f"{_TRADE_MCP_BASE_URL}{path}",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


_MAX_RISK_CANDIDATES = 5


def _extract_candidate_proposals(deliverable_path):
    """Pull symbol + proposed entry/stop from the analyst deliverable.

    Supports both payload shapes:
    - legacy single-candidate: payload.symbol / entry_price / stop_loss
    - concentrated-growth multi-candidate: payload.candidates[] with the
      same per-candidate fields (only SIMULATED_BUY_CANDIDATE entries are
      risk-relevant; WATCHLIST_ONLY entries carry no entry/stop)
    Returns a list of proposals (possibly empty), capped at
    _MAX_RISK_CANDIDATES.
    """
    with open(deliverable_path, encoding="utf-8") as f:
        data = json.load(f)
    payload = data.get("payload") or {}

    def proposal(entry_dict):
        symbol = entry_dict.get("symbol")
        if not symbol or not isinstance(symbol, str):
            return None
        return {
            "symbol": symbol.strip().upper(),
            "entry": entry_dict.get("entry_price"),
            "stop": entry_dict.get("stop_loss"),
        }

    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        proposals = []
        for c in candidates:
            if not isinstance(c, dict):
                continue
            action = (c.get("candidate_action") or "").upper()
            if action and "BUY" not in action:
                continue  # WATCHLIST_ONLY etc. carry no actionable risk
            p = proposal(c)
            if p:
                proposals.append(p)
        return proposals[:_MAX_RISK_CANDIDATES]

    single = proposal(payload)
    return [single] if single else []


_MAX_MARKET_SYMBOLS = 25  # matches trade-mcp watchlist digest cap


def _extract_watch_symbols(deliverable_path):
    """Pull watch symbols from the trend deliverable.

    Supports payload.symbols[] and top-level symbols[]; items are dicts
    with a 'symbol' key or plain strings. Returns an upper-cased,
    de-duplicated, order-preserving list."""
    with open(deliverable_path, encoding="utf-8") as f:
        data = json.load(f)
    items = ((data.get("payload") or {}).get("symbols")
             or data.get("symbols") or [])
    symbols = []
    for item in items:
        sym = item.get("symbol") if isinstance(item, dict) else item
        if isinstance(sym, str) and sym.strip():
            s = sym.strip().upper()
            if s not in symbols:
                symbols.append(s)
    return symbols[:_MAX_MARKET_SYMBOLS]


def append_trade_mcp_context(prompt_text, flow_key, to_role,
                             previous_deliverable_path, mode=None):
    """Append a deterministic trade-mcp context block for push-path roles.

    mode kommer fra bridge_roles.trade_mcp_push_mode (migration 004)."""
    if not mode:
        return prompt_text
    try:
        if mode == "watchlist":
            context = _trade_mcp_get("/api/context/watchlist")
        elif mode == "market":
            # market01: one deterministic per-symbol fact block for every
            # watch symbol in the trend deliverable — prices/indicators come
            # from trade-mcp, never from web search (flow 070: Tavily price
            # failures pushed every candidate to WATCHLIST_ONLY).
            from urllib.parse import quote
            symbols = _extract_watch_symbols(previous_deliverable_path)
            if not symbols:
                print("  Trade-MCP push: no symbols in previous "
                      "deliverable; dispatching without context")
                return prompt_text
            contexts = []
            for symbol in symbols:
                found = _trade_mcp_get(
                    f"/api/assets?q={quote(symbol)}").get("assets", [])
                exact = [a for a in found
                         if a.get("canonical_symbol", "").upper() == symbol]
                if not exact:
                    print(f"  Trade-MCP push: symbol {symbol!r} not in "
                          f"registry; skipped")
                    continue
                ctx = _trade_mcp_get(
                    f"/api/context/trend/{exact[0]['id']}")
                ctx["symbol"] = symbol
                contexts.append(ctx)
            if not contexts:
                print("  Trade-MCP push: no symbols resolvable in "
                      "registry; dispatching without context")
                return prompt_text
            context = {"context_type": "market_multi",
                       "symbols_requested": len(symbols),
                       "symbols_resolved": len(contexts),
                       "assets": contexts}
        else:  # risk
            proposals = _extract_candidate_proposals(
                previous_deliverable_path)
            if not proposals:
                print("  Trade-MCP push: no candidate symbol in previous "
                      "deliverable; dispatching without context")
                return prompt_text
            from urllib.parse import quote, urlencode
            contexts = []
            for proposal in proposals:
                found = _trade_mcp_get(
                    f"/api/assets?q={quote(proposal['symbol'])}"
                ).get("assets", [])
                exact = [a for a in found
                         if a.get("canonical_symbol", "").upper()
                         == proposal["symbol"]]
                if not exact:
                    print(f"  Trade-MCP push: symbol "
                          f"{proposal['symbol']!r} not in registry; skipped")
                    continue
                params = {}
                if proposal["entry"] is not None:
                    params["entry"] = proposal["entry"]
                if proposal["stop"] is not None:
                    params["stop"] = proposal["stop"]
                query = f"?{urlencode(params)}" if params else ""
                ctx = _trade_mcp_get(
                    f"/api/context/risk/{exact[0]['id']}{query}"
                )
                ctx["candidate_symbol"] = proposal["symbol"]
                contexts.append(ctx)
            if not contexts:
                print("  Trade-MCP push: no candidates resolvable in "
                      "registry; dispatching without context")
                return prompt_text
            context = (contexts[0] if len(contexts) == 1
                       else {"context_type": "risk_multi",
                             "candidates": contexts})
        block = (
            f"\n\n<deterministic_market_context source=\"trade-mcp\" "
            f"mode=\"{mode}\">\n"
            + json.dumps(context, indent=1)
            + "\n</deterministic_market_context>\n"
            "<context_rule>The block above contains precomputed, versioned, "
            "deterministic facts from trade-mcp. Treat them as authoritative "
            "for prices, indicators, portfolio exposure, and risk arithmetic "
            "— do NOT recompute these values and do NOT web-search for "
            "values already provided. If a needed value is absent or marked "
            "degraded, say so in missing_data instead of estimating it."
            "</context_rule>"
        )
        print(f"  Trade-MCP push: injected {mode} context "
              f"(~{len(block) // 4} est. tokens)")
        return prompt_text + block
    except Exception as exc:
        print(f"  Trade-MCP push: unavailable ({exc}); "
              "dispatching without deterministic context")
        return prompt_text


def _bridge_dir():
    """Return the configured bridge directory."""
    return os.environ.get(
        "DPMTF_BRIDGE_DIR", os.path.expanduser("~/.bridge")
    )


def _db_path():
    """Return the absolute database path, resolving relative paths against PROJECT_ROOT."""
    import config as _cfg
    p = _cfg.get_db_path()
    if not os.path.isabs(p):
        p = os.path.join(PROJECT_ROOT, p)
    return p


def _model_allocator_path():
    """Return the absolute path to the model-allocator wrapper script."""
    import config as _cfg
    return os.path.join(
        _cfg.get_project_path("model-allocator"),
        "scripts",
        "model-allocator",
    )


# Large local runtimes (SGLang on a 30B AWQ model, llama.cpp on a 100B+ GGUF)
# need far longer than the allocator CLI's 120s default to reach a healthy
# health endpoint — weight load, CUDA graph capture and FlashInfer JIT all
# happen before the port answers. When the CLI timeout expires the adapter
# KILLS the server it just started, so a too-short timeout does not merely
# report failure: it guarantees the role never gets a model.
_MODEL_START_TIMEOUT = int(os.environ.get("DPMTF_MODEL_START_TIMEOUT", "900"))
_VRAM_RELEASE_TIMEOUT = int(os.environ.get("DPMTF_VRAM_RELEASE_TIMEOUT", "120"))


def _gpu_free_mib():
    """Return (free_mib, total_mib) for GPU 0, or (None, None) if unknown."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--id=0", "--query-gpu=memory.free,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return None, None
        free_s, total_s = result.stdout.strip().splitlines()[0].split(",")
        return int(free_s.strip()), int(total_s.strip())
    except Exception:
        return None, None


def _host_mem_mib():
    """Return (available_mib, shmem_mib) from /proc/meminfo, or (None, None).

    Shmem matters as much as VRAM for this chain: llama.cpp with
    --n-cpu-moe keeps the CPU-resident experts in shared memory (38 GB for
    Laguna), and unlike page cache that memory is NOT reclaimable — it is
    freed only when the server process exits. The next model cannot load
    its weights until it is gone.
    """
    try:
        values = {}
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                key, _, rest = line.partition(":")
                if key in ("MemAvailable", "Shmem"):
                    values[key] = int(rest.strip().split()[0]) // 1024
        return values.get("MemAvailable"), values.get("Shmem")
    except Exception:
        return None, None


def _wait_for_vram_release(timeout=None, min_free_ratio=0.85):
    """Block until the GPU has actually handed back its memory.

    A process dying returns control long before the driver has reclaimed
    its allocation, so the next model would load into a GPU that is still
    full. The adapters now confirm a stop against the server port, which
    means this wait is only ever waiting on the driver — usually a second
    or two, not the tens of seconds a fixed sleep would have to assume.

    So it converges on two conditions instead of one deadline: the target
    free memory being reached, or the reading going flat. Flat means the
    reclaim has finished and no amount of further waiting will change the
    number. Without that second condition an unreachable target burns the
    entire budget — observed twice, 120 seconds of dead time each, when
    another process legitimately held part of the GPU.

    Returns True when the GPU settled, False on timeout (the caller
    continues anyway — a slow release is better than a dead chain).
    """
    timeout = _VRAM_RELEASE_TIMEOUT if timeout is None else timeout
    free, total = _gpu_free_mib()
    if free is None:
        time.sleep(2.0)  # no nvidia-smi — fall back to a blind wait
        return False

    target = int(total * min_free_ratio)
    started = time.time()
    deadline = started + timeout
    stable_polls = 0
    previous = free

    def _report(reason, value):
        avail, shmem = _host_mem_mib()
        host = ""
        if avail is not None:
            host = f"; host RAM {avail} MiB available, {shmem} MiB shmem"
        print(f"  VRAM {reason}: {value} MiB free of {total} MiB "
              f"after {time.time() - started:.1f}s{host}")

    while time.time() < deadline:
        if free >= target:
            _report("released", free)
            return True
        # Give the driver a moment before trusting a flat reading: the
        # reclaim can start a beat after the process exits.
        if time.time() - started >= 2.0:
            stable_polls = stable_polls + 1 if free <= previous else 0
            if stable_polls >= 3:
                _report("settled below target", free)
                return True
        previous = free
        time.sleep(0.5)
        free, total = _gpu_free_mib()
        if free is None:
            return False

    print(f"  WARNING: VRAM only {free}/{total} MiB free after {timeout}s "
          f"(target {target} MiB) — starting next model anyway")
    return False


def _run_allocator_start(model_alias, timeout=None):
    """Warm up an allocator-managed model before prompt injection.

    Runs `model-allocator start --alias <model_alias>` with an outer timeout.
    Returns True on success, False on failure (dispatch continues anyway).
    """
    start_timeout = _MODEL_START_TIMEOUT if timeout is None else timeout
    start_cmd = [_model_allocator_path(), "start", "--alias", model_alias,
                 "--timeout", str(start_timeout)]
    try:
        t0 = time.time()
        result = subprocess.run(
            start_cmd,
            capture_output=True,
            text=True,
            timeout=start_timeout + 60,
        )
        elapsed = int(time.time() - t0)
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            stdout = result.stdout.strip() if result.stdout else ""
            print(f"  WARNING: model-allocator start returned "
                  f"{result.returncode} after {elapsed}s: {stderr or stdout}")
            return False
        print(f"  Warmed allocator model '{model_alias}' in {elapsed}s")
        return True
    except subprocess.TimeoutExpired:
        print(f"  WARNING: model-allocator start timed out for '{model_alias}' "
              f"after {start_timeout + 60}s")
        return False
    except Exception as exc:
        print(f"  WARNING: model-allocator start failed: {exc}")
        return False


def _sweep_orphaned_leases():
    """Drop lease rows left behind by dead/cyclic runs (hygiene, no model stop).

    Runs once at the top of each dispatch. Leases persist in SQLite and a
    crashed, killed, or never-closing cyclic run never releases them, so
    they accumulate indefinitely. sweep_orphaned deletes rows past an age
    threshold only — it never stops a model (VRAM reclaim stays with
    _stop_other_local_models). Best-effort: a sweep failure must never block
    a dispatch.
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "job_queue"))
        from model_lease import LeaseRegistry
        swept = LeaseRegistry.sweep_orphaned()
        if swept:
            detail = ", ".join(f"{l.alias}({l.job_id})" for l in swept)
            print(f"  Lease sweep: dropped {len(swept)} orphaned lease(s): {detail}")
    except Exception as exc:
        print(f"  WARNING: orphaned-lease sweep skipped: {exc}")


def _run_allocator_stop(model_alias, timeout=45):
    """Stop an allocator-managed model without hanging.

    Runs `model-allocator stop --alias <model_alias>` with an outer timeout.
    Returns True on success/already-unloaded, False on real failure.
    """
    stop_cmd = [_model_allocator_path(), "stop", "--alias", model_alias]
    try:
        result = subprocess.run(
            stop_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            print(f"  WARNING: model-allocator stop returned {result.returncode}: {stderr}")
            return False
        print(f"  Stopped allocator model '{model_alias}'")
        return True
    except subprocess.TimeoutExpired:
        print(f"  WARNING: model-allocator stop timed out for '{model_alias}'")
        return False
    except Exception as exc:
        print(f"  WARNING: model-allocator stop failed: {exc}")
        return False


_REAL_MODEL_CACHE = {}


def _resolve_real_model(alias):
    """Resolve an alias to its concrete model via the allocator (cached).

    Two aliases can point at the same real model (review01-local and
    review02-local both run qwen3.6:35b-a3b-64k) — VRAM decisions must
    compare real models, never aliases. Returns "" when unresolvable.
    """
    if alias in _REAL_MODEL_CACHE:
        return _REAL_MODEL_CACHE[alias]
    for client in ("opencode", "claude-code"):
        try:
            result = subprocess.run(
                [_model_allocator_path(), "validate",
                 "--alias", alias, "--client", client, "--json"],
                capture_output=True, text=True, timeout=20,
            )
            if result.returncode in (0, 2) and result.stdout.strip():
                real = json.loads(result.stdout).get("resolved_real_model") or ""
                if real:
                    _REAL_MODEL_CACHE[alias] = real
                    return real
        except Exception:
            continue
    _REAL_MODEL_CACHE[alias] = ""
    return ""


def _allocator_state_dir():
    """The directory where local backend adapters keep their PID files."""
    return os.environ.get("MODEL_ALLOCATOR_STATE_DIR") or tempfile.gettempdir()


def _stop_other_local_models(to_alias):
    """Stop resident local models that would deny the target its VRAM.

    The VRAM-first swap only frees the SENDER's model. A local model started
    outside the current step — a manual `model-allocator start`, a crashed
    chain's leftovers — is invisible to it, and warming the target into a
    full GPU makes llama-server exit on OOM within a second (reveng verdicts
    061/062, 2026-08-14). Local adapters drop `model-allocator-{alias}-{port}.pid`
    in the state dir, so residency is enumerable without hardcoding aliases.
    Aliases sharing the target's real model are left loaded — the target
    reuses those weights.
    """
    if not to_alias:
        return
    prefix = "model-allocator-"
    try:
        names = os.listdir(_allocator_state_dir())
    except OSError:
        return
    to_real = _resolve_real_model(to_alias)
    stopped_any = False
    for name in names:
        if not (name.startswith(prefix) and name.endswith(".pid")):
            continue
        alias = name[len(prefix):-len(".pid")].rsplit("-", 1)[0]
        if not alias or alias == to_alias:
            continue
        real = _resolve_real_model(alias)
        if to_real and real and real == to_real:
            continue
        print(f"  GPU sweep: stopping resident local model '{alias}' "
              f"before warming '{to_alias}'")
        _run_allocator_stop(alias)
        stopped_any = True
    if stopped_any:
        _wait_for_vram_release()


def _backend_is_down(alias):
    """True when the alias resolves to a LOCAL backend whose server is dead.

    Injecting into a role whose backend is down still lands in the pane, so
    trace.log said "delivered" while the turn died on "Cannot connect to
    API" — and the watchdog read the chain as complete (reveng verdict 061).
    This is the gate that makes that state visible. Fail-open on anything
    unparseable and on non-local backends: a cloud alias has no local server
    to probe, and a false "down" would make the watchdog re-nudge a healthy
    delivery until escalation.
    """
    if not alias:
        return False
    try:
        result = subprocess.run(
            [_model_allocator_path(), "status", "--alias", alias],
            capture_output=True, text=True, timeout=20,
        )
        status = json.loads(result.stdout) if result.stdout.strip() else {}
    except Exception:
        return False
    if status.get("backend") not in ("llama_cpp", "sglang"):
        return False
    return not status.get("running", True)


def _release_from_model_first(handoff_id, from_alias, to_alias):
    """Free the completing role's VRAM BEFORE the next model is warmed.

    Warming the target model while the predecessor is still resident put
    both in VRAM at once — observed live: qwen3-coder:30b loaded 6%/94%
    CPU/GPU because the 35b was never unloaded. When both aliases resolve
    to the SAME real model, the lease is released without stopping (the
    target keeps using the loaded weights — no swap needed at all).

    Returns True when the from-model was handled (release/stop done here).
    """
    if not from_alias or from_alias == to_alias:
        return False
    from_real = _resolve_real_model(from_alias)
    to_real = _resolve_real_model(to_alias) if to_alias else ""
    same_real = bool(from_real) and from_real == to_real
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "job_queue"))
        from model_lease import LeaseRegistry
        if same_real:
            LeaseRegistry.release(handoff_id, from_alias, stop_model=False)
            print(f"  Lease on '{from_alias}' released without stop — "
                  f"same real model as '{to_alias}' ({to_real})")
        else:
            stopped = LeaseRegistry.release(handoff_id, from_alias)
            if stopped:
                print(f"  VRAM-first swap: stopped '{from_alias}' before "
                      f"warming '{to_alias}'")
                _wait_for_vram_release()
            else:
                remaining = LeaseRegistry.lease_count(from_alias)
                if remaining == 0:
                    # No lease was ever registered under this handoff id
                    # (historic key mismatches) — the model is unclaimed,
                    # free the VRAM anyway.
                    _run_allocator_stop(from_alias)
                    _wait_for_vram_release()
                else:
                    # The leases belong to earlier handoffs — the lease key is
                    # the handoff id, but a model outlives the handoff that
                    # claimed it. Honouring them here kept the predecessor
                    # resident and loaded the target into a full GPU, which is
                    # how every outbound swap stalled. The models differ (the
                    # same_real branch above already handled the shared case),
                    # so on one GPU the old one cannot stay.
                    print(f"  Model '{from_alias}' carries {remaining} lease(s) "
                          f"from earlier handoffs — stale, clearing and stopping")
                    LeaseRegistry.release_all(from_alias)
                    _wait_for_vram_release()
    except Exception:
        if not same_real:
            _run_allocator_stop(from_alias)
            _wait_for_vram_release()
    return True


def wait_session_ready(session_name, timeout=5):
    """Poll until tmux session is actually running. Returns True if ready."""
    for _ in range(timeout * 10):
        result = subprocess.run(
            ["tmux", "has-session", "-t", "=" + session_name],
            capture_output=True,
        )
        if result.returncode == 0:
            return True
        time.sleep(0.1)
    return False


def get_pane_command(session_name):
    """Detect which tool runs in the session's active pane.

    Returns lowercase string: 'opencode', 'claude', or 'unknown'.
    Used to adapt injection method per tool type.
    """
    result = subprocess.run(
        ["tmux", "list-panes", "-t", "=" + session_name, "-F", "#{pane_current_command}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return "unknown"
    cmd = result.stdout.strip().lower()
    if "opencode" in cmd:
        return "opencode"
    # Checked before the "node" test below on purpose: pi is a node program,
    # and matching it as "claude" would route its prompts down the raw
    # send-keys path — no XML stripping, no soft-clear preamble — which is
    # the shape that cost nine reveng handoffs a human nudge each.
    elif cmd == "pi" or cmd.endswith("/pi"):
        return "pi"
    elif "node" in cmd or "claude" in cmd:
        return "claude"
    return "unknown"


def inject_via_send_keys(session_name, text, enter_command="default"):
    """Send text + submit key via tmux send-keys.

    Supports per-role enter_command:
      - 'default': Enter in same command (Claude Code, standard)
      - 'c-m': Two-step — text first, then separate C-m (Freebuff)
      - 'c-j': Two-step with C-j (Ctrl+J / line feed)
      - 'c-d': Two-step with C-d (Ctrl+D / EOF)
    """
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".txt", prefix="bridge-inject-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        subprocess.run(["tmux", "load-buffer", tmp], check=True)

        # Submit based on enter_command
        # = prefix: exact session match (prevents prefix-matching imple01→imple01pay)
        # :0 suffix required — paste-buffer/send-keys need a window target
        # If session_name already contains a window spec (e.g. "flow-myflow:0"),
        # don't append another :0 — use it as-is.
        if ":" in session_name:
            target = "=" + session_name
        else:
            target = "=" + session_name + ":0"
        if enter_command == "c-m":
            # Two-step: paste text first, then separate C-m (Freebuff)
            subprocess.run(
                ["tmux", "paste-buffer", "-t", target], check=True
            )
            time.sleep(0.3)
            subprocess.run(
                ["tmux", "send-keys", "-t", target, "", "C-m"], check=True
            )
        elif enter_command == "c-j":
            subprocess.run(
                ["tmux", "paste-buffer", "-t", target], check=True
            )
            time.sleep(0.3)
            subprocess.run(
                ["tmux", "send-keys", "-t", target, "", "C-j"], check=True
            )
        elif enter_command == "c-d":
            subprocess.run(
                ["tmux", "paste-buffer", "-t", target], check=True
            )
            time.sleep(0.3)
            subprocess.run(
                ["tmux", "send-keys", "-t", target, "", "C-d"], check=True
            )
        else:  # "default" — paste text then Enter (Claude Code, standard)
            subprocess.run(
                ["tmux", "paste-buffer", "-t", target], check=True
            )
            time.sleep(0.3)
            subprocess.run(
                ["tmux", "send-keys", "-t", target, "Enter"], check=True
            )
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def inject_via_paste_buffer(session_name, text, enter_command="default"):
    """Write to temp file, load-buffer, paste-buffer, send submit key. Used for OpenCode sessions.

    Supports per-role enter_command (same values as inject_via_send_keys).
    """
    fd, tmp_path = tempfile.mkstemp(suffix=".txt", prefix="bridge-prompt-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        subprocess.run(["tmux", "load-buffer", tmp_path], check=True)
        # If session_name already contains a window spec, don't append :0
        if ":" in session_name:
            paste_target = "=" + session_name
        else:
            paste_target = "=" + session_name + ":0"
        subprocess.run(["tmux", "paste-buffer", "-t", paste_target], check=True)
        time.sleep(0.3)

        # Submit based on enter_command
        # = prefix: exact session match (prevents prefix-matching imple01→imple01pay)
        # :0 suffix required — paste-buffer/send-keys need a window target
        # If session_name already contains a window spec (e.g. "flow-myflow:0"),
        # don't append another :0 — use it as-is.
        if ":" in session_name:
            target = "=" + session_name
        else:
            target = "=" + session_name + ":0"
        if enter_command == "c-m":
            subprocess.run(
                ["tmux", "send-keys", "-t", target, "", "C-m"], check=True
            )
        elif enter_command == "c-j":
            subprocess.run(
                ["tmux", "send-keys", "-t", target, "", "C-j"], check=True
            )
        elif enter_command == "c-d":
            subprocess.run(
                ["tmux", "send-keys", "-t", target, "", "C-d"], check=True
            )
        else:  # "default" — original behavior
            subprocess.run(
                ["tmux", "send-keys", "-t", target, "Enter"], check=True
            )
        time.sleep(0.3)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _strip_xml_tags(text):
    """Remove XML tags from text to prevent model confusion.

    OpenCode models (especially qwen3-coder) see XML tags like <handoff>,
    <role>, <task> and hallucinate XML-style function calls instead of
    using opencode's native tool calling format. This converts opening
    tags to plain-text headers and removes closing tags entirely.
    """
    import re
    # Opening tags → plain text headers (closing tags just removed)
    opening_replacements = [
        (r'<handoff>', '--- Handoff ---'),
        (r'<role>', 'Role:'),
        (r'<task>', 'Task:'),
        (r'<constraint>', 'Constraint:'),
        (r'<deliverable>', 'Deliverable:'),
        (r'<notification>', 'Notification:'),
        (r'<handoff_id>', 'Handoff ID: '),
        (r'<source_role>', 'Source Role: '),
        (r'<deliverable_input>', 'Input:'),
        (r'<deliverable_output>', 'Output:'),
        (r'<context>', 'Context:'),
        (r'<project>', 'Project: '),
        (r'<dispatch_command>', 'Dispatch Command:'),
        # Spec section 26: PATCH_MODE_BLOCK opens with this tag. Unlisted,
        # the catch-all below reduced it to a bare 'deterministic_patch'
        # header — pi_test handoffs 005/006 delivered it that way and the
        # implementer reported the mode framing absent.
        (r'<implementation_mode>', 'Implementation Mode: '),
        (r'<parameter[^>]*>', ''),
        (r'<function[^>]*>', ''),
    ]
    for pattern, replacement in opening_replacements:
        text = re.sub(pattern, replacement, text)
    # Remove all closing tags
    text = re.sub(r'</[a-zA-Z_][a-zA-Z0-9_]*[^>]*>', '', text)
    # Remove any remaining XML tags
    text = re.sub(r'<[a-zA-Z_][a-zA-Z0-9_]*[^>]*/?>', '', text)
    # Clean up extra whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def wait_for_pane_idle(session_name, timeout=45, poll=1.5):
    """Block until the client's pane is quiet: no activity markers and no
    change between two consecutive reads.

    This exists because a fixed `time.sleep(2)` after the fresh-session
    command was not long enough for OpenCode, and the cost of being early
    is not a slow dispatch but a corrupted one -- the task text lands in an
    input box the client is still redrawing, and what gets submitted is not
    what was sent. See inject_prompt for the measured failure.

    Returns True when the pane settled, False on timeout. A timeout is
    reported and then ignored: a late dispatch beats a blocked chain, and
    the caller's own submit-verification still runs.
    """
    deadline = time.time() + timeout
    previous = None
    markers = activity_markers(session_name)
    while time.time() < deadline:
        tail = _pane_tail(session_name)
        if previous is not None and tail == previous and not any(
            marker in tail for marker in markers
        ):
            return True
        previous = tail
        time.sleep(poll)
    print(f"  Pane idle wait: '{session_name}' still changing after "
          f"{timeout}s — proceeding anyway")
    return False


def _wrap_prompt_for_harness(to_role, text):
    """Prepare a prompt headed for a harness role for injection.

    The preferred_cloud_harness supervisor (super-deep-deep4) runs on the
    DeepSeek Harness through the persistent Harness Terminal. The terminal
    wraps the task into the one-shot `dsh --profile headless ...` command
    itself, so dispatch now sends the *semantic task* (flattened to a single
    request line for the terminal's stdin), not the full shell command. The
    command builder stays in harness.build_task_invocation — there is no
    second builder here.

    Non-dsh roles return their text unchanged, so every existing interactive
    client path is byte-for-byte unaffected.
    """
    try:
        if harness.resolve_harness(to_role) == "dsh":
            return text.replace("\n", " ")
    except Exception:
        pass
    return text


class PaneBusyRefused(Exception):
    """Raised by inject_prompt when the target pane refuses to accept a paste.

    Bound by preferred_cloud_harness Run 006 GOAL.md §1 D6(b): a busy pane
    (mid-turn activity markers) or an interactive menu/selector must not
    be pasted into, and the delivery must be REQUEUED with backoff —
    never silently dropped, never marked completed, never double-injected.

    The signal_*() call sites catch this and:
      1. print a "REFUSED_INJECTION: <reason>" marker to stdout/stderr so
         the broker can detect the refusal and requeue the row (the broker
         inspects stdout for the REFUSED_INJECTION prefix);
      2. return False so dispatch.py main() exits 0 without logging a
         trace.log delivery entry — recover_orphaned_rows and
         dispatch.py:transition_recently_delivered will both see the
         transition as NOT delivered, and the next claim retries.
    """


# Menu / selector patterns. Deliberately narrow and conservative — these
# match genuine interactive menus, NOT the ordinary idle footer (which
# carries generic glyphs and token totals — see the _ACTIVITY_MARKERS
# comment). The m3 mutation guard (GOAL.md §5) binds here: removing the
# menu-refusal condition must make the new dispatch_injection tests go RED.
# A selector AFFORDANCE is sufficient on its own: it only renders while a
# widget is actually waiting for input.
_MENU_AFFORDANCE_PATTERNS = (
    # Select/choose prompts (case-insensitive)
    r"\bselect\s+(an?\s+)?option\b",
    r"\bchoose\s+(an?\s+)?option\b",
    r"\bplease\s+(select|choose|pick)\b",
    # Selection headers ending in a colon ("Choose an action:", "Choose:")
    # — the colon separates a prompt from prose that merely mentions
    # choosing.
    r"\b(select|choose|pick)(\s+an?\s+\w+)?\s*:",
    r"\benter to select\b",
    r"\bpress enter to continue\b",
    # Confirmation prompts (npx install, plan approval, ...)
    r"\bok to proceed\b",
    r"\(y/n\)",
    r"\[y/n\]",
    r"\bapprove\s+(this\s+)?plan\b",
    r"\bdo you want to proceed\b",
)

# A numbered option list ("1. yes", "1) yes") is NOT sufficient on its own:
# model-authored summaries in an idle pane's scrollback are full of numbered
# lists, and treating them as menus refused every delivery to the supervisor
# terminal in a livelock (run 007, row 71, 2026-08-21 — the harness
# terminal's own turn summary matched). A numbered list counts only when a
# selector affordance is present in the same tail.
_MENU_NUMBERED_LIST = r"\n\s*\d+[\.\)]\s+\S"


def _pane_has_menu_or_selector(tail: str) -> bool:
    """True iff the pane tail shows an interactive menu/selector.

    Used by both inject_prompt (refuse to paste) and
    verify_injection_submitted (refuse to press Enter) — the menu check
    is shared so a pane that looked like a menu at injection time and
    a pane that looks like a menu at verify time get the same refusal.

    An affordance ("Enter to select", "Ok to proceed", "(y/n)", ...) is
    conclusive alone. A bare numbered list never is — it must co-occur
    with an affordance, because idle scrollback legitimately contains
    numbered lists (see _MENU_NUMBERED_LIST comment).
    """
    if not tail:
        return False
    for pat in _MENU_AFFORDANCE_PATTERNS:
        if re.search(pat, tail, re.IGNORECASE):
            return True
    return False


def _check_pane_safe_to_inject(session_name: str) -> None:
    """Read the pane tail and raise PaneBusyRefused if it shows
    activity markers (mid-turn) or an interactive menu/selector.

    Callers (signal_send / signal_complete / signal_escalation /
    signal_answer) catch the exception and emit REFUSED_INJECTION so
    the broker requeues with backoff (Run 006 D6(b)).
    """
    tail = _pane_tail(session_name)
    markers = activity_markers(session_name)
    for marker in markers:
        if marker in tail:
            raise PaneBusyRefused(
                f"pane '{session_name}' is busy (activity marker "
                f"{marker!r} present in tail)"
            )
    if _pane_has_menu_or_selector(tail):
        raise PaneBusyRefused(
            f"pane '{session_name}' shows interactive menu/selector "
            f"(would select an arbitrary option on submit)"
        )


def inject_prompt(session_name, text, enter_command="default",
                  fresh_session_command=None):
    """Detect tool type and route to correct injection method.

    For OpenCode sessions, prepends soft-clear preamble before actual prompt.
    For Claude Code sessions, uses send-keys directly.

    fresh_session_command (from bridge_roles.fresh_session_command — e.g.
    '/new' for OpenCode, '/clear' for Claude Code, NULL = opt out) is sent
    into the pane before the prompt to start the task on an EMPTY context.
    `ollama stop` only clears the server-side KV cache — the client resends
    its whole transcript with the next prompt, dragging previous tasks'
    context (and KV VRAM) into every new task. The command is per-role
    configuration so this code stays tool-independent. Use for new-task
    dispatches; never for escalation answers (the role must keep its
    context there).

    enter_command controls how the submit key is sent:
      - 'default': Enter (standard for Claude Code / OpenCode)
      - 'c-m': Two-step C-m (Freebuff)
      - 'c-j': Two-step C-j
      - 'c-d': Two-step C-d
    """
    # Run 006 D6(b): refuse to paste into a busy pane (mid-turn activity
    # markers) or an interactive menu/selector. The refusal is requeued
    # with backoff by the broker — never silently dropped, never marked
    # completed, never double-injected. This check runs BEFORE the
    # fresh_session_command path AND before any actual paste, because
    # send-keys into a menu pane would select an arbitrary option.
    _check_pane_safe_to_inject(session_name)

    tool = get_pane_command(session_name)
    # Observability: prompt size per dispatch (context-tuning data point).
    print(f"  Injection: {len(text)} chars (~{len(text) // 4} est. tokens) "
          f"-> '{session_name}' ({tool})")
    if fresh_session_command:
        subprocess.run(
            ["tmux", "send-keys", "-t", _pane_target(session_name),
             fresh_session_command, "Enter"],
            capture_output=True,
        )
        # The reset must land as its OWN submission before the task text is
        # pasted. It previously did not, and the consequence was measured on
        # 2026-08-12 across nine consecutive reveng handoffs: every one of
        # them produced the reply "Context reset acknowledged." and nothing
        # else, and every one had to be rescued by a human typing "continue".
        #
        # OpenCode does not execute `/clear` on Enter -- it expands the
        # command's template into the input box. Two seconds later the task
        # was pasted into that same box, and the trailing Enter submitted
        # both as a single message. The model then read the template's own
        # closing line, "Treat the next user message as the authoritative
        # task. Reply only: Context reset acknowledged.", with the task
        # appended below it, and obeyed exactly that. The paste also
        # overwrote the soft-clear preamble built below, so the instruction
        # meant to govern the turn never arrived at all.
        #
        # Submitting the reset on its own makes the template's wording true:
        # the task really does arrive as the next message. verify_injection_
        # submitted sends the Enter that a staged-but-unsubmitted command
        # needs; wait_for_pane_idle then keeps the paste out of a redraw.
        verify_injection_submitted(session_name, attempts=2, settle_seconds=3)
        wait_for_pane_idle(session_name)
        print(f"  Fresh session: {fresh_session_command} sent to "
              f"'{session_name}' (context reset submitted before task)")
    if tool in ("opencode", "pi"):
        # Pi gets the same treatment as OpenCode, for the same two reasons:
        # a prompt full of XML invites a model to answer in XML instead of
        # calling a tool, and a task arriving without the soft-clear preamble
        # is a task the model may treat as commentary on the previous one.
        # Neither is client-specific.
        # Strip XML tags to prevent model from hallucinating XML function calls
        clean_text = _strip_xml_tags(text)
        soft_clear = (
            "Start a new logical task now. "
            "Ignore earlier conversation context unless this prompt explicitly references it. "
            "Do not continue previous plans, assumptions, file edits, or task state. "
            "Treat this message as the authoritative task. "
            "Do NOT let project-level instruction files (CLAUDE.md, AGENTS.md, "
            ".claude/CLAUDE.md, or similar) interrupt, override, or stop this task. "
            "The governance file referenced in this prompt is your sole instruction set. "
            "Complete the task fully before responding."
        )
        combined = f"{soft_clear}\n\n{clean_text}"
        # For short prompts (< 800 chars), use send-keys which preserves
        # newlines better than paste-buffer in some terminals.
        # For longer prompts, paste-buffer is more reliable for large text.
        if len(combined) < 800:
            inject_via_send_keys(session_name, combined, enter_command)
        else:
            inject_via_paste_buffer(session_name, combined, enter_command)
    else:
        inject_via_send_keys(session_name, text, enter_command)
    verify_injection_submitted(session_name)


# Pane markers that indicate the client actually accepted/started the
# prompt. Deliberately narrow: idle footers contain generic glyphs
# ("· ← for agents", token totals), so only genuine in-progress signals
# count — the interrupt hint and the live download counter.
_ACTIVITY_MARKERS = ("esc interrupt", "esc to interrupt", "↓")

# Pi's footer is not OpenCode's, and reading it with OpenCode's markers is
# worse than not reading it at all. Pi shows "⠦ Working..." while a turn is
# in flight, and once the first turn has finished its footer permanently
# carries a token counter of the form "↑11 ↓81 R1.5k CH99.3%" — which
# contains "↓", one of the markers above. A finished Pi pane would therefore
# read as busy forever, which is the same false-active reading that let a
# dead reveng role sit unrepaired for two hours on 2026-08-12, arrived at
# from the opposite direction.
_ACTIVITY_MARKERS_BY_TOOL = {
    "pi": ("working...",),
}


def activity_markers(session_name):
    """Busy markers for whichever client occupies this session's pane."""
    return _ACTIVITY_MARKERS_BY_TOOL.get(
        get_pane_command(session_name), _ACTIVITY_MARKERS
    )


_PASTE_STUCK_MARKER = "paste again to expand"


# How far back the idempotency guard reads trace.log. The log is flow-wide,
# so this must comfortably outlast a single run's worth of entries.
_TRACE_SCAN_LINES = 4000


def transition_recently_delivered(bridge_dir, from_role, to_role, handoff_id,
                                  within_minutes=None):
    """True when trace.log shows this exact transition was already delivered.

    Delivery events are 'dispatched' (signal_send) and 'signal_complete'
    (callback injection). Failed attempts do not count. Used as an
    idempotency guard: a transition happens at most once per handoff id, so
    any further signal for the same (from_role->to_role, id) is a duplicate —
    the model's own late signal racing the scheduler nudge, or a re-run
    command.

    `within_minutes=None` means **ever**, and it is the right default: handoff
    ids never repeat within a flow, so a delivered transition stays delivered
    and age cannot make a duplicate legitimate. The bound used to be ten
    minutes, which contradicted the rule stated above. preferred_cloud runs
    004 and 005 paid for it four times: a re-run signal landing at ~12.4
    minutes cleared the window, re-validated the handoff as if it were a fresh
    deliverable, wrote an auto-prepended `<deliverable>` tag into it, and
    injected it into a role that was already working on it. A fifth arrived
    nineteen minutes after its run had closed and would have had the reviewer
    overwrite an approved verdict.

    A retry after a *failed* delivery is unaffected — `gate_rejected`,
    `signal_complete_failed` and `gate_rejection_undelivered` are not delivery
    events, so a role that was rejected can always signal again. For the case
    this cannot foresee — a `dispatched` that was logged but genuinely did not
    land — `--force` bypasses the guard.

    The scan reads the tail of a flow-wide log, so "ever" means "within the
    last `_TRACE_SCAN_LINES` entries". That is far past any live handoff.
    """
    trace = os.path.join(bridge_dir, "trace.log")
    try:
        with open(trace, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()[-_TRACE_SCAN_LINES:]
    except OSError:
        return False
    cutoff = None if within_minutes is None else time.time() - within_minutes * 60
    for line in reversed(lines):
        parts = line.split(" | ")
        if len(parts) < 4:
            continue
        if parts[1] != f"{from_role}->{to_role}" or parts[2] != str(handoff_id):
            continue
        if parts[3] not in ("dispatched", "signal_complete",
                            "signal_complete_to_human"):
            continue
        if cutoff is None:
            return True
        try:
            ts = datetime.strptime(
                parts[0], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            return True  # unparseable timestamp — assume recent, stay safe
        return ts >= cutoff
    return False


def _pane_target(session_name):
    """Exact-match pane target for capture-pane/send-keys.

    tmux resolves `=session` for has-session but NOT reliably for
    pane-level commands on grouped sessions — capture-pane needs the
    window spec (`=session:0`). Without it, capture failed silently and
    verify_injection_submitted always saw "no activity".
    """
    if ":" in session_name:
        return "=" + session_name
    return "=" + session_name + ":0"


def _pane_tail(session_name, lines=25):
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", _pane_target(session_name), "-p"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return ""
    return "\n".join(result.stdout.splitlines()[-lines:]).lower()


def verify_injection_submitted(session_name, attempts=3, settle_seconds=5):
    """Verify the injected prompt was actually SUBMITTED, not left sitting
    in the client's input buffer (observed: 'paste again to expand' state,
    silent unsubmitted pastes — flows 062/064 required manual Enter).

    Heuristic: after a settle delay, an accepted prompt shows activity
    markers (spinner/token counter) in the pane. A stuck paste shows the
    paste-expand hint or no activity. Remedy: resend Enter, recheck.
    Never raises; prints the outcome for the dispatch log.

    Run 006 D6(c): when the pane tail shows an interactive menu/selector,
    this function NEVER presses Enter (an Enter would select an arbitrary
    menu option). It reports the injection as UNCONFIRMED and leaves the
    pane alone. The stuck-paste remedy (resending Enter on the
    'paste again to expand' hint) still works — that hint is not a menu.
    """
    markers = activity_markers(session_name)
    for attempt in range(1, attempts + 1):
        time.sleep(settle_seconds)
        tail = _pane_tail(session_name)
        if _PASTE_STUCK_MARKER in tail:
            print(f"  Injection verify: stuck paste in '{session_name}' "
                  f"(attempt {attempt}) — resending Enter")
            subprocess.run(["tmux", "send-keys", "-t",
                            _pane_target(session_name),
                            "Enter"], capture_output=True)
            continue
        if _pane_has_menu_or_selector(tail):
            # Run 006 D6(c): never press Enter into a menu pane. An
            # Enter would select an arbitrary option. Report
            # UNCONFIRMED and leave the pane alone.
            print(f"  Injection verify: '{session_name}' shows interactive "
                  f"menu/selector — leaving pane alone, UNCONFIRMED")
            return False
        if any(marker in tail for marker in markers):
            print(f"  Injection verify: '{session_name}' active "
                  f"(attempt {attempt})")
            return True
        # No activity and no stuck-paste hint and no menu: the prompt
        # may be sitting unsubmitted without the hint (observed flow
        # 064 portfolio01).
        print(f"  Injection verify: no activity in '{session_name}' "
              f"(attempt {attempt}) — sending Enter")
        subprocess.run(["tmux", "send-keys", "-t",
                        _pane_target(session_name),
                        "Enter"], capture_output=True)
    tail = _pane_tail(session_name)
    submitted = any(m in tail for m in markers)
    print(f"  Injection verify: final state for '{session_name}': "
          f"{'active' if submitted else 'UNCONFIRMED — check pane manually'}")
    return submitted


def _resolve_existing_target(bridge_dir, subdir, target):
    """Return the target filename to symlink, preferring the original.

    If the requested file does not exist but a zero-padded variant does
    (e.g. 42_trend01_trade.json vs 042_trend01_trade.json), use the
    existing variant so current.md never dangles after a filename
    normalization performed by a downstream role/tool.
    """
    candidates = [target]
    m = re.match(r"^(\d+)_(.+)$", target)
    if m:
        candidates.append(f"{int(m.group(1)):03d}_{m.group(2)}")
    for candidate in candidates:
        if os.path.exists(os.path.join(bridge_dir, subdir, candidate)):
            return candidate
    return target


def update_symlink(bridge_dir, subdir, target):
    """Update current.md symlink for timeline navigation.

    The symlink target is resolved to an existing file when possible so the
    current.md cursor remains a reliable pointer across filename changes.
    """
    link_path = os.path.join(bridge_dir, subdir, "current.md")
    resolved_target = _resolve_existing_target(bridge_dir, subdir, target)
    try:
        if os.path.islink(link_path) or os.path.exists(link_path):
            os.unlink(link_path)
    except FileNotFoundError:
        pass
    os.symlink(resolved_target, link_path)


def log(direction, handoff_id, status, message, source="manual"):
    """Append to trace.log with UTC timestamp."""
    bridge_dir = _bridge_dir()
    trace_log = os.path.join(bridge_dir, "trace.log")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = f"{ts} | {direction} | {handoff_id} | {status} | {source} | {message}\n"
    os.makedirs(bridge_dir, exist_ok=True)
    with open(trace_log, "a", encoding="utf-8") as f:
        f.write(entry)


_GATE_MAX_REJECTIONS = int(os.environ.get("DPMTF_GATE_MAX_REJECTIONS", "2"))


def _gate_rejection_count(from_role, handoff_id):
    """How many times the gate has already turned this handoff back."""
    return _gate_rejection_state(from_role, handoff_id)[0]


def _gate_rejection_state(from_role, handoff_id):
    """(count, epoch of the most recent rejection) for this sender+handoff."""
    trace_log = os.path.join(_bridge_dir(), "trace.log")
    count = 0
    last_ts = 0.0
    try:
        with open(trace_log, encoding="utf-8") as handle:
            for line in handle:
                parts = [p.strip() for p in line.split("|")]
                # Match the SENDER exactly. A substring test counts the
                # wrong role: "review01SG" is inside "imple01SG->review01SG",
                # so the implementer's rejection was charged to the reviewer
                # and it escalated on its first offence instead of getting
                # its one chance to fix the deliverable.
                if (len(parts) >= 4 and parts[2] == str(handoff_id)
                        and parts[3] == "gate_rejected"
                        and parts[1].split("->")[0].strip() == from_role):
                    count += 1
                    try:
                        stamp = datetime.strptime(
                            parts[0], "%Y-%m-%dT%H:%M:%SZ"
                        ).replace(tzinfo=timezone.utc).timestamp()
                        last_ts = max(last_ts, stamp)
                    except ValueError:
                        pass
    except OSError:
        pass
    return count, last_ts


def _handle_gate_rejection(payload, handoff_id, bridge_dir):
    """Return a blocked deliverable to the role that wrote it.

    Without this the gate stops the chain in silence: the deliverable is
    refused, the rejection note is written, and nobody is told. The author
    believes it finished, the reviewer is never called, and the supervisor
    cannot park on a failure it never hears about.

    The rejection goes back to the role that produced the deliverable, which
    is still on the model it just used — so the round trip costs no GPU
    swap. Its context is deliberately preserved (no fresh_session_command):
    the role needs to remember what it was doing to fix it.

    After `DPMTF_GATE_MAX_REJECTIONS` attempts the loop stops. Sending the
    same work back to the same model a third time is how a chain spins
    forever, and by then the supervisor should rewrite the handoff or park.
    """
    from_role = payload.get("from_role", "")
    to_role = payload.get("to_role", "")
    direction = f"{from_role}->{to_role}"

    deliverable_dir = payload.get("deliverable_dir", "") or ""
    base = (deliverable_dir if os.path.isabs(deliverable_dir)
            else os.path.join(bridge_dir, deliverable_dir))
    note_path = os.path.join(base, f"{handoff_id}-gate-rejection.md")
    try:
        detail = Path(note_path).read_text(encoding="utf-8")
    except OSError:
        detail = "(the gate wrote no rejection note — check the dispatch log)"

    prior, last_rejection = _gate_rejection_state(from_role, handoff_id)

    # Re-running the gate over a deliverable nobody has touched since the
    # last refusal is the same refusal, not a new one. Counting it burned
    # the role's one chance while it was still working — a role that
    # re-signals reflexively, or a watchdog nudge arriving mid-fix, ran the
    # retry budget to zero in seconds.
    deliverable_path = os.path.join(
        base, payload.get("deliverable_file", "") or "")
    try:
        unchanged_since_rejection = (
            last_rejection > 0
            and os.stat(deliverable_path).st_mtime <= last_rejection)
    except OSError:
        unchanged_since_rejection = False

    if unchanged_since_rejection:
        print(f"  Gate refused {handoff_id} again, but the deliverable has "
              f"not changed since the last rejection — same offence, not "
              f"counting it. {from_role} still has the rejection.")
        return True

    attempts = prior + 1
    if attempts >= _GATE_MAX_REJECTIONS:
        log(direction, handoff_id, "gate_escalation_required",
            f"Gate blocked {handoff_id} {attempts}x — not returning it again; "
            f"supervisor must rewrite the handoff or park")
        print(f"  Gate has now blocked {handoff_id} {attempts} times — "
              f"NOT returning it to {from_role} again.")
        print(f"  This needs the supervisor: rewrite the handoff or park.")
        print(f"  Rejection detail: {note_path}")
        return False

    try:
        role_data = load_role_from_db(from_role, db_path=_db_path())
    except ValueError:
        print(f"  Cannot return the rejection — role '{from_role}' unknown")
        return False

    session = role_data.get("tmux_session")
    if not session or not wait_session_ready(session, timeout=3):
        print(f"  Cannot return the rejection — session '{session}' not running")
        log(direction, handoff_id, "gate_rejection_undelivered",
            f"session '{session}' not running")
        return False

    project_root = PROJECT_ROOT
    flow_key = payload.get("flow_key", "")
    prompt = (
        f"## Your deliverable was blocked before it reached {to_role}\n\n"
        f"An automatic evidence gate compared your report against the "
        f"working tree and refused it. This is not a review opinion — it "
        f"read the filesystem.\n\n"
        f"{detail}\n"
        f"## What to do now\n\n"
        f"Do NOT rewrite the report to look more convincing. Either make "
        f"the changes for real, or state plainly which ones you did not "
        f"make and why. Declining a change with a reason passes the gate; "
        f"claiming one that did not happen never will.\n\n"
        f"Check your own work first:\n\n"
        f"    cd {project_root} && git status --short\n\n"
        f"Then rewrite {handoff_id}-result.md so it matches what that "
        f"command actually shows, and signal again:\n\n"
        # 009: routed through the broker. The role enqueues a queue row;
    # the host-side broker daemon polls and dispatches via dispatch.py.
    f"    nohup python3 {project_root}/scripts/bridgeV002/bridge_broker.py "
        f"enqueue "
        f"--flow {flow_key} --from-role {from_role} "
        f"--to-role {from_role} "
        f"--id {handoff_id} --action signal-complete "
        f"> /tmp/bridge-enqueue-{flow_key}-{handoff_id}.log 2>&1 &\n"
    )

    # Run 006 D6(b): busy/menu pane → refuse + requeue (broker seam).
    try:
        inject_prompt(session, prompt,
                      enter_command=role_data.get("enter_command", "default"),
                      fresh_session_command=None)
    except PaneBusyRefused as _exc:
        print(f"REFUSED_INJECTION: {_exc}", flush=True)
        print(f"REFUSED_INJECTION: {_exc}", file=sys.stderr)
        return False
    log(direction, handoff_id, "gate_rejected",
        f"Evidence gate blocked the deliverable; returned to {from_role} "
        f"(attempt {attempts}/{_GATE_MAX_REJECTIONS})")
    print(f"  Gate rejection returned to '{from_role}' "
          f"(attempt {attempts}/{_GATE_MAX_REJECTIONS}) — no model swap needed")
    return True


def _update_cycle_state(handoff_id, flow_key, active_role, title=None,
                        design_notes=None, verification_checklist=None):
    """Update docs/bridgeV002/current-cycle.json after a successful dispatch.

    Called by every signal function to keep the Architect's cold-start state
    current. The JSON file is the single source of truth for cycle state —
    StartUpNextSession.md holds only durable reference information.
    """
    project_root = os.environ.get(
        "DPMTF_PROJECT_ROOT",
        str(Path(__file__).resolve().parent.parent)
    )
    cycle_file = os.path.join(project_root, "docs", "bridgeV002", "current-cycle.json")

    # Read existing state (preserve fields not being updated)
    current = {}
    if os.path.exists(cycle_file):
        try:
            with open(cycle_file, "r", encoding="utf-8") as f:
                current = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # Update fields
    current["last_handoff"] = handoff_id
    current["flow"] = flow_key
    current["active_role"] = active_role
    if title is not None:
        current["title"] = title
    if design_notes is not None:
        current["design_notes"] = design_notes
    if verification_checklist is not None:
        current["verification_checklist"] = verification_checklist
    current["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Write atomically via temp file
    os.makedirs(os.path.dirname(cycle_file), exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="cycle-",
                               dir=os.path.dirname(cycle_file))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
        os.replace(tmp, cycle_file)
    except OSError:
        if os.path.exists(tmp):
            os.unlink(tmp)


def build_step_payload(step, flow_key, handoff_id, bridge_dir):
    """Build a structured payload dict from a step row, convention rule, and context.

    The payload is the single source of truth passed to all dispatch scripts via CLI.

    Args:
        step: dict from bridge_flow_steps row
        flow_key: the flow key (e.g. 'heavy', 'simplified')
        handoff_id: string handoff ID (e.g. '106')
        bridge_dir: path to the bridge directory

    Returns:
        dict with keys: flow_key, step_key, from_role, to_role,
                       deliverable_dir, deliverable_pattern,
                       deliverable_file, error_msg, prompt_template,
                       handoff_id, bridge_dir
    """
    payload = {
        "flow_key": flow_key,
        "step_key": step.get("step_key", ""),
        "from_role": step.get("from_role", ""),
        "to_role": step.get("to_role", ""),
        "handoff_id": handoff_id,
        "bridge_dir": bridge_dir,
    }

    # deliverable_dir: use step value, fall back to convention template
    rule_key = step.get("rule_key")
    if step.get("deliverable_dir"):
        payload["deliverable_dir"] = step["deliverable_dir"]
    elif rule_key:
        try:
            convention = resolve_convention_from_db(rule_key, db_path=_db_path())
            payload["deliverable_dir"] = convention.get("dir_template", "")
        except (ValueError, sqlite3.OperationalError):
            payload["deliverable_dir"] = ""
    else:
        payload["deliverable_dir"] = ""

    # deliverable_pattern: use step value, fall back to convention template
    if step.get("deliverable_pattern"):
        payload["deliverable_pattern"] = step["deliverable_pattern"]
    elif rule_key:
        try:
            convention = resolve_convention_from_db(rule_key, db_path=_db_path())
            payload["deliverable_pattern"] = convention.get("pattern_template", "")
        except (ValueError, sqlite3.OperationalError):
            payload["deliverable_pattern"] = ""
    else:
        payload["deliverable_pattern"] = ""

    # deliverable_file: pattern with {ID} replaced by handoff_id,
    # {role_key} replaced by from_role (the role writing the file)
    pattern = payload.get("deliverable_pattern", "")
    payload["deliverable_file"] = pattern.replace("{ID}", handoff_id).replace("{role_key}", payload["from_role"])

    # error_msg: use step value, fall back to convention template
    if step.get("error_msg"):
        payload["error_msg"] = step["error_msg"]
    elif rule_key:
        try:
            convention = resolve_convention_from_db(rule_key, db_path=_db_path())
            tmpl = convention.get("error_template", "")
            payload["error_msg"] = tmpl.format(
                step_type=step.get("step_key", ""),
                to_role=payload["to_role"],
            )
        except (ValueError, sqlite3.OperationalError):
            payload["error_msg"] = f"Failed to deliver to {payload['to_role']}."
    else:
        payload["error_msg"] = f"Failed to deliver to {payload['to_role']}."

    # prompt_template: convention-provided template for enriched injection (Phase 2)
    if rule_key:
        try:
            convention = resolve_convention_from_db(rule_key, db_path=_db_path())
            payload["prompt_template"] = convention.get("prompt_template", "")
        except (ValueError, sqlite3.OperationalError):
            payload["prompt_template"] = ""
    else:
        payload["prompt_template"] = ""

    return payload


def step_to_cli_args(payload):
    """Convert a payload dict to a list of CLI arguments for subprocess invocation.

    Returns list like ['--flow-key', 'heavy', '--step-key', 'architect_to_implementer', ...]
    """
    args = []
    key_map = {
        "flow_key": "--flow-key",
        "step_key": "--step-key",
        "from_role": "--from-role",
        "to_role": "--to-role",
        "deliverable_dir": "--deliverable-dir",
        "deliverable_pattern": "--deliverable-pattern",
        "deliverable_file": "--deliverable-file",
        "handoff_id": "--handoff-id",
        "bridge_dir": "--bridge-dir",
        "prompt_template": "--prompt-template",
    }
    for pk, flag in key_map.items():
        val = payload.get(pk)
        if val is not None:
            args.append(flag)
            args.append(str(val))
    return args


def resolve_script_key(script_key, bridge_dir=None):
    """Resolve a script key (from bridge_flow_steps) to an absolute file path.

    Looks up the script key in bridge_scripts table, resolves placeholders
    in the stored path, and returns the absolute path.

    Args:
        script_key: Script key string (e.g. 'post-dispatch-common')
        bridge_dir: Optional bridge directory for placeholder resolution

    Returns:
        Absolute path to the script file, or None if not found.
    """
    if not script_key:
        return None

    scripts = list_scripts_from_db(db_path=_db_path())
    script_path = None
    for s in scripts:
        if s.get("script_key") == script_key:
            script_path = s.get("path", "")
            break

    if not script_path:
        print(f"  WARNING: Script key '{script_key}' not found in bridge_scripts")
        return None

    # Resolve placeholders in the stored path
    resolved = resolve_placeholders(script_path, bridge_dir=bridge_dir)
    # bridge_scripts stores paths relative to the project root. Roles run
    # dispatch from their own working directory — the flow's target project,
    # which for cloud_pay is a different repository entirely — so a relative
    # path resolved against the caller's CWD points at nothing. The script
    # was then reported missing and silently skipped.
    if resolved and not os.path.isabs(resolved):
        resolved = os.path.join(PROJECT_ROOT, resolved)
    return resolved


def execute_script_with_params(script_path, payload):
    """Execute a pre/post dispatch script with flow-context parameters.

    Args:
        script_path: Absolute path to the Python script to execute.
        payload: dict with flow context (flow_key, step_key, from_role, etc.)

    Returns:
        True on success, False on failure.
    """
    if not script_path:
        return True
    if not os.path.exists(script_path):
        # Configured but absent. Continuing here is how a gate disables
        # itself without anyone noticing: the step still ran, nothing was
        # checked, and the log said only "not found". A hook someone
        # deliberately configured is not optional.
        print(f"  ERROR: Configured script not found: {script_path}")
        print(f"         Refusing to continue — a configured check that "
              f"cannot run must not pass silently.")
        return False

    cli_args = step_to_cli_args(payload)
    cmd = ["python3", script_path] + cli_args

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Script {script_path} failed (rc={result.returncode})")
        stderr_preview = result.stderr[:300] if result.stderr else "(no stderr)"
        print(f"  Stderr: {stderr_preview}")
        return False
    stdout_truncated = result.stdout[:500] if result.stdout else ""
    if stdout_truncated:
        print(f"  Script output: {stdout_truncated.rstrip()}")
    return True


def _run_pre_dispatch_scripts(pre_script_value, payload, bridge_dir=None):
    """Run the chain's pre-dispatch scripts in listed order; abort on first failure.

    The pre_dispatch_script column on bridge_flow_steps may hold a single
    script key (today's contract) OR a comma-separated list of keys
    (Run 018 Spec #13). The helper splits on commas, resolves each key,
    runs them in listed order, and aborts on the first failure. A single
    script behaves byte-identically to today's behavior:
      * one resolve call
      * one "Running pre-dispatch script: <path>" line
      * one execute_script_with_params call
      * the same "Pre-dispatch script failed -- aborting" message on failure

    Returns (ok, ran_any):
      ok == False iff a script FAILED (caller MUST abort).
      ran_any == True iff at least one script actually executed (i.e.
      at least one key resolved to a real path AND we got past the
      resolve step). Callers that gate a downstream exists-check on
      "did a pre-dispatch run" (signal_complete) MUST consult ran_any
      so the check is byte-identical to today's "check runs only
      after a resolved script actually executed".

    An unregistered key (resolve returns None) is SKIPPED — neither
    runs nor aborts. Today this is exactly the existing behavior at
    both call sites (resolve returning None falls through, no print,
    no abort). The chaining refactor preserves it for each list entry.
    """
    if not pre_script_value:
        return True, False
    keys = [k.strip() for k in pre_script_value.split(",") if k.strip()]
    ran_any = False
    for key in keys:
        resolved_path = resolve_script_key(key, bridge_dir=bridge_dir)
        if resolved_path is None:
            # Unregistered key: SKIP (today's behavior — neither runs
            # nor aborts). The split-then-strip guarantees we never
            # downgrade a real-but-unregistered key into "".
            continue
        print(f"  Running pre-dispatch script: {resolved_path}")
        ran_any = True
        if not execute_script_with_params(resolved_path, payload):
            print(f"  Pre-dispatch script failed -- aborting")
            return False, True
    return True, ran_any


def session_alive(session_name):
    """Check if tmux session exists and is running. Instant yes/no, no wait."""
    result = subprocess.run(
        ["tmux", "has-session", "-t", "=" + session_name],
        capture_output=True,
    )
    return result.returncode == 0


def run_flow_step_db(flow_key, step_key, handoff_id, bridge_dir=None):
    """Execute a single flow step using database-backed configuration.

    Replaces INI-based run_flow_step(). All role config, step data, and
    convention templates are loaded from the database at runtime.

    Golden rule sequential dispatch sequence (no-kill v2):
      1. Load flow + step from DB
      2. Build payload from step + convention
      3. Load to_role from DB
      4. Check session_alive(target) -- instant yes/no, no wait
      5. Verify deliverable file exists -- fail fast if missing
      6. Ensure deliverable subdirectory exists
      7. Inject prompt (tool-aware: paste-buffer for OpenCode, send-keys for Claude)
      8. Post-dispatch: offload predecessor's Ollama model to free VRAM
      9. Update symlink + log dispatch event
    """
    import config as dpmtf_config

    if bridge_dir is None:
        bridge_dir = os.environ.get(
            "DPMTF_BRIDGE_DIR", dpmtf_config.get_bridge_base_path()
        )

    # Step 1: Load flow + step from DB
    try:
        flow_data = load_flow_from_db(flow_key, db_path=_db_path())
    except ValueError as e:
        print(f"Error loading flow '{flow_key}' from database: {e}")
        return False

    steps = flow_data["steps"]
    target_step = None
    if step_key:
        for s in steps:
            if s.get("step_key") == step_key:
                target_step = s
                break
    else:
        target_step = steps[0] if steps else None

    if not target_step:
        step_err = (f"Step '{step_key}' not found in flow '{flow_key}'"
                     if step_key else f"No active steps in flow '{flow_key}'")
        print(f"Error: {step_err}")
        return False

    # Step 2: Build payload from step + convention
    payload = build_step_payload(target_step, flow_key, handoff_id, bridge_dir)

    # Extract rule_key for validation and content template resolution (Step 6-7)
    rule_key = target_step.get("rule_key")

    # Step 3: Load to_role from DB
    try:
        to_role = load_role_from_db(payload["to_role"],
                                    db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{payload['to_role']}' from database: {e}")
        return False

    print(f"\nDispatch: {payload['from_role']} -> {payload['to_role']}")
    print(f"  Flow: {flow_key}, Step: {payload['step_key']}")
    print(f"  Deliverable: {payload['deliverable_file']}")

    tmux_session = to_role["tmux_session"]
    role_type = to_role.get("role_type", "agent")

    # G1: Human recipients skip tmux dispatch (no session, no injection)
    if role_type == "human":
        full_deliverable_path = os.path.join(bridge_dir,
                                             payload["deliverable_dir"],
                                             payload["deliverable_file"])
        print(f"  INFO: Delivering to human recipient — {full_deliverable_path}")
        log(
            f"{payload['from_role']}->{payload['to_role']}",
            handoff_id,
            "dispatched_to_human",
            f"Deliverable written to {full_deliverable_path} for human review",
        )
        return True

    # Step 4: Check session is alive (persistent session, not started)
    if not session_alive(tmux_session):
        print(f"  ERROR: Target session '{tmux_session}' is not running")
        log(
            f"{payload['from_role']}->{payload['to_role']}",
            handoff_id,
            "failed",
            f"Target session '{tmux_session}' is not running",
        )
        return False

    # Step 5: Verify deliverable file exists (fail fast)
    full_deliverable_path = os.path.join(bridge_dir,
                                         payload["deliverable_dir"],
                                         payload["deliverable_file"])
    if not os.path.exists(full_deliverable_path):
        print(f"  ERROR: Deliverable missing: {full_deliverable_path}")
        log(
            f"{payload['from_role']}->{payload['to_role']}",
            handoff_id,
            "failed",
            f"Deliverable missing: {full_deliverable_path}",
        )
        return False

    # Step 6
    ensure_subdir(bridge_dir, payload["deliverable_dir"])

    # ── Model lifecycle: swap from-role model → to-role model ──
    # Handled automatically for every step. Stop the predecessor's model
    # first (free GPU), wait for VRAM offload, then warm the target model.
    # Pre/post scripts are reserved for flow-specific logic (import gates,
    # validation) — NOT for model management.
    from_role_data = load_role_from_db(payload["from_role"],
                                       db_path=_db_path())
    from_source, from_alias = get_effective_model_source(
        from_role_data["role_key"],
        step_key=target_step.get("step_key"),
        flow_key=flow_key,
        db_path=_db_path(),
    )
    to_source, to_alias = get_effective_model_source(
        payload["to_role"],
        step_key=target_step.get("step_key"),
        flow_key=flow_key,
        db_path=_db_path(),
    )
    if from_source == "model_allocator" and from_alias and from_alias != to_alias:
        _run_allocator_stop(from_alias)
        if to_source == "model_allocator" and to_alias:
            _wait_for_vram_release()
    if to_source == "model_allocator" and to_alias:
        _stop_other_local_models(to_alias)
        _run_allocator_start(to_alias)

    # Pre-dispatch scripts: a single key (today) or comma-separated list
    # (Run 018 Spec #13). Single value behaves byte-identically to
    # today's inline resolve + execute + abort; a list runs in order,
    # aborts on first failure. See _run_pre_dispatch_scripts for the
    # contract.
    ok, _ = _run_pre_dispatch_scripts(
        target_step.get("pre_dispatch_script"), payload, bridge_dir=bridge_dir
    )
    if not ok:
        return False

    # Auto-prepend missing XML sections + validate deliverable
    step_validation_required = target_step.get("validation_required", 0)
    if step_validation_required and rule_key:
        # Safety net: auto-prepend missing XML sections before validation
        prepend_result = auto_prepend_xml_sections(
            full_deliverable_path, rule_key,
            handoff_id=handoff_id,
            source_role=payload["from_role"],
            flow_key=flow_key,
            bridge_dir=bridge_dir,
            db_path=_db_path(),
        )
        if prepend_result["prepended"]:
            print(f"  WARNING: Auto-prepended missing XML sections: {', '.join(prepend_result['missing'])}")
            log(
                f"{payload['from_role']}->{payload['to_role']}",
                handoff_id,
                "auto_prepend",
                f"Model omitted required XML sections; auto-prepended: {', '.join(prepend_result['missing'])}",
            )
        vresult = validate_deliverable_against_schema(full_deliverable_path, rule_key,
                                                      db_path=_db_path())
        if not vresult["valid"]:
            print(f"  ERROR: Deliverable validation failed, missing sections: {vresult['missing']}")
            log(
                f"{payload['from_role']}->{payload['to_role']}",
                handoff_id,
                "failed",
                f"Validation failed: missing {', '.join(vresult['missing'])}",
            )
            return False

    # Compose final injection text: use convention prompt_template or content_template from DB
    # Resolve model_name for {model_name} placeholder (via allocator alias)
    target_model_name_rs = to_role.get("default_model_alias", "")

    # Resolve output_file: the filename the TO role should write
    output_pattern_rs = payload.get("deliverable_pattern", "{ID}_{role_key}.json")
    output_file_rs = output_pattern_rs.replace("{ID}", payload["handoff_id"]).replace("{role_key}", payload["to_role"])

    prompt_text = payload.get("prompt_template", "")
    if not prompt_text:
        ctemplate = resolve_content_template_from_db(rule_key, db_path=_db_path())
        if ctemplate:
            prompt_text = ctemplate.replace("{handoff_id}", payload["handoff_id"])
            prompt_text = prompt_text.replace("{source_role}", payload["from_role"])
            prompt_text = prompt_text.replace("{next_role}", payload["to_role"])
            prompt_text = prompt_text.replace("{bridge_dir}", bridge_dir)
            prompt_text = prompt_text.replace("{flow_key}", payload["flow_key"])
            prompt_text = prompt_text.replace("{escalation_role}", escalation_role(payload["flow_key"]))
            prompt_text = prompt_text.replace("{project_path}", get_flow_target_project(payload["flow_key"], db_path=_db_path()))
            prompt_text = prompt_text.replace("{deliverable_dir}", payload["deliverable_dir"])
            prompt_text = prompt_text.replace("{deliverable_file}", payload["deliverable_file"])
            prompt_text = prompt_text.replace("{output_file}", output_file_rs)
            prompt_text = prompt_text.replace("{model_name}", target_model_name_rs)
            prompt_text = prompt_text.replace("{previous_deliverable_path}", full_deliverable_path)
        else:
            prompt_text = f"Read and execute {full_deliverable_path}"
    else:
        prompt_text = prompt_text.replace("{bridge_dir}", bridge_dir)
        prompt_text = prompt_text.replace("{handoff_id}", payload["handoff_id"])
        prompt_text = prompt_text.replace("{flow_key}", payload["flow_key"])
        prompt_text = prompt_text.replace("{escalation_role}", escalation_role(payload["flow_key"]))
        prompt_text = prompt_text.replace("{project_path}", get_flow_target_project(payload["flow_key"], db_path=_db_path()))
        prompt_text = prompt_text.replace("{deliverable_dir}", payload["deliverable_dir"])
        prompt_text = prompt_text.replace("{deliverable_file}", payload["deliverable_file"])
        prompt_text = prompt_text.replace("{output_file}", output_file_rs)
        prompt_text = prompt_text.replace("{model_name}", target_model_name_rs)
        prompt_text = prompt_text.replace("{previous_deliverable_path}", full_deliverable_path)

    prompt_text = apply_mode_block(prompt_text, _db_path(), flow_key, payload["step_key"], payload["to_role"])

    # Run 006 D6(b): busy/menu pane → refuse + requeue (broker seam).
    try:
        inject_prompt(tmux_session, prompt_text,
                      enter_command=to_role.get("enter_command", "default"),
                      fresh_session_command=to_role.get("fresh_session_command"))
    except PaneBusyRefused as _exc:
        print(f"REFUSED_INJECTION: {_exc}", flush=True)
        print(f"REFUSED_INJECTION: {_exc}", file=sys.stderr)
        return False
    time.sleep(0.5)

    # Post-dispatch: run post-script (cleanup/verification).
    # Model stop was handled before the pre-script above.

    post_script = target_step.get("post_dispatch_script")
    if post_script:
        resolved_path = resolve_script_key(post_script, bridge_dir=bridge_dir)
        if resolved_path:
            print(f"  Running post-dispatch script: {resolved_path}")
            execute_script_with_params(resolved_path, payload)

    update_symlink(bridge_dir, payload["deliverable_dir"], payload["deliverable_file"])

    # A delivered injection with a dead backend is NOT a delivery the chain
    # can act on — log a status the watchdog's field-exact needles will not
    # count, so its sender-stall branch re-sends (and re-warms) instead of
    # reading the flow as complete.
    backend_down = (to_source == "model_allocator"
                    and _backend_is_down(to_alias))
    if backend_down:
        print(f"  WARNING: backend for '{to_alias}' is down at injection — "
              f"logging dispatched_backend_down")
    log(
        f"{payload['from_role']}->{payload['to_role']}",
        handoff_id,
        "dispatched" if not backend_down else "dispatched_backend_down",
        f"Delivered {payload['deliverable_file']} to {tmux_session} (DB-driven)"
        + ("" if not backend_down else f" but backend '{to_alias}' is down"),
    )

    return True


def _ensure_session_ready(role_key, db_path=None):
    """Ensure a role's tmux session exists and has its coding frontend started.

    Creates the tmux session if missing, then sends the start command.
    Used by auto-chain to recover when a target session has died.

    Returns True if the session is ready after recovery, False otherwise.
    """
    if db_path is None:
        db_path = _db_path()

    try:
        role = load_role_from_db(role_key, db_path=db_path)
    except ValueError:
        print(f"  _ensure_session_ready: role '{role_key}' not found in DB")
        return False

    session_name = role.get("tmux_session", role_key)

    # Step 1: Create tmux session if it doesn't exist
    if not session_alive(session_name):
        print(f"  Creating tmux session '{session_name}'...")
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  ERROR: Failed to create session '{session_name}': {result.stderr.strip()}")
            return False
        time.sleep(0.3)

    # Step 2: Start coding frontend via Model Allocator
    model_source, model_alias = get_effective_model_source(
        role_key, db_path=db_path
    )
    if model_source == "model_allocator" and model_alias:
        try:
            import config as _cfg
            allocator_path = os.path.join(
                _cfg.get_project_path("model-allocator"), "scripts", "model-allocator"
            )
            # Determine client from the role's enter_command (Freebuff uses c-m)
            enter_cmd = role.get("enter_command", "default")
            if enter_cmd == "c-m":
                allocator_client = "freebuff"
            elif enter_cmd in ("c-j", "c-d"):
                allocator_client = "opencode"
            else:
                allocator_client = "opencode"
            run_cmd = [allocator_path, "run",
                        "--role", role_key,
                        "--client", allocator_client]
            if role.get("max_output_tokens"):
                run_cmd += ["--max-output-tokens", str(role["max_output_tokens"])]
            result = subprocess.run(
                run_cmd, capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                shell_str = result.stdout.strip()
                cwd = _cfg.get_project_root()
                cmd_str = f"cd {cwd} && {shell_str}"
                subprocess.run(
                    ["tmux", "send-keys", "-t", f"={session_name}:0",
                     cmd_str, "Enter"],
                    capture_output=True, text=True,
                )
                print(f"  Started coding frontend in '{session_name}' "
                      f"(allocator alias={model_alias})")
                time.sleep(1.0)
            else:
                print(f"  ERROR: allocator run failed: {result.stderr.strip()}")
                return False
        except Exception as e:
            print(f"  ERROR: allocator run error: {e}")
            return False
    else:
        print(f"  WARNING: role '{role_key}' has no model_allocator alias — "
              f"skipping frontend start")

    return session_alive(session_name)


def signal_complete(flow_key, step_key, from_role_key, handoff_id,
                    bridge_dir=None, force=False):
    """Signal that a role has completed its deliverable for a flow step.

    Replaces legacy bridge.py complete <ID>. DB-driven: loads the completed
    step, resolves callback convention, builds prompt from content_template,
    injects into next role's tmux session, and optionally chains to next step.

    Golden rule sequential dispatch sequence (no-kill v2):
      1. Load flow + steps from DB
      2. Find current step (by step_key or by matching from_role)
      3. Build payload from step + convention
      4. Load to_role from DB -> get tmux_session
      5. Check session_alive(to_role) -- fail if not running
      6. Verify deliverable file exists (written by completing role)
      7. Resolve content_template placeholders ({handoff_id}, {source_role}, ...)
      8. Inject callback prompt into to_role's tmux session
      9. Post-dispatch: stop from_role's Ollama model (VRAM cleanup)
      10. Update symlink in deliverable_dir
      11. Log completion event to trace.log

    Chain advancement is handled by the role itself via the <chain_advancement>
    block in the json_output content_template — the role runs signal-complete
    after writing its output. No code-level auto-chain here (removed — it
    duplicated the prompt-driven mechanism and caused multi-injections).
    """
    import config as dpmtf_config

    if bridge_dir is None:
        bridge_dir = os.environ.get(
            "DPMTF_BRIDGE_DIR", dpmtf_config.get_bridge_base_path()
        )

    _sweep_orphaned_leases()

    # Step 1: Load flow + steps from DB
    try:
        flow_data = load_flow_from_db(flow_key, db_path=_db_path())
    except ValueError as e:
        print(f"Error loading flow '{flow_key}' from database: {e}")
        return False

    steps = flow_data["steps"]

    # Step 2: Find current step (by step_key or by matching from_role)
    current_step = None
    if step_key:
        for s in steps:
            if s.get("step_key") == step_key:
                current_step = s
                break
    elif from_role_key:
        for s in steps:
            if s.get("from_role") == from_role_key:
                current_step = s
                break

    if not current_step:
        lookup = step_key if step_key else from_role_key
        print(f"Error: Step not found for '{lookup}' in flow '{flow_key}'")
        return False

    # Step 2a: manual-dispatch-only steps refuse chain delivery
    # (bridge_flow_steps.auto_dispatch = 0, migration 054). pi_test's
    # fan-out defect: every oc_imple01 completion was followed by a
    # second, improvised `--signal-complete --from-role human`, which on
    # this cyclic flow resolves the FIRST from_role='human' step
    # (human-pi_imple01) and re-injects the same handoff id into the
    # parallel implementer — a duplicate run of a possibly
    # repository-mutating task. The refusal fires BEFORE any session or
    # deliverable check: it must be the answer, not a side effect of a
    # missing session. --signal-send remains the only way into such a
    # step.
    if current_step.get("auto_dispatch") == 0:
        print(f"  REFUSED: step '{current_step.get('step_key')}' is "
              f"manual-dispatch only (auto_dispatch=0) — use --signal-send "
              f"explicitly; chain delivery is not allowed for this step")
        log(
            f"{current_step.get('from_role')}->{current_step.get('to_role')}",
            handoff_id,
            "signal_complete_refused",
            f"Step '{current_step.get('step_key')}' is manual-dispatch only "
            f"(auto_dispatch=0)",
        )
        return False

    # Step 3: Build payload from step + convention
    payload = build_step_payload(current_step, flow_key, handoff_id, bridge_dir)

    # Step 4: Load to_role from DB
    try:
        to_role = load_role_from_db(payload["to_role"],
                                    db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{payload['to_role']}' from database: {e}")
        return False

    rule_key = current_step.get("rule_key")

    print(f"\nSignal Complete: {payload['from_role']} -> {payload['to_role']}")
    print(f"  Flow: {flow_key}, Step: {payload['step_key']}")
    print(f"  Deliverable: {payload['deliverable_file']}")

    tmux_session = to_role["tmux_session"]
    role_type = to_role.get("role_type", "agent")

    # G1: Human recipients skip tmux dispatch (no session, no injection)
    if role_type == "human":
        full_deliverable_path = os.path.join(bridge_dir,
                                             payload["deliverable_dir"],
                                             payload["deliverable_file"])
        # Idempotency also applies to human deliveries — models re-run the
        # signal command (handoff 316: review02->human logged twice).
        # Harmless (no injection) but pollutes the trace bookkeeping.
        if not force and transition_recently_delivered(
                bridge_dir, payload["from_role"], payload["to_role"],
                handoff_id):
            print(f"  SKIP: {payload['from_role']}->{payload['to_role']} "
                  f"#{handoff_id} already delivered to human — duplicate "
                  f"suppressed (use --force to override)")
            return True
        print(f"  INFO: Completion delivered to human recipient — {full_deliverable_path}")
        log(
            f"{payload['from_role']}->{payload['to_role']}",
            handoff_id,
            "signal_complete_to_human",
            f"Completion deliverable at {full_deliverable_path} for human review",
        )
        return True

    # Step 5: Check target session is alive
    if not session_alive(tmux_session):
        print(f"  ERROR: Target session '{tmux_session}' is not running")
        log(
            f"{payload['from_role']}->{payload['to_role']}",
            handoff_id,
            "signal_complete_failed",
            f"Target session '{tmux_session}' is not running",
        )
        return False

    # Step 5a: Idempotency guard. A transition happens at most once per
    # handoff id — if trace.log shows it was already delivered within the
    # grace window, any further signal is a duplicate (the model's own late
    # signal racing the scheduler nudge, or a re-run command). This guard is
    # what makes fast nudging safe. --force bypasses for manual re-dispatch.
    #
    # The flock closes the seconds-level race the trace check cannot: two
    # signal processes starting within the same injection window would both
    # pass the trace check before either has logged. The lock is held until
    # process exit; a concurrent holder means an identical signal is already
    # in flight — treat as duplicate.
    if not force:
        import fcntl
        lock_name = f"bridge-tx-{flow_key}-{payload['from_role']}-{handoff_id}.lock"
        lock_path = os.path.join(tempfile.gettempdir(), lock_name)
        try:
            _tx_lock = open(lock_path, "w")
            fcntl.flock(_tx_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"  SKIP: identical signal for "
                  f"{payload['from_role']}->{payload['to_role']} "
                  f"#{handoff_id} already in flight — duplicate suppressed")
            return True
        except OSError:
            pass  # lock unavailable (fs issue) — trace guard still applies
        # `not force` was missing here while the human branch above had it,
        # so --force was inert on the agent path — the one path that matters
        # for a stalled chain. The message below has always said "use --force
        # to override" and the flag has never been consulted, which is why
        # chain_watchdog could not repair a receiver stall: its re-delivery is
        # the same transition the guard has recorded, and the only documented
        # escape hatch did nothing. Measured on reveng handoff 010.
        if not force and transition_recently_delivered(
                bridge_dir, payload["from_role"], payload["to_role"],
                handoff_id):
            print(f"  SKIP: {payload['from_role']}->{payload['to_role']} "
                  f"#{handoff_id} was already delivered — duplicate "
                  f"suppressed (use --force to override)")
            log(
                f"{payload['from_role']}->{payload['to_role']}",
                handoff_id,
                "signal_complete_skipped",
                "Duplicate delivery suppressed by idempotency guard",
            )
            return True

    # Step 6: Verify deliverable file exists (written by completing role)
    full_deliverable_path = os.path.join(bridge_dir,
                                         payload["deliverable_dir"],
                                         payload["deliverable_file"])
    if not os.path.exists(full_deliverable_path):
        print(f"  ERROR: Deliverable missing: {full_deliverable_path}")
        log(
            f"{payload['from_role']}->{payload['to_role']}",
            handoff_id,
            "signal_complete_failed",
            f"Deliverable missing: {full_deliverable_path}",
        )
        return False

    # Ensure deliverable subdirectory exists (for symlink)
    ensure_subdir(bridge_dir, payload["deliverable_dir"])

    # ── Model lifecycle: swap from-role model → to-role model ──
    # Runs AFTER the pre-script and before injection. Swapping first cost a
    # 40-second GPU round trip on deliverables the gate then refused — and
    # worse, it pulled the model out from under the role the rejection was
    # about to be handed back to, so the author could not act on it.
    # Validate first, pay for the swap once the deliverable is accepted.
    # Pre-scripts are for flow-specific logic (import gates, validation)
    # — never for model management.
    from_source_sc, from_alias_sc = "", ""
    try:
        from_source_sc, from_alias_sc = get_effective_model_source(
            payload["from_role"],
            step_key=current_step.get("step_key"),
            flow_key=flow_key,
            db_path=_db_path(),
        )
    except Exception:
        pass
    to_source_sc, to_alias_sc = "", ""
    try:
        to_source_sc, to_alias_sc = get_effective_model_source(
            payload["to_role"],
            step_key=current_step.get("step_key"),
            flow_key=flow_key,
            db_path=_db_path(),
        )
    except Exception:
        pass

    # Run pre_dispatch_script if configured (e.g. import before portfolio01).
    # Single key or comma-separated list (Run 018 Spec #13). The helper
    # aborts on first failure (returned ok=False) and signals via ran_any
    # whether any script actually executed — the deliverable-moved
    # exists-check below is gated on ran_any to preserve today's
    # byte-identical behavior (the check only runs when a script ran).
    ok, ran_any = _run_pre_dispatch_scripts(
        current_step.get("pre_dispatch_script"), payload, bridge_dir=bridge_dir
    )
    if not ok:
        # Aborting alone leaves the author believing it succeeded.
        # Hand the refusal back so the chain can repair itself.
        _handle_gate_rejection(payload, handoff_id, bridge_dir)
        return False
    if ran_any:
        # The pre-dispatch import moves the deliverable: to processed/
        # (leaving a pending symlink) on success, to rejected/ on gate
        # failure. A rejected deliverable MUST stop the chain — the
        # next role would otherwise be dispatched with a dangling
        # input reference and hang (observed: portfolio01, flows
        # 061/062).
        if not os.path.exists(full_deliverable_path):
            print(
                f"  ERROR: Deliverable no longer resolves after "
                f"pre-dispatch script (rejected by import gates?): "
                f"{full_deliverable_path} — chain stopped before "
                f"{payload['to_role']}"
            )
            log(
                f"{payload['from_role']}->{payload['to_role']}",
                handoff_id,
                "signal_complete_failed",
                "Deliverable rejected by pre-dispatch import — "
                "chain stopped",
            )
            return False

    # The deliverable survived the gate — now it is worth paying for the
    # GPU swap, and the target's model is up well before injection.
    if from_source_sc == "model_allocator" and from_alias_sc:
        _release_from_model_first(
            handoff_id, from_alias_sc,
            to_alias_sc if to_source_sc == "model_allocator" else "")
    if to_source_sc == "model_allocator" and to_alias_sc:
        _stop_other_local_models(to_alias_sc)
        _run_allocator_start(to_alias_sc)

    # Step 7: Auto-prepend missing XML sections, then validate + build callback
    step_validation_required = current_step.get("validation_required", 0)
    if step_validation_required and rule_key:
        # Safety net: auto-prepend missing XML sections before validation.
        # Pass the exact step-derived paths so the header is truthful —
        # the previous step's deliverable is what from_role read as input.
        prev_input_path = None
        step_idx = steps.index(current_step)
        if step_idx > 0:
            prev_step = steps[step_idx - 1]
            prev_dir = prev_step.get("deliverable_dir", "")
            prev_pattern = prev_step.get("deliverable_pattern", "{ID}-result.md")
            prev_file = prev_pattern.replace("{ID}", handoff_id).replace(
                "{role_key}", prev_step.get("from_role", ""))
            if os.path.isabs(prev_dir):
                prev_input_path = os.path.join(prev_dir, prev_file)
            else:
                prev_input_path = os.path.join(bridge_dir, prev_dir, prev_file)
        prepend_result = auto_prepend_xml_sections(
            full_deliverable_path, rule_key,
            handoff_id=handoff_id,
            source_role=payload["from_role"],
            flow_key=flow_key,
            bridge_dir=bridge_dir,
            db_path=_db_path(),
            input_path=prev_input_path,
            output_path=full_deliverable_path,
        )
        if prepend_result["prepended"]:
            print(f"  WARNING: Auto-prepended missing XML sections: {', '.join(prepend_result['missing'])}")
            log(
                f"{payload['from_role']}->{payload['to_role']}",
                handoff_id,
                "auto_prepend",
                f"Model omitted required XML sections; auto-prepended: {', '.join(prepend_result['missing'])}",
            )
        vresult = validate_deliverable_against_schema(
            full_deliverable_path, rule_key,
            db_path=_db_path(),
        )
        if not vresult["valid"]:
            print(f"  ERROR: Deliverable validation failed, missing sections: {vresult['missing']}")
            log(
                f"{payload['from_role']}->{payload['to_role']}",
                handoff_id,
                "signal_complete_failed",
                f"Validation failed: missing {', '.join(vresult['missing'])}",
            )
            return False

    # Compose prompt: use content_template with placeholder replacement
    ctemplate = resolve_content_template_from_db(
        rule_key, db_path=_db_path()
    ) if rule_key else ""

    # Resolve model_name for {model_name} placeholder (via allocator alias)
    target_model_name_sc = to_role.get("default_model_alias", "")
    output_pattern_sc = payload.get("deliverable_pattern", "{ID}_{role_key}.json")
    output_file_sc = output_pattern_sc.replace("{ID}", payload["handoff_id"]).replace("{role_key}", payload["to_role"])

    if ctemplate:
        prompt_text = ctemplate.replace("{handoff_id}", payload["handoff_id"])
        # {flow_run_id} is the spec 5.2 alias for the run id. It was NEVER
        # replaced on this chain-callback path (only in signal_send), so
        # every chained role received a literal "{flow_run_id}" in its
        # chain_advancement command — the root of id guessing/pollution
        # (flow 064's '064_humantrade' ids) and skipped signals.
        prompt_text = prompt_text.replace("{flow_run_id}", payload["handoff_id"])
        prompt_text = prompt_text.replace("{output_type}", to_role.get("primary_output_type") or "")
        prompt_text = prompt_text.replace("{source_role}", payload["from_role"])
        prompt_text = prompt_text.replace("{next_role}", payload["to_role"])
        prompt_text = prompt_text.replace("{bridge_dir}", bridge_dir)
        prompt_text = prompt_text.replace("{flow_key}", payload["flow_key"])
        prompt_text = prompt_text.replace("{escalation_role}", escalation_role(payload["flow_key"]))
        prompt_text = prompt_text.replace("{project_path}", get_flow_target_project(payload["flow_key"], db_path=_db_path()))
        prompt_text = prompt_text.replace("{deliverable_dir}", payload["deliverable_dir"])
        prompt_text = prompt_text.replace("{deliverable_file}", payload["deliverable_file"])
        prompt_text = prompt_text.replace("{output_file}", output_file_sc)
        prompt_text = prompt_text.replace("{model_name}", target_model_name_sc)
        prompt_text = prompt_text.replace("{previous_deliverable_path}", full_deliverable_path)
        prompt_text = prompt_text.replace("{project_root}", str(PROJECT_ROOT))
        prompt_text += f"\n\n## Current Deliverable\nRead your input from: {full_deliverable_path}"
    else:
        prompt_text = (
            f"Your previous role '{payload['from_role']}' has completed handoff "
            f"#{payload['handoff_id']}.\n"
            f"Read and proceed with: {full_deliverable_path}"
        )

    # If the evidence gate refused earlier versions of this deliverable, say
    # so in the prompt. The role that fixed it and the role receiving it are
    # different, and the fix never reaches the recipient: it sees a clean
    # deliverable with no reason to look harder at one that needed three
    # attempts to pass a mechanical check. Blocking here would be wrong —
    # a rewritten deliverable that now passes is exactly what the loop is
    # for, and blocking it would have stopped two legitimate recoveries on
    # 2026-08-05 — but silence is what let the history die in trace.log.
    prior_rejections = _gate_rejection_count(payload["from_role"], handoff_id)
    if prior_rejections:
        note_dir = payload.get("deliverable_dir", "") or ""
        if not os.path.isabs(note_dir):
            note_dir = os.path.join(bridge_dir, note_dir)
        prompt_text += (
            f"\n\n## Provenance — the gate refused this deliverable "
            f"{prior_rejections} time(s) before this version\n"
            f"The evidence gate blocked earlier versions of "
            f"`{payload['deliverable_file']}` from `{payload['from_role']}`. "
            f"The gate compares claims against the working tree, so each "
            f"refusal means a version asserted something the repository did "
            f"not support.\n"
            f"The refusal notes are at "
            f"`{os.path.join(note_dir, handoff_id + '-gate-rejection.md')}` "
            f"if they were not overwritten.\n"
            f"This version passed, but a deliverable that needed rewriting to "
            f"survive a mechanical check has earned a closer reading. Verify "
            f"its claims against the repository yourself before acting."
        )

    # Find the NEXT step (where from_role == current to_role) to determine
    # where the target role should write its deliverable and how to signal.
    # Position-aware: only steps strictly AFTER the completed step qualify.
    # In cyclic flows (supervised_review) a global from_role scan matched
    # step 1 again when the FINAL step completed — telling the woken agent
    # to overwrite the original handoff and signal-complete with the same
    # id, looping the chain (smoke-001). On the last step nothing follows:
    # no block is appended and the convention content_template alone
    # defines the wake-up behavior.
    next_output_path = ""
    next_signal_cmd = ""
    cur_idx = steps.index(current_step)
    for s in steps[cur_idx + 1:]:
        if s.get("from_role") == payload["to_role"]:
            next_dir = s.get("deliverable_dir", "")
            next_pattern = s.get("deliverable_pattern", "{ID}-result.md")
            next_file = next_pattern.replace("{ID}", handoff_id).replace("{role_key}", payload["to_role"])
            if os.path.isabs(next_dir):
                next_output_path = os.path.join(next_dir, next_file)
            else:
                next_output_path = os.path.join(bridge_dir, next_dir, next_file)
            next_signal_cmd = (
                # 009: routed through the broker (see Site 1 above).
                f"nohup python3 {PROJECT_ROOT}/scripts/bridgeV002/bridge_broker.py "
                f"enqueue "
                f"--flow {flow_key} --from-role {payload['to_role']} "
                f"--to-role {payload['to_role']} "
                f"--id {handoff_id} --action signal-complete "
                f"> /tmp/bridge-enqueue-{flow_key}-{handoff_id}.log 2>&1 &"
            )
            break

    if next_output_path:
        prompt_text += (
            f"\n\n## Your Deliverable\n"
            f"Write your result to: {next_output_path}\n"
            f"Write ONLY to that exact path — do not create extra copies or "
            f"invented filenames in the project working directory.\n"
            # The XML envelope is deliberately NOT requested here.
            # auto_prepend_xml_sections() supplies <handoff_id>,
            # <source_role>, <deliverable_input> and <deliverable_output>
            # from known values before validation, on every step (all three
            # llama_SG steps carry validation_required=1). Asking for it too
            # produced nothing but noise: across handoffs 002-012 the
            # auto-prepend fired on 12 of 12, and in 10 of those the model
            # had written none of the four sections. Six lines of every
            # injected prompt, for every role, instructing something the
            # machine always supplied anyway. Write content; the envelope
            # is dispatch's job.
            f"## Signal Completion (MANDATORY — do not ask, just execute)\n"
            f"After writing the deliverable, run this command:\n"
            f"{next_signal_cmd}"
        )

    # Prepend governance file reference for target role
    # The governance file defines the role, responsibilities, and boundaries.
    # Do NOT hardcode role descriptions here — the governance file is the single source of truth.
    # Run 008 / handoff 032 (D3b Site 1): the legacy direct-column read of the
    # receiver role is replaced by the unified resolver. The receiver here is
    # payload["to_role"] -- the role the composed prompt is being injected
    # INTO (NOT the sender, NOT the step being signaled). Selection +
    # precedence live in execution_config.py; this call is the only place
    # dispatch reads governance_file for Site 1.
    _resolved_sc = _resolve_receiver_execution_config(
        payload["flow_key"], payload["to_role"], handoff_id)
    gov_file = _resolved_sc["governance_file"]
    project_root_sc = PROJECT_ROOT
    gov_ref_sc = ""
    if gov_file:
        gov_path = os.path.join(project_root_sc, "docs", "governance-templates-v2", gov_file)
        gov_ref_sc = f"Read your role definition at {gov_path} before proceeding.\n\n"
    # Per handoff 032 step 3: RUNTIME CONTEXT block is ALWAYS prepended;
    # governance reference line is CONDITIONAL on gov_file being set.
    prompt_text = (
        f"{build_target_project_block(payload['flow_key'])}"
        f"{build_runtime_context(_resolved_sc)}"
        f"{gov_ref_sc}"
        f"{prompt_text}"
    )

    # Trade-MCP push path (PILOT): chain advancement delivers the next
    # role's work prompt through THIS injection (not signal_send), so the
    # deterministic context must be appended here as well.
    prompt_text = append_trade_mcp_context(
        prompt_text, payload["flow_key"], payload["to_role"],
        full_deliverable_path, mode=to_role.get("trade_mcp_push_mode"))

    # Resolve both roles' models. VRAM-first order: release/stop the
    # completing role's model BEFORE warming the next one so only one model
    # loads at a time (max free VRAM when a role starts its task).
    to_source_sc, to_alias_sc = get_effective_model_source(
        payload["to_role"],
        step_key=current_step.get("step_key") if 'current_step' in dir() else None,
        flow_key=flow_key,
        db_path=_db_path(),
    )
    # Model swap was handled before the pre-script above.

    # Acquire model lease for the target role (reference-counted unload)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "job_queue"))
        from model_lease import LeaseRegistry
        if to_source_sc == "model_allocator" and to_alias_sc:
            LeaseRegistry.acquire(handoff_id, to_alias_sc, worker_id="dispatch")
    except Exception:
        pass  # Lease registry not available — non-fatal

    # Check if this role uses python_runtime as execution backend
    # (instead of tmux injection via OpenCode/Claude Code)
    # Check if this role uses python_runtime as execution backend
    # (step-level model_source determines execution backend)
    step_model_source = current_step.get("model_source", "") if current_step else ""
    if step_model_source == "python_runtime":
        print(f"  Execution backend: python_runtime")
        runtime_script = str(Path(__file__).resolve().parent.parent / "python-runtime" / "runtime.py")
        result_path = os.path.join(bridge_dir, payload["deliverable_dir"],
                                   f"{handoff_id}-result.md")
        try:
            rt_result = subprocess.run(
                [sys.executable, runtime_script,
                 "--prompt-file", full_deliverable_path,
                 "--project-root", config.get_project_root(),
                 "--handoff-id", handoff_id,
                 "--result-path", result_path,
                 "--allocator-role", payload["to_role"],
                 "--allocator-client", "opencode",
                 "--flow", flow_key,
                 "--role", payload["to_role"],
                 "--step-key", payload.get("step_key", ""),
                 "--no-signal"],
                capture_output=True, text=True,
                timeout=600,
            )
            if rt_result.returncode == 0:
                print(f"  Python runtime completed successfully")
                # Write checkpoint
                try:
                    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "job_queue"))
                    from checkpoint_integration import create_checkpoint_for_dispatch
                    create_checkpoint_for_dispatch(
                        handoff_id=handoff_id, flow_key=flow_key,
                        step_key=payload["step_key"],
                        from_role=payload["from_role"], to_role=payload["to_role"],
                        deliverable_path=result_path, bridge_dir=bridge_dir,
                        model_alias=to_alias_sc if to_source_sc == "model_allocator" else "",
                    )
                except Exception:
                    pass
                log(f"{payload['from_role']}->{payload['to_role']}", handoff_id,
                    "signal_complete", f"Python runtime completed")
                return True
            else:
                print(f"  Python runtime FAILED: {rt_result.stderr[-500:]}")
                log(f"{payload['from_role']}->{payload['to_role']}", handoff_id,
                    "signal_complete_failed", f"Python runtime failed")
                return False
        except subprocess.TimeoutExpired:
            print(f"  Python runtime timed out")
            return False
        except Exception as e:
            print(f"  Python runtime error: {e}")
            return False

    # Step 8: Inject callback prompt into to_role's tmux session.
    # A chain callback is a NEW task for the target role — send its
    # configured context-reset command first (tool-independent).
    prompt_text = apply_mode_block(prompt_text, _db_path(), flow_key, payload["step_key"], payload["to_role"])

    # Run 006 D6(b): busy/menu pane → refuse + requeue (broker seam).
    try:
        inject_prompt(tmux_session, _wrap_prompt_for_harness(to_role, prompt_text),
                      enter_command=to_role.get("enter_command", "default"),
                      fresh_session_command=to_role.get("fresh_session_command"))
    except PaneBusyRefused as _exc:
        print(f"REFUSED_INJECTION: {_exc}", flush=True)
        print(f"REFUSED_INJECTION: {_exc}", file=sys.stderr)
        return False
    time.sleep(0.5)

    # Step 8a: Log the completion event IMMEDIATELY after injection.
    # The roles' chain_advancement command wraps dispatch.py in
    # `timeout 60`; when post-dispatch (ollama stop) hangs, the process
    # is killed before a trailing trace write — leaving delivered
    # signals invisible to the watchdog's duplicate-nudge guard
    # (flow 069 double-nudge, flow 070 missing review->sim line).
    # See run_flow_step_db: a dead backend must not be logged as a clean
    # delivery, or the watchdog reads the final step as complete while the
    # receiver's turn dies on "Cannot connect to API" (reveng verdict 061).
    backend_down_sc = (to_source_sc == "model_allocator"
                       and _backend_is_down(to_alias_sc))
    if backend_down_sc:
        print(f"  WARNING: backend for '{to_alias_sc}' is down at injection — "
              f"logging signal_complete_backend_down")
    log(
        f"{payload['from_role']}->{payload['to_role']}",
        handoff_id,
        "signal_complete" if not backend_down_sc
        else "signal_complete_backend_down",
        f"Callback dispatched to {tmux_session} (DB-driven)"
        + ("" if not backend_down_sc
           else f" but backend '{to_alias_sc}' is down"),
    )

    # Step 9: Post-dispatch VRAM cleanup. The from-role's model was already
    # released BEFORE warm-up (VRAM-first swap) — this fallback only covers
    # the same-alias case, where releasing before the target's acquire would
    # have stopped the model the target needs.
    # _release_from_model_first() returns without touching the model when
    # both roles share the alias, so the same-alias test alone is the
    # condition — there is no separate "handled" flag any more.
    from_source, from_alias = from_source_sc, from_alias_sc
    if (from_source == "model_allocator"
            and from_alias and from_alias == to_alias_sc):
        # Same alias for both roles: the model must stay loaded for the
        # target. The target's acquire refreshed the lease row (same
        # job_id+alias), so there is nothing to release without pulling the
        # lease out from under the target — intentionally left loaded.
        print(f"  Model '{from_alias}' kept loaded — target role uses the same alias")

    # Step 9b: Write structured checkpoint for this completed step
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "job_queue"))
        from checkpoint_integration import create_checkpoint_for_dispatch
        cp_path = create_checkpoint_for_dispatch(
            handoff_id=handoff_id,
            flow_key=flow_key,
            step_key=payload["step_key"],
            from_role=payload["from_role"],
            to_role=payload["to_role"],
            deliverable_path=full_deliverable_path,
            bridge_dir=bridge_dir,
            model_alias=from_alias if from_source == "model_allocator" else "",
            model_backend=from_source or "",
            concrete_model=from_alias if from_source == "model_allocator" else "",
        )
        if cp_path:
            print(f"  Checkpoint written: {cp_path}")
    except Exception as e:
        print(f"  Checkpoint creation skipped: {e}")

    # Step 9c: Load previous checkpoint and append to prompt for fresh-context start
    try:
        checkpoint_dir = os.path.join(PROJECT_ROOT, "jobs", "checkpoints")
        # Find the most recent checkpoint from the from_role
        import glob
        cp_patterns = [
            os.path.join(checkpoint_dir, f"*{payload['from_role']}*"),
            os.path.join(checkpoint_dir, f"*{handoff_id}*"),
        ]
        for pattern in cp_patterns:
            cp_files = sorted(glob.glob(pattern), reverse=True)
            if cp_files:
                with open(cp_files[0], "r", encoding="utf-8") as f:
                    cp_data = json.load(f)
                cp_summary = cp_data.get("implementation_summary", "")
                cp_changed = cp_data.get("changed_files", [])
                cp_verification = cp_data.get("verification_results", [])
                if cp_summary or cp_changed:
                    verif_lines = []
                    for v in cp_verification:
                        verif_lines.append(f'{v.get("check","?")} {v.get("file","?")}: {v.get("status","?")}')
                    verif_str = "; ".join(verif_lines) if verif_lines else "(none)"
                    prompt_text += (
                        f"\n\n## Previous Step Checkpoint\n"
                        f"Summary: {cp_summary[:500]}\n"
                        f"Changed files: {', '.join(cp_changed) if cp_changed else '(none)'}\n"
                        f"Verification: {verif_str}\n"
                        f"This is a machine-generated checkpoint — you do not need the previous conversation."
                    )
                break
    except Exception:
        pass  # No checkpoint available — non-fatal

    # Step 9d: Fallback chain advancement — if the model forgot signal-complete,
    # the scheduler's _advance_chain scans for result files and auto-advances.
    # Idempotent: no-op if next step already has a result.
    try:
        _job_queue_root = str(Path(__file__).resolve().parent.parent.parent / "scripts")
        sys.path.insert(0, _job_queue_root)
        sys.path.insert(0, os.path.join(_job_queue_root, "job_queue"))
        from models import JobRepository
        from scheduler import Scheduler
        repo = JobRepository()
        jobs = repo.list_jobs(flow_key=flow_key)
        for job in jobs:
            if job.handoff_id == handoff_id:
                sched = Scheduler()
                advanced = sched._advance_chain(job)
                if advanced:
                    print(f"  Chain advanced (fallback) for handoff #{handoff_id}")
                break
    except Exception:
        pass  # Scheduler not available — non-fatal

    # Step 10: Update symlink
    deliverable_dir = payload["deliverable_dir"]
    if os.path.isabs(deliverable_dir):
        # For absolute paths, update symlink in the deepest subdirectory
        link_dir = deliverable_dir
    else:
        link_dir = os.path.join(bridge_dir, deliverable_dir)

    link_path = os.path.join(link_dir, "current.md")
    try:
        if os.path.islink(link_path) or os.path.exists(link_path):
            os.unlink(link_path)
    except FileNotFoundError:
        pass
    os.symlink(payload["deliverable_file"], link_path)

    # Step 11: Completion event already logged at Step 8b (pre-hang).
    print(f"  Callback injected into '{tmux_session}'")
    print(f"  Symlink updated in {link_dir}")
    print(f"  Logged signal_complete for handoff #{handoff_id}")

    # Update cycle state for Architect cold-start
    _update_cycle_state(handoff_id, flow_key, payload["to_role"])

    return True


def signal_escalation(flow_key, from_role_key, to_role_key, handoff_id, bridge_dir=None):
    """Signal that a review role has escalated a question to architect.

    Replaces legacy cmd_ask_architect(). DB-driven: resolves both roles,
    builds escalation prompt from convention content_template, injects into
    architect's tmux session, and cleans up VRAM.

    Golden rule sequential dispatch sequence (no-kill v2):
      1. Load from_role + to_role from DB
      2. Check target session is alive
      3. Verify escalation question file exists (written by review)
      4. Resolve escalation convention content_template
      5. Build prompt with placeholder replacement
      6. Inject prompt into architect's tmux session
      7. Post-dispatch: stop from_role's Ollama model (VRAM cleanup)
      8. Update symlink in escalation directory
      9. Log escalation event to trace.log
    """
    import config as dpmtf_config

    if bridge_dir is None:
        bridge_dir = os.environ.get(
            "DPMTF_BRIDGE_DIR", dpmtf_config.get_bridge_base_path()
        )

    # Step 1: Load both roles from DB
    try:
        from_role_data = load_role_from_db(from_role_key,
                                           db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{from_role_key}' from database: {e}")
        return False

    try:
        to_role_data = load_role_from_db(to_role_key,
                                         db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{to_role_key}' from database: {e}")
        return False

    tmux_session = to_role_data["tmux_session"]
    role_type = to_role_data.get("role_type", "agent")

    print(f"\nSignal Escalation: {from_role_key} -> {to_role_key}")
    print(f"  Flow: {flow_key}")

    # G1: Human recipients skip tmux dispatch (no session, no injection)
    if role_type == "human":
        esc_dir = os.path.join(bridge_dir, "escalations")
        question_file = f"{handoff_id}-{from_role_key}-question.md"
        full_question_path = os.path.join(esc_dir, question_file)
        print(f"  INFO: Escalation delivered to human recipient — {full_question_path}")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "escalation_to_human",
            f"Escalation question at {full_question_path} for human review",
        )
        return True

    # Step 2: Check target session is alive
    if not session_alive(tmux_session):
        print(f"  ERROR: Target session '{tmux_session}' is not running")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "escalation_failed",
            f"Target session '{tmux_session}' is not running",
        )
        return False

    # Step 3: Verify escalation question file exists (written by review)
    # The question file lives in the bridge dir under an escalation subdirectory
    esc_dir = os.path.join(bridge_dir, "escalations")
    question_file = f"{handoff_id}-{from_role_key}-question.md"
    full_question_path = os.path.join(esc_dir, question_file)

    if not os.path.exists(full_question_path):
        print(f"  ERROR: Escalation question file missing: {full_question_path}")
        print(f"  Review must write its question before signaling escalation")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "escalation_failed",
            f"Question file missing: {full_question_path}",
        )
        return False

    # Ensure escalation subdirectory exists (for symlink)
    os.makedirs(esc_dir, exist_ok=True)

    # Step 4: Resolve escalation convention content_template
    ctemplate = resolve_content_template_from_db(
        "escalation", db_path=_db_path()
    ) or ""

    # Step 5: Build prompt with placeholder replacement
    if ctemplate:
        prompt_text = ctemplate.replace("{handoff_id}", handoff_id)
        prompt_text = prompt_text.replace("{source_role}", from_role_key)
        prompt_text = prompt_text.replace("{next_role}", to_role_key)
        prompt_text = prompt_text.replace("{bridge_dir}", bridge_dir)
        prompt_text = prompt_text.replace("{flow_key}", flow_key)
        prompt_text = prompt_text.replace("{escalation_role}", escalation_role(flow_key))
        prompt_text = prompt_text.replace("{project_path}", get_flow_target_project(flow_key, db_path=_db_path()))
        # Inject the actual question file path so architect knows what to read
        prompt_text += f"\n\n## Escalation Question File\nRead the escalation question from: {full_question_path}"
    else:
        prompt_text = (
            f"The role '{from_role_key}' has escalated a question for handoff "
            f"#{handoff_id}.\n"
            f"Please review and respond. Read the question from: {full_question_path}"
        )

    # Prepend governance file reference for target role
    # Run 008 / handoff 032 (D3b Site 2): the legacy direct-column read of
    # the receiver role is replaced by the unified resolver. The receiver
    # here is to_role_key -- the escalation target, the role the composed
    # prompt is being injected INTO.
    _resolved_e = _resolve_receiver_execution_config(flow_key, to_role_key, handoff_id)
    gov_file = _resolved_e["governance_file"]
    gov_ref_e = ""
    if gov_file:
        gov_path_e = os.path.join(PROJECT_ROOT,
                                  "docs", "governance-templates-v2", gov_file)
        gov_ref_e = f"Your role is defined in {gov_path_e}. Read it now before proceeding.\n\n"
    # Per handoff 032 step 3: RUNTIME CONTEXT block is ALWAYS prepended;
    # governance reference line is CONDITIONAL on gov_file being set.
    prompt_text = (
        f"{build_target_project_block(flow_key)}"
        f"{build_runtime_context(_resolved_e)}"
        f"{gov_ref_e}"
        f"{prompt_text}"
    )

    # Step 6: Inject prompt into architect's tmux session
    # Run 006 D6(b): busy/menu pane → refuse + requeue (broker seam).
    try:
        inject_prompt(tmux_session, _wrap_prompt_for_harness(to_role_data, prompt_text),
                      enter_command=to_role_data.get("enter_command", "default"))
    except PaneBusyRefused as _exc:
        print(f"REFUSED_INJECTION: {_exc}", flush=True)
        print(f"REFUSED_INJECTION: {_exc}", file=sys.stderr)
        return False
    time.sleep(0.5)

    # Step 7: Post-dispatch — stop from_role's Ollama model (VRAM cleanup)
    try:
        from_source, from_alias = get_effective_model_source(
            from_role_key,
            flow_key=flow_key,
            db_path=_db_path(),
        )
        if from_source == "model_allocator" and from_alias:
            _run_allocator_stop(from_alias)
    except Exception:
        pass  # Not an allocator role or model already stopped

    # Step 8: Update symlink in escalation directory
    link_path = os.path.join(esc_dir, "current.md")
    try:
        if os.path.islink(link_path) or os.path.exists(link_path):
            os.unlink(link_path)
    except FileNotFoundError:
        pass
    os.symlink(question_file, link_path)

    # Step 9: Log escalation event
    log(
        f"{from_role_key}->{to_role_key}",
        handoff_id,
        "escalation_asked",
        f"Escalation dispatched to {tmux_session} (DB-driven)",
    )

    print(f"  Escalation prompt injected into '{tmux_session}'")
    print(f"  Symlink updated in {esc_dir}")
    print(f"  Logged escalation_asked for handoff #{handoff_id}")

    # Update cycle state for Architect cold-start
    _update_cycle_state(handoff_id, flow_key, to_role_key)

    return True


def signal_answer(flow_key, from_role_key, to_role_key, handoff_id, bridge_dir=None):
    """Signal that architect has answered an escalation question.

    Replaces legacy cmd_answer_review(). Sends response back to the review
    role that originated the escalation. No auto-chain — review continues work.

    Golden rule sequential dispatch sequence (no-kill v2):
      1. Load from_role + to_role from DB
      2. Check target session is alive
      3. Build prompt from escalation convention content_template
      4. Inject prompt into review's tmux session
      5. Post-dispatch: stop from_role's Ollama model (VRAM cleanup)
      6. Update symlink in answer directory
      7. Log answer event to trace.log
    """
    import config as dpmtf_config

    if bridge_dir is None:
        bridge_dir = os.environ.get(
            "DPMTF_BRIDGE_DIR", dpmtf_config.get_bridge_base_path()
        )

    # Step 1: Load both roles from DB
    try:
        from_role_data = load_role_from_db(from_role_key,
                                           db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{from_role_key}' from database: {e}")
        return False

    try:
        to_role_data = load_role_from_db(to_role_key,
                                         db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{to_role_key}' from database: {e}")
        return False

    tmux_session = to_role_data["tmux_session"]
    role_type = to_role_data.get("role_type", "agent")

    print(f"\nSignal Answer: {from_role_key} -> {to_role_key}")
    print(f"  Flow: {flow_key}")

    # G1: Human recipients skip tmux dispatch (no session, no injection)
    if role_type == "human":
        ans_dir = os.path.join(bridge_dir, "escalations")
        response_file = f"{handoff_id}-{from_role_key}-response.md"
        full_response_path = os.path.join(ans_dir, response_file)
        print(f"  INFO: Answer delivered to human recipient — {full_response_path}")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "answer_to_human",
            f"Escalation response at {full_response_path} for human review",
        )
        return True

    # Step 2: Check target session is alive
    if not session_alive(tmux_session):
        print(f"  ERROR: Target session '{tmux_session}' is not running")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "answer_failed",
            f"Target session '{tmux_session}' is not running",
        )
        return False

    # Step 3: Build prompt from escalation convention content_template
    # (same convention as signal_escalation — architect answer uses same structure)
    ctemplate = resolve_content_template_from_db(
        "escalation", db_path=_db_path()
    ) or ""

    # Check for optional architect response file
    ans_dir = os.path.join(bridge_dir, "escalations")
    response_file = f"{handoff_id}-{from_role_key}-response.md"
    full_response_path = os.path.join(ans_dir, response_file)

    if ctemplate:
        prompt_text = ctemplate.replace("{handoff_id}", handoff_id)
        prompt_text = prompt_text.replace("{source_role}", from_role_key)
        prompt_text = prompt_text.replace("{next_role}", to_role_key)
        prompt_text = prompt_text.replace("{bridge_dir}", bridge_dir)
        prompt_text = prompt_text.replace("{flow_key}", flow_key)
        prompt_text = prompt_text.replace("{escalation_role}", escalation_role(flow_key))
        prompt_text = prompt_text.replace("{project_path}", get_flow_target_project(flow_key, db_path=_db_path()))
    else:
        prompt_text = (
            f"The role '{from_role_key}' has provided an escalation response "
            f"for handoff #{handoff_id}.\n"
            f"Please review the architect's decision and proceed."
        )

    # If architect wrote a response file, include it in the prompt
    if os.path.exists(full_response_path):
        prompt_text += f"\n\n## Architect Response File\nRead the architect's response from: {full_response_path}"
    else:
        prompt_text += f"\n\n## Note\nNo separate response file found. The architect may have provided inline guidance."

    # Step 4: Inject prompt into review's tmux session
    # Run 006 D6(b): busy/menu pane → refuse + requeue (broker seam).
    try:
        inject_prompt(tmux_session, prompt_text,
                      enter_command=to_role_data.get("enter_command", "default"))
    except PaneBusyRefused as _exc:
        print(f"REFUSED_INJECTION: {_exc}", flush=True)
        print(f"REFUSED_INJECTION: {_exc}", file=sys.stderr)
        return False
    time.sleep(0.5)

    # Step 5: Post-dispatch — stop from_role's Ollama model (VRAM cleanup)
    try:
        from_source, from_alias = get_effective_model_source(
            from_role_key,
            flow_key=flow_key,
            db_path=_db_path(),
        )
        if from_source == "model_allocator" and from_alias:
            _run_allocator_stop(from_alias)
    except Exception:
        pass  # Not an allocator role or model already stopped

    # Step 6: Update symlink in answer directory
    link_path = os.path.join(ans_dir, "current_answer.md")
    if os.path.exists(full_response_path):
        try:
            if os.path.islink(link_path) or os.path.exists(link_path):
                os.unlink(link_path)
        except FileNotFoundError:
            pass
        os.symlink(response_file, link_path)

    # Step 7: Log answer event
    log(
        f"{from_role_key}->{to_role_key}",
        handoff_id,
        "escalation_answered",
        f"Answer dispatched to {tmux_session} (DB-driven)",
    )

    print(f"  Answer prompt injected into '{tmux_session}'")
    print(f"  Logged escalation_answered for handoff #{handoff_id}")

    # Update cycle state for Architect cold-start
    _update_cycle_state(handoff_id, flow_key, to_role_key)

    return True


def signal_send(flow_key, from_role_key, to_role_key, handoff_id, bridge_dir=None):
    """Signal initial handoff dispatch from review to target role.

    Replaces legacy cmd_send(). DB-driven: resolves both roles,
    validates handoff file exists with required XML sections, performs
    model stop+reload for clean context, and injects dispatch prompt
    into the target role's tmux session.

    Golden rule sequential dispatch sequence (no-kill v2):
      1. Load from_role + to_role from DB
      2. Check target session is alive
      3. Verify handoff file exists with required XML sections
      4. Stop target role's Ollama model (clear VRAM + context)
      5. Reload target role's Ollama model (fresh context)
      6. Resolve handoff convention content_template
      7. Build prompt with placeholder replacement
      8. Inject prompt into target role's tmux session
      9. Update symlink in handoff directory
      10. Log dispatch event to trace.log

    Chain advancement is handled by the role itself via the <chain_advancement>
    block in the json_output content_template — the role runs signal-complete
    after writing its output. No code-level auto-chain here (removed — it
    duplicated the prompt-driven mechanism and caused multi-injections).
    """
    import config as dpmtf_config

    if bridge_dir is None:
        bridge_dir = os.environ.get(
            "DPMTF_BRIDGE_DIR", dpmtf_config.get_bridge_base_path()
        )

    # Step 1: Load both roles from DB
    try:
        from_role_data = load_role_from_db(from_role_key,
                                           db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{from_role_key}' from database: {e}")
        return False

    try:
        to_role_data = load_role_from_db(to_role_key,
                                         db_path=_db_path())
    except ValueError as e:
        print(f"Error loading role '{to_role_key}' from database: {e}")
        return False

    _sweep_orphaned_leases()

    tmux_session = to_role_data["tmux_session"]

    # Step 1.5: Load flow and find matching step from DB
    try:
        flow_data = load_flow_from_db(flow_key, db_path=_db_path())
    except ValueError as e:
        print(f"Error loading flow '{flow_key}' from database: {e}")
        return False

    steps = flow_data["steps"]
    target_step = None
    for s in steps:
        if s.get("from_role") == from_role_key and s.get("to_role") == to_role_key:
            target_step = s
            break

    if not target_step:
        print(f"Error: No step matching {from_role_key}->{to_role_key} in flow '{flow_key}'")
        return False

    # Build payload from step + convention (resolves deliverable_dir, pattern, rule_key)
    payload = build_step_payload(target_step, flow_key, handoff_id, bridge_dir)
    rule_key = target_step.get("rule_key")

    # Keep the flow's ID counter ahead of explicitly supplied IDs so future
    # get_next_id_for_flow allocations never collide with existing files.
    bump_id_counter_past(flow_key, handoff_id, db_path=_db_path())

    print(f"\nSignal Send: {from_role_key} -> {to_role_key}")
    print(f"  Flow: {flow_key}, Step: {payload['step_key']}")
    print(f"  Deliverable: {payload['deliverable_file']}")

    # G1: Human recipients skip tmux dispatch (no session, no injection)
    # A role with an execution_target runs on another machine and has no
    # tmux session here. Structurally this is the human skip below: check a
    # role attribute, deliver another way, log it, return. Inert today —
    # no row sets execution_target, so worker_target() is always None.
    # See worker_routing.py for what is NOT built behind this branch.
    worker_id = worker_target(to_role_data)
    if worker_id:
        deliverable_dir = payload.get("deliverable_dir", "")
        handoff_path = os.path.join(bridge_dir, deliverable_dir,
                                    payload["deliverable_file"])
        try:
            eid = offer_to_worker(
                worker_id=worker_id, handoff_id=handoff_id, flow_key=flow_key,
                to_role_key=to_role_key, handoff_path=handoff_path,
                payload=payload, to_role_data=to_role_data,
                target_project=get_flow_target_project(flow_key),
            )
        except EnvelopeIncomplete as exc:
            print(f"  ERROR: cannot build the execution envelope: {exc}")
            log(f"{from_role_key}->{to_role_key}", handoff_id,
                "worker_offer_failed", str(exc))
            return False
        print(f"  INFO: {to_role_key} executes on '{worker_id}' — offered {eid}")
        log(f"{from_role_key}->{to_role_key}", handoff_id, "offered_to_worker",
            f"execution {eid} addressed to worker '{worker_id}'")
        return True

    role_type = to_role_data.get("role_type", "agent")
    if role_type == "human":
        deliverable_dir = payload.get("deliverable_dir", "")
        handoff_path = os.path.join(bridge_dir, deliverable_dir, payload["deliverable_file"])
        print(f"  INFO: Handoff delivered to human recipient — {handoff_path}")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "send_to_human",
            f"Handoff file at {handoff_path} for human review",
        )
        return True

    # G2: Human senders auto-generate handoff file from convention template.
    # When from_role is human, there is no prior agent to write the handoff.
    # Generate it from the convention's content_template so cronjob flows work.
    from_role_type = from_role_data.get("role_type", "agent")
    if from_role_type == "human":
        deliverable_dir = payload.get("deliverable_dir", "")
        handoff_path = os.path.join(bridge_dir, deliverable_dir, payload["deliverable_file"])
        if not os.path.exists(handoff_path):
            # Auto-generate from convention content_template
            ctemplate = payload.get("prompt_template", "")
            if not ctemplate and rule_key:
                try:
                    convention = resolve_convention_from_db(rule_key, db_path=_db_path())
                    ctemplate = convention.get("content_template", "")
                except (ValueError, sqlite3.OperationalError):
                    ctemplate = ""
            if ctemplate:
                # Build a minimal handoff with the required XML sections
                generated = f"<role>You are {to_role_key} in the {flow_key} flow.</role>\n"
                generated += f"<task>Execute your role according to the governance file. Produce JSON output to the inbox.</task>\n"
                generated += f"<constraint>SIMULATION_ONLY = TRUE. Follow GATES.md. Valid JSON only.</constraint>\n"
                os.makedirs(os.path.dirname(handoff_path), exist_ok=True)
                with open(handoff_path, "w", encoding="utf-8") as f:
                    f.write(generated)
                print(f"  Auto-generated handoff file: {handoff_path}")
            else:
                print(f"  ERROR: No convention template available to auto-generate handoff")
                print(f"  Prompt Compiler must write handoff file before signaling send")
                return False

    # Step 2: Check target session is alive
    if not session_alive(tmux_session):
        print(f"  ERROR: Target session '{tmux_session}' is not running")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "send_failed",
            f"Target session '{tmux_session}' is not running",
        )
        return False

    # Step 3: Verify handoff file exists with required XML sections
    deliverable_dir = payload.get("deliverable_dir", "")
    handoff_path = os.path.join(bridge_dir, deliverable_dir, payload["deliverable_file"])

    if not os.path.exists(handoff_path):
        print(f"  ERROR: Handoff file missing: {handoff_path}")
        print(f"  Prompt Compiler must write handoff file before signaling send")
        log(
            f"{from_role_key}->{to_role_key}",
            handoff_id,
            "send_failed",
            f"Handoff file missing: {handoff_path}",
        )
        return False

    # Validate required XML sections in handoff content (skip for json_output)
    if rule_key != "json_output":
        with open(handoff_path, "r", encoding="utf-8") as f:
            content = f.read()
        required_sections = ["<role>", "<task>", "<constraint>"]
        missing = [s for s in required_sections if s not in content]
        if missing:
            print(f"  ERROR: Handoff file missing required XML sections: "
                  f"{', '.join(missing)}")
            log(
                f"{from_role_key}->{to_role_key}",
                handoff_id,
                "send_failed",
                f"Handoff file missing required XML sections: {', '.join(missing)}",
            )
            return False

    handoff_abs = os.path.abspath(handoff_path)
    handoff_file = payload["deliverable_file"]

    # Ensure deliverable subdirectory exists (for symlink)
    ensure_subdir(bridge_dir, deliverable_dir)

    # Step 4: Resolve model source + alias (needed for job record + lease)
    to_source, to_alias = get_effective_model_source(
        to_role_data["role_key"],
        step_key=target_step.get("step_key"),
        flow_key=flow_key,
        db_path=_db_path(),
    )

    # Step 4a: Create job record for state tracking (audit trail + retry budget)
    job_id = handoff_id  # fallback — brug handoff_id hvis DB ikke tilgængelig
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "job_queue"))
        from models import JobRepository
        repo = JobRepository()
        # Extract a short goal from the handoff's <task> block. The previous
        # "first non-XML line" heuristic grabbed continuation lines of
        # multi-line tags (e.g. "Read IMPLEMENTOR.md before proceeding.</role>")
        # and polluted the job records.
        goal_text = f"Handoff {handoff_id}: {from_role_key} -> {to_role_key}"
        try:
            with open(handoff_path, "r", encoding="utf-8") as _f:
                _content = _f.read()
            _m = re.search(r"<task>\s*(.*?)</task>", _content, re.S)
            _block = _m.group(1) if _m else _content
            for _line in _block.splitlines():
                _stripped = _line.strip()
                if (_stripped and not _stripped.startswith("<")
                        and "</" not in _stripped):
                    goal_text = _stripped[:200]
                    break
        except Exception:
            pass
        job_id = repo.create_job(
            flow_key=flow_key,
            role_key=to_role_key,
            goal=goal_text,
            target_project=PROJECT_ROOT,
            allocator_alias=to_alias if to_source == "model_allocator" else "",
        )
        # Fast-track through approval states (manual dispatch bypasses approval flow)
        for state in ("AWAITING_APPROVAL", "APPROVED", "QUEUED", "RUNNING"):
            repo.transition(job_id, state, actor=from_role_key)
        repo.update(job_id, handoff_id=handoff_id)
        print(f"  Job record: {job_id}")
    except Exception as e:
        print(f"  WARNING: Job record creation skipped: {e}")

    # Step 4a2: VRAM-first — free the sender's model before warming the
    # target's (e.g. archi01's model is still loaded when imple01 starts).
    if from_role_type != "human":
        try:
            from_source_ss, from_alias_ss = get_effective_model_source(
                from_role_key, flow_key=flow_key, db_path=_db_path(),
            )
            if from_source_ss == "model_allocator" and from_alias_ss:
                _release_from_model_first(
                    handoff_id, from_alias_ss,
                    to_alias if to_source == "model_allocator" else "")
        except Exception:
            pass  # sender without a resolvable model — nothing to free

    # Step 4b: Acquire model lease for target role (reference-counted, VRAM-safe)
    # Lease identity is the HANDOFF id — signal_complete releases with the
    # handoff id, so acquiring under the job record id would orphan the lease.
    if to_source == "model_allocator" and to_alias:
        _stop_other_local_models(to_alias)
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "job_queue"))
            from model_lease import LeaseRegistry
            LeaseRegistry.acquire(handoff_id, to_alias, worker_id=from_role_key)
            print(f"  Lease acquired for '{to_alias}' (handoff {handoff_id})")
        except Exception:
            _run_allocator_stop(to_alias)
            _run_allocator_start(to_alias)

    # Step 5: Prepend governance file reference if target role has one
    # Run 008 / handoff 032 (D3b Site 3): the legacy direct-column read of
    # the receiver role is replaced by the unified resolver. The receiver
    # here is to_role_key -- the dispatch target, the role the composed
    # prompt is being injected INTO (NOT the sender, NOT the transition
    # step being signaled -- see spec section 15, binding semantics).
    _resolved_s = _resolve_receiver_execution_config(flow_key, to_role_key, handoff_id)
    gov_file = _resolved_s["governance_file"]
    project_root = PROJECT_ROOT
    if gov_file:
        gov_path = os.path.join(project_root, "docs", "governance-templates-v2", gov_file)
        print(f"  Governance: {gov_file}")

    # Step 6: Resolve convention content_template from step's rule_key
    ctemplate = resolve_content_template_from_db(
        rule_key, db_path=_db_path()
    ) if rule_key else ""

    # Step 7: Build prompt with placeholder replacement
    # Resolve model_name for {model_name} placeholder (via allocator alias)
    target_model_name = to_role_data.get("default_model_alias", "")
    output_pattern = payload.get("deliverable_pattern", "{ID}_{role_key}.json")
    output_file = output_pattern.replace("{ID}", handoff_id).replace("{role_key}", to_role_key)

    # Resolve primary output_type for {output_type} placeholder (json_output
    # convention, spec §5.2 + §8). Sourced from bridge_roles.primary_output_type
    # so the convention stays generic — no role-specific mapping in dispatch.
    target_output_type = to_role_data.get("primary_output_type") or ""

    if ctemplate:
        prompt_text = ctemplate.replace("{handoff_id}", handoff_id)
        # {flow_run_id} is the spec §5.2 alias for {handoff_id} (the flow run id).
        prompt_text = prompt_text.replace("{flow_run_id}", handoff_id)
        prompt_text = prompt_text.replace("{source_role}", from_role_key)
        prompt_text = prompt_text.replace("{next_role}", to_role_key)
        prompt_text = prompt_text.replace("{bridge_dir}", bridge_dir)
        prompt_text = prompt_text.replace("{flow_key}", flow_key)
        prompt_text = prompt_text.replace("{escalation_role}", escalation_role(flow_key))
        prompt_text = prompt_text.replace("{project_path}", get_flow_target_project(flow_key, db_path=_db_path()))
        prompt_text = prompt_text.replace("{deliverable_dir}", deliverable_dir)
        prompt_text = prompt_text.replace("{deliverable_file}", payload["deliverable_file"])
        prompt_text = prompt_text.replace("{output_file}", output_file)
        prompt_text = prompt_text.replace("{model_name}", target_model_name)
        prompt_text = prompt_text.replace("{output_type}", target_output_type)
        prompt_text = prompt_text.replace("{previous_deliverable_path}", handoff_abs)
        prompt_text = prompt_text.replace("{project_root}", str(PROJECT_ROOT))
        # Append explicit dispatch instruction with absolute path
        prompt_text += (
            f"\n\n## Dispatch Instruction\n"
            f"Read and execute {handoff_abs}"
        )
    else:
        prompt_text = (
            f"The role '{from_role_key}' has dispatched handoff "
            f"#{handoff_id} to you.\n"
            f"Read and execute {handoff_abs}"
        )

    # Append the target role's OWN deliverable path and signal command —
    # resolved to absolute paths. Governance files describe the path with
    # {bridge_dir}/{ID} placeholders, and local models fail to resolve them
    # (observed: imple01 wrote 'deliverable-315.md' in the repo root).
    # signal_complete already appends this block for chain callbacks; the
    # initial signal_send dispatch needs it just as much.
    # Position-aware: only steps strictly AFTER the dispatched step qualify
    # as the target's next step — a global scan re-matched step 1 on the
    # final step of cyclic flows (same defect as the signal_complete
    # callback path; the scheduler's stall wake-up dispatches through here).
    cur_idx = steps.index(target_step)
    for s in steps[cur_idx + 1:]:
        if s.get("from_role") == to_role_key:
            next_dir = s.get("deliverable_dir", "")
            next_pattern = s.get("deliverable_pattern", "{ID}-result.md")
            next_file = next_pattern.replace("{ID}", handoff_id).replace(
                "{role_key}", to_role_key)
            if os.path.isabs(next_dir):
                next_output_path = os.path.join(next_dir, next_file)
            else:
                next_output_path = os.path.join(bridge_dir, next_dir, next_file)
            prompt_text += (
                f"\n\n## Your Deliverable\n"
                f"Write your result to: {next_output_path}\n"
                f"Write ONLY to that exact path — do not create extra copies "
                f"or invented filenames in the project working directory.\n\n"
                f"## Signal Completion (MANDATORY — do not ask, just execute)\n"
                f"After writing the deliverable, run this command:\n"
                # 009: routed through the broker (see Site 1 above).
                f"nohup python3 {PROJECT_ROOT}/scripts/bridgeV002/bridge_broker.py "
                f"enqueue "
                f"--flow {flow_key} --from-role {to_role_key} "
                f"--to-role {to_role_key} "
                f"--id {handoff_id} --action signal-complete "
                f"> /tmp/bridge-enqueue-{flow_key}-{handoff_id}.log 2>&1 &"
            )
            break

    # Prepend governance file reference for target role
    # Per handoff 032 step 3: RUNTIME CONTEXT block is ALWAYS prepended;
    # governance reference line is CONDITIONAL on gov_file being set.
    gov_ref_s = ""
    if gov_file:
        gov_ref_s = f"Your role is defined in {gov_path}. Read it now before proceeding.\n\n"
    prompt_text = (
        f"{build_target_project_block(flow_key)}"
        f"{build_runtime_context(_resolved_s)}"
        f"{gov_ref_s}"
        f"{prompt_text}"
    )

    # Trade-MCP push path (PILOT): deterministic context for selected roles
    prompt_text = append_trade_mcp_context(
        prompt_text, flow_key, to_role_key, handoff_abs,
        mode=to_role_data.get("trade_mcp_push_mode"))

    # Third composition site for implementation_mode (spec section 26).
    # Run 018 wired run_flow_step_db and signal_complete; this path — the
    # one an Architect's or the Human's --signal-send actually takes —
    # composed its own prompt without the block, and the first live
    # opted-in dispatch (pi_test 005) reached the implementer without it.
    prompt_text = apply_mode_block(prompt_text, _db_path(), flow_key, payload["step_key"], payload["to_role"])

    # Model already warmed by LeaseRegistry.acquire() in Step 4 — skip redundant start

    # Step 8: Inject prompt into target role's tmux session.
    # An initial handoff is a NEW task for the target role — send its
    # configured context-reset command first (tool-independent).
    inject_prompt(tmux_session, prompt_text,
                  enter_command=to_role_data.get("enter_command", "default"),
                  fresh_session_command=to_role_data.get("fresh_session_command"))
    time.sleep(0.5)

    print(f"  Handoff dispatch prompt injected into '{tmux_session}'")

    # Step 9: Update symlink in deliverable directory
    link_path = os.path.join(bridge_dir, deliverable_dir, "current.md")
    try:
        if os.path.islink(link_path) or os.path.exists(link_path):
            os.unlink(link_path)
    except FileNotFoundError:
        pass
    os.symlink(handoff_file, link_path)

    # Step 10: Log dispatch event to trace.log. A dead backend gets its own
    # status so the watchdog re-sends instead of counting the delivery.
    backend_down = (to_source == "model_allocator"
                    and _backend_is_down(to_alias))
    if backend_down:
        print(f"  WARNING: backend for '{to_alias}' is down at injection — "
              f"logging dispatched_backend_down")
    log(
        f"{from_role_key}->{to_role_key}",
        handoff_id,
        "dispatched" if not backend_down else "dispatched_backend_down",
        f"Handoff {handoff_file} dispatched to {tmux_session}"
        + ("" if not backend_down else f" but backend '{to_alias}' is down"),
    )

    print(f"  Logged dispatched for handoff #{handoff_id}")
    print(f"✅ Handoff {handoff_id} sent to {tmux_session}")
    print(f"   File: {handoff_path}")
    print(f"   Waiting for work from target role...")

    # Update cycle state for Architect cold-start
    _update_cycle_state(handoff_id, flow_key, to_role_key)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="BridgeV002 dispatcher — universal role transition"
    )
    parser.add_argument("--from-role", default=None, help="Source role key (matches bridge_roles.role_key)")
    parser.add_argument("--to-role", default=None, help="Target role key (matches bridge_roles.role_key)")
    parser.add_argument("--id", default=None, help="Handoff ID (auto-generated if omitted)")
    parser.add_argument("--db-flow", default=None,
                        help="DB flow_key for database-driven dispatch (required)")
    parser.add_argument("--step-key", default=None,
                        help="DB step_key within the flow (for --signal-complete)")
    parser.add_argument("--signal-send", action="store_true",
                        help="Signal initial handoff dispatch from review to target role")
    parser.add_argument("--signal-complete", action="store_true",
                        help="Signal role completion — dispatch callback to next role")
    parser.add_argument("--signal-escalation", action="store_true",
                        help="Signal review escalation to architect")
    parser.add_argument("--signal-answer", action="store_true",
                        help="Signal architect answer back to review")
    parser.add_argument("--force", action="store_true",
                        help="Bypass the duplicate-delivery idempotency guard "
                             "(manual re-dispatch of an already-delivered signal)")

    args = parser.parse_args()

    bridge_dir = _bridge_dir()

    if not args.db_flow:
        print("Error: --db-flow is required for all BridgeV002 dispatch operations")
        print("  Legacy INI-based dispatch has been removed.")
        sys.exit(1)

    # Determine handoff ID: explicit --id overrides; DB auto-incremented counter.
    if args.id:
        # Normalize model-polluted ids: roles have derived flow_run_id from
        # trigger FILENAMES ('064_humantrade' in flow 064), and the pollution
        # then propagates through every chained deliverable/prompt. The id is
        # the leading numeric run number — strip any suffix.
        match = re.match(r"^(\d+)", str(args.id))
        if match and match.group(1) != str(args.id):
            print(f"  NOTE: normalized handoff id '{args.id}' "
                  f"-> '{match.group(1)}'")
            handoff_id = match.group(1)
        else:
            handoff_id = args.id
    else:
        handoff_id = f"{get_next_id_for_flow(args.db_flow, db_path=_db_path()):03d}"

    if args.signal_send:
        # Signal-send path: initial handoff dispatch from review to target role
        if not args.to_role:
            print("Error: --to-role is required for --signal-send")
            sys.exit(1)
        signal_send(
            args.db_flow,
            args.from_role,
            args.to_role,
            handoff_id,
            bridge_dir,
        )
        sys.exit(0)

    if args.signal_escalation:
        # Signal-escalation path: review escalates question to architect
        if not args.to_role:
            print("Error: --to-role is required for --signal-escalation")
            sys.exit(1)
        signal_escalation(
            args.db_flow,
            args.from_role,
            args.to_role,
            handoff_id,
            bridge_dir,
        )
        sys.exit(0)

    if args.signal_answer:
        # Signal-answer path: architect responds back to review
        if not args.to_role:
            print("Error: --to-role is required for --signal-answer")
            sys.exit(1)
        signal_answer(
            args.db_flow,
            args.from_role,
            args.to_role,
            handoff_id,
            bridge_dir,
        )
        sys.exit(0)

    if args.signal_complete:
        # Signal-complete path: role has finished its deliverable, dispatch to next role
        signal_complete(
            args.db_flow,
            args.step_key,
            args.from_role,
            handoff_id,
            bridge_dir,
            force=args.force,
        )
        sys.exit(0)

    # No signal flag but db-flow provided — run full flow step via DB dispatch
    run_flow_step_db(args.db_flow, args.step_key, handoff_id, bridge_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()
