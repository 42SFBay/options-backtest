"""
Iron Condor Strategy Implementation.

Dili's baseline strategy:
- 2 DTE (or 0 DTE)
- Delta: 0.15 on both legs
- Wing span: 20-30 points
- Entry time: 10:15 AM ET (7:15 AM PDT)
"""
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np

from ..utils.pricing import (
    find_strike_by_delta,
    calculate_iron_condor_credit,
    iron_condor_pnl_at_expiry,
)


@dataclass
class IronCondorPosition:
    """Represents an iron condor position."""
    entry_date: str
    expiry_date: str
    underlying_symbol: str
    underlying_price: float
    
    # Strikes
    put_long_strike: float
    put_short_strike: float
    call_short_strike: float
    call_long_strike: float
    
    # Greeks at entry
    entry_delta_call: float
    entry_delta_put: float
    entry_iv: float
    
    # Economics
    credit_received: float
    max_loss: float
    contracts: int = 1
    
    # Exit info (filled when closed)
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # 'expiry', 'profit_target', 'stop_loss', 'manual'
    pnl: Optional[float] = None


@dataclass
class IronCondorConfig:
    """Configuration for iron condor strategy."""
    # Core parameters
    delta: float = 0.15
    wing_width: int = 20  # Points for SPX
    dte: int = 2
    
    # Entry rules
    entry_time: str = "10:15"  # ET
    
    # Exit rules
    profit_target_pct: Optional[float] = None  # e.g., 0.50 for 50% of credit
    stop_loss_pct: Optional[float] = None  # e.g., 2.0 for 2x credit
    
    # Filters
    min_vix: Optional[float] = None
    max_vix: Optional[float] = None
    skip_days: list = None  # e.g., ['Monday', 'Friday']
    
    # Position sizing
    max_risk_per_trade: float = 3000  # Max loss per trade
    contracts: int = 1


