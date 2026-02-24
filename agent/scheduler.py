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
from analysis.sentiment import analyze_sentiment, generate_signal_description, record_cache_hit
from analysis.decision_engine import (
    score_buy_signal,
    score_sell_signal,
    calculate_position_size,
    get_effective_buy_threshold,
    get_effective_sell_threshold,
    calculate_opportunity_score,
)
from notifications import ntfy
from db import supabase_client as db

logger = logging.getLogger(__name__)

# In-memory state — persistent state lives in Supabase.
# open_positions keys: ticker -> {trade_id, price, quantity}
open_positions: dict[str, dict] = {}
cooldowns: dict[str, datetime] = {}
daily_signals = 0
daily_trades = 0

# Cache för generate_signal_description: förhindrar upprepade Gemini-anrop för samma signal
# Nyckel: "ticker:BUY/SELL" -> (description, expires_at)
_description_cache: dict[str, tuple[str, float]] = {}
_DESCRIPTION_TTL = 2 * 3600  # 2h — återanvänd samma beskrivning för upprepade signaler


async def _get_signal_description(ticker: str, signal_type: str, price: float, reasons: list[str], news_headline: str = "") -> str:
    """Hämtar signalbeskrivning från cache eller genererar ny via Gemini (max 1 anrop/2h per ticker+typ)."""
    key = f"{ticker}:{signal_type}"
    now = _time.monotonic()
    cached = _description_cache.get(key)
    if cached and now < cached[1]:
        record_cache_hit("description")
        logger.info(f"[Gemini CACHE HIT] description:{ticker}:{signal_type} | TTL={cached[1] - now:.0f}s kvar")
        return cached[0]
    logger.info(f"[Gemini CACHE MISS] description:{ticker}:{signal_type} | Genererar ny...")
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
            await process_ticker(ticker, stock_config=stock, index_df=index_df, market_regime=market_regime, stock_config_map=stock_config_map)
        except Exception as e:
            logger.error(f"Fel vid bearbetning av {ticker}: {e}", exc_info=True)


