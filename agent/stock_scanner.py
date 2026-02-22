"""
Weekly stock scanner.
Scans a universe of Swedish large/mid cap stocks, scores them on volatility,
volume and trend quality, then suggests replacements for the current watchlist.
"""
import logging
from datetime import datetime, timezone
from data.yahoo_client import get_price_history
from analysis.indicators import calculate_indicators
from db.supabase_client import get_client, get_watchlist
from notifications import ntfy

logger = logging.getLogger(__name__)

# Broad universe of Swedish stocks to evaluate
STOCK_UNIVERSE = {
    # Large cap
    "ERIC B":   "Ericsson B",
    "VOLV B":   "Volvo B",
    "INVE B":   "Investor B",
    "SEB A":    "SEB A",
    "SHB A":    "Handelsbanken A",
    "SWED A":   "Swedbank A",
    "AZN":      "AstraZeneca",
    "ATCO A":   "Atlas Copco A",
    "ABB":      "ABB",
    "ALFA":     "Alfa Laval",
    "SAND":     "Sandvik",
    "SKF B":    "SKF B",
    "HEXA B":   "Hexagon B",
    "NIBE B":   "NIBE B",
    "BOL":      "Boliden",
    "TELE2 B":  "Tele2 B",
    "TELIA":    "Telia",
    "HM B":     "H&M B",
    "ASSA B":   "Assa Abloy B",
    "ESSITY B": "Essity B",
    "LUND B":   "Lundbergföretagen B",
    "FABG":     "Fabege",
    # Already in watchlist
    "EVO":      "Evolution",
    "SINCH":    "Sinch",
    "EMBRAC B": "Embracer Group B",
    "HTRO":     "Hexatronic",
    "SSAB B":   "SSAB B",
    # Mid cap candidates
    "BETS B":   "Betsson B",
    "CINT":     "Cint Group",
    "LATO B":   "Latour B",
    "NOLA B":   "Nolato B",
    "PEAB B":   "Peab B",
    "SWMA":     "Swedish Match",
    "TOBS B":   "Tobii B",
    "XVIVO":    "XVIVO Perfusion",
}

YAHOO_SYMBOLS = {
    "ERIC B":   "ERIC-B.ST",
    "VOLV B":   "VOLV-B.ST",
    "INVE B":   "INVE-B.ST",
    "SEB A":    "SEB-A.ST",
    "SHB A":    "SHB-A.ST",
    "SWED A":   "SWED-A.ST",
    "AZN":      "AZN.ST",
    "ATCO A":   "ATCO-A.ST",
    "ABB":      "ABB.ST",
    "ALFA":     "ALFA.ST",
    "SAND":     "SAND.ST",
    "SKF B":    "SKF-B.ST",
    "HEXA B":   "HEXA-B.ST",
    "NIBE B":   "NIBE-B.ST",
    "BOL":      "BOL.ST",
    "TELE2 B":  "TELE2-B.ST",
    "TELIA":    "TELIA.ST",
    "HM B":     "HM-B.ST",
    "ASSA B":   "ASSA-B.ST",
    "ESSITY B": "ESSITY-B.ST",
    "LUND B":   "LUND-B.ST",
    "FABG":     "FABG.ST",
    "EVO":      "EVO.ST",
    "SINCH":    "SINCH.ST",
    "EMBRAC B": "EMBRAC-B.ST",
    "HTRO":     "HTRO.ST",
    "SSAB B":   "SSAB-B.ST",
    "BETS B":   "BETS-B.ST",
    "CINT":     "CINT.ST",
    "LATO B":   "LATO-B.ST",
    "NOLA B":   "NOLA-B.ST",
    "PEAB B":   "PEAB-B.ST",
    "SWMA":     "SWMA.ST",
    "TOBS B":   "TOBS-B.ST",
    "XVIVO":    "XVIVO.ST",
}


