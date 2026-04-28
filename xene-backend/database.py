import os
import logging
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_db() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_KEY"]
        _client = create_client(url, key)
    return _client


def get_youtube_channel_id(yt_url: str) -> str | None:
    """Retrieve cached channel_id from database for a YouTube URL."""
    try:
        db = get_db()
        # Query youtube_channel_cache table for this URL
        result = db.table("youtube_channel_cache").select("channel_id").eq("yt_url", yt_url).execute()
        if result.data and len(result.data) > 0:
            channel_id = result.data[0].get("channel_id")
            logger.debug(f"[db] Found cached channel_id for {yt_url}: {channel_id}")
            return channel_id
    except Exception as e:
        # Table might not exist yet — that's OK, will create on first save
        logger.debug(f"[db] Could not query youtube_channel_cache: {e}")
    return None


def save_youtube_channel_id(yt_url: str, channel_id: str) -> bool:
    """Store channel_id mapping in database for future lookups."""
    try:
        db = get_db()
        # Upsert: insert or update if URL already exists
        # Note: resolved_at and created_at use DEFAULT NOW() in the table, so we don't need to pass them
        result = db.table("youtube_channel_cache").upsert({
            "yt_url": yt_url,
            "channel_id": channel_id
        }).execute()
        logger.info(f"[db] Saved channel_id for {yt_url}: {channel_id}")
        return True
    except Exception as e:
        logger.error(f"[db] Error saving channel_id for {yt_url}: {e}")
        return False


# --- System Cache Helpers ---

def get_system_cache(key: str) -> dict | None:
    """Retrieve a value from the system_cache table if not expired."""
    try:
        db = get_db()
        now = datetime.now(timezone.utc).isoformat()
        result = db.table("system_cache").select("value, expires_at").eq("key", key).execute()
        
        if result.data:
            entry = result.data[0]
            expires_at = entry.get("expires_at")
            if expires_at:
                # Basic string comparison for ISO dates is safe for expiration check
                if expires_at < now:
                    logger.debug(f"[db] System cache expired for key: {key}")
                    return None
            return entry.get("value")
    except Exception as e:
        logger.error(f"[db] Error reading system_cache for {key}: {e}")
    return None


