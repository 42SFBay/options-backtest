#!/usr/bin/env python3
"""
Test Dynamic Rules - Delta, Wing Width, and Other Adaptive Strategies
"""
import sys
sys.path.insert(0, '/home/ubuntu/clawd/projects/options-backtest')

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List

from src.data import DataManager
from src.rules import RuleEngine, Rule, Condition


def load_data():
    """Load 5Y market data"""
    dm = DataManager()
    prices = dm.get_underlying_prices('SPX', '2021-01-29', '2026-01-29')
    vix = dm.get_vix_data('2021-01-29', '2026-01-29')
    
    prices = prices.reset_index()
    prices.columns = [c.lower() for c in prices.columns]
    vix = vix.reset_index()
    vix.columns = [c.lower() for c in vix.columns]
    vix = vix.rename(columns={'close': 'vix_close'})
    
    prices['date'] = pd.to_datetime(prices['date']).dt.tz_localize(None).dt.normalize()
    vix['date'] = pd.to_datetime(vix['date']).dt.tz_localize(None).dt.normalize()
    
    df = prices.merge(vix[['date', 'vix_close']], on='date', how='inner')
    df = df.sort_values('date').reset_index(drop=True)
    
    # Add derived fields
    df['prev_close'] = df['close'].shift(1)
    df['gap_pct'] = abs(df['open'] - df['prev_close']) / df['prev_close'] * 100
    df['dow'] = df['date'].dt.dayofweek  # 0=Mon, 3=Thu, 4=Fri
    df['day_return'] = (df['close'] - df['open']) / df['open'] * 100
    
    # Momentum indicators
    df['momentum_5d'] = df['close'].pct_change(5) * 100
    df['momentum_10d'] = df['close'].pct_change(10) * 100
    df['down_days_streak'] = 0
    
    streak = 0
    for i in range(1, len(df)):
        if df.loc[i-1, 'day_return'] < 0:
            streak += 1
        else:
            streak = 0
        df.loc[i, 'down_days_streak'] = streak
    
    return df.dropna()


def simulate_ic(df, row, delta, wing, contracts):
    """
    Simulate iron condor P&L for a single day.
    Returns (pnl, is_win, credit, max_loss)
    """
    spot = row['close']
    vix = row['vix_close']
    day_range = row['high'] - row['low']
    
    # Estimate strike distances based on delta and VIX
    # Higher delta = closer to money, higher premium but higher risk
    # Using rough approximation: delta 0.10 ≈ 1.3 stdev, delta 0.15 ≈ 1.0 stdev
    stdev_daily = spot * (vix / 100) / np.sqrt(252)
    
    if delta <= 0.10:
        strike_dist = stdev_daily * 1.5
    elif delta <= 0.12:
        strike_dist = stdev_daily * 1.3
    elif delta <= 0.14:
        strike_dist = stdev_daily * 1.1
    elif delta <= 0.16:
        strike_dist = stdev_daily * 0.95
    else:
        strike_dist = stdev_daily * 0.8
    
    put_short = spot - strike_dist
    call_short = spot + strike_dist
    
    # Credit received (rough: 30% of wing width for OTM spreads)
    credit_per_contract = wing * 100 * 0.30
    max_loss_per_contract = wing * 100 - credit_per_contract
    
    credit = credit_per_contract * contracts
    max_loss = max_loss_per_contract * contracts
    
    # Check if breached
    breached = (row['low'] < put_short) or (row['high'] > call_short)
    
    if breached:
        # Simplified: if breached, assume 70% of max loss on average
        pnl = credit - (max_loss * 0.7)
    else:
        pnl = credit
    
    return pnl, not breached, credit, max_loss


