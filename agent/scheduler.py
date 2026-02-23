import logging
import time as _time
from datetime import datetime, date, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import PAPER_BALANCE
import settings as _settings
from data.yahoo_client import get_price_history, get_current_price, get_index_history, get_earnings_date
from data.news_fetcher import fetch_news
from data.insider_fetcher import fetch_insider_trades
from analysis.indicators import calculate_indicators, calculate_relative_strength, calculate_market_regime
from analysis.sentiment import analyze_sentiment, generate_signal_description
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

# Dedup-cache för nyhetssparande: förhindrar att samma rubrik sparas flera gånger per dag
# Nyckel: "ticker:headline" -> expires_at (monotonic)
_news_save_cache: dict[str, float] = {}
_NEWS_SAVE_TTL = 24 * 3600  # 24h — sparar varje unik rubrik max en gång per dag

# Cache för generate_signal_description: förhindrar upprepade Gemini-anrop för samma signal
# Nyckel: "ticker:BUY/SELL" -> (description, expires_at)
_description_cache: dict[str, tuple[str, float]] = {}
_DESCRIPTION_TTL = 2 * 3600  # 2h — återanvänd samma beskrivning för upprepade signaler


def _should_save_news(ticker: str, headline: str) -> bool:
    """Returnerar True (och markerar som sparad) om rubriken inte sparats senaste 24h."""
    key = f"{ticker}:{headline}"
    now = _time.monotonic()
    if _news_save_cache.get(key, 0) > now:
        return False
    _news_save_cache[key] = now + _NEWS_SAVE_TTL
    return True


async def _get_signal_description(ticker: str, signal_type: str, price: float, reasons: list[str], news_headline: str = "") -> str:
    """Hämtar signalbeskrivning från cache eller genererar ny via Gemini (max 1 anrop/2h per ticker+typ)."""
    key = f"{ticker}:{signal_type}"
    now = _time.monotonic()
    cached = _description_cache.get(key)
    if cached and now < cached[1]:
        return cached[0]
    description = await generate_signal_description(ticker, signal_type, price, reasons, news_headline)
    _description_cache[key] = (description, now + _DESCRIPTION_TTL)
    return description

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

    # Fetch OMXS30 once per loop — used for relative strength and market regime
    try:
        index_df = await get_index_history()
    except Exception as e:
        logger.warning(f"Kunde inte hämta OMXS30-data: {e}")
        index_df = None

    market_regime = calculate_market_regime(index_df)
    logger.info(f"Marknadsregim: {market_regime}")

    watchlist = await db.get_watchlist()
    stock_config_map = {s["ticker"]: s for s in watchlist}

    for stock in watchlist:
        ticker = stock["ticker"]

        if ticker in cooldowns and cooldowns[ticker] > now:
            logger.debug(f"{ticker}: cooldown aktiv till {cooldowns[ticker]}")
            continue

        try:
            await process_ticker(ticker, stock_config=stock, index_df=index_df, market_regime=market_regime)
        except Exception as e:
            logger.error(f"Fel vid bearbetning av {ticker}: {e}", exc_info=True)


