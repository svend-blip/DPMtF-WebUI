#!/usr/bin/env bash
set -euo pipefail
cd /home/svend/DPMtF-WebUI

echo "run_telegram_claude_output_watch_loop started: $(date)"

while true; do
  python3 scripts/telegram_claude_output_watch.py || true
  sleep 10
done
