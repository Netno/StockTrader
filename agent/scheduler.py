import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import TICKERS, PAPER_BALANCE, MAX_POSITIONS, SIGNAL_THRESHOLD
from data.yahoo_client import get_price_history, get_current_price
from data.news_fetcher import fetch_news
from data.insider_fetcher import fetch_insider_trades
from analysis.indicators import calculate_indicators
from analysis.sentiment import analyze_sentiment
from analysis.decision_engine import (
    score_buy_signal,
    score_sell_signal,
    calculate_position_size,
    calculate_stop_take,
)
from notifications import ntfy
from db import supabase_client as db

logger = logging.getLogger(__name__)

# In-memory state — persistent state lives in Supabase.
# open_positions keys: ticker -> {trade_id, price, quantity, stop_loss_price, take_profit_price}
open_positions: dict[str, dict] = {}
cooldowns: dict[str, datetime] = {}
daily_signals = 0
daily_trades = 0

scheduler = AsyncIOScheduler(timezone="Europe/Stockholm")


async def load_open_positions():
    """Load confirmed open trades from DB into memory on startup."""
    try:
        trades = await db.get_open_trades()
        for trade in trades:
            open_positions[trade["ticker"]] = {
                "trade_id": trade["id"],
                "price": trade["entry_price"],
                "quantity": trade["quantity"],
                "stop_loss_price": trade["stop_loss_price"],
                "take_profit_price": trade["take_profit_price"],
            }
        logger.info(f"Laddade {len(open_positions)} oppna positioner fran databasen.")
    except Exception as e:
        logger.warning(f"Kunde inte ladda positioner fran DB (korsningstabell saknas?): {e}")


async def morning_check():
    """08:30 – Check report calendar, reset daily counters."""
    logger.info("Morning check started.")
    global daily_signals, daily_trades
    daily_signals = 0
    daily_trades = 0
    logger.info("Morning check complete.")


async def morning_summary():
    """08:45 – Send morning push notification."""
    portfolio_value, portfolio_pct = await db.get_portfolio_summary(PAPER_BALANCE)
    paused = [t for t, until in cooldowns.items() if until > datetime.now(timezone.utc)]
    await ntfy.send_morning_summary(
        portfolio_value=portfolio_value,
        portfolio_pct=portfolio_pct,
        open_positions=len(open_positions),
        reports_today=[],
        paused_tickers=paused,
    )


async def trading_loop():
    """Every 2 minutes Mon–Fri 09:00–17:30 – main analysis loop."""
    now = datetime.now(timezone.utc)
    logger.info(f"Trading loop tick: {now.strftime('%H:%M:%S')}")

    watchlist = await db.get_watchlist()

    for stock in watchlist:
        ticker = stock["ticker"]

        if ticker in cooldowns and cooldowns[ticker] > now:
            logger.debug(f"{ticker}: cooldown aktiv till {cooldowns[ticker]}")
            continue

        try:
            await process_ticker(ticker)
        except Exception as e:
            logger.error(f"Fel vid bearbetning av {ticker}: {e}", exc_info=True)