async def process_ticker(ticker: str, stock_config: dict | None = None, index_df=None, market_regime: str = "NEUTRAL"):
    global daily_signals, daily_trades
    now = datetime.now(timezone.utc)
    cfg = stock_config or {}
    company = cfg.get("name", ticker)

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

    # 2. Relative strength vs OMXS30
    rs = calculate_relative_strength(df, index_df) if index_df is not None else None
    if rs is not None:
        indicators["relative_strength"] = rs

    in_position = ticker in open_positions

    # 3. Pre-score (tekniska indikatorer utan sentiment) — gate för Gemini-anrop
    pre_buy_score, _ = score_buy_signal(
        ticker, indicators, news_sentiment=None, insider_trades=None,
        has_open_report_soon=False, relative_strength=rs, market_regime=market_regime,
    )
    pre_sell_score = 0
    if in_position:
        pre_sell_score, _ = score_sell_signal(
            ticker, indicators, open_positions[ticker], news_sentiment=None, relative_strength=rs
        )

    # Hämta nyheter (cachas 30 min — billigt)
    # Kör Gemini-sentimentanalys BARA om teknisk signal redan är lovande
    _SENTIMENT_GATE = 35  # poäng utan sentiment för att motivera Gemini-anrop
    needs_sentiment = in_position or pre_buy_score >= _SENTIMENT_GATE or pre_sell_score >= _SENTIMENT_GATE

    news_list = await fetch_news(ticker, company)
    latest_sentiment = None

    if needs_sentiment:
        for item in news_list[:1]:  # max 1 Gemini-anrop per ticker per loop
            sentiment = await analyze_sentiment(ticker, item["headline"])
            if _should_save_news(ticker, item["headline"]):
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
        logger.debug(f"{ticker}: sentimentanalys körd (pre_score buy={pre_buy_score} sell={pre_sell_score})")
    else:
        logger.debug(f"{ticker}: Gemini hoppas over (pre_score={pre_buy_score}p < {_SENTIMENT_GATE}p)")

    # 4. Insider data
    insider_trades = await fetch_insider_trades(ticker, company_name=company)

    # 5. Earnings date — avoid buying within 48h of a report
    has_report_soon = False
    try:
        earnings_str = await get_earnings_date(ticker)
        if earnings_str:
            report_date = date.fromisoformat(earnings_str[:10])
            delta = (report_date - date.today()).days
            has_report_soon = 0 <= delta <= 2
            if has_report_soon:
                logger.info(f"{ticker}: rapport om {delta} dag(ar) — köp-penalty aktiv")
    except Exception as e:
        logger.debug(f"{ticker}: Kunde inte hämta rapportdatum: {e}")

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
            # Alert user to sell on Avanza — no auto-close
            label = "Stop-loss" if hit_sl else "Take-profit"
            reasons = [f"{label} natt ({price:.2f} kr) — salj pa Avanza"]
            news_headline = news_list[0]["headline"] if news_list else ""
            description = await _get_signal_description(ticker, "SELL", price, reasons, news_headline)
            indicators["signal_description"] = description

            await db.save_signal(
                ticker, "SELL", price, qty, 100.0, 100, reasons, indicators, 0.0, 0.0,
            )
            notif_subtype = "sl_triggered" if hit_sl else "tp_triggered"
            await ntfy.send_sell_signal(
                ticker, company, price, qty, pnl_pct, pnl_kr, reasons, 100.0,
                notif_subtype=notif_subtype,
            )

            # Cooldown 2h — förhindrar upprepade SL/TP-signaler om priset svävar kring nivån
            cooldowns[ticker] = now + timedelta(hours=2)

            daily_signals += 1
            logger.info(
                f"SALJ-ALERT {ticker} ({label}) | pris={price} | anvandaren maste salja pa Avanza"
            )

        else:
            # Check indicator-based sell signal
            sell_score, sell_reasons = score_sell_signal(
                ticker, indicators, position, latest_sentiment, relative_strength=rs
            )

            # Sell threshold — separate from buy, lowered further in BEAR market
            effective_sell_threshold = _settings.get_int("sell_threshold") - (10 if market_regime == "BEAR" else 0)
            if sell_score >= effective_sell_threshold:
                confidence = min(99.0, float(sell_score))
                sell_reasons.append("Salj pa Avanza och stang positionen i appen")
                news_headline = news_list[0]["headline"] if news_list else ""
                description = await _get_signal_description(ticker, "SELL", price, sell_reasons, news_headline)
                indicators["signal_description"] = description

                await db.save_signal(
                    ticker, "SELL", price, qty, confidence, sell_score,
                    sell_reasons, indicators, 0.0, 0.0,
                )
                await ntfy.send_sell_signal(
                    ticker, company, price, qty, pnl_pct, pnl_kr, sell_reasons, confidence,
                )

                # Cooldown 4h för indikatorbaserade säljsignaler
                cooldowns[ticker] = now + timedelta(hours=4)

                daily_signals += 1
                logger.info(
                    f"SALJ-SIGNAL {ticker} | score={sell_score} | anvandaren maste salja pa Avanza"
                )

    # 4b. BUY logic — generates a PENDING signal; user must confirm via dashboard
    else:
        buy_score, buy_reasons = score_buy_signal(
            ticker, indicators, latest_sentiment, insider_trades,
            has_open_report_soon=has_report_soon,
            relative_strength=rs,
            market_regime=market_regime,
        )

        # Segment-differentiated threshold based on avg daily SEK turnover
        # Large cap (>100M/dag): stricter threshold — more signals available, higher bar
        # Mid cap (30–100M/dag): standard threshold
        # Small cap (<30M/dag): same as standard (few signals, don't raise bar further)
        base_threshold = _settings.get_int("signal_threshold")
        try:
            avg_turnover = (df["close"] * df["volume"]).mean()
            if avg_turnover >= 100_000_000:
                signal_threshold = base_threshold + 10  # Large cap: +10p
                logger.debug(f"{ticker}: Large cap ({avg_turnover/1e6:.0f}M SEK/dag) — tröskel {signal_threshold}p")
            else:
                signal_threshold = base_threshold
        except Exception:
            signal_threshold = base_threshold

        if buy_score < signal_threshold:
            return

        # Positions full — check if rotation is warranted
        if len(open_positions) >= _settings.get_int("max_positions"):
            # Score all open positions using their OWN indicators (not the new candidate's)
            weakest_ticker = None
            weakest_sell_score = -1
            weakest_indicators = {}
            for pos_ticker, pos in open_positions.items():
                try:
                    pos_df = await get_price_history(pos_ticker, days=220)
                    pos_indicators = calculate_indicators(pos_df) if not pos_df.empty else {}
                    pos_rs = calculate_relative_strength(pos_df, index_df) if (not pos_df.empty and index_df is not None) else None
                except Exception:
                    pos_indicators = {}
                    pos_rs = None
                pos_sell_score, _ = score_sell_signal(pos_ticker, pos_indicators, pos, latest_sentiment, relative_strength=pos_rs)
                if pos_sell_score > weakest_sell_score:
                    weakest_sell_score = pos_sell_score
                    weakest_ticker = pos_ticker
                    weakest_indicators = pos_indicators

            # Only rotate if new candidate is significantly better than weakest position
            if weakest_ticker and buy_score > weakest_sell_score + 15:
                pos = open_positions[weakest_ticker]
                pos_price = pos["price"]
                pos_qty = pos["quantity"]
                rotation_reasons = [
                    f"Rotation: {ticker} ({buy_score}p) ar battre an {weakest_ticker} ({weakest_sell_score}p)",
                    f"Salj {weakest_ticker} pa Avanza for att frigora kapital",
                ]
                await db.save_signal(
                    weakest_ticker, "SELL", pos_price, pos_qty, float(weakest_sell_score),
                    weakest_sell_score, rotation_reasons, weakest_indicators, 0.0, 0.0,
                )
                weakest_cfg = stock_config_map.get(weakest_ticker, {})
                await ntfy.send_sell_signal(
                    weakest_ticker, weakest_cfg.get("name", weakest_ticker),
                    pos_price, pos_qty, 0.0, 0.0, rotation_reasons, float(weakest_sell_score),
                )
                logger.info(
                    f"ROTATION: Salj {weakest_ticker} for att kopa {ticker} | "
                    f"ny score={buy_score} > gammal score={weakest_sell_score}"
                )
            else:
                logger.debug(f"{ticker}: max positioner natt, ingen rotation motiverad.")
            return

        confidence = min(99.0, float(buy_score))
        position_value = calculate_position_size(confidence)
        quantity = int(position_value / price) if price > 0 else 0

        if quantity < 1:
            logger.info(f"{ticker}: for hogt pris for en hel aktie.")
            return

        stop_loss, take_profit = calculate_stop_take(price, indicators, cfg)
        news_headline = news_list[0]["headline"] if news_list else ""
        description = await _get_signal_description(ticker, "BUY", price, buy_reasons, news_headline)
        indicators["signal_description"] = description

        await db.save_signal(
            ticker, "BUY", price, quantity, confidence, buy_score,
            buy_reasons, indicators, stop_loss, take_profit,
        )
        await ntfy.send_buy_signal(
            ticker, company, price, quantity,
            price * quantity, buy_reasons, stop_loss, take_profit, confidence,
        )

        # Cooldown 24h — förhindrar upprepade identiska signaler vid nästa tick
        cooldowns[ticker] = now + timedelta(hours=24)

        daily_signals += 1
        logger.info(
            f"KOP-SIGNAL {ticker} | score={buy_score} | qty={quantity} | "
            f"SL={stop_loss} | TP={take_profit} | VANTAR BEKRAFTELSE"
        )


