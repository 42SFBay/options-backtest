"""
Backtest with Dynamic Rules.

Compares different rule sets and their performance.

Usage:
    python run_rules_backtest.py                    # Run all rule sets
    python run_rules_backtest.py --ruleset baseline # Run specific rule set
    python run_rules_backtest.py --compare          # Compare all rule sets
"""
import argparse
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

# Add project to path
sys.path.insert(0, '/home/ubuntu/clawd/projects/options-backtest')

from src.data import DataManager, SimulatedOptionsData
from src.rules import (
    RuleEngine, Rule, Condition,
    RULE_SETS, get_rule_engine, list_rule_sets,
    create_baseline_rules, create_combined_adaptive_rules,
)
from src.strategies.iron_condor import IronCondorStrategy, IronCondorConfig, IronCondorPosition
from src.utils.pricing import iron_condor_pnl_at_expiry


class DynamicBacktestEngine:
    """
    Backtesting engine with dynamic rule support.
    """
    
    def __init__(
        self,
        symbol: str = 'SPX',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        self.symbol = symbol
        self.dm = DataManager()
        
        # Default to last year
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=365)
            start_date = start_dt.strftime('%Y-%m-%d')
        
        self.start_date = start_date
        self.end_date = end_date
        
        # Load data
        print(f"Loading data for {symbol} from {start_date} to {end_date}...")
        self.prices = self.dm.get_underlying_prices(symbol, start_date, end_date)
        self.vix = self.dm.get_vix_data(start_date, end_date)
        print(f"Loaded {len(self.prices)} trading days")
    
    def run_with_rules(
        self,
        rule_engine: RuleEngine,
        verbose: bool = False,
    ) -> Dict:
        """
        Run backtest with dynamic rules.
        
        Rules are evaluated each day to determine trading parameters.
        """
        positions: List[IronCondorPosition] = []
        open_positions: List[IronCondorPosition] = []
        skipped_days = []
        rule_applications = []  # Track which rules applied each day
        
        sim_data = SimulatedOptionsData(self.dm)
        trading_days = list(self.prices.index)
        
        for i, current_date in enumerate(trading_days):
            date_str = current_date.strftime('%Y-%m-%d')
            day_of_week = current_date.strftime('%A')
            
            underlying_price = self.prices.loc[current_date, 'Close']
            
            # Get VIX
            try:
                vix_value = self.vix.loc[current_date, 'Close']
            except KeyError:
                vix_idx = self.vix.index.get_indexer([current_date], method='nearest')[0]
                vix_value = self.vix.iloc[vix_idx]['Close']
            
            # Build context for rule evaluation
            context = rule_engine.build_context(
                date_str, underlying_price, vix_value,
                self.prices, self.vix
            )
            
            # Get dynamic parameters
            params = rule_engine.get_params(context)
            applied_rules = params.get("_applied_rules", [])
            
            if verbose and applied_rules:
                print(f"{date_str}: VIX={vix_value:.1f}, gap={context.get('gap', 0):.2f}%, "
                      f"rules={applied_rules}")
            
            rule_applications.append({
                "date": date_str,
                "vix": vix_value,
                "gap": context.get("gap", 0),
                "momentum_5d": context.get("momentum_5d", 0),
                "rules": applied_rules,
                "skip": params.get("skip", False),
                "profit_target_pct": params.get("profit_target_pct"),
                "stop_loss_pct": params.get("stop_loss_pct"),
            })
            
            # Check open positions for exit (using that day's params)
            still_open = []
            for pos in open_positions:
                expiry_dt = datetime.strptime(pos.expiry_date, '%Y-%m-%d')
                current_dt = current_date.to_pydatetime().replace(tzinfo=None)
                days_remaining = max(0, (expiry_dt - current_dt).days)
                
                current_iv = self.dm.estimate_iv_from_vix(vix_value, days_remaining)
                
                should_exit, reason, pnl = self._check_exit_with_params(
                    pos, date_str, underlying_price, current_iv, days_remaining, params
                )
                
                if should_exit:
                    pos.exit_date = date_str
                    pos.pnl = pnl
                    pos.exit_reason = reason
                else:
                    still_open.append(pos)
            
            open_positions = still_open
            
            # Skip entry if rules say so
            if params.get("skip", False):
                skipped_days.append(date_str)
                continue
            
            # Create new position with dynamic params
            config = IronCondorConfig(
                delta=params.get("delta", 0.15),
                wing_width=params.get("wing_width", 30),
                dte=params.get("dte", 2),
                profit_target_pct=params.get("profit_target_pct"),
                stop_loss_pct=params.get("stop_loss_pct"),
            )
            
            # Calculate expiry date
            expiry_date = self.dm.get_expiry_date(date_str, config.dte)
            expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
            last_day = trading_days[-1].to_pydatetime().replace(tzinfo=None)
            if expiry_dt > last_day:
                continue
            
            entry_iv = self.dm.estimate_iv_from_vix(vix_value, config.dte)
            
            # Create position (handling asymmetric deltas and sizing)
            delta_put = params.get("delta_put", config.delta)
            delta_call = params.get("delta_call", config.delta)
            contracts = int(params.get("contracts", 1))
            
            pos = self._create_position_with_params(
                date_str, expiry_date, self.symbol,
                underlying_price, entry_iv, config.dte,
                delta_put, delta_call, config.wing_width, contracts
            )
            if pos:
                positions.append(pos)
                open_positions.append(pos)
        
        # Close remaining positions at final day
        final_date = trading_days[-1].strftime('%Y-%m-%d')
        final_price = self.prices.iloc[-1]['Close']
        for pos in open_positions:
            pnl = iron_condor_pnl_at_expiry(
                final_price,
                pos.call_short_strike, pos.call_long_strike,
                pos.put_short_strike, pos.put_long_strike,
                pos.credit_received / (100 * pos.contracts)
            ) * 100 * pos.contracts
            pos.exit_date = final_date
            pos.pnl = pnl
            pos.exit_reason = 'end_of_backtest'
        
        # Calculate statistics
        stats = self._calculate_stats(positions)
        
        return {
            "stats": stats,
            "trades": len(positions),
            "skipped_days": len(skipped_days),
            "positions": positions,
            "rule_applications": rule_applications,
        }
    
    def _create_position_with_params(
        self,
        date: str,
        expiry_date: str,
        symbol: str,
        underlying_price: float,
        iv: float,
        dte: int,
        delta_put: float,
        delta_call: float,
        wing_width: int,
        contracts: int = 1,
    ) -> Optional[IronCondorPosition]:
        """Create position with potentially asymmetric deltas and variable sizing."""
        from src.utils.pricing import find_strike_by_delta, calculate_iron_condor_credit
        
        T = dte / 365.0
        risk_free_rate = 0.05
        
        # Find strikes
        call_short = find_strike_by_delta(
            underlying_price, T, risk_free_rate, iv,
            target_delta=delta_call, option_type='call', precision=5.0
        )
        put_short = find_strike_by_delta(
            underlying_price, T, risk_free_rate, iv,
            target_delta=-delta_put, option_type='put', precision=5.0
        )
        
        call_long = call_short + wing_width
        put_long = put_short - wing_width
        
        # Calculate credit
        credit, _, _, max_loss, _, _ = calculate_iron_condor_credit(
            underlying_price,
            call_short, call_long,
            put_short, put_long,
            T, risk_free_rate, iv
        )
        
        return IronCondorPosition(
            entry_date=date,
            expiry_date=expiry_date,
            underlying_symbol=symbol,
            underlying_price=underlying_price,
            put_long_strike=put_long,
            put_short_strike=put_short,
            call_short_strike=call_short,
            call_long_strike=call_long,
            entry_delta_call=delta_call,
            entry_delta_put=-delta_put,
            entry_iv=iv,
            credit_received=credit * 100 * contracts,
            max_loss=max_loss * 100 * contracts,
            contracts=contracts,
        )
    
    def _check_exit_with_params(
        self,
        position: IronCondorPosition,
        current_date: str,
        underlying_price: float,
        current_iv: float,
        days_remaining: int,
        params: Dict,
    ):
        """Check exit with dynamic PT/SL parameters."""
        from src.utils.pricing import calculate_iron_condor_credit
        
        T = days_remaining / 365.0
        
        if T <= 0:
            pnl = iron_condor_pnl_at_expiry(
                underlying_price,
                position.call_short_strike, position.call_long_strike,
                position.put_short_strike, position.put_long_strike,
                position.credit_received / 100
            ) * 100
            return True, 'expiry', pnl
        
        # Current theoretical value
        current_credit, _, _, _, _, _ = calculate_iron_condor_credit(
            underlying_price,
            position.call_short_strike, position.call_long_strike,
            position.put_short_strike, position.put_long_strike,
            T, 0.05, current_iv
        )
        current_value = current_credit * 100
        pnl = position.credit_received - current_value
        
        # Dynamic PT/SL
        profit_target_pct = params.get("profit_target_pct")
        stop_loss_pct = params.get("stop_loss_pct")
        
        if profit_target_pct:
            target_pnl = position.credit_received * profit_target_pct
            if pnl >= target_pnl:
                return True, 'profit_target', pnl
        
        if stop_loss_pct:
            max_loss = position.credit_received * stop_loss_pct
            if pnl <= -max_loss:
                return True, 'stop_loss', pnl
        
        return False, None, pnl
    
    def _calculate_stats(self, positions: List[IronCondorPosition]) -> Dict:
        """Calculate statistics from positions."""
        closed = [p for p in positions if p.pnl is not None]
        
        if not closed:
            return {"total_trades": 0}
        
        pnls = [p.pnl for p in closed]
        wins = [p for p in closed if p.pnl > 0]
        losses = [p for p in closed if p.pnl <= 0]
        
        return {
            'total_trades': len(closed),
            'total_pnl': sum(pnls),
            'win_rate': len(wins) / len(closed) if closed else 0,
            'avg_pnl': np.mean(pnls) if pnls else 0,
            'avg_win': np.mean([p.pnl for p in wins]) if wins else 0,
            'avg_loss': np.mean([p.pnl for p in losses]) if losses else 0,
            'max_win': max(pnls) if pnls else 0,
            'max_loss': min(pnls) if pnls else 0,
            'sharpe': np.mean(pnls) / np.std(pnls) if np.std(pnls) > 0 else 0,
            'by_exit_reason': {
                reason: len([p for p in closed if p.exit_reason == reason])
                for reason in set(p.exit_reason for p in closed)
            }
        }


