import os
import re
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from models import BeatportArtist, BeatportRelease

logger = logging.getLogger(__name__)

API_BASE = "https://api.beatport.com/v4"

# Regex patterns adapted from beets-beatport4 (MIT)
_SCRIPT_SRC_PATTERN = re.compile(r'src=["\']([^"\']*\.js[^"\']*)["\']')
_CLIENT_ID_PATTERN = re.compile(r"API_CLIENT_ID:\s*['\"]([^'\"]+)['\"]")

# In-memory token cache
_access_token: str | None = None
_token_expires_at: datetime | None = None

# In-memory client_id cache (changes rarely — only when Beatport redeploys docs)
_client_id_cache: str | None = None

REDIRECT_URI = f"{API_BASE}/auth/o/post-message/"


def _bp_username() -> str:
    v = os.environ.get("BEATPORT_USERNAME", "")
    if not v:
        raise RuntimeError("BEATPORT_USERNAME not set")
    return v


def _bp_password() -> str:
    v = os.environ.get("BEATPORT_PASSWORD", "")
    if not v:
        raise RuntimeError("BEATPORT_PASSWORD not set")
    return v


def _token_is_valid() -> bool:
    if not _access_token or not _token_expires_at:
        return False
    return datetime.now(timezone.utc) < _token_expires_at


async def _fetch_client_id() -> str:
    """Scrape the public API_CLIENT_ID from Beatport's docs JS bundle."""
    global _client_id_cache
    if _client_id_cache:
        logger.debug("[beatport] Using cached client_id")
        return _client_id_cache

    logger.info("[beatport] Fetching client_id from docs page")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{API_BASE}/docs/")
        resp.raise_for_status()
        html = resp.text

    script_urls = _SCRIPT_SRC_PATTERN.findall(html)
    logger.info(f"[beatport] Found {len(script_urls)} script tags in docs page")

    async with httpx.AsyncClient(timeout=15) as client:
        for src in script_urls:
            url = src if src.startswith("http") else f"https://api.beatport.com{src}"
            try:
                js_resp = await client.get(url)
                js_resp.raise_for_status()
                js = js_resp.text
                matches = _CLIENT_ID_PATTERN.findall(js)
                if matches:
                    _client_id_cache = matches[0]
                    logger.info(f"[beatport] Found client_id in {url}")
                    return _client_id_cache
            except Exception as exc:
                logger.debug(f"[beatport] Script fetch failed for {url}: {exc}")

    raise RuntimeError("[beatport] Could not extract API_CLIENT_ID from docs page")


async def _authenticate() -> str:
    """
    Full Beatport OAuth flow:
      1. POST /auth/login/ — session cookie
      2. GET  /auth/o/authorize/ — auth code via redirect
      3. POST /auth/o/token/ — exchange code for bearer token
    """
    global _access_token, _token_expires_at

    client_id = await _fetch_client_id()
    username = _bp_username()
    password = _bp_password()

    logger.info(f"[beatport] Starting OAuth flow for user={username}")

    # httpx.AsyncClient persists cookies across requests within the same instance
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        # Step 1: login to establish session + CSRF cookie
        login_resp = await client.post(
            f"{API_BASE}/auth/login/",
            json={"username": username, "password": password},
        )
        logger.info(f"[beatport] Login status={login_resp.status_code}")
        login_resp.raise_for_status()
        login_data = login_resp.json()

        if "username" not in login_data:
            raise RuntimeError(f"[beatport] Login failed: {login_data}")
        logger.info(f"[beatport] Logged in as {login_data.get('username')}")

        # Step 2: get authorization code
        auth_url = (
            f"{API_BASE}/auth/o/authorize/?"
            + urlencode({
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": REDIRECT_URI,
            })
        )
        logger.info(f"[beatport] Requesting auth code from {auth_url}")
        auth_resp = await client.get(auth_url)
        logger.info(
            f"[beatport] Authorize status={auth_resp.status_code} "
            f"location={auth_resp.headers.get('Location', 'none')[:80]}"
        )

        location = auth_resp.headers.get("Location", "")
        if not location:
            body_snippet = auth_resp.text[:300]
            raise RuntimeError(
                f"[beatport] No Location header in authorize response. "
                f"Body: {body_snippet}"
            )

        parsed = urlparse(location)
        codes = parse_qs(parsed.query).get("code")
        if not codes:
            raise RuntimeError(
                f"[beatport] No code param in redirect: {location}"
            )
        auth_code = codes[0]
        logger.debug(f"[beatport] Got auth code (length={len(auth_code)})")

        # Step 3: exchange code for token
        token_resp = await client.post(
            f"{API_BASE}/auth/o/token/",
            params={
                "code": auth_code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
                "client_id": client_id,
            },
        )
        logger.info(f"[beatport] Token exchange status={token_resp.status_code}")
        token_resp.raise_for_status()
        token_data = token_resp.json()

    _access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", 36000) - 60
    _token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    logger.info(f"[beatport] Token acquired, expires in {expires_in}s")
    return _access_token


