import time
import httpx
import pandas as pd
from config import TWELVE_DATA_API_KEY

BASE_URL = "https://api.twelvedata.com"

# Mapping from our ticker names to Twelve Data symbols (exchange: STO = Stockholm)
TWELVE_SYMBOLS = {
    "EVO":      "EVO:STO",
    "SINCH":    "SINCH:STO",
    "EMBRAC B": "EMBRAC-B:STO",
    "HTRO":     "HTRO:STO",
    "SSAB B":   "SSAB-B:STO",
}

# Simple in-memory cache: key -> (value, expires_at)
_cache: dict[str, tuple] = {}
_HISTORY_TTL = 300   # 5 minutes
_PRICE_TTL   = 60    # 1 minute


def _symbol(ticker: str) -> str:
    return TWELVE_SYMBOLS.get(ticker, ticker)


def _get_cache(key: str):
    entry = _cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    return None


def _set_cache(key: str, value, ttl: int):
    _cache[key] = (value, time.monotonic() + ttl)


async def get_price_history(ticker: str, days: int = 220) -> pd.DataFrame:
    """Fetch historical OHLCV data via Twelve Data (cached)."""
    cache_key = f"history:{ticker}:{days}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    symbol = _symbol(ticker)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/time_series",
            params={
                "symbol": symbol,
                "interval": "1day",
                "outputsize": days,
                "apikey": TWELVE_DATA_API_KEY,
            },
        )
    data = resp.json()

    if data.get("status") == "error" or "values" not in data:
        return pd.DataFrame()

    df = pd.DataFrame(data["values"])
    df["date"] = pd.to_datetime(df["datetime"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[["date", "open", "high", "low", "close", "volume"]].dropna()
    df = df.sort_values("date").reset_index(drop=True)

    _set_cache(cache_key, df, _HISTORY_TTL)
    return df


async def get_current_price(ticker: str) -> dict:
    """Get current price via Twelve Data (cached)."""
    cache_key = f"price:{ticker}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    symbol = _symbol(ticker)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/price",
            params={"symbol": symbol, "apikey": TWELVE_DATA_API_KEY},
        )
    data = resp.json()

    price = float(data.get("price", 0) or 0)
    result = {"price": price, "volume": None, "change_pct": None}

    _set_cache(cache_key, result, _PRICE_TTL)
    return result
