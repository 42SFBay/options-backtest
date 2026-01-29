#!/usr/bin/env python3
"""
Quick script to run the optimal strategy based on findings.

Usage:
    python run_optimal.py              # Run with defaults (1 year, VIX≤20)
    python run_optimal.py --days 90    # Last 90 days
    python run_optimal.py --no-vix     # Disable VIX filter
    python run_optimal.py --verbose    # Show individual trades
"""
import argparse
from datetime import datetime, timedelta
from src.backtest import BacktestEngine
from src.strategies.iron_condor import IronCondorConfig


def main():
    parser = argparse.ArgumentParser(description='Run optimal iron condor strategy')
    parser.add_argument('--days', type=int, default=365, help='Days of history')
    parser.add_argument('--symbol', default='SPX', help='SPX or QQQ')
    parser.add_argument('--delta', type=float, default=0.15, help='Delta')
    parser.add_argument('--wing', type=int, default=30, help='Wing width')
    parser.add_argument('--dte', type=int, default=2, help='DTE')
    parser.add_argument('--max-vix', type=float, default=20, help='Max VIX (0 to disable)')
    parser.add_argument('--no-vix', action='store_true', help='Disable VIX filter')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show trades')
    
    args = parser.parse_args()
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=args.days)
    start_date = start_dt.strftime('%Y-%m-%d')
    
    max_vix = None if args.no_vix or args.max_vix == 0 else args.max_vix
    
    print(f"Running {args.symbol} Iron Condor Backtest")
    print(f"Period: {start_date} to {end_date} ({args.days} days)")
    print(f"Config: delta={args.delta}, wing={args.wing}, dte={args.dte}")
    print(f"VIX Filter: {'None' if max_vix is None else f'≤{max_vix}'}")
    print("-" * 50)
    
    engine = BacktestEngine(args.symbol, start_date, end_date)
    config = IronCondorConfig(
        delta=args.delta,
        wing_width=args.wing,
        dte=args.dte,
        max_vix=max_vix,
    )
    
    result = engine.run_iron_condor_backtest(config)
    stats = result['statistics']
    
    print(f"\nResults:")
    print(f"  Total Trades:  {stats['total_trades']}")
    print(f"  Win Rate:      {stats['win_rate']*100:.1f}%")
    print(f"  Total P&L:     ${stats['total_pnl']:,.0f}")
    print(f"  Avg P&L:       ${stats['avg_pnl']:.0f}/trade")
    print(f"  Max Loss:      ${stats['max_loss']:,.0f}")
    print(f"  Sharpe Ratio:  {stats['sharpe']:.2f}")
    
    if args.verbose:
        print(f"\nTrades:")
        for t in result['trades']:
            status = "✓" if t['pnl'] > 0 else "✗"
            print(f"  {status} {t['entry_date']} → {t['expiry_date']}: "
                  f"${t['pnl']:,.0f} ({t['exit_reason']})")


if __name__ == '__main__':
    main()
