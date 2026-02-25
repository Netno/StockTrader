"""
Stock scanner: discovery + rotation.

Discovery mode (positions < MAX_POSITIONS):
  Scans the full universe every morning to find the best trading candidates.
  Replaces the watchlist with top ~15 stocks so the trading loop has a broad
  pool to generate buy signals from.

Rotation mode (positions >= MAX_POSITIONS):
  After market close, scans for stronger candidates and rotates out the
  weakest watchlist stock if the improvement is significant.
"""
import asyncio
import logging
from datetime import datetime, timezone
from data.yahoo_client import get_price_history, get_index_history
from analysis.indicators import calculate_indicators, calculate_relative_strength, calculate_market_regime
from analysis.decision_engine import score_buy_signal
from db.supabase_client import get_client, get_watchlist, bulk_update_watchlist
from notifications import ntfy

logger = logging.getLogger(__name__)

# Broad universe of Swedish stocks to evaluate.
# Covers all Nasdaq Stockholm Large Cap + Mid Cap (124 aktier).
# The liquidity filter (MIN_DAILY_TURNOVER_SEK) automatically removes
# any stock that doesn't meet the turnover threshold.
# Unified stock data — single source of truth.
# Each entry: (ticker, display_name, avanza_url, yahoo_symbol)
# Backward-compatible dicts (STOCK_UNIVERSE, AVANZA_URLS, YAHOO_SYMBOLS)
# are derived at the bottom — never define them separately.
_STOCK_DATA: list[tuple[str, str, str, str]] = [
    # ── Large Cap ──────────────────────────────────────────────
    ("AAK", "AAK", "https://www.avanza.se/aktier/om-aktien.html/26268/aak", "AAK.ST"),
    ("ABB", "ABB", "https://www.avanza.se/aktier/om-aktien.html/5447/abb", "ABB.ST"),
    ("AFRY", "AFRY", "https://www.avanza.se/aktier/om-aktien.html/5765/afry", "AFRY.ST"),
    ("ALFA", "Alfa Laval", "https://www.avanza.se/aktier/om-aktien.html/5580/alfa-laval", "ALFA.ST"),
    ("ALIV SDB", "Autoliv SDB", "https://www.avanza.se/aktier/om-aktien.html/5236/autoliv-sdb", "ALIV-SDB.ST"),
    ("ASSA B", "Assa Abloy B", "https://www.avanza.se/aktier/om-aktien.html/5271/assa-abloy-b", "ASSA-B.ST"),
    ("ATCO A", "Atlas Copco A", "https://www.avanza.se/aktier/om-aktien.html/5234/atlas-copco-a", "ATCO-A.ST"),
    ("ATCO B", "Atlas Copco B", "https://www.avanza.se/aktier/om-aktien.html/5235/atlas-copco-b", "ATCO-B.ST"),
    ("AZN", "AstraZeneca", "https://www.avanza.se/aktier/om-aktien.html/5361/astrazeneca", "AZN.ST"),
    ("AXFO", "Axfood", "https://www.avanza.se/aktier/om-aktien.html/5465/axfood", "AXFO.ST"),
    ("BALD B", "Balder B", "https://www.avanza.se/aktier/om-aktien.html/5519/balder-b", "BALD-B.ST"),
    ("BILL", "Billerud", "https://www.avanza.se/aktier/om-aktien.html/5253/billerud", "BILL.ST"),
    ("BOL", "Boliden", "https://www.avanza.se/aktier/om-aktien.html/5564/boliden", "BOL.ST"),
    ("CAST", "Castellum", "https://www.avanza.se/aktier/om-aktien.html/5353/castellum", "CAST.ST"),
    ("DOME", "Dometic", "https://www.avanza.se/aktier/om-aktien.html/549782/dometic-group", "DOME.ST"),
    ("EKTA B", "Elekta B", "https://www.avanza.se/aktier/om-aktien.html/5280/elekta-b", "EKTA-B.ST"),
    ("ELUX B", "Electrolux B", "https://www.avanza.se/aktier/om-aktien.html/5238/electrolux-b", "ELUX-B.ST"),
    ("EMBRAC B", "Embracer Group B", "https://www.avanza.se/aktier/om-aktien.html/707695/embracer-group-b", "EMBRAC-B.ST"),
    ("EPRO A", "Epiroc A", "https://www.avanza.se/aktier/om-aktien.html/831540/epiroc-a", "EPRO-A.ST"),
    ("EPRO B", "Epiroc B", "https://www.avanza.se/aktier/om-aktien.html/831541/epiroc-b", "EPRO-B.ST"),
    ("EQT", "EQT", "https://www.avanza.se/aktier/om-aktien.html/956272/eqt", "EQT.ST"),
    ("ERIC B", "Ericsson B", "https://www.avanza.se/aktier/om-aktien.html/5240/ericsson-b", "ERIC-B.ST"),
    ("ESSITY B", "Essity B", "https://www.avanza.se/aktier/om-aktien.html/764241/essity-b", "ESSITY-B.ST"),
    ("EVO", "Evolution", "https://www.avanza.se/aktier/om-aktien.html/549768/evolution", "EVO.ST"),
    ("GETI B", "Getinge B", "https://www.avanza.se/aktier/om-aktien.html/5282/getinge-b", "GETI-B.ST"),
    ("HEXA B", "Hexagon B", "https://www.avanza.se/aktier/om-aktien.html/5286/hexagon-b", "HEXA-B.ST"),
    ("HM B", "H&M B", "https://www.avanza.se/aktier/om-aktien.html/5364/h-m-b", "HM-B.ST"),
    ("HOLMEN B", "Holmen B", "https://www.avanza.se/aktier/om-aktien.html/5244/holmen-b", "HOLM-B.ST"),
    ("HPOL B", "Hexpol B", "https://www.avanza.se/aktier/om-aktien.html/39498/hexpol-b", "HPOL-B.ST"),
    ("HUSQ B", "Husqvarna B", "https://www.avanza.se/aktier/om-aktien.html/45189/husqvarna-b", "HUSQ-B.ST"),
    ("INDU C", "Industrivärden C", "https://www.avanza.se/aktier/om-aktien.html/5245/industrivarden-c", "INDU-C.ST"),
    ("INDT", "Indutrade", "https://www.avanza.se/aktier/om-aktien.html/26607/indutrade", "INDT.ST"),
    ("INVE B", "Investor B", "https://www.avanza.se/aktier/om-aktien.html/5247/investor-b", "INVE-B.ST"),
    ("INTRUM", "Intrum", "https://www.avanza.se/aktier/om-aktien.html/5223/intrum", "INTRUM.ST"),
    ("KINV B", "Kinnevik B", "https://www.avanza.se/aktier/om-aktien.html/5369/kinnevik-b", "KINV-B.ST"),
    ("LAGR B", "Lagercrantz Group B", "https://www.avanza.se/aktier/om-aktien.html/5514/lagercrantz-group-b", "LAGR-B.ST"),
    ("LATO B", "Latour B", "https://www.avanza.se/aktier/om-aktien.html/5321/latour-b", "LATO-B.ST"),
    ("LIFCO B", "Lifco B", "https://www.avanza.se/aktier/om-aktien.html/520898/lifco-b", "LIFCO-B.ST"),
    ("LOOMIS", "Loomis", "https://www.avanza.se/aktier/om-aktien.html/154930/loomis", "LOOMIS.ST"),
    ("LUND B", "Lundbergföretagen B", "https://www.avanza.se/aktier/om-aktien.html/5375/lundbergforetagen-b", "LUND-B.ST"),
    ("MTRS", "Munters Group", "https://www.avanza.se/aktier/om-aktien.html/753399/munters-group", "MTRS.ST"),
    ("NDA SE", "Nordea", "https://www.avanza.se/aktier/om-aktien.html/5249/nordea-bank", "NDA-SE.ST"),
    ("NIBE B", "NIBE B", "https://www.avanza.se/aktier/om-aktien.html/5325/nibe-industrier-b", "NIBE-B.ST"),
    ("SAAB B", "Saab B", "https://www.avanza.se/aktier/om-aktien.html/5260/saab-b", "SAAB-B.ST"),
    ("SAND", "Sandvik", "https://www.avanza.se/aktier/om-aktien.html/5471/sandvik", "SAND.ST"),
    ("SBB B", "Samhällsbyggnadsbolaget B", "https://www.avanza.se/aktier/om-aktien.html/808046/sbb-b", "SBB-B.ST"),
    ("SCA B", "SCA B", "https://www.avanza.se/aktier/om-aktien.html/5263/sca-b", "SCA-B.ST"),
    ("SEB A", "SEB A", "https://www.avanza.se/aktier/om-aktien.html/5255/seb-a", "SEB-A.ST"),
    ("SECU B", "Securitas B", "https://www.avanza.se/aktier/om-aktien.html/5270/securitas-b", "SECU-B.ST"),
    ("SECT B", "Sectra B", "https://www.avanza.se/aktier/om-aktien.html/16226/sectra-b", "SECT-B.ST"),
    ("SHB A", "Handelsbanken A", "https://www.avanza.se/aktier/om-aktien.html/5264/handelsbanken-a", "SHB-A.ST"),
    ("SINCH", "Sinch", "https://www.avanza.se/aktier/om-aktien.html/599956/sinch", "SINCH.ST"),
    ("SKF B", "SKF B", "https://www.avanza.se/aktier/om-aktien.html/5259/skf-b", "SKF-B.ST"),
    ("SOBI", "Swedish Orphan Biovitrum", "https://www.avanza.se/aktier/om-aktien.html/51308/swedish-orphan-biovitrum", "SOBI.ST"),
    ("SSAB A", "SSAB A", "https://www.avanza.se/aktier/om-aktien.html/5261/ssab-a", "SSAB-A.ST"),
    ("SSAB B", "SSAB B", "https://www.avanza.se/aktier/om-aktien.html/495284/ssab-b", "SSAB-B.ST"),
    ("STE R", "Stora Enso R", "https://www.avanza.se/aktier/om-aktien.html/5256/stora-enso-r", "STE-R.ST"),
    ("SWEC B", "Sweco B", "https://www.avanza.se/aktier/om-aktien.html/5409/sweco-b", "SWEC-B.ST"),
    ("SWED A", "Swedbank A", "https://www.avanza.se/aktier/om-aktien.html/5241/swedbank-a", "SWED-A.ST"),
    ("TELE2 B", "Tele2 B", "https://www.avanza.se/aktier/om-aktien.html/5386/tele2-b", "TELE2-B.ST"),
    ("TELIA", "Telia", "https://www.avanza.se/aktier/om-aktien.html/5479/telia-company", "TELIA.ST"),
    ("TIGO SDB", "Millicom SDB", "https://www.avanza.se/aktier/om-aktien.html/5384/millicom-sdb", "TIGO-SDB.ST"),
    ("TREL B", "Trelleborg B", "https://www.avanza.se/aktier/om-aktien.html/5267/trelleborg-b", "TREL-B.ST"),
    ("VOLCAR B", "Volvo Cars B", "https://www.avanza.se/aktier/om-aktien.html/1041480/volvo-cars-b", "VOLCAR-B.ST"),
    ("VOLV A", "Volvo A", "https://www.avanza.se/aktier/om-aktien.html/5268/volvo-a", "VOLV-A.ST"),
    ("VOLV B", "Volvo B", "https://www.avanza.se/aktier/om-aktien.html/5269/volvo-b", "VOLV-B.ST"),
    # ── Mid Cap ────────────────────────────────────────────────
    ("ACAD", "Academedia", "https://www.avanza.se/aktier/om-aktien.html/560907/academedia", "ACAD.ST"),
    ("ADDT B", "AddTech B", "https://www.avanza.se/aktier/om-aktien.html/5537/addtech-b", "ADDT-B.ST"),
    ("AMBEA", "Ambea", "https://www.avanza.se/aktier/om-aktien.html/753387/ambea", "AMBEA.ST"),
    ("ARJO B", "Arjo B", "https://www.avanza.se/aktier/om-aktien.html/831548/arjo-b", "ARJO-B.ST"),
    ("ATRLJ B", "Atrium Ljungberg B", "https://www.avanza.se/aktier/om-aktien.html/5272/atrium-ljungberg-b", "ATRLJ-B.ST"),
    ("BETS B", "Betsson B", "https://www.avanza.se/aktier/om-aktien.html/5482/betsson-b", "BETS-B.ST"),
    ("BIOG B", "BioGaia B", "https://www.avanza.se/aktier/om-aktien.html/5507/biogaia-b", "BIOG-B.ST"),
    ("BONAV B", "Bonava B", "https://www.avanza.se/aktier/om-aktien.html/764238/bonava-b", "BONAV-B.ST"),
    ("BOOZT", "Boozt", "https://www.avanza.se/aktier/om-aktien.html/780423/boozt", "BOOZT.ST"),
    ("BRAV", "Bravida Holding", "https://www.avanza.se/aktier/om-aktien.html/753395/bravida-holding", "BRAV.ST"),
    ("BUFAB", "Bufab", "https://www.avanza.se/aktier/om-aktien.html/518131/bufab", "BUFAB.ST"),
    ("BURE", "Bure Equity", "https://www.avanza.se/aktier/om-aktien.html/5277/bure-equity", "BURE.ST"),
    ("CAMX", "Camurus", "https://www.avanza.se/aktier/om-aktien.html/521499/camurus", "CAMX.ST"),
    ("CATE", "Catena", "https://www.avanza.se/aktier/om-aktien.html/5484/catena", "CATE.ST"),
    ("CIBUS", "Cibus Nordic Real Estate", "https://www.avanza.se/aktier/om-aktien.html/867390/cibus-nordic", "CIBUS.ST"),
    ("CINT", "Cint Group", "https://www.avanza.se/aktier/om-aktien.html/1061965/cint-group", "CINT.ST"),
    ("CLAS B", "Clas Ohlson B", "https://www.avanza.se/aktier/om-aktien.html/5276/clas-ohlson-b", "CLAS-B.ST"),
    ("COOR", "Coor Service Management", "https://www.avanza.se/aktier/om-aktien.html/523418/coor-service-management", "COOR.ST"),
    ("CTM", "CellaVision", "https://www.avanza.se/aktier/om-aktien.html/5490/cellavision", "CTM.ST"),
    ("DIOS", "Dios Fastigheter", "https://www.avanza.se/aktier/om-aktien.html/45191/dios-fastigheter", "DIOS.ST"),
    ("ELAN B", "Elanders B", "https://www.avanza.se/aktier/om-aktien.html/5485/elanders-b", "ELAN-B.ST"),
    ("FABG", "Fabege", "https://www.avanza.se/aktier/om-aktien.html/5300/fabege", "FABG.ST"),
    ("GREP", "Gränges", "https://www.avanza.se/aktier/om-aktien.html/510194/granges", "GREP.ST"),
    ("HEBA B", "HEBA Fastigheter B", "https://www.avanza.se/aktier/om-aktien.html/5506/heba-b", "HEBA-B.ST"),
    ("HMS", "HMS Networks", "https://www.avanza.se/aktier/om-aktien.html/98412/hms-networks", "HMS.ST"),
    ("HTRO", "Hexatronic", "https://www.avanza.se/aktier/om-aktien.html/299737/hexatronic-group", "HTRO.ST"),
    ("HUFV A", "Hufvudstaden A", "https://www.avanza.se/aktier/om-aktien.html/5287/hufvudstaden-a", "HUFV-A.ST"),
    ("JM", "JM", "https://www.avanza.se/aktier/om-aktien.html/5501/jm", "JM.ST"),
    ("KABE B", "KABE B", "https://www.avanza.se/aktier/om-aktien.html/5308/kabe-b", "KABE-B.ST"),
    ("KNOW", "Knowit", "https://www.avanza.se/aktier/om-aktien.html/5515/knowit", "KNOW.ST"),
    ("LIME", "Lime Technologies", "https://www.avanza.se/aktier/om-aktien.html/867393/lime-technologies", "LIME.ST"),
    ("MEKO", "Meko", "https://www.avanza.se/aktier/om-aktien.html/5324/meko", "MEKO.ST"),
    ("MEDIO B", "Medicover B", "https://www.avanza.se/aktier/om-aktien.html/788849/medicover-b", "MEDIO-B.ST"),
    ("MYCR", "Mycronic", "https://www.avanza.se/aktier/om-aktien.html/5383/mycronic", "MYCR.ST"),
    ("NCAB", "NCAB Group", "https://www.avanza.se/aktier/om-aktien.html/856458/ncab-group", "NCAB.ST"),
    ("NEWA B", "New Wave Group B", "https://www.avanza.se/aktier/om-aktien.html/5326/new-wave-group-b", "NEWA-B.ST"),
    ("NOLA B", "Nolato B", "https://www.avanza.se/aktier/om-aktien.html/5327/nolato-b", "NOLA-B.ST"),
    ("NOTE", "NOTE", "https://www.avanza.se/aktier/om-aktien.html/5328/note", "NOTE.ST"),
    ("NP3", "NP3 Fastigheter", "https://www.avanza.se/aktier/om-aktien.html/519504/np3-fastigheter", "NP3.ST"),
    ("NYFOSA", "Nyfosa", "https://www.avanza.se/aktier/om-aktien.html/907825/nyfosa", "NYFOSA.ST"),
    ("OEM B", "OEM International B", "https://www.avanza.se/aktier/om-aktien.html/5329/oem-international-b", "OEM-B.ST"),
    ("PEAB B", "Peab B", "https://www.avanza.se/aktier/om-aktien.html/5330/peab-b", "PEAB-B.ST"),
    ("PLAZ B", "Platzer Fastigheter B", "https://www.avanza.se/aktier/om-aktien.html/519508/platzer-fastigheter-b", "PLAZ-B.ST"),
    ("PNDX B", "Pandox B", "https://www.avanza.se/aktier/om-aktien.html/720476/pandox-b", "PNDX-B.ST"),
    ("RATO B", "Ratos B", "https://www.avanza.se/aktier/om-aktien.html/5397/ratos-b", "RATO-B.ST"),
    ("RESURS", "Resurs Holding", "https://www.avanza.se/aktier/om-aktien.html/569437/resurs-holding", "RESURS.ST"),
    ("RVRC", "Revolution Race", "https://www.avanza.se/aktier/om-aktien.html/1041388/rvrc-holding", "RVRC.ST"),
    ("SAGAX B", "Sagax B", "https://www.avanza.se/aktier/om-aktien.html/405815/sagax-b", "SAGAX-B.ST"),
    ("SAVE", "Nordnet", "https://www.avanza.se/aktier/om-aktien.html/325295/nordnet", "SAVE.ST"),
    ("SDIP B", "Sdiptech B", "https://www.avanza.se/aktier/om-aktien.html/784434/sdiptech-b", "SDIP-B.ST"),
    ("SYSR", "Synsam Group", "https://www.avanza.se/aktier/om-aktien.html/956279/synsam-group", "SYSR.ST"),
    ("THULE", "Thule Group", "https://www.avanza.se/aktier/om-aktien.html/521491/thule-group", "THULE.ST"),
    ("TOBS B", "Tobii B", "https://www.avanza.se/aktier/om-aktien.html/625680/tobii-b", "TOBS-B.ST"),
    ("TROAX", "Troax Group", "https://www.avanza.se/aktier/om-aktien.html/549766/troax-group", "TROAX.ST"),
    ("VBG B", "VBG Group B", "https://www.avanza.se/aktier/om-aktien.html/5342/vbg-group-b", "VBG-B.ST"),
    ("WALL B", "Wallenstam B", "https://www.avanza.se/aktier/om-aktien.html/5344/wallenstam-b", "WALL-B.ST"),
    ("WIHL", "Wihlborgs Fastigheter", "https://www.avanza.se/aktier/om-aktien.html/5345/wihlborgs-fastigheter", "WIHL.ST"),
    ("XVIVO", "XVIVO Perfusion", "https://www.avanza.se/aktier/om-aktien.html/376275/xvivo-perfusion", "XVIVO.ST"),
]

