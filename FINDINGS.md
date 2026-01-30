# Options Backtest Findings

**Date:** 2026-01-30
**Period Tested:** 2021-01-01 to 2026-01-01 (5 years)
**Hypotheses Tested:** 70+

## Executive Summary

After testing 70+ configurations, the **optimal strategy** balancing P&L and risk is:

```
Config: thu_vix25_d25_w70
- Delta: 0.25
- Wing Width: 70
- DTE: 2
- Skip: Thursday + VIX > 25

Results:
- P&L: $1,108,693
- Win Rate: 89.5%
- Sharpe: 1.00
- Trades: 861
```

## Top Configurations

### By P&L (Absolute Maximum)

| Rank | Config | P&L | Trades | Win Rate | Sharpe |
|------|--------|-----|--------|----------|--------|
| 1 | delta0.25_wing70 | $1,354,054 | 1253 | 83.5% | 0.70 |
| 2 | delta0.28_wing60 | $1,354,921 | 1253 | 81.2% | 0.67 |
| 3 | delta0.22_wing100 | $1,347,416 | 1253 | 85.4% | 0.68 |
| 4 | delta0.25_wing70 | $1,354,054 | 1253 | 83.5% | 0.70 |

### By Sharpe (Risk-Adjusted, >500 trades)

| Rank | Config | Sharpe | P&L | Win Rate |
|------|--------|--------|-----|----------|
| 1 | maxsharpe_vix1620_wedthu | 2.56 | $152,149 | 98.2% |
| 2 | conservative_thu_vix20_d18_w50 | 1.27 | $548,254 | 93.4% |
| 3 | thu_vix25_d25_w70 | 1.00 | $1,108,693 | 89.5% |
| 4 | wedthu_d16_w40 | 0.97 | $494,595 | 93.8% |

### Best Balance (P&L > $1M, Sharpe > 0.85)

| Config | P&L | Win Rate | Sharpe |
|--------|-----|----------|--------|
| thu_vix25_d25_w70 | $1,108,693 | 89.5% | 1.00 |
| balanced_thu_d22_w60 | $1,062,265 | 89.7% | 0.91 |
| high_pnl_thu_d25_w60 | $1,167,821 | 87.5% | 0.88 |

## Key Findings

### What Works ✅

1. **Skip Thursday** - Single biggest improvement
   - Win rate: +10%
   - Sharpe: +30%
   - P&L: Minimal impact

2. **Higher Delta (0.22-0.25)** - More premium collected
   - 0.15 → 0.25 = +80% P&L
   - Tradeoff: Lower win rate

3. **Wider Wings (60-70)** - More spread protection
   - Wing 30 → 70 = +60% P&L
   - Minimal win rate impact

4. **Skip VIX > 25** - Avoid extreme volatility
   - Sharpe: +15%
   - P&L: -10% (acceptable tradeoff)

5. **DTE 2** - Optimal time decay
   - DTE 2 beats DTE 1, 3, 5, 7

### What Doesn't Work ❌

1. **DTE 0** - Catastrophic (-$2.3M loss, 0.2% WR)
2. **DTE 7** - Too much time risk
3. **Skip multiple days** - Reduces P&L too much
4. **Aggressive VIX filters** - Kills trade count
5. **Momentum filters** - No significant improvement

### Year-by-Year Performance

Using delta0.22, wing60 (no filters):

| Year | P&L | Trades | Win Rate | Sharpe |
|------|-----|--------|----------|--------|
| 2021 | $284,967 | 249 | 92.8% | 1.29 |
| 2022 | $155,359 | 249 | 75.1% | 0.37 |
| 2023 | $214,605 | 248 | 85.5% | 0.94 |
| 2024 | $226,473 | 249 | 85.1% | 0.74 |
| 2025 | $244,891 | 247 | 83.4% | 0.67 |

**Note:** Even in 2022 (bear market), strategy remained profitable.

## Recommendations

### For Maximum P&L
```
Delta: 0.25
Wing: 70
DTE: 2
Filters: None
Expected: $1.35M/5yr, 83.5% WR
```

### For Best Risk-Adjusted (Recommended)
```
Delta: 0.25
Wing: 70
DTE: 2
Filters: Skip Thursday, Skip VIX > 25
Expected: $1.11M/5yr, 89.5% WR, 1.00 Sharpe
```

### For Conservative/High Win Rate
```
Delta: 0.18
Wing: 50
DTE: 2
Filters: Skip Thursday, Skip VIX > 20
Expected: $548K/5yr, 93.4% WR, 1.27 Sharpe
```

## Next Steps

1. Paper trade the recommended config
2. Monitor for 30 days
3. Validate against out-of-sample data
4. Consider position sizing based on account size
