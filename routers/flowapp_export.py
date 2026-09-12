"""FlowApp export endpoints — Run 031 WORK 1 (DPMtF side).

Read-only HTTP surface behind the "Export FlowApp" button:

  GET /api/bridge-v2/flowapp-export/capability
      Local handshake probe against the external FlowRunner exporter.
      States per the D6 transport decision:
        absent       — no usable HTTP response (refused / timeout /
                       non-200 / unparseable body)
        compatible   — HTTP 200, service == "flowrunner-exporter",
                       api_version == 1, available == true
        incompatible — HTTP 200 with parseable JSON that mismatches on
                       service, api_version, or available

  GET /api/bridge-v2/flowapp-export/description?flow_key=<key>
      Minimum read-only description of one flow (identity, ordered
      steps, resolved execution facts). SELECTs only, parameterized.
      Unknown flow_key -> 404.

app.py is FROZEN, so these routes attach to the bridge router object:
routers/bridge.py includes this module's router at its bottom, and
app.py already includes the bridge router. No FlowRunner code is
imported; the exporter lives elsewhere and is only ever probed over
HTTP. No hardcoded home paths — the status URL is a module constant
overridable via the FLOWRUNNER_EXPORTER_URL environment variable.
"""

import json
import re
import logging
import os
import sqlite3
import subprocess
import sys
import urllib.request

from fastapi import APIRouter, HTTPException, Query

from routers.shared import get_db_path

logger = logging.getLogger(__name__)

# ── D6 transport contract constants ─────────────────────────────────
DEFAULT_EXPORTER_STATUS_URL = "http://127.0.0.1:8791/exporter/status"
EXPORTER_STATUS_URL = os.environ.get(
    "FLOWRUNNER_EXPORTER_URL", DEFAULT_EXPORTER_STATUS_URL
)
EXPORTER_PROBE_TIMEOUT_SECONDS = 2.0

EXPECTED_SERVICE = "flowrunner-exporter"
EXPECTED_API_VERSION = 1

router = APIRouter(prefix="/flowapp-export", tags=["flowapp-export"])


def classify_capability(status_code, body):
    """Pure classifier: (HTTP status, raw body text) -> (state, detail).

    ``body`` is the raw response body as text (or None). No network
    access here — unit-testable with canned inputs. ``state`` is one of
    "absent" | "compatible" | "incompatible" per the D6 transport
    decision.
    """
    if status_code != 200:
        return ("absent", f"exporter probe returned HTTP {status_code}")
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return ("absent", "exporter probe body was not parseable JSON")
    if not isinstance(payload, dict):
        return ("absent", "exporter probe body was not a JSON object")
    service = payload.get("service")
    api_version = payload.get("api_version")
    available = payload.get("available")
    if service != EXPECTED_SERVICE:
        return ("incompatible", f"unexpected service {service!r}")
    if api_version != EXPECTED_API_VERSION:
        return ("incompatible", f"unsupported api_version {api_version!r}")
    if available is not True:
        return ("incompatible", "exporter reports available != true")
    return ("compatible", "exporter reachable and compatible")


def probe_exporter(url=None):
    """Perform the handshake probe and classify the result.

    Any transport-level failure (refused, timeout, DNS, non-HTTP) is
    state "absent" — never an exception out of the endpoint.
    """
    target = url or EXPORTER_STATUS_URL
    try:
        with urllib.request.urlopen(target, timeout=EXPORTER_PROBE_TIMEOUT_SECONDS) as resp:
            status_code = resp.getcode()
            body = resp.read().decode("utf-8", "replace")
    except Exception as exc:  # no usable response at all -> absent
        return ("absent", f"no response from exporter: {exc}")
    return classify_capability(status_code, body)



#: FlowRunner's closed permission vocabulary (internal/flowapp AllPermissions).
#: An exported value outside this set is rejected by its loader, so anything
#: unrecognised falls back to the safe mode rather than shipping a broken app.
_FLOWRUNNER_PERMISSIONS = ("read_only", "workspace_write", "full_access")


