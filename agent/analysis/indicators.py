from typing import Optional
import pandas as pd
import pandas_ta as pta


def calculate_relative_strength(
    stock_df: pd.DataFrame,
    index_df: pd.DataFrame,
    period: int = 20,
) -> Optional[float]:
    """
    Calculate relative strength of stock vs OMXS30 over last `period` trading days.
    Returns (1+stock_return) / (1+index_return).
    > 1.0 = outperforming the index, < 1.0 = underperforming.
    Returns None if data is insufficient.
    """
    if stock_df is None or index_df is None:
        return None
    if stock_df.empty or index_df.empty:
        return None
    if len(stock_df) < period or len(index_df) < period:
        return None

    stock_return = (stock_df["close"].iloc[-1] / stock_df["close"].iloc[-period]) - 1
    index_return = (index_df["close"].iloc[-1] / index_df["close"].iloc[-period]) - 1

    denominator = 1 + index_return
    if denominator == 0:
        return None

    rs = (1 + stock_return) / denominator
    return round(float(rs), 4)


def calculate_indicators(df: pd.DataFrame) -> dict:
    """Calculate all technical indicators from an OHLCV DataFrame."""
    if df.empty or len(df) < 20:
        return {}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # RSI (14)
    rsi_s = pta.rsi(close, length=14)

    # MACD (12, 26, 9)
    macd_df = pta.macd(close, fast=12, slow=26, signal=9)

    # Moving averages
    ma20_s = pta.sma(close, length=20)
    ma50_s = pta.sma(close, length=50) if len(df) >= 50 else None
    ma200_s = pta.sma(close, length=200) if len(df) >= 200 else None
    ema20_s = pta.ema(close, length=20)

    # Bollinger Bands (20, 2)
    bb_df = pta.bbands(close, length=20, std=2)

    # ATR (14)
    atr_s = pta.atr(high, low, close, length=14)

    # Volume ratio vs 20-day average
    vol_avg = volume.rolling(20).mean().iloc[-1]
    current_vol = volume.iloc[-1]
    volume_ratio = float(current_vol / vol_avg) if vol_avg and vol_avg > 0 else 1.0

    def last(s):
        return round(float(s.iloc[-1]), 4) if s is not None and not s.empty else None

    def prev(s):
        return round(float(s.iloc[-2]), 4) if s is not None and len(s) > 2 else None

    macd_col = [c for c in macd_df.columns if c.startswith("MACD_")][0] if macd_df is not None else None
    sig_col  = [c for c in macd_df.columns if c.startswith("MACDs_")][0] if macd_df is not None else None
    hist_col = [c for c in macd_df.columns if c.startswith("MACDh_")][0] if macd_df is not None else None

    bb_upper = [c for c in bb_df.columns if "BBU" in c][0] if bb_df is not None else None
    bb_lower = [c for c in bb_df.columns if "BBL" in c][0] if bb_df is not None else None
    bb_mid   = [c for c in bb_df.columns if "BBM" in c][0] if bb_df is not None else None

    return {
        "rsi":              last(rsi_s),
        "macd":             last(macd_df[macd_col]) if macd_col else None,
        "macd_signal":      last(macd_df[sig_col])  if sig_col  else None,
        "macd_histogram":   last(macd_df[hist_col]) if hist_col else None,
        "macd_prev":        prev(macd_df[macd_col]) if macd_col else None,
        "macd_signal_prev": prev(macd_df[sig_col])  if sig_col  else None,
        "ma20":             last(ma20_s),
        "ma50":             last(ma50_s),
        "ma200":            last(ma200_s),
        "ema20":            last(ema20_s),
        "bollinger_upper":  last(bb_df[bb_upper]) if bb_upper else None,
        "bollinger_lower":  last(bb_df[bb_lower]) if bb_lower else None,
        "bollinger_mid":    last(bb_df[bb_mid])   if bb_mid   else None,
        "atr":              last(atr_s),
        "volume_ratio":     round(volume_ratio, 2),
        "current_price":    round(float(close.iloc[-1]), 2),
    }
