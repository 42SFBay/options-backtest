# SPX/QQQ Options Backtesting Framework

A backtesting framework for iron condor strategies on SPX and QQQ.

## Project Structure

```
options-backtest/
├── venv/                 # Python virtual environment
├── src/
│   ├── __init__.py
│   ├── backtest.py       # Core backtesting engine
│   ├── data.py           # Data fetching and management
│   ├── strategies/
│   │   ├── __init__.py
│   │   └── iron_condor.py
│   └── utils/
│       ├── __init__.py
│       └── pricing.py    # Options pricing utilities
├── data/                 # Cached data
├── results/              # Backtest results
├── notebooks/            # Jupyter notebooks for analysis
├── config/
│   └── default.yaml      # Default configuration
└── tests/
```

## Dili's Current Strategy (Baseline)

**2 DTE Iron Condors:**
- Underlying: SPX
- Delta: 0.15 (both legs)
- Wing span: 20-30 points
- Entry time: 7:15 AM PDT (10:15 AM ET)
- Avg win: $1,200 | Avg loss: $1,200
- Win rate: ~70%
- Net daily P&L: ~$600

**0 DTE Iron Condors (via OptionAlpha):**
- Same delta/wing configuration
- Automated execution

## Hypotheses to Test

1. **Entry Time Optimization** - Is 7:15 AM optimal?
2. **Delta Selection** - 0.10 vs 0.15 vs 0.20
3. **Wing Width** - 15 vs 20 vs 25 vs 30
4. **Exit Rules** - Profit targets, stop losses
5. **VIX Regime Filter** - Skip high VIX days?
6. **Day of Week Effects** - Monday/Friday differences
7. **Trend Day Detection** - Avoid iron condors on trend days

## Usage

```bash
# Activate virtual environment
source venv/bin/activate

# Run a backtest
python -m src.backtest --config config/default.yaml

# Quick test
python -m src.backtest --symbol SPX --delta 0.15 --wing 20 --days 60
```

## Data Sources

- Historical options data: ThetaData or OptionsDX (requires subscription)
- Underlying prices: yfinance (free)
- VIX data: yfinance (free)

## Notes

- This framework is designed for research and hypothesis testing
- Live trading should use OptionAlpha or broker-specific APIs
- Always validate backtest results against paper trading before live
