#!/usr/bin/env python3
"""
Comprehensive risk analysis for strategy comparison.
Answers: Which strategy is truly BEST considering drawdown, avg P&L, max risk?
"""
import sys
sys.path.insert(0, '/home/ubuntu/clawd/projects/options-backtest')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from src.data import DataManager
from src.utils.pricing import iron_condor_pnl_at_expiry


def load_market_data(start: str, end: str) -> pd.DataFrame:
    """Load SPX market data with VIX"""
    dm = DataManager()
    
    # Get SPX prices
    prices = dm.get_underlying_prices('SPX', start, end)
    prices = prices.reset_index()
    prices.columns = [c.lower() for c in prices.columns]
    
    # Get VIX
    vix = dm.get_vix_data(start, end)
    vix = vix.reset_index()
    vix.columns = [c.lower() for c in vix.columns]
    vix = vix.rename(columns={'close': 'vix_close'})
    vix = vix[['date', 'vix_close']]
    
    # Normalize dates - remove timezone
    prices['date'] = pd.to_datetime(prices['date']).dt.tz_localize(None).dt.normalize()
    vix['date'] = pd.to_datetime(vix['date']).dt.tz_localize(None).dt.normalize()
    
    df = prices.merge(vix, on='date', how='inner')
    return df


def simulate_strategy(
    df: pd.DataFrame,
    filters: Dict,
    delta: float,
    wing: int,
    contracts: int = 10,
    credit_per_spread: float = 1.0  # Simplified: $1 per $1 of wing width
) -> List[Dict]:
    """
    Simulate iron condor trades with given parameters.
    Returns list of trade results.
    """
    trades = []
    
    for i, row in df.iterrows():
        # Apply filters
        dow = row['date'].weekday()  # 0=Mon, 3=Thu, 4=Fri
        
        # Day of week filter
        if 'dow' in filters:
            if dow not in filters['dow']:
                continue
        
        # VIX filter
        if 'vix_above' in filters:
            if row['vix_close'] < filters['vix_above']:
                continue
        
        if 'vix_below' in filters:
            if row['vix_close'] > filters['vix_below']:
                continue
        
        # Gap filter
        if 'gap_below' in filters:
            gap = abs(row['open'] - row['prev_close']) / row['prev_close'] * 100
            if gap > filters['gap_below']:
                continue
        
        # Simplified IC simulation
        spot = row['close']
        
        # Estimate strikes based on delta (rough approximation)
        # Higher delta = closer to money
        atm_distance = spot * (1 - delta) * 0.1  # Rough ATM distance based on delta
        
        put_short = spot - atm_distance
        put_long = put_short - wing
        call_short = spot + atm_distance
        call_long = call_short + wing
        
        # Credit received (simplified)
        credit = wing * 0.3 * contracts * 100  # ~30% of max risk as credit
        
        # Max risk
        max_risk = (wing * 100 * contracts) - credit
        
        # P&L calculation at expiry (0DTE - same day)
        # For simplicity: win if price stays between short strikes
        day_move = row['high'] - row['low']
        breached = (row['low'] < put_short) or (row['high'] > call_short)
        
        if breached:
            # Loss - simplified to max loss
            # In reality would be partial based on where it closed
            if row['close'] < put_short:
                loss = (put_short - max(row['close'], put_long)) * 100 * contracts
            elif row['close'] > call_short:
                loss = (min(row['close'], call_long) - call_short) * 100 * contracts
            else:
                loss = 0  # Breached but recovered
            pnl = credit - loss
        else:
            pnl = credit
        
        trades.append({
            'date': row['date'],
            'spot': spot,
            'vix': row['vix_close'],
            'credit': credit,
            'max_risk': max_risk,
            'pnl': pnl,
            'win': pnl > 0
        })
    
    return trades