def run_backtest(df, config, capital=20000):
    """
    Run backtest with given configuration.
    
    config = {
        'delta': 0.14 or callable(row) -> delta,
        'wing': 40 or callable(row) -> wing,
        'skip_dow': [3],  # Thursday
        'vix_max': 20,
        'vix_min': None,
        'gap_max': None,
        'momentum_filter': None,  # e.g., ('5d', -3) = skip if 5d momentum < -3%
        'down_streak_max': None,  # e.g., 3 = skip after 3 down days
        'name': 'Config Name'
    }
    """
    trades = []
    
    for i, row in df.iterrows():
        # Get delta and wing (can be dynamic)
        if callable(config.get('delta')):
            delta = config['delta'](row)
        else:
            delta = config.get('delta', 0.14)
        
        if callable(config.get('wing')):
            wing = config['wing'](row)
        else:
            wing = config.get('wing', 40)
        
        # Calculate contracts based on wing and capital
        risk_per_contract = wing * 100 * 0.70  # 70% of wing is max loss
        contracts = int(capital / risk_per_contract)
        if contracts < 1:
            contracts = 1
        
        # Apply filters
        skip = False
        skip_reason = None
        
        # Day of week filter
        if config.get('skip_dow') and row['dow'] in config['skip_dow']:
            skip = True
            skip_reason = 'dow'
        
        # VIX max filter
        if config.get('vix_max') and row['vix_close'] > config['vix_max']:
            skip = True
            skip_reason = 'vix_high'
        
        # VIX min filter
        if config.get('vix_min') and row['vix_close'] < config['vix_min']:
            skip = True
            skip_reason = 'vix_low'
        
        # Gap filter
        if config.get('gap_max') and row['gap_pct'] > config['gap_max']:
            skip = True
            skip_reason = 'gap'
        
        # Momentum filter
        if config.get('momentum_filter'):
            period, threshold = config['momentum_filter']
            mom_col = f'momentum_{period}'
            if mom_col in row and row[mom_col] < threshold:
                skip = True
                skip_reason = 'momentum'
        
        # Down streak filter
        if config.get('down_streak_max') and row['down_days_streak'] >= config['down_streak_max']:
            skip = True
            skip_reason = 'streak'
        
        if skip:
            continue
        
        # Run simulation
        pnl, is_win, credit, max_loss = simulate_ic(df, row, delta, wing, contracts)
        
        trades.append({
            'date': row['date'],
            'delta': delta,
            'wing': wing,
            'contracts': contracts,
            'vix': row['vix_close'],
            'pnl': pnl,
            'win': is_win,
            'credit': credit,
            'max_loss': max_loss,
        })
    
    return trades


def analyze_trades(trades, name):
    """Compute stats from trades"""
    if not trades:
        return {'name': name, 'trades': 0}
    
    pnls = [t['pnl'] for t in trades]
    wins = [t for t in trades if t['win']]
    losses = [t for t in trades if not t['win']]
    
    total_pnl = sum(pnls)
    avg_pnl = np.mean(pnls)
    win_rate = len(wins) / len(trades) * 100
    
    # Sharpe
    if np.std(pnls) > 0:
        sharpe = (np.mean(pnls) / np.std(pnls)) * np.sqrt(252)
    else:
        sharpe = 0
    
    # Max drawdown
    cumsum = np.cumsum(pnls)
    peak = np.maximum.accumulate(cumsum)
    drawdown = cumsum - peak
    max_dd = drawdown.min()
    
    # Avg contracts
    avg_contracts = np.mean([t['contracts'] for t in trades])
    
    return {
        'name': name,
        'trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_pnl': avg_pnl,
        'sharpe': sharpe,
        'max_dd': max_dd,
        'avg_contracts': avg_contracts,
    }


def print_results(results):
    """Print comparison table"""
    print("\n" + "="*120)
    print("HYPOTHESIS TESTING RESULTS (5Y: 2021-2026, $20K Capital)")
    print("="*120)
    
    print(f"\n{'Config':<45} {'Trades':>7} {'WR%':>7} {'Sharpe':>8} {'Max DD':>10} {'5Y P&L':>12} {'Avg Cont':>9}")
    print("-"*120)
    
    for r in sorted(results, key=lambda x: x.get('sharpe', 0), reverse=True):
        if r['trades'] == 0:
            continue
        print(f"{r['name']:<45} {r['trades']:>7} {r['win_rate']:>6.1f}% {r['sharpe']:>8.2f} "
              f"${r['max_dd']:>9,.0f} ${r['total_pnl']:>11,.0f} {r['avg_contracts']:>9.1f}")