def _resolved_step_permission():
    """The permission mode this host actually runs simple-harness steps under.

    Hardcoding ``read_only`` shipped an app that could not do its work: every
    step was denied write access, the harness exited permission_denied, and
    nothing was produced (found in the 2000 smoke test, 2026-09-10). DPMtF's
    own chain runs these very roles under ``workspace_write``, resolved by the
    harness allocator, so exporting read_only misdescribed the flow rather
    than securing it.

    Resolution is best-effort and never fatal: the exporter must keep working
    on a host without the allocator, where the safe mode is the honest answer.
    """
    try:
        import sys as _sys
        _bridge = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts", "bridgeV002")
        if _bridge not in _sys.path:
            _sys.path.insert(0, _bridge)
        import harness  # noqa: E402 -- late and optional by design
        mode = (harness._standalone().config
                .get_simple_harness_permission() or "").strip().lower()
    except Exception:
        return "read_only"
    return mode if mode in _FLOWRUNNER_PERMISSIONS else "read_only"



def _resolved_model_binding(role_key, client):
    """The concrete engine binding for a role+client, from the model allocator.

    Resolved HERE, at export time, on the machine where the allocator lives.
    A receiving machine cannot infer an endpoint or an engine name, and the
    Human's requirement (2026-09-10) is that it must not have to: install
    FlowRunner, import the FlowApp, type the secrets, run. So the binding
    travels inside the app instead — FlowRunner never needs the allocator.

    Only the NAME of the key variable travels. "Secrets are always typed in
    FlowRunner and are never transferred at export" (Human, 2026-09-10), and
    FlowRunner pins that with its own canary test.

    Best-effort by design: an export on a host without the allocator still
    produces a valid FlowApp, it simply carries no binding and the receiving
    operator supplies one with --model-name and FLOWRUNNER_MODEL_ENDPOINT.
    """
    role_key = (role_key or "").strip()
    client = (client or "").strip()
    if not role_key or not client:
        return {}
    try:
        import config  # late import; sys.path set up by routers/bridge.py
        root = config.get_project_path("model-allocator")
        proc = subprocess.run(
            [sys.executable, "-m", "model_allocator", "resolve",
             "--role", role_key, "--client", client],
            cwd=root, capture_output=True, text=True, timeout=20,
            # PYTHONPATH explicitly rather than relying on cwd or on the
            # package being installed: the allocator uses a src/ layout, so
            # the importable root is <root>/src. Under uvicorn neither cwd nor
            # a site-packages copy applied and the failure was "No module named
            # model_allocator", which the caller would otherwise have seen only
            # as a silently missing binding. Both paths are offered so a flat
            # checkout keeps working.
            env={**os.environ, "PYTHONPATH": os.pathsep.join(
                [os.path.join(root, "src"), root,
                 os.environ.get("PYTHONPATH", "")]).strip(os.pathsep)},
        )
        if proc.returncode != 0:
            logger.warning("model allocator rc=%s for role=%s client=%s: %s",
                           proc.returncode, role_key, client,
                           (proc.stderr or "").strip()[:300])
            return {}
        resolved = json.loads(proc.stdout)
    except Exception as exc:
        # Never fatal, but never silent either: a binding that quietly fails
        # to resolve produces a FlowApp that looks complete and is not.
        logger.warning("model binding unresolved for role=%s client=%s: %s: %s",
                       role_key, client, type(exc).__name__, exc)
        return {}
    if not isinstance(resolved, dict):
        return {}
    binding = {}
    for src, dst in (("real_model", "model"),
                     ("default_api_base", "endpoint"),
                     ("api_key_env", "api_key_env"),
                     ("backend", "backend")):
        value = (resolved.get(src) or "").strip()
        if value:
            binding[dst] = value
    return binding


def _resolve_execution_config(flow_key, step_key, db_path):
    """Late import of the bridge resolver — sys.path is set up by
    routers/bridge.py, which is the only importer of this module."""
    import execution_config
    return execution_config.resolve_execution_config(
        flow_key, step_key, db_path=db_path
    )


