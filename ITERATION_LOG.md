# Rules Iteration Log

## Session: 2026-01-29

### Starting Point
- **Best so far**: Combined rules (Sharpe 2.07, 97.3% win rate, 150 trades)
- **Baseline**: Fixed 0.15/0.15 (Sharpe 0.70, 85.9% win rate, 249 trades)

### Iteration Queue
1. [x] Test different PT/SL combinations for VIX sweet spot
2. [x] Test tighter skip conditions vs looser
3. [ ] Position sizing based on confidence
4. [ ] Monthly seasonality integration
5. [x] Test 0.20/0.20, 0.25/0.25, 0.10/0.10 variants
6. [ ] Combine best filters with dynamic PT/SL

---

## Iteration 1: Skip Conditions (19:55 UTC)

**Finding: Skip conditions are the ONLY thing that matters for 2 DTE**

| Skip Config | Trades | Win Rate | Sharpe |
|-------------|--------|----------|--------|
| Thu+VIX≤17+gap<0.3% | 96 | **98.9%** | **2.11** |
| Thu+VIX≤20 | 150 | 97.3% | 2.07 |
| Thu only | 201 | 95.5% | 1.10 |
| No skips | 249 | 87.5% | 0.69 |

**Key insight**: Thursday skip alone gives huge boost (0.69 → 1.10 Sharpe)

---

## Iteration 2: PT/SL Doesn't Matter for 2 DTE (20:00 UTC)

**Finding: All 150 trades exit at EXPIRY, not via PT/SL**

Tested: 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, None
Result: ALL configurations produce identical Sharpe (2.07)

**Why**: 2 DTE positions don't have time for intraday exits. They expire before PT/SL triggers.

**DTE comparison with skip filters:**
| DTE | Win Rate | Sharpe | PT/SL Triggered? |
|-----|----------|--------|------------------|
| 0 | 0.7% | -1.91 | No (disaster) |
| 1 | 93.4% | 0.73 | No |
| 2 | 97.3% | 2.07 | No |
| 3 | 85.2% | 0.67 | YES (116 PT, 20 SL) |

---

## Decisions Made

1. **Keep 2 DTE as optimal** - Higher DTE loses edge, 0 DTE is terrible
2. **PT/SL is irrelevant for 2 DTE** - Don't complicate rules with it
3. **Focus on skip conditions** - That's where the alpha is
4. **Thursday is poison** - Skipping it alone improves Sharpe by 60%

---

## Iteration 3: Position Sizing (20:20 UTC)

**Finding: Dynamic sizing based on VIX significantly improves results**

| Strategy | P&L | Sharpe | Avg Size |
|----------|-----|--------|----------|
| Baseline 1x | $95K | 2.07 | 1.0x |
| **2x when VIX 14-18** | **$177K** | **2.81** | 1.8x |
| 2x when VIX 15-18 | $164K | 2.44 | 1.7x |
| Progressive (2x calm, 3x 16-18) | $226K | 2.39 | 2.3x |

**Best risk-adjusted**: 2x sizing when VIX 14-18 → Sharpe jumps from 2.07 to 2.81

---

## Questions for Dili

1. **Risk tolerance for sizing?** 
   - Conservative: 2x in VIX 14-18 only (Sharpe 2.81)
   - Aggressive: Progressive 2x/3x (P&L $226K but Sharpe 2.39)
   
2. **Should we test 3+ DTE with dynamic PT/SL?** - That's where PT/SL actually matters, but Sharpe is worse

3. **Interest in 0 DTE rescue?** - Current 0 DTE is -1.91 Sharpe; could test heavier filtering

---
