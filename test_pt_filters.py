#!/usr/bin/env python3
"""
Test:
1. Profit Targets (take profit at X% of max profit)
2. Consecutive Loss Rules (skip/reduce after N losses)
3. Various Filters (gap, momentum, VIX ranges, etc.)
"""
import sys
sys.path.insert(0, '/home/ubuntu/clawd/projects/options-backtest')

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List

from src.data import DataManager


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
    df['dow'] = df['date'].dt.dayofweek
    df['prev_close'] = df['close'].shift(1)
    df['gap_pct'] = abs(df['open'] - df['prev_close']) / df['prev_close'] * 100
    df['day_return'] = (df['close'] - df['open']) / df['open'] * 100
    
    # Momentum
    df['momentum_5d'] = df['close'].pct_change(5) * 100
    df['momentum_10d'] = df['close'].pct_change(10) * 100
    
    # Down streak
    df['down_days'] = 0
    streak = 0
    for i in range(1, len(df)):
        if df.loc[i-1, 'close'] < df.loc[i-1, 'open']:
            streak += 1
        else:
            streak = 0
        df.loc[i, 'down_days'] = streak
    
    # Weekly high/low
    df['week_high'] = df['high'].rolling(5).max()
    df['week_low'] = df['low'].rolling(5).min()
    df['near_week_high'] = (df['close'] / df['week_high']) > 0.98
    df['near_week_low'] = (df['close'] / df['week_low']) < 1.02
    
    return df.dropna()


def simulate_trade(row, delta, wing, contracts, profit_target_pct=None, stop_loss_pct=0.5):
    """
    Simulate trade with optional profit target and stop loss.
    
    profit_target_pct: Take profit when unrealized gain = X% of credit (e.g., 0.5 = 50%)
    stop_loss_pct: Stop loss at X% of credit (e.g., 0.5 = 50%)
    """
    spot = row['open']
    vix = row['vix_close']
    
    # Strike calculation
    stdev_daily = spot * (vix / 100) / np.sqrt(252)
    if delta <= 0.10:
        mult = 1.5
    elif delta <= 0.12:
        mult = 1.3
    elif delta <= 0.14:
        mult = 1.1
    else:
        mult = 0.95
    
    strike_dist = stdev_daily * mult
    put_short = spot - strike_dist
    call_short = spot + strike_dist
    
    credit_per = wing * 100 * 0.30
    credit = credit_per * contracts
    max_profit = credit  # Max profit is the credit received
    
    # Intraday movement simulation
    day_low = row['low']
    day_high = row['high']
    day_close = row['close']
    
    touched_put = day_low <= put_short
    touched_call = day_high >= call_short
    
    # Check profit target first (assumes we can exit early if price stays in range)
    if profit_target_pct is not None:
        # Simplified: if price stayed well within strikes all day, we hit PT
        # Use a proxy: if neither strike was touched and close is near open
        price_range = (day_high - day_low) / spot
        if not touched_put and not touched_call and price_range < 0.01:
            # Calm day - assume we hit profit target
            pnl = credit * profit_target_pct
            return pnl, 'profit_target', credit
    
    # Check stop loss
    if touched_put:
        intraday_loss = max(0, (put_short - day_low)) * 100 * contracts
    elif touched_call:
        intraday_loss = max(0, (day_high - call_short)) * 100 * contracts
    else:
        intraday_loss = 0
    
    stop_amount = credit * stop_loss_pct
    if intraday_loss >= stop_amount:
        pnl = credit - stop_amount
        return pnl, 'stop_loss', credit
    
    # Hold to expiry
    if day_close < put_short:
        loss = min((put_short - day_close), wing) * 100 * contracts
        pnl = credit - loss
        return pnl, 'breach_put', credit
    elif day_close > call_short:
        loss = min((day_close - call_short), wing) * 100 * contracts
        pnl = credit - loss
        return pnl, 'breach_call', credit
    else:
        return credit, 'win', credit


