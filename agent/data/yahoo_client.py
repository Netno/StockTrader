import os
import time
import httpx
import pandas as pd

# Vercel frontend acts as Yahoo Finance proxy (Railway IPs are blocked by Yahoo)
FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")

# Simple in-memory cache: key -> (value, expires_at)
_cache: dict[str, tuple] = {}
_HISTORY_TTL = 300   # 5 minutes
_PRICE_TTL   = 60    # 1 minute


def _get_cache(key: str):
    entry = _cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    return None


def _set_cache(key: str, value, ttl: int):
    _cache[key] = (value, time.monotonic() + ttl)


async def get_price_history(ticker: str, days: int = 220) -> pd.DataFrame:
    """Fetch historical OHLCV data via Vercel proxy (cached)."""
    cache_key = f"history:{ticker}:{days}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    url = f"{FRONTEND_URL}/api/market/{ticker}?type=history"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)

    data = resp.json()
    if "error" in data or "data" not in data:
        return pd.DataFrame()

    rows = data["data"]
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[["date", "open", "high", "low", "close", "volume"]].dropna()
    df = df.sort_values("date").reset_index(drop=True)

    _set_cache(cache_key, df, _HISTORY_TTL)
    return df


async def get_current_price(ticker: str) -> dict:
    """Get current price via Vercel proxy (cached)."""
    cache_key = f"price:{ticker}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    url = f"{FRONTEND_URL}/api/market/{ticker}?type=price"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)

    data = resp.json()
    result = {
        "price": float(data.get("price") or 0),
        "volume": data.get("volume"),
        "change_pct": data.get("change_pct"),
    }

    _set_cache(cache_key, result, _PRICE_TTL)
    return result
