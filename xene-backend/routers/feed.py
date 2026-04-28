import logging
import asyncio
from datetime import timezone, datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from models import FeedItem
from services import soundcloud, bandcamp, youtube
from services.beatport import get_label_releases
from database import get_cached_feed_items, get_cached_feed_items_batch, get_last_polled, get_last_polled_batch, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feed", tags=["feed"])

# Deduplicates concurrent live fetches for the same (platform, artist_name).
# Two simultaneous /feed/merged requests won't both trigger a live fetch for the same artist.
_inflight: dict[tuple[str, str], asyncio.Event] = {}


def _db_row_to_feed_item(item_data: dict) -> FeedItem:
    """Convert a raw feed_items DB row to a FeedItem, normalizing timezone."""
    if isinstance(item_data["published_at"], str):
        # Handle 'Z' or '+00:00'
        raw = item_data["published_at"].replace('Z', '+00:00')
        item_data["published_at"] = datetime.fromisoformat(raw)

    item = FeedItem(
        id=item_data["internal_id"],
        platform=item_data["platform"],
        artist_name=item_data["artist_name"],
        content_type=item_data["content_type"],
        title=item_data["title"],
        body=item_data["body"],
        artwork_url=item_data["artwork_url"],
        external_url=item_data["external_url"],
        published_at=item_data["published_at"],
        duration_seconds=item_data.get("duration_seconds"),
        play_count=item_data.get("play_count"),
        like_count=item_data.get("like_count"),
    )
    if item.published_at.tzinfo is None:
        item.published_at = item.published_at.replace(tzinfo=timezone.utc)
    return item


