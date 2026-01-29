"""
Core backtesting engine for options strategies.

Usage:
    python -m src.backtest --symbol SPX --delta 0.15 --wing 20 --days 60
"""
import argparse
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import pandas as pd
import numpy as np

from .data import DataManager, SimulatedOptionsData
from .strategies.iron_condor import IronCondorStrategy, IronCondorConfig, IronCondorPosition


class BacktestEngine:
    """
    Backtesting engine for options strategies.
    """
    
    def __init__(
        self,
        symbol: str = 'SPX',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        data_manager: Optional[DataManager] = None
    ):
        self.symbol = symbol
        self.dm = data_manager or DataManager()
        
        # Default to last 60 days
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=90)
            start_date = start_dt.strftime('%Y-%m-%d')
        
        self.start_date = start_date
        self.end_date = end_date
        
        # Load data
        self.prices = self.dm.get_underlying_prices(symbol, start_date, end_date)
        self.vix = self.dm.get_vix_data(start_date, end_date)
        
        # Results storage
        self.trades: List[IronCondorPosition] = []
        self.daily_pnl: Dict[str, float] = {}
    
    def run_iron_condor_backtest(
        self,
        config: IronCondorConfig
    ) -> Dict:
        """
        Run iron condor backtest with given configuration.
        
        Returns:
            Dictionary with backtest results and statistics
        """
        strategy = IronCondorStrategy(config)
        sim_data = SimulatedOptionsData(self.dm)
        
        # Track open positions
        open_positions: List[IronCondorPosition] = []
        
        # Get trading days
        trading_days = list(self.prices.index)
        
        for i, current_date in enumerate(trading_days):
            date_str = current_date.strftime('%Y-%m-%d')
            day_of_week = current_date.strftime('%A')
            
            # Get market data for the day
            underlying_price = self.prices.loc[current_date, 'Close']
            
            # Get VIX (use nearest available date)
            try:
                vix_value = self.vix.loc[current_date, 'Close']
            except KeyError:
                # Find nearest VIX value
                vix_idx = self.vix.index.get_indexer([current_date], method='nearest')[0]
                vix_value = self.vix.iloc[vix_idx]['Close']
            
            # Check open positions for exit
            still_open = []
            for pos in open_positions:
                expiry_dt = datetime.strptime(pos.expiry_date, '%Y-%m-%d')
                current_dt = current_date.to_pydatetime().replace(tzinfo=None)
                days_remaining = max(0, (expiry_dt - current_dt).days)
                
                # Estimate current IV
                current_iv = self.dm.estimate_iv_from_vix(vix_value, days_remaining)
                
                should_exit, reason, pnl = strategy.check_exit(
                    pos, date_str, underlying_price, current_iv, days_remaining
                )
                
                if should_exit:
                    strategy.close_position(pos, date_str, pnl, reason)
                else:
                    still_open.append(pos)
            
            open_positions = still_open
            
            # Check if we should enter new position
            if strategy.should_enter(date_str, underlying_price, vix_value, day_of_week):
                # Calculate expiry date
                expiry_date = self.dm.get_expiry_date(date_str, config.dte)
                
                # Make sure we have data for expiry
                expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
                last_day = trading_days[-1].to_pydatetime().replace(tzinfo=None)
                if expiry_dt > last_day:
                    continue
                
                # Estimate IV for entry
                entry_iv = self.dm.estimate_iv_from_vix(vix_value, config.dte)
                
                # Create position
                pos = strategy.create_position(
                    date_str, expiry_date, self.symbol,
                    underlying_price, entry_iv, config.dte
                )
                open_positions.append(pos)
        
        # Close any remaining open positions at final day
        final_date = trading_days[-1].strftime('%Y-%m-%d')
        final_price = self.prices.iloc[-1]['Close']
        for pos in open_positions:
            from .utils.pricing import iron_condor_pnl_at_expiry
            pnl = iron_condor_pnl_at_expiry(
                final_price,
                pos.call_short_strike, pos.call_long_strike,
                pos.put_short_strike, pos.put_long_strike,
                pos.credit_received / (100 * pos.contracts)
            ) * 100 * pos.contracts
            strategy.close_position(pos, final_date, pnl, 'end_of_backtest')
        
        # Calculate results
        stats = strategy.get_statistics()
        
        return {
            'config': {
                'symbol': self.symbol,
                'start_date': self.start_date,
                'end_date': self.end_date,
                'delta': config.delta,
                'wing_width': config.wing_width,
                'dte': config.dte,
                'profit_target': config.profit_target_pct,
                'stop_loss': config.stop_loss_pct,
            },
            'statistics': stats,
            'trades': [
                {
                    'entry_date': t.entry_date,
                    'expiry_date': t.expiry_date,
                    'underlying_price': t.underlying_price,
                    'put_short': t.put_short_strike,
                    'call_short': t.call_short_strike,
                    'credit': t.credit_received,
                    'exit_date': t.exit_date,
                    'exit_reason': t.exit_reason,
                    'pnl': t.pnl,
                }
                for t in strategy.positions
            ]
        }


