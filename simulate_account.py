#!/usr/bin/env python3
"""
Account simulation with position sizing.

Usage:
    python simulate_account.py                    # Default $50K, 2% risk
    python simulate_account.py --capital 100000   # Custom starting capital
    python simulate_account.py --risk 0.01        # 1% risk per trade
"""
import argparse
from datetime import datetime, timedelta
from src.backtest import BacktestEngine
from src.strategies.iron_condor import IronCondorConfig
import pandas as pd


def simulate_account(
    starting_capital: float = 50000,
    risk_pct: float = 0.02,
    max_vix: float = 20,
    days: int = 365,
):
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=days)
    start_date = start_dt.strftime('%Y-%m-%d')
    
    # Run backtest
    engine = BacktestEngine('SPX', start_date, end_date)
    config = IronCondorConfig(delta=0.15, wing_width=30, dte=2, max_vix=max_vix)
    result = engine.run_iron_condor_backtest(config)
    
    trades = pd.DataFrame(result['trades'])
    
    # Simulate account
    account = starting_capital
    peak = starting_capital
    max_dd = 0
    max_loss_per_contract = 30 * 100  # Wing width * 100
    
    equity_curve = [{'date': start_date, 'equity': starting_capital}]
    
    for _, trade in trades.iterrows():
        contracts = max(1, int(account * risk_pct / max_loss_per_contract))
        pnl_per_contract = trade['pnl'] / config.contracts
        trade_pnl = pnl_per_contract * contracts
        
        account += trade_pnl
        equity_curve.append({
            'date': trade['exit_date'],
            'equity': account,
            'pnl': trade_pnl,
            'contracts': contracts,
        })
        
        peak = max(peak, account)
        dd = (peak - account) / peak
        max_dd = max(max_dd, dd)
    
    return {
        'starting_capital': starting_capital,
        'ending_capital': account,
        'total_return_pct': (account - starting_capital) / starting_capital * 100,
        'max_drawdown_pct': max_dd * 100,
        'total_trades': len(trades),
        'win_rate': result['statistics']['win_rate'],
        'equity_curve': pd.DataFrame(equity_curve),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capital', type=float, default=50000)
    parser.add_argument('--risk', type=float, default=0.02)
    parser.add_argument('--max-vix', type=float, default=20)
    parser.add_argument('--days', type=int, default=365)
    args = parser.parse_args()
    
    result = simulate_account(
        starting_capital=args.capital,
        risk_pct=args.risk,
        max_vix=args.max_vix,
        days=args.days,
    )
    
    print(f"\n=== ACCOUNT SIMULATION ===")
    print(f"Strategy: SPX IC, 0.15δ, 30w, 2DTE, VIX≤{args.max_vix}")
    print(f"Risk per trade: {args.risk*100:.1f}%")
    print(f"Period: {args.days} days\n")
    
    print(f"Starting Capital: ${result['starting_capital']:,.0f}")
    print(f"Ending Capital:   ${result['ending_capital']:,.0f}")
    print(f"Total Return:     {result['total_return_pct']:.1f}%")
    print(f"Max Drawdown:     {result['max_drawdown_pct']:.1f}%")
    print(f"Total Trades:     {result['total_trades']}")
    print(f"Win Rate:         {result['win_rate']*100:.1f}%")
    
    # Monthly summary
    df = result['equity_curve']
    if 'date' in df.columns and len(df) > 1:
        df['date'] = pd.to_datetime(df['date'])
        df['month'] = df['date'].dt.to_period('M')
        monthly = df.groupby('month')['pnl'].sum().dropna()
        
        print(f"\n=== MONTHLY P&L ===")
        for month, pnl in monthly.items():
            print(f"  {month}: ${pnl:,.0f}")


if __name__ == '__main__':
    main()
