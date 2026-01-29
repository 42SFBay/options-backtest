"""
Dynamic Rule Engine for Options Trading.

Rules can change parameters daily based on market conditions.
Supports:
- Profit target / stop loss adjustments
- Delta adjustments
- Position sizing adjustments
- Entry/skip conditions

Usage:
    from src.rules import RuleEngine, Rule, Condition
    
    engine = RuleEngine()
    engine.add_rule(
        Rule(
            name="calm_market",
            conditions=[Condition("vix", "<", 18)],
            params={"profit_target_pct": 0.15, "stop_loss_pct": 0.15}
        )
    )
    engine.add_rule(
        Rule(
            name="volatile_market",
            conditions=[Condition("vix", ">=", 18)],
            params={"profit_target_pct": 0.30, "stop_loss_pct": 0.50}
        )
    )
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass
class Condition:
    """
    A single condition to evaluate.
    
    Examples:
        Condition("vix", "<", 18)
        Condition("gap", "<=", 0.5)
        Condition("above_sma20", "==", True)
        Condition("day_of_week", "not_in", ["Thursday"])
        Condition("momentum_5d", "between", (-0.01, 0.01))
    """
    field: str
    operator: str  # <, <=, >, >=, ==, !=, in, not_in, between
    value: Any
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate condition against context."""
        if self.field not in context:
            return False
        
        actual = context[self.field]
        
        if self.operator == "<":
            return actual < self.value
        elif self.operator == "<=":
            return actual <= self.value
        elif self.operator == ">":
            return actual > self.value
        elif self.operator == ">=":
            return actual >= self.value
        elif self.operator == "==":
            return actual == self.value
        elif self.operator == "!=":
            return actual != self.value
        elif self.operator == "in":
            return actual in self.value
        elif self.operator == "not_in":
            return actual not in self.value
        elif self.operator == "between":
            low, high = self.value
            return low <= actual <= high
        else:
            raise ValueError(f"Unknown operator: {self.operator}")
    
    def __repr__(self):
        return f"{self.field} {self.operator} {self.value}"


@dataclass
class Rule:
    """
    A rule that maps conditions to trading parameters.
    
    All conditions must be True for the rule to apply.
    Higher priority rules are evaluated first.
    """
    name: str
    conditions: List[Condition]
    params: Dict[str, Any]  # Parameters to apply when rule matches
    priority: int = 0  # Higher = evaluated first
    
    def matches(self, context: Dict[str, Any]) -> bool:
        """Check if all conditions are met."""
        return all(c.evaluate(context) for c in self.conditions)
    
    def __repr__(self):
        conds = " AND ".join(str(c) for c in self.conditions)
        return f"Rule({self.name}: if {conds} -> {self.params})"


@dataclass 
class RuleSet:
    """A named collection of rules for A/B testing."""
    name: str
    description: str
    rules: List[Rule] = field(default_factory=list)
    default_params: Dict[str, Any] = field(default_factory=dict)
    
    def add_rule(self, rule: Rule):
        self.rules.append(rule)
        self.rules.sort(key=lambda r: -r.priority)  # Higher priority first