def run_parameter_sweep(
    symbol: str = 'SPX',
    start_date: str = None,
    end_date: str = None,
    deltas: List[float] = [0.10, 0.12, 0.15, 0.18, 0.20],
    wing_widths: List[int] = [15, 20, 25, 30],
    dtes: List[int] = [0, 1, 2, 3],
) -> pd.DataFrame:
    """
    Run parameter sweep across delta, wing width, and DTE combinations.
    """
    results = []
    
    total = len(deltas) * len(wing_widths) * len(dtes)
    count = 0
    
    for delta in deltas:
        for wing in wing_widths:
            for dte in dtes:
                count += 1
                print(f"Running {count}/{total}: delta={delta}, wing={wing}, dte={dte}")
                
                config = IronCondorConfig(
                    delta=delta,
                    wing_width=wing,
                    dte=dte,
                )
                
                try:
                    # Create fresh engine for each run to avoid state issues
                    engine = BacktestEngine(symbol, start_date, end_date)
                    result = engine.run_iron_condor_backtest(config)
                    stats = result['statistics']
                    
                    results.append({
                        'delta': delta,
                        'wing_width': wing,
                        'dte': dte,
                        'total_trades': stats.get('total_trades', 0),
                        'win_rate': stats.get('win_rate', 0),
                        'total_pnl': stats.get('total_pnl', 0),
                        'avg_pnl': stats.get('avg_pnl', 0),
                        'avg_win': stats.get('avg_win', 0),
                        'avg_loss': stats.get('avg_loss', 0),
                        'max_loss': stats.get('max_loss', 0),
                        'sharpe': stats.get('sharpe', 0),
                    })
                except Exception as e:
                    print(f"Error: {e}")
                    results.append({
                        'delta': delta,
                        'wing_width': wing,
                        'dte': dte,
                        'error': str(e),
                    })
    
    return pd.DataFrame(results)


def main():
    parser = argparse.ArgumentParser(description='Options Backtesting Engine')
    parser.add_argument('--symbol', type=str, default='SPX', help='Underlying symbol')
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--delta', type=float, default=0.15, help='Delta for short strikes')
    parser.add_argument('--wing', type=int, default=20, help='Wing width in points')
    parser.add_argument('--dte', type=int, default=2, help='Days to expiration')
    parser.add_argument('--profit-target', type=float, help='Profit target as fraction of credit')
    parser.add_argument('--stop-loss', type=float, help='Stop loss as multiple of credit')
    parser.add_argument('--sweep', action='store_true', help='Run parameter sweep')
    parser.add_argument('--output', type=str, help='Output file for results')
    
    args = parser.parse_args()
    
    if args.sweep:
        print(f"Running parameter sweep on {args.symbol}...")
        results = run_parameter_sweep(
            args.symbol,
            args.start,
            args.end,
        )
        print("\nResults:")
        print(results.to_string())
        
        if args.output:
            results.to_csv(args.output, index=False)
            print(f"\nSaved to {args.output}")
    else:
        print(f"Running backtest: {args.symbol}, delta={args.delta}, wing={args.wing}, dte={args.dte}")
        
        engine = BacktestEngine(args.symbol, args.start, args.end)
        config = IronCondorConfig(
            delta=args.delta,
            wing_width=args.wing,
            dte=args.dte,
            profit_target_pct=args.profit_target,
            stop_loss_pct=args.stop_loss,
        )
        
        results = engine.run_iron_condor_backtest(config)
        
        print("\n" + "="*60)
        print("BACKTEST RESULTS")
        print("="*60)
        print(f"\nConfiguration:")
        for k, v in results['config'].items():
            print(f"  {k}: {v}")
        
        print(f"\nStatistics:")
        for k, v in results['statistics'].items():
            if isinstance(v, float):
                print(f"  {k}: {v:.2f}")
            else:
                print(f"  {k}: {v}")
        
        print(f"\nSample Trades (first 5):")
        for trade in results['trades'][:5]:
            print(f"  {trade['entry_date']} -> {trade['exit_date']}: "
                  f"${trade['pnl']:.0f} ({trade['exit_reason']})")
        
        if args.output:
            import json
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\nFull results saved to {args.output}")


if __name__ == '__main__':
    main()
