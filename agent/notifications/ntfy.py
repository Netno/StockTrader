import hashlib
import httpx
import uuid as _uuid
from datetime import datetime, timezone
from config import NTFY_URL, PAPER_TRADING, FRONTEND_URL


async def send_buy_signal(
    ticker: str,
    company: str,
    price: float,
    quantity: int,
    total: float,
    reasons: list,
    stop_loss: float,
    take_profit: float,
    confidence: float,
):
    mode = "PAPER " if PAPER_TRADING else ""
    reasons_str = "\n".join(f"  {r} ✓" for r in reasons[:4])
    message = (
        f"{mode}KOP {company} ({ticker})\n"
        f"Pris: {price:.2f} kr | Antal: {quantity} aktier (~{total:.0f} kr)\n"
        f"{reasons_str}\n"
        f"Stop-loss: {stop_loss:.2f} kr\n"
        f"Take-profit: {take_profit:.2f} kr\n"
        f"Confidence: {confidence:.0f}%"
    )
    signals_url = f"{FRONTEND_URL}/dashboard/signals" if FRONTEND_URL else None
    await _send(message, title=f"KOP {ticker}", priority="high",
                tags=["chart_with_upwards_trend"], notif_type="buy_signal", ticker=ticker,
                click_url=signals_url)


async def send_sell_signal(
    ticker: str,
    company: str,
    price: float,
    quantity: int,
    profit_pct: float,
    profit_sek: float,
    reasons: list,
    confidence: float,
    notif_subtype: str = "sell_signal",
):
    mode = "PAPER " if PAPER_TRADING else ""
    emoji = ":tada:" if profit_sek > 0 else ":chart_decreasing:"
    reasons_str = "\n".join(f"  {r} ✓" for r in reasons[:3])
    message = (
        f"{mode}SALJ {company} ({ticker})\n"
        f"Pris: {price:.2f} kr | Innehav: {quantity} aktier\n"
        f"Resultat: {profit_pct:+.1f}% ({profit_sek:+.0f} kr) {emoji}\n"
        f"{reasons_str}\n"
        f"Confidence: {confidence:.0f}%"
    )
    dashboard_url = f"{FRONTEND_URL}/dashboard" if FRONTEND_URL else None
    await _send(message, title=f"SALJ {ticker}", priority="high",
                tags=["chart_with_downwards_trend"], notif_type=notif_subtype, ticker=ticker,
                click_url=dashboard_url)


async def send_report_warning(ticker: str, company: str, report_date: str, has_position: bool):
    position_str = "Stanger position" if has_position else "Nuvarande position: INGEN"
    message = (
        f"RAPPORT OM 48H - {ticker}\n"
        f"Agenten pausar trading i {company}\n"
        f"Rapport: {report_date}\n"
        f"{position_str}"
    )
    await _send(message, title=f"Rapport varning {ticker}", priority="default",
                tags=["warning"], notif_type="report_warning", ticker=ticker)


async def send_morning_summary(
    portfolio_value: float,
    portfolio_pct: float,
    open_positions: int,
    reports_today: list,
    paused_tickers: list,
):
    reports_str = ", ".join(reports_today) if reports_today else "Inga"
    paused_str = ", ".join(paused_tickers) if paused_tickers else "Inga"
    message = (
        f"Borsen oppnar om 15 min\n"
        f"Portfolj: {portfolio_value:.0f} kr ({portfolio_pct:+.1f}%)\n"
        f"Oppna positioner: {open_positions}\n"
        f"Dagens rapporter: {reports_str}\n"
        f"Pausade aktier: {paused_str}"
    )
    await _send(message, title="Morgonsummering", priority="default",
                tags=["sun"], notif_type="morning_summary")


async def send_evening_summary(
    portfolio_value: float,
    portfolio_pct: float,
    signals_today: int,
    trades_today: int,
):
    message = (
        f"Borsen stangd\n"
        f"Portfolj: {portfolio_value:.0f} kr ({portfolio_pct:+.1f}%)\n"
        f"Signaler idag: {signals_today}\n"
        f"Affarer idag: {trades_today}"
    )
    await _send(message, title="Kvallssummering", priority="low",
                tags=["crescent_moon"], notif_type="evening_summary")


async def _send(
    message: str,
    title: str,
    priority: str = "default",
    tags: list = None,
    notif_type: str = "info",
    ticker: str = None,
    click_url: str = None,
):
    headers = {"Title": title, "Priority": priority}
    if tags:
        headers["Tags"] = ",".join(tags)
    if click_url:
        headers["Click"] = click_url

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                NTFY_URL,
                content=message.encode("utf-8"),
                headers=headers,
                timeout=10,
            )
        except Exception as e:
            print(f"ntfy error: {e}")

    # Log to Supabase regardless of ntfy success
    await _log(notif_type, title, message, ticker)


async def _log(notif_type: str, title: str, message: str, ticker: str = None):
    try:
        from db.supabase_client import get_client
        db = get_client()

        # Deterministiskt ID baserat på typ + ticker + timme.
        # Två Railway-instanser som kör simultant (deploy-overlap) genererar samma ID
        # → Supabase upsert på primary key är atomisk → bara en rad sparas.
        hour_key = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
        dedup_str = f"{notif_type}:{ticker or 'portfolio'}:{hour_key}"
        dedup_id = str(_uuid.UUID(hashlib.md5(dedup_str.encode()).hexdigest()))

        db.table("stock_notifications").upsert({
            "id": dedup_id,
            "type": notif_type,
            "title": title,
            "message": message,
            "ticker": ticker,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="id").execute()
    except Exception as e:
        print(f"Notification log error: {e}")