async def _get_token() -> str:
    if _token_is_valid():
        return _access_token
    return await _authenticate()


async def search_artists(query: str, limit: int = 10) -> list[BeatportArtist]:
    """
    Search Beatport catalog for artists matching the query string.
    Used at add-artist time to discover and store the canonical Beatport artist ID.
    """
    logger.info(f"[beatport] Searching artists query={query!r} limit={limit}")
    token = await _get_token()

    # Try the dedicated catalog/artists endpoint first (more precise than search)
    params = {"q": query, "per_page": min(limit, 25), "page": 1}
    logger.debug(f"[beatport] Artist search params={params}")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{API_BASE}/catalog/artists/",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "Xene/0.1 +https://xene.app",
            },
        )
        logger.info(f"[beatport] Artist search status={resp.status_code}")
        logger.debug(f"[beatport] Artist search response (first 500): {resp.text[:500]}")

        if resp.status_code == 200:
            data = resp.json()
            raw = data.get("results", data) if isinstance(data, dict) else data
        else:
            # Fallback: use the general search endpoint with type=artists
            logger.warning(
                f"[beatport] catalog/artists/ returned {resp.status_code}, "
                "falling back to catalog/search"
            )
            fallback = await client.get(
                f"{API_BASE}/catalog/search/",
                params={"q": query, "type": "artists", "per_page": min(limit, 25)},
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "Xene/0.1 +https://xene.app",
                },
            )
            logger.info(f"[beatport] Fallback search status={fallback.status_code}")
            logger.debug(f"[beatport] Fallback response (first 500): {fallback.text[:500]}")
            fallback.raise_for_status()
            fdata = fallback.json()
            raw = fdata.get("artists", fdata.get("results", []))

    logger.info(f"[beatport] Got {len(raw)} artist candidate(s) for {query!r}")
    if not raw:
        logger.warning(f"[beatport] No artists found for query={query!r}")

    artists = []
    for a in raw[:limit]:
        artist_id = str(a.get("id", ""))
        slug = a.get("slug", "")
        image = a.get("image", {})
        image_url = image.get("uri") or image.get("dynamic_uri") if image else None
        if image_url and "{w}" in image_url:
            image_url = image_url.replace("{w}", "200").replace("{h}", "200")

        artists.append(BeatportArtist(
            beatport_id=artist_id,
            name=a.get("name", ""),
            slug=slug or None,
            image_url=image_url,
            artist_url=(
                f"https://www.beatport.com/artist/{slug}/{artist_id}"
                if slug and artist_id
                else "https://www.beatport.com"
            ),
        ))

    return artists


