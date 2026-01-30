#!/usr/bin/env python3
"""
Test Stop Loss Strategies:
1. No stop loss (hold to expiry)
2. Stop loss at X% of credit received (e.g., 100%, 150%, 200% of credit)
3. Stop loss at X% of max loss (e.g., 25%, 50%, 75% of wing width)
4. Stop loss on touch (any intraday touch of short strike)
5. Stop loss on breach (close beyond short strike)
6. Profit target variations
"""
import sys
sys.path.insert(0, '/home/ubuntu/clawd/projects/options-backtest')

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple

from src.data import DataManager


def load_data():
    """Load 5Y market data with OHLC"""
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
    
    return df.dropna()


def get_strike_prices(row, delta, spot):
    """Calculate short strike prices based on delta and VIX"""
    vix = row['vix_close']
    stdev_daily = spot * (vix / 100) / np.sqrt(252)
    
    # Delta to stdev multiplier (rough approximation)
    if delta <= 0.10:
        mult = 1.5
    elif delta <= 0.12:
        mult = 1.3
    elif delta <= 0.14:
        mult = 1.1
    elif delta <= 0.16:
        mult = 0.95
    else:
        mult = 0.8
    
    strike_dist = stdev_daily * mult
    put_short = spot - strike_dist
    call_short = spot + strike_dist
    
    return put_short, call_short


def simulate_trade_with_stop(row, delta, wing, contracts, stop_config):
    """
    Simulate a single trade with stop loss logic.
    
    stop_config = {
        'type': 'none' | 'pct_credit' | 'pct_max_loss' | 'touch' | 'breach',
        'value': float (e.g., 1.5 for 150% of credit)
    }
    
    Returns: (pnl, exit_reason, credit, max_loss)
    """
    spot = row['open']  # Entry at open
    day_low = row['low']
    day_high = row['high']
    day_close = row['close']
    
    put_short, call_short = get_strike_prices(row, delta, spot)
    put_long = put_short - wing
    call_long = call_short + wing
    
    # Credit received (roughly 30% of wing width)
    credit_per_contract = wing * 100 * 0.30
    max_loss_per_contract = wing * 100 - credit_per_contract
    
    credit = credit_per_contract * contracts
    max_loss = max_loss_per_contract * contracts
    
    # Check for intraday touch/breach
    touched_put = day_low <= put_short
    touched_call = day_high >= call_short
    breached_put = day_close < put_short
    breached_call = day_close > call_short
    
    stop_type = stop_config.get('type', 'none')
    stop_value = stop_config.get('value', 1.0)
    
    # ==========================================
    # STOP LOSS LOGIC
    # ==========================================
    
    if stop_type == 'none':
        # Hold to expiry - full P&L based on close
        if breached_put:
            loss = min((put_short - day_close), wing) * 100 * contracts
            pnl = credit - loss
            exit_reason = 'breach_put'
        elif breached_call:
            loss = min((day_close - call_short), wing) * 100 * contracts
            pnl = credit - loss
            exit_reason = 'breach_call'
        else:
            pnl = credit
            exit_reason = 'win'
    
    elif stop_type == 'pct_credit':
        # Stop when loss reaches X% of credit received
        stop_loss_amount = credit * stop_value
        
        # Estimate max intraday loss
        if touched_put:
            intraday_loss_put = max(0, (put_short - day_low)) * 100 * contracts
        else:
            intraday_loss_put = 0
        
        if touched_call:
            intraday_loss_call = max(0, (day_high - call_short)) * 100 * contracts
        else:
            intraday_loss_call = 0
        
        intraday_loss = max(intraday_loss_put, intraday_loss_call)
        
        if intraday_loss >= stop_loss_amount:
            # Stopped out
            pnl = credit - stop_loss_amount
            exit_reason = f'stop_{int(stop_value*100)}pct_credit'
        elif breached_put or breached_call:
            # Not stopped but breached at close
            if breached_put:
                loss = min((put_short - day_close), wing) * 100 * contracts
            else:
                loss = min((day_close - call_short), wing) * 100 * contracts
            pnl = credit - loss
            exit_reason = 'breach_no_stop'
        else:
            pnl = credit
            exit_reason = 'win'
    
    elif stop_type == 'pct_max_loss':
        # Stop when loss reaches X% of max possible loss (wing width)
        stop_loss_amount = max_loss * stop_value
        
        if touched_put:
            intraday_loss_put = max(0, min((put_short - day_low), wing)) * 100 * contracts
        else:
            intraday_loss_put = 0
        
        if touched_call:
            intraday_loss_call = max(0, min((day_high - call_short), wing)) * 100 * contracts
        else:
            intraday_loss_call = 0
        
        intraday_loss = max(intraday_loss_put, intraday_loss_call)
        
        if intraday_loss >= stop_loss_amount:
            pnl = credit - stop_loss_amount
            exit_reason = f'stop_{int(stop_value*100)}pct_maxloss'
        elif breached_put or breached_call:
            if breached_put:
                loss = min((put_short - day_close), wing) * 100 * contracts
            else:
                loss = min((day_close - call_short), wing) * 100 * contracts
            pnl = credit - loss
            exit_reason = 'breach_no_stop'
        else:
            pnl = credit
            exit_reason = 'win'
    
    elif stop_type == 'touch':
        # Exit immediately on any touch of short strike
        if touched_put or touched_call:
            # Assume we exit at a small loss (spread between touch and exit)
            # Roughly 50% of credit lost on touch exit
            pnl = credit * 0.5 * -1  # Small loss
            exit_reason = 'stop_touch'
        else:
            pnl = credit
            exit_reason = 'win'
    
    elif stop_type == 'breach':
        # Exit only if price CLOSES beyond short strike
        if breached_put:
            # Already breached, take the loss but cap at max
            loss = min((put_short - day_close), wing) * 100 * contracts
            pnl = credit - loss
            exit_reason = 'stop_breach'
        elif breached_call:
            loss = min((day_close - call_short), wing) * 100 * contracts
            pnl = credit - loss
            exit_reason = 'stop_breach'
        else:
            pnl = credit
            exit_reason = 'win'
    
    return pnl, exit_reason, credit, max_loss


