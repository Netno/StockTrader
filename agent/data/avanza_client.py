import pandas as pd
from datetime import datetime, timedelta
from avanza import Avanza
from config import AVANZA_USERNAME, AVANZA_PASSWORD, AVANZA_TOTP_SECRET

_avanza: Avanza = None


async def get_client() -> Avanza:
    global _avanza
    if _avanza is None:
        _avanza = await Avanza.create({
            "username": AVANZA_USERNAME,
            "password": AVANZA_PASSWORD,
            "totpSecret": AVANZA_TOTP_SECRET,
        })
    return _avanza


async def get_price_history(avanza_id: str, days: int = 220) -> pd.DataFrame:
    """Fetch historical OHLCV data for indicator calculation."""
    client = await get_client()

    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")

    data = await client.get_chart_data(
        avanza_id,
        "ONE_DAY",
        from_date,
        to_date,
    )

    if not data or "ohlc" not in data:
        return pd.DataFrame()

    df = pd.DataFrame(data["ohlc"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.rename(columns={
        "timestamp": "date",
        "close": "close",
        "volume": "volume",
        "high": "high",
        "low": "low",
        "open": "open",
    })
    df = df.sort_values("date").reset_index(drop=True)
    return df


async def get_current_price(avanza_id: str) -> dict:
    """Get current price and volume for a ticker."""
    client = await get_client()
    info = await client.get_stock_info(avanza_id)
    return {
        "price": info.get("lastPrice"),
        "volume": info.get("totalVolumeTraded"),
        "change_pct": info.get("changePercent"),
    }