# ── D(a): DPMtF → FlowRunner Description bridge (format=flowrunner) ──
# The FlowRunner exporter's Description schema needs INLINE governance
# text, an abstract model PROFILE (never an inference-engine name — its
# rule 8), and a harness from its supported set. This transform reads
# governance text from the governance dir, maps the DPMtF facts, and
# raises HTTPException(422) on anything FlowRunner cannot accept.
_FR_SUPPORTED_HARNESSES = frozenset(
    {"simple-harness", "codex", "goose", "crush", "pi", "dsh", "claude-code"}
)
_ENGINE_WORDS = ("freetoken", "qwen", "sglang", "ollama", "llama.cpp")


def _fr_profile_id(to_role, flow_key):
    """Abstract, rule-8-safe model profile id from the executing role.

    DPMtF model_aliases frequently name an inference engine (e.g.
    ``freetoken-qwen38-flash-next``); FlowRunner's rule 8 forbids that in
    a model profile. The executing role is the abstract identity, so we
    derive the profile from ``to_role`` (minus the flow-family prefix),
    and fall back to ``model`` if the role itself names an engine.
    """
    role = (to_role or "model").strip()
    fam = flow_key.split("-")[0]
    if role.startswith(fam + "-"):
        role = role[len(fam) + 1:]
    low = role.lower()
    if any(w in low for w in _ENGINE_WORDS):
        role = "model"
    return role or "model"


_FAMILY_FLOW_KEY = re.compile(r"^(\d+)-\d+-([A-Za-z]+)$")


def _flowapp_identifier(flow_key: str) -> str:
    """Short FlowApp identifier for ``app.identifier`` in the description.

    FlowRunner installs an imported FlowApp under this name, so it should
    read the way the operator names things: a two-flow family key such as
    ``2000-02-ELOOP`` becomes ``eloop2000`` (loop name + family number),
    matching the hand-made ``eloop2000``/``ploop2000`` folders. Any other
    key becomes a lower-case slug (``[a-z0-9-]``).
    """
    m = _FAMILY_FLOW_KEY.match(flow_key or "")
    if m:
        return f"{m.group(2).lower()}{m.group(1)}"
    slug = re.sub(r"[^a-z0-9]+", "-", (flow_key or "").lower()).strip("-")
    return slug or "flowapp"


def _flowapp_family(flow_key: str) -> str:
    """Family number of a two-flow family key (``2000-02-ELOOP`` -> ``2000``).

    Both flows of a family carry the same value, so FlowRunner keeps their
    planning artefacts (drafts, promoted runs, handoffs, verdicts) in one tree
    under ``<target-repo>/.flowrunner/<family>/``. Other keys yield "".
    """
    m = _FAMILY_FLOW_KEY.match(flow_key or "")
    return m.group(1) if m else ""


