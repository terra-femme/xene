import logging
from fastapi import APIRouter, HTTPException, Query
from services.beatport import get_artist_releases, get_artist_releases_by_id, search_artists
from models import BeatportArtist, BeatportRelease

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/beatport", tags=["beatport"])


@router.get("/artists/search", response_model=list[BeatportArtist])
async def artist_search(
    q: str = Query(..., min_length=1, description="Artist name to search for"),
    limit: int = Query(10, ge=1, le=25),
):
    """
    Search Beatport for artists matching a name query.
    Returns candidates with beatport_id — call this once when a user adds an artist,
    then store the confirmed beatport_id in the artists table for all future feed fetches.
    """
    logger.info(f"[beatport router] GET /beatport/artists/search q={q!r} limit={limit}")
    try:
        results = await search_artists(q, limit=limit)
        logger.info(f"[beatport router] Returning {len(results)} artist candidate(s)")
        return results
    except RuntimeError as exc:
        logger.error(f"[beatport router] RuntimeError: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/releases", response_model=list[BeatportRelease])
async def releases_by_artist_name(
    artist: str = Query(..., description="Artist name to search for"),
    limit: int = Query(10, ge=1, le=25),
):
    """
    Search Beatport for recent releases by artist name.
    Used when only the artist name is known (no Beatport ID stored).
    """
    logger.info(f"[beatport router] GET /beatport/releases artist={artist!r} limit={limit}")
    try:
        results = await get_artist_releases(artist, limit=limit)
        logger.info(f"[beatport router] Returning {len(results)} release(s)")
        return results
    except RuntimeError as exc:
        logger.error(f"[beatport router] RuntimeError: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/releases/by-id", response_model=list[BeatportRelease])
async def releases_by_artist_id(
    artist_id: int = Query(..., description="Beatport numeric artist ID"),
    limit: int = Query(10, ge=1, le=25),
):
    """
    Fetch releases by Beatport artist ID — more precise than name search.
    Use once the artist's Beatport ID has been discovered and stored.
    """
    logger.info(f"[beatport router] GET /beatport/releases/by-id artist_id={artist_id} limit={limit}")
    try:
        results = await get_artist_releases_by_id(artist_id, limit=limit)
        logger.info(f"[beatport router] Returning {len(results)} release(s)")
        return results
    except RuntimeError as exc:
        logger.error(f"[beatport router] RuntimeError: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))