STOCK_UNIVERSE = {t[0]: t[1] for t in _STOCK_DATA}
AVANZA_URLS    = {t[0]: t[2] for t in _STOCK_DATA}
YAHOO_SYMBOLS  = {t[0]: t[3] for t in _STOCK_DATA}

MIN_DAILY_TURNOVER_SEK = 30_000_000   # 30M SEK/dag — filtrerar bort illikvida mikrokap
MIN_HISTORY_DAYS      = 50            # Minst 50 handelsdagar för tillförlitlig bedömning


def score_candidate(ticker: str, indicators: dict, df) -> tuple[float, list[str]]:
    """
    Score a stock as a trading candidate (0–100+).
    Returns score=0 and a disqualification reason if liquidity/history filters fail.
    Higher score = bättre handelskandidat.
    """
    score = 0.0
    reasons = []

    price = indicators.get("current_price", 0)
    atr = indicators.get("atr", 0)

    # LIKVIDITETSFILTER: minst 30M SEK/dag i genomsnittlig omsättning.
    # Filtrerar bort mikrokap och First North-bolag med låg handel.
    if not df.empty and "close" in df.columns and "volume" in df.columns:
        avg_turnover = (df["close"] * df["volume"]).mean()
        if avg_turnover < MIN_DAILY_TURNOVER_SEK:
            return 0.0, [f"Filtrerad: omsättning {avg_turnover / 1e6:.1f}M SEK/dag (min {MIN_DAILY_TURNOVER_SEK // 1_000_000}M)"]
        elif avg_turnover >= 200_000_000:
            score += 20
            reasons.append(f"Mycket hög likviditet: {avg_turnover / 1e6:.0f}M SEK/dag")
        elif avg_turnover >= 80_000_000:
            score += 10
            reasons.append(f"God likviditet: {avg_turnover / 1e6:.0f}M SEK/dag")

    # HISTORIKFILTER: minst 50 handelsdagar för tillförlitliga indikatorer
    if len(df) < MIN_HISTORY_DAYS:
        return 0.0, [f"Filtrerad: bara {len(df)} handelsdagar (min {MIN_HISTORY_DAYS})"]

    # 1. Daglig volatilitet (ATR / pris) — vi vill ha 2–8% för bra handelsmöjligheter
    if price and atr:
        daily_vol_pct = (atr / price) * 100
        if 2 <= daily_vol_pct <= 8:
            score += 25
            reasons.append(f"Bra volatilitet: {daily_vol_pct:.1f}%/dag")
        elif daily_vol_pct > 8:
            score += 10
            reasons.append(f"Hög volatilitet: {daily_vol_pct:.1f}%/dag")
        else:
            reasons.append(f"Låg volatilitet: {daily_vol_pct:.1f}%/dag")

    # 2. Volymratio — vi vill ha >1.0 (aktivt handlad)
    vol_ratio = indicators.get("volume_ratio", 0)
    if vol_ratio >= 1.5:
        score += 20
        reasons.append(f"Hög volym: {vol_ratio:.1f}× snitt")
    elif vol_ratio >= 1.0:
        score += 10
        reasons.append(f"Normal volym: {vol_ratio:.1f}× snitt")

    # 3. Trендkvalitet — pris vs MA50/MA200
    ma50 = indicators.get("ma50")
    ma200 = indicators.get("ma200")
    if price and ma50 and price > ma50:
        score += 20
        reasons.append("Pris över MA50 (upptrend)")
    if price and ma200 and price > ma200:
        score += 15
        reasons.append("Pris över MA200 (långsiktig upptrend)")

    # 4. RSI i handelsbart läge (30–70)
    rsi = indicators.get("rsi")
    if rsi and 30 <= rsi <= 70:
        score += 10
        reasons.append(f"RSI: {rsi:.0f} (handelsbart läge)")

    return round(score, 1), reasons


