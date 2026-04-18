import os
import httpx
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from services.token_store import encrypt_token
from database import get_db
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

IG_AUTH_URL = "https://api.instagram.com/oauth/authorize"
IG_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
IG_LONG_LIVED_URL = "https://graph.instagram.com/access_token"


@router.get("/instagram")
async def instagram_login():
    """Redirect user to Instagram OAuth consent screen."""
    params = (
        f"client_id={os.environ['IG_APP_ID']}"
        f"&redirect_uri={os.environ['IG_REDIRECT_URI']}"
        f"&scope=user_profile,user_media"
        f"&response_type=code"
    )
    return RedirectResponse(f"{IG_AUTH_URL}?{params}")


@router.get("/instagram/callback")
async def instagram_callback(code: str, user_id: str):
    """
    Exchange code for a long-lived Instagram token and store it encrypted.
    user_id must be passed as a query param from the frontend redirect.
    """
    logger.info(f"[auth] Instagram callback for user {user_id}")

    async with httpx.AsyncClient() as client:
        # Exchange code for short-lived token
        short_resp = await client.post(IG_TOKEN_URL, data={
            "client_id": os.environ["IG_APP_ID"],
            "client_secret": os.environ["IG_APP_SECRET"],
            "grant_type": "authorization_code",
            "redirect_uri": os.environ["IG_REDIRECT_URI"],
            "code": code,
        })
        if short_resp.status_code != 200:
            logger.error(f"[auth] Short-lived token exchange failed: {short_resp.text}")
            raise HTTPException(status_code=400, detail="Token exchange failed")

        short_token = short_resp.json()["access_token"]

        # Exchange short-lived for long-lived (60-day) token
        long_resp = await client.get(IG_LONG_LIVED_URL, params={
            "grant_type": "ig_exchange_token",
            "client_secret": os.environ["IG_APP_SECRET"],
            "access_token": short_token,
        })
        if long_resp.status_code != 200:
            logger.error(f"[auth] Long-lived token exchange failed: {long_resp.text}")
            raise HTTPException(status_code=400, detail="Long-lived token exchange failed")

        long_data = long_resp.json()
        long_token = long_data["access_token"]

    encrypted = encrypt_token(long_token)
    db = get_db()
    db.table("platform_connections").upsert({
        "user_id": user_id,
        "platform": "instagram",
        "encrypted_token": encrypted,
    }).execute()

    logger.info(f"[auth] Instagram token stored for user {user_id}")
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    return RedirectResponse(f"{frontend_url}/connections?connected=instagram")
