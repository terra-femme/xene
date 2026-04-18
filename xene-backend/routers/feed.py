import logging
from fastapi import APIRouter, HTTPException, Query
from models import FeedItem
from services import soundcloud, bandcamp

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("/soundcloud", response_model=list[FeedItem])
async def get_soundcloud_feed(
    username: str = Query(..., description="SoundCloud username"),
):
    logger.info(f"[feed] GET /feed/soundcloud username={username}")
    try:
        return await soundcloud.get_tracks(username)
    except Exception as e:
        logger.error(f"[feed] SoundCloud error for {username}: {e}")
        raise HTTPException(status_code=502, detail=f"SoundCloud feed error: {e}")


@router.get("/bandcamp", response_model=list[FeedItem])
async def get_bandcamp_feed(
    url: str = Query(..., description="Bandcamp artist URL"),
    artist_name: str = Query(..., description="Display name for the artist"),
):
    logger.info(f"[feed] GET /feed/bandcamp url={url}")
    try:
        return await bandcamp.get_feed(url, artist_name)
    except Exception as e:
        logger.error(f"[feed] Bandcamp error for {url}: {e}")
        raise HTTPException(status_code=502, detail=f"Bandcamp feed error: {e}")


@router.get("/oembed")
async def get_oembed(
    url: str = Query(..., description="SoundCloud track URL"),
):
    """Return the oEmbed iframe HTML for a SoundCloud track URL."""
    logger.info(f"[feed] GET /feed/oembed url={url}")
    try:
        return await soundcloud.get_oembed(url)
    except Exception as e:
        logger.error(f"[feed] oEmbed error for {url}: {e}")
        raise HTTPException(status_code=502, detail=f"oEmbed error: {e}")


@router.get("/merged", response_model=list[FeedItem])
async def get_merged_feed(
    sc: list[str] = Query(default=[], description="SoundCloud usernames"),
    bc_url: list[str] = Query(default=[], description="Bandcamp artist URLs"),
    bc_name: list[str] = Query(default=[], description="Bandcamp artist display names (same order as bc_url)"),
):
    """
    Fetch and merge feeds for multiple artists across platforms.
    Returns all items sorted newest-first.
    Used by the frontend feed hook — no DB required.
    """
    logger.info(f"[feed] GET /feed/merged sc={sc} bc_url={bc_url}")
    all_items: list[FeedItem] = []

    for username in sc:
        try:
            items = await soundcloud.get_tracks(username)
            all_items.extend(items)
        except Exception as e:
            logger.warning(f"[feed] Skipping SC {username}: {e}")

    for url, name in zip(bc_url, bc_name):
        try:
            items = await bandcamp.get_feed(url, name)
            all_items.extend(items)
        except Exception as e:
            logger.warning(f"[feed] Skipping BC {url}: {e}")

    all_items.sort(key=lambda x: x.published_at, reverse=True)
    logger.info(f"[feed] Merged feed returned {len(all_items)} items")
    return all_items
