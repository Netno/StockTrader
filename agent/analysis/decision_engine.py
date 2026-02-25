from typing import Optional
from data.insider_fetcher import has_significant_insider_buy
import settings as _settings


# ── Friktionsmodell (courtage + spread + slippage) ──────────────────────

def calculate_courtage(order_value: float, total_equity: float) -> float:
    """Avanzas courtagetrappa.

    Under 50 000 SEK totalt equity → 0 kr courtage (Avanza Start).
    Över 50 000 SEK → max(1 kr, ordervärde × 0.25%).
    """
    if total_equity < 50_000:
        return 0.0
    return max(1.0, order_value * 0.0025)


def estimate_spread_cost(order_value: float, avg_daily_turnover: float = 0.0) -> float:
    """Estimera spread/slippage-kostnad i SEK baserat på likviditetssegment.

    Stora bolag (>100M/dag):  ~0.15%
    Medelstora (30–100M/dag): ~0.40%
    Små (<30M/dag):           ~0.80%
    """
    if avg_daily_turnover >= 100_000_000:
        return order_value * 0.0015
    elif avg_daily_turnover >= 30_000_000:
        return order_value * 0.004
    else:
        return order_value * 0.008


def calculate_transaction_cost(
    order_value: float,
    total_equity: float,
    avg_daily_turnover: float = 0.0,
) -> float:
    """Total transaktionskostnad (courtage + spread) i SEK."""
    return (
        calculate_courtage(order_value, total_equity)
        + estimate_spread_cost(order_value, avg_daily_turnover)
    )


def calculate_round_trip_cost_pct(
    order_value: float,
    total_equity: float,
    avg_daily_turnover: float = 0.0,
) -> float:
    """Round-trip kostnad (köp + sälj) som procent av ordervärdet."""
    one_way = calculate_transaction_cost(order_value, total_equity, avg_daily_turnover)
    return (one_way * 2 / order_value * 100) if order_value > 0 else 0.0


# ── ATR-baserade prisnivåer ─────────────────────────────────────────────

def calculate_atr_stop_loss(price: float, atr: float, multiplier: float = 1.8) -> float:
    """ATR-baserad stop-loss.  Default 1.8× ATR under inträde."""
    if atr <= 0 or price <= 0:
        return round(price * 0.94, 2)  # fallback 6%
    return round(price - (atr * multiplier), 2)


def calculate_atr_take_profit(price: float, atr: float, multiplier: float = 3.5) -> float:
    """ATR-baserad take-profit.  Default 3.5× ATR ger ~2:1 R/R."""
    if atr <= 0 or price <= 0:
        return round(price * 1.12, 2)  # fallback 12%
    return round(price + (atr * multiplier), 2)