def set_system_cache(key: str, value: dict, expires_at: datetime | None = None) -> bool:
    """Store a value in the system_cache table."""
    try:
        db = get_db()
        data = {
            "key": key,
            "value": value,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        if expires_at:
            data["expires_at"] = expires_at.isoformat()
            
        db.table("system_cache").upsert(data).execute()
        logger.debug(f"[db] Set system_cache for key: {key}")
        return True
    except Exception as e:
        logger.error(f"[db] Error writing system_cache for {key}: {e}")
        return False


# --- Feed Cache Helpers ---

def get_last_polled(platform: str, artist_name: str) -> datetime | None:
    """Check system_cache for when this artist/platform was last fetched."""
    key = f"last_polled:{platform}:{artist_name}"
    val = get_system_cache(key)
    if val and "timestamp" in val:
        try:
            return datetime.fromisoformat(val["timestamp"])
        except Exception:
            return None
    return None


def set_last_polled(platform: str, artist_name: str):
    """Mark artist/platform as polled right now."""
    key = f"last_polled:{platform}:{artist_name}"
    set_system_cache(key, {"timestamp": datetime.now(timezone.utc).isoformat()})


def save_feed_items(items: list[dict]):
    """Save a list of normalized FeedItem dicts to the database."""
    if not items:
        return
    try:
        db = get_db()
        logger.debug(f"[db] save_feed_items: attempting to save {len(items)} items")
        logger.debug(f"[db] First item keys: {list(items[0].keys()) if items else 'none'}")
        # Upsert multiple items. Unique constraint on (platform, internal_id) handles duplicates.
        result = db.table("feed_items").upsert(items, on_conflict="platform,internal_id").execute()
        logger.info(f"[db] Upserted {len(items)} feed items, server returned {len(result.data) if result.data else 0} rows")
    except Exception as e:
        logger.error(f"[db] Error saving feed items ({len(items)} items): {e}", exc_info=True)


def save_artist_articles(articles: list[dict]):
    """Save a list of articles to the artist_articles table."""
    if not articles:
        return
    try:
        db = get_db()
        # Upsert articles. Unique constraint on (artist_id, url) handles duplicates.
        db.table("artist_articles").upsert(articles, on_conflict="artist_id,url").execute()
        logger.info(f"[db] Upserted {len(articles)} artist articles")
    except Exception as e:
        logger.error(f"[db] Error saving artist articles: {e}")


def update_last_press_scout(artist_id: str):
    """Update the last_press_scout_at timestamp for an artist."""
    try:
        db = get_db()
        db.table("artists").update({"last_press_scout_at": datetime.now(timezone.utc).isoformat()}).eq("id", artist_id).execute()
        logger.info(f"[db] Updated last_press_scout_at for artist {artist_id}")
    except Exception as e:
        logger.error(f"[db] Error updating last_press_scout_at: {e}")


def get_artist_articles(artist_id: str, limit: int = 10) -> list[dict]:
    """Retrieve articles for a specific artist."""
    try:
        db = get_db()
        result = db.table("artist_articles").select("*").eq("artist_id", artist_id).order("published_at", desc=True).limit(limit).execute()
        return result.data
    except Exception as e:
        logger.error(f"[db] Error fetching articles for artist {artist_id}: {e}")
        return []


def get_last_polled_batch(platform: str, artist_names: list[str]) -> dict[str, "datetime | None"]:
    """Get last_polled timestamps for multiple artists in ONE Supabase call."""
    if not artist_names:
        return {}
    try:
        db = get_db()
        keys = [f"last_polled:{platform}:{name}" for name in artist_names]
        now = datetime.now(timezone.utc).isoformat()
        result = db.table("system_cache").select("key, value, expires_at").in_("key", keys).execute()
        key_to_dt: dict[str, "datetime | None"] = {}
        for row in result.data:
            key = row.get("key", "")
            expires_at = row.get("expires_at")
            if expires_at and expires_at < now:
                key_to_dt[key] = None
            elif row.get("value") and "timestamp" in row["value"]:
                try:
                    key_to_dt[key] = datetime.fromisoformat(row["value"]["timestamp"])
                except Exception:
                    key_to_dt[key] = None
            else:
                key_to_dt[key] = None
        return {name: key_to_dt.get(f"last_polled:{platform}:{name}") for name in artist_names}
    except Exception as e:
        logger.error("[db] get_last_polled_batch %s failed: %s", platform, e)
        return {name: None for name in artist_names}


def get_cached_feed_items_batch(platform: str, artist_names: list[str], limit_per_artist: int = 150, days: int = 31) -> dict[str, list[dict]]:
    """Get cached feed items for multiple artists in ONE Supabase call. Returns dict keyed by artist_name."""
    if not artist_names:
        return {}
    try:
        db = get_db()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        result = (
            db.table("feed_items")
            .select("*")
            .eq("platform", platform)
            .gte("published_at", cutoff)
            .in_("artist_name", artist_names)
            .order("published_at", desc=True)
            .limit(limit_per_artist * len(artist_names))
            .execute()
        )
        grouped: dict[str, list[dict]] = {name: [] for name in artist_names}
        for row in result.data:
            name = row.get("artist_name")
            if name in grouped and len(grouped[name]) < limit_per_artist:
                grouped[name].append(row)
        logger.debug("[db] get_cached_feed_items_batch platform=%s artists=%d rows=%d", platform, len(artist_names), len(result.data))
        return grouped
    except Exception as e:
        logger.error("[db] get_cached_feed_items_batch %s failed: %s", platform, e)
        return {name: [] for name in artist_names}


def get_cached_feed_items(platform: str, artist_name: str | None = None, limit: int = 50, days: int = 31) -> list[dict]:
    """Retrieve cached feed items for a platform from the last `days` days only."""
    try:
        db = get_db()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = (
            db.table("feed_items")
            .select("*")
            .eq("platform", platform)
            .gte("published_at", cutoff)
        )
        if artist_name:
            query = query.eq("artist_name", artist_name)
        result = query.order("published_at", desc=True).limit(limit).execute()
        logger.debug("[db] get_cached_feed_items platform=%s days=%d returned %d rows", platform, days, len(result.data))
        return result.data
    except Exception as e:
        logger.error(f"[db] Error fetching cached feed items for {platform}: {e}")
        return []


def delete_old_feed_items(days: int = 365):
    """Delete feed items older than the specified number of days."""
    try:
        db = get_db()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        # In Supabase/PostgREST, we can use 'lt' for 'less than'
        result = db.table("feed_items").delete().lt("published_at", cutoff).execute()
        logger.info(f"[db] Deleted old feed items before {cutoff}")
        return result
    except Exception as e:
        logger.error(f"[db] Error deleting old feed items: {e}")
        return None