async def process_ticker(ticker: str):
    global daily_signals, daily_trades
    company = TICKERS.get(ticker, {}).get("name", ticker)

    # 1. Price history + indicators
    df = await get_price_history(ticker, days=220)
    if df.empty:
        logger.warning(f"{ticker}: tom DataFrame fran Yahoo Finance.")
        return

    indicators = calculate_indicators(df)
    if not indicators:
        logger.warning(f"{ticker}: kunde inte berakna indikatorer.")
        return

    current = await get_current_price(ticker)
    price = current.get("price") or indicators["current_price"]
    volume = current.get("volume") or 0

    await db.save_price(ticker, price, volume)
    await db.save_indicators(ticker, indicators)

    # 2. News + sentiment
    news_list = await fetch_news(ticker, company)
    latest_sentiment = None

    for item in news_list[:2]:
        sentiment = await analyze_sentiment(ticker, item["headline"])
        await db.save_news(
            ticker=ticker,
            headline=item["headline"],
            url=item["url"],
            sentiment=sentiment["sentiment"],
            sentiment_score=sentiment["score"],
            reason=sentiment["reason"],
            source=item["source"],
            published_at=item["published_at"],
        )
        if latest_sentiment is None:
            latest_sentiment = sentiment

    # 3. Insider data
    insider_trades = await fetch_insider_trades(ticker)

    in_position = ticker in open_positions

    # 4a. SELL / SL / TP logic
    if in_position:
        position = open_positions[ticker]
        trade_id = position.get("trade_id")
        buy_price = position["price"]
        qty = position["quantity"]
        pnl_kr = (price - buy_price) * qty
        pnl_pct = ((price - buy_price) / buy_price) * 100

        hit_sl = price <= position["stop_loss_price"]
        hit_tp = price >= position["take_profit_price"]

        if hit_sl or hit_tp:
            # Auto-close: stop-loss or take-profit triggered
            close_reason = "stop_loss" if hit_sl else "take_profit"
            label = "Stop-loss" if hit_sl else "Take-profit"
            reasons = [f"{label} natt ({price:.2f} kr)"]

            await db.save_signal(
                ticker, "SELL", price, qty, 100.0, 100, reasons, indicators, 0.0, 0.0,
            )
            if trade_id:
                await db.close_trade(trade_id, price, close_reason, pnl_kr, pnl_pct)
            await ntfy.send_sell_signal(
                ticker, company, price, qty, pnl_pct, pnl_kr, reasons, 100.0,
            )

            del open_positions[ticker]
            daily_signals += 1
            daily_trades += 1
            logger.info(
                f"AUTO-STANG {ticker} ({close_reason}) | P&L={pnl_pct:+.1f}% ({pnl_kr:+.0f} kr)"
            )

        else:
            # Check indicator-based sell signal
            sell_score, sell_reasons = score_sell_signal(
                ticker, indicators, position, latest_sentiment
            )

            if sell_score >= SIGNAL_THRESHOLD:
                confidence = min(99.0, float(sell_score))

                await db.save_signal(
                    ticker, "SELL", price, qty, confidence, sell_score,
                    sell_reasons, indicators, 0.0, 0.0,
                )
                if trade_id:
                    await db.close_trade(trade_id, price, "signal", pnl_kr, pnl_pct)
                await ntfy.send_sell_signal(
                    ticker, company, price, qty, pnl_pct, pnl_kr, sell_reasons, confidence,
                )

                del open_positions[ticker]
                daily_signals += 1
                daily_trades += 1
                logger.info(
                    f"SALJ {ticker} | score={sell_score} | P&L={pnl_pct:+.1f}% ({pnl_kr:+.0f} kr)"
                )

    # 4b. BUY logic — generates a PENDING signal; user must confirm via dashboard
    else:
        if len(open_positions) >= MAX_POSITIONS:
            return

        buy_score, buy_reasons = score_buy_signal(
            ticker, indicators, latest_sentiment, insider_trades,
            has_open_report_soon=False,
        )

        if buy_score >= SIGNAL_THRESHOLD:
            confidence = min(99.0, float(buy_score))
            position_value = calculate_position_size(confidence)
            quantity = int(position_value / price) if price > 0 else 0

            if quantity < 1:
                logger.info(f"{ticker}: for lat pris for en hel aktie.")
                return

            stop_loss, take_profit = calculate_stop_take(ticker, price, indicators)

            await db.save_signal(
                ticker, "BUY", price, quantity, confidence, buy_score,
                buy_reasons, indicators, stop_loss, take_profit,
            )
            # No auto-execution — user confirms via dashboard
            await ntfy.send_buy_signal(
                ticker, company, price, quantity,
                price * quantity, buy_reasons, stop_loss, take_profit, confidence,
            )

            daily_signals += 1
            logger.info(
                f"KOP-SIGNAL {ticker} | score={buy_score} | qty={quantity} | "
                f"SL={stop_loss} | TP={take_profit} | VANTAR BEKRAFTELSE"
            )


async def evening_summary():
    """17:35 – Send evening push notification."""
    portfolio_value, portfolio_pct = await db.get_portfolio_summary(PAPER_BALANCE)
    await ntfy.send_evening_summary(portfolio_value, portfolio_pct, daily_signals, daily_trades)


async def weekly_scan():
    """Sunday 18:00 – scan broader universe and suggest watchlist changes."""
    from stock_scanner import run_scan
    await run_scan()


def setup_scheduler() -> AsyncIOScheduler:
    # 08:30 – Morgonkontroll
    scheduler.add_job(morning_check, CronTrigger(day_of_week="mon-fri", hour=8, minute=30))
    # 08:45 – Morgonsummering
    scheduler.add_job(morning_summary, CronTrigger(day_of_week="mon-fri", hour=8, minute=45))
    # 09:00–17:28 – Handelsloop var 2:a minut
    scheduler.add_job(
        trading_loop,
        CronTrigger(day_of_week="mon-fri", hour="9-17", minute="*/2"),
    )
    # 17:35 – Kvallssummering
    scheduler.add_job(evening_summary, CronTrigger(day_of_week="mon-fri", hour=17, minute=35))
    # Sondag 18:00 – veckovis aktiesskanning
    scheduler.add_job(weekly_scan, CronTrigger(day_of_week="sun", hour=18, minute=0))

    return scheduler
