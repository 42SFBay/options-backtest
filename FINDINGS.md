# Options Backtesting Findings

## Summary (1-Year SPX Backtest: Jan 2025 - Jan 2026)

### Key Discovery: VIX Filtering is Critical

**Corrected Results (1-Year Backtest, Jan 2025 - Jan 2026):**

| Strategy | Trades | Win Rate | Total P&L | Avg P&L | Sharpe |
|----------|--------|----------|-----------|---------|--------|
| Baseline (0.15δ, 30w, 2DTE) | 249 | 92.0% | $126,023 | $506 | 0.76 |
| + VIX ≤ 25 filter | 229 | 93.0% | $121,812 | $532 | 0.88 |
| + VIX ≤ 20 filter | 186 | 94.6% | $107,636 | $579 | **1.22** |
| + VIX ≤ 17 filter | 123 | 95.9% | $72,076 | $586 | 1.23 |

**VIX thresholds trade off volume vs quality:**
- VIX ≤ 20: Best balance of P&L ($108K) and Sharpe (1.22)
- VIX ≤ 17: Higher win rate (96%), slightly better Sharpe, but 34% fewer trades

**Why VIX filtering works:**
| VIX Range | Days | Big Moves (>1%) |
|-----------|------|-----------------|
| 0-18      | 153  | 8%              |
| 18-20     | 35   | 31%             |
| 20-25     | 43   | 37%             |
| 25+       | 20   | 65%             |

When VIX > 20, you're 4x more likely to see a 1%+ move that blows through your strikes.

### Optimal Configuration

```
Symbol: SPX
Strategy: Iron Condor
Delta: 0.15 (both legs)
Wing Width: 30 points
DTE: 2 days
VIX Filter: Skip if VIX > 20

Expected Results:
- Win Rate: ~98%
- Avg P&L per trade: ~$309
- Annual P&L: ~$57,000 (186 trades)
- Max Drawdown: ~$2,600
- Sharpe: 1.32
```

### What Doesn't Help Much

1. **0 DTE** - 32% win rate, huge losses. Avoid.
2. **Day-of-week filtering** - Marginal improvement, not worth the lost trades.
3. **Profit targets / Stop losses** - Positions expire before triggering on 1-2 DTE.

### What We Haven't Tested Yet

1. Entry time optimization (7:15 AM vs other times)
2. Trend day detection (avoid iron condors on trend days)
3. Real options data (currently using Black-Scholes simulation)
4. Correlation with market regimes
5. Different expiration cycles (weeklies vs monthlies)

## Data Limitations

- Using simulated options prices via Black-Scholes + VIX-derived IV
- Real bid/ask spreads not modeled
- Slippage not included
- For production: need ThetaData or OptionsDX for actual historical chains

## Account Simulation (VIX ≤ 20, 2% Risk/Trade)

| Starting | Ending | Return | Max DD |
|----------|--------|--------|--------|
| $25,000  | $132,636 | 431% | 6.7% |
| $50,000  | $157,636 | 215% | 3.9% |
| $100,000 | $207,636 | 108% | 2.2% |

**Key observation:** April 2025 crash was completely avoided (0 trades that month due to VIX > 20).

## Next Steps

1. Get real historical options data (ThetaData/OptionsDX)
2. Test entry time optimization (needs intraday data)
3. Add live trading integration (OptionAlpha API)
4. Correlation analysis with market regimes

## Hypothesis Testing Results

### H1: Delta Optimization
- 0.15 delta optimal for risk-adjusted returns (Sharpe 1.22)
- Lower delta = safer (0.08δ = 98% win), higher = more P&L but worse Sharpe

### H2: Wing Width
- 25-30pt wings optimal (Sharpe 1.22-1.23)
- Wider = more premium but diminishing Sharpe

### H3: DTE
- **2 DTE is clearly optimal** (Sharpe 1.22)
- 1 DTE too risky (Sharpe 0.55), 3+ loses edge

### H4: Day-of-Week
- Thursday notably weaker ($346/trade vs $550-680 other days)
- Skip Friday marginal improvement, not conclusive

### H5: Aggressive in Calm Markets
- VIX ≤ 15 + 0.25δ = $929/trade, but only 26 trades/year
- Valid secondary strategy for low-vol periods

### H6: Combined Optimizations
- Best combined: δ0.18, w35, VIX≤20 = $138K/year, Sharpe 1.13
- But baseline δ0.15, w30 has better Sharpe (1.22)

### H7: Seasonality
- No significant monthly patterns
- All months profitable with VIX filter

### H8: Losing Streaks
- Max consecutive losses: 2
- Losses isolated, not clustered
- VIX filter effectively prevents drawdowns

## Exit Strategy Analysis

Tested profit targets (PT) and stop losses (SL) on various DTEs:

| Strategy | Win Rate | P&L | Sharpe |
|----------|----------|-----|--------|
| Hold to expiry | 89% | $90K | 0.59 |
| PT 50% + SL 1x | 90% | $69K | 0.63 |

**Conclusion:** Exit rules provide marginal improvement. On 2 DTE, positions resolve too fast for exits to trigger meaningfully.

## Advanced Filters

### Trend Direction (SMA Filter) - KEY FINDING
| Condition | Win Rate | Sharpe |
|-----------|----------|--------|
| Above SMA20 | 96% | 1.19 |
| Below SMA20 | 92% | 2.67* |
*Low sample (13 trades)

### Optimized Filter Stack
| Filters | Trades | Win Rate | Sharpe |
|---------|--------|----------|--------|
| VIX≤20 only | 137 | 96% | 1.24 |
| VIX≤17 + SMA20 | 102 | **97%** | **1.41** |
| VIX≤20 + SMA10 | 109 | 96% | 1.35 |

## Final Optimized Strategy

```
SPX Iron Condor
Delta: 0.15
Wing: 30 points  
DTE: 2 days

FILTERS:
1. VIX ≤ 17
2. Price > 20-day SMA

EXPECTED RESULTS:
- Win Rate: 97%
- Sharpe: 1.41
- ~102 trades/year
- ~$62K annual P&L (1 contract)
```

### VIX-Based Position Sizing
| VIX Range | Avg P&L | Suggested Size |
|-----------|---------|----------------|
| <14 | $689 | 1.5x |
| 14-16 | $539 | 1.0x |
| 16-18 | $619 | 1.25x |

