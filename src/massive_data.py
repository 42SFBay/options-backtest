#!/usr/bin/env python3
"""
Massive.com data fetcher for options backtesting.
Replaces ThetaData with free Massive API.
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm
from scipy.optimize import brentq
import json
import os

API_KEY = "Td9cMGlx_c1vqpBuvxT_qVUu3P3730cc"
BASE_URL = "https://api.massive.com"

HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# Cache directory
CACHE_DIR = "/home/ubuntu/clawd/projects/options-backtest/cache/massive"
os.makedirs(CACHE_DIR, exist_ok=True)


def get_spy_price(date: str) -> float:
    """Get SPY close price for a date, multiply by 10 for SPX proxy."""
    cache_file = f"{CACHE_DIR}/spy_{date[:7]}.json"
    
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            data = json.load(f)
        if date in data:
            return data[date] * 10  # SPY -> SPX approximation
    
    # Fetch month of data
    start = date[:8] + "01"
    end_dt = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=31)
    end = end_dt.strftime("%Y-%m-%d")
    
    url = f"{BASE_URL}/v2/aggs/ticker/SPY/range/1/day/{start}/{end}"
    resp = requests.get(url, headers=HEADERS)
    results = resp.json().get("results", [])
    
    data = {}
    for r in results:
        dt = datetime.fromtimestamp(r["t"] / 1000).strftime("%Y-%m-%d")
        data[dt] = r["c"]  # close price
    
    # Save cache
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            existing = json.load(f)
        existing.update(data)
        data = existing
    
    with open(cache_file, "w") as f:
        json.dump(data, f)
    
    return data.get(date, 0) * 10


def get_vix_proxy(date: str) -> float:
    """
    Estimate VIX from UVXY price movements.
    This is approximate - UVXY tracks VIX futures, not spot VIX.
    Use a rough conversion: VIX ≈ 15 + (UVXY_return * 50)
    """
    # For now, return a default. We'll refine this.
    # TODO: Build better VIX proxy or find free VIX data
    return 16.0  # Default assumption


def black_scholes_price(S, K, T, r, sigma, option_type="put"):
    """Calculate Black-Scholes option price."""
    if T <= 0:
        if option_type == "put":
            return max(K - S, 0)
        else:
            return max(S - K, 0)
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == "put":
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    else:
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def implied_volatility(price, S, K, T, r, option_type="put"):
    """Back-calculate IV from option price using Black-Scholes."""
    if T <= 0 or price <= 0:
        return 0.20  # default
    
    def objective(sigma):
        return black_scholes_price(S, K, T, r, sigma, option_type) - price
    
    try:
        iv = brentq(objective, 0.01, 3.0)
        return iv
    except:
        return 0.20  # default if can't solve


def calculate_delta(S, K, T, r, sigma, option_type="put"):
    """Calculate option delta."""
    if T <= 0:
        if option_type == "put":
            return -1.0 if K > S else 0.0
        else:
            return 1.0 if S > K else 0.0
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    
    if option_type == "put":
        return norm.cdf(d1) - 1
    else:
        return norm.cdf(d1)


def get_options_chain(underlying: str, date: str, expiration: str, option_type: str = "put"):
    """
    Get options chain for a given underlying, date, and expiration.
    Returns DataFrame with strike, price, delta, IV.
    """
    cache_file = f"{CACHE_DIR}/chain_{underlying}_{expiration}_{option_type}.json"
    
    # Get underlying price
    S = get_spy_price(date)
    if S == 0:
        return pd.DataFrame()
    
    # Calculate time to expiration
    exp_dt = datetime.strptime(expiration, "%Y-%m-%d")
    date_dt = datetime.strptime(date, "%Y-%m-%d")
    T = max((exp_dt - date_dt).days / 365.0, 0.001)
    
    r = 0.05  # Risk-free rate assumption
    
    # Get contracts for this expiration
    contract_type = "put" if option_type == "put" else "call"
    
    # Calculate strike range based on typical delta range we care about
    # For puts: 0.05-0.25 delta means roughly 92-98% of spot
    min_strike = int(S * 0.88)
    max_strike = int(S * 1.02)
    
    url = f"{BASE_URL}/v3/reference/options/contracts"
    params = {
        "underlying_ticker": underlying,
        "expiration_date": expiration,
        "contract_type": contract_type,
        "strike_price.gte": min_strike,
        "strike_price.lte": max_strike,
        "limit": 250
    }
    
    resp = requests.get(url, headers=HEADERS, params=params)
    contracts = resp.json().get("results", [])
    
    if not contracts:
        return pd.DataFrame()
    
    # Get prices for each contract
    chain_data = []
    for contract in contracts:
        ticker = contract["ticker"]
        strike = contract["strike_price"]
        
        # Skip strikes too far from current price (wider range for OTM options)
        if strike < S * 0.80 or strike > S * 1.10:
            continue
        
        # Get historical price for this contract on this date
        url = f"{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{date}/{date}"
        resp = requests.get(url, headers=HEADERS)
        results = resp.json().get("results", [])
        
        if results:
            price = results[0]["c"]  # close price
            
            # Calculate IV and delta
            iv = implied_volatility(price, S, strike, T, r, option_type)
            delta = calculate_delta(S, strike, T, r, iv, option_type)
            
            chain_data.append({
                "ticker": ticker,
                "strike": strike,
                "price": price,
                "iv": iv,
                "delta": delta,
                "underlying_price": S
            })
    
    return pd.DataFrame(chain_data)


def find_strike_by_delta(chain: pd.DataFrame, target_delta: float) -> dict:
    """Find the strike closest to target delta."""
    if chain.empty:
        return None
    
    chain = chain.copy()
    chain["delta_diff"] = abs(chain["delta"] - (-target_delta))  # Put delta is negative
    closest = chain.loc[chain["delta_diff"].idxmin()]
    
    return {
        "strike": closest["strike"],
        "price": closest["price"],
        "delta": closest["delta"],
        "iv": closest["iv"],
        "ticker": closest["ticker"]
    }


def get_option_price_at_expiry(ticker: str, expiration: str) -> float:
    """Get option price at expiration (should be intrinsic value or 0)."""
    url = f"{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{expiration}/{expiration}"
    resp = requests.get(url, headers=HEADERS)
    results = resp.json().get("results", [])
    
    if results:
        return results[0]["c"]
    return 0.0


def get_available_expirations(underlying: str, start_date: str, end_date: str) -> list:
    """Get available expiration dates for an underlying."""
    url = f"{BASE_URL}/v3/reference/options/contracts"
    params = {
        "underlying_ticker": underlying,
        "expiration_date.gte": start_date,
        "expiration_date.lte": end_date,
        "limit": 250
    }
    
    resp = requests.get(url, headers=HEADERS, params=params)
    contracts = resp.json().get("results", [])
    
    expirations = sorted(set(c["expiration_date"] for c in contracts))
    return expirations


if __name__ == "__main__":
    # Test the data fetcher
    print("Testing Massive data fetcher...")
    
    # Test SPY/SPX price
    date = "2026-01-27"
    spx = get_spy_price(date)
    print(f"SPX proxy for {date}: {spx:.2f}")
    
    # Get available expirations
    print(f"\nAvailable expirations near {date}:")
    exps = get_available_expirations("SPX", "2026-01-28", "2026-02-05")
    for exp in exps[:5]:
        print(f"  {exp}")
    
    # Test options chain with actual expiration
    if exps:
        exp = exps[0]
        print(f"\nFetching options chain for SPX, expiring {exp}...")
        chain = get_options_chain("SPX", date, exp, "put")
        print(f"Found {len(chain)} contracts")
        if not chain.empty:
            print(chain.head(10))
            
            # Find 0.14 delta strike
            strike = find_strike_by_delta(chain, 0.14)
            if strike:
                print(f"\n0.14 delta strike: {strike}")
