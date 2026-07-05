#!/usr/bin/env bash
# ollama-stop-all.sh — Stop all running Ollama models to free context/VRAM
#
# Runs `ollama ps`, parses running model names, and runs `ollama stop` on each.
# This clears local model context before the trade/scoring cronjobs start.
#
# Designed for cron (e.g. 08:45 before trade-cronjob at 09:00 Mon-Fri,
# and before scoring-cronjob at 10:00 Sunday):
#   45 8 * * * /home/svend/DPMtF-WebUI/scripts/ollama-stop-all.sh >> /home/svend/DPMtF-WebUI/logs/ollama-stop-all.log 2>&1

set -euo pipefail

PROJECT_ROOT="/home/svend/DPMtF-WebUI"

echo "═══════════════════════════════════════════════════════════"
echo "  Ollama Stop-All — Free context on local models"
echo "  Started: $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════════"

# Check ollama is available
if ! command -v ollama >/dev/null 2>&1; then
    echo "ERROR: ollama command not found"
    exit 1
fi

# Check ollama daemon is running
if ! ollama ps >/dev/null 2>&1; then
    echo "Ollama daemon not running. Nothing to stop."
    echo "═══════════════════════════════════════════════════════════"
    echo "  Finished: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "═══════════════════════════════════════════════════════════"
    exit 0
fi

# Get running models (skip header line, first column is the model name).
# Model names contain a colon but no spaces, so awk field 1 is safe.
RUNNING=$(ollama ps 2>/dev/null | awk 'NR>1 {print $1}' | grep -v '^$' || true)

if [ -z "$RUNNING" ]; then
    echo "No Ollama models running. Nothing to stop."
    echo "═══════════════════════════════════════════════════════════"
    echo "  Finished: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "═══════════════════════════════════════════════════════════"
    exit 0
fi

echo "Running models found:"
echo "$RUNNING" | sed 's/^/  - /'
echo ""

# Stop each running model.
STOPPED=0
FAILED=0
while IFS= read -r model; do
    [ -z "$model" ] && continue
    echo "Stopping $model..."
    if ollama stop "$model" 2>/dev/null; then
        echo "  Stopped: $model"
        STOPPED=$((STOPPED+1))
    else
        echo "  FAILED to stop: $model"
        FAILED=$((FAILED+1))
    fi
done <<< "$RUNNING"

echo ""
echo "Summary: $STOPPED stopped, $FAILED failed"

# Ollama unloads models asynchronously — the process lingers in "Stopping..."
# state for a few seconds after `ollama stop` returns. Wait, then re-check.
echo "Waiting 5s for asynchronous unload..."
sleep 5

# Re-check. A model still listed is only a real problem if it is NOT in the
# "Stopping..." state (i.e. it has an active keep_alive window remaining).
REMAINING=$(ollama ps 2>/dev/null | awk 'NR>1 && $0 !~ /Stopping/ {print $1}' | grep -v '^$' || true)
if [ -n "$REMAINING" ]; then
    echo "WARNING: models still active (not stopping) after stop attempt:"
    echo "$REMAINING" | sed 's/^/  - /'
else
    echo "All models stopped or stopping. Context cleared."
fi

echo "═══════════════════════════════════════════════════════════"
echo "  Finished: $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════════"
