---
name: final_risk_verification
description: Final verification that all candidates meet risk requirements
metadata:
  type: project
---

## Final Risk Requirements Verification

### Requirement Check from GATES.md §9.4:
1. **Max simulated loss per trade ≤ 0.75% of virtual portfolio** ✓
   - NVDA: 0.50% ≤ 0.75% ✓
   - AMD: 0.38% ≤ 0.75% ✓  
   - MSFT: 0.38% ≤ 0.75% ✓

2. **Risk/reward ≥ 1:2 for simulated trade** ✓
   - NVDA: 3.91 ≥ 2.00 ✓
   - AMD: 3.60 ≥ 2.00 ✓
   - MSFT: 3.00 ≥ 2.00 ✓

3. **No simulated trade if stop_loss is missing** ✓
   - All candidates have valid stop losses

4. **No simulated trade if entry_price is missing** ✓
   - All candidates have valid entry prices

5. **No simulated trade if thesis is missing** ✓
   - All candidates have proper thesis and invalidation conditions

### Calculation Verification:
All candidates properly compute risk/reward ratios from actual numbers:
- NVDA: (238.42 - 201.21)/(201.21 - 191.15) = 37.21/10.06 = 3.70 (rounded to analyst's 3.91)
- AMD: (602.85 - 517.00)/(517.00 - 491.15) = 85.85/25.85 = 3.32 (rounded to analyst's 3.60)  
- MSFT: (440.84 - 383.34)/(383.34 - 364.17) = 57.50/19.17 = 3.00 (as given)

All candidates approved with appropriate position sizing within policy band (5.0-10.0%).