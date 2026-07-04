from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import logging
import os
import io
import json
import sys
import platform
import subprocess
import sqlite3
from datetime import datetime
from fastapi import HTTPException
import config  # DPMtF-WebUI central config (Spor A — hardcoding cleanup)
from pathlib import Path

# BridgeV002 database-backed lookup (Spor I)
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts" / "bridgeV002"))
from bridge_lib import (
    load_role_from_db,
    load_flow_from_db,
    list_roles_from_db,
    list_flows_from_db,
    _bridgev002_tables_exist,
    get_next_id_for_flow,
)
from dispatch import build_step_payload

# Machine Profile healthcheck (Fase 1)
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from system_healthcheck import run_healthcheck

app = FastAPI(title="DPMtF WebUI")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database path
DB_PATH = config.get_db_path()

# Fallback locale for i18n
FALLBACK_LOCALE = config.get_default_locale()

# Logging configuration (Fase 0 - Optimization Roadmap)
logger = logging.getLogger(__name__)

_log_file = config.get_logging_file()
try:
    os.makedirs(os.path.dirname(_log_file), exist_ok=True)
except OSError:
    pass

log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

_file_handler = logging.FileHandler(_log_file, encoding="utf-8")
_file_handler.setFormatter(log_formatter)

_console_handler = logging.StreamHandler(sys.stderr)
_console_handler.setFormatter(log_formatter)

_root_logger = logging.getLogger()
_root_logger.setLevel(config.get_logging_level())
_root_logger.addHandler(_file_handler)
_root_logger.addHandler(_console_handler)

logger.info("DPMtF WebUI logging initialized (level=%s, file=%s)", config.get_logging_level(), _log_file)

# Startup config validation (Fase Ø-4 — Optimization Roadmap)
# Raises ConfigValidationError if config.py source still contains a
# hardcoded user-specific path string.
try:
    config.validate_no_hardcoded_paths()
    logger.info("DPMtF WebUI config validation passed (no hardcoded user paths)")
except config.ConfigValidationError as exc:
    logger.error("DPMtF WebUI config validation FAILED: %s", exc)
    raise
# Default app profiles









# ── Bridge router (Spor I + J — BridgeV002 database integration + CRUD) ─────


# ── Machine Profile Fase 1 — System Setup API ──────────────────








# ── Register routers (modular split — Fase B) ───────────────

from routers.bridge import router as bridge_router

app.include_router(bridge_router)

from routers.panels import router as panels_router

app.include_router(panels_router)

from routers.prompt_compiler import router as prompt_compiler_router

app.include_router(prompt_compiler_router)

from routers.governance import router as governance_router

app.include_router(governance_router)

from routers.system import router as system_router

app.include_router(system_router)

from routers.app_profiles import router as app_profiles_router

app.include_router(app_profiles_router)

from routers.validation import router as validation_router

app.include_router(validation_router)

from routers.webui import router as webui_router

app.include_router(webui_router)

from routers.git import router as git_router

app.include_router(git_router)

from routers.sessions import router as sessions_router

app.include_router(sessions_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9130)