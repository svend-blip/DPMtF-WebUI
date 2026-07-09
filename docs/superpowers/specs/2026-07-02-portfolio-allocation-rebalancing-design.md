# Portfolio Allocation / Rebalancing Loop — Tightened Design Spec

> **Status:** Design — awaiting build
> **Language standard:** en-US for governance/spec docs
> **Scope:** Portfolio-aware allocation proposal layer for Trade Cockpit / eToro demo bridge
> **Execution mode:** Human-approved only. `AUTO_EXECUTION_DISABLED` remains authoritative.

---

## 1. Purpose

The Trade Cockpit must reason across the full portfolio, not evaluate one candidate at a time in isolation.

The allocation layer must consider:

* available liquidity
* open positions
* approved new candidates
* position size and capital lock-up
* unrealized P/L
* portfolio concentration
* cash buffer requirements
* risk-adjusted favorability
* potential swaps where a weaker position is closed to fund a stronger candidate

The output is one consolidated and ranked `allocation_plan`.

The plan is decision support only. It must never execute trades automatically.

---

## 2. Architectural Placement

Add a dedicated portfolio role after simulation:

```text
trend01_trade
→ market01_trade
→ analyst01_trade
→ risk01_trade
→ review01_trade
→ sim01_trade
→ portfolio01_trade
→ human_gate
→ bridge_execution
```

`portfolio01_trade` is additive and must not replace `risk01_trade`.

Responsibilities:

```text
risk01_trade:
  Evaluates isolated candidate risk.

sim01_trade:
  Produces approved trade candidates.

portfolio01_trade:
  Evaluates candidates against the existing portfolio and liquidity state.

bridge_execution:
  Executes only Human-approved plan items, with hard gates.
```

---

## 3. Non-Goals for v1

The first build must avoid overreach.

Out of scope for v1:

```text
auto execution
intra-day trigger engine
partial closes
portfolio optimization solver
tax optimization
multi-broker support
short selling
leverage optimization
automatic threshold changes from learn01
```

Allowed in v1:

```text
read-only scoring
allocation_plan generation
open_new proposal
hold proposal
skip_candidate proposal
close_then_open proposal after Human Gate
full-close only
one swap maximum per run
```

---

## 4. Inputs to portfolio01_trade

`portfolio01_trade` reads four input groups.

### 4.1 Approved candidates from sim01_trade

Required fields:

```text
candidate_trade_id
symbol
instrument_id
entry
stop_loss
take_profit
confidence
risk_reward
thesis
expected_horizon
recommended_position_size
candidate_status
```

Only candidates with approved simulation status may enter the allocation layer.

### 4.2 Current eToro portfolio

From `sync-positions`:

```text
position_id
symbol
instrument_id
current_rate
entry_rate
unrealized_pl
realized_pl_where_relevant
invested_amount
units
current_exposure
stop_loss_if_known
take_profit_if_known
opened_at_if_known
```

### 4.3 Liquidity

From `/api/etoro/status` and local state:

```text
credit
pending_order_commitments
reserved_cash_buffer
available_liquidity
estimated_total_portfolio_value
```

### 4.4 Portfolio rules

From config:

```text
max_position_size_pct
max_sector_exposure_pct
max_theme_exposure_pct
max_concurrent_new_positions
max_swaps_per_run
minimum_swap_delta
minimum_cash_buffer_pct
minimum_cash_buffer_absolute
near_take_profit_protection_enabled
near_take_profit_threshold_pct
partial_close_enabled
auto_execution_enabled
```

For v1:

```text
max_swaps_per_run = 1
partial_close_enabled = false
auto_execution_enabled = false
```

---

## 5. Output Contract

`portfolio01_trade` produces exactly one output type:

```text
allocation_plan
```

The plan must be:

```text
ranked
deterministic
human-readable
machine-validated
execution-safe
traceable to input_refs
```

It must include both recommended actions and skipped candidates.

