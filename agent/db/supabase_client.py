import logging
from datetime import datetime, timezone
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, PAPER_BALANCE

logger = logging.getLogger(__name__)

_client: Client = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def save_price(ticker: str, price: float, volume: int):
    get_client().table("stock_prices").insert({
        "ticker": ticker,
        "price": price,
        "volume": volume,
        "timestamp": _now(),
    }).execute()


async def save_indicators(ticker: str, indicators: dict):
    INDICATOR_FIELDS = {
        "rsi", "macd", "macd_signal", "macd_histogram",
        "ma20", "ma50", "ma200", "ema20",
        "bollinger_upper", "bollinger_lower", "atr", "volume_ratio",
        "buy_score",
    }
    get_client().table("stock_indicators").insert({
        "ticker": ticker,
        **{k: v for k, v in indicators.items() if k in INDICATOR_FIELDS},
        "timestamp": _now(),
    }).execute()


async def save_signal(
    ticker: str,
    signal_type: str,
    price: float,
    quantity: int,
    confidence: float,
    score: int,
    reasons: list,
    indicators: dict,
    stop_loss: float,
    take_profit: float,
) -> str | None:
    result = get_client().table("stock_signals").insert({
        "ticker": ticker,
        "signal_type": signal_type,
        "price": price,
        "quantity": quantity,
        "confidence": confidence,
        "score": score,
        "reasons": reasons,
        "indicators": indicators,
        "stop_loss_price": stop_loss,
        "take_profit_price": take_profit,
        "paper_mode": True,
        "executed": False,
        "status": "pending" if signal_type == "BUY" else "auto",
        "created_at": _now(),
    }).execute()
    return result.data[0]["id"] if result.data else None


async def confirm_signal(signal_id: str):
    get_client().table("stock_signals").update({
        "status": "confirmed",
        "executed": True,
        "confirmed_at": _now(),
    }).eq("id", signal_id).execute()


async def reject_signal(signal_id: str):
    get_client().table("stock_signals").update({
        "status": "rejected",
    }).eq("id", signal_id).execute()


async def save_trade(
    ticker: str,
    signal_id: str,
    entry_price: float,
    quantity: int,
    stop_loss: float,
    take_profit: float,
) -> str | None:
    result = get_client().table("stock_trades").insert({
        "ticker": ticker,
        "signal_id": signal_id,
        "entry_price": entry_price,
        "quantity": quantity,
        "stop_loss_price": stop_loss,
        "take_profit_price": take_profit,
        "total_value": round(entry_price * quantity, 2),
        "status": "open",
        "paper_mode": True,
        "opened_at": _now(),
        "created_at": _now(),
    }).execute()
    return result.data[0]["id"] if result.data else None


async def close_trade(
    trade_id: str,
    exit_price: float,
    close_reason: str,
    pnl_kr: float,
    pnl_pct: float,
):
    get_client().table("stock_trades").update({
        "status": "closed",
        "exit_price": exit_price,
        "close_reason": close_reason,
        "pnl_kr": round(pnl_kr, 2),
        "pnl_pct": round(pnl_pct, 2),
        "closed_at": _now(),
    }).eq("id", trade_id).execute()


async def get_open_trades() -> list:
    result = (
        get_client()
        .table("stock_trades")
        .select("*")
        .eq("status", "open")
        .execute()
    )
    return result.data or []


async def get_trade_history() -> list:
    result = (
        get_client()
        .table("stock_trades")
        .select("*")
        .eq("status", "closed")
        .order("closed_at", desc=True)
        .execute()
    )
    return result.data or []


