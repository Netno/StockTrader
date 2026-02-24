from typing import Optional
from data.insider_fetcher import has_significant_insider_buy
import settings as _settings


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

    # REGIMFILTER: penalisera köp i sidlesgående/fallande marknad
    if market_regime == "BEAR":
        score -= 30
        reasons.append("⛔ Marknadsregim: BEAR (OMXS30 under MA200) -30p")
    elif market_regime == "NEUTRAL":
        score -= 10
        reasons.append("Marknadsregim: NEUTRAL -10p")
    elif market_regime in ("BULL", "BULL_EARLY"):
        pass  # Ingen penalty i upptrend

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

    # Volume > 150% of 20-day avg — direction-adjusted
    # Hög volym på uppgångsdag = starkt bekräftelsesignal (+15p)
    # Hög volym utan riktning = svagare (+8p)
    # Hög volym på nedgångsdag = säljpress, ej köpsignal (0p)
    if volume_ratio >= 1.5:
        if daily_return is not None and daily_return > 0:
            score += 15
            reasons.append(f"Volym: +{(volume_ratio - 1) * 100:.0f}% vs snitt (prisstigande dag)")
        elif daily_return is not None and daily_return < 0:
            pass  # Hög volym på nedgång — säljpress, ej köpsignal
        else:
            score += 8
            reasons.append(f"Volym: +{(volume_ratio - 1) * 100:.0f}% vs snitt")

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

    # P&L-aware sell pressure — replaces fixed SL/TP triggers
    # Large unrealized loss: technical signs + big loss = strong sell signal
    if current_price and buy_price > 0:
        pnl_pct = ((current_price - buy_price) / buy_price) * 100
        if pnl_pct < -10:
            score += 25
            reasons.append(f"Stor orealiserad förlust ({pnl_pct:.1f}%)")
        elif pnl_pct < -6:
            score += 15
            reasons.append(f"Orealiserad förlust ({pnl_pct:.1f}%)")
        # Large unrealized gain: consider taking profit
        elif pnl_pct > 15:
            score += 15
            reasons.append(f"Stor orealiserad vinst ({pnl_pct:.1f}%) — överväg att ta hem")

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


def calculate_position_size(confidence_pct: float, atr_pct: float = 0.0) -> float:
    """Return position size in SEK based on confidence and volatility.
    
    Higher confidence = larger position.
    Higher volatility = smaller position (risk-adjusted).
    """
    max_size = _settings.get_float("max_position_size")

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
    # ATR/price > 4% = high vol → scale down to 70%
    # ATR/price > 6% = very high → scale down to 50%
    if atr_pct > 0.06:
        size *= 0.50
    elif atr_pct > 0.04:
        size *= 0.70

    return round(size, 2)
