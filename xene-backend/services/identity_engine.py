"""
Identity Engine — deterministic scoring and field mapping.

This module contains ONLY pure functions: no I/O, no AI calls, no HTTP.
It is the system layer boundary between raw AI extraction output and
canonical identity truth stored in the artists table.

Ported from gemini/lib/aiService.ts :: calculateNodeConfidence()
and the normalization step in gemini/server.ts :: /api/auto-discover.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from services import platform_utils

logger = logging.getLogger(__name__)


def calculate_node_confidence(data: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministic, entity-type-aware identity confidence scoring.
    """
    entity_type = (data.get("entity_type") or "artist").lower()
    is_label = entity_type in ("label", "organization")

    # Source Trust Scoring:
    # 1. API_VERIFIED (SoundCloud web-profiles) = HIGH TRUST
    # 2. DETERMINISTIC_MATCH (Cross-verified) = HIGH TRUST
    # 3. AI_SCOUTED = LOW TRUST
    # 4. EXPLICIT_BIO_LINK = MEDIUM TRUST

    def _get_signal_strength(key: str) -> float:
        val = data.get(key)
        if not val:
            return 0.0
        
        authority = data.get(f"{key}_authority", "LOW")
        if authority == "HIGH":
            return 1.0  # Full strength (API verified or explicit bio link)
        if authority == "MEDIUM":
            return 0.8
        return 0.5  # Default AI scouted

    if is_label:
        # LABEL / ORGANIZATION scoring using signal strengths
        identity_cores = (
            _get_signal_strength("beatport_artist_id") +
            _get_signal_strength("bandcamp_url")
        )
        medium_signals = (
            _get_signal_strength("soundcloud_username") +
            _get_signal_strength("youtube_channel_id")
        )
        weak_signals = (
            _get_signal_strength("website_url") +
            _get_signal_strength("spotify_id")
        )
        entity_tag = "label"
    else:
        # ARTIST / BAND scoring
        identity_cores = (
            _get_signal_strength("spotify_id") +
            _get_signal_strength("apple_music_id") +
            _get_signal_strength("deezer_id") +
            _get_signal_strength("tidal_id")
        )
        medium_signals = (
            _get_signal_strength("soundcloud_username") +
            _get_signal_strength("youtube_channel_id") +
            _get_signal_strength("beatport_artist_id")
        )
        weak_signals = (
            _get_signal_strength("website_url") +
            _get_signal_strength("bandcamp_url")
        )
        entity_tag = "artist"

    # Thresholds adjusted for floating point signal strengths
    if identity_cores >= 1.5 or (identity_cores >= 0.8 and medium_signals >= 1.4) or (medium_signals + weak_signals >= 2.5):
        id_conf = "HIGH"
    elif identity_cores >= 0.8 or (medium_signals >= 1.4 and weak_signals >= 0.4):
        id_conf = "MEDIUM"
    else:
        id_conf = "LOW"

    total = identity_cores + medium_signals + weak_signals
    if total >= 4:
        coverage = "COMPLETE"
    elif total >= 2:
        coverage = "PARTIAL"
    else:
        coverage = "FRAGMENTED"

    # Weighted score calculation with authority modulation
    base_score = (identity_cores * 0.40) + (medium_signals * 0.15) + (weak_signals * 0.05)
    score = min(base_score, 1.0)

    logger.info(
        "[identity_trace] %s [%s] | cores=%d medium=%d weak=%d → conf=%s coverage=%s score=%.2f",
        data.get("name", "Unknown"), entity_tag, identity_cores, medium_signals, weak_signals, id_conf, coverage, score,
    )

    return {
        "confidence": round(score, 4),
        "identity_confidence": id_conf,
        "coverage_level": coverage,
        "conflict_state": False,
    }