async def get_pending_buy_signals() -> list:
    result = (
        get_client()
        .table("stock_signals")
        .select("*")
        .eq("signal_type", "BUY")
        .eq("status", "pending")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


async def save_news(
    ticker: str,
    headline: str,
    url: str,
    sentiment: str,
    sentiment_score: float,
    reason: str,
    source: str,
    published_at,
) -> bool:
    """Spara en nyhet till databasen. Returnerar False om den redan finns (dedup)."""
    # Dedup-kontroll direkt i DB — förhindrar dubletter oavsett cache-status
    try:
        existing = get_client().table("stock_news").select("id").eq("ticker", ticker).eq("headline", headline).limit(1).execute()
        if existing.data:
            return False
    except Exception:
        pass  # vid DB-läsfel, försök ändå (hellre dubblett än att missa nyheten)

    get_client().table("stock_news").insert({
        "ticker": ticker,
        "headline": headline,
        "url": url,
        "sentiment": sentiment,
        "sentiment_score": sentiment_score,
        "gemini_reason": reason,
        "source": source,
        "published_at": published_at.isoformat() if published_at else None,
        "created_at": _now(),
    }).execute()
    return True


async def get_open_positions() -> list:
    """Legacy: return open BUY entries from stock_portfolio."""
    result = (
        get_client()
        .table("stock_portfolio")
        .select("*")
        .eq("action", "BUY")
        .eq("paper_mode", True)
        .execute()
    )
    return result.data or []


async def get_watchlist() -> list:
    result = (
        get_client()
        .table("stock_watchlist")
        .select("*")
        .eq("active", True)
        .execute()
    )
    return result.data or []


async def bulk_update_watchlist(keep_tickers: set[str], new_entries: list[dict]):
    """
    Replace watchlist: keep positioned stocks, deactivate others, add new candidates.

    keep_tickers: tickers with open positions (never deactivated)
    new_entries: list of dicts with keys: ticker, name, strategy, stop_loss_pct,
                 take_profit_pct, atr_multiplier, avanza_url
    """
    client = get_client()
    # Get current active watchlist
    current = client.table("stock_watchlist").select("ticker").eq("active", True).execute()
    current_tickers = {r["ticker"] for r in (current.data or [])}

    new_tickers = {e["ticker"] for e in new_entries}

    # Deactivate stocks that are NOT in keep_tickers AND NOT in new_entries
    to_deactivate = current_tickers - keep_tickers - new_tickers
    for ticker in to_deactivate:
        client.table("stock_watchlist").update({
            "active": False,
        }).eq("ticker", ticker).execute()
        logger.info(f"[Discovery] Avaktiverade {ticker} från watchlist")

    # Add new entries (only those not already active)
    for entry in new_entries:
        if entry["ticker"] in current_tickers:
            # Already active — keep it
            continue
        # Check if ticker exists but is inactive — reactivate
        existing = client.table("stock_watchlist").select("id").eq("ticker", entry["ticker"]).limit(1).execute()
        if existing.data:
            client.table("stock_watchlist").update({
                "active": True,
                "strategy": entry.get("strategy", "trend_following"),
                "stop_loss_pct": entry.get("stop_loss_pct", 0.05),
                "take_profit_pct": entry.get("take_profit_pct", 0.10),
                "atr_multiplier": entry.get("atr_multiplier", 1.3),
            }).eq("ticker", entry["ticker"]).execute()
            logger.info(f"[Discovery] Återaktiverade {entry['ticker']} i watchlist")
        else:
            client.table("stock_watchlist").insert({
                "ticker": entry["ticker"],
                "name": entry.get("name", entry["ticker"]),
                "strategy": entry.get("strategy", "trend_following"),
                "stop_loss_pct": entry.get("stop_loss_pct", 0.05),
                "take_profit_pct": entry.get("take_profit_pct", 0.10),
                "atr_multiplier": entry.get("atr_multiplier", 1.3),
                "avanza_url": entry.get("avanza_url"),
                "active": True,
                "created_at": _now(),
            }).execute()
            logger.info(f"[Discovery] Lade till {entry['ticker']} i watchlist")

    final = client.table("stock_watchlist").select("ticker").eq("active", True).execute()
    logger.info(f"[Discovery] Watchlist nu: {len(final.data or [])} aktier aktiva")


async def set_cooldown(ticker: str, until: datetime):
    get_client().table("stock_watchlist").update({
        "cooldown_until": until.isoformat(),
    }).eq("ticker", ticker).execute()


async def get_total_deposited() -> float:
    """Sum of all deposits — this is the user's total capital basis."""
    try:
        result = get_client().table("stock_deposits").select("amount").execute()
        return sum(r["amount"] for r in (result.data or []))
    except Exception:
        return 0.0


async def add_deposit(amount: float, note: str = "") -> str | None:
    result = get_client().table("stock_deposits").insert({
        "amount": amount,
        "note": note,
        "created_at": _now(),
    }).execute()
    return result.data[0]["id"] if result.data else None


async def get_portfolio_summary(initial_balance: float = PAPER_BALANCE) -> tuple[float, float]:
    """Return (current_value, pct_change) based on open confirmed trades with live prices."""
    try:
        deposited = await get_total_deposited()
    except Exception:
        deposited = initial_balance
    trades = await get_open_trades()
    invested_at_cost = sum(t["total_value"] for t in trades)

    # Use live prices for market value when possible
    market_value = 0.0
    for t in trades:
        try:
            from data.yahoo_client import get_current_price
            current = await get_current_price(t["ticker"])
            live_price = current.get("price") or t["entry_price"]
        except Exception:
            live_price = t["entry_price"]
        market_value += live_price * t["quantity"]

    # Realized P&L from closed trades
    try:
        closed = get_client().table("stock_trades").select("pnl_kr").eq("status", "closed").execute()
        realized_pnl = sum(r["pnl_kr"] or 0 for r in (closed.data or []))
    except Exception:
        realized_pnl = 0.0

    cash = max(0.0, deposited + realized_pnl - invested_at_cost)
    current_value = cash + market_value
    pct = ((current_value - deposited) / deposited) * 100 if deposited else 0.0
    return round(current_value, 2), round(pct, 2)


def upsert_ai_stats(stats: dict):
    """Upsert this hour's AI stats to DB (stock_ai_stats table)."""
    row = {
        "date": stats["date"],
        "hour": stats.get("hour", 0),
        "model": stats.get("model", ""),
        "calls_ok": stats.get("calls_ok", 0),
        "calls_failed": stats.get("calls_failed", 0),
        "calls_rate_limited": stats.get("calls_rate_limited", 0),
        "cache_hits": stats.get("cache_hits", 0),
        "input_tokens": stats.get("input_tokens", 0),
        "output_tokens": stats.get("output_tokens", 0),
        "total_latency_s": stats.get("total_latency_s", 0.0),
        "by_type": stats.get("by_type", {}),
        "updated_at": _now(),
    }
    try:
        result = get_client().table("stock_ai_stats").upsert(
            row, on_conflict="date,hour"
        ).execute()
        logger.info(f"[AI Stats DB] Upsert OK för {stats['date']} H{stats.get('hour', 0)}: "
                     f"{stats.get('calls_ok', 0)} anrop, {len(result.data or [])} rader")
    except Exception as e:
        logger.error(f"[AI Stats DB] Upsert MISSLYCKADES för {stats['date']} H{stats.get('hour', 0)}: "
                     f"{type(e).__name__}: {e}")
        raise


def load_ai_stats_for_date_hour(date_str: str, hour: int) -> dict | None:
    """Load AI stats for a specific date+hour from DB."""
    result = (
        get_client()
        .table("stock_ai_stats")
        .select("*")
        .eq("date", date_str)
        .eq("hour", hour)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_ai_stats_history(days: int = 30) -> list:
    """Get AI stats history (all hourly rows) ordered by date+hour desc."""
    result = (
        get_client()
        .table("stock_ai_stats")
        .select("*")
        .order("date", desc=True)
        .order("hour", desc=True)
        .limit(days * 24)
        .execute()
    )
    return result.data or []