def score_buy_signal(
    ticker: str,
    indicators: dict,
    news_sentiment: Optional[dict] = None,
    insider_trades: Optional[list] = None,
    has_open_report_soon: bool = False,
    relative_strength: Optional[float] = None,
    market_regime: str = "NEUTRAL",
) -> tuple[int, list[str]]:
    """
    Calculate buy signal score.
    Returns (score, reasons). Signal fires if score >= threshold (default 60).
    """
    score = 0
    reasons = []

    rsi = indicators.get("rsi")
    volume_ratio = indicators.get("volume_ratio", 1.0)
    daily_return = indicators.get("daily_return")
    current_price = indicators.get("current_price")
    ma50 = indicators.get("ma50")
    ma200 = indicators.get("ma200")
    bb_lower = indicators.get("bollinger_lower")
    macd = indicators.get("macd")
    macd_signal = indicators.get("macd_signal")
    macd_prev = indicators.get("macd_prev")
    macd_signal_prev = indicators.get("macd_signal_prev")
    macd_histogram = indicators.get("macd_histogram")
    macd_histogram_prev = indicators.get("macd_histogram_prev")

    # Regimhantering sker ENBART via get_effective_buy_threshold().
    # Score representerar individuell aktiekvalitet — ren teknisk/fundamental
    # signal utan marknadsbias, så att vi kan jämföra aktier rättvist.

    # RSI < 35 → +25p om pris över MA200 (upptrend), annars +10p
    if rsi is not None and rsi < 35:
        in_uptrend = ma200 and current_price and current_price > ma200
        if in_uptrend:
            score += 25
            reasons.append(f"RSI: {rsi:.1f} (översålt i upptrend)")
        else:
            score += 10
            reasons.append(f"RSI: {rsi:.1f} (översålt men under MA200 — svagare signal)")

    # MACD bullish crossover + positivt histogram → +20p
    if None not in (macd, macd_signal, macd_prev, macd_signal_prev):
        if macd_prev < macd_signal_prev and macd > macd_signal:
            if macd_histogram is not None and macd_histogram > 0:
                score += 20
                reasons.append("MACD crossover uppåt (histogram positivt)")
            else:
                score += 10
                reasons.append("MACD crossover uppåt (histogram ej bekräftat)")

    # MACD momentum: histogram positivt OCH stigande → +10p
    # Fångar pågående bullish momentum EFTER crossover (varar 5–10 dagar),
    # inte bara den enstaka crossover-dagen.
    if (macd_histogram is not None and macd_histogram_prev is not None
            and macd_histogram > 0 and macd_histogram > macd_histogram_prev):
        score += 10
        reasons.append(f"MACD momentum: histogram stigande ({macd_histogram:.4f})")

    # MA50-studs: pris precis OVANFÖR MA50 (0–2%) → +20p
    # Pris precis UNDER MA50 (-2%–0) → -10p (nedbrott, ej studs)
    if current_price and ma50:
        pct_from_ma50 = (current_price - ma50) / ma50
        if 0 <= pct_from_ma50 < 0.02:
            score += 20
            reasons.append(f"Pris studsar på MA50 ovanifrån ({ma50:.2f})")
        elif -0.02 <= pct_from_ma50 < 0:
            score -= 10
            reasons.append(f"Pris precis under MA50 ({ma50:.2f}) — nedbrott -10p")

    # MA200-studs: pris precis OVANFÖR MA200 (0–2%) → +20p
    # Pris precis UNDER MA200 (-2%–0) → -15p
    if current_price and ma200:
        pct_from_ma200 = (current_price - ma200) / ma200
        if 0 <= pct_from_ma200 < 0.02:
            score += 20
            reasons.append(f"Pris studsar på MA200 ovanifrån ({ma200:.2f})")
        elif -0.02 <= pct_from_ma200 < 0:
            score -= 15
            reasons.append(f"Pris precis under MA200 ({ma200:.2f}) — varning -15p")

    # Volymbekräftelse — direction-adjusted
    # >150% på uppgångsdag: starkt bekräftelsesignal (+15p)
    # >120% på uppgångsdag: normal institutionell köpaktivitet (+8p)
    # Hög volym på nedgångsdag: säljpress, ingen köppoäng
    if daily_return is not None and daily_return > 0:
        if volume_ratio >= 1.5:
            score += 15
            reasons.append(f"Volym: +{(volume_ratio - 1) * 100:.0f}% vs snitt (stark uppgång)")
        elif volume_ratio >= 1.2:
            score += 8
            reasons.append(f"Volym: +{(volume_ratio - 1) * 100:.0f}% vs snitt (uppgång)")
    elif daily_return is not None and daily_return < 0:
        pass  # Hög volym på nedgång — säljpress, ej köpsignal
    elif volume_ratio >= 1.5:
        score += 5
        reasons.append(f"Volym: +{(volume_ratio - 1) * 100:.0f}% vs snitt (riktning oklar)")

    # Gemini positive sentiment → +15p
    if news_sentiment and news_sentiment.get("sentiment") == "POSITIVE":
        score += 15
        reasons.append(f"Gemini: Positivt sentiment ({news_sentiment.get('reason', '')})")

    # Insider buy >500k SEK → +10p
    if insider_trades and has_significant_insider_buy(insider_trades):
        score += 10
        reasons.append("Insiderköp >500 000 kr (FI)")

    # Bollinger lower band touch (within 1%) → +10p, kräver även RSI < 45
    if current_price and bb_lower and current_price <= bb_lower * 1.01:
        if rsi is not None and rsi < 45:
            score += 10
            reasons.append(f"Bollinger: Touch undre band ({bb_lower:.2f}, bekräftat av RSI)")

    # ── BULL-MARKET SIGNALS ────────────────────────────────────────────

    # Pullback i upptrend: RSI 35–55, pris > MA50 > MA200 → +15p
    # Fångar den vanligaste lönsamma swingtraden i BULL-marknad:
    # moderat pullback i stark trend. Bandet 35–55 täcker:
    #  - RSI 35–40: gränslandet mot översålt (gapet mot RSI<35-signalen)
    #  - RSI 40–50: klassisk pullback
    #  - RSI 50–55: mild konsolidering i stark trend
    # Kräver att pris > MA50 > MA200 — bekräftar etablerad upptrend.
    if (rsi is not None and 35 <= rsi <= 55
            and current_price and ma50 and ma200
            and current_price > ma50 and ma50 > ma200):
        score += 15
        reasons.append(f"Pullback i upptrend: RSI {rsi:.0f}, pris > MA50 > MA200")

    # Trendstyrka: MA50 > MA200 (Golden Cross) → +10p
    # Bekräftar att aktien är i en etablerad upptrend.
    if ma50 and ma200 and ma50 > ma200:
        score += 10
        reasons.append("Trendstyrka: MA50 > MA200 (Golden Cross)")

    # Rapport within 48h → -25p hard penalty
    if has_open_report_soon:
        score -= 25
        reasons.append("⚠️ Rapport inom 48h (penalty -25p)")

    # Relative strength vs OMXS30 (20-day)
    if relative_strength is not None:
        if relative_strength >= 1.15:
            score += 20
            reasons.append(f"RS vs OMXS30: +{(relative_strength - 1) * 100:.0f}% (stark outperformance)")
        elif relative_strength >= 1.05:
            score += 10
            reasons.append(f"RS vs OMXS30: +{(relative_strength - 1) * 100:.0f}% (outperformance)")
        elif relative_strength < 0.90:
            score -= 10
            reasons.append(f"RS vs OMXS30: {(relative_strength - 1) * 100:.0f}% (underperformance, -10p)")

    return score, reasons


