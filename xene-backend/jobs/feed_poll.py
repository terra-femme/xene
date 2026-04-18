import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services import soundcloud, bandcamp

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def poll_all_artists():
    """
    Background job: refresh the feed cache for every artist in the system.
    Runs hourly so the feed is always fresh when users open the app.
    Uses in-memory caches in soundcloud.py and bandcamp.py — no DB writes needed.
    """
    logger.info("[feed_poll] Starting hourly feed refresh")

    # Import here to avoid circular imports at module load time
    from database import get_db

    try:
        db = get_db()
        result = db.table("artists").select("name, soundcloud_username, bandcamp_url").execute()
        artists = result.data
    except Exception as e:
        logger.error(f"[feed_poll] Could not fetch artists from DB: {e}")
        return

    sc_count = 0
    bc_count = 0

    for artist in artists:
        if artist.get("soundcloud_username"):
            try:
                soundcloud.invalidate_cache(artist["soundcloud_username"])
                await soundcloud.get_tracks(artist["soundcloud_username"])
                sc_count += 1
            except Exception as e:
                logger.warning(f"[feed_poll] SC failed for {artist['name']}: {e}")

        if artist.get("bandcamp_url"):
            try:
                await bandcamp.get_feed(artist["bandcamp_url"], artist["name"])
                bc_count += 1
            except Exception as e:
                logger.warning(f"[feed_poll] BC failed for {artist['name']}: {e}")

    logger.info(f"[feed_poll] Done — refreshed {sc_count} SC + {bc_count} BC feeds")


def start_feed_scheduler():
    scheduler.add_job(poll_all_artists, "interval", hours=1, id="feed_poll")
    scheduler.start()
    logger.info("[feed_poll] Feed poll scheduler started (interval: 1h)")
