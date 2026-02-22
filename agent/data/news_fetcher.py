import feedparser
import httpx
from datetime import datetime, timezone
from typing import List, Dict

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?q={query}&hl=sv&gl=SE&ceid=SE:sv"
)


async def fetch_news(ticker: str, company_name: str, max_items: int = 5) -> List[Dict]:
    """Fetch latest news for a ticker via Google News RSS."""
    query = f"{company_name} aktie".replace(" ", "+")
    url = GOOGLE_NEWS_RSS.format(query=query)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()

    feed = feedparser.parse(resp.text)

    news = []
    for entry in feed.entries[:max_items]:
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

        news.append({
            "ticker": ticker,
            "headline": entry.title,
            "url": entry.link,
            "source": entry.get("source", {}).get("title", "Google News"),
            "published_at": published,
        })

    return news