async def evening_summary():
    """17:35 – Send evening push notification."""
    portfolio_value, portfolio_pct = await db.get_portfolio_summary(PAPER_BALANCE)
    await ntfy.send_evening_summary(portfolio_value, portfolio_pct, daily_signals, daily_trades)


async def daily_scan():
    """17:45 Mon–Fri – scan full universe, rotate watchlist if better candidates found."""
    from stock_scanner import run_scan
    await run_scan()


async def weekly_scan():
    """Sunday 18:00 – full universe scan (same as daily but explicit)."""
    from stock_scanner import run_scan
    await run_scan()


def setup_scheduler() -> AsyncIOScheduler:
    tz = "Europe/Stockholm"
    # 08:30 – Morgonkontroll
    scheduler.add_job(morning_check, CronTrigger(day_of_week="mon-fri", hour=8, minute=30, timezone=tz))
    # 08:45 – Morgonsummering
    scheduler.add_job(morning_summary, CronTrigger(day_of_week="mon-fri", hour=8, minute=45, timezone=tz))
    # 09:00–16:58 – Handelsloop var 2:a minut
    scheduler.add_job(
        trading_loop,
        CronTrigger(day_of_week="mon-fri", hour="9-16", minute="*/2", timezone=tz),
    )
    # 17:00–17:28 – Handelsloop (sista 15 minuter, inte 17:30+)
    scheduler.add_job(
        trading_loop,
        CronTrigger(day_of_week="mon-fri", hour=17, minute="0,2,4,6,8,10,12,14,16,18,20,22,24,26,28", timezone=tz),
    )
    # 17:35 – Kvallssummering
    scheduler.add_job(evening_summary, CronTrigger(day_of_week="mon-fri", hour=17, minute=35, timezone=tz))
    # 17:45 – Daglig skanning av hela universumet
    scheduler.add_job(daily_scan, CronTrigger(day_of_week="mon-fri", hour=17, minute=45, timezone=tz))
    # Sondag 18:00 – veckovis aktiesskanning
    scheduler.add_job(weekly_scan, CronTrigger(day_of_week="sun", hour=18, minute=0, timezone=tz))

    return scheduler
