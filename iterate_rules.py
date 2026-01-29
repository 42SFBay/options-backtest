"""
Rule Iteration Script - Tests variations of rule parameters.
"""
import sys
sys.path.insert(0, '/home/ubuntu/clawd/projects/options-backtest')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from src.rules import RuleEngine, Rule, Condition
from run_rules_backtest import DynamicBacktestEngine


def create_parameterized_combined_rules(
    pt_low_vix: float = 0.15,
    sl_low_vix: float = 0.15,
    pt_sweet_spot: float = 0.15,
    sl_sweet_spot: float = 0.15,
    pt_normal: float = 0.20,
    sl_normal: float = 0.25,
    skip_thursday: bool = True,
    skip_vix_above: float = 20,
    skip_gap_above: float = 0.5,
    vix_sweet_low: float = 16,
    vix_sweet_high: float = 17,
) -> RuleEngine:
    """
    Create combined rules with parameterized PT/SL values.
    """
    engine = RuleEngine({
        "delta": 0.15,
        "delta_put": 0.15,
        "delta_call": 0.15,
        "wing_width": 30,
        "dte": 2,
        "profit_target_pct": pt_normal,
        "stop_loss_pct": sl_normal,
        "skip": False,
    })
    
    # SKIP CONDITIONS
    if skip_thursday:
        engine.add_rule(Rule(
            name="skip_thursday",
            conditions=[Condition("day_of_week", "==", "Thursday")],
            params={"skip": True},
            priority=100,
        ))
    
    if skip_vix_above:
        engine.add_rule(Rule(
            name="skip_high_vix",
            conditions=[Condition("vix", ">", skip_vix_above)],
            params={"skip": True},
            priority=100,
        ))
    
    if skip_gap_above:
        engine.add_rule(Rule(
            name="skip_large_gap",
            conditions=[Condition("gap", ">", skip_gap_above)],
            params={"skip": True},
            priority=100,
        ))
    
    # VIX SWEET SPOT
    engine.add_rule(Rule(
        name="vix_sweet_spot",
        conditions=[
            Condition("vix", ">=", vix_sweet_low),
            Condition("vix", "<=", vix_sweet_high),
            Condition("gap", "<", skip_gap_above if skip_gap_above else 999),
        ],
        params={"profit_target_pct": pt_sweet_spot, "stop_loss_pct": sl_sweet_spot},
        priority=50,
    ))
    
    # LOW VIX
    engine.add_rule(Rule(
        name="low_vix_tight",
        conditions=[
            Condition("vix", "<", vix_sweet_low),
            Condition("gap", "<", 0.3),
        ],
        params={"profit_target_pct": pt_low_vix, "stop_loss_pct": sl_low_vix},
        priority=40,
    ))
    
    return engine


def test_pt_sl_grid():
    """Test grid of PT/SL values."""
    print("="*80)
    print("TESTING PT/SL GRID")
    print("="*80)
    
    engine = DynamicBacktestEngine('SPX')
    
    # Test symmetric PT/SL values
    pt_sl_values = [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, None]
    
    results = []
    
    for pt in pt_sl_values:
        for sl in pt_sl_values:
            if pt is None and sl is None:
                label = "hold_to_expiry"
            elif pt is None:
                label = f"SL_{sl:.0%}"
            elif sl is None:
                label = f"PT_{pt:.0%}"
            else:
                label = f"PT{pt:.0%}_SL{sl:.0%}"
            
            print(f"Testing {label}...", end=" ", flush=True)
            
            rule_engine = create_parameterized_combined_rules(
                pt_low_vix=pt,
                sl_low_vix=sl,
                pt_sweet_spot=pt,
                sl_sweet_spot=sl,
                pt_normal=pt,
                sl_normal=sl,
            )
            
            result = engine.run_with_rules(rule_engine)
            stats = result["stats"]
            
            print(f"Sharpe: {stats.get('sharpe', 0):.2f}")
            
            results.append({
                "label": label,
                "pt": pt,
                "sl": sl,
                "trades": result["trades"],
                "win_rate": stats.get("win_rate", 0),
                "total_pnl": stats.get("total_pnl", 0),
                "avg_pnl": stats.get("avg_pnl", 0),
                "sharpe": stats.get("sharpe", 0),
                "max_loss": stats.get("max_loss", 0),
            })
    
    df = pd.DataFrame(results)
    df = df.sort_values("sharpe", ascending=False)
    
    print("\n" + "="*80)
    print("TOP 15 PT/SL COMBINATIONS")
    print("="*80)
    print(df.head(15).to_string(index=False))
    
    return df