def analyze_results(trades: List[Dict], name: str) -> Dict:
    """Compute comprehensive risk metrics"""
    if not trades:
        return None
    
    pnls = [t['pnl'] for t in trades]
    pnl_series = pd.Series(pnls)
    cumulative = pnl_series.cumsum()
    
    # Basic stats
    total_pnl = sum(pnls)
    avg_pnl = np.mean(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    
    # Max drawdown (peak to trough)
    peak = cumulative.expanding().max()
    drawdown = cumulative - peak
    max_dd = drawdown.min()
    
    # Find when max DD occurred
    max_dd_idx = drawdown.idxmin()
    max_dd_date = trades[max_dd_idx]['date'] if max_dd_idx < len(trades) else None
    
    # Consecutive losses
    consecutive_losses = 0
    max_consecutive_losses = 0
    for p in pnls:
        if p <= 0:
            consecutive_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        else:
            consecutive_losses = 0
    
    # Risk metrics
    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    max_loss = min(pnls) if pnls else 0
    max_win = max(pnls) if pnls else 0
    
    # Profit factor
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # Risk-adjusted metrics
    std_pnl = np.std(pnls) if len(pnls) > 1 else 0
    sharpe = (avg_pnl / std_pnl) * np.sqrt(252) if std_pnl > 0 else 0
    
    # Sortino (downside deviation only)
    downside_pnls = [p for p in pnls if p < 0]
    downside_std = np.std(downside_pnls) if len(downside_pnls) > 1 else 0
    sortino = (avg_pnl / downside_std) * np.sqrt(252) if downside_std > 0 else float('inf')
    
    # Max risk per trade (from trades)
    max_risk_per_trade = np.mean([t['max_risk'] for t in trades])
    
    # Recovery factor (total profit / max drawdown)
    recovery = abs(total_pnl / max_dd) if max_dd != 0 else float('inf')
    
    return {
        'name': name,
        'trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': len(wins) / len(trades) * 100,
        'total_pnl': total_pnl,
        'avg_pnl': avg_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'max_win': max_win,
        'max_loss': max_loss,
        'max_drawdown': max_dd,
        'max_dd_date': max_dd_date,
        'max_consecutive_losses': max_consecutive_losses,
        'sharpe': sharpe,
        'sortino': min(sortino, 99),  # Cap for display
        'profit_factor': min(profit_factor, 99),
        'max_risk_trade': max_risk_per_trade,
        'recovery_factor': min(recovery, 99),
    }


def print_comparison(results: List[Dict]):
    """Print comprehensive comparison table"""
    print("\n" + "="*130)
    print("COMPREHENSIVE STRATEGY COMPARISON (5 Years: 2021-01-29 to 2026-01-29)")
    print("="*130)
    
    # Table 1: Core Performance
    print("\n📊 CORE PERFORMANCE")
    print("-"*100)
    print(f"{'Strategy':<28} {'Trades':>6} {'WR%':>6} {'Total P&L':>12} {'Avg P&L':>9} {'Max DD':>11} {'Sharpe':>7}")
    print("-"*100)
    
    for r in sorted(results, key=lambda x: x['sharpe'], reverse=True):
        print(f"{r['name']:<28} {r['trades']:>6} {r['win_rate']:>5.1f}% "
              f"${r['total_pnl']:>10,.0f} ${r['avg_pnl']:>7,.0f} "
              f"${r['max_drawdown']:>10,.0f} {r['sharpe']:>7.2f}")
    
    # Table 2: Risk Analysis
    print("\n⚠️  RISK ANALYSIS")
    print("-"*100)
    print(f"{'Strategy':<28} {'Max Loss':>10} {'Max Risk':>10} {'Max Con.L':>9} {'Sortino':>8} {'PF':>6} {'Recovery':>8}")
    print("-"*100)
    
    for r in sorted(results, key=lambda x: x['max_drawdown'], reverse=True):  # Less negative first
        print(f"{r['name']:<28} ${r['max_loss']:>9,.0f} ${r['max_risk_trade']:>9,.0f} "
              f"{r['max_consecutive_losses']:>9} {r['sortino']:>8.2f} {r['profit_factor']:>6.1f} {r['recovery_factor']:>8.2f}")
    
    # Table 3: Win/Loss Breakdown
    print("\n💰 WIN/LOSS BREAKDOWN")
    print("-"*90)
    print(f"{'Strategy':<28} {'Wins':>5} {'Losses':>6} {'Avg Win':>10} {'Avg Loss':>10} {'Max Win':>10}")
    print("-"*90)
    
    for r in results:
        print(f"{r['name']:<28} {r['wins']:>5} {r['losses']:>6} "
              f"${r['avg_win']:>9,.0f} ${r['avg_loss']:>9,.0f} ${r['max_win']:>9,.0f}")
    
    # Composite scoring
    print("\n" + "="*80)
    print("🏆 COMPOSITE RANKING")
    print("="*80)
    print("\nWeights: Sharpe(30%) + Sortino(20%) + WinRate(20%) + MaxDD(15%) + ProfitFactor(15%)")
    print()
    
    # Normalize metrics
    max_sharpe = max(r['sharpe'] for r in results)
    max_sortino = max(min(r['sortino'], 20) for r in results)  # Cap sortino
    max_wr = max(r['win_rate'] for r in results)
    min_dd = min(r['max_drawdown'] for r in results)  # Most negative
    max_pf = max(min(r['profit_factor'], 20) for r in results)
    
    for r in results:
        # Normalize to 0-1 scale
        norm_sharpe = r['sharpe'] / max_sharpe if max_sharpe > 0 else 0
        norm_sortino = min(r['sortino'], 20) / max_sortino if max_sortino > 0 else 0
        norm_wr = r['win_rate'] / max_wr if max_wr > 0 else 0
        norm_dd = 1 - (r['max_drawdown'] / min_dd) if min_dd != 0 else 0  # Invert (less negative = better)
        norm_pf = min(r['profit_factor'], 20) / max_pf if max_pf > 0 else 0
        
        # Weighted composite
        r['composite'] = (
            norm_sharpe * 0.30 +
            norm_sortino * 0.20 +
            norm_wr * 0.20 +
            norm_dd * 0.15 +
            norm_pf * 0.15
        )
    
    ranked = sorted(results, key=lambda x: x['composite'], reverse=True)
    
    for i, r in enumerate(ranked, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        print(f"{medal} {i}. {r['name']:<30} Score: {r['composite']:.3f}")
    
    # Final recommendation
    best = ranked[0]
    print("\n" + "="*80)
    print("✅ RECOMMENDATION")
    print("="*80)
    print(f"\nBest Overall: {best['name']}")
    print(f"  • {best['trades']} trades over 5 years ({best['trades']/5:.0f}/year)")
    print(f"  • Win Rate: {best['win_rate']:.1f}% ({best['losses']} losses total)")
    print(f"  • Avg P&L: ${best['avg_pnl']:,.0f} per trade")
    print(f"  • Max Drawdown: ${best['max_drawdown']:,.0f}")
    print(f"  • Sharpe: {best['sharpe']:.2f}")
    print(f"  • Max Consecutive Losses: {best['max_consecutive_losses']}")
    
    # Risk warning
    print("\n⚠️  RISK NOTES:")
    worst_dd = min(results, key=lambda x: x['max_drawdown'])
    worst_loss = min(results, key=lambda x: x['max_loss'])
    print(f"  • Worst max drawdown across strategies: ${worst_dd['max_drawdown']:,.0f} ({worst_dd['name']})")
    print(f"  • Worst single-day loss: ${worst_loss['max_loss']:,.0f} ({worst_loss['name']})")


def main():
    print("Loading 5 years of market data...")
    
    # Load data
    df = load_market_data('2021-01-29', '2026-01-29')
    print(f"Loaded {len(df)} trading days")
    
    # Calculate previous close for gap filter
    df = df.sort_values('date').reset_index(drop=True)
    df['prev_close'] = df['close'].shift(1)
    df = df.dropna()
    
    # Define candidate strategies (from our iterations)
    candidates = [
        # (name, filters, delta, wing)
        ("Thu+VIX>20+δ0.14+w50", {'dow': [3], 'vix_above': 20}, 0.14, 50),
        ("Thu+VIX>20+δ0.15+w50", {'dow': [3], 'vix_above': 20}, 0.15, 50),
        ("Thu+VIX>20+δ0.14+w40", {'dow': [3], 'vix_above': 20}, 0.14, 40),
        ("Thu+VIX>20+δ0.12+w35", {'dow': [3], 'vix_above': 20}, 0.12, 35),
        ("Thu+VIX>21+δ0.14+w50", {'dow': [3], 'vix_above': 21}, 0.14, 50),
        ("Thu+Fri+VIX>20+δ0.14+w50", {'dow': [3, 4], 'vix_above': 20}, 0.14, 50),
        ("VIX>20 only (no day)", {'vix_above': 20}, 0.14, 50),
        ("Thu+VIX>20+δ0.14+w70", {'dow': [3], 'vix_above': 20}, 0.14, 70),
    ]
    
    results = []
    for name, filters, delta, wing in candidates:
        print(f"  Testing: {name}...")
        trades = simulate_strategy(df, filters, delta, wing)
        metrics = analyze_results(trades, name)
        if metrics:
            results.append(metrics)
    
    print_comparison(results)


if __name__ == "__main__":
    main()
