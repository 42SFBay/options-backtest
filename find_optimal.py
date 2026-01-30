#!/usr/bin/env python3
"""
Find the optimal combination based on previous findings.
"""

import sys
sys.path.insert(0, '/home/ubuntu/clawd/projects/options-backtest')

from src.rules import RuleEngine, Rule, Condition
from run_rules_backtest import DynamicBacktestEngine
import pandas as pd

START = "2021-01-01"
END = "2026-01-01"

engine_instance = DynamicBacktestEngine(symbol="SPX", start_date=START, end_date=END)

results = []

def run_backtest(rule_engine, name):
    result = engine_instance.run_with_rules(rule_engine, verbose=False)
    stats = result["stats"]
    return {
        "name": name,
        "trades": stats["total_trades"],
        "win_rate": stats["win_rate"],
        "pnl": stats["total_pnl"],
        "sharpe": stats["sharpe"],
    }

print("=" * 70)
print("OPTIMAL COMBINATIONS - Based on previous findings")
print("=" * 70)

# Combo 1: Skip Thursday + wider wings (50)
print("\n### Combo 1: Skip Thursday + Wing 50")
engine = RuleEngine({
    "delta": 0.15, "wing_width": 50, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_thu", [Condition("day_of_week", "==", "Thursday")], {"skip": True}, 100))
result = run_backtest(engine, "thu_wing50")
results.append(result)
print(f"  {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# Combo 2: Skip Thursday + delta 0.20
print("\n### Combo 2: Skip Thursday + Delta 0.20")
engine = RuleEngine({
    "delta": 0.20, "wing_width": 30, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_thu", [Condition("day_of_week", "==", "Thursday")], {"skip": True}, 100))
result = run_backtest(engine, "thu_delta20")
results.append(result)
print(f"  {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# Combo 3: Skip Thursday + delta 0.20 + wing 50 (MAX P&L CONFIG)
print("\n### Combo 3: Skip Thursday + Delta 0.20 + Wing 50 (MAX P&L)")
engine = RuleEngine({
    "delta": 0.20, "wing_width": 50, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_thu", [Condition("day_of_week", "==", "Thursday")], {"skip": True}, 100))
result = run_backtest(engine, "thu_delta20_wing50")
results.append(result)
print(f"  {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# Combo 4: Skip Wed+Thu + delta 0.16 + wing 40
print("\n### Combo 4: Skip Wed+Thu + Delta 0.16 + Wing 40")
engine = RuleEngine({
    "delta": 0.16, "wing_width": 40, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_days", [Condition("day_of_week", "in", ["Wednesday", "Thursday"])], {"skip": True}, 100))
result = run_backtest(engine, "wedthu_d16_w40")
results.append(result)
print(f"  {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# Combo 5: VIX 14-20 + Skip Thursday + delta 0.18
print("\n### Combo 5: VIX 14-20 + Skip Thursday + Delta 0.18")
engine = RuleEngine({
    "delta": 0.18, "wing_width": 35, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_thu", [Condition("day_of_week", "==", "Thursday")], {"skip": True}, 100))
engine.add_rule(Rule("skip_low_vix", [Condition("vix", "<", 14)], {"skip": True}, 100))
engine.add_rule(Rule("skip_high_vix", [Condition("vix", ">", 20)], {"skip": True}, 100))
result = run_backtest(engine, "vix1420_thu_d18_w35")
results.append(result)
print(f"  {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# Combo 6: Skip Thursday + max gap 0.75% + delta 0.18 + wing 40
print("\n### Combo 6: Skip Thursday + Gap < 0.75% + Delta 0.18 + Wing 40")
engine = RuleEngine({
    "delta": 0.18, "wing_width": 40, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_thu", [Condition("day_of_week", "==", "Thursday")], {"skip": True}, 100))
engine.add_rule(Rule("skip_gap", [Condition("gap", ">", 0.75)], {"skip": True}, 100))
result = run_backtest(engine, "thu_gap75_d18_w40")
results.append(result)
print(f"  {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# Combo 7: AGGRESSIVE P&L - delta 0.22, wing 60, skip nothing
print("\n### Combo 7: AGGRESSIVE P&L - Delta 0.22, Wing 60, No filters")
engine = RuleEngine({
    "delta": 0.22, "wing_width": 60, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
result = run_backtest(engine, "aggressive_d22_w60")
results.append(result)
print(f"  {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# Combo 8: BALANCED - Skip Thu + delta 0.16 + wing 35
print("\n### Combo 8: BALANCED - Skip Thu + Delta 0.16 + Wing 35")
engine = RuleEngine({
    "delta": 0.16, "wing_width": 35, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_thu", [Condition("day_of_week", "==", "Thursday")], {"skip": True}, 100))
result = run_backtest(engine, "balanced_thu_d16_w35")
results.append(result)
print(f"  {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# Combo 9: MAX SHARPE target - VIX 16-20 + Skip Wed+Thu
print("\n### Combo 9: MAX SHARPE - VIX 16-20 + Skip Wed+Thu")
engine = RuleEngine({
    "delta": 0.14, "wing_width": 30, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_days", [Condition("day_of_week", "in", ["Wednesday", "Thursday"])], {"skip": True}, 100))
engine.add_rule(Rule("skip_low_vix", [Condition("vix", "<", 16)], {"skip": True}, 100))
engine.add_rule(Rule("skip_high_vix", [Condition("vix", ">", 20)], {"skip": True}, 100))
result = run_backtest(engine, "maxsharpe_vix1620_wedthu")
results.append(result)
print(f"  {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# Combo 10: CONSERVATIVE HIGH WR - Skip Thu + VIX 14-18 + delta 0.12
print("\n### Combo 10: CONSERVATIVE HIGH WR - Skip Thu + VIX 14-18 + Delta 0.12")
engine = RuleEngine({
    "delta": 0.12, "wing_width": 25, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_thu", [Condition("day_of_week", "==", "Thursday")], {"skip": True}, 100))
engine.add_rule(Rule("skip_low_vix", [Condition("vix", "<", 14)], {"skip": True}, 100))
engine.add_rule(Rule("skip_high_vix", [Condition("vix", ">", 18)], {"skip": True}, 100))
result = run_backtest(engine, "conservative_d12_vix1418")
results.append(result)
print(f"  {result['trades']} trades, {result['win_rate']:.1%} WR, ${result['pnl']:,.0f} P&L, {result['sharpe']:.2f} Sharpe")

# Summary
print("\n" + "=" * 70)
print("SUMMARY - RANKED BY P&L")
print("=" * 70)
df = pd.DataFrame(results)
df_sorted = df.sort_values("pnl", ascending=False)
for _, row in df_sorted.iterrows():
    print(f"{row['name']:30s}: ${row['pnl']:>10,.0f} | {row['trades']:>4} trades | {row['win_rate']:.1%} WR | {row['sharpe']:.2f} Sharpe")

print("\n" + "=" * 70)
print("SUMMARY - RANKED BY SHARPE")
print("=" * 70)
df_sorted = df.sort_values("sharpe", ascending=False)
for _, row in df_sorted.iterrows():
    print(f"{row['name']:30s}: {row['sharpe']:.2f} Sharpe | ${row['pnl']:>10,.0f} | {row['trades']:>4} trades | {row['win_rate']:.1%} WR")

df.to_csv("/home/ubuntu/clawd/projects/options-backtest/optimal_combos.csv", index=False)
print("\nSaved to optimal_combos.csv")
