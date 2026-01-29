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

## Iteration 4: 0 DTE Rescue Attempt (20:45 UTC)

**Finding: 0 DTE is hopeless, cannot be rescued**

| 0 DTE Config | Trades | Win Rate | Sharpe |
|--------------|--------|----------|--------|
| No filters | 251 | 0.4% | -2.02 |
| Skip Thu + VIX>18 | 124 | 0.8% | -1.81 |
| VIX 14-16 only | 51 | 0.0% | -1.92 |

Even aggressive filtering can't save 0 DTE. Abandon this line.

---

## Iteration 5: Delta + Wing Optimization (20:50 UTC)

**Finding: Delta 0.14 beats 0.15!**

| Delta | Wing | Win Rate | Sharpe | P&L |
|-------|------|----------|--------|-----|
| **0.14** | **30** | **99.3%** | **2.99** | $166K |
| 0.14 | 35 | 99.3% | 2.97 | $184K |
| 0.15 | 35 | 97.3% | 2.85 | $197K |
| 0.15 | 30 | 97.3% | 2.81 | $177K |

**New best configuration:**
- Delta: 0.14 (was 0.15)
- Wing: 30pt
- Skip: Thursday + VIX > 20
- Sizing: 2x when VIX 14-18
- **Sharpe: 2.99** (was 2.81)
- **Win Rate: 99.3%** (was 97.3%)

---

## Iteration 6: Multi-Year Validation (20:55 UTC)

**Finding: Strategy holds up but Sharpe degrades over longer periods**

| Period | 1x Sharpe | 2x Sharpe | 2x P&L |
|--------|-----------|-----------|--------|
| 1 year | 2.21 | **4.55** | $185K |
| 2 years | 0.39 | 1.14 | $306K |
| 3 years | 0.27 | 0.93 | $413K |

**Interpretation:**
- 2024 had more losses (win rate drops from 99% to 87%)
- 2x sizing still roughly doubles Sharpe
- Still profitable over 3 years, but 2025 was exceptionally good

**NEW BEST CONFIG (validated):**
```
delta: 0.14
wing: 30
dte: 2
skip: Thursday, VIX > 20
sizing: 2x always

1-Year Results:
- Win Rate: 99.3%
- Sharpe: 4.55
- P&L: $185K (2 contracts)
```

## Iteration 7: VIX Thresholds + Day-of-Week (21:00 UTC)

**VIX Skip Threshold:**
| Threshold | Trades | Win Rate | Sharpe |
|-----------|--------|----------|--------|
| VIX > 17 | 96 | 99.0% | 4.03 |
| VIX > 18 | 122 | 99.2% | 4.22 |
| VIX > 19 | 139 | 99.3% | 4.46 |
| **VIX > 20** | 150 | 99.3% | **4.55** |
| VIX > 22 | 170 | 98.2% | 2.96 |

**Day-of-Week Skip (1-Year):**
| Skip | Trades | Win Rate | Sharpe |
|------|--------|----------|--------|
| Thu only | 150 | 99.3% | 4.55 |
| **Thu+Fri** | 115 | **100%** | **9.88** |

**BUT Multi-Year Tells Different Story:**
| Period | Thu Only | Thu+Fri |
|--------|----------|---------|
| 1Y P&L | $185K | $144K |
| 5Y P&L | $713K | $536K |
| 5Y Sharpe | 2.65 | 2.58 |

**Conclusion:** Thu+Fri's 100% in 1Y was luck. Long-term, Thu only = more P&L, similar Sharpe.

---

## Current Best Configs

**For Max P&L (Thu only):**
```
delta: 0.14, wing: 30, dte: 2
skip: Thursday, VIX > 20
sizing: 2x
5Y: $713K P&L, Sharpe 2.65
```

**For Max Short-Term Sharpe (Thu+Fri):**
```
delta: 0.14, wing: 30, dte: 2
skip: Thursday, Friday, VIX > 20
sizing: 2x
1Y: $144K P&L, Sharpe 9.88
```

## Iteration 8: Monthly Seasonality (21:05 UTC)

**Best/Worst Months (3Y data):**
- **100% WR**: May, June, October
- **Lowest WR**: January (93.6%), December (94.1%)