def main():
    print("Loading 5Y data...")
    df = load_data()
    print(f"Loaded {len(df)} trading days")
    
    results = []
    
    # ============================================
    # BASELINE CONFIGS
    # ============================================
    print("\n--- Testing Baseline Configs ---")
    
    # Best known config
    config = {
        'name': 'Baseline: δ0.14 w40 Thu VIX>20',
        'delta': 0.14,
        'wing': 40,
        'skip_dow': [3],
        'vix_max': 20,
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    # ============================================
    # HYPOTHESIS 1: Dynamic Delta based on VIX
    # ============================================
    print("\n--- Hypothesis 1: Dynamic Delta (VIX-based) ---")
    
    # Lower delta when VIX is higher (more conservative in vol)
    def dynamic_delta_conservative(row):
        if row['vix_close'] > 25:
            return 0.10
        elif row['vix_close'] > 20:
            return 0.12
        elif row['vix_close'] > 16:
            return 0.14
        else:
            return 0.16
    
    config = {
        'name': 'Dynamic Delta (VIX): 0.10-0.16',
        'delta': dynamic_delta_conservative,
        'wing': 40,
        'skip_dow': [3],
        'vix_max': 25,  # Allow higher VIX with lower delta
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    # Aggressive: Higher delta when VIX is high (more premium)
    def dynamic_delta_aggressive(row):
        if row['vix_close'] > 20:
            return 0.18
        elif row['vix_close'] > 16:
            return 0.15
        else:
            return 0.12
    
    config = {
        'name': 'Dynamic Delta (Aggressive): 0.12-0.18',
        'delta': dynamic_delta_aggressive,
        'wing': 40,
        'skip_dow': [3],
        'vix_max': 25,
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    # ============================================
    # HYPOTHESIS 2: Dynamic Wing based on VIX
    # ============================================
    print("\n--- Hypothesis 2: Dynamic Wing Width (VIX-based) ---")
    
    # Wider wings when VIX is high
    def dynamic_wing_vix(row):
        if row['vix_close'] > 22:
            return 60
        elif row['vix_close'] > 18:
            return 50
        else:
            return 40
    
    config = {
        'name': 'Dynamic Wing (VIX): w40-60',
        'delta': 0.14,
        'wing': dynamic_wing_vix,
        'skip_dow': [3],
        'vix_max': 25,
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    # Narrower wings when VIX is high (more premium, more risk)
    def dynamic_wing_inverse(row):
        if row['vix_close'] > 22:
            return 30
        elif row['vix_close'] > 18:
            return 35
        else:
            return 45
    
    config = {
        'name': 'Dynamic Wing (Inverse): w30-45',
        'delta': 0.14,
        'wing': dynamic_wing_inverse,
        'skip_dow': [3],
        'vix_max': 25,
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    # ============================================
    # HYPOTHESIS 3: Momentum Filter
    # ============================================
    print("\n--- Hypothesis 3: Momentum Filter ---")
    
    # Skip when 5d momentum is very negative
    config = {
        'name': 'Skip when 5d momentum < -3%',
        'delta': 0.14,
        'wing': 40,
        'skip_dow': [3],
        'vix_max': 20,
        'momentum_filter': ('5d', -3),
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    config = {
        'name': 'Skip when 5d momentum < -5%',
        'delta': 0.14,
        'wing': 40,
        'skip_dow': [3],
        'vix_max': 20,
        'momentum_filter': ('5d', -5),
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    # ============================================
    # HYPOTHESIS 4: Down Streak Filter
    # ============================================
    print("\n--- Hypothesis 4: Down Days Streak Filter ---")
    
    config = {
        'name': 'Skip after 3+ down days',
        'delta': 0.14,
        'wing': 40,
        'skip_dow': [3],
        'vix_max': 20,
        'down_streak_max': 3,
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    config = {
        'name': 'Skip after 4+ down days',
        'delta': 0.14,
        'wing': 40,
        'skip_dow': [3],
        'vix_max': 20,
        'down_streak_max': 4,
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    # ============================================
    # HYPOTHESIS 5: Gap Filter
    # ============================================
    print("\n--- Hypothesis 5: Gap Filter ---")
    
    config = {
        'name': 'Skip gap > 1%',
        'delta': 0.14,
        'wing': 40,
        'skip_dow': [3],
        'vix_max': 20,
        'gap_max': 1.0,
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    config = {
        'name': 'Skip gap > 0.5%',
        'delta': 0.14,
        'wing': 40,
        'skip_dow': [3],
        'vix_max': 20,
        'gap_max': 0.5,
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    # ============================================
    # HYPOTHESIS 6: VIX Sweet Spot
    # ============================================
    print("\n--- Hypothesis 6: VIX Sweet Spot ---")
    
    config = {
        'name': 'VIX 14-18 only (sweet spot)',
        'delta': 0.14,
        'wing': 40,
        'skip_dow': [3],
        'vix_max': 18,
        'vix_min': 14,
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    config = {
        'name': 'VIX 15-20 only',
        'delta': 0.14,
        'wing': 40,
        'skip_dow': [3],
        'vix_max': 20,
        'vix_min': 15,
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    # ============================================
    # HYPOTHESIS 7: Combined Dynamic Rules
    # ============================================
    print("\n--- Hypothesis 7: Combined Dynamic Rules ---")
    
    def combined_delta(row):
        if row['vix_close'] > 22:
            return 0.10
        elif row['vix_close'] > 18:
            return 0.12
        else:
            return 0.14
    
    def combined_wing(row):
        if row['vix_close'] > 22:
            return 50
        elif row['vix_close'] > 18:
            return 45
        else:
            return 40
    
    config = {
        'name': 'Combined: Dynamic δ + Wing + Skip Thu',
        'delta': combined_delta,
        'wing': combined_wing,
        'skip_dow': [3],
        'vix_max': 25,
        'gap_max': 1.0,
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    # Combined with momentum
    config = {
        'name': 'Combined: Dynamic + Momentum < -3%',
        'delta': combined_delta,
        'wing': combined_wing,
        'skip_dow': [3],
        'vix_max': 25,
        'momentum_filter': ('5d', -3),
    }
    trades = run_backtest(df, config)
    results.append(analyze_trades(trades, config['name']))
    print(f"  {config['name']}: {len(trades)} trades")
    
    # ============================================
    # PRINT RESULTS
    # ============================================
    print_results(results)
    
    # ============================================
    # SAVE FOR DASHBOARD
    # ============================================
    print("\n\n" + "="*80)
    print("KEY FINDINGS FOR DASHBOARD")
    print("="*80)
    
    # Sort by Sharpe
    sorted_results = sorted(results, key=lambda x: x.get('sharpe', 0), reverse=True)
    
    print("\nTOP 5 BY SHARPE:")
    for i, r in enumerate(sorted_results[:5], 1):
        print(f"  {i}. {r['name']}")
        print(f"     Sharpe: {r['sharpe']:.2f}, WR: {r['win_rate']:.1f}%, P&L: ${r['total_pnl']:,.0f}")
    
    # Find improvements over baseline
    baseline = [r for r in results if 'Baseline' in r['name']][0]
    print(f"\nBASELINE: {baseline['name']}")
    print(f"  Sharpe: {baseline['sharpe']:.2f}, P&L: ${baseline['total_pnl']:,.0f}")
    
    print("\nIMPROVEMENTS OVER BASELINE:")
    for r in sorted_results:
        if r['sharpe'] > baseline['sharpe'] and 'Baseline' not in r['name']:
            improvement = (r['sharpe'] - baseline['sharpe']) / baseline['sharpe'] * 100
            print(f"  ✓ {r['name']}")
            print(f"    Sharpe: {r['sharpe']:.2f} (+{improvement:.1f}%), P&L: ${r['total_pnl']:,.0f}")
    
    return results


if __name__ == "__main__":
    results = main()