This is important because skipped candidates are later needed by `score01_trade` and `learn01_trade`.

---

## 6. Favorability Score

`favorability_score` is the common comparison metric for:

```text
existing open positions
new approved candidates
```

The score is normalized:

```text
0.00 = very poor
1.00 = excellent
```

The score is for ranking and allocation proposals only.

It must not be used as the only execution condition.

### 6.1 Score Components

```text
favorability_score =
  expected_return_component
+ risk_reward_component
+ confidence_component
+ thesis_quality_component
+ portfolio_fit_component
+ liquidity_efficiency_component
- downside_risk_penalty
- concentration_penalty
- stale_data_penalty
- transaction_cost_penalty
```

All components should be normalized to avoid one field dominating the score accidentally.

### 6.2 Existing Position Score

For existing positions:

```text
remaining_expected_return =
  (take_profit - current_rate) / current_rate
```

If take profit is missing, the system must not invent one.

Fallback behavior:

```text
if take_profit missing:
  reduce data_completeness
  add warning
  use conservative favorability cap
```

Recommended cap:

```text
max_favorability_without_take_profit = 0.55
```

### 6.3 Candidate Score

For new candidates:

```text
candidate_expected_return =
  (take_profit - planned_entry) / planned_entry
```

If entry, stop loss, or take profit is missing, the candidate must be marked:

```text
skip_candidate
```

with reason:

```text
missing_required_trade_levels
```

---

## 7. Liquidity Model

Liquidity must be computed conservatively.

```text
reserved_cash_buffer =
  max(total_portfolio_value * 0.05, 50)

available_liquidity =
  credit
- reserved_cash_buffer
- pending_order_commitments
```

`available_liquidity` must never be allowed below zero in calculations:

```text
available_liquidity = max(0, available_liquidity)
```

### 7.1 Open New

A candidate can be proposed as `open_new` only if:

```text
available_liquidity >= required_cash
```

and:

```text
estimated_cash_after_action >= reserved_cash_buffer
```

### 7.2 Close Then Open

A candidate can be proposed as `close_then_open` only if:

```text
available_liquidity + estimated_freed_cash >= required_cash
```

and:

```text
swap_delta >= minimum_swap_delta
```

and:

```text
max_swaps_per_run not exceeded
```

and:

```text
close target is eligible for closing
```

---

## 8. Swap Logic

A swap is not just "candidate better than position".

A swap must account for friction, uncertainty, and anti-churn.

```text
swap_delta =
  candidate_favorability
- existing_position_favorability
- estimated_close_cost_score
- estimated_open_cost_score
- slippage_buffer_score
- churn_penalty_score
```

v1 threshold:

```text
minimum_swap_delta = 0.10
```

`minimum_swap_delta` is in normalized score units, not percentage return.

### 8.1 Hard Swap Blocks

Do not propose `close_then_open` if:

```text
candidate confidence below threshold
candidate data quality is low
existing position is protected by near-TP rule
position cannot be verified in latest portfolio sync
required cash cannot be estimated
estimated freed cash cannot be estimated
close target has already been selected for another plan item
max_swaps_per_run exceeded
```

### 8.2 Negative P/L Positions

Negative P/L positions may be proposed for closing.

However, the plan item must include a UI warning:

```text
This closes a negative-P/L position. Realized loss should be reviewed before approval.
```

Negative P/L alone must not protect a weak position.

---

## 9. Near Take-Profit Protection

Positions close to take profit should normally not be swapped out.

Rule:

```text
do_not_swap_if_position_near_take_profit = true
```

Suggested v1 logic:

```text
remaining_to_tp_pct =
  (take_profit - current_rate) / current_rate

if remaining_to_tp_pct <= near_take_profit_threshold_pct:
  block close_then_open
```

Recommended v1 threshold:

```text
near_take_profit_threshold_pct = 0.05
```

If take profit is missing, this protection cannot be evaluated. Add warning:

```text
near_take_profit_protection_not_evaluable
```

