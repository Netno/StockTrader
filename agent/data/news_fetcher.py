import feedparser
import httpx
import time
from datetime import datetime, timezone
from typing import List, Dict

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?q={query}&hl=sv&gl=SE&ceid=SE:sv"
)

# Cache: (ticker, company_name) -> (result, expires_at) — 30 minuters TTL
_news_cache: dict[tuple, tuple] = {}
_NEWS_TTL = 30 * 60  # 30 minuter


async def fetch_news(ticker: str, company_name: str, max_items: int = 5) -> List[Dict]:
    """Fetch latest news for a ticker via Google News RSS (cached 30 min)."""
    cache_key = (ticker, company_name)
    cached_entry = _news_cache.get(cache_key)
    if cached_entry and time.monotonic() < cached_entry[1]:
        return cached_entry[0]

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

    _news_cache[cache_key] = (news, time.monotonic() + _NEWS_TTL)
    return news