def score_sell_signal(
    ticker: str,
    indicators: dict,
    position: dict,
    news_sentiment: Optional[dict] = None,
    relative_strength: Optional[float] = None,
) -> tuple[int, list[str]]:
    """
    Calculate sell signal score based on technical analysis and sentiment.
    Returns (score, reasons). Signal fires if score >= sell_threshold.
    No automatic stop-loss — the agent only recommends, the user decides.
    """
    score = 0
    reasons = []

    rsi = indicators.get("rsi")
    current_price = indicators.get("current_price")
    ma50 = indicators.get("ma50")
    macd = indicators.get("macd")
    macd_signal = indicators.get("macd_signal")
    macd_prev = indicators.get("macd_prev")
    macd_signal_prev = indicators.get("macd_signal_prev")

    buy_price = position.get("price", 0)

    # RSI > 70 → +25p
    if rsi is not None and rsi > 70:
        score += 25
        reasons.append(f"RSI: {rsi:.1f} (överköpt)")

    # MACD bearish crossover → +20p
    if None not in (macd, macd_signal, macd_prev, macd_signal_prev):
        if macd_prev > macd_signal_prev and macd < macd_signal:
            score += 20
            reasons.append("MACD crossover nedåt")

    # ATR-relativ P&L-bedömning — anpassar sig till aktiens volatilitet
    atr = indicators.get("atr", 0)
    if current_price and buy_price > 0:
        pnl_pct = ((current_price - buy_price) / buy_price) * 100
        # Använd ATR relativt köpkurs som volatilitetsreferens
        atr_pct = (atr / buy_price * 100) if (atr and buy_price > 0) else 3.0

        # Förlust > 2× ATR → stark säljsignal (anpassad till volatilitet)
        if pnl_pct < -(atr_pct * 2.0):
            score += 25
            reasons.append(f"Förlust {pnl_pct:.1f}% > 2× ATR ({atr_pct:.1f}%) — allvarlig")
        elif pnl_pct < -(atr_pct * 1.5):
            score += 15
            reasons.append(f"Förlust {pnl_pct:.1f}% > 1.5× ATR ({atr_pct:.1f}%)")
        # Vinst > 4× ATR → överväg realisering
        elif pnl_pct > atr_pct * 4.0:
            score += 15
            reasons.append(f"Vinst {pnl_pct:.1f}% > 4× ATR — överväg att ta hem")

    # Gemini negative sentiment → +15p
    if news_sentiment and news_sentiment.get("sentiment") == "NEGATIVE":
        score += 15
        reasons.append(f"Gemini: Negativt sentiment ({news_sentiment.get('reason', '')})")

    # Close below MA50 → +20p
    if current_price and ma50 and current_price < ma50:
        score += 20
        reasons.append(f"Pris under MA50 ({ma50:.2f})")

    # Relative strength vs OMXS30 — persistent underperformance → sell
    if relative_strength is not None and relative_strength < 0.90:
        score += 15
        reasons.append(f"RS vs OMXS30: {(relative_strength - 1) * 100:.0f}% (underperformance)")

    return score, reasons