---

## 10. Action Types

Allowed action types:

```text
hold
open_new
close_then_open
skip_candidate
```

Reserved for later:

```text
close
reduce_position
increase_position
```

`close` as a standalone recommendation should not be enabled in v1 unless there is a separate risk/emergency rule.

Reason: v1 portfolio logic is about allocation and swaps, not discretionary liquidation.

---

## 11. allocation_plan JSON Schema

```json
{
  "output_type": "allocation_plan",
  "schema_version": "trade_allocation_plan_v001",
  "flow_type": "trade_cockpit_simulation_v001",
  "role_stage": "portfolio01_trade",
  "simulation_id": "SIM-...",
  "input_refs": [],
  "run_id": "ALLOC-RUN-...",
  "created_at": "ISO-8601",
  "portfolio_snapshot": {
    "credit": 0,
    "reserved_cash_buffer": 0,
    "pending_order_commitments": 0,
    "available_liquidity": 0,
    "estimated_total_portfolio_value": 0,
    "open_positions_count": 0,
    "total_exposure": 0,
    "snapshot_source": "sync-positions",
    "snapshot_at": "ISO-8601"
  },
  "allocation_summary": {
    "recommended_actions_count": 0,
    "open_new_count": 0,
    "close_then_open_count": 0,
    "hold_count": 0,
    "skipped_count": 0,
    "estimated_cash_after_actions": 0,
    "max_swaps_per_run": 1,
    "swaps_used": 0
  },
  "allocation_plan": [
    {
      "plan_item_id": "ALLOC-ITEM-...",
      "rank": 1,
      "action": "close_then_open",
      "candidate_trade_id": "TRADE-...",
      "candidate_symbol": "XYZ",
      "candidate_instrument_id": 123,
      "position_id": "POS-...",
      "position_symbol": "ABC",
      "position_instrument_id": 456,
      "close_targets": [
        {
          "position_id": "POS-...",
          "symbol": "ABC",
          "estimated_freed_cash": 0,
          "unrealized_pl": 0,
          "realized_loss_warning": false,
          "reason": "Lower remaining favorability than candidate"
        }
      ],
      "candidate_favorability": 0,
      "existing_position_favorability": 0,
      "swap_delta": 0,
      "score_breakdown": {
        "expected_return_component": 0,
        "risk_reward_component": 0,
        "confidence_component": 0,
        "portfolio_fit_component": 0,
        "downside_risk_penalty": 0,
        "concentration_penalty": 0,
        "transaction_cost_penalty": 0,
        "stale_data_penalty": 0
      },
      "liquidity_impact": {
        "required_cash": 0,
        "freed_cash": 0,
        "available_cash_before": 0,
        "estimated_cash_after": 0,
        "cash_buffer_after": 0,
        "liquidity_gate_status": "pass"
      },
      "risk_impact": {
        "portfolio_risk_before": 0,
        "portfolio_risk_after": 0,
        "concentration_change": "neutral",
        "position_size_pct_after": 0
      },
      "rationale": "Candidate has materially better expected risk-adjusted return than the current position.",
      "warnings": [],
      "blockers": [],
      "execution_gates": [
        "human_approval_required",
        "portfolio_snapshot_must_be_refreshed",
        "swap_targets_must_close_first",
        "liquidity_must_be_rechecked_after_close",
        "order_size_must_be_revalidated"
      ],
      "human_review": {
        "required": true,
        "status": "pending",
        "reviewed_by": null,
        "reviewed_at": null
      }
    }
  ],
  "skipped_candidates": [
    {
      "candidate_trade_id": "TRADE-...",
      "symbol": "XYZ",
      "reason": "insufficient_liquidity_and_no_valid_swap",
      "candidate_favorability": 0,
      "warnings": []
    }
  ],
  "quality": {
    "confidence": "medium",
    "data_completeness": "partial",
    "warnings": [],
    "blockers": []
  }
}
```

---

## 12. Database Changes