def _derive_stock_config(indicators: dict, df) -> dict:
    """
    Derive per-stock trading config (strategy, SL%, TP%, ATR-multiplier)
    from the stock's own volatility profile.
    """
    price = indicators.get("current_price", 1)
    atr = indicators.get("atr") or 0
    rsi = indicators.get("rsi") or 50
    ma50 = indicators.get("ma50")
    ma200 = indicators.get("ma200")
    atr_pct = atr / price if price else 0.02

    # Strategy determination
    if rsi < 40 and ma50 and price < ma50:
        strategy = "mean_reversion"
    elif ma50 and ma200 and price > ma50 and price > ma200:
        strategy = "trend_following"
    else:
        strategy = "trend_following"

    # ATR-baserade SL/TP — begränsade till rimliga intervall
    stop_loss_pct  = round(min(0.09, max(0.03, atr_pct * 1.5)), 3)
    take_profit_pct = round(min(0.18, max(0.06, atr_pct * 3.0)), 3)

    return {
        "strategy":        strategy,
        "stop_loss_pct":   stop_loss_pct,
        "take_profit_pct": take_profit_pct,
        "atr_multiplier":  1.3,
    }


ROTATION_MARGIN = 25   # Ny kandidat måste vara minst 25p bättre än den svagaste
DISCOVERY_WATCHLIST_SIZE = 15  # Antal aktier i watchlist under discovery-fas


