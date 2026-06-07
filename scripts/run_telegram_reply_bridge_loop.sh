#!/usr/bin/env bash
set -euo pipefail
cd /home/svend/DPMtF-WebUI
echo "DPMtF Telegram reply bridge loop started: $(date)"
while true; do
  scripts/telegram_reply_bridge.py || true
  sleep 3
done