def run_backtest(df, config, capital=20000):
    """Run backtest with config"""
    trades = []
    consecutive_losses = 0
    skip_next = 0  # Skip next N trades after consecutive losses
    
    delta = config.get('delta', 0.14)
    wing = config.get('wing', 40)
    profit_target = config.get('profit_target', None)
    stop_loss = config.get('stop_loss', 0.5)
    
    # Consecutive loss rule
    consec_loss_threshold = config.get('consec_loss_threshold', None)  # e.g., 2
    consec_loss_skip = config.get('consec_loss_skip', 0)  # Skip next N trades
    consec_loss_reduce = config.get('consec_loss_reduce', 1.0)  # Reduce size to X%
    
    risk_per = wing * 100 * 0.70
    base_contracts = max(1, int(capital / risk_per))
    
    for i, row in df.iterrows():
        # Basic filters
        if config.get('skip_dow') and row['dow'] in config['skip_dow']:
            continue
        if config.get('vix_max') and row['vix_close'] > config['vix_max']:
            continue
        if config.get('vix_min') and row['vix_close'] < config['vix_min']:
            continue
        if config.get('gap_max') and row['gap_pct'] > config['gap_max']:
            continue
        if config.get('momentum_min') and row['momentum_5d'] < config['momentum_min']:
            continue
        if config.get('down_days_max') and row['down_days'] >= config['down_days_max']:
            continue
        if config.get('skip_near_low') and row['near_week_low']:
            continue
        if config.get('skip_near_high') and row['near_week_high']:
            continue
        
        # Consecutive loss rule - skip trades
        if skip_next > 0:
            skip_next -= 1
            continue
        
        # Determine contract size (may be reduced after consecutive losses)
        if consec_loss_threshold and consecutive_losses >= consec_loss_threshold:
            contracts = max(1, int(base_contracts * consec_loss_reduce))
        else:
            contracts = base_contracts
        
        # Run trade
        pnl, exit_reason, credit = simulate_trade(
            row, delta, wing, contracts, profit_target, stop_loss
        )
        
        # Track consecutive losses
        if pnl < 0:
            consecutive_losses += 1
            if consec_loss_threshold and consecutive_losses >= consec_loss_threshold:
                skip_next = consec_loss_skip
        else:
            consecutive_losses = 0
        
        trades.append({
            'date': row['date'],
            'pnl': pnl,
            'exit_reason': exit_reason,
            'contracts': contracts,
            'win': pnl > 0,
        })
    
    return trades


def analyze(trades, name):
    """Analyze trades"""
    if not trades:
        return {'name': name, 'trades': 0, 'total_pnl': 0, 'avg_loss': 0, 'max_dd': 0}
    
    pnls = [t['pnl'] for t in trades]
    wins = [t for t in trades if t['win']]
    losses = [t for t in trades if not t['win']]
    
    total_pnl = sum(pnls)
    avg_loss = np.mean([t['pnl'] for t in losses]) if losses else 0
    
    cumsum = np.cumsum(pnls)
    peak = np.maximum.accumulate(cumsum)
    max_dd = (cumsum - peak).min()
    
    return {
        'name': name,
        'trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': len(wins) / len(trades) * 100 if trades else 0,
        'total_pnl': total_pnl,
        'avg_pnl': np.mean(pnls),
        'avg_loss': avg_loss,
        'max_dd': max_dd,
    }


def print_results(results, title):
    """Print results sorted by P&L"""
    print(f"\n{'='*120}")
    print(title)
    print('='*120)
    print(f"{'Strategy':<50} {'5Y P&L':>12} {'Avg Loss':>12} {'Max DD':>12} {'WR%':>8} {'Trades':>7}")
    print('-'*120)
    
    for r in sorted(results, key=lambda x: -x['total_pnl']):
        if r['trades'] == 0:
            continue
        print(f"{r['name']:<50} ${r['total_pnl']:>11,.0f} ${r['avg_loss']:>11,.0f} ${r['max_dd']:>11,.0f} {r['win_rate']:>7.1f}% {r['trades']:>7}")


