"""
Runtime settings — loaded from stock_settings table in Supabase.
Falls back to env vars / hardcoded defaults if DB is unavailable.
Call load() on startup, then use get() anywhere.
"""
import logging
from config import MAX_POSITIONS as _MAX_POSITIONS, MAX_POSITION_SIZE as _MAX_POSITION_SIZE, SIGNAL_THRESHOLD as _SIGNAL_THRESHOLD

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "max_positions":    str(_MAX_POSITIONS),
    "max_position_size": str(_MAX_POSITION_SIZE),
    "signal_threshold": str(_SIGNAL_THRESHOLD),  # köptröskel
    "sell_threshold":   "55",                     # säljtröskel (lägre = lättare att sälja)
    "cash_buffer":      "2000",                   # likviditetsbuffert (SEK)
    "rotation_tau":     "1.5",                    # friktionströskel för rotation (%)
}

_cache: dict[str, str] = dict(_DEFAULTS)


def get(key: str, default: str = None) -> str:
    return _cache.get(key, default if default is not None else _DEFAULTS.get(key, ""))


def get_int(key: str) -> int:
    return int(get(key))


def get_float(key: str) -> float:
    return float(get(key))


def all_settings() -> dict:
    return dict(_cache)


async def load():
    """Load settings from Supabase. Call once at startup."""
    global _cache
    try:
        from db.supabase_client import get_client
        result = get_client().table("stock_settings").select("key,value").execute()
        if result.data:
            db_vals = {r["key"]: r["value"] for r in result.data}
            _cache = {**_DEFAULTS, **db_vals}
            logger.info(f"Settings laddade från DB: {_cache}")
        else:
            logger.info("stock_settings-tabellen är tom — använder standardvärden.")
    except Exception as e:
        logger.warning(f"Kunde inte ladda settings från DB: {e} — använder standardvärden.")


async def save(key: str, value: str):
    """Persist a setting to Supabase and update cache."""
    from datetime import datetime, timezone
    from db.supabase_client import get_client
    get_client().table("stock_settings").upsert({
        "key": key,
        "value": str(value),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    _cache[key] = str(value)
    logger.info(f"Setting sparad: {key} = {value}")