async def process_ticker(ticker: str, stock_config: dict | None = None, index_df=None, market_regime: str = "NEUTRAL", stock_config_map: dict | None = None, manual: bool = False):
    global daily_signals, daily_trades
    now = datetime.now(timezone.utc)
    cfg = stock_config or {}
    stock_config_map = stock_config_map or {}
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

    # 2. Relative strength vs OMXS30
    rs = calculate_relative_strength(df, index_df) if index_df is not None else None
    if rs is not None:
        indicators["relative_strength"] = rs

    in_position = ticker in open_positions

    # 3. Pre-score (tekniska indikatorer utan sentiment) — gate för AI-anrop
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
    _SENTIMENT_GATE = 20  # poäng utan sentiment för att motivera AI-anrop
    needs_sentiment = manual or in_position or pre_buy_score >= _SENTIMENT_GATE or pre_sell_score >= _SENTIMENT_GATE

    news_list = await fetch_news(ticker, company)
    latest_sentiment = None

    if needs_sentiment:
        for item in news_list[:1]:  # max 1 Gemini-anrop per ticker per loop
            sentiment = await analyze_sentiment(ticker, item["headline"])
            # save_news har inbyggd dedup — sparar bara om rubriken inte redan finns
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
        logger.info(f"{ticker}: sentimentanalys körd{' (manuell)' if manual else ''} | resultat={latest_sentiment.get('sentiment') if latest_sentiment else 'NONE'} (pre_score buy={pre_buy_score} sell={pre_sell_score})")
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

    # Spara live-score till stock_indicators MED sentiment inkluderat
    # Beräkna full buy-score (med sentiment, insider, rapport) för korrekt dashboard-visning
    full_buy_score, _ = score_buy_signal(
        ticker, indicators, latest_sentiment, insider_trades,
        has_open_report_soon=has_report_soon,
        relative_strength=rs,
        market_regime=market_regime,
    )
    indicators["buy_score"] = full_buy_score
    await db.save_indicators(ticker, indicators)

    # 4a. SELL logic — indicator-based sell recommendations
    if in_position:
        position = open_positions[ticker]
        trade_id = position.get("trade_id")
        buy_price = position["price"]
        qty = position["quantity"]
        pnl_kr = (price - buy_price) * qty
        pnl_pct = ((price - buy_price) / buy_price) * 100

        # Check indicator-based sell signal
        sell_score, sell_reasons = score_sell_signal(
            ticker, indicators, position, latest_sentiment, relative_strength=rs
        )

        # Adaptive sell threshold by market regime
        effective_sell_threshold = get_effective_sell_threshold(
            _settings.get_int("sell_threshold"), market_regime=market_regime
        )
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
                f"SALJ-SIGNAL {ticker} | score={sell_score} | P&L={pnl_pct:+.1f}% | anvandaren maste salja pa Avanza"
            )

    # 4b. BUY logic — generates a PENDING signal; user must confirm via dashboard
    else:
        buy_score, buy_reasons = score_buy_signal(
            ticker, indicators, latest_sentiment, insider_trades,
            has_open_report_soon=has_report_soon,
            relative_strength=rs,
            market_regime=market_regime,
        )

        # Adaptive buy threshold by market regime + liquidity segment
        base_threshold = _settings.get_int("signal_threshold")
        try:
            avg_turnover = (df["close"] * df["volume"]).mean()
            signal_threshold = get_effective_buy_threshold(
                base_threshold,
                market_regime=market_regime,
                avg_turnover=float(avg_turnover),
            )
            logger.debug(
                f"{ticker}: adaptiv köp-tröskel {signal_threshold}p "
                f"(regim={market_regime}, omsättning={avg_turnover/1e6:.0f}M/dag)"
            )
        except Exception:
            signal_threshold = get_effective_buy_threshold(base_threshold, market_regime=market_regime)

        if buy_score < signal_threshold:
            return

        candidate_atr = indicators.get("atr", 0)
        candidate_atr_pct = (candidate_atr / price) if (candidate_atr and price > 0) else 0.0
        candidate_opportunity = calculate_opportunity_score(
            buy_score,
            relative_strength=rs,
            atr_pct=candidate_atr_pct,
            volume_ratio=float(indicators.get("volume_ratio", 1.0) or 1.0),
            market_regime=market_regime,
        )

        # Positions full — check if rotation is warranted
        if len(open_positions) >= _settings.get_int("max_positions"):
            # Score all open positions using their OWN indicators (not the new candidate's)
            # Beräkna buy-score för varje position (som om vi analyserade den idag)
            # och jämför med kandidatens buy-score — samma skala
            weakest_ticker = None
            weakest_opp_score = float('inf')  # lägst opportunity = svagast
            weakest_buy_score = float('inf')
            weakest_indicators = {}
            weakest_current_price = 0.0
            for pos_ticker, pos in open_positions.items():
                try:
                    pos_df = await get_price_history(pos_ticker, days=220)
                    pos_indicators = calculate_indicators(pos_df) if not pos_df.empty else {}
                    pos_rs = calculate_relative_strength(pos_df, index_df) if (not pos_df.empty and index_df is not None) else None
                except Exception:
                    pos_indicators = {}
                    pos_rs = None
                # Beräkna buy-score (samma skala som kandidaten) istället för sell-score
                pos_buy_score, _ = score_buy_signal(
                    pos_ticker, pos_indicators,
                    news_sentiment=None, insider_trades=None,
                    has_open_report_soon=False,
                    relative_strength=pos_rs,
                    market_regime=market_regime,
                )
                pos_price = pos_indicators.get("current_price", pos.get("price", 0))
                pos_atr = pos_indicators.get("atr", 0)
                pos_atr_pct = (pos_atr / pos_price) if (pos_atr and pos_price > 0) else 0.0
                pos_opp_score = calculate_opportunity_score(
                    pos_buy_score,
                    relative_strength=pos_rs,
                    atr_pct=pos_atr_pct,
                    volume_ratio=float(pos_indicators.get("volume_ratio", 1.0) or 1.0),
                    market_regime=market_regime,
                )
                if pos_opp_score < weakest_opp_score:
                    weakest_opp_score = pos_opp_score
                    weakest_buy_score = pos_buy_score
                    weakest_ticker = pos_ticker
                    weakest_indicators = pos_indicators
                    weakest_current_price = pos_indicators.get("current_price", pos["price"])

            # Rotate only if candidate is clearly better on risk-adjusted opportunity scale
            if weakest_ticker and candidate_opportunity > weakest_opp_score + 8:
                pos = open_positions[weakest_ticker]
                # Använd aktuellt marknadspris — inte entry-pris
                current_price_weak = weakest_current_price or pos["price"]
                pos_qty = pos["quantity"]
                pnl_kr = (current_price_weak - pos["price"]) * pos_qty
                pnl_pct = ((current_price_weak - pos["price"]) / pos["price"]) * 100 if pos["price"] else 0
                rotation_reasons = [
                    f"Rotation: {ticker} opportunity {candidate_opportunity:.1f} > {weakest_ticker} {weakest_opp_score:.1f}",
                    f"Salj {weakest_ticker} pa Avanza for att frigora kapital",
                ]
                await db.save_signal(
                    weakest_ticker, "SELL", current_price_weak, pos_qty, float(buy_score),
                    buy_score, rotation_reasons, weakest_indicators, 0.0, 0.0,
                )
                weakest_cfg = stock_config_map.get(weakest_ticker, {})
                await ntfy.send_sell_signal(
                    weakest_ticker, weakest_cfg.get("name", weakest_ticker),
                    current_price_weak, pos_qty, pnl_pct, pnl_kr, rotation_reasons, float(buy_score),
                )
                logger.info(
                    f"ROTATION: Salj {weakest_ticker} for att kopa {ticker} | "
                    f"ny opp={candidate_opportunity:.1f} > gammal opp={weakest_opp_score:.1f}"
                )
            else:
                logger.debug(
                    f"{ticker}: max positioner natt, ingen rotation "
                    f"(opp={candidate_opportunity:.1f} vs svagaste={weakest_opp_score:.1f})."
                )
            return

        confidence = min(99.0, float(buy_score))
        atr = indicators.get("atr", 0)
        atr_pct = (atr / price) if (atr and price > 0) else 0.0
        position_value = calculate_position_size(confidence, atr_pct=atr_pct)
        quantity = int(position_value / price) if price > 0 else 0

        if quantity < 1:
            logger.info(f"{ticker}: for hogt pris for en hel aktie.")
            return

        news_headline = news_list[0]["headline"] if news_list else ""
        description = await _get_signal_description(ticker, "BUY", price, buy_reasons, news_headline)
        indicators["signal_description"] = description

        await db.save_signal(
            ticker, "BUY", price, quantity, confidence, buy_score,
            buy_reasons, indicators, 0.0, 0.0,
        )
        await ntfy.send_buy_signal(
            ticker, company, price, quantity,
            price * quantity, buy_reasons, confidence,
        )

        # Cooldown 24h — förhindrar upprepade identiska signaler vid nästa tick
        cooldowns[ticker] = now + timedelta(hours=24)

        daily_signals += 1
        logger.info(
            f"KOP-SIGNAL {ticker} | score={buy_score} | qty={quantity} | VANTAR BEKRAFTELSE"
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
