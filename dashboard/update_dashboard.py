#!/usr/bin/env python3
"""
Update dashboard with latest backtest results.

Usage:
    python dashboard/update_dashboard.py
"""
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rules import RuleEngine, Rule, Condition
from run_rules_backtest import DynamicBacktestEngine


def run_all_strategies():
    """Run all strategies and return results."""
    engine = DynamicBacktestEngine('SPX')
    results = []
    
    strategies = [
        {
            "name": "2x when VIX 14-18 + Skip Thu",
            "rules": lambda e: [
                e.add_rule(Rule('skip_thu', [Condition('day_of_week', '==', 'Thursday')], {'skip': True}, 100)),
                e.add_rule(Rule('skip_vix', [Condition('vix', '>', 20)], {'skip': True}, 100)),
                e.add_rule(Rule('size_2x', [Condition('vix', '>=', 14), Condition('vix', '<=', 18)], {'contracts': 2}, 50)),
            ],
            "status": "BEST",
        },
        {
            "name": "Progressive 2x/3x sizing",
            "rules": lambda e: [
                e.add_rule(Rule('skip_thu', [Condition('day_of_week', '==', 'Thursday')], {'skip': True}, 100)),
                e.add_rule(Rule('skip_vix', [Condition('vix', '>', 20)], {'skip': True}, 100)),
                e.add_rule(Rule('size_3x', [Condition('vix', '>=', 16), Condition('vix', '<=', 18)], {'contracts': 3}, 60)),
                e.add_rule(Rule('size_2x', [Condition('vix', '<', 16)], {'contracts': 2}, 50)),
            ],
            "status": "HIGH P&L",
        },
        {
            "name": "Combined filters (no sizing)",
            "rules": lambda e: [
                e.add_rule(Rule('skip_thu', [Condition('day_of_week', '==', 'Thursday')], {'skip': True}, 100)),
                e.add_rule(Rule('skip_vix', [Condition('vix', '>', 20)], {'skip': True}, 100)),
            ],
            "status": "BASELINE",
        },
        {
            "name": "Skip Thursday only",
            "rules": lambda e: [
                e.add_rule(Rule('skip_thu', [Condition('day_of_week', '==', 'Thursday')], {'skip': True}, 100)),
            ],
            "status": "SIMPLE",
        },
        {
            "name": "No filters (baseline)",
            "rules": lambda e: [],
            "status": "AVOID",
        },
    ]
    
    for strat in strategies:
        print(f"Running: {strat['name']}...", end=" ", flush=True)
        
        rule_engine = RuleEngine({
            'delta': 0.15, 'wing_width': 30, 'dte': 2,
            'contracts': 1, 'skip': False,
        })
        strat['rules'](rule_engine)
        
        result = engine.run_with_rules(rule_engine)
        stats = result['stats']
        
        results.append({
            "name": strat['name'],
            "trades": result['trades'],
            "win_rate": stats.get('win_rate', 0),
            "total_pnl": stats.get('total_pnl', 0),
            "sharpe": stats.get('sharpe', 0),
            "status": strat['status'],
        })
        
        print(f"Sharpe: {stats.get('sharpe', 0):.2f}")
    
    return results


def save_results(results):
    """Save results to JSON for dashboard."""
    output = {
        "updated": datetime.now().isoformat(),
        "strategies": results,
        "best_sharpe": max(r['sharpe'] for r in results),
        "best_pnl": max(r['total_pnl'] for r in results),
    }
    
    output_path = Path(__file__).parent / "data.json"
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to {output_path}")
    return output


if __name__ == "__main__":
    print("Updating dashboard with latest backtest results...\n")
    results = run_all_strategies()
    data = save_results(results)
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Best Sharpe: {data['best_sharpe']:.2f}")
    print(f"Best P&L: ${data['best_pnl']:,.0f}")