@router.get("/merged", response_model=list[FeedItem])
async def get_merged_feed(
    artist_id: str = Query(default=None, description="Optional: Filter for a single artist ID"),
    platform: str = Query(default=None, description="Optional: Filter for a single platform (soundcloud, bandcamp, youtube, beatport, twitch)"),
    sc: list[str] = Query(default=[], description="SoundCloud usernames"),
    sc_name: list[str] = Query(default=[], description="SoundCloud artist display names"),
    bc_url: list[str] = Query(default=[], description="Bandcamp artist URLs"),
    bc_name: list[str] = Query(default=[], description="Bandcamp artist display names"),
    yt_url: list[str] = Query(default=[], description="YouTube channel URLs"),
    yt_name: list[str] = Query(default=[], description="YouTube artist display names"),
    bp_label_id: list[str] = Query(default=[], description="Beatport label IDs (parsed as int internally)"),
    bp_label_name: list[str] = Query(default=[], description="Beatport label display names"),
    requested_name: list[str] = Query(default=[], description="All display names in this request"),
    force_refresh: bool = Query(default=False, description="Bypass cache"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=30, ge=1, le=100),
):
    logger.info(
        "[feed] GET sc=%d bc=%d yt=%d bp=%d platform=%s page=%d force=%s artist_id=%s",
        len(sc), len(bc_url), len(yt_url), len(bp_label_id), platform, page, force_refresh, artist_id
    )
    all_items: list[FeedItem] = []

    async def fetch_platform_items(p_id: str, inputs: list[str], display_names: list[str], service_func, ttl_hours: int, cache_days: int = 730):
        if platform and platform != p_id:
            return []

        # Strip nullish values up front
        valid_pairs = [
            (val, d_name) for val, d_name in zip(inputs, display_names)
            if val and str(val).strip().lower() not in ("null", "none", "undefined", "")
        ]
        if not valid_pairs:
            return []

        valid_vals, valid_names = zip(*valid_pairs)

        # TWO Supabase calls replace N×2 sequential calls (the main latency driver).
        # get_cached_feed_items_batch and get_last_polled_batch each issue one query
        # covering all artists for this platform.
        now = datetime.now(timezone.utc)
        cached_batch = get_cached_feed_items_batch(p_id, list(valid_names), limit_per_artist=150, days=cache_days)
        polled_batch = get_last_polled_batch(p_id, list(valid_names))

        platform_items = []
        for val, d_name in valid_pairs:
            cached_items = [_db_row_to_feed_item(r) for r in cached_batch.get(d_name, [])]
            lp = polled_batch.get(d_name)
            stale = not lp or (now - lp) > timedelta(hours=ttl_hours)

            if not force_refresh and not stale and cached_items:
                logger.info("[feed] %s cache HIT for %s: %d items", p_id.upper(), d_name, len(cached_items))
                platform_items.extend(cached_items)
            else:
                inflight_key = (p_id, d_name)
                if inflight_key in _inflight:
                    logger.info("[feed] %s %s already in-flight — waiting for concurrent fetch", p_id.upper(), d_name)
                    try:
                        await asyncio.wait_for(asyncio.shield(_inflight[inflight_key].wait()), timeout=45)
                    except (asyncio.TimeoutError, KeyError):
                        logger.warning("[feed] Timed out waiting for in-flight %s %s", p_id.upper(), d_name)
                    fresh_raw = get_cached_feed_items(p_id, artist_name=d_name, days=cache_days, limit=150)
                    platform_items.extend([_db_row_to_feed_item(r) for r in fresh_raw] or cached_items)
                    continue

                event = asyncio.Event()
                _inflight[inflight_key] = event
                logger.info("[feed] %s cache MISS/STALE for %s (stale=%s) — fetching live", p_id.upper(), d_name, stale)
                try:
                    if p_id == "bandcamp":
                        if "bandcamp.com" not in val:
                            val = f"https://{val}.bandcamp.com"
                        elif not val.startswith("http"):
                            val = "https://" + val

                    live_items = await service_func(val, d_name)
                    if live_items:
                        platform_items.extend(live_items)
                        logger.info("[feed] %s live SUCCESS for %s: %d items", p_id.upper(), d_name, len(live_items))
                    else:
                        logger.info("[feed] %s live EMPTY for %s, falling back to cache (%d items)", p_id.upper(), d_name, len(cached_items))
                        platform_items.extend(cached_items)
                except Exception as e:
                    logger.warning("[feed] %s live FAILURE for %s: %s, falling back to cache (%d items)", p_id.upper(), d_name, e, len(cached_items))
                    platform_items.extend(cached_items)
                finally:
                    _inflight.pop(inflight_key, None)
                    event.set()
        return platform_items

    # ── Parallel Execution ────────────────────────────────────────────────
    tasks = []

    # Only add tasks for the requested platform (or all if none specified)
    if not platform or platform == "soundcloud":
        async def fetch_soundcloud_with_reposts():
            # Get regular tracks — only recent content (last 31 days)
            tracks = await fetch_platform_items("soundcloud", sc, sc_name, soundcloud.get_tracks, 6, cache_days=31)

            # Fetch reposts for artists that have labels configured
            reposts = []
            if sc_name:
                try:
                    db = get_db()
                    # Query for artists with soundcloud_repost_labels configured
                    res = db.table("artists").select("name, soundcloud_repost_labels").in_("name", list(sc_name)).execute()
                    artist_configs = {a["name"]: a.get("soundcloud_repost_labels") or [] for a in res.data}

                    for username, artist_name in zip(sc, sc_name):
                        if artist_name not in artist_configs:
                            continue
                        labels = artist_configs[artist_name]
                        if not labels:
                            continue

                        # For each configured label, fetch reposts crediting this artist
                        for label_username in labels:
                            try:
                                logger.info("[feed] Fetching SoundCloud reposts from %s for %s", label_username, artist_name)
                                label_reposts = await soundcloud.get_artist_reposts_by_label(label_username, [username])
                                reposts.extend(label_reposts)
                                logger.info("[feed] Got %d reposts from %s", len(label_reposts), label_username)
                            except Exception as e:
                                logger.warning("[feed] Failed to fetch reposts from %s: %s", label_username, e)
                except Exception as e:
                    logger.warning("[feed] Failed to fetch repost configs: %s", e)

            return tracks + reposts

        tasks.append(fetch_soundcloud_with_reposts())
    if not platform or platform == "bandcamp":
        tasks.append(fetch_platform_items("bandcamp", bc_url, bc_name, bandcamp.get_feed, 2, cache_days=3650))
    if not platform or platform == "youtube":
        tasks.append(fetch_platform_items("youtube", yt_url, yt_name, youtube.get_videos, 12))
    
    # Beatport handling — parse ids safely; skip any that are not valid integers
    # (e.g. "null" or "none" strings stored incorrectly in DB)
    if not platform or platform == "beatport":
        _SKIP = {"null", "none", "undefined", ""}
        for raw_id, b_name in zip(bp_label_id, bp_label_name):
            if str(raw_id).strip().lower() in _SKIP:
                logger.warning("[feed] Skipping beatport id=%r for '%s' — not a valid integer", raw_id, b_name)
                continue
            try:
                b_id = int(raw_id)
            except (ValueError, TypeError):
                logger.warning("[feed] Skipping beatport id=%r for '%s' — could not parse as int", raw_id, b_name)
                continue
            tasks.append(get_label_releases(b_id, label_name=b_name))

    results = await asyncio.gather(*tasks)
    for sublist in results:
        all_items.extend(sublist)

    if not all_items:
        return []

    # Final name-based filter if requested for a specific ID
    if artist_id:
        from database import get_db
        db = get_db()
        art_res = db.table("artists").select("name").eq("id", artist_id).execute()
        if art_res.data:
            target = art_res.data[0]["name"]
            logger.info("[feed] Filtering for artist_id=%s, target_name='%s'", artist_id, target)
            original_count = len(all_items)
            all_items = [i for i in all_items if i.artist_name == target]
            logger.info("[feed] Filtered from %d to %d items for '%s'", original_count, len(all_items), target)

    # Deduplicate & Sort
    seen_ids = set()
    unique_items = []
    
    # Sort all_items by date first
    all_items.sort(key=lambda x: x.published_at, reverse=True)

    for item in all_items:
        # 1. Strict ID deduplication (same platform, same ID)
        id_key = (item.platform, item.id)
        if id_key in seen_ids:
            continue
            
        if item.published_at.tzinfo is None:
            item.published_at = item.published_at.replace(tzinfo=timezone.utc)
            
        unique_items.append(item)
        seen_ids.add(id_key)

    # unique_items already sorted by date desc from the pre-loop sort
    
    start = (page - 1) * limit
    paginated = unique_items[start : start + limit]
    logger.info("[feed] Returning %d items (total %d unique)", len(paginated), len(unique_items))
    return paginated