class IronCondorStrategy:
    """
    Iron condor strategy for SPX/QQQ.
    
    Sells an OTM call spread and OTM put spread simultaneously.
    Profits when the underlying stays within the short strikes.
    """
    
    def __init__(self, config: IronCondorConfig = None):
        self.config = config or IronCondorConfig()
        self.positions: list[IronCondorPosition] = []
        
    def should_enter(
        self,
        date: str,
        underlying_price: float,
        vix: float,
        day_of_week: str
    ) -> bool:
        """
        Check if we should enter a new position.
        """
        config = self.config
        
        # VIX filter
        if config.min_vix and vix < config.min_vix:
            return False
        if config.max_vix and vix > config.max_vix:
            return False
        
        # Day of week filter
        if config.skip_days and day_of_week in config.skip_days:
            return False
        
        return True
    
    def calculate_strikes(
        self,
        underlying_price: float,
        iv: float,
        dte: int,
        risk_free_rate: float = 0.05
    ) -> Tuple[float, float, float, float]:
        """
        Calculate strike prices for the iron condor.
        
        Returns:
            Tuple of (put_long, put_short, call_short, call_long)
        """
        T = dte / 365.0
        delta = self.config.delta
        wing = self.config.wing_width
        
        # Find short strikes at target delta
        call_short = find_strike_by_delta(
            underlying_price, T, risk_free_rate, iv,
            target_delta=delta, option_type='call', precision=5.0
        )
        put_short = find_strike_by_delta(
            underlying_price, T, risk_free_rate, iv,
            target_delta=-delta, option_type='put', precision=5.0
        )
        
        # Long strikes are wing_width away
        call_long = call_short + wing
        put_long = put_short - wing
        
        return put_long, put_short, call_short, call_long
    
    def create_position(
        self,
        date: str,
        expiry_date: str,
        symbol: str,
        underlying_price: float,
        iv: float,
        dte: int,
        risk_free_rate: float = 0.05
    ) -> IronCondorPosition:
        """
        Create a new iron condor position.
        """
        T = dte / 365.0
        
        # Calculate strikes
        put_long, put_short, call_short, call_long = self.calculate_strikes(
            underlying_price, iv, dte, risk_free_rate
        )
        
        # Calculate credit and risk
        credit, _, _, max_loss, _, _ = calculate_iron_condor_credit(
            underlying_price,
            call_short, call_long,
            put_short, put_long,
            T, risk_free_rate, iv
        )
        
        # Adjust contracts based on max risk
        contracts = self.config.contracts
        if max_loss > 0:
            max_contracts = int(self.config.max_risk_per_trade / (max_loss * 100))
            contracts = min(contracts, max(1, max_contracts))
        
        position = IronCondorPosition(
            entry_date=date,
            expiry_date=expiry_date,
            underlying_symbol=symbol,
            underlying_price=underlying_price,
            put_long_strike=put_long,
            put_short_strike=put_short,
            call_short_strike=call_short,
            call_long_strike=call_long,
            entry_delta_call=self.config.delta,
            entry_delta_put=-self.config.delta,
            entry_iv=iv,
            credit_received=credit * 100 * contracts,  # Per contract * 100 shares
            max_loss=max_loss * 100 * contracts,
            contracts=contracts,
        )
        
        self.positions.append(position)
        return position
    
    def check_exit(
        self,
        position: IronCondorPosition,
        current_date: str,
        underlying_price: float,
        current_iv: float,
        days_remaining: int,
        risk_free_rate: float = 0.05
    ) -> Tuple[bool, str, float]:
        """
        Check if position should be exited.
        
        Returns:
            Tuple of (should_exit, reason, current_value)
        """
        T = days_remaining / 365.0
        
        # Calculate current position value
        if T <= 0:
            # At expiry
            pnl_per_contract = iron_condor_pnl_at_expiry(
                underlying_price,
                position.call_short_strike, position.call_long_strike,
                position.put_short_strike, position.put_long_strike,
                position.credit_received / (100 * position.contracts)
            )
            return True, 'expiry', pnl_per_contract * 100 * position.contracts
        
        # Current theoretical value
        current_credit, _, _, _, _, _ = calculate_iron_condor_credit(
            underlying_price,
            position.call_short_strike, position.call_long_strike,
            position.put_short_strike, position.put_long_strike,
            T, risk_free_rate, current_iv
        )
        current_value = current_credit * 100 * position.contracts
        pnl = position.credit_received - current_value
        
        # Profit target
        if self.config.profit_target_pct:
            target_pnl = position.credit_received * self.config.profit_target_pct
            if pnl >= target_pnl:
                return True, 'profit_target', pnl
        
        # Stop loss
        if self.config.stop_loss_pct:
            max_loss = position.credit_received * self.config.stop_loss_pct
            if pnl <= -max_loss:
                return True, 'stop_loss', pnl
        
        return False, None, pnl
    
    def close_position(
        self,
        position: IronCondorPosition,
        exit_date: str,
        pnl: float,
        reason: str
    ):
        """Close a position and record the result."""
        position.exit_date = exit_date
        position.pnl = pnl
        position.exit_reason = reason
    
    def get_statistics(self) -> dict:
        """Calculate strategy statistics from closed positions."""
        closed = [p for p in self.positions if p.pnl is not None]
        
        if not closed:
            return {}
        
        pnls = [p.pnl for p in closed]
        wins = [p for p in closed if p.pnl > 0]
        losses = [p for p in closed if p.pnl <= 0]
        
        return {
            'total_trades': len(closed),
            'total_pnl': sum(pnls),
            'win_rate': len(wins) / len(closed) if closed else 0,
            'avg_win': np.mean([p.pnl for p in wins]) if wins else 0,
            'avg_loss': np.mean([p.pnl for p in losses]) if losses else 0,
            'max_win': max(pnls) if pnls else 0,
            'max_loss': min(pnls) if pnls else 0,
            'avg_pnl': np.mean(pnls) if pnls else 0,
            'sharpe': np.mean(pnls) / np.std(pnls) if np.std(pnls) > 0 else 0,
            'expectancy': np.mean(pnls) if pnls else 0,
            'by_exit_reason': {
                reason: len([p for p in closed if p.exit_reason == reason])
                for reason in set(p.exit_reason for p in closed)
            }
        }
