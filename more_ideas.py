#!/usr/bin/env python3
"""
More hypotheses - dynamic sizing, time-based, etc.
"""
import sys
sys.path.insert(0, '/home/ubuntu/clawd/projects/options-backtest')
from src.rules import RuleEngine, Rule, Condition
from run_rules_backtest import DynamicBacktestEngine

START, END = "2021-01-01", "2026-01-01"
engine_instance = DynamicBacktestEngine(symbol="SPX", start_date=START, end_date=END)

def run(engine, name):
    result = engine_instance.run_with_rules(engine, verbose=False)
    s = result["stats"]
    print(f"{name:40s}: ${s['total_pnl']:>10,.0f} | {s['total_trades']:>4} | {s['win_rate']:.1%} | {s['sharpe']:.2f}")
    return s

print("=" * 80)
print("MORE IDEAS")
print("=" * 80)

# 1. Dynamic delta based on VIX (lower delta when VIX high)
print("\n### Dynamic Delta based on VIX ###")
engine = RuleEngine({
    "delta": 0.22, "wing_width": 60, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("low_vix", [Condition("vix", "<", 15)], {"delta": 0.25}, 50))
engine.add_rule(Rule("med_vix", [Condition("vix", ">=", 15), Condition("vix", "<", 20)], {"delta": 0.22}, 50))
engine.add_rule(Rule("high_vix", [Condition("vix", ">=", 20)], {"delta": 0.18}, 50))
run(engine, "dynamic_delta_vix")

# 2. Skip specific problematic market conditions
print("\n### Skip specific conditions ###")
engine = RuleEngine({
    "delta": 0.22, "wing_width": 60, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
# Skip when VIX > 30 (extreme)
engine.add_rule(Rule("skip_extreme_vix", [Condition("vix", ">", 30)], {"skip": True}, 100))
run(engine, "skip_vix_over_30")

# 3. Skip when VIX > 25
engine = RuleEngine({
    "delta": 0.22, "wing_width": 60, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_high_vix", [Condition("vix", ">", 25)], {"skip": True}, 100))
run(engine, "skip_vix_over_25")

# 4. Dynamic wing based on VIX (wider when VIX high)
print("\n### Dynamic Wing based on VIX ###")
engine = RuleEngine({
    "delta": 0.22, "wing_width": 50, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("low_vix", [Condition("vix", "<", 18)], {"wing_width": 50}, 50))
engine.add_rule(Rule("high_vix", [Condition("vix", ">=", 18)], {"wing_width": 80}, 50))
run(engine, "dynamic_wing_vix")

# 5. Only trade Tues/Wed (best days based on individual tests)
print("\n### Trade only Tue/Wed/Fri ###")
engine = RuleEngine({
    "delta": 0.22, "wing_width": 60, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_mon_thu", [Condition("day_of_week", "in", ["Monday", "Thursday"])], {"skip": True}, 100))
run(engine, "only_tue_wed_fri")

# 6. Skip Monday (weekend gap effect) + Thursday
engine = RuleEngine({
    "delta": 0.22, "wing_width": 60, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_mon_thu", [Condition("day_of_week", "in", ["Monday", "Thursday"])], {"skip": True}, 100))
run(engine, "skip_mon_thu_d22_w60")

# 7. Combo: Skip Thu + VIX < 25 + higher params
print("\n### Best combos with filters ###")
engine = RuleEngine({
    "delta": 0.25, "wing_width": 70, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_thu", [Condition("day_of_week", "==", "Thursday")], {"skip": True}, 100))
engine.add_rule(Rule("skip_vix25", [Condition("vix", ">", 25)], {"skip": True}, 100))
run(engine, "thu_vix25_d25_w70")

# 8. Conservative high sharpe with decent P&L
engine = RuleEngine({
    "delta": 0.18, "wing_width": 50, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_thu", [Condition("day_of_week", "==", "Thursday")], {"skip": True}, 100))
engine.add_rule(Rule("skip_vix20", [Condition("vix", ">", 20)], {"skip": True}, 100))
run(engine, "conservative_thu_vix20_d18_w50")

# 9. Trade only when momentum positive (uptrend)
print("\n### Momentum filters ###")
engine = RuleEngine({
    "delta": 0.22, "wing_width": 60, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_down", [Condition("momentum_5d", "<", -0.02)], {"skip": True}, 100))
run(engine, "skip_strong_downtrend")

# 10. Skip big down days (gap < -0.5%)
engine = RuleEngine({
    "delta": 0.22, "wing_width": 60, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_down_gap", [Condition("gap", "<", -0.5)], {"skip": True}, 100))
run(engine, "skip_negative_gap_05")

# 11. Opposite - only trade on down days (contrarian)
engine = RuleEngine({
    "delta": 0.22, "wing_width": 60, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("only_down", [Condition("gap", ">", 0)], {"skip": True}, 100))
run(engine, "contrarian_only_down_gap")

# 12. Skip both extremes (gap > 1% or gap < -1%)
engine = RuleEngine({
    "delta": 0.22, "wing_width": 60, "dte": 2,
    "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
})
engine.add_rule(Rule("skip_up_gap", [Condition("gap", ">", 1.0)], {"skip": True}, 100))
engine.add_rule(Rule("skip_down_gap", [Condition("gap", "<", -1.0)], {"skip": True}, 100))
run(engine, "skip_extreme_gaps_1pct")

print("\n" + "=" * 80)
print("FINAL BEST CONFIG CANDIDATES")
print("=" * 80)

# Best P&L with reasonable risk
configs = [
    {"delta": 0.25, "wing": 70, "name": "max_pnl_d25_w70"},
    {"delta": 0.22, "wing": 60, "skip_thu": True, "name": "balanced_thu_d22_w60"},
    {"delta": 0.25, "wing": 60, "skip_thu": True, "name": "high_pnl_thu_d25_w60"},
    {"delta": 0.22, "wing": 60, "skip_vix": 25, "name": "safe_vix25_d22_w60"},
]

for cfg in configs:
    engine = RuleEngine({
        "delta": cfg["delta"], "wing_width": cfg["wing"], "dte": 2,
        "profit_target_pct": 0.30, "stop_loss_pct": 0.50, "skip": False,
    })
    if cfg.get("skip_thu"):
        engine.add_rule(Rule("skip_thu", [Condition("day_of_week", "==", "Thursday")], {"skip": True}, 100))
    if cfg.get("skip_vix"):
        engine.add_rule(Rule("skip_vix", [Condition("vix", ">", cfg["skip_vix"])], {"skip": True}, 100))
    run(engine, cfg["name"])
