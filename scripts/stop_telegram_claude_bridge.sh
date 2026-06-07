#!/usr/bin/env bash
set -euo pipefail

for SESSION in dpmtf_telegram_bridge dpmtf_claude_input_watch; do
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux kill-session -t "$SESSION"
    echo "stopped $SESSION"
  else
    echo "not running $SESSION"
  fi
done

echo "Remaining DPMtF tmux sessions:"
tmux ls 2>/dev/null | grep -E "dpmtf_(claude_code|telegram_bridge|claude_input_watch)" || true