def run_backtest_with_stop(df, config, stop_config, capital=20000):
    """Run backtest with specific stop loss configuration"""
    trades = []
    
    delta = config.get('delta', 0.14)
    wing = config.get('wing', 40)
    skip_dow = config.get('skip_dow', [3])
    vix_max = config.get('vix_max', 20)
    
    risk_per_contract = wing * 100 * 0.70
    contracts = max(1, int(capital / risk_per_contract))
    
    for i, row in df.iterrows():
        # Apply filters
        if row['dow'] in skip_dow:
            continue
        if row['vix_close'] > vix_max:
            continue
        
        pnl, exit_reason, credit, max_loss = simulate_trade_with_stop(
            row, delta, wing, contracts, stop_config
        )
        
        trades.append({
            'date': row['date'],
            'pnl': pnl,
            'exit_reason': exit_reason,
            'credit': credit,
            'max_loss': max_loss,
            'win': pnl > 0,
        })
    
    return trades


def analyze_trades(trades, name):
    """Compute stats"""
    if not trades:
        return {'name': name, 'trades': 0}
    
    pnls = [t['pnl'] for t in trades]
    wins = [t for t in trades if t['win']]
    losses = [t for t in trades if not t['win']]
    
    # Exit reason breakdown
    exit_reasons = {}
    for t in trades:
        reason = t['exit_reason']
        if reason not in exit_reasons:
            exit_reasons[reason] = 0
        exit_reasons[reason] += 1
    
    total_pnl = sum(pnls)
    avg_pnl = np.mean(pnls)
    win_rate = len(wins) / len(trades) * 100
    
    if np.std(pnls) > 0:
        sharpe = (np.mean(pnls) / np.std(pnls)) * np.sqrt(252)
    else:
        sharpe = 0
    
    # Max drawdown
    cumsum = np.cumsum(pnls)
    peak = np.maximum.accumulate(cumsum)
    drawdown = cumsum - peak
    max_dd = drawdown.min()
    
    # Average win/loss
    avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0
    avg_loss = np.mean([t['pnl'] for t in losses]) if losses else 0
    
    return {
        'name': name,
        'trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_pnl': avg_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'sharpe': sharpe,
        'max_dd': max_dd,
        'exit_reasons': exit_reasons,
    }


def print_results(results):
    """Print comparison table"""
    print("\n" + "="*130)
    print("STOP LOSS STRATEGY COMPARISON (5Y: 2021-2026, $20K Capital)")
    print("="*130)
    
    print(f"\n{'Strategy':<40} {'Trades':>7} {'WR%':>7} {'Sharpe':>8} {'Max DD':>10} {'Avg Win':>10} {'Avg Loss':>10} {'5Y P&L':>12}")
    print("-"*130)
    
    for r in sorted(results, key=lambda x: x.get('sharpe', 0), reverse=True):
        if r['trades'] == 0:
            continue
        print(f"{r['name']:<40} {r['trades']:>7} {r['win_rate']:>6.1f}% {r['sharpe']:>8.2f} "
              f"${r['max_dd']:>9,.0f} ${r['avg_win']:>9,.0f} ${r['avg_loss']:>9,.0f} ${r['total_pnl']:>11,.0f}")
    
    # Print exit reason breakdown for top strategies
    print("\n" + "="*80)
    print("EXIT REASON BREAKDOWN")
    print("="*80)
    
    for r in sorted(results, key=lambda x: x.get('sharpe', 0), reverse=True)[:5]:
        print(f"\n{r['name']}:")
        for reason, count in sorted(r.get('exit_reasons', {}).items(), key=lambda x: -x[1]):
            pct = count / r['trades'] * 100
            print(f"  {reason:<25}: {count:>4} ({pct:>5.1f}%)")


