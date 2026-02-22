import httpx
from datetime import datetime, timedelta
from typing import List, Dict

FI_INSIDER_URL = "https://www.fi.se/sv/vara-register/insynshandel/GetInsynshandel/"


async def fetch_insider_trades(ticker: str, days: int = 30) -> List[Dict]:
    """Fetch insider trades from Finansinspektionen's open API."""
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    params = {
        "issuerName": ticker,
        "fromTransactionDate": from_date,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(FI_INSIDER_URL, params=params, timeout=15)

    if resp.status_code != 200:
        return []

    try:
        data = resp.json()
    except Exception:
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