def compare_rule_sets(
    symbol: str = 'SPX',
    start_date: str = None,
    end_date: str = None,
):
    """Compare all rule sets."""
    engine = DynamicBacktestEngine(symbol, start_date, end_date)
    
    results = []
    for name, (desc, factory) in RULE_SETS.items():
        print(f"\n{'='*60}")
        print(f"Testing: {name} - {desc}")
        print('='*60)
        
        rule_engine = factory()
        result = engine.run_with_rules(rule_engine)
        
        stats = result["stats"]
        results.append({
            "rule_set": name,
            "description": desc,
            "trades": result["trades"],
            "skipped": result["skipped_days"],
            "win_rate": stats.get("win_rate", 0),
            "total_pnl": stats.get("total_pnl", 0),
            "avg_pnl": stats.get("avg_pnl", 0),
            "sharpe": stats.get("sharpe", 0),
        })
        
        print(f"Trades: {result['trades']} ({result['skipped_days']} skipped)")
        print(f"Win Rate: {stats.get('win_rate', 0)*100:.1f}%")
        print(f"Total P&L: ${stats.get('total_pnl', 0):,.0f}")
        print(f"Sharpe: {stats.get('sharpe', 0):.2f}")
    
    # Summary table
    print("\n" + "="*80)
    print("COMPARISON SUMMARY")
    print("="*80)
    
    df = pd.DataFrame(results)
    df = df.sort_values("sharpe", ascending=False)
    
    print(df.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    
    return df


def main():
    parser = argparse.ArgumentParser(description='Dynamic Rules Backtest')
    parser.add_argument('--symbol', type=str, default='SPX')
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--ruleset', type=str, help='Specific rule set to test')
    parser.add_argument('--compare', action='store_true', help='Compare all rule sets')
    parser.add_argument('--list', action='store_true', help='List available rule sets')
    parser.add_argument('--verbose', action='store_true', help='Show rule applications')
    
    args = parser.parse_args()
    
    if args.list:
        list_rule_sets()
        return
    
    if args.compare:
        compare_rule_sets(args.symbol, args.start, args.end)
        return
    
    # Run single rule set
    engine = DynamicBacktestEngine(args.symbol, args.start, args.end)
    
    if args.ruleset:
        rule_engine = get_rule_engine(args.ruleset)
        print(f"Using rule set: {args.ruleset}")
    else:
        rule_engine = create_baseline_rules()
        print("Using baseline rules (0.15/0.15 PT/SL)")
    
    result = engine.run_with_rules(rule_engine, verbose=args.verbose)
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    stats = result["stats"]
    print(f"Trades: {result['trades']}")
    print(f"Skipped Days: {result['skipped_days']}")
    print(f"Win Rate: {stats.get('win_rate', 0)*100:.1f}%")
    print(f"Total P&L: ${stats.get('total_pnl', 0):,.0f}")
    print(f"Avg P&L: ${stats.get('avg_pnl', 0):,.0f}")
    print(f"Sharpe: {stats.get('sharpe', 0):.2f}")
    print(f"Exit Reasons: {stats.get('by_exit_reason', {})}")


if __name__ == '__main__':
    main()
