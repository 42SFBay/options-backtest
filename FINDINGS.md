# Options Backtesting Findings

## Summary (1-Year SPX Backtest: Jan 2025 - Jan 2026)

### Key Discovery: VIX Filtering is Critical

| Strategy | Trades | Win Rate | Total P&L | Avg P&L | Max Loss | Sharpe |
|----------|--------|----------|-----------|---------|----------|--------|
| Baseline (0.15δ, 30w, 2DTE) | 249 | 92.0% | $46,126 | $185 | -$2,658 | 0.31 |
| + VIX ≤ 25 filter | 229 | 96.9% | $62,849 | $274 | -$2,658 | 0.69 |
| + VIX ≤ 20 filter | 186 | 98.4% | $57,390 | $309 | -$2,638 | **1.32** |

**VIX ≤ 20 filter improves Sharpe by 4.2x while maintaining 98%+ win rate.**

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

## Next Steps

1. Get real historical options data
2. Test entry time optimization
3. Add trend day detection
4. Build position sizing based on account size
5. Add live trading integration
