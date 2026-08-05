# 439 — TRADE_HUMAN

> **en-US is the standard language for all governance-templates-v2 files.**

## Role

You are **humantrade** (Human) in the DPMtF trade flows. You are the flow initiator and
the endpoint for all trade cockpit outputs.

## When You Are Active

- **Flow initiation:** You (or a cronjob) start `trade_cockpit_simulation_v001` by dispatching
  from humantrade to trend01_trade. The dispatch system skips tmux injection for human roles
  and starts the first agent role directly.
- **Flow initiation:** You (or a cronjob) start `trade_cockpit_scoring_v001` by dispatching
  from humantrade to score01_trade.
- **Review:** You review trade outputs in the Trade Cockpit WebUI (port 9140).

## Scope Authority

- You approve or reject proposed rule changes from learn01_trade
- You configure cronjob schedules
- You set the prompt template for daily trend scans
- You decide when to run the scoring flow

## Flows

| Flow | Your Role |
|------|-----------|
| `trade_cockpit_simulation_v001` | Initiator (human → trend01_trade) |
| `trade_cockpit_scoring_v001` | Initiator (human → score01_trade) |

## Cronjob Initiation

```bash
# Daily simulation flow (weekdays 08:57)
57 8 * * 1-5 cd "$HOME/DPMtF-WebUI" && python3 scripts/bridgeV002/dispatch.py \
  --db-flow trade_cockpit_simulation_v001 \
  --signal-send \
  --from-role humantrade \
  --to-role trend01_trade

# Weekly scoring flow (Sundays 18:00)
0 18 * * 0 cd "$HOME/DPMtF-WebUI" && python3 scripts/bridgeV002/dispatch.py \
  --db-flow trade_cockpit_scoring_v001 \
  --signal-send \
  --from-role humantrade \
  --to-role score01_trade
```

## Constraints

- SIMULATION_ONLY = TRUE — never enable real trading without explicit approval
- All rule changes from learn01_trade require your explicit approval
- Review trade-ui dashboard regularly to monitor simulation results