def score_candidate(ticker: str, indicators: dict, df) -> tuple[float, list[str]]:
    """
    Score a stock as a trading candidate (0–100).
    Higher = better trading opportunities.
    """
    score = 0.0
    reasons = []

    # 1. Daily volatility (ATR / price) — want 2–8%
    price = indicators.get("current_price", 0)
    atr = indicators.get("atr", 0)
    if price and atr:
        daily_vol_pct = (atr / price) * 100
        if 2 <= daily_vol_pct <= 8:
            score += 30
            reasons.append(f"Bra volatilitet: {daily_vol_pct:.1f}%/dag")
        elif daily_vol_pct > 8:
            score += 15
            reasons.append(f"Hög volatilitet: {daily_vol_pct:.1f}%/dag")
        else:
            reasons.append(f"Låg volatilitet: {daily_vol_pct:.1f}%/dag")

    # 2. Volume ratio — want > 1.0 (active trading)
    vol_ratio = indicators.get("volume_ratio", 0)
    if vol_ratio >= 1.5:
        score += 25
        reasons.append(f"Hög volym: {vol_ratio:.1f}× snitt")
    elif vol_ratio >= 1.0:
        score += 15
        reasons.append(f"Normal volym: {vol_ratio:.1f}× snitt")

    # 3. Trend quality — price vs MA50/MA200
    ma50 = indicators.get("ma50")
    ma200 = indicators.get("ma200")
    if price and ma50 and price > ma50:
        score += 20
        reasons.append("Pris över MA50 (upptrend)")
    if price and ma200 and price > ma200:
        score += 15
        reasons.append("Pris över MA200 (långsiktig upptrend)")

    # 4. RSI in tradeable range (30–70)
    rsi = indicators.get("rsi")
    if rsi and 30 <= rsi <= 70:
        score += 10
        reasons.append(f"RSI i handelsbart läge: {rsi:.0f}")

    return round(score, 1), reasons


async def run_scan():
    """Main scan function — called weekly by scheduler."""
    logger.info("Startar veckovis aktiesskanning...")
    db = get_client()

    # Get current watchlist tickers
    watchlist = await get_watchlist()
    current_tickers = {s["ticker"] for s in watchlist}

    results = []

    for ticker, name in STOCK_UNIVERSE.items():
        yahoo_symbol = YAHOO_SYMBOLS.get(ticker)
        if not yahoo_symbol:
            continue
        try:
            df = await get_price_history(ticker, days=60)
            if df.empty or len(df) < 20:
                continue
            indicators = calculate_indicators(df)
            if not indicators:
                continue
            score, reasons = score_candidate(ticker, indicators, df)
            results.append({
                "ticker": ticker,
                "name": name,
                "score": score,
                "reasons": reasons,
                "indicators": indicators,
                "in_watchlist": ticker in current_tickers,
            })
            logger.info(f"  {ticker}: {score:.0f}p")
        except Exception as e:
            logger.warning(f"  {ticker}: fel – {e}")

    if not results:
        logger.warning("Skanning returnerade inga resultat.")
        return

    # Sort by score
    results.sort(key=lambda x: x["score"], reverse=True)

    # Top candidates NOT in watchlist
    top_new = [r for r in results if not r["in_watchlist"]][:5]

    # Weakest in current watchlist
    current_scored = [r for r in results if r["in_watchlist"]]
    current_scored.sort(key=lambda x: x["score"])
    weakest = current_scored[:2] if current_scored else []

    suggestions = []
    for candidate in top_new:
        for weak in weakest:
            if candidate["score"] > weak["score"] + 10:
                suggestion = {
                    "suggested_ticker": candidate["ticker"],
                    "suggested_name": candidate["name"],
                    "suggested_score": candidate["score"],
                    "suggested_reasons": candidate["reasons"],
                    "replace_ticker": weak["ticker"],
                    "replace_name": weak["name"],
                    "replace_score": weak["score"],
                    "status": "pending",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                db.table("stock_suggestions").insert(suggestion).execute()
                suggestions.append(suggestion)
                logger.info(
                    f"Förslag: byt {weak['ticker']} ({weak['score']:.0f}p) "
                    f"mot {candidate['ticker']} ({candidate['score']:.0f}p)"
                )

    # Send ntfy summary
    if suggestions:
        lines = "\n".join(
            f"  ↕ Byt {s['replace_ticker']} ({s['replace_score']:.0f}p) → "
            f"{s['suggested_ticker']} ({s['suggested_score']:.0f}p)"
            for s in suggestions[:3]
        )
        await ntfy._send(
            f"📊 Veckoanalys klar – {len(suggestions)} förslag:\n{lines}\n\nGodkänn i dashboarden.",
            title="Watchlist-förslag",
            priority="default",
            tags=["bar_chart"],
        )
    else:
        logger.info("Inga bytesförslag – nuvarande watchlist är fortsatt optimal.")

    logger.info(f"Skanning klar. {len(results)} aktier analyserade, {len(suggestions)} förslag.")