async def discovery_scan():
    """
    Morning discovery: scan full universe and fill watchlist with top candidates.

    Called at 08:55 when open positions < MAX_POSITIONS.
    Ranks all stocks by combined candidate score + technical buy pre-score,
    then sets the top DISCOVERY_WATCHLIST_SIZE as the active watchlist.
    Stocks with open positions are always kept.
    """
    logger.info("=== DISCOVERY SCAN START ===")
    logger.info(f"Skannar {len(STOCK_UNIVERSE)} aktier för att hitta bästa handels­kandidaterna...")

    # Get current open positions (must keep these)
    db_client = get_client()
    open_trades = db_client.table("stock_trades").select("ticker").eq("status", "open").execute()
    positioned_tickers = {t["ticker"] for t in (open_trades.data or [])}
    logger.info(f"Skyddade positioner: {positioned_tickers or '{inga}'}")

    # Current watchlist — gives stability bonus to existing entries
    watchlist = await get_watchlist()
    current_watchlist_tickers = {s["ticker"] for s in watchlist}

    # Fetch OMXS30 for relative strength
    try:
        index_df = await get_index_history()
    except Exception as e:
        logger.warning(f"Kunde inte hämta OMXS30-data: {e}")
        index_df = None

    market_regime = calculate_market_regime(index_df)
    logger.info(f"Marknadsregim: {market_regime}")

    results = []
    filtered = []    # Tickers filtered by liquidity/history/data
    error_tickers = []  # Tickers that threw exceptions
    scanned = 0
    errors = 0

    for ticker, name in STOCK_UNIVERSE.items():
        yahoo_symbol = YAHOO_SYMBOLS.get(ticker)
        if not yahoo_symbol:
            filtered.append({"ticker": ticker, "reason": "Ingen Yahoo-symbol"})
            continue
        try:
            df = await get_price_history(ticker, days=220)
            if df.empty or len(df) < MIN_HISTORY_DAYS:
                days_available = 0 if df.empty else len(df)
                filtered.append({"ticker": ticker, "reason": f"För lite data: {days_available} dagar (min {MIN_HISTORY_DAYS})"})
                continue

            indicators = calculate_indicators(df)
            if not indicators:
                filtered.append({"ticker": ticker, "reason": "Indikatorberäkning misslyckades"})
                continue

            # 1. Candidate score (liquidity, volatility, trend)
            cand_score, cand_reasons = score_candidate(ticker, indicators, df)
            if cand_score == 0:
                reason = cand_reasons[0] if cand_reasons else "okänd"
                filtered.append({"ticker": ticker, "reason": reason})
                logger.debug(f"  {ticker}: filtrerad — {reason}")
                continue

            # 2. Technical buy pre-score (without sentiment — quick & free)
            rs = calculate_relative_strength(df, index_df) if index_df is not None else None
            buy_pre_score, buy_reasons = score_buy_signal(
                ticker, indicators,
                news_sentiment=None, insider_trades=None,
                has_open_report_soon=False,
                relative_strength=rs,
                market_regime=market_regime,
            )

            # Combined score: 40% candidate quality + 60% buy readiness
            # This prioritizes stocks that are both good candidates AND close to a buy signal
            combined_score = cand_score * 0.4 + buy_pre_score * 0.6

            # Stability bonus: stocks already on the watchlist get a small boost
            # to prevent unnecessary churn
            if ticker in current_watchlist_tickers:
                combined_score += 5
                cand_reasons.append("Stabilitet: redan på watchlist (+5p)")

            results.append({
                "ticker": ticker,
                "name": name,
                "candidate_score": cand_score,
                "buy_pre_score": buy_pre_score,
                "combined_score": round(combined_score, 1),
                "reasons": cand_reasons,
                "buy_reasons": buy_reasons,
                "indicators": indicators,
                "df": df,
                "is_positioned": ticker in positioned_tickers,
            })
            scanned += 1

            if buy_pre_score >= 30:
                logger.info(f"  {ticker}: kandidat={cand_score:.0f}p  köp_pre={buy_pre_score:.0f}p  kombi={combined_score:.0f}p ★")
            else:
                logger.debug(f"  {ticker}: kandidat={cand_score:.0f}p  köp_pre={buy_pre_score:.0f}p  kombi={combined_score:.0f}p")

        except Exception as e:
            errors += 1
            error_tickers.append({"ticker": ticker, "error": str(e)})
            logger.warning(f"  {ticker}: fel — {e}")

        # Throttle to avoid Yahoo rate-limiting
        await asyncio.sleep(0.5)

    if not results:
        logger.warning("Discovery scan returnerade inga resultat.")
        return {"scanned": scanned, "errors": errors, "market_regime": market_regime,
                "watchlist_size": 0, "candidates": [],
                "filtered": filtered, "error_tickers": error_tickers}

    # Sort by combined score
    results.sort(key=lambda x: x["combined_score"], reverse=True)

    # Select top candidates: positioned stocks always included + best N non-positioned
    positioned_results = [r for r in results if r["is_positioned"]]
    non_positioned = [r for r in results if not r["is_positioned"]]
    slots_available = DISCOVERY_WATCHLIST_SIZE - len(positioned_results)
    top_candidates = non_positioned[:max(0, slots_available)]

    final_selection = positioned_results + top_candidates

    # Build new watchlist entries
    new_entries = []
    for r in final_selection:
        if r["ticker"] in positioned_tickers:
            continue  # positioned stocks are already in watchlist — don't re-add
        cfg = _derive_stock_config(r["indicators"], r["df"])
        new_entries.append({
            "ticker": r["ticker"],
            "name": r["name"],
            "strategy": cfg["strategy"],
            "stop_loss_pct": cfg["stop_loss_pct"],
            "take_profit_pct": cfg["take_profit_pct"],
            "atr_multiplier": cfg["atr_multiplier"],
            "avanza_url": AVANZA_URLS.get(r["ticker"]),
        })

    # Update watchlist in DB
    await bulk_update_watchlist(positioned_tickers, new_entries)

    # Seed indicators + prices for all watchlist stocks so the frontend shows data immediately
    # (otherwise stocks won't have data until next trading loop tick)
    from db.supabase_client import save_indicators, save_price
    seeded = 0
    for r in final_selection:
        try:
            ind = r["indicators"].copy()
            ind["buy_score"] = r["buy_pre_score"]
            await save_indicators(r["ticker"], ind)
            if ind.get("current_price"):
                await save_price(r["ticker"], ind["current_price"], int(ind.get("volume_ratio", 0) * 1000000))
            seeded += 1
        except Exception as e:
            logger.debug(f"Seed indicators {r['ticker']}: {e}")
    logger.info(f"Seedade indikatorer för {seeded}/{len(final_selection)} watchlist-aktier")

    # Summary notification
    top5 = final_selection[:5]
    top5_lines = []
    for r in top5:
        star = "⭐" if r["buy_pre_score"] >= 40 else "▪"
        top5_lines.append(
            f"  {star} {r['ticker']} — kombi {r['combined_score']:.0f}p (köp {r['buy_pre_score']:.0f}p)"
        )
    top5_str = "\n".join(top5_lines)

    msg = (
        f"Discovery: {scanned} aktier skannade, {len(final_selection)} i watchlist\n"
        f"Marknadsregim: {market_regime}\n\n"
        f"Topp 5 kandidater:\n{top5_str}"
    )
    if errors > 0:
        msg += f"\n\n⚠ {errors} aktier kunde inte analyseras"
        # Visa vilka aktier som failade
        for et in error_tickers[:5]:
            msg += f"\n  • {et['ticker']}: {et['error'][:60]}"
    if filtered:
        msg += f"\n\n{len(filtered)} aktier filtrerade (likviditet/data)"

    await ntfy._send(
        msg,
        title=f"Discovery — {len(final_selection)} aktier bevakas",
        priority="default",
        tags=["mag", "bar_chart"],
        notif_type="discovery_scan",
    )

    logger.info(
        f"=== DISCOVERY SCAN KLAR === "
        f"{scanned} skannade, {len(filtered)} filtrerade, {len(final_selection)} i watchlist, {errors} fel"
    )

    # Return structured result for API consumers
    scan_result = {
        "scanned": scanned,
        "errors": errors,
        "filtered_count": len(filtered),
        "total_universe": len(STOCK_UNIVERSE),
        "market_regime": market_regime,
        "watchlist_size": len(final_selection),
        "candidates": [
            {
                "ticker": r["ticker"],
                "name": r["name"],
                "combined_score": r["combined_score"],
                "candidate_score": r["candidate_score"],
                "buy_pre_score": r["buy_pre_score"],
                "reasons": r["reasons"][:3],
                "buy_reasons": r["buy_reasons"][:5],
                "is_positioned": r["is_positioned"],
            }
            for r in final_selection
        ],
        "filtered": filtered,
        "error_tickers": error_tickers,
    }

    # Persist to DB for reload-safe display + historical comparison
    try:
        from db.supabase_client import save_discovery_scan
        scan_id = await save_discovery_scan(scan_result)
        if scan_id:
            scan_result["scan_id"] = scan_id
    except Exception as e:
        logger.warning(f"Kunde inte spara discovery scan till DB: {e}")

    return scan_result