def main():
    print("Loading data...")
    df = load_data()
    print(f"Loaded {len(df)} days\n")
    
    base = {'delta': 0.14, 'wing': 40, 'skip_dow': [3], 'vix_max': 20, 'stop_loss': 0.5}
    
    # =============================================
    # TEST 1: PROFIT TARGETS
    # =============================================
    print("--- Testing Profit Targets ---")
    results_pt = []
    
    # No profit target (baseline)
    config = {**base, 'profit_target': None}
    trades = run_backtest(df, config)
    results_pt.append(analyze(trades, "No Profit Target (Hold)"))
    
    for pt in [0.25, 0.50, 0.75, 0.90]:
        config = {**base, 'profit_target': pt}
        trades = run_backtest(df, config)
        results_pt.append(analyze(trades, f"Profit Target @ {int(pt*100)}% of Credit"))
    
    print_results(results_pt, "PROFIT TARGET COMPARISON")
    
    # =============================================
    # TEST 2: CONSECUTIVE LOSS RULES
    # =============================================
    print("\n--- Testing Consecutive Loss Rules ---")
    results_cl = []
    
    # Baseline
    config = {**base}
    trades = run_backtest(df, config)
    results_cl.append(analyze(trades, "No Consecutive Loss Rule"))
    
    # Skip after N losses
    for threshold in [2, 3]:
        for skip in [1, 2, 3]:
            config = {**base, 'consec_loss_threshold': threshold, 'consec_loss_skip': skip}
            trades = run_backtest(df, config)
            results_cl.append(analyze(trades, f"Skip {skip} after {threshold} losses"))
    
    # Reduce size after N losses
    for threshold in [2, 3]:
        for reduce in [0.5, 0.25]:
            config = {**base, 'consec_loss_threshold': threshold, 'consec_loss_reduce': reduce}
            trades = run_backtest(df, config)
            results_cl.append(analyze(trades, f"Reduce to {int(reduce*100)}% after {threshold} losses"))
    
    print_results(results_cl, "CONSECUTIVE LOSS RULES COMPARISON")
    
    # =============================================
    # TEST 3: FILTERS
    # =============================================
    print("\n--- Testing Filters ---")
    results_f = []
    
    # Baseline
    config = {**base}
    trades = run_backtest(df, config)
    results_f.append(analyze(trades, "Baseline (Thu skip, VIX>20)"))
    
    # Gap filters
    for gap in [0.5, 1.0, 1.5]:
        config = {**base, 'gap_max': gap}
        trades = run_backtest(df, config)
        results_f.append(analyze(trades, f"+ Gap < {gap}%"))
    
    # Momentum filters
    for mom in [-5, -3, -2]:
        config = {**base, 'momentum_min': mom}
        trades = run_backtest(df, config)
        results_f.append(analyze(trades, f"+ 5d Momentum > {mom}%"))
    
    # Down days filter
    for days in [3, 4, 5]:
        config = {**base, 'down_days_max': days}
        trades = run_backtest(df, config)
        results_f.append(analyze(trades, f"+ Skip after {days}+ down days"))
    
    # VIX range filters
    for vmin, vmax in [(12, 18), (14, 20), (15, 22), (16, 25)]:
        config = {**base, 'vix_min': vmin, 'vix_max': vmax}
        trades = run_backtest(df, config)
        results_f.append(analyze(trades, f"VIX {vmin}-{vmax} only"))
    
    # Near high/low filters
    config = {**base, 'skip_near_low': True}
    trades = run_backtest(df, config)
    results_f.append(analyze(trades, "+ Skip near weekly low"))
    
    config = {**base, 'skip_near_high': True}
    trades = run_backtest(df, config)
    results_f.append(analyze(trades, "+ Skip near weekly high"))
    
    # Combined filters
    config = {**base, 'gap_max': 1.0, 'down_days_max': 4}
    trades = run_backtest(df, config)
    results_f.append(analyze(trades, "+ Gap<1% + Skip 4+ down days"))
    
    config = {**base, 'vix_min': 14, 'vix_max': 20, 'gap_max': 1.0}
    trades = run_backtest(df, config)
    results_f.append(analyze(trades, "VIX 14-20 + Gap<1%"))
    
    print_results(results_f, "FILTER COMPARISON")
    
    # =============================================
    # SUMMARY
    # =============================================
    print("\n" + "="*80)
    print("TOP 5 OVERALL (by P&L)")
    print("="*80)
    
    all_results = results_pt + results_cl + results_f
    all_results = [r for r in all_results if r['trades'] > 0]
    
    # Remove duplicates by name
    seen = set()
    unique = []
    for r in all_results:
        if r['name'] not in seen:
            seen.add(r['name'])
            unique.append(r)
    
    for i, r in enumerate(sorted(unique, key=lambda x: -x['total_pnl'])[:10], 1):
        print(f"{i:2}. {r['name']:<50}")
        print(f"    P&L: ${r['total_pnl']:,.0f} | Avg Loss: ${r['avg_loss']:,.0f} | Max DD: ${r['max_dd']:,.0f} | WR: {r['win_rate']:.1f}%")
    
    return all_results


if __name__ == "__main__":
    results = main()
