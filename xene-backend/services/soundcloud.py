import re
import os
import httpx
import logging
from models import FeedItem
from datetime import datetime, timezone, timedelta
from database import get_system_cache, set_system_cache, save_feed_items, get_cached_feed_items, set_last_polled

logger = logging.getLogger(__name__)

SC_OEMBED_URL = "https://soundcloud.com/oembed"
SC_API_BASE = "https://api.soundcloud.com"
SC_TOKEN_URL = f"{SC_API_BASE}/oauth2/token"

# In-memory secondary cache (still useful for super-fast response within a single request)
_cache: dict = {}
CACHE_TTL_SECONDS = 3600  # 1 hour for tracks

# User ID cache (soundcloud user IDs are static, cache for much longer)
_user_id_cache: dict = {}  # { username: { "user_id": str, "avatar_url": str|None, "bio": str|None, "fetched_at": datetime } }
USER_ID_CACHE_TTL_SECONDS = 604800  # 7 days

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Regex to find common platform URLs in bio text
_BIO_URL_PATTERNS = {
    "spotify": re.compile(r"open\.spotify\.com/(?:artist|user)/[a-zA-Z0-9]+"),
    "bandcamp": re.compile(r"[a-zA-Z0-9.-]+\.bandcamp\.com"),
    "patreon": re.compile(r"patreon\.com/[a-zA-Z0-9_-]+"),
    "gumroad": re.compile(r"gumroad\.com/[a-zA-Z0-9_-]+"),
    "instagram": re.compile(r"instagram\.com/[a-zA-Z0-9._-]+"),
    "youtube": re.compile(r"youtube\.com/(?:@|channel/|c/)[a-zA-Z0-9_-]+"),
    "twitter": re.compile(r"(?:twitter\.com|x\.com)/[a-zA-Z0-9_-]+"),
    "beatport": re.compile(r"beatport\.com/(?:artist|label)/[a-zA-Z0-9_-]+/\d+"),
    "discogs": re.compile(r"discogs\.com/(?:label|artist|release)/[0-9a-zA-Z._-]+"),
}

def extract_links_from_bio(bio_text: str) -> dict[str, str]:
    """Parse raw bio text for explicit intent links."""
    found = {}
    if not bio_text:
        return found
    for platform, pattern in _BIO_URL_PATTERNS.items():
        match = pattern.search(bio_text)
        if match:
            url = match.group(0)
            if not url.startswith("http"):
                url = "https://" + url
            found[platform] = url
    return found


def _is_stale(username: str) -> bool:
    entry = _cache.get(username)
    if not entry:
        return True
    age = (datetime.now(timezone.utc) - entry["fetched_at"]).total_seconds()
    return age > CACHE_TTL_SECONDS


async def _get_token(client: httpx.AsyncClient) -> str | None:
    """
    Fetch a client_credentials OAuth token from SoundCloud.
    Tokens are cached in Supabase until they expire (typically 1 hour).
    """
    token_key = "soundcloud_client_credentials"
    cached = get_system_cache(token_key)
    if cached and "access_token" in cached:
        logger.debug("[soundcloud] Using cached token from database")
        return cached["access_token"]

    client_id = os.environ.get("SC_CLIENT_ID") or os.environ.get("SOUNDCLOUD_CLIENT_ID")
    client_secret = os.environ.get("SC_CLIENT_SECRET") or os.environ.get("SOUNDCLOUD_CLIENT_SECRET")

    if not client_id or not client_secret:
        logger.warning("[soundcloud] SOUNDCLOUD_CLIENT_ID/SECRET not set — cannot get OAuth token")
        return None

    logger.info("[soundcloud] Fetching new OAuth token from SoundCloud")
    resp = await client.post(
        SC_TOKEN_URL,
        data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
        headers=_UA,
        timeout=10,
    )
    if resp.status_code != 200:
        logger.warning(f"[soundcloud] Token request failed: {resp.status_code} {resp.text[:200]}")
        return None

    data = resp.json()
    token = data.get("access_token")
    expires_in = data.get("expires_in", 3600)
    
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
    set_system_cache(token_key, {"access_token": token}, expires_at=expires_at)
    
    logger.info(f"[soundcloud] Obtained and cached OAuth token (expires in {expires_in}s)")
    return token