def calculate_position_size(
    confidence_pct: float,
    atr_pct: float = 0.0,
    total_equity: float = 0.0,
    cash_buffer: float = 0.0,
    max_positions: int = 0,
) -> float:
    """Dynamisk position sizing baserad på totalt kapital och volatilitet.

    Formel: min(MAX_POSITION_VALUE, (TOTAL_EQUITY - CASH_BUFFER) / N)
    Sedan skalas ned med confidence och volatilitet.

    Args:
        confidence_pct: Signalens styrka (0–100).
        atr_pct: ATR / pris (0.0–1.0).
        total_equity: Portföljens totala värde i SEK (0 = använd fast max).
        cash_buffer: Likviditetsbuffert att reservera (SEK).
        max_positions: Max antal simultana positioner.
    """
    settings_max = _settings.get_float("max_position_size")
    if max_positions <= 0:
        max_positions = _settings.get_int("max_positions")
    if cash_buffer <= 0:
        cash_buffer = _settings.get_float("cash_buffer") if _settings.get("cash_buffer") else 2000.0

    # Dynamiskt positionstak: (equity - buffert) / N, begränsat av settings-max
    if total_equity > 0:
        dynamic_max = max(0, (total_equity - cash_buffer)) / max(1, max_positions)
        max_size = min(settings_max, dynamic_max) if settings_max > 0 else dynamic_max
    else:
        max_size = settings_max

    max_size = max(0.0, max_size)

    # Confidence scaling
    if confidence_pct >= 80:
        size = max_size
    elif confidence_pct >= 70:
        size = max_size * 0.80
    elif confidence_pct >= 60:
        size = max_size * 0.65
    else:
        size = max_size * 0.40

    # Volatility adjustment — reduce size for highly volatile stocks
    if atr_pct > 0.06:
        size *= 0.50
    elif atr_pct > 0.04:
        size *= 0.70

    return round(max(0.0, size), 2)


def get_effective_buy_threshold(
    base_threshold: int,
    market_regime: str = "NEUTRAL",
    avg_turnover: Optional[float] = None,
) -> int:
    """Adaptive buy threshold based on market regime and liquidity segment.

    Higher threshold in weak market and highly liquid names to reduce overtrading.
    """
    threshold = int(base_threshold)

    # Regime adjustment — enda stället regim påverkar köpbeslut.
    # Score representerar aktiens individuella kvalitet (regim-agnostisk).
    # Tröskeln styr hur bra setupen behöver vara givet marknadsklimatet.
    if market_regime == "BEAR":
        threshold += 10  # Var +12 — kräv stark setup men stäng inte av helt
    elif market_regime == "NEUTRAL":
        threshold += 2   # Var +4 — sidledes marknad, individuella aktier kan fortfarande ha bra setups
    elif market_regime == "BULL_EARLY":
        threshold -= 3
    elif market_regime == "BULL":
        threshold -= 5

    # Liquidity segment adjustment — only penalize very illiquid stocks
    # Large/mid cap stocks should NOT be penalized for high liquidity;
    # that punishes exactly the stocks we want to buy.
    if avg_turnover is not None:
        if avg_turnover < 15_000_000:
            threshold += 3

    # Safety clamps — allow lower threshold in strong bull markets
    # (system has hard position limits + manual confirmation as safeguards)
    return max(50, min(85, threshold))


def get_effective_sell_threshold(base_threshold: int, market_regime: str = "NEUTRAL") -> int:
    """Adaptive sell threshold.

    In BEAR market we exit earlier; in BULL we require a slightly stronger sell signal.
    """
    threshold = int(base_threshold)
    if market_regime == "BEAR":
        threshold -= 10
    elif market_regime == "NEUTRAL":
        threshold -= 2
    elif market_regime == "BULL":
        threshold += 3
    return max(40, min(75, threshold))


def calculate_opportunity_score(
    buy_score: float,
    relative_strength: Optional[float] = None,
    atr_pct: float = 0.0,
    volume_ratio: float = 1.0,
    market_regime: str = "NEUTRAL",
) -> float:
    """Risk-adjusted opportunity score used for ranking/rotation.

    Starts from buy_score, then rewards strength/liquidity confirmation,
    and penalizes high volatility and weak market regimes.
    """
    score = float(buy_score)

    # Relative strength quality
    if relative_strength is not None:
        if relative_strength >= 1.15:
            score += 8
        elif relative_strength >= 1.05:
            score += 4
        elif relative_strength < 0.95:
            score -= 6

    # Volume confirmation
    if volume_ratio >= 1.5:
        score += 3
    elif volume_ratio < 0.8:
        score -= 2

    # Volatility penalty
    if atr_pct > 0.06:
        score -= 8
    elif atr_pct > 0.04:
        score -= 4

    # Regime context
    if market_regime == "BEAR":
        score -= 5
    elif market_regime == "BULL":
        score += 2

    return round(score, 1)
