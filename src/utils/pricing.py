"""
Options pricing utilities using Black-Scholes model.
"""
import numpy as np
from scipy.stats import norm
from typing import Tuple


def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Calculate Black-Scholes call option price.
    
    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate
        sigma: Volatility (annualized)
    
    Returns:
        Call option price
    """
    if T <= 0:
        return max(0, S - K)
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def black_scholes_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Calculate Black-Scholes put option price.
    """
    if T <= 0:
        return max(0, K - S)
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def delta_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Calculate delta for a call option."""
    if T <= 0:
        return 1.0 if S > K else 0.0
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return norm.cdf(d1)


def delta_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Calculate delta for a put option."""
    if T <= 0:
        return -1.0 if S < K else 0.0
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return norm.cdf(d1) - 1


def find_strike_by_delta(
    S: float, 
    T: float, 
    r: float, 
    sigma: float, 
    target_delta: float,
    option_type: str = 'call',
    precision: float = 0.5
) -> float:
    """
    Find the strike price that gives a target delta.
    
    Args:
        S: Current stock price
        T: Time to expiration (in years)
        r: Risk-free interest rate
        sigma: Volatility
        target_delta: Desired delta (positive for calls, negative for puts)
        option_type: 'call' or 'put'
        precision: Strike price precision (default 0.5 for SPX)
    
    Returns:
        Strike price
    """
    # Binary search for strike
    if option_type == 'call':
        low_K, high_K = S * 0.8, S * 1.2
        delta_func = delta_call
    else:
        low_K, high_K = S * 0.8, S * 1.2
        delta_func = lambda s, k, t, r, sig: -delta_put(s, k, t, r, sig)
        target_delta = abs(target_delta)
    
    while high_K - low_K > precision:
        mid_K = (low_K + high_K) / 2
        mid_delta = delta_func(S, mid_K, T, r, sigma)
        
        if mid_delta > target_delta:
            low_K = mid_K
        else:
            high_K = mid_K
    
    # Round to precision
    return round((low_K + high_K) / 2 / precision) * precision


def calculate_iron_condor_credit(
    S: float,
    call_short_K: float,
    call_long_K: float,
    put_short_K: float,
    put_long_K: float,
    T: float,
    r: float,
    sigma: float
) -> Tuple[float, float, float, float, float]:
    """
    Calculate iron condor premium and max risk.
    
    Returns:
        Tuple of (total_credit, call_spread_credit, put_spread_credit, max_loss, breakeven_low, breakeven_high)
    """
    # Call spread (sell lower strike, buy higher strike)
    short_call = black_scholes_call(S, call_short_K, T, r, sigma)
    long_call = black_scholes_call(S, call_long_K, T, r, sigma)
    call_credit = short_call - long_call
    
    # Put spread (sell higher strike, buy lower strike)
    short_put = black_scholes_put(S, put_short_K, T, r, sigma)
    long_put = black_scholes_put(S, put_long_K, T, r, sigma)
    put_credit = short_put - long_put
    
    total_credit = call_credit + put_credit
    
    # Max loss is width of spread minus credit
    call_width = call_long_K - call_short_K
    put_width = put_short_K - put_long_K
    max_loss = max(call_width, put_width) - total_credit
    
    # Breakevens
    breakeven_low = put_short_K - total_credit
    breakeven_high = call_short_K + total_credit
    
    return total_credit, call_credit, put_credit, max_loss, breakeven_low, breakeven_high


def iron_condor_pnl_at_expiry(
    S_final: float,
    call_short_K: float,
    call_long_K: float,
    put_short_K: float,
    put_long_K: float,
    credit_received: float
) -> float:
    """
    Calculate iron condor P&L at expiration.
    
    Args:
        S_final: Underlying price at expiration
        call_short_K, call_long_K: Call spread strikes
        put_short_K, put_long_K: Put spread strikes
        credit_received: Initial credit received
    
    Returns:
        P&L (positive = profit)
    """
    # Call spread value at expiry (short - long)
    call_spread_value = max(0, S_final - call_short_K) - max(0, S_final - call_long_K)
    
    # Put spread value at expiry (short - long)
    put_spread_value = max(0, put_short_K - S_final) - max(0, put_long_K - S_final)
    
    # Total cost to close
    cost_to_close = call_spread_value + put_spread_value
    
    # P&L = credit received - cost to close
    return credit_received - cost_to_close
