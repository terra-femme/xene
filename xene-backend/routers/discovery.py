import asyncio
import logging
import os
import re
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from database import get_db
from models import ArtistCreate, ArtistOut
from services import platform_utils
from services.identity_engine import (
    calculate_node_confidence,
    compute_cross_verified,
    map_ai_result_to_artist_fields,
)
from services.llm_discovery import (
    fetch_soundcloud_web_profile_breadcrumbs,
    get_llm_orchestrator,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("/status")
async def discovery_status() -> dict[str, Any]:
    """Whether any LLM provider is configured and which water-fall is active."""
    o = get_llm_orchestrator()
    return {
        "hasProviders": o.has_providers(),
        "providers": o.describe_providers(),
    }


from services.soundcloud import _resolve_user_info, extract_links_from_bio, _UA
import httpx

@router.get("/auto-discover")
async def auto_discover(
    name: str = Query(..., min_length=1, description="Artist display name to scan"),
    sc_profile_url: str | None = Query(
        default=None, description="Optional SoundCloud profile URL for official web-profile hints"
    ),
) -> dict[str, Any]:
    """
    Relational Identity Walk (v2.7):
    1. Listen to Artist first (SC bio + web-profiles).
    2. Multi-hop Discogs if found in bio.
    3. Recursive AI scouting for missing platforms.
    4. Write only HIGH-authority links to mapped; hold LLM inferences as suggested_*.

    Authority model:
    - HIGH: SC web-profiles (API network map), SC bio (artist's own words), Discogs API (curated external links)
    - MEDIUM: Beatport search match with name similarity 0.72–0.84
    - LOW / not saved: LLM-inferred IDs (held as suggested_* fields, never written to DB)
    """
    from difflib import SequenceMatcher

    o = get_llm_orchestrator()
    if not o.has_providers():
        raise HTTPException(status_code=503, detail="LLM providers not configured")

    n = name.strip()
    sc_bio = None
    sc_username = None
    discogs_context: dict[str, Any] | None = None

    # Source-tracked link buckets — each bucket is HIGH authority by definition.
    # Web-profile wins over bio if both have the same platform key.
    sc_bio_links: dict[str, str] = {}         # SC bio regex extraction
    sc_webprofile_links: dict[str, str] = {}  # SC web-profiles API (network → URL)
    discogs_links: dict[str, str] = {}        # Discogs entity profile external URLs

    explicit_links: dict[str, str] = {}       # merged view for LLM context + field writing

    # 1. Listen to Artist (Seed Phase)
    if sc_profile_url:
        try:
            from urllib.parse import urlparse
            sc_username = urlparse(sc_profile_url).path.strip("/").split("/")[0]
            logger.info("[discovery] Seed username: %s from %s", sc_username, sc_profile_url)

            async with httpx.AsyncClient() as client:
                _user_id, _, sc_bio = await _resolve_user_info(sc_username, client)

                from services.soundcloud import _get_token
                system_token = await _get_token(client)

                from services.llm_discovery import fetch_soundcloud_web_profile_breadcrumbs
                web_profiles = await fetch_soundcloud_web_profile_breadcrumbs(sc_profile_url, system_token)

                sc_bio_links = extract_links_from_bio(sc_bio)
                for net, pinfo in web_profiles.items():
                    if pinfo.get("url"):
                        sc_webprofile_links[net] = pinfo["url"]
                        logger.info("[discovery] [HIGH][SC-web-profile] %s → %s", net, pinfo["url"])

            # Web-profile beats bio for the same platform key
            explicit_links = {**sc_bio_links, **sc_webprofile_links}
            logger.info(
                "[discovery] Explicit links — bio=%d web-profile=%d total=%d for %s",
                len(sc_bio_links), len(sc_webprofile_links), len(explicit_links), n,
            )
        except Exception as e:
            logger.warning("[discovery] SoundCloud seed extraction failed: %s", e, exc_info=True)

    # 1b. Multi-hop Discogs — curated external URLs (Bandcamp, Beatport, etc.)
    if explicit_links.get("discogs"):
        try:
            from services import discogs as discogs_svc
            logger.info("[discovery] [HIGH] Discogs multi-hop: %s", explicit_links["discogs"])
            discogs_data = await discogs_svc.fetch_entity_links(explicit_links["discogs"])
            if discogs_data:
                discogs_context = discogs_data
                logger.info(
                    "[discovery] Discogs enrichment: canonical_name='%s', links=%s",
                    discogs_data.get("name"), list(discogs_data.get("links", {}).keys()),
                )
                for p, url in discogs_data.get("links", {}).items():
                    if p not in explicit_links:
                        explicit_links[p] = url
                        discogs_links[p] = url
                        logger.info("[discovery] [HIGH][Discogs] %s → %s", p, url)

                canonical_name = discogs_data.get("name", "")
                profile_excerpt = (discogs_data.get("profile") or "")[:600]
                discogs_note = (
                    f"\n\n[Discogs Profile — Verified External Source]\n"
                    f"Canonical Name: {canonical_name}\n"
                    f"Profile: {profile_excerpt}"
                )
                sc_bio = (sc_bio or "") + discogs_note
                logger.info("[discovery] Discogs canonical name '%s' appended to LLM context", canonical_name)
        except Exception as e:
            logger.warning("[discovery] Discogs multi-hop failed: %s", e, exc_info=True)

    # 2. Recursive AI Walk
    logger.info("[discovery] Recursive walk for: %s", n)
    ai_data = await o.recursive_identity_walk(n, sc_bio, explicit_links)
    discovery_provider = (ai_data or {}).pop("_provider", "unknown")
    logger.info("[discovery] Walk answered by: %s", discovery_provider)

    # 3. Identity Normalization
    mapped = map_ai_result_to_artist_fields(ai_data or {}, artist_name=n)

    # --- SPOTIFY WRITE GATE ---
    # LLM Spotify IDs pass format checks but are unverifiable — only write from explicit sources.
    ai_spotify_id = mapped.pop("spotify_id", None)
    mapped.pop("spotify_url", None)
    if ai_spotify_id:
        mapped["suggested_spotify_id"] = ai_spotify_id
        logger.warning("[discovery] Spotify ID from LLM held as suggested_spotify_id (not saved): %s", ai_spotify_id)

    # --- POWER ALIAS MAP ---
    _POWER_ALIASES = {
        "planet v": "V Recordings",
        "liquid v": "V Recordings",
        "chronic": "V Recordings",
        "philly blunt": "V Recordings",
    }
    search_n = n.lower().strip()
    if search_n in _POWER_ALIASES:
        canonical_n = _POWER_ALIASES[search_n]
        mapped["name"] = canonical_n
        logger.info("[discovery] Power Alias: %r → %r", n, canonical_n)
    else:
        canonical_n = mapped.get("name", n)

    # --- SOUNDCLOUD AUTHORITY (seed URL is user-provided, inherently HIGH) ---
    if sc_username:
        mapped["soundcloud_username"] = sc_username
        mapped["soundcloud_authority"] = "HIGH"
        if not mapped.get("soundcloud_url"):
            mapped["soundcloud_url"] = platform_utils.get_canonical_url("soundcloud", sc_username)
        logger.info("[discovery] [HIGH] SoundCloud username from seed (LOCKED): %s", sc_username)
        # Mark as locked so later AI extraction doesn't overwrite it
        mapped["_soundcloud_locked"] = True

    is_label = mapped.get("entity_type") in ("label", "organization")

    # --- PROACTIVE DISCOGS SEARCH ---
    # If no Discogs URL was found in the SC bio or web-profiles, search Discogs by canonical
    # name. This is the critical path for labels like Planet V / V Recordings whose SC bio
    # does not link to Discogs but whose Discogs entry lists Bandcamp and Beatport URLs.
    # Running this BEFORE the Beatport gate means a Discogs-sourced Beatport URL will cause
    # the Beatport search to be skipped entirely — we use the verified URL directly.
    if discogs_context is None:
        try:
            from services import discogs as discogs_svc
            dg_entity_type = "label" if is_label else "artist"
            logger.info(
                "[discovery] No Discogs URL in SC bio — proactive search for '%s' (%s)",
                canonical_n, dg_entity_type,
            )
            discogs_data = await discogs_svc.search_entity(canonical_n, dg_entity_type)
            if discogs_data:
                discogs_context = discogs_data
                logger.info(
                    "[discovery] Proactive Discogs match: canonical_name='%s', links=%s",
                    discogs_data.get("name"), list(discogs_data.get("links", {}).keys()),
                )
                for p, url in discogs_data.get("links", {}).items():
                    if p not in explicit_links:
                        explicit_links[p] = url
                        discogs_links[p] = url
                        logger.info("[discovery] [HIGH][Discogs-proactive] %s → %s", p, url)
            else:
                logger.info("[discovery] Proactive Discogs search: no confident match for '%s'", canonical_n)
        except Exception as e:
            logger.warning("[discovery] Proactive Discogs search failed: %s", e, exc_info=True)

    # --- BEATPORT TRUTH RECONCILIATION (name-similarity gated) ---
    from services import beatport as beatport_svc
    beatport_from_explicit = "beatport" in explicit_links

    def _name_sim(a: str, b: str) -> float:
        a_n, b_n = a.lower().strip(), b.lower().strip()
        ratio = SequenceMatcher(None, a_n, b_n).ratio()
        # Boost prefix matches: handles labels that append a city for disambiguation.
        # e.g. "Sofa Sound" (Beatport) vs "Sofa Sound Bristol" (xene) — "Sofa Sound" is
        # a word-boundary prefix of the longer name, so it's a strong match.
        shorter, longer = (a_n, b_n) if len(a_n) <= len(b_n) else (b_n, a_n)
        if shorter and longer.startswith(shorter + " "):
            ratio = max(ratio, 0.75)
        return ratio

    if beatport_from_explicit:
        # Explicit Beatport URL from SC bio or Discogs — already handled in the loop below
        logger.info("[discovery] Beatport URL from explicit source — search skipped")
    elif is_label:
        logger.info("[discovery] Beatport search: label '%s' (limit=5)", canonical_n)
        bp_results = await beatport_svc.search_labels(canonical_n, limit=5)
        if bp_results:
            aliases = [canonical_n] + list((discogs_context or {}).get("aliases", []))
            best_match: dict | None = None
            best_score = 0.0
            for candidate in bp_results:
                score = max(_name_sim(candidate["name"], alias) for alias in aliases)
                logger.debug("[discovery] Beatport candidate '%s' sim=%.2f", candidate["name"], score)
                if score > best_score:
                    best_score = score
                    best_match = candidate

            if best_match and best_score >= 0.72:
                mapped["beatport_artist_id"] = best_match["id"]
                mapped["beatport_url"] = best_match["url"]
                mapped["beatport_artist_name"] = best_match["name"]
                mapped["beatport_authority"] = "HIGH" if best_score >= 0.85 else "MEDIUM"
                logger.info(
                    "[discovery] Beatport label matched: '%s' id=%s sim=%.2f authority=%s",
                    best_match["name"], best_match["id"], best_score, mapped["beatport_authority"],
                )
            else:
                logger.warning(
                    "[discovery] Beatport rejected all label candidates (best_sim=%.2f) for '%s' — not writing",
                    best_score, canonical_n,
                )
                mapped.pop("beatport_artist_id", None)
                mapped.pop("beatport_url", None)
    else:
        logger.info("[discovery] Beatport search: artist '%s' (limit=5)", canonical_n)
        bp_results = await beatport_svc.search_artists(canonical_n, limit=5)
        if bp_results:
            aliases = [canonical_n]
            best_match_artist = None
            best_score = 0.0
            for candidate in bp_results:
                score = max(_name_sim(candidate.name, alias) for alias in aliases)
                logger.debug("[discovery] Beatport candidate '%s' sim=%.2f", candidate.name, score)
                if score > best_score:
                    best_score = score
                    best_match_artist = candidate

            if best_match_artist and best_score >= 0.72:
                mapped["beatport_artist_id"] = best_match_artist.beatport_id
                mapped["beatport_url"] = best_match_artist.artist_url
                mapped["beatport_artist_name"] = best_match_artist.name
                mapped["beatport_authority"] = "HIGH" if best_score >= 0.85 else "MEDIUM"
                logger.info(
                    "[discovery] Beatport artist matched: '%s' id=%s sim=%.2f authority=%s",
                    best_match_artist.name, best_match_artist.beatport_id, best_score, mapped["beatport_authority"],
                )
            else:
                logger.warning(
                    "[discovery] Beatport rejected all artist candidates (best_sim=%.2f) for '%s' — not writing",
                    best_score, canonical_n,
                )
                mapped.pop("beatport_artist_id", None)
                mapped.pop("beatport_url", None)

    # --- EXPLICIT LINK FIELD MAPPING WITH SOURCE AUTHORITY ---
    # All three source buckets (SC bio, SC web-profiles, Discogs) are HIGH authority.
    # SC explicit links always win over Discogs if both have the same platform.

    def _link_source(platform: str) -> str:
        if platform in sc_webprofile_links:
            return "SC-web-profile"
        if platform in sc_bio_links:
            return "SC-bio"
        if platform in discogs_links:
            return "Discogs"
        return "unknown"

    all_edges = ai_data.get("suggestedEdges", []) if ai_data else []

    for p, url in explicit_links.items():
        raw_id = url.rstrip("/").split("/")[-1]
        # Strip query parameters (e.g., ?si=... from Spotify share links)
        if "?" in raw_id:
            raw_id = raw_id.split("?")[0]
        source = _link_source(p)

        # CRITICAL: Guard against overwriting HIGH-authority sources that were already set
        if p == "soundcloud" and mapped.get("_soundcloud_locked"):
            logger.warning(
                "[discovery] SKIPPED soundcloud field from %s (already locked from seed URL): %s",
                source, raw_id
            )
            continue

        if p == "spotify":
            if platform_utils.validate_id("spotify", raw_id):
                mapped["spotify_id"] = raw_id
                mapped["spotify_url"] = platform_utils.get_canonical_url("spotify", raw_id)
                mapped["spotify_authority"] = "HIGH"
                mapped.pop("suggested_spotify_id", None)  # Confirmed — clear the tentative hold
                logger.info("[discovery] [HIGH][%s] Spotify: %s", source, raw_id)
            else:
                logger.warning("[discovery] Spotify ID from explicit link failed format check: %s", raw_id)
        elif p == "bandcamp":
            canonical_bc = platform_utils.get_canonical_url("bandcamp", url)
            if canonical_bc:
                mapped["bandcamp_url"] = canonical_bc
                mapped["bandcamp_authority"] = "HIGH"
                logger.info("[discovery] [HIGH][%s] Bandcamp: %s", source, canonical_bc)
        elif p == "youtube":
            if platform_utils.validate_id("youtube", raw_id):
                mapped["youtube_channel_id"] = raw_id
                mapped["youtube_url"] = platform_utils.get_canonical_url("youtube", raw_id)
                mapped["youtube_authority"] = "HIGH"
                logger.info("[discovery] [HIGH][%s] YouTube: %s", source, raw_id)
        elif p == "instagram":
            clean = raw_id.lstrip("@")
            mapped["instagram_username"] = clean
            mapped["instagram_url"] = platform_utils.get_canonical_url("instagram", clean)
            mapped["instagram_authority"] = "HIGH"
            logger.info("[discovery] [HIGH][%s] Instagram: %s", source, clean)
        elif p == "twitter":
            clean = raw_id.lstrip("@")
            mapped["twitter_username"] = clean
            mapped["twitter_url"] = platform_utils.get_canonical_url("twitter", clean)
            mapped["twitter_authority"] = "HIGH"
            logger.info("[discovery] [HIGH][%s] Twitter: %s", source, clean)
        elif p == "beatport":
            bp_m = re.search(r"/(?:label|artist)/[^/]+/(\d+)", url)
            if bp_m:
                bp_id = bp_m.group(1)
                mapped["beatport_artist_id"] = bp_id
                mapped["beatport_url"] = platform_utils.get_canonical_url(
                    "beatport", bp_id, mapped.get("entity_type", "artist")
                )
                mapped["beatport_authority"] = "HIGH"
                logger.info("[discovery] [HIGH][%s] Beatport from explicit URL: id=%s", source, bp_id)
        elif p == "discogs":
            pass  # Context only — no DB column

        if p != "discogs":
            all_edges.append({
                "targetName": f"{p}: {raw_id}",
                "relationship": "Verified Link",
                "type": "EXPLICIT_BIO_LINK",
                "source": source,
            })
        else:
            all_edges.append({
                "targetName": f"discogs: {url}",
                "relationship": "Multi-hop Source",
                "type": "VERIFIED_EXTERNAL_LINK",
                "source": source,
            })

    mapped["edges"] = all_edges

    if mapped.get("analysis"):
        mapped["analysis"] = f"[via {discovery_provider}] {mapped['analysis']}"
    elif discovery_provider != "unknown":
        mapped["analysis"] = f"[via {discovery_provider}] No detailed analysis returned."

    # Clean up internal flags before response
    mapped.pop("_soundcloud_locked", None)

    # 4. System Layer Scoring
    scores = calculate_node_confidence(mapped)

    # --- VERIFIED-ONLY RETURN GATE ---
    # A field only reaches the return dict (and therefore the DB) if its authority was
    # explicitly set to HIGH or MEDIUM by a verified source (SC bio, SC web-profile, Discogs,
    # or a Beatport search candidate that cleared the name-similarity threshold).
    #
    # LLM-inferred values that were never confirmed by a real source are returned as
    # suggested_* so the discovery UI can surface them for human review — but they are
    # never written to canonical DB columns.

    def _verified(field: str, auth_key: str) -> Any:
        return mapped.get(field) if mapped.get(auth_key) in ("HIGH", "MEDIUM") else None

    def _suggested(field: str, auth_key: str) -> Any:
        if mapped.get(auth_key) not in ("HIGH", "MEDIUM") and mapped.get(field):
            return mapped.get(field)
        return None

    return {
        "name": n,
        "entity_type": mapped.get("entity_type"),
        # SoundCloud — always from the user-provided seed URL (HIGH)
        "soundcloud_username": mapped.get("soundcloud_username"),
        "soundcloud_url": mapped.get("soundcloud_url"),
        "soundcloud_authority": mapped.get("soundcloud_authority", "LOW"),
        # Bandcamp — only if found in SC bio/web-profiles or Discogs
        "bandcamp_url": _verified("bandcamp_url", "bandcamp_authority"),
        "bandcamp_authority": mapped.get("bandcamp_authority", "LOW"),
        "suggested_bandcamp_url": _suggested("bandcamp_url", "bandcamp_authority"),
        # YouTube — only if found in SC bio/web-profiles or Discogs
        "youtube_channel_id": _verified("youtube_channel_id", "youtube_authority"),
        "youtube_url": _verified("youtube_url", "youtube_authority"),
        "youtube_authority": mapped.get("youtube_authority", "LOW"),
        "suggested_youtube_channel_id": _suggested("youtube_channel_id", "youtube_authority"),
        # Beatport — only if from an explicit URL or passed name-similarity threshold (≥0.72)
        "beatport_artist_id": _verified("beatport_artist_id", "beatport_authority"),
        "beatport_artist_name": mapped.get("beatport_artist_name"),
        "beatport_url": _verified("beatport_url", "beatport_authority"),
        "beatport_authority": mapped.get("beatport_authority", "LOW"),
        # Spotify — only if found in SC bio/web-profiles or Discogs
        "spotify_id": _verified("spotify_id", "spotify_authority"),
        "spotify_url": _verified("spotify_url", "spotify_authority"),
        "spotify_authority": mapped.get("spotify_authority", "LOW"),
        "suggested_spotify_id": mapped.get("suggested_spotify_id"),
        # Instagram — only if found in SC bio/web-profiles or Discogs
        "instagram_username": _verified("instagram_username", "instagram_authority"),
        "instagram_url": _verified("instagram_url", "instagram_authority"),
        "instagram_authority": mapped.get("instagram_authority", "LOW"),
        "suggested_instagram_username": _suggested("instagram_username", "instagram_authority"),
        # Twitter — only if found in SC bio/web-profiles or Discogs
        "twitter_username": _verified("twitter_username", "twitter_authority"),
        "twitter_url": _verified("twitter_url", "twitter_authority"),
        "twitter_authority": mapped.get("twitter_authority", "LOW"),
        "suggested_twitter_username": _suggested("twitter_username", "twitter_authority"),
        # Website — LLM-inferred websites are frequently hallucinated; always hold as suggested
        "website_url": None,
        "suggested_website_url": mapped.get("website_url"),
        # Metadata (not gated — these are non-link fields)
        "analysis": mapped.get("analysis"),
        "edges": mapped.get("edges", []),
        "confidence": scores.get("confidence"),
        "identity_confidence": scores.get("identity_confidence"),
        "coverage_level": scores.get("coverage_level"),
        "sc_bio": sc_bio,
        "discovery_provider": discovery_provider,
        "discogs_enrichment": {
            "canonical_name": discogs_context.get("name"),
            "discogs_id": discogs_context.get("discogs_id"),
            "entity_type": discogs_context.get("entity_type"),
            "image_url": discogs_context.get("image_url"),
            "links_found": list((discogs_context.get("links") or {}).keys()),
        } if discogs_context else None,
    }


class SaveDiscoveryBody(BaseModel):
    name: str
    entity_type: str = "artist"
    soundcloud_username: str | None = None
    soundcloud_url: str | None = None
    soundcloud_authority: str = "LOW"
    bandcamp_url: str | None = None
    bandcamp_authority: str = "LOW"
    youtube_channel_id: str | None = None
    youtube_url: str | None = None
    youtube_authority: str = "LOW"
    beatport_artist_id: str | None = None
    beatport_artist_name: str | None = None
    beatport_url: str | None = None
    beatport_authority: str = "LOW"
    spotify_id: str | None = None
    spotify_url: str | None = None
    spotify_authority: str = "LOW"
    instagram_username: str | None = None
    instagram_url: str | None = None
    instagram_authority: str = "LOW"
    twitter_username: str | None = None
    twitter_url: str | None = None
    twitter_authority: str = "LOW"
    twitch_login: str | None = None
    twitch_url: str | None = None
    twitch_authority: str = "LOW"
    website_url: str | None = None
    analysis: str | None = None
    edges: list[dict] = []
    raw_ai_result: dict | None = None
    # suggested_* fields — UI display only, never written to DB canonical columns
    suggested_spotify_id: str | None = None
    suggested_bandcamp_url: str | None = None
    suggested_youtube_channel_id: str | None = None
    suggested_instagram_username: str | None = None
    suggested_twitter_username: str | None = None
    suggested_website_url: str | None = None


@router.post("/save-discovery", status_code=201)
async def save_discovery(
    body: SaveDiscoveryBody,
    x_user_id: str | None = Header(default=None),
):
    """
    Confirm and persist a discovery result after user approval.
    Runs deterministic scoring, then upserts into the artists table.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")

    data = body.model_dump(exclude_none=True)

    # Strip suggested_* and raw_ai_result — UI display only, no DB columns exist for them
    data = {k: v for k, v in data.items() if not k.startswith("suggested_") and k != "raw_ai_result"}

    # Normalize entity_type to lowercase — the DB CHECK constraint requires it
    # LLMs sometimes return "Label", "Artist", etc. with mixed case
    _VALID_ENTITY_TYPES = {"artist", "band", "label", "organization", "venue", "brand"}
    raw_et = data.get("entity_type", "artist")
    normalized_et = raw_et.lower() if raw_et else "artist"
    data["entity_type"] = normalized_et if normalized_et in _VALID_ENTITY_TYPES else "artist"
    logger.info("[discovery] entity_type normalized: %r → %r", raw_et, data["entity_type"])

    # Re-run system scoring on confirmed data
    scores = calculate_node_confidence(data)
    data.update(scores)

    db = get_db()
    import time
    data["user_id"] = x_user_id
    data["last_discovered_at"] = __import__("datetime").datetime.utcnow().isoformat()

    # Upsert by (name, user_id) — don't create duplicates
    existing = (
        db.table("artists")
        .select("id")
        .eq("user_id", x_user_id)
        .ilike("name", data["name"])
        .execute()
    )
    # Filter out columns that might not exist in older DB schemas to prevent 500 errors
    # if the user hasn't run the 004 migration yet.
    def _safe_data(d: dict):
        new_cols = {
            "soundcloud_url", "youtube_url", "spotify_url", "beatport_url",
            "instagram_url", "twitch_url", "twitter_url", "twitter_username",
            "soundcloud_authority", "youtube_authority", "spotify_authority",
            "beatport_authority", "instagram_authority", "twitch_authority",
            "twitter_authority", "bandcamp_authority",
            "suggested_spotify_id",  # never in old schema
        }
        return {k: v for k, v in d.items() if k not in new_cols}

    if existing.data:
        artist_id = existing.data[0]["id"]
        try:
            result = db.table("artists").update(data).eq("id", artist_id).execute()
        except Exception as e:
            if "PGRST204" in str(e):
                 logger.warning("[discovery] Migration missing, falling back to legacy update")
                 result = db.table("artists").update(_safe_data(data)).eq("id", artist_id).execute()
            else: raise e
        logger.info("[discovery] Updated existing artist '%s' for %s", data["name"], x_user_id)
    else:
        try:
            result = db.table("artists").insert(data).execute()
        except Exception as e:
            if "PGRST204" in str(e):
                 logger.warning("[discovery] Migration missing, falling back to legacy insert")
                 result = db.table("artists").insert(_safe_data(data)).execute()
            else: raise e
        logger.info("[discovery] Saved new artist '%s' for %s", data["name"], x_user_id)

    # Pre-warm the feed cache for all extracted platforms immediately (Tier 1+2 baseline)
    # Fire-and-forget: runs concurrently while response is sent so feed is ready when user navigates
    asyncio.create_task(_prefetch_artist_feeds(data))

    return result.data[0]


async def _prefetch_artist_feeds(data: dict) -> None:
    """
    Pre-populate feed_items for every platform field present on the saved artist.
    Called as a fire-and-forget task from save_discovery so the feed cache is warm
    before the frontend's first /feed/merged request arrives.
    """
    from services import soundcloud, bandcamp, youtube

    name = data.get("name", "unknown")
    tasks: list[tuple[str, Any]] = []

    # Tier 1 — SoundCloud (always the seed platform)
    if data.get("soundcloud_username"):
        tasks.append(("soundcloud", soundcloud.get_tracks(data["soundcloud_username"], name)))

    # Tier 2 — Enrichment platforms
    if data.get("bandcamp_url"):
        tasks.append(("bandcamp", bandcamp.get_feed(data["bandcamp_url"], name)))

    if data.get("youtube_url") or data.get("youtube_channel_id"):
        yt = data.get("youtube_url") or data.get("youtube_channel_id")
        if yt:
            tasks.append(("youtube", youtube.get_videos(yt, name)))

    if data.get("beatport_url") and data.get("beatport_artist_id"):
        # For labels, use get_label_releases, for artists use get_artist_releases_by_id
        from services import beatport
        is_label = data.get("entity_type") in ("label", "organization")
        if is_label:
            tasks.append(("beatport", beatport.get_label_releases(data["beatport_artist_id"], name)))
        else:
            tasks.append(("beatport", beatport.get_artist_releases_by_id(data["beatport_artist_id"])))

    if not tasks:
        logger.info("[prefetch] No feed platforms to pre-warm for %s", name)
        return

    logger.info("[prefetch] Pre-warming %d platform(s) for %s: %s",
                len(tasks), name, [t[0] for t in tasks])

    results = await asyncio.gather(*[coro for _, coro in tasks], return_exceptions=True)

    for (platform, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            logger.warning("[prefetch] %s pre-warm failed for %s: %s", platform, name, result)
        else:
            count = len(result) if isinstance(result, list) else 0
            logger.info("[prefetch] %s pre-warm complete for %s: %d items cached", platform, name, count)


@router.get("/social-scout")
async def social_scout(
    platform: str = Query(..., min_length=1),
    artist_name: str = Query(..., min_length=1, alias="artistName"),
    username: str = Query(..., min_length=1),
) -> dict[str, Any]:
    o = get_llm_orchestrator()
    if not o.has_providers():
        raise HTTPException(
            status_code=503,
            detail="No LLM API keys configured. Set GEMINI_API_KEY and/or OPENROUTER_API_KEY.",
        )
    p = platform.strip()
    an = artist_name.strip()
    u = username.strip()
    return await o.scout_social(p, an, u)


@router.get("/graph")
async def get_node_graph(x_user_id: str | None = Header(default=None)):
    """
    Diagnostic Graph: Returns artists as central hubs with their 
    extracted links and AI reasoning as connected nodes.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    
    db = get_db()
    result = db.table("artists").select("*").eq("user_id", x_user_id).execute()
    artists = result.data or []
    
    nodes = []
    links = []
    
    for a in artists:
        logger.info("[graph_debug] Processing artist: %s (id: %s)", a.get("name"), a.get("id"))
        artist_node_id = f"artist_{a['id']}"
        
        # 1. Hub Node (The Artist)
        nodes.append({
            "id": artist_node_id,
            "name": a["name"],
            "type": a["entity_type"],
            "confidence": a.get("identity_confidence", "LOW"),
            "category": "HUB"
        })
        
        # 2. Add Explicit Platform Nodes (The "Extracted" Chain)
        # Prioritize URLs over raw IDs for the display name
        platforms = {
            "soundcloud": a.get("soundcloud_url") or a.get("soundcloud_username"),
            "bandcamp": a.get("bandcamp_url"),
            "beatport": a.get("beatport_url") or a.get("beatport_artist_id"),
            "spotify": a.get("spotify_url") or a.get("spotify_id"),
            "youtube": a.get("youtube_url") or a.get("youtube_channel_id"),
            "instagram": a.get("instagram_url") or a.get("instagram_username"),
        }
        
        found_data_points = 0
        for p_name, p_val in platforms.items():
            if p_val:
                found_data_points += 1
                node_id = f"{p_name}_{a['id']}"
                logger.debug("[graph_debug]   + Found platform: %s = %s", p_name, p_val)
                nodes.append({
                    "id": node_id,
                    "name": f"{p_name}: {p_val}",
                    "type": "platform",
                    "category": "DATA_POINT"
                })
                links.append({
                    "source": artist_node_id,
                    "target": node_id,
                    "relationship": "EXTRACTED",
                    "type": "PLATFORM_IDENTITY_MATCH"
                })
        logger.info("[graph_debug]   -> Created %d data point nodes", found_data_points)

        # 3. Add AI Reasoning Node (The "Analysis" Chain)
        if a.get("analysis"):
            logger.info("[graph_debug]   + Found analysis text (length: %d)", len(a["analysis"]))
            analysis_id = f"analysis_{a['id']}"
            nodes.append({
                "id": analysis_id,
                "name": "LLM Reasoning",
                "type": "reasoning",
                "category": "ANALYSIS",
                "full_text": a["analysis"]
            })
            links.append({
                "source": artist_node_id,
                "target": analysis_id,
                "relationship": "REASONED",
                "type": "AI_SUGGESTED"
            })
        else:
            logger.warning("[graph_debug]   ! No analysis text found for artist %s", a.get("name"))
        
        # 4. Add Cross-Platform Edges
        edges = a.get("edges") or []
        if isinstance(edges, str):
            import json
            try:
                edges = json.loads(edges)
            except:
                edges = []
        
        for e in edges:
            if not isinstance(e, dict): continue
            target_name = e.get('targetName') or e.get('target_name')
            if not target_name: continue
            
            edge_node_id = f"edge_{target_name}_{a['id']}"
            nodes.append({
                "id": edge_node_id,
                "name": target_name,
                "type": "edge",
                "category": "SUGGESTION"
            })
            links.append({
                "source": artist_node_id,
                "target": edge_node_id,
                "relationship": e.get("relationship", "suggested"),
                "type": e.get("type", "AI_SUGGESTED")
            })
            
    return {"nodes": nodes, "links": links}