Prefer storing the allocation plan as a first-class object.

### 12.1 trade_allocation_plans

```text
id
run_id
simulation_id
schema_version
created_at
portfolio_snapshot_json
allocation_summary_json
allocation_plan_json
quality_json
status
human_review_status
executed_at
```

### 12.2 trade_allocation_plan_items

```text
id
allocation_plan_id
plan_item_id
rank
action
candidate_trade_id
candidate_symbol
candidate_instrument_id
position_id
position_symbol
position_instrument_id
candidate_favorability
position_favorability
swap_delta
score_breakdown_json
liquidity_impact_json
risk_impact_json
rationale
warnings_json
blockers_json
human_review_status
execution_status
created_at
updated_at
```

### 12.3 simulated_trades additions

```text
allocation_plan_id
allocation_plan_item_id
allocation_action
allocation_rank
candidate_favorability
allocation_rationale
requires_close_first
swap_delta
```

### 12.4 etoro_orders additions

```text
allocation_plan_id
allocation_plan_item_id
close_targets_json
close_before_open
liquidity_gate_status
allocation_rationale
execution_sequence_status
```

---

## 13. Bridge Execution Design

The bridge must support a composite action:

```text
close_then_open
```

This action must be idempotent and stateful.

### 13.1 Execution Sequence

```text
1. Verify Human approval for the specific plan_item_id.
2. Refresh portfolio snapshot.
3. Verify target position still exists.
4. Verify target position still matches expected instrument_id.
5. Verify candidate order still has valid instrument_id.
6. Recalculate liquidity and required cash.
7. Close target position.
8. Verify close confirmation.
9. Refresh /status and sync-positions.
10. Verify liquidity is now available.
11. Execute new order.
12. Verify order result.
13. Store execution result.
14. Mark plan item execution_status.
```

### 13.2 Hard Stop Conditions

The bridge must stop if:

```text
human approval missing
portfolio snapshot stale
position not found
position instrument mismatch
candidate instrument missing
candidate instrument mismatch
close confirmation missing
liquidity still insufficient after close
order execution rejected
eToro status unavailable
```

### 13.3 Required Error Codes

```text
HUMAN_APPROVAL_MISSING
PORTFOLIO_SNAPSHOT_STALE
POSITION_NOT_FOUND
POSITION_INSTRUMENT_MISMATCH
CANDIDATE_INSTRUMENT_MISSING
CANDIDATE_INSTRUMENT_MISMATCH
CLOSE_CONFIRMATION_MISSING
INSUFFICIENT_LIQUIDITY_AFTER_CLOSE
ORDER_EXECUTION_REJECTED
ETORO_STATUS_UNAVAILABLE
```

### 13.4 Idempotency

Each bridge execution must use:

```text
allocation_plan_id
allocation_plan_item_id
execution_attempt_id
```

The bridge must not execute the same approved plan item twice.

If a close succeeded but the open failed, the item must be marked:

```text
partial_sequence_failed_after_close
```

and surfaced clearly in WebUI.

---

## 14. WebUI Design

The eToro panel must show the allocation plan as one decision card with per-item approval.

Each item displays:

```text
Rank
Action
Candidate
Position to close
Required cash
Freed cash
Swap delta
Candidate favorability
Existing position favorability
Score breakdown
Risk impact
Liquidity impact
Warnings
Blockers
Rationale
Human approval control
Execution status
```

### 14.1 UI Labels

```text
OPEN_NEW:
Buy XYZ using free liquidity.
Required cash: $100.
Available after cash buffer: $250.

CLOSE_THEN_OPEN:
Close ABC first, estimated freed cash: $120.
Then buy XYZ, required cash: $100.
Swap delta: +0.18.
Reason: XYZ has stronger risk-adjusted expected return and better portfolio fit.
```

### 14.2 Warning Examples

```text
Closes a negative-P/L position.
Portfolio snapshot must be refreshed before execution.
Near take-profit protection could not be evaluated.
Candidate confidence is only medium.
Liquidity must be rechecked after close.
```

