import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scheduler import setup_scheduler, load_open_positions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Startar AKTIEMOTOR...")
    import settings
    await settings.load()
    sched = setup_scheduler()
    sched.start()
    await load_open_positions()
    logger.info("Scheduler igng.")
    yield
    sched.shutdown()
    logger.info("Scheduler stoppad.")


app = FastAPI(title="Aktiemotor API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "aktiemotor"}


_summary_cache: dict = {}
_SUMMARY_TTL = 60  # sekunder — minskar Supabase+Yahoo-anrop från 4–6/minut till 1/minut


@app.get("/api/summary")
async def get_summary():
    """Portfolio summary: deposits → current value, with full P&L and available cash."""
    import time as _time
    from db.supabase_client import get_client, get_total_deposited
    from data.yahoo_client import get_current_price
    from scheduler import open_positions

    now_mono = _time.monotonic()
    if _summary_cache.get("data") and now_mono < _summary_cache.get("expires", 0):
        return _summary_cache["data"]

    # Total deposited capital (sum of all deposits)
    try:
        total_deposited = await get_total_deposited()
    except Exception:
        from config import PAPER_BALANCE
        total_deposited = PAPER_BALANCE

    # Realized P&L from closed trades
    try:
        result = get_client().table("stock_trades").select("pnl_kr,total_value").eq("status", "closed").execute()
        realized_pnl = sum(r["pnl_kr"] or 0 for r in (result.data or []))
    except Exception:
        realized_pnl = 0.0

    # Open positions: invested at cost + live market value
    invested = 0.0
    market_value = 0.0
    for ticker, pos in open_positions.items():
        qty = pos["quantity"]
        entry = pos["price"]
        invested += entry * qty
        try:
            current = await get_current_price(ticker)
            live = current.get("price") or entry
        except Exception:
            live = entry
        market_value += live * qty

    unrealized_pnl = market_value - invested

    # Cash = deposits + realized gains/losses - currently invested at cost
    cash = max(0.0, total_deposited + realized_pnl - invested)

    # Total portfolio value = cash + current market value of open positions
    total_value = cash + market_value
    total_pct = ((total_value - total_deposited) / total_deposited) * 100 if total_deposited else 0.0

    result = {
        "total_deposited": round(total_deposited, 2),   # What you put in total
        "available_cash": round(cash, 2),               # Free to use right now
        "invested": round(invested, 2),                 # Locked in open positions (at cost)
        "market_value": round(market_value, 2),         # Current value of open positions
        "realized_pnl": round(realized_pnl, 2),         # Locked-in gains/losses
        "unrealized_pnl": round(unrealized_pnl, 2),     # Floating gains/losses
        "total_value": round(total_value, 2),           # The number that matters
        "total_pct": round(total_pct, 2),               # Return vs total deposited
    }
    _summary_cache["data"] = result
    _summary_cache["expires"] = _time.monotonic() + _SUMMARY_TTL
    return result


@app.get("/api/deposits")
async def get_deposits():
    from db.supabase_client import get_client
    result = (
        get_client()
        .table("stock_deposits")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@app.post("/api/deposits")
async def add_deposit(body: dict):
    from db.supabase_client import add_deposit as db_add
    amount = float(body.get("amount", 0))
    note = body.get("note", "")
    if amount <= 0:
        return {"error": "Beloppet maste vara positivt"}
    deposit_id = await db_add(amount, note)
    return {"ok": True, "id": deposit_id, "amount": amount}


@app.get("/api/watchlist")
async def get_watchlist():
    from db import supabase_client as db
    return await db.get_watchlist()


@app.get("/api/positions")
async def get_positions():
    """Return open positions with live price and P&L."""
    from scheduler import open_positions
    from data.yahoo_client import get_current_price

    result = {}
    for ticker, pos in open_positions.items():
        try:
            current = await get_current_price(ticker)
            current_price = current.get("price") or pos["price"]
        except Exception:
            current_price = pos["price"]

        entry = pos["price"]
        qty = pos["quantity"]
        pnl_kr = round((current_price - entry) * qty, 2)
        pnl_pct = round(((current_price - entry) / entry) * 100, 2) if entry else 0.0

        result[ticker] = {
            **pos,
            "current_price": current_price,
            "pnl_kr": pnl_kr,
            "pnl_pct": pnl_pct,
        }
    return result


@app.get("/api/signals")
async def get_signals(limit: int = 50, status: str = None):
    from db.supabase_client import get_client
    query = (
        get_client()
        .table("stock_signals")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if status:
        query = query.eq("status", status)
    return query.execute().data


class ConfirmBody(BaseModel):
    price: float | None = None
    quantity: int | None = None


@app.post("/api/signals/{signal_id}/confirm")
async def confirm_signal(signal_id: str, body: ConfirmBody = None):
    """User confirms a pending BUY signal — creates a live trade."""
    from db.supabase_client import get_client, confirm_signal as db_confirm, save_trade
    from scheduler import open_positions, daily_trades
    import scheduler as _scheduler
    import settings as _settings

    if body is None:
        body = ConfirmBody()

    result = get_client().table("stock_signals").select("*").eq("id", signal_id).execute()
    if not result.data:
        return {"error": "Signal hittades inte"}

    signal = result.data[0]

    if signal["signal_type"] != "BUY":
        return {"error": "Bara KOP-signaler kan bekraftas"}
    if signal["status"] not in ("pending", "confirmed"):
        return {"error": f"Signalen ar redan {signal['status']}"}
    if signal["ticker"] in open_positions:
        return {"error": f"Har redan en oppna position i {signal['ticker']}"}
    max_pos = _settings.get_int("max_positions")
    if len(open_positions) >= max_pos:
        return {"error": f"Max antal positioner ({max_pos}) uppnått"}

    # Use user-supplied price/quantity or fall back to signal values
    entry_price = body.price if body.price is not None else signal["price"]
    quantity = body.quantity if body.quantity is not None else signal["quantity"]

    trade_id = await save_trade(
        ticker=signal["ticker"],
        signal_id=signal_id,
        entry_price=entry_price,
        quantity=quantity,
        stop_loss=0.0,
        take_profit=0.0,
    )

    await db_confirm(signal_id)

    open_positions[signal["ticker"]] = {
        "trade_id": trade_id,
        "price": entry_price,
        "quantity": quantity,
    }

    _scheduler.daily_trades += 1

    return {"ok": True, "trade_id": trade_id, "ticker": signal["ticker"], "entry_price": entry_price, "quantity": quantity}


@app.post("/api/signals/{signal_id}/reject")
async def reject_signal(signal_id: str):
    """User rejects a pending BUY signal."""
    from db.supabase_client import reject_signal as db_reject
    await db_reject(signal_id)
    return {"ok": True}


@app.get("/api/trades")
async def get_trades(status: str = None):
    """All trades with optional status filter: open | closed."""
    from db.supabase_client import get_client
    query = (
        get_client()
        .table("stock_trades")
        .select("*")
        .order("created_at", desc=True)
    )
    if status:
        query = query.eq("status", status)
    return query.execute().data


class CloseBody(BaseModel):
    price: float | None = None


@app.post("/api/trades/{trade_id}/close")
async def close_trade_manual(trade_id: str, body: CloseBody = None):
    """Manually close an open position. User can supply actual sell price."""
    from db.supabase_client import get_client, close_trade
    from scheduler import open_positions
    from data.yahoo_client import get_current_price

    if body is None:
        body = CloseBody()

    result = get_client().table("stock_trades").select("*").eq("id", trade_id).execute()
    if not result.data:
        return {"error": "Handel hittades inte"}

    trade = result.data[0]
    if trade["status"] != "open":
        return {"error": "Handeln ar redan stangd"}

    ticker = trade["ticker"]

    if body.price is not None:
        exit_price = body.price
    else:
        try:
            current = await get_current_price(ticker)
            exit_price = current.get("price") or trade["entry_price"]
        except Exception:
            exit_price = trade["entry_price"]

    pnl_kr = (exit_price - trade["entry_price"]) * trade["quantity"]
    pnl_pct = ((exit_price - trade["entry_price"]) / trade["entry_price"]) * 100

    await close_trade(trade_id, exit_price, "manual", pnl_kr, pnl_pct)

    if ticker in open_positions:
        del open_positions[ticker]

    return {
        "ok": True,
        "exit_price": exit_price,
        "pnl_kr": round(pnl_kr, 2),
        "pnl_pct": round(pnl_pct, 2),
    }


@app.get("/api/news")
async def get_news(ticker: str = None, limit: int = 50):
    from db.supabase_client import get_client
    query = (
        get_client()
        .table("stock_news")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if ticker:
        query = query.eq("ticker", ticker)
    return query.execute().data


@app.post("/api/news/cleanup")
async def cleanup_duplicate_news():
    """Ta bort dubbletter i stock_news — behåll den äldsta per ticker+headline."""
    from db.supabase_client import get_client
    client = get_client()
    all_news = client.table("stock_news").select("id, ticker, headline, created_at").order("created_at", desc=False).execute()
    if not all_news.data:
        return {"ok": True, "deleted": 0}

    seen: dict[str, str] = {}  # "ticker:headline" -> first id
    to_delete: list[str] = []
    for row in all_news.data:
        key = f"{row['ticker']}:{row['headline']}"
        if key in seen:
            to_delete.append(row["id"])
        else:
            seen[key] = row["id"]

    for news_id in to_delete:
        client.table("stock_news").delete().eq("id", news_id).execute()

    return {"ok": True, "deleted": len(to_delete), "kept": len(seen)}


@app.get("/api/portfolio")
async def get_portfolio():
    from db.supabase_client import get_client
    result = (
        get_client()
        .table("stock_portfolio")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@app.get("/api/indicators/{ticker}")
async def get_indicators(ticker: str):
    from db.supabase_client import get_client
    result = (
        get_client()
        .table("stock_indicators")
        .select("*")
        .eq("ticker", ticker)
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else {}


@app.get("/api/test/{ticker}")
async def test_ticker(ticker: str):
    """Manually run a full analysis for a ticker and return the result. No DB writes."""
    from data.yahoo_client import get_price_history, get_current_price
    from analysis.indicators import calculate_indicators
    from analysis.decision_engine import score_buy_signal, score_sell_signal

    ticker = ticker.upper()
    df = await get_price_history(ticker, days=220)
    if df.empty:
        return {"error": f"Ingen data fran Yahoo Finance for {ticker}."}

    indicators = calculate_indicators(df)
    if not indicators:
        return {"error": "Kunde inte berakna indikatorer."}

    current = await get_current_price(ticker)
    price = current.get("price") or indicators["current_price"]

    buy_score, buy_reasons = score_buy_signal(ticker, indicators)

    return {
        "ticker": ticker,
        "price": price,
        "data_points": len(df),
        "indicators": indicators,
        "buy_score": buy_score,
        "buy_reasons": buy_reasons,
        "signal_threshold": 60,
        "would_trigger_buy": buy_score >= 60,
    }


@app.post("/api/fetch-news/{ticker}")
async def fetch_news_for_ticker(ticker: str):
    """Manually fetch news + Gemini sentiment for a ticker and save to Supabase."""
    from data.news_fetcher import fetch_news
    from analysis.sentiment import analyze_sentiment
    from db import supabase_client as db
    from db.supabase_client import get_watchlist

    ticker = ticker.upper()
    watchlist = await get_watchlist()
    stock = next((s for s in watchlist if s["ticker"] == ticker), {})
    company = stock.get("name", ticker)

    news_list = await fetch_news(ticker, company, max_items=5)
    if not news_list:
        return {"error": f"Inga nyheter hittades for {ticker}."}

    saved = []
    for item in news_list[:1]:  # max 1 Gemini-anrop per manuellt anrop
        sentiment = await analyze_sentiment(ticker, item["headline"])
        was_saved = await db.save_news(
            ticker=ticker,
            headline=item["headline"],
            url=item["url"],
            sentiment=sentiment["sentiment"],
            sentiment_score=sentiment["score"],
            reason=sentiment["reason"],
            source=item["source"],
            published_at=item["published_at"],
        )
        saved.append({
            "headline": item["headline"],
            "sentiment": sentiment["sentiment"],
            "score": sentiment["score"],
            "reason": sentiment["reason"],
            "already_existed": not was_saved,
        })

    return {"ticker": ticker, "fetched": len(saved), "news": saved}


@app.get("/api/suggestions")
async def get_suggestions():
    from db.supabase_client import get_client
    result = (
        get_client()
        .table("stock_suggestions")
        .select("*")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    return result.data


@app.post("/api/suggestions/{suggestion_id}/accept")
async def accept_suggestion(suggestion_id: str):
    from db.supabase_client import get_client
    get_client().table("stock_suggestions").update({"status": "accepted"}).eq("id", suggestion_id).execute()
    return {"ok": True}


@app.post("/api/suggestions/{suggestion_id}/reject")
async def reject_suggestion(suggestion_id: str):
    from db.supabase_client import get_client
    get_client().table("stock_suggestions").update({"status": "rejected"}).eq("id", suggestion_id).execute()
    return {"ok": True}


@app.get("/api/ai-stats")
async def get_ai_stats():
    """Return AI usage stats for the current hour + daily totals."""
    from analysis.sentiment import get_ai_stats
    from db.supabase_client import get_ai_stats_history
    stats = get_ai_stats()
    # Also compute daily totals from all hourly rows for today
    try:
        all_rows = get_ai_stats_history(days=1)
        today_rows = [r for r in all_rows if r["date"] == stats["date"]]
        daily = {
            "calls_ok": sum(r["calls_ok"] for r in today_rows),
            "calls_failed": sum(r["calls_failed"] for r in today_rows),
            "calls_rate_limited": sum(r["calls_rate_limited"] for r in today_rows),
            "cache_hits": sum(r["cache_hits"] for r in today_rows),
            "input_tokens": sum(r["input_tokens"] for r in today_rows),
            "output_tokens": sum(r["output_tokens"] for r in today_rows),
            "total_latency_s": sum(r["total_latency_s"] for r in today_rows),
        }
        daily["total_calls"] = daily["calls_ok"] + daily["calls_failed"]
        daily["total_tokens"] = daily["input_tokens"] + daily["output_tokens"]
        daily["avg_latency_s"] = round(daily["total_latency_s"] / daily["calls_ok"], 2) if daily["calls_ok"] > 0 else 0
    except Exception:
        daily = stats
    return {**stats, "daily_totals": daily}


@app.get("/api/ai-stats/history")
async def get_ai_stats_history(granularity: str = "daily", days: int = 30):
    """Return AI stats history. granularity=daily aggregates per day, hourly returns raw rows."""
    from db.supabase_client import get_ai_stats_history as fetch_history
    rows = fetch_history(days=days)

    if granularity == "hourly":
        # Return raw hourly rows, add label
        for r in rows:
            r["label"] = f"{r['date']} {r['hour']:02d}:00"
        return rows

    # Aggregate by day
    from collections import defaultdict
    by_day: dict = defaultdict(lambda: {
        "calls_ok": 0, "calls_failed": 0, "calls_rate_limited": 0,
        "cache_hits": 0, "input_tokens": 0, "output_tokens": 0,
        "total_latency_s": 0.0, "model": "", "by_type": {},
    })
    for r in rows:
        d = by_day[r["date"]]
        d["calls_ok"] += r["calls_ok"]
        d["calls_failed"] += r["calls_failed"]
        d["calls_rate_limited"] += r["calls_rate_limited"]
        d["cache_hits"] += r["cache_hits"]
        d["input_tokens"] += r["input_tokens"]
        d["output_tokens"] += r["output_tokens"]
        d["total_latency_s"] += r["total_latency_s"]
        d["model"] = r.get("model", "")
        # Merge by_type
        for k, v in (r.get("by_type") or {}).items():
            d["by_type"][k] = d["by_type"].get(k, 0) + v

    result = []
    for dt in sorted(by_day.keys()):
        d = by_day[dt]
        d["date"] = dt
        d["label"] = dt
        d["total_tokens"] = d["input_tokens"] + d["output_tokens"]
        d["avg_latency_s"] = round(d["total_latency_s"] / d["calls_ok"], 2) if d["calls_ok"] > 0 else 0
        result.append(d)
    return result


@app.get("/api/settings")
async def get_settings():
    import settings
    return {
        "settings": settings.all_settings(),
        "descriptions": {
            "max_positions":     "Max antal öppna positioner samtidigt",
            "max_position_size": "Max investerat belopp per position (kr)",
            "signal_threshold":  "Minimumscore (0–100) för att skicka köp/säljsignal",
        },
    }


@app.post("/api/settings")
async def update_settings(body: dict):
    import settings
    allowed = {"max_positions", "max_position_size", "signal_threshold"}
    updated = {}
    for key, value in body.items():
        if key not in allowed:
            continue
        try:
            float(value)  # validate numeric
        except (TypeError, ValueError):
            return {"error": f"Ogiltigt värde för {key}: {value}"}
        await settings.save(key, str(value))
        updated[key] = str(value)
    return {"ok": True, "updated": updated}


@app.post("/api/reset")
async def reset_all():
    """Clear all trades, signals, and deposits. Use before making a fresh deposit."""
    from db.supabase_client import get_client
    from scheduler import open_positions

    db = get_client()
    db.table("stock_trades").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    db.table("stock_signals").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    db.table("stock_deposits").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    db.table("stock_notifications").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

    open_positions.clear()

    return {"ok": True, "message": "Allt nollställt. Gör en ny insättning för att starta."}


@app.post("/api/scan")
async def trigger_scan():
    """Manually trigger the weekly stock scanner."""
    from stock_scanner import run_scan
    await run_scan()
    return {"ok": True, "message": "Skanning startad."}


def _is_trading_hours() -> bool:
    """Return True if current Stockholm time is Mon–Fri 09:00–17:30."""
    from zoneinfo import ZoneInfo
    now_swe = datetime.now(ZoneInfo("Europe/Stockholm"))
    return now_swe.weekday() < 5 and 9 <= now_swe.hour < 18


@app.post("/api/run")
async def trigger_trading_loop():
    """Manually trigger a full trading loop iteration for all watchlist tickers."""
    if not _is_trading_hours():
        return {"ok": False, "message": "Utanför handelstid (mån–fre 09:00–17:30). Inget körs."}
    from scheduler import trading_loop
    await trading_loop()
    return {"ok": True, "message": "Trading loop kord for alla bevakade aktier."}


@app.post("/api/run/{ticker}")
async def trigger_single_ticker(ticker: str, background_tasks: BackgroundTasks):
    """Manually run process_ticker for a single ticker (full DB writes + signal generation)."""
    from scheduler import process_ticker
    from db.supabase_client import get_watchlist
    ticker = ticker.upper()
    watchlist = await get_watchlist()
    stock_config = next((s for s in watchlist if s["ticker"] == ticker), {})
    background_tasks.add_task(process_ticker, ticker, stock_config, None, "NEUTRAL", None, True)
    return {"ok": True, "message": f"Analys av {ticker} startad i bakgrunden (manuell, sentiment alltid på)."}


@app.post("/api/notify-test")
async def send_test_notification():
    """Send a test push notification via ntfy."""
    from notifications import ntfy
    await ntfy.send_buy_signal(
        ticker="EVO",
        company="Evolution",
        price=532.20,
        quantity=4,
        total=2128.80,
        reasons=["TEST: RSI 32 (oversalt)", "TEST: MACD crossover uppat"],
        confidence=75.0,
    )
    return {"ok": True, "message": "Testnotis skickad till ntfy."}


@app.post("/api/test-signal")
async def insert_test_signal():
    """Insert a fake pending BUY signal for EVO to test the confirm/reject flow."""
    from db.supabase_client import save_signal, get_client
    from data.yahoo_client import get_current_price

    ticker = "EVO"
    current = await get_current_price(ticker)
    price = current.get("price") or 500.0
    quantity = 4

    signal_id = await save_signal(
        ticker=ticker,
        signal_type="BUY",
        price=price,
        quantity=quantity,
        confidence=75.0,
        score=75,
        reasons=["TEST: RSI oversalt", "TEST: MACD crossover uppat"],
        indicators={"current_price": price, "rsi": 32.0},
        stop_loss=0.0,
        take_profit=0.0,
    )
    return {
        "ok": True,
        "signal_id": signal_id,
        "ticker": ticker,
        "price": price,
        "quantity": quantity,
        "message": "Testsignal skapad — ga till /api/signals eller frontenden for att bekrafta.",
    }


@app.get("/api/test-ai-stats-write")
async def test_ai_stats_write():
    """Test writing to stock_ai_stats table — returns success or exact error."""
    from db.supabase_client import get_client, upsert_ai_stats
    errors = []
    # Test 1: Direct read to verify table access
    try:
        result = get_client().table("stock_ai_stats").select("*").limit(1).execute()
        read_ok = True
        read_rows = len(result.data or [])
    except Exception as e:
        read_ok = False
        read_rows = 0
        errors.append(f"READ failed: {type(e).__name__}: {e}")

    # Test 2: Try upsert
    test_stats = {
        "date": "2099-01-01",
        "hour": 0,
        "model": "test",
        "calls_ok": 1,
        "calls_failed": 0,
        "calls_rate_limited": 0,
        "cache_hits": 0,
        "input_tokens": 100,
        "output_tokens": 50,
        "total_latency_s": 0.5,
        "by_type": {"test": 1},
    }
    try:
        upsert_ai_stats(test_stats)
        write_ok = True
    except Exception as e:
        write_ok = False
        errors.append(f"WRITE failed: {type(e).__name__}: {e}")

    # Test 3: Verify the row was written
    verify_ok = False
    if write_ok:
        try:
            result = get_client().table("stock_ai_stats").select("*").eq("date", "2099-01-01").execute()
            verify_ok = len(result.data or []) > 0
            if not verify_ok:
                errors.append("VERIFY failed: Row was not saved (RLS blocking writes?)")
            # Clean up test row
            get_client().table("stock_ai_stats").delete().eq("date", "2099-01-01").execute()
        except Exception as e:
            errors.append(f"VERIFY failed: {type(e).__name__}: {e}")

    return {
        "read_ok": read_ok,
        "read_rows": read_rows,
        "write_ok": write_ok,
        "verify_ok": verify_ok,
        "errors": errors,
        "diagnosis": "ALL OK" if (read_ok and write_ok and verify_ok) else
                     "RLS policy saknas - kor CREATE POLICY SQL i Supabase" if (read_ok and write_ok and not verify_ok) else
                     "Tabellen saknas eller schema-fel" if not read_ok else
                     "Write error - se errors",
    }


@app.get("/api/test-ai-gemini")
async def test_ai_gemini_call():
    """Make a real Gemini call and verify stats are persisted to DB."""
    from analysis.sentiment import get_ai_stats, _ai_stats, _persist_stats
    from db.supabase_client import get_client
    import time as _time

    # Snapshot before
    before = {k: v for k, v in _ai_stats.items()}

    # Make a real Gemini call
    from analysis.sentiment import analyze_sentiment
    t0 = _time.monotonic()
    result = await analyze_sentiment("TEST", "Ericsson rapporterar rekordomsattning och hojer utdelningen")
    elapsed = round(_time.monotonic() - t0, 2)

    # Snapshot after
    after = get_ai_stats()

    # Check DB
    db_row = None
    try:
        r = get_client().table("stock_ai_stats").select("*").eq("date", after["date"]).eq("hour", after["hour"]).limit(1).execute()
        db_row = r.data[0] if r.data else None
    except Exception as e:
        db_row = {"error": str(e)}

    return {
        "gemini_result": result,
        "elapsed_s": elapsed,
        "stats_before_calls_ok": before.get("calls_ok", 0),
        "stats_after_calls_ok": after.get("calls_ok", 0),
        "stats_incremented": after.get("calls_ok", 0) > before.get("calls_ok", 0),
        "db_row": db_row,
        "db_has_data": db_row is not None and "error" not in db_row,
        "diagnosis": (
            "Gemini + DB persistence OK" if (db_row and "error" not in db_row and (db_row.get("calls_ok", 0) > 0 or db_row.get("cache_hits", 0) > 0))
            else "Gemini OK men DB-row saknas" if result else "Gemini-anrop misslyckades"
        ),
    }