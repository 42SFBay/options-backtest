#!/usr/bin/env python3
"""
Systematic hypothesis testing for options backtest.
Iterate through all ideas until we find the optimal configuration.
"""

import sys
sys.path.insert(0, '/home/ubuntu/clawd/projects/options-backtest')

from src.data import DataManager
from src.rules import RuleEngine, Rule, Condition
import pandas as pd
import numpy as np
from datetime import datetime
import itertools

# Import the engine from run_rules_backtest
from run_rules_backtest import DynamicBacktestEngine

START = "2021-01-01"
END = "2026-01-01"

# Create engine once (loads data)
engine_instance = DynamicBacktestEngine(symbol="SPX", start_date=START, end_date=END)

results = []

def run_backtest(rule_engine, name):
    """Run backtest with given rule engine and return results."""
    result = engine_instance.run_with_rules(rule_engine, verbose=False)
    stats = result["stats"]
    
    return {
        "name": name,
        "trades": stats["total_trades"],
        "win_rate": stats["win_rate"],
        "pnl": stats["total_pnl"],
        "sharpe": stats["sharpe"],
        "avg_pnl": stats["avg_pnl"],
        "max_dd": stats.get("max_drawdown", 0),
    }

# ============================================================
# HYPOTHESIS 1: Skip different days of the week
# ============================================================
print("=" * 60)
print("HYPOTHESIS 1: Skip different days of the week")
print("=" * 60)

