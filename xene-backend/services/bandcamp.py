import httpx
import feedparser
import logging
from models import FeedItem
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)


async def get_feed(bandcamp_url: str, artist_name: str) -> list[FeedItem]:
    """Parse a Bandcamp artist RSS feed into normalized FeedItems."""
    feed_url = f"{bandcamp_url.rstrip('/')}/feed"
    logger.info(f"[bandcamp] Parsing feed: {feed_url}")

    # Fetch with httpx — feedparser's built-in fetcher can get blocked
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            feed_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=10,
            follow_redirects=True,
        )
        resp.raise_for_status()
        content = resp.text

    parsed = feedparser.parse(content)
    logger.info(f"[bandcamp] Feed title: '{parsed.feed.get('title', 'N/A')}' bozo={parsed.bozo}")

    if parsed.bozo:
        logger.warning(f"[bandcamp] Feed parse warning for {bandcamp_url}: {parsed.bozo_exception}")

    logger.info(f"[bandcamp] Got {len(parsed.entries)} entries for {artist_name}")

    items: list[FeedItem] = []
    for entry in parsed.entries:
        try:
            published_at = (
                parsedate_to_datetime(entry.published)
                if entry.get("published")
                else datetime.now(timezone.utc)
            )
            items.append(FeedItem(
                id=entry.get("id", entry.get("link", "")),
                platform="bandcamp",
                artist_name=artist_name,
                content_type="release",
                title=entry.get("title"),
                body=entry.get("summary"),
                external_url=entry.get("link", bandcamp_url),
                published_at=published_at,
            ))
        except Exception as e:
            logger.warning(f"[bandcamp] Skipping entry '{entry.get('title')}': {e}")

    return items
