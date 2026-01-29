"""
Data fetching and management for options backtesting.

Data sources:
- yfinance: Free underlying prices and VIX
- ThetaData: Historical options chains (paid)
- OptionsDX: Historical options chains (paid)
"""
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import pandas as pd
import numpy as np

# Try importing yfinance, handle if not available
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False


class DataManager:
    """
    Manages data fetching and caching for backtesting.
    """
    
    def __init__(self, cache_dir: str = "data"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def get_underlying_prices(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Get underlying price data.
        
        Returns DataFrame with columns: Open, High, Low, Close, Volume
        """
        cache_file = os.path.join(
            self.cache_dir, 
            f"{symbol}_{start_date}_{end_date}_prices.csv"
        )
        
        if use_cache and os.path.exists(cache_file):
            df = pd.read_csv(cache_file, index_col=0)
            df.index = pd.to_datetime(df.index, utc=True)
            return df
        
        if not HAS_YFINANCE:
            raise ImportError("yfinance not installed. Run: pip install yfinance")
        
        # Map symbols
        yf_symbol = symbol
        if symbol == 'SPX':
            yf_symbol = '^GSPC'
        elif symbol == 'QQQ':
            yf_symbol = 'QQQ'
        
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(start=start_date, end=end_date)
        
        if use_cache and not df.empty:
            df.to_csv(cache_file)
        
        return df
    
    def get_vix_data(
        self,
        start_date: str,
        end_date: str,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """Get VIX data."""
        cache_file = os.path.join(
            self.cache_dir,
            f"VIX_{start_date}_{end_date}.csv"
        )
        
        if use_cache and os.path.exists(cache_file):
            df = pd.read_csv(cache_file, index_col=0)
            df.index = pd.to_datetime(df.index, utc=True)
            return df
        
        if not HAS_YFINANCE:
            raise ImportError("yfinance not installed")
        
        vix = yf.Ticker('^VIX')
        df = vix.history(start=start_date, end=end_date)
        
        if use_cache and not df.empty:
            df.to_csv(cache_file)
        
        return df
    
    def estimate_iv_from_vix(self, vix_close: float, dte: int) -> float:
        """
        Estimate IV for SPX options based on VIX.
        
        This is a rough approximation. VIX represents 30-day expected IV.
        We adjust based on DTE using a simple term structure model.
        """
        # VIX is annualized vol * 100
        annualized_vol = vix_close / 100
        
        # Simple term structure adjustment
        # Short-dated options typically have higher IV in volatile markets
        if dte <= 1:
            adjustment = 1.15  # 15% higher for 0-1 DTE
        elif dte <= 3:
            adjustment = 1.08  # 8% higher for 2-3 DTE
        elif dte <= 7:
            adjustment = 1.03
        else:
            adjustment = 1.0
        
        return annualized_vol * adjustment
    
    def get_trading_days(
        self,
        start_date: str,
        end_date: str,
        symbol: str = 'SPX'
    ) -> List[str]:
        """Get list of trading days in date range."""
        prices = self.get_underlying_prices(symbol, start_date, end_date)
        return [d.strftime('%Y-%m-%d') for d in prices.index]
    
    def get_expiry_date(self, trade_date: str, dte: int) -> str:
        """
        Calculate expiry date for a given trade date and DTE.
        Accounts for weekends (simplified - doesn't handle holidays).
        """
        trade_dt = datetime.strptime(trade_date, '%Y-%m-%d')
        
        # Add business days
        current = trade_dt
        days_added = 0
        while days_added < dte:
            current += timedelta(days=1)
            if current.weekday() < 5:  # Monday = 0, Friday = 4
                days_added += 1
        
        return current.strftime('%Y-%m-%d')


class SimulatedOptionsData:
    """
    Simulates options data when real options chain data isn't available.
    
    Uses Black-Scholes model with VIX-based IV estimates.
    Good for initial testing but real options data is needed for production backtests.
    """
    
    def __init__(self, data_manager: DataManager):
        self.dm = data_manager
    
    def get_option_chain(
        self,
        symbol: str,
        date: str,
        expiry_date: str,
        underlying_price: float,
        vix: float
    ) -> Dict:
        """
        Generate simulated option chain data.
        
        In production, this would fetch from ThetaData or OptionsDX.
        """
        dte = self._days_between(date, expiry_date)
        iv = self.dm.estimate_iv_from_vix(vix, dte)
        
        # Generate strikes around current price
        min_strike = int(underlying_price * 0.90)
        max_strike = int(underlying_price * 1.10)
        strike_step = 5 if symbol == 'SPX' else 1
        
        strikes = list(range(min_strike, max_strike + 1, strike_step))
        
        return {
            'date': date,
            'expiry': expiry_date,
            'underlying': underlying_price,
            'dte': dte,
            'iv': iv,
            'strikes': strikes,
        }
    
    def _days_between(self, date1: str, date2: str) -> int:
        """Calculate trading days between two dates."""
        d1 = datetime.strptime(date1, '%Y-%m-%d')
        d2 = datetime.strptime(date2, '%Y-%m-%d')
        
        # Simplified: count business days
        days = 0
        current = d1
        while current < d2:
            current += timedelta(days=1)
            if current.weekday() < 5:
                days += 1
        return days


def load_theta_data(file_path: str) -> pd.DataFrame:
    """
    Load historical options data from ThetaData export.
    
    Expected columns:
    - date, expiry, strike, call_bid, call_ask, put_bid, put_ask, 
      call_delta, put_delta, underlying_price, iv
    """
    return pd.read_csv(file_path, parse_dates=['date', 'expiry'])


def load_optionsdx_data(file_path: str) -> pd.DataFrame:
    """
    Load historical options data from OptionsDX export.
    
    Adjust column names as needed based on their format.
    """
    df = pd.read_csv(file_path)
    # Map columns to standard format
    # (adjust based on actual OptionsDX format)
    return df