def test_skip_conditions():
    """Test different skip condition combinations."""
    print("\n" + "="*80)
    print("TESTING SKIP CONDITIONS")
    print("="*80)
    
    engine = DynamicBacktestEngine('SPX')
    
    skip_configs = [
        {"skip_thursday": False, "skip_vix_above": None, "skip_gap_above": None, "name": "no_skips"},
        {"skip_thursday": True, "skip_vix_above": None, "skip_gap_above": None, "name": "skip_thu_only"},
        {"skip_thursday": False, "skip_vix_above": 20, "skip_gap_above": None, "name": "skip_vix20"},
        {"skip_thursday": False, "skip_vix_above": 18, "skip_gap_above": None, "name": "skip_vix18"},
        {"skip_thursday": False, "skip_vix_above": None, "skip_gap_above": 0.5, "name": "skip_gap0.5"},
        {"skip_thursday": False, "skip_vix_above": None, "skip_gap_above": 0.3, "name": "skip_gap0.3"},
        {"skip_thursday": True, "skip_vix_above": 20, "skip_gap_above": None, "name": "thu+vix20"},
        {"skip_thursday": True, "skip_vix_above": 20, "skip_gap_above": 0.5, "name": "thu+vix20+gap0.5"},
        {"skip_thursday": True, "skip_vix_above": 18, "skip_gap_above": 0.3, "name": "thu+vix18+gap0.3"},
        {"skip_thursday": True, "skip_vix_above": 17, "skip_gap_above": 0.3, "name": "thu+vix17+gap0.3"},
    ]
    
    results = []
    
    for config in skip_configs:
        name = config.pop("name")
        print(f"Testing {name}...", end=" ", flush=True)
        
        rule_engine = create_parameterized_combined_rules(**config)
        result = engine.run_with_rules(rule_engine)
        stats = result["stats"]
        
        print(f"Trades: {result['trades']}, Sharpe: {stats.get('sharpe', 0):.2f}")
        
        results.append({
            "config": name,
            "trades": result["trades"],
            "skipped": result["skipped_days"],
            "win_rate": stats.get("win_rate", 0),
            "total_pnl": stats.get("total_pnl", 0),
            "sharpe": stats.get("sharpe", 0),
        })
    
    df = pd.DataFrame(results)
    df = df.sort_values("sharpe", ascending=False)
    
    print("\n" + "="*80)
    print("SKIP CONDITIONS COMPARISON")
    print("="*80)
    print(df.to_string(index=False))
    
    return df


def test_vix_ranges():
    """Test different VIX sweet spot ranges."""
    print("\n" + "="*80)
    print("TESTING VIX SWEET SPOT RANGES")
    print("="*80)
    
    engine = DynamicBacktestEngine('SPX')
    
    vix_ranges = [
        (14, 16), (15, 17), (16, 17), (16, 18), (14, 18), (15, 18),
        (13, 15), (17, 19), (15, 16), (16, 19),
    ]
    
    results = []
    
    for low, high in vix_ranges:
        print(f"Testing VIX {low}-{high}...", end=" ", flush=True)
        
        rule_engine = create_parameterized_combined_rules(
            vix_sweet_low=low,
            vix_sweet_high=high,
        )
        result = engine.run_with_rules(rule_engine)
        stats = result["stats"]
        
        print(f"Sharpe: {stats.get('sharpe', 0):.2f}")
        
        results.append({
            "vix_range": f"{low}-{high}",
            "trades": result["trades"],
            "win_rate": stats.get("win_rate", 0),
            "total_pnl": stats.get("total_pnl", 0),
            "sharpe": stats.get("sharpe", 0),
        })
    
    df = pd.DataFrame(results)
    df = df.sort_values("sharpe", ascending=False)
    
    print("\n" + "="*80)
    print("VIX RANGES COMPARISON")
    print("="*80)
    print(df.to_string(index=False))
    
    return df


def test_conditional_pt_sl():
    """Test using different PT/SL for different conditions."""
    print("\n" + "="*80)
    print("TESTING CONDITIONAL PT/SL (different values for different VIX)")
    print("="*80)
    
    engine = DynamicBacktestEngine('SPX')
    
    # Test idea: tighter exits when conditions are good, wider when moderate
    configs = [
        # (pt_low, sl_low, pt_sweet, sl_sweet, pt_normal, sl_normal, name)
        (0.15, 0.15, 0.15, 0.15, 0.15, 0.15, "all_0.15"),
        (0.15, 0.15, 0.15, 0.15, 0.25, 0.30, "tight_low_wide_normal"),
        (0.10, 0.10, 0.15, 0.15, 0.20, 0.25, "progressive"),
        (0.20, 0.15, 0.15, 0.15, 0.25, 0.30, "pt_varies"),
        (0.15, 0.20, 0.15, 0.20, 0.15, 0.30, "sl_varies"),
        (None, 0.15, None, 0.15, None, 0.25, "pt_none_sl_varies"),
        (0.15, None, 0.15, None, 0.20, None, "pt_varies_sl_none"),
        (0.10, 0.20, 0.15, 0.25, 0.20, 0.35, "asymmetric"),
    ]
    
    results = []
    
    for pt_low, sl_low, pt_sweet, sl_sweet, pt_normal, sl_normal, name in configs:
        print(f"Testing {name}...", end=" ", flush=True)
        
        rule_engine = create_parameterized_combined_rules(
            pt_low_vix=pt_low,
            sl_low_vix=sl_low,
            pt_sweet_spot=pt_sweet,
            sl_sweet_spot=sl_sweet,
            pt_normal=pt_normal,
            sl_normal=sl_normal,
        )
        result = engine.run_with_rules(rule_engine)
        stats = result["stats"]
        
        print(f"Sharpe: {stats.get('sharpe', 0):.2f}")
        
        results.append({
            "config": name,
            "trades": result["trades"],
            "win_rate": stats.get("win_rate", 0),
            "total_pnl": stats.get("total_pnl", 0),
            "avg_pnl": stats.get("avg_pnl", 0),
            "sharpe": stats.get("sharpe", 0),
        })
    
    df = pd.DataFrame(results)
    df = df.sort_values("sharpe", ascending=False)
    
    print("\n" + "="*80)
    print("CONDITIONAL PT/SL COMPARISON")
    print("="*80)
    print(df.to_string(index=False))
    
    return df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", choices=["pt_sl", "skip", "vix", "conditional", "all"], default="all")
    args = parser.parse_args()
    
    if args.test == "pt_sl" or args.test == "all":
        test_pt_sl_grid()
    
    if args.test == "skip" or args.test == "all":
        test_skip_conditions()
    
    if args.test == "vix" or args.test == "all":
        test_vix_ranges()
    
    if args.test == "conditional" or args.test == "all":
        test_conditional_pt_sl()
