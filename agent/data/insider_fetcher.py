import logging
import httpx
from datetime import datetime, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)

FI_INSIDER_URL = "https://www.fi.se/sv/vara-register/insynshandel/GetInsynshandel/"


async def fetch_insider_trades(ticker: str, company_name: str = None, days: int = 30) -> List[Dict]:
    """Fetch insider trades from Finansinspektionen's open API.
    FI's API searches by company name (e.g. 'Evolution AB'), not ticker symbol.
    Pass company_name for accurate results; falls back to ticker if not provided.
    """
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    search_name = company_name or ticker

    params = {
        "issuerName": search_name,
        "fromTransactionDate": from_date,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(FI_INSIDER_URL, params=params, timeout=15)
    except Exception as e:
        logger.warning(f"{ticker}: FI insider-anrop misslyckades: {e}")
        return []

    if resp.status_code != 200:
        logger.warning(f"{ticker}: FI returnerade HTTP {resp.status_code} for '{search_name}'")
        return []

    try:
        data = resp.json()
    except Exception as e:
        logger.warning(f"{ticker}: FI JSON-parsningsfel: {e}")
        return []

    trades = []
    for item in data:
        trades.append({
            "ticker": ticker,
            "person": item.get("person"),
            "role": item.get("position"),
            "action": item.get("typeOfTransaction", ""),
            "amount": (item.get("volume") or 0) * (item.get("price") or 0),
            "price": item.get("price"),
            "quantity": item.get("volume"),
            "date": item.get("transactionDate"),
        })

    if trades:
        logger.info(f"{ticker}: {len(trades)} insidertransaktioner fran FI (senaste {days} dagar)")
    else:
        logger.debug(f"{ticker}: inga insidertransaktioner fran FI")

    return trades


def has_significant_insider_buy(trades: List[Dict], min_amount: float = 500_000) -> bool:
    """Return True if any insider bought for >500k SEK."""
    buy_keywords = {"köp", "buy", "förvärv", "acquisition"}
    for trade in trades:
        action = trade.get("action", "").lower()
        if any(kw in action for kw in buy_keywords):
            if trade.get("amount", 0) >= min_amount:
                return True
    return False
