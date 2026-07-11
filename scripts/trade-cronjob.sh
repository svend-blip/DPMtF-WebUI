#!/usr/bin/env bash
# trade-cronjob.sh — Daily Trade Cockpit simulation flow starter
#
# Usage:
#   ./scripts/trade-cronjob.sh [FLOW_ID]
#
# If FLOW_ID is omitted, the next ID from the database counter is used.
#
# Designed for cron:
#   0 9 * * 1-5 /home/svend/DPMtF-WebUI/scripts/trade-cronjob.sh >> /home/svend/DPMtF-WebUI/logs/trade-cronjob.log 2>&1

set -euo pipefail

PROJECT_ROOT="/home/svend/DPMtF-WebUI"

# cd FIRST — cron runs with CWD=$HOME (/home/svend), so a relative
# config.get_db_path() ("databases/dpmtf.db") would resolve to
# /home/svend/databases/dpmtf.db and break stop_tmuxflow/start_tmuxflow.
# All child scripts must inherit the project root as CWD.
cd "$PROJECT_ROOT"

TRADE_INBOX=$(python3 -c "import sys; sys.path.insert(0, '${PROJECT_ROOT}'); import config; print(config.get_trade_inbox_dir())")
LOG_DIR="${PROJECT_ROOT}/logs"
FLOW_KEY="trade_cockpit_simulation_v001"

# ── Resolve flow ID ──────────────────────────────────

if [ $# -ge 1 ]; then
    FLOW_ID="$1"
else
    # Atomically reserve the next ID AND increment the counter via the
    # shared library function. A raw SELECT would never advance the
    # counter (dispatch.py only increments when --id is omitted), causing
    # every cron run to reuse the same ID and collide with stale output.
    FLOW_ID=$(python3 -c "
import sys
sys.path.insert(0, '${PROJECT_ROOT}/scripts/bridgeV002')
from bridge_lib import get_next_id_for_flow
print(f'{get_next_id_for_flow(\"${FLOW_KEY}\", db_path=\"${PROJECT_ROOT}/databases/dpmtf.db\"):03d}')
")
fi

echo "═══════════════════════════════════════════════════════════"
echo "  Trade Cockpit Cronjob — Flow ${FLOW_ID}"
echo "  Started: $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════════"

# ── 1. Pre-flight cleanup ─────────────────────────────

echo ""
echo "[1/6] Pre-flight cleanup..."

# Stop ALL loaded Ollama models (free VRAM, clear context) — dynamic list
# from `ollama ps`, no hardcoded model names (config-consolidation).
ollama ps 2>/dev/null | awk 'NR>1 && NF {print $1}' | while read -r model; do
    echo "  Stopping $model..."
    ollama stop "$model" 2>/dev/null || true
done
echo "  Ollama models cleared."

# Kill old trade tmux sessions — DB-driven (no hardcoding, always covers all roles)
python3 "${PROJECT_ROOT}/scripts/bridgeV002/stop_tmuxflow.py" "$FLOW_KEY" 2>/dev/null || true

echo "  Tmux sessions cleared."

# ── 2. Create tmux sessions ───────────────────────────

echo ""
echo "[2/6] Creating tmux sessions..."

# DB-driven: start_tmuxflow.py queries bridge_flow_steps → bridge_roles for all
# required session names. No hardcoding — new roles (e.g. portfolio01_trade) are
# automatically covered as long as they exist in the database.
python3 "${PROJECT_ROOT}/scripts/bridgeV002/start_tmuxflow.py" "$FLOW_KEY"

# ── 3. Start coding frontends ─────────────────────────

echo ""
echo "[3/6] Starting coding frontends..."
python3 scripts/bridgeV002/start_coding.py "$FLOW_KEY"

# ── 4. Create trigger file ────────────────────────────

echo ""
echo "[4/6] Creating trigger file..."
mkdir -p "$TRADE_INBOX"
cat > "${TRADE_INBOX}/${FLOW_ID}_humantrade.json" << TRIGGEREOF
<role>You are trend01_trade in the ${FLOW_KEY} flow.</role>
<flow_run_id>${FLOW_ID}</flow_run_id>
<output_file>${FLOW_ID}_trend01_trade.json</output_file>
<task>Execute your role according to the governance file. Write your JSON output to a NEW file named exactly as output_file above, in the same inbox directory. NEVER overwrite this trigger file. Use flow_run_id "${FLOW_ID}" (the numeric run id above) in your output wrapper and in all signals — never derive it from filenames.</task>
<constraint>SIMULATION_ONLY = TRUE. Follow GATES.md. Valid JSON only.</constraint>
TRIGGEREOF
echo "  Created: ${FLOW_ID}_humantrade.json"

# ── 5. Wait for models to initialize ──────────────────

echo ""
echo "[5/6] Waiting for models to initialize (10s)..."
sleep 10

# ── 6. Dispatch ────────────────────────────────────────

echo ""
echo "[6/6] Dispatching flow ${FLOW_ID}..."
python3 scripts/bridgeV002/dispatch.py \
    --db-flow "$FLOW_KEY" \
    --signal-send --from-role humantrade --to-role trend01_trade \
    --id "$FLOW_ID"

echo ""
# ── 7. Chain watchdog (hardening 1b) ─────────────────
# Auto-nudges write-but-no-signal stalls and samples ollama ps
# (context/GPU-split observability). Scoped to this run: exits when
# portfolio01 delivers or after 90 minutes.
echo ""
echo "[7/7] Starting chain watchdog (90 min max)..."
# Parametre (stall/loop/max) laeses fra profiles/machine.local.json [watchdog]
nohup python3 "${PROJECT_ROOT}/scripts/bridgeV002/chain_watchdog.py" \
    --run-id "${FLOW_ID}" \
    >> "${LOG_DIR}/chain-watchdog.log" 2>&1 &
echo "  Watchdog PID: $!"

echo "═══════════════════════════════════════════════════════════"
echo "  Flow ${FLOW_ID} dispatch complete"
echo "  Finished: $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════════"