Human approval is per plan item.

Approval of one item must not approve the whole plan.

---

## 15. Anti-Churn Rules

v1 defaults:

```text
max_swaps_per_run = 1
minimum_swap_delta = 0.10
minimum_holding_period_days = optional
do_not_swap_if_position_near_take_profit = true
do_not_swap_if_data_quality_low = true
do_not_swap_if_candidate_confidence_below_threshold = true
partial_close_disabled = true
auto_execution_disabled = true
```

Additional recommended rule:

```text
do_not_swap_same_symbol = true
```

A same-symbol case should be treated later as increase/reduce/reposition logic, not as a v1 swap.

---

## 16. Learning Loop

`learn01_trade` must remain recommend-only.

It may evaluate:

```text
Did the opened candidate outperform the closed position?
Did skipped candidates outperform selected candidates?
Was minimum_swap_delta too low?
Was minimum_swap_delta too high?
Did close_then_open improve portfolio return?
Did swaps cause unnecessary churn?
Were negative-P/L closes justified?
Were near-TP protections helpful?
```

It may recommend changes to:

```text
favorability weights
minimum_swap_delta
max_swaps_per_run
cash buffer
risk penalties
near_take_profit_threshold_pct
```

It must not automatically change production thresholds.

Any threshold change requires Human approval.

---

## 17. Build Phases

### Phase 1 — Read-only scoring

Build:

```text
favorability score
liquidity model
portfolio snapshot parsing
candidate-vs-position comparison
```

Output only:

```text
hold
open_new
skip_candidate
```

No close suggestions yet.

---

### Phase 2 — allocation_plan JSON

Add:

```text
portfolio01_trade
allocation_plan output_type
trade_allocation_plans table
trade_allocation_plan_items table
```

Swaps may be marked as:

```text
swap_candidate_only
```

but not as executable actions.

---

### Phase 3 — Swap proposals

Enable:

```text
close_then_open
```

as proposal only.

Still no bridge execution.

Human Gate required.

---

### Phase 4 — Bridge support

Add execution sequence:

```text
close
verify close
refresh liquidity
open
verify order
store result
```

Add hard gates, error codes, and idempotency.

---

### Phase 5 — WebUI

Add allocation plan card in eToro panel.

Support:

```text
per-item approval
warnings
blockers
execution status
score breakdown
liquidity impact
```

---

### Phase 6 — Learning

Extend:

```text
score01_trade
learn01_trade
```

to evaluate allocation and swap outcomes historically.

---

## 18. Resolved Decisions

```text
Cadence:
  Daily first, after cockpit run.
  Intra-day price-triggered allocation is later.

Favorability scale:
  Normalized 0.00–1.00.

minimum_swap_delta:
  0.10 normalized score for v1.

max_swaps_per_run:
  1.

Partial close:
  Disabled in v1.

Cash buffer:
  5% of total portfolio value, minimum $50.

Negative-P/L positions:
  May be closed if swap_delta and gates pass.
  UI warning required.

Near take-profit protection:
  Enabled.
  Suggested threshold: <=5% remaining to TP.
```

---

## 19. Recommended v1 Standard

```text
portfolio01_trade = new role after sim01_trade
output_type = allocation_plan
auto_execution = disabled
partial_close = disabled
max_swaps_per_run = 1
minimum_swap_delta = 0.10 normalized score
cash_buffer_required = true
cash_buffer = max(5% of portfolio value, $50)
close_then_open requires Human approval
approval is per plan item
bridge must verify close before open
bridge must be idempotent
bridge must never execute same plan item twice
learn01_trade is recommend-only
```

---

## 20. Key Safety Principle

The allocation layer may recommend that capital should move.

Only the Human Gate may approve that move.

Only the bridge may execute it.

The bridge must always re-check portfolio state, position existence, instrument identity, and liquidity before each irreversible step.