def map_ai_result_to_artist_fields(ai_result: dict[str, Any], artist_name: str = "") -> dict[str, Any]:
    """
    Translate raw AI extraction output into flat artists-table column names.

    CRITICAL: Enforces platform-specific field constraints to prevent data contamination.
    Example: Instagram handles must NOT be written to soundcloud_username field.
    """
    out: dict[str, Any] = {}

    # Capture Canonical Name Override
    # This allows resolving "Planet V" -> "V Recordings"
    canonical_name = ai_result.get("canonicalName") or ai_result.get("name") or artist_name
    out["name"] = canonical_name

    # Improved Label Detection
    _VALID_ENTITY_TYPES = {"artist", "band", "label", "organization", "venue", "brand"}
    raw_entity_type = ai_result.get("entityType")
    entity_type = raw_entity_type.lower() if raw_entity_type else None

    if not entity_type or entity_type == "artist":
        name_lower = canonical_name.lower()
        if any(w in name_lower for w in ["recordings", "records", "productions", "music group"]):
            entity_type = "label"

    if entity_type not in _VALID_ENTITY_TYPES:
        entity_type = "artist"

    out["entity_type"] = entity_type

    def _set(key: str, value: Any) -> None:
        if value:
            out[key] = value

    def _detect_platform_from_id(raw_id: str) -> str | None:
        """Heuristic: detect which platform a handle/username likely belongs to."""
        raw_id_lower = raw_id.lower()

        # Instagram pattern: handles with underscores are common (r3idy_dnb, user_name)
        # But more importantly: Instagram handles are often @-prefixed in raw form
        if "_dnb" in raw_id_lower or "_" in raw_id_lower and "@" not in raw_id:
            # Instagram-style handles with underscores are suspicious in SC context
            if "soundcloud" not in raw_id_lower:
                return "instagram"  # Likely Instagram-style naming

        # Twitter pattern: starts with @ or contains /status/
        if raw_id.startswith("@") or "/status/" in raw_id:
            return "twitter"

        # SoundCloud pattern: alphanumeric + hyphens, no underscores in usernames
        # SoundCloud usernames rarely have underscores; Instagram handles often do
        if "@" not in raw_id and not raw_id.startswith("http"):
            if "soundcloud" in raw_id.lower():
                return "soundcloud"

        return None

    def _set_canonical(key: str, platform: str, val: Any) -> None:
        if not val or str(val).lower() in ("null", "none", "bandcamp", "soundcloud"):
            return

        # --- ROBUST ID EXTRACTION ---
        # If it's a URL, extract the cleanest identifier (slug or ID)
        raw_id = str(val).strip()
        if "://" in raw_id:
             from urllib.parse import urlparse
             path = urlparse(raw_id).path.strip("/")
             if path:
                 if platform == "soundcloud":
                     # user or user/tracks -> user
                     raw_id = path.split("/")[0]
                 elif platform == "youtube":
                     # @handle or channel/UC... -> handle or ID
                     if "/channel/" in raw_id:
                         raw_id = path.split("/")[-1]
                     else:
                         raw_id = path.split("/")[0]
                 elif platform == "beatport":
                     # /artist/slug/ID -> ID
                     raw_id = path.split("/")[-1]
                 else:
                     raw_id = path.split("/")[-1]

        # Clean @ from handles for internal storage
        if platform in ("youtube", "instagram", "twitter") and raw_id.startswith("@"):
            raw_id = raw_id.lstrip("@")

        # --- PLATFORM CONTAMINATION CHECK ---
        # If we're trying to write to a SoundCloud field, verify the ID actually looks like SoundCloud
        detected_platform = _detect_platform_from_id(raw_id)
        if platform == "soundcloud" and detected_platform and detected_platform != "soundcloud":
            logger.warning(
                "[identity_engine] REJECTED: Detected %s data in soundcloud field (raw_id=%r) — potential contamination from artist bio extraction",
                detected_platform, raw_id
            )
            return  # Skip this write entirely

        if platform_utils.validate_id(platform, raw_id):
            out[key] = raw_id
            # Generate the canonical absolute URL
            full_url = platform_utils.get_canonical_url(platform, raw_id, entity_type)
            if full_url:
                out[f"{platform}_url"] = full_url
            logger.debug("[identity_engine] [%s] Set %s=%r (validated)", platform, key, raw_id)
        else:
            logger.debug("[identity_engine] [%s] Rejected invalid format: %r", platform, raw_id)

    # Platform Mapping with Validation
    _set_canonical("soundcloud_username", "soundcloud", _nested(ai_result, "soundcloudRss", "url"))
    _set_canonical("youtube_channel_id", "youtube", _nested(ai_result, "youtube", "id"))
    _set_canonical("spotify_id", "spotify", _nested(ai_result, "spotify", "id"))
    
    # Bandcamp
    bc_url = _nested(ai_result, "bandcampRss", "url")
    if bc_url:
        bc_canonical = platform_utils.get_canonical_url("bandcamp", bc_url)
        if bc_canonical:
            out["bandcamp_url"] = bc_canonical

    # Beatport Mapping
    bp = ai_result.get("beatport") or {}
    bp_id = bp.get("labelId") or bp.get("artistId")
    if bp_id and platform_utils.validate_id("beatport", str(bp_id)):
        out["beatport_artist_id"] = str(bp_id)
        # Capture the actual slug, fallback to a clean version of the name
        raw_slug = bp.get("slug") or canonical_name
        bp_slug = re.sub(r'[^a-z0-9]+', '-', raw_slug.lower()).strip('-')
        out["beatport_url"] = platform_utils.get_canonical_url("beatport", str(bp_id), entity_type, slug=bp_slug)
        out["beatport_artist_name"] = bp.get("name") or canonical_name

    # Spotify — standard format
    sp_id = _nested(ai_result, "spotify", "id")
    if sp_id and platform_utils.validate_id("spotify", sp_id):
        out["spotify_id"] = sp_id
        out["spotify_url"] = platform_utils.get_canonical_url("spotify", sp_id)

    _set("website_url", _nested(ai_result, "website", "url"))
    _set("analysis", ai_result.get("analysis"))


    passive = ai_result.get("passivePlatforms") or {}
    _set("instagram_username", passive.get("instagram"))
    if passive.get("instagram"):
        out["instagram_url"] = platform_utils.get_canonical_url("instagram", passive["instagram"])
        
    _set("twitter_username", passive.get("twitter"))
    if passive.get("twitter"):
        out["twitter_url"] = platform_utils.get_canonical_url("twitter", passive["twitter"])

    # Normalise suggested edges: add authority defaults (AI = LOW authority)
    raw_edges = ai_result.get("suggestedEdges") or []
    if raw_edges:
        import time
        now_ms = int(time.time() * 1000)
        out["edges"] = [
            {
                "targetName": e.get("targetName", ""),
                "relationship": e.get("relationship", ""),
                "sourceUrl": e.get("sourceUrl", ""),
                "type": e.get("type", "AI_SUGGESTED"),
                "authorityLevel": "LOW",  # AI edges are always LOW authority
                "lastVerified": now_ms,
            }
            for e in raw_edges
            if e.get("targetName")
        ]

    logger.debug("[identity_engine] mapped fields for %s: %s", artist_name, list(out.keys()))
    
    # Final cleanup: remove any fields that are literally the string "null"
    # and ensure non-existent IDs are truly None
    return {k: v for k, v in out.items() if v is not None and str(v).lower() != "null"}


def compute_cross_verified(
    ai_result: dict[str, Any],
    sc_web_profiles: dict[str, Any],
) -> bool:
    """
    Deterministic cross-verification: did the SC web-profiles handshake
    confirm at least one platform link that the AI also found?

    This replaces the old 'crossVerified' field that was incorrectly
    requested from the AI. Cross-verification is a system-layer judgment.
    """
    if not sc_web_profiles:
        return False

    sc_confirmed_networks = set(sc_web_profiles.keys())

    ai_found_networks: set[str] = set()
    if _nested(ai_result, "spotify", "id"):
        ai_found_networks.add("spotify")
    if _nested(ai_result, "youtube", "id"):
        ai_found_networks.add("youtube")
    if _nested(ai_result, "bandcampRss", "url"):
        ai_found_networks.add("bandcamp")

    overlap = sc_confirmed_networks & ai_found_networks
    result = len(overlap) > 0
    if result:
        logger.info("[identity_engine] cross_verified via SC web-profiles: %s", overlap)
    return result


def _nested(data: dict[str, Any], *keys: str) -> Any:
    """Safe nested dict access. Returns None if any key is missing."""
    current = data
    for k in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(k)
    return current or None
