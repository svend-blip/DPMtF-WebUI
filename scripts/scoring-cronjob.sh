#!/usr/bin/env bash
# scoring-cronjob.sh — Weekly Trade Cockpit scoring flow starter
#
# Usage:
#   ./scripts/scoring-cronjob.sh [FLOW_ID]
#
# Designed for cron (weekly, e.g. Sunday 10:00):
#   0 10 * * 0 /home/svend/DPMtF-WebUI/scripts/scoring-cronjob.sh >> /home/svend/DPMtF-WebUI/logs/scoring-cronjob.log 2>&1

set -euo pipefail

PROJECT_ROOT="/home/svend/DPMtF-WebUI"

# cd FIRST — cron runs with CWD=$HOME (/home/svend), so a relative
# config.get_db_path() ("databases/dpmtf.db") would resolve to
# /home/svend/databases/dpmtf.db and break stop_tmuxflow/start_tmuxflow.
# All child scripts must inherit the project root as CWD.
cd "$PROJECT_ROOT"

TRADE_INBOX=$(python3 -c "import sys; sys.path.insert(0, '${PROJECT_ROOT}'); import config; print(config.get_trade_inbox_dir())")
LOG_DIR="${PROJECT_ROOT}/logs"
FLOW_KEY="trade_cockpit_scoring_v001"

# ── Resolve flow ID ──────────────────────────────────

if [ $# -ge 1 ]; then
    FLOW_ID="$1"
else
    # Atomically reserve the next ID AND increment the counter via the
    # shared library function (also auto-creates the row if missing).
    # A raw SELECT would crash on the missing scoring counter row and
    # never advance the counter on subsequent runs.
    FLOW_ID=$(python3 -c "
import sys
sys.path.insert(0, '${PROJECT_ROOT}/scripts/bridgeV002')
from bridge_lib import get_next_id_for_flow
print(f'{get_next_id_for_flow(\"${FLOW_KEY}\", db_path=\"${PROJECT_ROOT}/databases/dpmtf.db\"):03d}')
")
fi

echo "═══════════════════════════════════════════════════════════"
echo "  Trade Cockpit Scoring — Flow ${FLOW_ID}"
echo "  Started: $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════════"

# ── 1. Pre-flight cleanup ─────────────────────────────

echo ""
echo "[1/6] Pre-flight cleanup..."

SCORING_MODELS=("qwen3.6:27b-q4_K_M")
for model in "${SCORING_MODELS[@]}"; do
    if ollama ps 2>/dev/null | grep -q "$model"; then
        echo "  Stopping $model..."
        ollama stop "$model" 2>/dev/null || true
    fi
done
echo "  Ollama models cleared."

for session in score01_trade learn01_trade; do
    if tmux has-session -t "$session" 2>/dev/null; then
        tmux kill-session -t "$session" 2>/dev/null || true
        echo "  Killed tmux session: $session"
    fi
done
echo "  Tmux sessions cleared."

# ── 2. Create tmux sessions ───────────────────────────

echo ""
echo "[2/6] Creating tmux sessions..."
for session in score01_trade learn01_trade; do
    tmux new-session -d -s "$session"
    echo "  Created: $session"
done

# ── 3. Start coding frontends ─────────────────────────

echo ""
echo "[3/6] Starting coding frontends..."
python3 scripts/bridgeV002/start_coding.py "$FLOW_KEY"

# ── 4. Create trigger file ────────────────────────────

echo ""
echo "[4/6] Creating trigger file..."
mkdir -p "$TRADE_INBOX"
cat > "${TRADE_INBOX}/${FLOW_ID}_humantrade.json" << TRIGGEREOF
<role>You are score01_trade in the ${FLOW_KEY} flow.</role>
<task>Execute your role according to the governance file. Produce JSON output to the inbox.</task>
<constraint>SIMULATION_ONLY = TRUE. Follow GATES.md. Valid JSON only.</constraint>
TRIGGEREOF
echo "  Created: ${FLOW_ID}_humantrade.json"

# ── 5. Wait for models to initialize ──────────────────

echo ""
echo "[5/6] Waiting for models to initialize (10s)..."
sleep 10

# ── 6. Dispatch ────────────────────────────────────────

echo ""
echo "[6/6] Dispatching scoring flow ${FLOW_ID}..."
python3 scripts/bridgeV002/dispatch.py \
    --db-flow "$FLOW_KEY" \
    --signal-send --from-role humantrade --to-role score01_trade \
    --id "$FLOW_ID"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Scoring flow ${FLOW_ID} dispatch complete"
echo "  Finished: $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════════"