async def run_scan():
    """Main scan function — called daily/weekly by scheduler."""
    logger.info("Startar aktiesskanning...")
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
            # 220 dagar för att MA200 ska beräknas korrekt
            df = await get_price_history(ticker, days=220)
            if df.empty or len(df) < MIN_HISTORY_DAYS:
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
                "df": df,
                "in_watchlist": ticker in current_tickers,
            })
            if score > 0:
                logger.info(f"  {ticker}: {score:.0f}p")
            else:
                logger.debug(f"  {ticker}: filtrerad – {reasons[0] if reasons else '?'}")
        except Exception as e:
            logger.warning(f"  {ticker}: fel – {e}")

        # Throttle to avoid Yahoo rate-limiting
        await asyncio.sleep(0.5)

    if not results:
        logger.warning("Skanning returnerade inga resultat.")
        return

    # Sort by score — disqualified stocks (score=0) hamnar sist
    results.sort(key=lambda x: x["score"], reverse=True)

    # Top candidates NOT in watchlist (only qualified, score > 0)
    top_new = [r for r in results if not r["in_watchlist"] and r["score"] > 0][:5]

    # Weakest in current watchlist (only those that qualified the liquidity filter)
    current_scored = [r for r in results if r["in_watchlist"] and r["score"] > 0]
    current_scored.sort(key=lambda x: x["score"])
    weakest = current_scored[:2] if current_scored else []

    # Check which tickers have open positions (never rotate out of those)
    open_trades = db.table("stock_trades").select("ticker").eq("status", "open").execute()
    open_tickers = {t["ticker"] for t in (open_trades.data or [])}

    replaced = []
    replaced_tickers = set()

    for candidate in top_new:
        for weak in weakest:
            if weak["ticker"] in replaced_tickers:
                continue
            if weak["ticker"] in open_tickers:
                logger.info(f"Hoppar over {weak['ticker']} — öppen position finns.")
                continue
            # Kräv att ny kandidat är minst ROTATION_MARGIN poäng bättre
            if candidate["score"] > weak["score"] + ROTATION_MARGIN:
                cfg = _derive_stock_config(candidate["indicators"], candidate["df"])

                # Deactivate the weak stock
                db.table("stock_watchlist").update({"active": False}).eq("ticker", weak["ticker"]).execute()

                # Add the better stock with derived config
                db.table("stock_watchlist").insert({
                    "ticker":          candidate["ticker"],
                    "name":            candidate["name"],
                    "strategy":        cfg["strategy"],
                    "stop_loss_pct":   cfg["stop_loss_pct"],
                    "take_profit_pct": cfg["take_profit_pct"],
                    "atr_multiplier":  cfg["atr_multiplier"],
                    "avanza_url":      AVANZA_URLS.get(candidate["ticker"]),
                    "active":          True,
                    "created_at":      datetime.now(timezone.utc).isoformat(),
                }).execute()

                replaced.append((weak, candidate))
                replaced_tickers.add(weak["ticker"])
                logger.info(
                    f"Bytte {weak['ticker']} ({weak['score']:.0f}p) mot "
                    f"{candidate['ticker']} ({candidate['score']:.0f}p) | "
                    f"strategi={cfg['strategy']} SL={cfg['stop_loss_pct']} TP={cfg['take_profit_pct']}"
                )
                break

    # Send ntfy summary
    if replaced:
        sections = []
        for w, c in replaced[:3]:
            top_reasons = c["reasons"][:3]
            reasons_str = "\n".join(f"    ✓ {r}" for r in top_reasons)
            sections.append(
                f"  {w['ticker']} ({w['score']:.0f}p) → {c['ticker']} ({c['score']:.0f}p)\n{reasons_str}"
            )
        lines = "\n".join(sections)
        await ntfy._send(
            f"Watchlist uppdaterad – {len(replaced)} byte(n):\n{lines}",
            title="Watchlist uppdaterad",
            priority="default",
            tags=["bar_chart"],
            notif_type="scan_suggestion",
        )
    else:
        await ntfy._send(
            "Nuvarande watchlist är fortsatt optimal – inga byten gjordes.",
            title="Watchlist-skanning klar",
            priority="min",
            tags=["bar_chart"],
            notif_type="scan_suggestion",
        )

    logger.info(f"Skanning klar. {len(results)} aktier analyserade, {len(replaced)} byten.")
