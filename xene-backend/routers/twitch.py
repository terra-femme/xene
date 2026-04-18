import logging
from fastapi import APIRouter, HTTPException, Query
from models import TwitchStream
from services import twitch

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twitch", tags=["twitch"])


@router.get("/live", response_model=list[TwitchStream])
async def get_live_status(
    logins: list[str] = Query(..., description="Twitch login names to check"),
):
    """
    Return live stream data for any of the given Twitch logins that are currently live.
    Only actively streaming channels are returned — offline channels are omitted.
    Results are cached for 2 minutes.
    """
    logger.info(f"[twitch] GET /twitch/live logins={logins}")
    if not logins:
        return []
    if len(logins) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 logins per request")
    try:
        return await twitch.get_live_status(logins)
    except RuntimeError as e:
        # Twitch credentials not configured
        logger.warning(f"[twitch] Credentials not set: {e}")
        raise HTTPException(status_code=503, detail="Twitch integration not configured")
    except Exception as e:
        logger.error(f"[twitch] Live status error: {e}")
        raise HTTPException(status_code=502, detail=f"Twitch API error: {e}")