async def get_artist_releases(
    artist_name: str,
    limit: int = 10,
) -> list[BeatportRelease]:
    """
    Search Beatport catalog for recent releases by artist name.
    Returns up to `limit` releases sorted by publish date descending.
    """
    logger.info(f"[beatport] Fetching releases for artist={artist_name!r} limit={limit}")
    token = await _get_token()

    params = {
        "q": artist_name,
        "type": "releases",
        "per_page": min(limit, 25),
    }
    logger.debug(f"[beatport] Search params={params}")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{API_BASE}/catalog/search/",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "Xene/0.1 +https://xene.app",
            },
        )
        logger.info(f"[beatport] Search status={resp.status_code}")
        logger.debug(f"[beatport] Search response (first 500): {resp.text[:500]}")
        resp.raise_for_status()
        data = resp.json()

    raw_releases = data.get("releases", [])
    logger.info(f"[beatport] Got {len(raw_releases)} release(s) for {artist_name!r}")
    if not raw_releases:
        logger.warning(f"[beatport] No releases found for artist={artist_name!r}")

    releases = []
    for r in raw_releases[:limit]:
        artists_list = [a.get("name", "") for a in r.get("artists", [])]
        artwork = r.get("image", {})
        artwork_url = artwork.get("uri") or artwork.get("dynamic_uri")
        if artwork_url and "{w}" in artwork_url:
            artwork_url = artwork_url.replace("{w}", "400").replace("{h}", "400")

        slug = r.get("slug", "")
        release_id = r.get("id", "")
        beatport_url = (
            f"https://www.beatport.com/release/{slug}/{release_id}"
            if slug and release_id
            else "https://www.beatport.com"
        )

        releases.append(BeatportRelease(
            beatport_id=str(release_id),
            title=r.get("name", ""),
            artists=artists_list,
            label=r.get("label", {}).get("name") if r.get("label") else None,
            artwork_url=artwork_url,
            release_url=beatport_url,
            published_at=r.get("publish_date") or r.get("new_release_date"),
            track_count=r.get("track_count", 0),
        ))

    return releases


async def get_artist_releases_by_id(
    artist_id: int | str,
    limit: int = 10,
) -> list[BeatportRelease]:
    """
    Fetch releases directly by Beatport artist ID.
    More precise than search — use when you have the artist's Beatport ID stored.
    """
    logger.info(f"[beatport] Fetching releases for artist_id={artist_id} limit={limit}")
    token = await _get_token()

    params = {"artist_id": artist_id, "per_page": min(limit, 25), "page": 1}
    logger.debug(f"[beatport] Releases by ID params={params}")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{API_BASE}/catalog/releases/",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "Xene/0.1 +https://xene.app",
            },
        )
        logger.info(f"[beatport] Releases by ID status={resp.status_code}")
        logger.debug(f"[beatport] Response (first 500): {resp.text[:500]}")
        resp.raise_for_status()
        data = resp.json()

    raw_releases = data.get("results", data) if isinstance(data, dict) else data
    logger.info(f"[beatport] Got {len(raw_releases)} release(s) for artist_id={artist_id}")
    if not raw_releases:
        logger.warning(f"[beatport] No releases found for artist_id={artist_id}")

    releases = []
    for r in raw_releases[:limit]:
        artists_list = [a.get("name", "") for a in r.get("artists", [])]
        artwork = r.get("image", {})
        artwork_url = artwork.get("uri") or artwork.get("dynamic_uri")
        if artwork_url and "{w}" in artwork_url:
            artwork_url = artwork_url.replace("{w}", "400").replace("{h}", "400")

        slug = r.get("slug", "")
        release_id = r.get("id", "")
        beatport_url = (
            f"https://www.beatport.com/release/{slug}/{release_id}"
            if slug and release_id
            else "https://www.beatport.com"
        )

        releases.append(BeatportRelease(
            beatport_id=str(release_id),
            title=r.get("name", ""),
            artists=artists_list,
            label=r.get("label", {}).get("name") if r.get("label") else None,
            artwork_url=artwork_url,
            release_url=beatport_url,
            published_at=r.get("publish_date") or r.get("new_release_date"),
            track_count=r.get("track_count", 0),
        ))

    return releases
