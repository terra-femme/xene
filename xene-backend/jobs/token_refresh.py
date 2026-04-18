import os
import httpx
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.token_store import encrypt_token, decrypt_token
from database import get_db

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

IG_REFRESH_URL = "https://graph.instagram.com/refresh_access_token"


async def refresh_instagram_tokens():
    """Refresh all Instagram tokens that expire within the next 10 days."""
    logger.info("[token_refresh] Running Instagram token refresh job")
    db = get_db()
    result = db.table("platform_connections").select("*").eq("platform", "instagram").execute()
    rows = result.data

    async with httpx.AsyncClient() as client:
        for row in rows:
            try:
                token = decrypt_token(row["encrypted_token"])
                resp = await client.get(IG_REFRESH_URL, params={
                    "grant_type": "ig_refresh_token",
                    "access_token": token,
                })
                if resp.status_code == 200:
                    new_token = resp.json()["access_token"]
                    encrypted = encrypt_token(new_token)
                    db.table("platform_connections").update({
                        "encrypted_token": encrypted,
                    }).eq("id", row["id"]).execute()
                    logger.info(f"[token_refresh] Refreshed token for connection {row['id']}")
                else:
                    logger.warning(f"[token_refresh] Refresh failed for {row['id']}: {resp.text}")
            except Exception as e:
                logger.error(f"[token_refresh] Error for connection {row['id']}: {e}")


def start_scheduler():
    # Runs every 7 days — Instagram tokens expire after 60 days
    scheduler.add_job(refresh_instagram_tokens, "interval", days=7, id="ig_token_refresh")
    scheduler.start()
    logger.info("[token_refresh] Scheduler started")
