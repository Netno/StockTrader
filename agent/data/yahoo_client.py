import asyncio
import logging
import os
import time
from typing import Optional
import httpx
import pandas as pd

logger = logging.getLogger(__name__)

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

    url = f"{FRONTEND_URL}/api/market/{ticker}?type=history&days={days}"

    # Retry with backoff for transient errors (rate-limit, timeout)
    last_err = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            break
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
            last_err = e
            if attempt < 2:
                wait = (attempt + 1) * 2  # 2s, 4s
                logger.debug(f"Yahoo retry {attempt+1}/2 for {ticker}: {e} — waiting {wait}s")
                await asyncio.sleep(wait)
    else:
        raise last_err  # type: ignore[misc]

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


async def get_index_history(days: int = 220) -> pd.DataFrame:
    """Fetch OMXS30 index history via Vercel proxy (cached)."""
    return await get_price_history("OMXS30", days)


async def get_earnings_date(ticker: str) -> Optional[str]:
    """Get next earnings date via Vercel proxy. Returns ISO date string or None. 24h cache."""
    cache_key = f"earnings:{ticker}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    url = f"{FRONTEND_URL}/api/market/{ticker}?type=earnings"
    date_str = None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
        data = resp.json()
        date_str = data.get("earnings_date")
    except Exception:
        pass

    _set_cache(cache_key, date_str, 86400)  # 24h
    return date_str


async def get_current_price(ticker: str) -> dict:
    """Get current price via Vercel proxy (cached)."""
    cache_key = f"price:{ticker}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    url = f"{FRONTEND_URL}/api/market/{ticker}?type=price"

    last_err = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            break
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
            last_err = e
            if attempt < 2:
                wait = (attempt + 1) * 2
                logger.debug(f"Yahoo retry {attempt+1}/2 for {ticker} price: {e}")
                await asyncio.sleep(wait)
    else:
        raise last_err  # type: ignore[misc]

    data = resp.json()
    raw_price = data.get("price")
    price = float(raw_price) if raw_price is not None and raw_price != 0 else None
    
    if price is None or price <= 0:
        # Returnera utan att cacha — Yahoo gav ogiltigt pris
        return {"price": None, "volume": data.get("volume"), "change_pct": data.get("change_pct")}

    result = {
        "price": price,
        "volume": data.get("volume"),
        "change_pct": data.get("change_pct"),
    }

    _set_cache(cache_key, result, _PRICE_TTL)
    return result