def _flowrunner_context(step_key: str, prev_key: str | None, next_key: str | None,
                        bridge_dir: str, from_role: str = "") -> str:
    """Execution-context notice prepended to every exported governance file.

    The role files are written for the DPMtF bridge (dispatch signals,
    bridge_broker, RUN-LEDGER, tmux, the flows directory). Under FlowRunner
    none of that exists — and when the target repository IS DPMtF-WebUI the
    scripts do exist, so a role following its file literally will probe the
    live chain (observed 2026-09-11). The notice puts those parts out of force
    and states the FlowRunner contract (SCOPE-ADDENDUM-RUN-STRUCTURE): every
    path the role reads or writes is named in its STEP INPUT, which FlowRunner
    generates from the run directory under ``.flowrunner/<family>/runs/NNN/``;
    finishing the turn is the completion signal. The role rules that used to
    live in the instance task (one handoff per cycle, END-REPORT closes the
    run, budget, no rehearsal, no commit) live here now.
    """
    role = (from_role or "").lower()
    if "decomposer" in role:
        role_block = (
            "- **You are the decomposer, addressed by name: you do not implement.** Each turn "
            "you write EXACTLY ONE file, at the path your STEP INPUT names: either the next "
            "handoff (`handoffs/NNN-<step>.md`, one work package for the implementer, in your "
            "governance's handoff format: role, task with concrete files and changes, scope "
            "fence copied from the GOAL, acceptance criteria copied verbatim from the GOAL's "
            "testgoals) or `END-REPORT.md` when every acceptance criterion of the GOAL is met "
            "by the work already on the tree. Writing neither fails the run; writing anything "
            "else in the repository is a role breach the reviewer rejects.\n"
            "- On a later cycle read the previous verdict first; a REJECTED verdict means the "
            "next handoff carries the corrections, not a rewrite of what passed.\n"
            "- Budget: at most 12 tool calls; no pytest, no rehearsal of the criteria, no "
            "exploration beyond the GOAL, CLAUDE.md, the previous verdict and the files the "
            "fence names. Write the file, summarise it in your final message, stop.\n"
        )
    elif "review" in role:
        role_block = (
            "- **You are the reviewer, addressed by name: you do not implement or fix.** Your "
            "ONLY write is the verdict file your STEP INPUT names (`verdicts/NNN-<step>.md`): "
            "APPROVED or REJECTED, with the evidence you measured yourself against the working "
            "tree — never against the result's prose. The repository stays as the implementer "
            "left it. After your turn the decomposer runs again and reads your verdict.\n"
        )
    elif "implement" in role:
        role_block = (
            "- **You are the implementer, addressed by name:** you change exactly what the "
            "handoff names, inside its scope fence, run its acceptance criteria, and record "
            "what you did with the measured evidence in the result file your STEP INPUT names "
            "(`results/NNN-<step>.md`). A missing result file fails the run.\n"
        )
    elif "planning" in role or "supervisor" in role:
        role_block = (
            "- **You are the planning supervisor, addressed by name: you do not implement and "
            "you do not promote.** You read `SCOPE.md` in the planning tree your STEP INPUT "
            "names and write goal drafts as `goals/GOAL-DRAFT-NNN.md` (the next free number), "
            "each sized for one execution run, with `> Depends on:` lines naming earlier "
            "drafts and ```testgoals that parse. Questions for the Human go to `backlog.md`. "
            "Promotion (`runs/NNN/GOAL.md`) is the Human's act in the FlowRunner desktop.\n"
        )
    else:
        role_block = ""
    return (
        "## FlowRunner execution context (prepended by the DPMtF exporter)\n\n"
        "You are running under **FlowRunner**, not under the DPMtF bridge. Everything in "
        "this file about the bridge does NOT apply and must not be attempted: no "
        "`dispatch.py`, no `bridge_broker.py`, no signal-send/signal-complete, no "
        "materialize/promote-goal, no bridge database tables, no bridge-related mcp-light "
        "tools, no tmux sessions, and never any path under the DPMtF bridge directory "
        f"(`{bridge_dir}` on the exporting machine; it does not exist elsewhere).\n\n"
        "- Your workspace is the target repository you were started in. Stay inside it: "
        "never read or modify other projects, other tools' sessions, or DPMtF's database "
        "(`databases/dpmtf.db`), even if the repository is DPMtF itself.\n"
        "- **Every path you read or write is named in the STEP INPUT after the divider "
        "below** — the GOAL, the run directory under `.flowrunner/<family>/runs/NNN/`, the "
        "previous deliverables and your own deliverable. Use those paths exactly; never "
        "invent `goals/`, `runs/`, `RUN-LEDGER.md` or `END-REPORT.md` locations of your own. "
        "`RUN-LEDGER.md` is written by FlowRunner, not by you.\n"
        f"{role_block}"
        "- Finishing your turn is the completion signal: the next step starts automatically. "
        "Summarise your deliverable in your final message.\n"
        "- Do not commit or push unless the note in your STEP INPUT explicitly grants it. "
        "Do not ask questions; state assumptions in your deliverable.\n\n"
        "---\n\n"
    )


