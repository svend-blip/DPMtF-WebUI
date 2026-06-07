#!/usr/bin/env bash
set -euo pipefail
cd /home/svend/DPMtF-WebUI
echo "DPMtF Claude input watcher loop started: $(date)"
while true; do
  scripts/telegram_claude_input_watch.py || true
  sleep 10
done
