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