def _to_flowrunner_description(flow_row, steps, db_path):
    """Build a FlowRunner exporter Description dict from DPMtF facts.

    Governance is inlined from the governance dir; the model profile is
    abstract (rule 8); the harness must be in FlowRunner's supported set
    (unknown -> 422, no fallback). Step permissions carry the mode the
    flow actually runs under here, resolved from the harness allocator
    (see ``_resolved_step_permission``); secrets are left empty for the
    Human to declare.
    """
    import config  # late import; sys.path set up by routers/bridge.py

    if not steps:
        raise HTTPException(status_code=422,
                            detail=f"flow '{flow_row['flow_key']}' has no active steps")
    gov_dir = config.get_governance_dir_abs()

    # A step's FROM_ROLE is the role that ACTS: `A-B` means A does the work
    # under its own governance and hands the deliverable to B. The step's
    # governance_file is A's -- verified against every 2000 step (e.g.
    # implementer-reviewer carries IMPLEMENTOR.md, and planning-human carries
    # SUPERVISOR_PLANNING.md). So the SOURCE decides whether a step is runnable.
    #
    # A step whose source is a human is the flow's ENTRY boundary: the Human
    # acts out of band and the input arrives as the run's --task, seeded into
    # the entry step's input file. It is not a runnable FlowApp step.
    #
    # A step whose source is an AGENT is always exported, even when it hands to
    # a human -- that hand-off is just the flow's exit, and the agent's work is
    # real (Human, 2026-09-10). Filtering on EITHER end used to drop both steps
    # of a planning loop like {family}-01-PLOOP, refusing a flow whose single
    # agent step (the planning supervisor) is perfectly runnable.
    human_roles = set()
    try:
        hconn = sqlite3.connect(db_path)
        hconn.row_factory = sqlite3.Row
        try:
            human_roles = {
                r["role_key"]
                for r in hconn.execute(
                    "SELECT role_key FROM bridge_roles WHERE role_type = 'human'")
            }
        finally:
            hconn.close()
    except sqlite3.Error:
        human_roles = set()
    human_roles.add("human")  # the literal human sentinel is always a human step

    def _is_human(role):
        return role in human_roles

    agent_steps = [s for s in steps if not _is_human(s.get("from_role"))]
    if not agent_steps:
        raise HTTPException(status_code=422, detail=(
            f"flow '{flow_row['flow_key']}' has no agent steps to export — every "
            f"step is performed by a human role (a placeholder for HUMAN.md). A "
            f"runnable FlowApp needs at least one step whose acting role is an agent."))

    step_permission = _resolved_step_permission()
    models, harnesses, flow_steps = {}, {}, []
    for i, s in enumerate(agent_steps):
        step_key = s["step_key"]
        try:
            facts = _resolve_execution_config(flow_row["flow_key"], step_key, db_path)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"execution-config unresolved for step '{step_key}': {exc}")
        gov_file = facts.get("governance_file")
        if not gov_file:
            raise HTTPException(status_code=422,
                                detail=f"step '{step_key}' has no governance_file")
        gov_path = os.path.join(gov_dir, gov_file)
        if not os.path.isfile(gov_path):
            raise HTTPException(
                status_code=422,
                detail=f"governance file not found for step '{step_key}': {gov_file}")
        with open(gov_path, encoding="utf-8") as fh:
            gov_text = fh.read()
        prev_key = agent_steps[i - 1]["step_key"] if i > 0 else None
        next_key = agent_steps[i + 1]["step_key"] if i + 1 < len(agent_steps) else None
        gov_text = _flowrunner_context(step_key, prev_key, next_key, config.get_bridge_dir(),
                                       s.get("from_role", "")) + gov_text
        harness = facts.get("harness_source")
        if harness not in _FR_SUPPORTED_HARNESSES:
            raise HTTPException(
                status_code=422,
                detail=(f"step '{step_key}' harness '{harness}' is not supported by "
                        f"FlowRunner (supported: {sorted(_FR_SUPPORTED_HARNESSES)})"))
        profile = _fr_profile_id(s.get("to_role", ""), flow_row["flow_key"])
        alias = facts.get("model_alias") or "default"
        model_entry = {"name": profile, "dpmtf_alias": alias}
        model_entry.update(_resolved_model_binding(s.get("from_role", ""), harness))
        models.setdefault(profile, model_entry)
        harnesses.setdefault(harness, {"name": harness, "type": harness})
        fr_step = {
            "name": step_key,
            "governance": gov_text,
            "model": profile,
            "harness": harness,
            "permissions": [step_permission],
        }
        if i + 1 < len(agent_steps):
            fr_step["next"] = agent_steps[i + 1]["step_key"]
        flow_steps.append(fr_step)

    # The key NAMES the bound profiles need, so `flowrunner secrets check`
    # on the receiving machine names exactly what the operator must type.
    required_secrets = sorted(
        {m["api_key_env"] for m in models.values() if m.get("api_key_env")})

    return {
        "app": {
            "identifier": _flowapp_identifier(flow_row["flow_key"]),
            "name": flow_row.get("name") or flow_row["flow_key"],
            "version": "1.0.0",
            # The family groups the planning loop and the execution loop it
            # feeds under one planning tree in the target repository
            # (FlowRunner SCOPE-ADDENDUM-RUN-STRUCTURE); "" for other flows.
            "family": _flowapp_family(flow_row["flow_key"]),
        },
        "schema_version": "1.0.0",
        "secrets": {"required": required_secrets, "optional": []},
        "runtime": {"permissions": ["read_only", "workspace_write", "full_access"]},
        "models": list(models.values()),
        "harnesses": list(harnesses.values()),
        "flows": [{"name": "main", "entry": agent_steps[0]["step_key"], "steps": flow_steps}],
    }