days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
for day in days:
    engine = RuleEngine({
        "delta": 0.15, "wing_width": 30, "dte": 2,
        "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
    })
    engine.add_rule(Rule(
        name=f"skip_{day.lower()}",
        conditions=[Condition("day_of_week", "==", day)],
        params={"skip": True},
        priority=100,
    ))
    result = run_backtest(engine, f"skip_{day}")
    results.append(result)
    print(f"Skip {day}: {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# ============================================================
# HYPOTHESIS 2: Different DTE values
# ============================================================
print("\n" + "=" * 60)
print("HYPOTHESIS 2: Different DTE values")
print("=" * 60)

for dte in [0, 1, 2, 3, 5, 7]:
    engine = RuleEngine({
        "delta": 0.15, "wing_width": 30, "dte": dte,
        "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
    })
    result = run_backtest(engine, f"dte_{dte}")
    results.append(result)
    print(f"DTE {dte}: {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# ============================================================
# HYPOTHESIS 3: Different delta values
# ============================================================
print("\n" + "=" * 60)
print("HYPOTHESIS 3: Different delta values")
print("=" * 60)

for delta in [0.08, 0.10, 0.12, 0.14, 0.16, 0.18, 0.20]:
    engine = RuleEngine({
        "delta": delta, "wing_width": 30, "dte": 2,
        "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
    })
    result = run_backtest(engine, f"delta_{delta}")
    results.append(result)
    print(f"Delta {delta}: {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# ============================================================
# HYPOTHESIS 4: Different wing widths
# ============================================================
print("\n" + "=" * 60)
print("HYPOTHESIS 4: Different wing widths")
print("=" * 60)

for wing in [15, 20, 25, 30, 35, 40, 50]:
    engine = RuleEngine({
        "delta": 0.15, "wing_width": wing, "dte": 2,
        "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
    })
    result = run_backtest(engine, f"wing_{wing}")
    results.append(result)
    print(f"Wing {wing}: {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# ============================================================
# HYPOTHESIS 5: VIX range filters
# ============================================================
print("\n" + "=" * 60)
print("HYPOTHESIS 5: VIX range filters (only trade in range)")
print("=" * 60)

vix_ranges = [(10, 15), (12, 18), (14, 18), (14, 20), (15, 20), (16, 20), (18, 25)]
for vix_low, vix_high in vix_ranges:
    engine = RuleEngine({
        "delta": 0.15, "wing_width": 30, "dte": 2,
        "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
    })
    # Skip if VIX outside range
    engine.add_rule(Rule(
        name="skip_low_vix",
        conditions=[Condition("vix", "<", vix_low)],
        params={"skip": True},
        priority=100,
    ))
    engine.add_rule(Rule(
        name="skip_high_vix",
        conditions=[Condition("vix", ">", vix_high)],
        params={"skip": True},
        priority=100,
    ))
    result = run_backtest(engine, f"vix_{vix_low}_{vix_high}")
    results.append(result)
    print(f"VIX {vix_low}-{vix_high}: {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# ============================================================
# HYPOTHESIS 6: Skip multiple days combinations
# ============================================================
print("\n" + "=" * 60)
print("HYPOTHESIS 6: Skip multiple days")
print("=" * 60)

day_combos = [
    ["Thursday", "Friday"],
    ["Monday", "Thursday"],
    ["Monday", "Friday"],
    ["Wednesday", "Thursday"],
]
for combo in day_combos:
    engine = RuleEngine({
        "delta": 0.15, "wing_width": 30, "dte": 2,
        "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
    })
    engine.add_rule(Rule(
        name="skip_days",
        conditions=[Condition("day_of_week", "in", combo)],
        params={"skip": True},
        priority=100,
    ))
    result = run_backtest(engine, f"skip_{'_'.join([d[:3] for d in combo])}")
    results.append(result)
    print(f"Skip {'+'.join([d[:3] for d in combo])}: {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# ============================================================
# HYPOTHESIS 7: Seasonal - skip certain months
# ============================================================
print("\n" + "=" * 60)
print("HYPOTHESIS 7: Skip volatile months")
print("=" * 60)

month_sets = [
    [1],  # January
    [9],  # September
    [10],  # October
    [9, 10],  # Sep-Oct
    [1, 9, 10],  # Jan, Sep, Oct
    [3],  # March
]
for months in month_sets:
    engine = RuleEngine({
        "delta": 0.15, "wing_width": 30, "dte": 2,
        "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
    })
    engine.add_rule(Rule(
        name="skip_months",
        conditions=[Condition("month", "in", months)],
        params={"skip": True},
        priority=100,
    ))
    month_names = {1:"Jan", 3:"Mar", 9:"Sep", 10:"Oct"}
    name = "+".join([month_names.get(m, str(m)) for m in months])
    result = run_backtest(engine, f"skip_month_{name}")
    results.append(result)
    print(f"Skip {name}: {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# ============================================================
# HYPOTHESIS 8: Gap size filters
# ============================================================
print("\n" + "=" * 60)
print("HYPOTHESIS 8: Gap size filters")
print("=" * 60)

for max_gap in [0.3, 0.4, 0.5, 0.75, 1.0]:
    engine = RuleEngine({
        "delta": 0.15, "wing_width": 30, "dte": 2,
        "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
    })
    engine.add_rule(Rule(
        name="skip_large_gap",
        conditions=[Condition("gap", ">", max_gap)],
        params={"skip": True},
        priority=100,
    ))
    result = run_backtest(engine, f"max_gap_{max_gap}")
    results.append(result)
    print(f"Max gap {max_gap}%: {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# ============================================================
# HYPOTHESIS 9: Momentum filters
# ============================================================
print("\n" + "=" * 60)
print("HYPOTHESIS 9: Momentum filters (5-day)")
print("=" * 60)

for mode in ["uptrend_only", "downtrend_only", "skip_strong_moves"]:
    engine = RuleEngine({
        "delta": 0.15, "wing_width": 30, "dte": 2,
        "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
    })
    if mode == "uptrend_only":
        engine.add_rule(Rule(
            name="skip_downtrend",
            conditions=[Condition("momentum_5d", "<", 0)],
            params={"skip": True},
            priority=100,
        ))
    elif mode == "downtrend_only":
        engine.add_rule(Rule(
            name="skip_uptrend",
            conditions=[Condition("momentum_5d", ">", 0)],
            params={"skip": True},
            priority=100,
        ))
    elif mode == "skip_strong_moves":
        engine.add_rule(Rule(
            name="skip_strong_up",
            conditions=[Condition("momentum_5d", ">", 0.03)],
            params={"skip": True},
            priority=100,
        ))
        engine.add_rule(Rule(
            name="skip_strong_down",
            conditions=[Condition("momentum_5d", "<", -0.03)],
            params={"skip": True},
            priority=100,
        ))
    result = run_backtest(engine, f"momentum_{mode}")
    results.append(result)
    print(f"{mode}: {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# ============================================================
# HYPOTHESIS 10: Combined best filters
# ============================================================
print("\n" + "=" * 60)
print("HYPOTHESIS 10: Combined best filters")
print("=" * 60)

# Skip Thursday + VIX 14-20
engine = RuleEngine({
    "delta": 0.15, "wing_width": 30, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_thu", [Condition("day_of_week", "==", "Thursday")], {"skip": True}, 100))
engine.add_rule(Rule("skip_low_vix", [Condition("vix", "<", 14)], {"skip": True}, 100))
engine.add_rule(Rule("skip_high_vix", [Condition("vix", ">", 20)], {"skip": True}, 100))
result = run_backtest(engine, "thu_vix14_20")
results.append(result)
print(f"Skip Thu + VIX 14-20: {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# Skip Thursday + gap > 0.5
engine = RuleEngine({
    "delta": 0.15, "wing_width": 30, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_thu", [Condition("day_of_week", "==", "Thursday")], {"skip": True}, 100))
engine.add_rule(Rule("skip_gap", [Condition("gap", ">", 0.5)], {"skip": True}, 100))
result = run_backtest(engine, "thu_gap05")
results.append(result)
print(f"Skip Thu + gap>0.5%: {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# Skip Thursday + Monday
engine = RuleEngine({
    "delta": 0.15, "wing_width": 30, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_days", [Condition("day_of_week", "in", ["Thursday", "Monday"])], {"skip": True}, 100))
result = run_backtest(engine, "thu_mon")
results.append(result)
print(f"Skip Thu + Mon: {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# ============================================================
# HYPOTHESIS 11: Position sizing based on VIX
# ============================================================
print("\n" + "=" * 60)
print("HYPOTHESIS 11: Position sizing (2x in favorable conditions)")
print("=" * 60)

# 2x when VIX 14-18
engine = RuleEngine({
    "delta": 0.15, "wing_width": 30, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
    "position_size": 1,
})
engine.add_rule(Rule(
    "size_2x_sweet",
    [Condition("vix", ">=", 14), Condition("vix", "<=", 18)],
    {"position_size": 2},
    50
))
result = run_backtest(engine, "size_2x_vix14_18")
results.append(result)
print(f"2x when VIX 14-18: {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# 2x when VIX < 16
engine = RuleEngine({
    "delta": 0.15, "wing_width": 30, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
    "position_size": 1,
})
engine.add_rule(Rule("size_2x_low", [Condition("vix", "<", 16)], {"position_size": 2}, 50))
result = run_backtest(engine, "size_2x_vix_lt16")
results.append(result)
print(f"2x when VIX < 16: {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("TOP 10 BY P&L")
print("=" * 60)

df = pd.DataFrame(results)
top_pnl = df.nlargest(10, "pnl")
for _, row in top_pnl.iterrows():
    print(f"{row['name']:25s}: ${row['pnl']:>10,.0f} | {row['trades']:>4} trades | {row['win_rate']:.1%} WR | {row['sharpe']:.2f} Sharpe")

print("\n" + "=" * 60)
print("TOP 10 BY SHARPE (with >500 trades)")
print("=" * 60)

top_sharpe = df[df['trades'] > 500].nlargest(10, "sharpe")
for _, row in top_sharpe.iterrows():
    print(f"{row['name']:25s}: {row['sharpe']:.2f} Sharpe | ${row['pnl']:>10,.0f} | {row['trades']:>4} trades | {row['win_rate']:.1%} WR")

print("\n" + "=" * 60)
print("TOP 10 BY WIN RATE (with >500 trades)")
print("=" * 60)

top_wr = df[df['trades'] > 500].nlargest(10, "win_rate")
for _, row in top_wr.iterrows():
    print(f"{row['name']:25s}: {row['win_rate']:.1%} WR | ${row['pnl']:>10,.0f} | {row['trades']:>4} trades | {row['sharpe']:.2f} Sharpe")

# Save results
df.to_csv("/home/ubuntu/clawd/projects/options-backtest/hypothesis_results.csv", index=False)
print(f"\nSaved {len(df)} results to hypothesis_results.csv")
