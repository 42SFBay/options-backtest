#!/usr/bin/env python3
"""
Push to extremes - find absolute max P&L
"""
import sys
sys.path.insert(0, '/home/ubuntu/clawd/projects/options-backtest')
from src.rules import RuleEngine, Rule, Condition
from run_rules_backtest import DynamicBacktestEngine

START, END = "2021-01-01", "2026-01-01"
engine_instance = DynamicBacktestEngine(symbol="SPX", start_date=START, end_date=END)

def test(params, name):
    engine = RuleEngine({
        "delta": params.get("delta", 0.15),
        "wing_width": params.get("wing", 30),
        "dte": params.get("dte", 2),
        "profit_target_pct": 0.30,
        "stop_loss_pct": 0.50,
        "skip": False,
    })
    if params.get("skip_thu"):
        engine.add_rule(Rule("skip_thu", [Condition("day_of_week", "==", "Thursday")], {"skip": True}, 100))
    result = engine_instance.run_with_rules(engine, verbose=False)
    s = result["stats"]
    print(f"{name:35s}: ${s['total_pnl']:>10,.0f} | {s['total_trades']:>4} | {s['win_rate']:.1%} | {s['sharpe']:.2f}")
    return s

print("=" * 80)
print("EXTREME TESTING - Finding Max P&L")
print("=" * 80)
print(f"{'Config':<35} | {'P&L':>12} | {'#Tr':>4} | {'WR':>5} | {'Sharpe':>6}")
print("-" * 80)

# Push delta higher
for d in [0.22, 0.25, 0.28, 0.30]:
    test({"delta": d, "wing": 50}, f"delta_{d}_wing50")

print()
# Push wing wider
for w in [60, 70, 80, 100]:
    test({"delta": 0.22, "wing": w}, f"delta0.22_wing{w}")

print()
# Delta + wing combos
for d, w in [(0.25, 60), (0.25, 70), (0.28, 60), (0.30, 50)]:
    test({"delta": d, "wing": w}, f"delta{d}_wing{w}")

print()
# With Thursday skip
for d, w in [(0.22, 60), (0.25, 50), (0.25, 60)]:
    test({"delta": d, "wing": w, "skip_thu": True}, f"thu_delta{d}_wing{w}")

print()
# Different DTE with aggressive params
for dte in [1, 2, 3]:
    test({"delta": 0.22, "wing": 60, "dte": dte}, f"dte{dte}_d0.22_w60")

print("\n" + "=" * 80)
print("Year-by-year breakdown for top config")
print("=" * 80)

for year in [2021, 2022, 2023, 2024, 2025]:
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    try:
        eng = DynamicBacktestEngine(symbol="SPX", start_date=start, end_date=end)
        rule_engine = RuleEngine({
            "delta": 0.22, "wing_width": 60, "dte": 2,
            "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
        })
        res = eng.run_with_rules(rule_engine, verbose=False)
        s = res["stats"]
        print(f"{year}: ${s['total_pnl']:>10,.0f} | {s['total_trades']:>3} trades | {s['win_rate']:.1%} WR | {s['sharpe']:.2f} Sharpe")
    except Exception as e:
        print(f"{year}: Error - {e}")
