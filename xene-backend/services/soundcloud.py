import re
import httpx
import feedparser
import logging
from models import FeedItem
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)

SC_OEMBED_URL = "https://soundcloud.com/oembed"
SC_FEEDS_BASE = "https://feeds.soundcloud.com/users/soundcloud:users:{user_id}/sounds.rss"

# In-memory cache: { username: { "user_id": str, "items": list[FeedItem], "fetched_at": datetime } }
_cache: dict = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


def _is_stale(username: str) -> bool:
    entry = _cache.get(username)
    if not entry:
        return True
    age = (datetime.now(timezone.utc) - entry["fetched_at"]).total_seconds()
    return age > CACHE_TTL_SECONDS


async def _resolve_user_id(username: str) -> str:
    """
    Scrape the SoundCloud profile page to extract the numeric user ID.
    SC embeds user data in a __sc_hydration JSON block on every public profile page.
    This is a one-time operation per artist — result is cached.
    """
    logger.info(f"[soundcloud] Resolving user ID for: {username}")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://soundcloud.com/{username}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            follow_redirects=True,
            timeout=10,
        )
        resp.raise_for_status()

    # SC inlines: window.__sc_hydration = [..., {"hydratable": "user", "data": {"id": 12345, ...}}, ...]
    match = re.search(r'"hydratable"\s*:\s*"user".*?"id"\s*:\s*(\d+)', resp.text)
    if not match:
        raise ValueError(f"Could not extract user ID for SoundCloud username: {username}")

    user_id = match.group(1)
    logger.info(f"[soundcloud] Resolved {username} → user_id={user_id}")
    return user_id


async def get_tracks(username: str) -> list[FeedItem]:
    """
    Fetch tracks for a SoundCloud username via their public RSS feed.
    Results are cached for 1 hour to avoid hammering the feed endpoint.
    """
    if not _is_stale(username):
        logger.info(f"[soundcloud] Returning cached feed for: {username}")
        return _cache[username]["items"]

    logger.info(f"[soundcloud] Fetching live RSS for: {username}")

    # Resolve user_id — use cached value if already resolved
    cached_user_id = _cache.get(username, {}).get("user_id")
    user_id = cached_user_id or await _resolve_user_id(username)

    rss_url = SC_FEEDS_BASE.format(user_id=user_id)
    logger.info(f"[soundcloud] Fetching RSS: {rss_url}")

    # Fetch with httpx so we control headers — feedparser's built-in fetcher
    # gets blocked by SoundCloud's CDN without a browser User-Agent.
    async with httpx.AsyncClient() as client:
        rss_resp = await client.get(
            rss_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=10,
        )
        rss_resp.raise_for_status()
        rss_content = rss_resp.text

    parsed = feedparser.parse(rss_content)
    logger.info(f"[soundcloud] Feed title: '{parsed.feed.get('title', 'N/A')}' bozo={parsed.bozo} version={parsed.version}")
    logger.info(f"[soundcloud] Raw RSS snippet: {rss_content[:600]}")

    if parsed.bozo:
        logger.warning(f"[soundcloud] RSS parse warning for {username}: {parsed.bozo_exception}")

    logger.info(f"[soundcloud] Got {len(parsed.entries)} tracks for {username}")

    artist_name = parsed.feed.get("title", username)
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
                platform="soundcloud",
                artist_name=artist_name,
                content_type="track",
                title=entry.get("title"),
                body=entry.get("summary"),
                external_url=entry.get("link", f"https://soundcloud.com/{username}"),
                published_at=published_at,
            ))
        except Exception as e:
            logger.warning(f"[soundcloud] Skipping entry '{entry.get('title')}': {e}")

    _cache[username] = {
        "user_id": user_id,
        "items": items,
        "fetched_at": datetime.now(timezone.utc),
    }
    return items


async def get_oembed(track_url: str) -> dict:
    """
    Fetch oEmbed data for a SoundCloud track URL.
    Returns the iframe HTML string the frontend uses to render a real player.
    """
    logger.info(f"[soundcloud] Fetching oEmbed for: {track_url}")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            SC_OEMBED_URL,
            params={
                "url": track_url,
                "format": "json",
                "color": "%23ff5500",
                "auto_play": "false",
                "hide_related": "true",
                "show_comments": "false",
                "show_user": "true",
                "show_reposts": "false",
            },
            timeout=8,
        )
        resp.raise_for_status()
        return resp.json()


def invalidate_cache(username: str | None = None):
    """Force a re-fetch on next request. Pass None to clear all."""
    if username:
        _cache.pop(username, None)
    else:
        _cache.clear()
