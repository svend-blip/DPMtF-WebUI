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


@router.get("/capability")
async def flowapp_export_capability():
    """Probe the external exporter and report the capability state."""
    state, detail = probe_exporter()
    return {"state": state, "detail": detail}


@router.get("/description")
async def flowapp_export_description(flow_key: str = Query(...)):
    """Read-only description of one flow for a standalone exporter."""
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
