#!/usr/bin/env bash
set -euo pipefail
cd /home/svend/DPMtF-WebUI

echo "Starting DPMtF Telegram bridge services..."

if ! tmux has-session -t dpmtf_telegram_bridge 2>/dev/null; then
  tmux new-session -d -s dpmtf_telegram_bridge -c /home/svend/DPMtF-WebUI "./scripts/run_telegram_reply_bridge_loop.sh"
  echo "started dpmtf_telegram_bridge"
else
  echo "already running dpmtf_telegram_bridge"
fi

if ! tmux has-session -t dpmtf_claude_input_watch 2>/dev/null; then
  tmux new-session -d -s dpmtf_claude_input_watch -c /home/svend/DPMtF-WebUI "./scripts/run_telegram_claude_input_watch_loop.sh"
  echo "started dpmtf_claude_input_watch"
else
  echo "already running dpmtf_claude_input_watch"
fi

if ! tmux has-session -t dpmtf_claude_output_watch 2>/dev/null; then
  tmux new-session -d -s dpmtf_claude_output_watch -c /home/svend/DPMtF-WebUI "./scripts/run_telegram_claude_output_watch_loop.sh"
  echo "started dpmtf_claude_output_watch"
else
  echo "already running dpmtf_claude_output_watch"
fi

echo "Active DPMtF tmux sessions:"
tmux ls | grep -E "dpmtf_(claude_code|telegram_bridge|claude_input_watch|claude_output_watch)" || true
