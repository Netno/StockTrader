from typing import Optional
from config import TICKERS
from data.insider_fetcher import has_significant_insider_buy
import settings as _settings


def score_buy_signal(
    ticker: str,
    indicators: dict,
    news_sentiment: Optional[dict] = None,
    insider_trades: Optional[list] = None,
    has_open_report_soon: bool = False,
    relative_strength: Optional[float] = None,
) -> tuple[int, list[str]]:
    """
    Calculate buy signal score.
    Returns (score, reasons). Signal fires if score >= 60.
    """
    score = 0
    reasons = []

    rsi = indicators.get("rsi")
    volume_ratio = indicators.get("volume_ratio", 1.0)
    current_price = indicators.get("current_price")
    ma50 = indicators.get("ma50")
    ma200 = indicators.get("ma200")
    bb_lower = indicators.get("bollinger_lower")
    macd = indicators.get("macd")
    macd_signal = indicators.get("macd_signal")
    macd_prev = indicators.get("macd_prev")
    macd_signal_prev = indicators.get("macd_signal_prev")

    # RSI < 35 → +25p
    if rsi is not None and rsi < 35:
        score += 25
        reasons.append(f"RSI: {rsi:.1f} (översålt)")

    # MACD bullish crossover → +20p
    if None not in (macd, macd_signal, macd_prev, macd_signal_prev):
        if macd_prev < macd_signal_prev and macd > macd_signal:
            score += 20
            reasons.append("MACD crossover uppåt")

    # Price near MA50 (within 2%) → +20p
    if current_price and ma50:
        if abs(current_price - ma50) / ma50 < 0.02:
            score += 20
            reasons.append(f"Pris studsar på MA50 ({ma50:.2f})")

    # Price near MA200 (within 2%) → +20p
    if current_price and ma200:
        if abs(current_price - ma200) / ma200 < 0.02:
            score += 20
            reasons.append(f"Pris studsar på MA200 ({ma200:.2f})")

    # Volume > 150% of 20-day avg → +15p
    if volume_ratio >= 1.5:
        score += 15
        reasons.append(f"Volym: +{(volume_ratio - 1) * 100:.0f}% vs snitt")

    # Gemini positive sentiment → +15p
    if news_sentiment and news_sentiment.get("sentiment") == "POSITIVE":
        score += 15
        reasons.append(f"Gemini: Positivt sentiment ({news_sentiment.get('reason', '')})")

    # Insider buy >500k SEK → +10p
    if insider_trades and has_significant_insider_buy(insider_trades):
        score += 10
        reasons.append("Insiderköp >500 000 kr (FI)")

    # Bollinger lower band touch (within 1%) → +10p
    if current_price and bb_lower:
        if current_price <= bb_lower * 1.01:
            score += 10
            reasons.append(f"Bollinger: Touch undre band ({bb_lower:.2f})")

    # Rapport within 48h → -20p penalty
    if has_open_report_soon:
        score -= 20
        reasons.append("⚠️ Rapport inom 48h (penalty -20p)")

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
    Calculate sell signal score.
    Returns (score, reasons). Signal fires if score >= 60.
    Stop-loss always triggers a sell regardless of score.
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

    stop_loss = position.get("stop_loss_price")
    take_profit = position.get("take_profit_price")

    # RSI > 70 → +25p
    if rsi is not None and rsi > 70:
        score += 25
        reasons.append(f"RSI: {rsi:.1f} (överköpt)")

    # MACD bearish crossover → +20p
    if None not in (macd, macd_signal, macd_prev, macd_signal_prev):
        if macd_prev > macd_signal_prev and macd < macd_signal:
            score += 20
            reasons.append("MACD crossover nedåt")

    # Take-profit reached → +30p
    if current_price and take_profit and current_price >= take_profit:
        score += 30
        reasons.append(f"Take-profit nådd ({take_profit:.2f} kr)")

    # Stop-loss reached → +50p (always triggers sell)
    if current_price and stop_loss and current_price <= stop_loss:
        score += 50
        reasons.append(f"Stop-loss nådd ({stop_loss:.2f} kr) ⛔")

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


def calculate_position_size(confidence_pct: float) -> float:
    """Return position size in SEK based on confidence level."""
    max_size = _settings.get_float("max_position_size")
    if confidence_pct >= 75:
        return max_size          # full storlek
    elif confidence_pct >= 60:
        return max_size * 0.72   # ~72%
    else:
        return max_size * 0.40   # ~40%


def calculate_stop_take(ticker: str, price: float, indicators: dict) -> tuple[float, float]:
    """Calculate ATR-based stop-loss and take-profit prices."""
    config = TICKERS.get(ticker, {})
    atr = indicators.get("atr") or 0
    atr_multiplier = config.get("atr_multiplier", 1.3)
    stop_pct = config.get("stop_loss_pct", 0.05)
    take_pct = config.get("take_profit_pct", 0.10)

    if atr > 0:
        stop_loss = price - (atr * atr_multiplier)
    else:
        stop_loss = price * (1 - stop_pct)

    take_profit = price * (1 + take_pct)

    return round(stop_loss, 2), round(take_profit, 2)
