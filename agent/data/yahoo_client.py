import asyncio
import time
import yfinance as yf
import pandas as pd

# Mapping from our ticker names to Yahoo Finance symbols
YAHOO_SYMBOLS = {
    "EVO":      "EVO.ST",
    "SINCH":    "SINCH.ST",
    "EMBRAC B": "EMBRAC-B.ST",
    "HTRO":     "HTRO.ST",
    "SSAB B":   "SSAB-B.ST",
}

# Simple in-memory cache: key -> (value, expires_at)
_cache: dict[str, tuple] = {}
_HISTORY_TTL = 300   # 5 minutes — history data doesn't change tick-by-tick
_PRICE_TTL   = 60    # 1 minute — current price is more time-sensitive


def _symbol(ticker: str) -> str:
    return YAHOO_SYMBOLS.get(ticker, ticker)


def _get_cache(key: str):
    entry = _cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    return None


def _set_cache(key: str, value, ttl: int):
    _cache[key] = (value, time.monotonic() + ttl)


def _fetch_history(symbol: str, period: str) -> pd.DataFrame:
    """Blocking yfinance call — run via asyncio.to_thread."""
    df = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        return pd.DataFrame()
    df = df.reset_index()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]
    return df[["date", "open", "high", "low", "close", "volume"]].dropna()


def _fetch_current_price(symbol: str) -> dict:
    """Blocking yfinance call — run via asyncio.to_thread."""
    info = yf.Ticker(symbol).fast_info
    return {
        "price": info.last_price,
        "volume": info.three_month_average_volume,
        "change_pct": None,
    }


async def get_price_history(ticker: str, days: int = 220) -> pd.DataFrame:
    """Fetch historical OHLCV data via Yahoo Finance (cached, non-blocking)."""
    cache_key = f"history:{ticker}:{days}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    symbol = _symbol(ticker)
    period = "1y" if days <= 365 else "2y"
    df = await asyncio.to_thread(_fetch_history, symbol, period)
    _set_cache(cache_key, df, _HISTORY_TTL)
    return df


async def get_current_price(ticker: str) -> dict:
    """Get current price and volume via Yahoo Finance (cached, non-blocking)."""
    cache_key = f"price:{ticker}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    symbol = _symbol(ticker)
    result = await asyncio.to_thread(_fetch_current_price, symbol)
    _set_cache(cache_key, result, _PRICE_TTL)
    return result