async def _resolve_user_info(username: str, client: httpx.AsyncClient) -> tuple[str, str | None, str | None]:
    """
    Resolve a SoundCloud permalink to user info using the official API.
    Caches result for 7 days. Returns (user_id, avatar_url, bio_text).
    """
    # Normalize: if username is a full URL, extract the actual username segment
    if "soundcloud.com/" in username:
        from urllib.parse import urlparse
        username = urlparse(username).path.strip("/").split("/")[0]
    elif "/" in username:
        username = username.strip("/").split("/")[0]
    
    # Check long-lived cache
    entry = _user_id_cache.get(username)
    if entry:
        age = (datetime.now(timezone.utc) - entry["fetched_at"]).total_seconds()
        if age < USER_ID_CACHE_TTL_SECONDS:
            return entry["user_id"], entry.get("avatar_url"), entry.get("bio")

    token = await _get_token(client)
    if not token:
        raise ValueError("Could not obtain SoundCloud token for resolution")

    logger.info(f"[soundcloud] Resolving profile via API: {username}")
    if len(username) > 100:
        logger.error(f"[soundcloud] Username too long for resolution: {username[:50]}...")
        raise ValueError(f"Invalid SoundCloud username: {username[:20]}...")

    profile_url = f"https://soundcloud.com/{username}"
    
    # Use official /resolve endpoint
    resp = await client.get(
        f"{SC_API_BASE}/resolve",
        params={"url": profile_url},
        headers={"Authorization": f"Bearer {token}", **_UA},
        timeout=10,
        follow_redirects=True
    )
    
    if resp.status_code != 200:
        logger.error(f"[soundcloud] API resolution failed for {username}: {resp.status_code}")
        if resp.status_code == 302:
             logger.error("[soundcloud] 302 found but not followed — check httpx config")
        # Last resort fallback to scrape if API resolve fails, but we prefer API
        raise ValueError(f"SoundCloud API could not resolve {username}")

    user_data = resp.json()
    user_id = str(user_data["id"])
    avatar_url = user_data.get("avatar_url", "").replace("-large.", "-t500x500.")
    bio_text = user_data.get("description")

    _user_id_cache[username] = {
        "user_id": user_id,
        "avatar_url": avatar_url,
        "bio": bio_text,
        "fetched_at": datetime.now(timezone.utc),
    }
    return user_id, avatar_url, bio_text


async def get_avatar_url(username: str) -> str | None:
    """Return cached SC avatar URL, fetching profile page if not yet resolved."""
    cached = _cache.get(username, {})
    if "avatar_url" in cached:
        return cached["avatar_url"]
    async with httpx.AsyncClient() as client:
        _, avatar_url, _ = await _resolve_user_info(username, client)
    _cache.setdefault(username, {})["avatar_url"] = avatar_url
    return avatar_url


