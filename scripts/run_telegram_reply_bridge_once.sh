#!/usr/bin/env bash
set -euo pipefail
cd /home/svend/DPMtF-WebUI
exec scripts/telegram_reply_bridge.py
