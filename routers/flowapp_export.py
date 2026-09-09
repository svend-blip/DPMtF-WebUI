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
import logging
import os
import sqlite3
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


def _to_flowrunner_description(flow_row, steps, db_path):
    """Build a FlowRunner exporter Description dict from DPMtF facts.

    Governance is inlined from the governance dir; the model profile is
    abstract (rule 8); the harness must be in FlowRunner's supported set
    (unknown -> 422, no fallback). Permissions default to the safe
    ``read_only``; secrets are left empty for the Human to declare.
    """
    import config  # late import; sys.path set up by routers/bridge.py

    if not steps:
        raise HTTPException(status_code=422,
                            detail=f"flow '{flow_row['flow_key']}' has no active steps")
    gov_dir = config.get_governance_dir_abs()
    models, harnesses, flow_steps = {}, {}, []
    for i, s in enumerate(steps):
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
        harness = facts.get("harness_source")
        if harness not in _FR_SUPPORTED_HARNESSES:
            raise HTTPException(
                status_code=422,
                detail=(f"step '{step_key}' harness '{harness}' is not supported by "
                        f"FlowRunner (supported: {sorted(_FR_SUPPORTED_HARNESSES)})"))
        profile = _fr_profile_id(s.get("to_role", ""), flow_row["flow_key"])
        alias = facts.get("model_alias") or "default"
        models.setdefault(profile, {"name": profile, "dpmtf_alias": alias})
        harnesses.setdefault(harness, {"name": harness, "type": harness})
        fr_step = {
            "name": step_key,
            "governance": gov_text,
            "model": profile,
            "harness": harness,
            "permissions": ["read_only"],
        }
        if i + 1 < len(steps):
            fr_step["next"] = steps[i + 1]["step_key"]
        flow_steps.append(fr_step)

    return {
        "app": {"name": flow_row.get("name") or flow_row["flow_key"], "version": "1.0.0"},
        "schema_version": "1.0.0",
        "secrets": {"required": [], "optional": []},
        "runtime": {"permissions": ["read_only", "workspace_write", "full_access"]},
        "models": list(models.values()),
        "harnesses": list(harnesses.values()),
        "flows": [{"name": "main", "entry": steps[0]["step_key"], "steps": flow_steps}],
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