async def get_tracks(username: str, display_name: str | None = None) -> list[FeedItem]:
    """
    Fetch tracks + reposts via SoundCloud API (client_credentials OAuth).
    Prefer database cache for efficiency.
    """
    # Normalize: AI sometimes stores a full SC URL instead of just the slug
    if "soundcloud.com/" in username:
        from urllib.parse import urlparse
        raw = username
        username = urlparse(username).path.strip("/").split("/")[0]
        logger.warning("[soundcloud] get_tracks received URL — normalized to username: %s (was: %s)", username, raw)
    elif "/" in username:
        username = username.strip("/").split("/")[0]

    # 1. Check in-memory secondary cache
    if not _is_stale(username):
        return _cache[username]["items"]

    async with httpx.AsyncClient() as client:
        token = await _get_token(client)
        if not token:
            return []

        # Resolve user ID from permalink
        try:
            user_id, avatar_url, _ = await _resolve_user_info(username, client)
        except Exception as e:
            logger.error(f"[soundcloud] Failed to resolve {username}: {e}")
            return []

        # Fetch tracks (this hits the /users/{id}/tracks endpoint which is the 'Tracks' tab)
        url = f"{SC_API_BASE}/users/{user_id}/tracks"
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}", **_UA})
        if resp.status_code != 200:
            logger.error(f"[soundcloud] API error: {resp.status_code} {resp.text[:200]}")
            return []

        data = resp.json()
        items = []
        for track in data:
            try:
                # SC API returns 'YYYY/MM/DD HH:MM:SS +0000'
                # Example: 2026/04/17 08:24:29 +0000
                raw_date = str(track["created_at"])
                # We need YYYY-MM-DDTHH:MM:SS+00:00
                parts = raw_date.split(" ")
                date_part = parts[0].replace("/", "-")
                time_part = parts[1]
                offset_part = parts[2].replace("+0000", "+00:00")
                
                pub_at = datetime.fromisoformat(f"{date_part}T{time_part}{offset_part}")
                
                items.append(FeedItem(
                    id=str(track["id"]),
                    platform="soundcloud",
                    # Use the display name we were given for the artist, 
                    # but the track title remains exactly as it is on SC.
                    artist_name=display_name or track.get("user", {}).get("username") or username,
                    content_type="track",
                    title=track["title"],
                    body=track.get("description"),
                    artwork_url=track.get("artwork_url") or avatar_url,
                    external_url=track["permalink_url"],
                    published_at=pub_at,
                    duration_seconds=int(track.get("duration", 0) / 1000),
                    play_count=track.get("playback_count"),
                    like_count=track.get("likes_count"),
                ))
            except Exception as e:
                logger.warning(f"[soundcloud] Skipping track {track.get('id')}: {e}")

        # Fetch reposts (artist's own reposts of other tracks)
        logger.info(f"[soundcloud] Fetching reposts for {username}")
        repost_url = f"{SC_API_BASE}/users/{user_id}/reposts/tracks"
        repost_resp = await client.get(repost_url, headers={"Authorization": f"Bearer {token}", **_UA})

        if repost_resp.status_code == 200:
            reposts_data = repost_resp.json()
            for track in reposts_data:
                try:
                    raw_date = str(track["created_at"])
                    parts = raw_date.split(" ")
                    date_part = parts[0].replace("/", "-")
                    time_part = parts[1]
                    offset_part = parts[2].replace("+0000", "+00:00")

                    pub_at = datetime.fromisoformat(f"{date_part}T{time_part}{offset_part}")

                    items.append(FeedItem(
                        id=str(track["id"]),
                        platform="soundcloud",
                        artist_name=display_name or track.get("user", {}).get("username") or username,
                        content_type="track",
                        title=track["title"],
                        body=track.get("description"),
                        artwork_url=track.get("artwork_url") or avatar_url,
                        external_url=track["permalink_url"],
                        published_at=pub_at,
                        duration_seconds=int(track.get("duration", 0) / 1000),
                        play_count=track.get("playback_count"),
                        like_count=track.get("likes_count"),
                    ))
                except Exception as e:
                    logger.warning(f"[soundcloud] Skipping repost {track.get('id')}: {e}")
            logger.info(f"[soundcloud] Got {len(reposts_data)} reposts for {username}")
        else:
            logger.warning(f"[soundcloud] Could not fetch reposts for {username}: {repost_resp.status_code}")

        # Fetch playlist/set reposts (labels release music as sets — this was never called before)
        logger.info(f"[soundcloud] Fetching playlist reposts for {username}")
        playlist_repost_url = f"{SC_API_BASE}/users/{user_id}/reposts/playlists"
        pl_resp = await client.get(playlist_repost_url, headers={"Authorization": f"Bearer {token}", **_UA})

        if pl_resp.status_code == 200:
            pl_reposts_data = pl_resp.json()
            artist_lower = (display_name or username).lower()
            skipped = 0

            for pl in pl_reposts_data:
                try:
                    uploader = pl.get("user", {}).get("username", "").lower()
                    title = pl.get("title", "")

                    if uploader != username.lower() and artist_lower not in title.lower():
                        skipped += 1
                        logger.debug(f"[soundcloud] Skip playlist repost '{title}' — not credited to {display_name or username}")
                        continue

                    raw_date = str(pl["created_at"])
                    parts = raw_date.split(" ")
                    date_part = parts[0].replace("/", "-")
                    time_part = parts[1]
                    offset_part = parts[2].replace("+0000", "+00:00")
                    pub_at = datetime.fromisoformat(f"{date_part}T{time_part}{offset_part}")

                    items.append(FeedItem(
                        id=f"playlist-{pl['id']}",
                        platform="soundcloud",
                        artist_name=display_name or username,
                        content_type="release",
                        title=title,
                        body=pl.get("description"),
                        artwork_url=pl.get("artwork_url") or avatar_url,
                        external_url=pl["permalink_url"],
                        published_at=pub_at,
                        track_count=pl.get("track_count"),
                    ))
                except Exception as e:
                    logger.warning(f"[soundcloud] Skipping playlist repost {pl.get('id')}: {e}")

            logger.info(f"[soundcloud] Got {len(pl_reposts_data) - skipped} matching playlist reposts ({skipped} skipped) for {username}")
        else:
            logger.warning(f"[soundcloud] Could not fetch playlist reposts for {username}: {pl_resp.status_code}")

    logger.info(f"[soundcloud] Built {len(items)} FeedItems for {username}")

    # Save to database cache
    db_items = [
        {
            "platform": item.platform,
            "internal_id": item.id,
            "artist_name": item.artist_name,
            "content_type": item.content_type,
            "title": item.title,
            "body": item.body,
            "artwork_url": item.artwork_url,
            "external_url": item.external_url,
            "published_at": item.published_at.isoformat(),
            "duration_seconds": item.duration_seconds,
            "play_count": item.play_count,
            "like_count": item.like_count,
            "track_count": item.track_count,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        for item in items
    ]
    save_feed_items(db_items)
    set_last_polled("soundcloud", display_name or username)

    _cache[username] = {
        "items": items,
        "fetched_at": datetime.now(timezone.utc),
    }
    return items


async def get_artist_reposts_by_label(label_username: str, target_artists: list[str]) -> list[FeedItem]:
    """
    Fetch reposts from a label, filtered to only include ones crediting target artists.
    Example: label "XL Recordings" reposts Arca — if Arca is in target_artists, include it.
    """
    if "soundcloud.com/" in label_username:
        from urllib.parse import urlparse
        label_username = urlparse(label_username).path.strip("/").split("/")[0]
    elif "/" in label_username:
        label_username = label_username.strip("/").split("/")[0]

    async with httpx.AsyncClient() as client:
        token = await _get_token(client)
        if not token:
            logger.warning(f"[soundcloud] Could not obtain token for repost fetch from {label_username}")
            return []

        try:
            label_id, _, _ = await _resolve_user_info(label_username, client)
        except Exception as e:
            logger.error(f"[soundcloud] Failed to resolve label {label_username}: {e}")
            return []

        # Fetch label's reposts
        url = f"{SC_API_BASE}/users/{label_id}/reposts/tracks"
        logger.info(f"[soundcloud] Fetching reposts from {label_username} (ID: {label_id})")
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}", **_UA})
        if resp.status_code != 200:
            logger.error(f"[soundcloud] Reposts API error for {label_username}: {resp.status_code}")
            return []

        reposts_data = resp.json()
        items = []
        target_lower = [a.lower() for a in target_artists]

        for repost in reposts_data:
            try:
                track = repost
                original_artist = track.get("user", {}).get("username", "").lower()

                # Filter: only include if original artist is in our target list
                if original_artist not in target_lower:
                    logger.debug(f"[soundcloud] Skipping repost — {original_artist} not in target artists")
                    continue

                raw_date = str(track["created_at"])
                parts = raw_date.split(" ")
                date_part = parts[0].replace("/", "-")
                time_part = parts[1]
                offset_part = parts[2].replace("+0000", "+00:00")
                pub_at = datetime.fromisoformat(f"{date_part}T{time_part}{offset_part}")

                items.append(FeedItem(
                    id=str(track["id"]),
                    platform="soundcloud",
                    artist_name=track.get("user", {}).get("username") or original_artist,
                    content_type="track",
                    title=track["title"],
                    body=track.get("description"),
                    artwork_url=track.get("artwork_url"),
                    external_url=track["permalink_url"],
                    published_at=pub_at,
                    duration_seconds=int(track.get("duration", 0) / 1000),
                    play_count=track.get("playback_count"),
                    like_count=track.get("likes_count"),
                ))
            except Exception as e:
                logger.warning(f"[soundcloud] Skipping repost {track.get('id')}: {e}")

        logger.info(f"[soundcloud] Got {len(items)} matching reposts from {label_username}")

        # Save to database cache
        if items:
            db_items = [
                {
                    "platform": item.platform,
                    "internal_id": item.id,
                    "artist_name": item.artist_name,
                    "content_type": item.content_type,
                    "title": item.title,
                    "body": item.body,
                    "artwork_url": item.artwork_url,
                    "external_url": item.external_url,
                    "published_at": item.published_at.isoformat(),
                    "duration_seconds": item.duration_seconds,
                    "play_count": item.play_count,
                    "like_count": item.like_count,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                for item in items
            ]
            save_feed_items(db_items)

        return items


async def get_oembed(track_url: str) -> dict:
    """Fetch oEmbed data for a SoundCloud URL."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(SC_OEMBED_URL, params={"url": track_url, "format": "json"})
        resp.raise_for_status()
        return resp.json()


def invalidate_cache(username: str | None = None):
    """Force a re-fetch on next request. Pass None to clear all."""
    if username:
        _cache.pop(username, None)
    else:
        _cache.clear()