**Monthly Filter Tests (3Y):**
| Filter | Trades | Win Rate | Sharpe | P&L |
|--------|--------|----------|--------|-----|
| No filter | 507 | 96.6% | 2.57 | $547K |
| Skip Jan | 460 | 97.0% | 2.76 | $502K |
| Skip Jan+Feb+Dec | 372 | 97.6% | 3.14 | $410K |
| Only May-Oct | 269 | 98.1% | 3.48 | $302K |

**Tradeoff**: More selective = better Sharpe but less P&L

---

## Summary of All Findings

| Config | 1Y Sharpe | 3Y Sharpe | 3Y P&L |
|--------|-----------|-----------|--------|
| Base (δ0.14, 2x, Thu, VIX>20) | 4.55 | 2.57 | $547K |
| + Skip Jan | - | 2.76 | $502K |
| + Skip Jan+Feb+Dec | - | 3.14 | $410K |
| + Thu+Fri (not Thu only) | 9.88 | 2.54 | $414K |

## Iteration 9: VIX Band Discovery (21:15 UTC)

**MAJOR FINDING: VIX 16-20 band = near-perfect win rate**

| Period | VIX 16-20 | Baseline (≤20) |
|--------|-----------|----------------|
| 1Y WR | **100%** | 99.3% |
| 1Y Sharpe | **8.46** | 4.55 |
| 1Y P&L | $122K | $185K |
| 3Y WR | **99.1%** | 96.6% |
| 3Y Sharpe | **5.13** | 2.57 |
| 3Y P&L | $269K | $547K |

**Interpretation:**
- VIX 16-20 is the "sweet spot" - elevated but not dangerous
- Trade fewer times but with near-certainty
- 2x Sharpe but ~50% P&L

**SPX vs QQQ:**
- SPX: Sharpe 4.55, P&L $185K
- QQQ: Sharpe 1.52, P&L $20K
- **SPX wins decisively**

---

## Three Strategy Variants

**1. MAX P&L (Baseline)**
```
VIX ≤ 20, Skip Thu
3Y: $547K P&L, Sharpe 2.57, 96.6% WR
```

**2. BALANCED (Skip January)**
```
VIX ≤ 20, Skip Thu + January
3Y: $502K P&L, Sharpe 2.76, 97.0% WR
```

**3. MAX SHARPE (VIX 16-20 only)**
```
VIX 16-20 only, Skip Thu
3Y: $269K P&L, Sharpe 5.13, 99.1% WR
```

## Iteration 10: SMA + Momentum Filters (21:25 UTC)

**SMA Filter Tests (3Y):**
| Filter | Trades | Win Rate | Sharpe | P&L |
|--------|--------|----------|--------|-----|
| Baseline | 507 | 96.6% | 2.57 | $547K |
| Above SMA20 | 411 | 96.6% | 2.47 | $443K |
| **Below SMA20** | 105 | 97.1% | **3.32** | $114K |

**Momentum Filter Tests (3Y):**
| Filter | Trades | Win Rate | Sharpe | P&L |
|--------|--------|----------|--------|-----|
| Baseline | 507 | 96.6% | 2.57 | $547K |
| **Downtrend only** (mom<0) | 167 | **98.2%** | **2.95** | $186K |
| Uptrend only (mom>0) | 344 | 95.9% | 2.44 | $366K |

**Insight:** Trading during pullbacks (below SMA or negative momentum) has better risk-adjusted returns.

---

## Filter Combinations Tested

| Config | Trades | WR | Sharpe | P&L |
|--------|--------|-----|--------|-----|
| VIX ≤20 + Thu (baseline) | 507 | 96.6% | 2.57 | $547K |
| **VIX 16-20 + Thu** | 228 | 99.1% | **5.13** | $269K |
| VIX ≤20 + Below SMA20 | 105 | 97.1% | 3.32 | $114K |
| VIX 16-20 + Gap<0.5% | 184 | 98.9% | 4.66 | $215K |

---

## Questions for Dili

1. **Which variant?** Max P&L vs Balanced vs Max Sharpe?
2. **VIX 16-20 for conservative mode?** Near-perfect but less trades
3. **Ready for paper trading?**

---