def main():
    print("Loading 5Y data...")
    df = load_data()
    print(f"Loaded {len(df)} trading days")
    
    results = []
    
    # Base config
    base_config = {
        'delta': 0.14,
        'wing': 40,
        'skip_dow': [3],
        'vix_max': 20,
    }
    
    # ============================================
    # TEST 1: No Stop Loss (Baseline)
    # ============================================
    print("\n--- Testing No Stop Loss (Hold to Expiry) ---")
    
    stop_config = {'type': 'none'}
    trades = run_backtest_with_stop(df, base_config, stop_config)
    results.append(analyze_trades(trades, "No Stop (Hold to Expiry)"))
    print(f"  No Stop: {len(trades)} trades")
    
    # ============================================
    # TEST 2: Stop Loss as % of Credit Received
    # ============================================
    print("\n--- Testing Stop Loss as % of Credit ---")
    
    for pct in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
        stop_config = {'type': 'pct_credit', 'value': pct}
        trades = run_backtest_with_stop(df, base_config, stop_config)
        name = f"Stop @ {int(pct*100)}% of Credit"
        results.append(analyze_trades(trades, name))
        print(f"  {name}: {len(trades)} trades")
    
    # ============================================
    # TEST 3: Stop Loss as % of Max Loss
    # ============================================
    print("\n--- Testing Stop Loss as % of Max Loss ---")
    
    for pct in [0.25, 0.50, 0.75, 1.0]:
        stop_config = {'type': 'pct_max_loss', 'value': pct}
        trades = run_backtest_with_stop(df, base_config, stop_config)
        name = f"Stop @ {int(pct*100)}% of Max Loss"
        results.append(analyze_trades(trades, name))
        print(f"  {name}: {len(trades)} trades")
    
    # ============================================
    # TEST 4: Stop on Touch
    # ============================================
    print("\n--- Testing Stop on Touch ---")
    
    stop_config = {'type': 'touch'}
    trades = run_backtest_with_stop(df, base_config, stop_config)
    results.append(analyze_trades(trades, "Stop on Touch (Any)"))
    print(f"  Stop on Touch: {len(trades)} trades")
    
    # ============================================
    # TEST 5: Stop on Breach (Close Beyond)
    # ============================================
    print("\n--- Testing Stop on Breach ---")
    
    stop_config = {'type': 'breach'}
    trades = run_backtest_with_stop(df, base_config, stop_config)
    results.append(analyze_trades(trades, "Stop on Breach (Close)"))
    print(f"  Stop on Breach: {len(trades)} trades")
    
    # ============================================
    # TEST 6: Combined with Profit Target
    # ============================================
    print("\n--- Testing with Profit Targets ---")
    
    # For profit targets, we'd need to modify the simulation
    # For now, showing stop loss results
    
    # ============================================
    # PRINT RESULTS
    # ============================================
    print_results(results)
    
    # ============================================
    # KEY FINDINGS
    # ============================================
    print("\n\n" + "="*80)
    print("KEY FINDINGS")
    print("="*80)
    
    baseline = [r for r in results if 'No Stop' in r['name']][0]
    print(f"\nBASELINE (No Stop): Sharpe {baseline['sharpe']:.2f}, WR {baseline['win_rate']:.1f}%")
    
    print("\nBEST STRATEGIES:")
    sorted_results = sorted(results, key=lambda x: x.get('sharpe', 0), reverse=True)
    for i, r in enumerate(sorted_results[:5], 1):
        improvement = (r['sharpe'] - baseline['sharpe']) / baseline['sharpe'] * 100 if baseline['sharpe'] > 0 else 0
        print(f"  {i}. {r['name']}")
        print(f"     Sharpe: {r['sharpe']:.2f} ({improvement:+.1f}%), WR: {r['win_rate']:.1f}%, Max DD: ${r['max_dd']:,.0f}")
    
    return results


if __name__ == "__main__":
    results = main()