class RuleEngine:
    """
    Engine that evaluates rules and returns parameters for each day.
    """
    
    def __init__(self, default_params: Dict[str, Any] = None):
        self.rules: List[Rule] = []
        self.default_params = default_params or {
            "delta": 0.15,
            "wing_width": 30,
            "dte": 2,
            "profit_target_pct": None,
            "stop_loss_pct": None,
            "contracts": 1,
            "skip": False,  # If True, skip trading this day
        }
    
    def add_rule(self, rule: Rule):
        """Add a rule to the engine."""
        self.rules.append(rule)
        # Sort by priority (higher first)
        self.rules.sort(key=lambda r: -r.priority)
    
    def clear_rules(self):
        """Remove all rules."""
        self.rules = []
    
    def get_params(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate rules and return parameters for the given context.
        
        First matching rule wins (by priority).
        Multiple rules can match if they don't conflict.
        """
        params = self.default_params.copy()
        applied_rules = []
        
        for rule in self.rules:
            if rule.matches(context):
                # Merge params (rule overrides defaults)
                params.update(rule.params)
                applied_rules.append(rule.name)
        
        params["_applied_rules"] = applied_rules
        return params
    
    def build_context(
        self,
        date: str,
        underlying_price: float,
        vix: float,
        prices_df: pd.DataFrame,
        vix_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Build context dictionary for rule evaluation.
        
        Computes all commonly-used features:
        - vix: VIX value
        - day_of_week: Monday, Tuesday, etc.
        - gap: Overnight gap percentage
        - momentum_5d: 5-day price momentum
        - above_sma20: True if price > 20-day SMA
        - above_sma50: True if price > 50-day SMA
        - vix_vs_avg: VIX relative to 10-day average
        - etc.
        """
        from datetime import datetime
        
        dt = pd.Timestamp(date)
        # Handle timezone-naive vs timezone-aware comparison
        if hasattr(prices_df.index, 'tz') and prices_df.index.tz is not None:
            dt = dt.tz_localize(prices_df.index.tz)
        dt_vix = pd.Timestamp(date)
        if hasattr(vix_df.index, 'tz') and vix_df.index.tz is not None:
            dt_vix = dt_vix.tz_localize(vix_df.index.tz)
        context = {
            "date": date,
            "underlying_price": underlying_price,
            "vix": vix,
            "day_of_week": dt.strftime("%A"),
            "month": dt.month,
            "month_name": dt.strftime("%B"),
        }
        
        # Calculate technical indicators if we have history
        try:
            # Handle timezone - try to find the date in the index
            try:
                loc = prices_df.index.get_loc(dt)
            except KeyError:
                # Try to find nearest match
                loc = prices_df.index.get_indexer([dt], method='nearest')[0]
            
            # Overnight gap
            if loc > 0:
                prev_close = prices_df.iloc[loc - 1]["Close"]
                current_open = prices_df.iloc[loc]["Open"]
                context["gap"] = abs((current_open - prev_close) / prev_close * 100)
            else:
                context["gap"] = 0
            
            # SMAs
            if loc >= 20:
                sma20 = prices_df.iloc[loc-20:loc]["Close"].mean()
                context["sma20"] = sma20
                context["above_sma20"] = underlying_price > sma20
            if loc >= 50:
                sma50 = prices_df.iloc[loc-50:loc]["Close"].mean()
                context["sma50"] = sma50
                context["above_sma50"] = underlying_price > sma50
            
            # Momentum
            if loc >= 5:
                price_5d_ago = prices_df.iloc[loc - 5]["Close"]
                context["momentum_5d"] = (underlying_price - price_5d_ago) / price_5d_ago
            if loc >= 10:
                price_10d_ago = prices_df.iloc[loc - 10]["Close"]
                context["momentum_10d"] = (underlying_price - price_10d_ago) / price_10d_ago
            
            # Consecutive down days
            down_days = 0
            for i in range(loc - 1, max(0, loc - 10), -1):
                if prices_df.iloc[i]["Close"] < prices_df.iloc[i-1]["Close"]:
                    down_days += 1
                else:
                    break
            context["consecutive_down_days"] = down_days
            
        except (KeyError, IndexError):
            pass
        
        # VIX-based features
        try:
            vix_loc = vix_df.index.get_indexer([dt_vix], method='nearest')[0]
            if vix_loc >= 10:
                vix_10d_avg = vix_df.iloc[vix_loc-10:vix_loc]["Close"].mean()
                context["vix_10d_avg"] = vix_10d_avg
                context["vix_vs_avg"] = vix / vix_10d_avg if vix_10d_avg > 0 else 1.0
        except (KeyError, IndexError):
            pass
        
        return context


# ============================================================
# PREDEFINED RULE SETS
# ============================================================

def create_baseline_rules() -> RuleEngine:
    """
    Baseline: Fixed 0.15/0.15 PT/SL regardless of conditions.
    """
    engine = RuleEngine({
        "delta": 0.15,
        "wing_width": 30,
        "dte": 2,
        "profit_target_pct": 0.15,
        "stop_loss_pct": 0.15,
        "skip": False,
    })
    return engine


def create_vix_adaptive_rules() -> RuleEngine:
    """
    Adaptive PT/SL based on VIX levels.
    
    Low VIX (<15): Tight exits, small gains are fine
    Normal VIX (15-20): Standard exits
    High VIX (>20): Wider stops to ride volatility
    """
    engine = RuleEngine({
        "delta": 0.15,
        "wing_width": 30,
        "dte": 2,
        "profit_target_pct": 0.50,
        "stop_loss_pct": 1.0,
        "skip": False,
    })
    
    # Low VIX: tight exits
    engine.add_rule(Rule(
        name="low_vix",
        conditions=[Condition("vix", "<", 15)],
        params={"profit_target_pct": 0.15, "stop_loss_pct": 0.15},
        priority=10,
    ))
    
    # Normal VIX: moderate exits
    engine.add_rule(Rule(
        name="normal_vix",
        conditions=[
            Condition("vix", ">=", 15),
            Condition("vix", "<=", 20),
        ],
        params={"profit_target_pct": 0.30, "stop_loss_pct": 0.30},
        priority=10,
    ))
    
    # High VIX: skip (or wide stops)
    engine.add_rule(Rule(
        name="high_vix",
        conditions=[Condition("vix", ">", 20)],
        params={"skip": True},  # Skip when VIX is high
        priority=10,
    ))
    
    return engine


def create_momentum_adaptive_rules() -> RuleEngine:
    """
    Adjust delta asymmetry based on momentum.
    Also adjust PT/SL based on trend strength.
    """
    engine = RuleEngine({
        "delta": 0.15,
        "delta_put": 0.15,
        "delta_call": 0.15,
        "wing_width": 30,
        "dte": 2,
        "profit_target_pct": 0.25,
        "stop_loss_pct": 0.50,
        "skip": False,
    })
    
    # Strong uptrend: tight PT (take profits), asymmetric delta
    engine.add_rule(Rule(
        name="strong_uptrend",
        conditions=[Condition("momentum_5d", ">", 0.02)],
        params={
            "delta_put": 0.10, 
            "delta_call": 0.20,
            "profit_target_pct": 0.15,
            "stop_loss_pct": 0.30,
        },
        priority=20,
    ))
    
    # Mild uptrend
    engine.add_rule(Rule(
        name="mild_uptrend",
        conditions=[
            Condition("momentum_5d", ">", 0.005),
            Condition("momentum_5d", "<=", 0.02),
        ],
        params={
            "delta_put": 0.12,
            "delta_call": 0.18,
            "profit_target_pct": 0.20,
            "stop_loss_pct": 0.35,
        },
        priority=15,
    ))
    
    # Mild downtrend
    engine.add_rule(Rule(
        name="mild_downtrend",
        conditions=[
            Condition("momentum_5d", "<", -0.005),
            Condition("momentum_5d", ">=", -0.02),
        ],
        params={
            "delta_put": 0.18,
            "delta_call": 0.12,
            "profit_target_pct": 0.20,
            "stop_loss_pct": 0.35,
        },
        priority=15,
    ))
    
    # Strong downtrend: skip or very asymmetric
    engine.add_rule(Rule(
        name="strong_downtrend",
        conditions=[Condition("momentum_5d", "<", -0.02)],
        params={"skip": True},
        priority=20,
    ))
    
    return engine


def create_gap_filter_rules() -> RuleEngine:
    """
    Skip days with large overnight gaps.
    Use tight exits on calm days, wider on moderate gaps.
    """
    engine = RuleEngine({
        "delta": 0.15,
        "wing_width": 30,
        "dte": 2,
        "profit_target_pct": 0.30,
        "stop_loss_pct": 0.50,
        "skip": False,
    })
    
    # No gap: very tight exits (0.15/0.15)
    engine.add_rule(Rule(
        name="no_gap",
        conditions=[Condition("gap", "<", 0.2)],
        params={"profit_target_pct": 0.15, "stop_loss_pct": 0.15},
        priority=20,
    ))
    
    # Small gap: moderate exits
    engine.add_rule(Rule(
        name="small_gap",
        conditions=[
            Condition("gap", ">=", 0.2),
            Condition("gap", "<", 0.5),
        ],
        params={"profit_target_pct": 0.25, "stop_loss_pct": 0.30},
        priority=15,
    ))
    
    # Large gap: skip
    engine.add_rule(Rule(
        name="large_gap",
        conditions=[Condition("gap", ">=", 0.5)],
        params={"skip": True},
        priority=25,
    ))
    
    return engine


def create_combined_adaptive_rules() -> RuleEngine:
    """
    Combines VIX, momentum, gap, and day-of-week into a comprehensive rule set.
    """
    engine = RuleEngine({
        "delta": 0.15,
        "delta_put": 0.15,
        "delta_call": 0.15,
        "wing_width": 30,
        "dte": 2,
        "profit_target_pct": 0.30,
        "stop_loss_pct": 0.50,
        "skip": False,
    })
    
    # SKIP CONDITIONS (highest priority)
    
    # Skip Thursdays (found to underperform)
    engine.add_rule(Rule(
        name="skip_thursday",
        conditions=[Condition("day_of_week", "==", "Thursday")],
        params={"skip": True},
        priority=100,
    ))
    
    # Skip high VIX
    engine.add_rule(Rule(
        name="skip_high_vix",
        conditions=[Condition("vix", ">", 20)],
        params={"skip": True},
        priority=100,
    ))
    
    # Skip large gaps
    engine.add_rule(Rule(
        name="skip_large_gap",
        conditions=[Condition("gap", ">", 0.5)],
        params={"skip": True},
        priority=100,
    ))
    
    # VIX SWEET SPOT (16-17): Tight exits, best conditions
    engine.add_rule(Rule(
        name="vix_sweet_spot",
        conditions=[
            Condition("vix", ">=", 16),
            Condition("vix", "<=", 17),
            Condition("gap", "<", 0.5),
        ],
        params={"profit_target_pct": 0.15, "stop_loss_pct": 0.15},
        priority=50,
    ))
    
    # LOW VIX (<15): Can afford tight exits
    engine.add_rule(Rule(
        name="low_vix_tight",
        conditions=[
            Condition("vix", "<", 15),
            Condition("gap", "<", 0.3),
        ],
        params={"profit_target_pct": 0.15, "stop_loss_pct": 0.15},
        priority=40,
    ))
    
    # NORMAL VIX with small gap
    engine.add_rule(Rule(
        name="normal_vix_calm",
        conditions=[
            Condition("vix", ">=", 15),
            Condition("vix", "<=", 20),
            Condition("gap", "<", 0.3),
        ],
        params={"profit_target_pct": 0.20, "stop_loss_pct": 0.25},
        priority=30,
    ))
    
    # MOMENTUM ADJUSTMENTS (delta asymmetry)
    engine.add_rule(Rule(
        name="uptrend_asymmetric",
        conditions=[Condition("momentum_5d", ">", 0.015)],
        params={"delta_put": 0.10, "delta_call": 0.20},
        priority=20,
    ))
    
    engine.add_rule(Rule(
        name="downtrend_asymmetric",
        conditions=[Condition("momentum_5d", "<", -0.015)],
        params={"delta_put": 0.20, "delta_call": 0.10},
        priority=20,
    ))
    
    return engine


# ============================================================
# RULE SET REGISTRY
# ============================================================

RULE_SETS = {
    "baseline": ("Fixed 0.15/0.15 PT/SL", create_baseline_rules),
    "vix_adaptive": ("PT/SL based on VIX levels", create_vix_adaptive_rules),
    "momentum": ("Delta asymmetry based on momentum", create_momentum_adaptive_rules),
    "gap_filter": ("PT/SL based on overnight gap", create_gap_filter_rules),
    "combined": ("VIX + momentum + gap + day-of-week", create_combined_adaptive_rules),
}


def list_rule_sets():
    """Print available rule sets."""
    print("\nAvailable Rule Sets:")
    print("-" * 60)
    for name, (desc, _) in RULE_SETS.items():
        print(f"  {name:20s} - {desc}")


def get_rule_engine(name: str) -> RuleEngine:
    """Get a rule engine by name."""
    if name not in RULE_SETS:
        raise ValueError(f"Unknown rule set: {name}. Use list_rule_sets() to see options.")
    return RULE_SETS[name][1]()
