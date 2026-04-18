import os
import httpx
import logging
from models import FeedItem
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

IG_GRAPH_BASE = "https://graph.instagram.com"


async def get_posts(access_token: str, artist_name: str, limit: int = 20) -> list[FeedItem]:
    """Fetch recent Instagram posts for the authenticated user."""
    logger.info(f"[instagram] Fetching posts for: {artist_name}")
    url = f"{IG_GRAPH_BASE}/me/media"
    params = {
        "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp",
        "limit": limit,
        "access_token": access_token,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    posts = data.get("data", [])
    logger.info(f"[instagram] Got {len(posts)} posts for {artist_name}")

    items: list[FeedItem] = []
    for p in posts:
        media_type = p.get("media_type", "")
        content_type = "video" if media_type == "VIDEO" else "image"
        try:
            items.append(FeedItem(
                id=p["id"],
                platform="instagram",
                artist_name=artist_name,
                content_type=content_type,
                body=p.get("caption"),
                media_url=p.get("media_url") or p.get("thumbnail_url"),
                external_url=p.get("permalink", ""),
                published_at=datetime.fromisoformat(
                    p["timestamp"].replace("Z", "+00:00")
                ) if p.get("timestamp") else datetime.now(timezone.utc),
            ))
        except Exception as e:
            logger.warning(f"[instagram] Skipping post {p.get('id')}: {e}")

    return items