@router.get("/capability")
async def flowapp_export_capability():
    """Probe the external exporter and report the capability state."""
    state, detail = probe_exporter()
    return {"state": state, "detail": detail}


@router.get("/description")
async def flowapp_export_description(
    flow_key: str = Query(...), format: str = Query(None)
):
    """Read-only description of one flow for a standalone exporter.

    Default returns the DPMtF-native facts JSON. ``format=flowrunner``
    returns a ready FlowRunner exporter Description YAML with inline
    governance, so the browser downloads a ``description.yaml`` that
    ``flowrunner export`` consumes directly.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        flow_row = cursor.execute(
            "SELECT flow_key, name FROM bridge_flows "
            "WHERE flow_key = ? AND is_active = 1",
            (flow_key,),
        ).fetchone()
        if flow_row is None:
            raise HTTPException(status_code=404, detail=f"Flow '{flow_key}' not found")
        step_rows = cursor.execute(
            "SELECT step_key, from_role, to_role, sort_order "
            "FROM bridge_flow_steps WHERE flow_key = ? AND is_active = 1 "
            "ORDER BY sort_order ASC",
            (flow_key,),
        ).fetchall()
    finally:
        conn.close()

    steps = [dict(r) for r in step_rows]

    if format == "flowrunner":
        import yaml
        from fastapi.responses import Response
        description = _to_flowrunner_description(dict(flow_row), steps, db_path)
        text = yaml.safe_dump(
            description, sort_keys=False, allow_unicode=True, width=100
        )
        return Response(content=text, media_type="application/x-yaml")

    execution_facts = []
    for step in steps:
        try:
            execution_facts.append(
                _resolve_execution_config(flow_key, step["step_key"], db_path)
            )
        except Exception as exc:
            logger.warning(
                "flowapp-export: execution-config resolve failed for %s/%s: %s",
                flow_key, step.get("step_key"), exc,
            )
            execution_facts.append(
                {"flow_key": flow_key, "step_key": step.get("step_key"),
                 "error": str(exc)}
            )

    return {
        "flow": dict(flow_row),
        "steps": steps,
        "step_count": len(steps),
        "execution_facts": execution_facts,
    }
