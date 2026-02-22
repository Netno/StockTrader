from datetime import datetime, timezone
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, PAPER_BALANCE

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
):
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
        return PAPER_BALANCE


async def add_deposit(amount: float, note: str = "") -> str | None:
    result = get_client().table("stock_deposits").insert({
        "amount": amount,
        "note": note,
        "created_at": _now(),
    }).execute()
    return result.data[0]["id"] if result.data else None


async def get_portfolio_summary(initial_balance: float = PAPER_BALANCE) -> tuple[float, float]:
    """Return (current_value, pct_change) based on open confirmed trades."""
    try:
        deposited = await get_total_deposited()
    except Exception:
        deposited = initial_balance
    trades = await get_open_trades()
    invested = sum(t["total_value"] for t in trades)
    cash = max(0.0, deposited - invested)
    current_value = cash + invested
    pct = ((current_value - deposited) / deposited) * 100 if deposited else 0.0
    return round(current_value, 2), round(pct, 2)
