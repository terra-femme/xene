import os
import time
import logging
import httpx
from datetime import datetime, timezone
from models import TwitchStream

logger = logging.getLogger(__name__)

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_STREAMS_URL = "https://api.twitch.tv/helix/streams"

# In-memory token store
_app_token: str | None = None
_token_expires_at: datetime | None = None

# In-memory live-status cache: { frozenset(logins): { "streams": list, "fetched_at": datetime } }
_live_cache: dict = {}
CACHE_TTL_SECONDS = 120  # 2 minutes — live status doesn't need sub-second freshness


def _client_id() -> str:
    v = os.environ.get("TWITCH_CLIENT_ID", "")
    if not v:
        raise RuntimeError("TWITCH_CLIENT_ID not set")
    return v


def _client_secret() -> str:
    v = os.environ.get("TWITCH_CLIENT_SECRET", "")
    if not v:
        raise RuntimeError("TWITCH_CLIENT_SECRET not set")
    return v


def _token_is_valid() -> bool:
    if not _app_token or not _token_expires_at:
        return False
    return datetime.now(timezone.utc) < _token_expires_at


async def _fetch_app_token() -> str:
    global _app_token, _token_expires_at
    logger.info("[twitch] Fetching new app access token")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            TWITCH_TOKEN_URL,
            params={
                "client_id": _client_id(),
                "client_secret": _client_secret(),
                "grant_type": "client_credentials",
            },
        )
        logger.info(f"[twitch] Token response status={resp.status_code}")
        resp.raise_for_status()
        data = resp.json()

    _app_token = data["access_token"]
    expires_in = data.get("expires_in", 3600) - 60  # 60s buffer before expiry
    _token_expires_at = datetime.fromtimestamp(time.time() + expires_in, tz=timezone.utc)
    logger.info(f"[twitch] App token acquired, expires in {expires_in}s")
    return _app_token


async def _get_token() -> str:
    if _token_is_valid():
        return _app_token
    return await _fetch_app_token()


def _cache_key(logins: list[str]) -> frozenset:
    return frozenset(login.lower() for login in logins)


def _is_cache_stale(key: frozenset) -> bool:
    entry = _live_cache.get(key)
    if not entry:
        return True
    age = (datetime.now(timezone.utc) - entry["fetched_at"]).total_seconds()
    stale = age > CACHE_TTL_SECONDS
    if not stale:
        logger.debug(f"[twitch] Cache hit for {set(key)}, age={age:.0f}s")
    return stale


async def get_live_status(logins: list[str]) -> list[TwitchStream]:
    """
    Check which of the given Twitch logins are currently live.
    Returns only the streams that are currently active.
    Results are cached for 2 minutes.
    """
    if not logins:
        logger.debug("[twitch] get_live_status called with empty logins list")
        return []

    key = _cache_key(logins)
    if not _is_cache_stale(key):
        return _live_cache[key]["streams"]

    logger.info(f"[twitch] Checking live status for {logins}")
    token = await _get_token()

    params = [("user_login", login) for login in logins]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            TWITCH_STREAMS_URL,
            params=params,
            headers={
                "Client-ID": _client_id(),
                "Authorization": f"Bearer {token}",
            },
        )
        logger.info(f"[twitch] Streams API status={resp.status_code}")
        logger.debug(f"[twitch] Streams response (first 500 chars): {resp.text[:500]}")
        resp.raise_for_status()
        data = resp.json()

    raw_streams = data.get("data", [])
    logger.info(f"[twitch] Got {len(raw_streams)} live stream(s) for logins={logins}")

    streams = []
    for s in raw_streams:
        # Thumbnail URL has {width}x{height} placeholders — replace with reasonable size
        thumb = s.get("thumbnail_url", "").replace("{width}", "640").replace("{height}", "360")
        login = s.get("user_login", "").lower()
        streams.append(TwitchStream(
            twitch_login=login,
            stream_title=s.get("title", ""),
            game_name=s.get("game_name", ""),
            viewer_count=s.get("viewer_count", 0),
            started_at=s.get("started_at"),
            thumbnail_url=thumb or None,
            stream_url=f"https://twitch.tv/{login}",
        ))

    _live_cache[key] = {
        "streams": streams,
        "fetched_at": datetime.now(timezone.utc),
    }
    return streams
