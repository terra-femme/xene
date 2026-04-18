import logging
from fastapi import APIRouter, HTTPException, Header
from models import ArtistCreate, ArtistOut
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/artists", tags=["artists"])


def _require_user(x_user_id: str | None) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    return x_user_id


@router.get("/", response_model=list[ArtistOut])
async def list_artists(x_user_id: str | None = Header(default=None)):
    user_id = _require_user(x_user_id)
    db = get_db()
    result = db.table("artists").select("*").eq("user_id", user_id).execute()
    return result.data


@router.post("/", response_model=ArtistOut, status_code=201)
async def create_artist(body: ArtistCreate, x_user_id: str | None = Header(default=None)):
    user_id = _require_user(x_user_id)
    db = get_db()
    result = db.table("artists").insert({**body.model_dump(), "user_id": user_id}).execute()
    logger.info(f"[artists] Created artist '{body.name}' for user {user_id}")
    return result.data[0]


@router.delete("/{artist_id}", status_code=204)
async def delete_artist(artist_id: str, x_user_id: str | None = Header(default=None)):
    user_id = _require_user(x_user_id)
    db = get_db()
    db.table("artists").delete().eq("id", artist_id).eq("user_id", user_id).execute()
    logger.info(f"[artists] Deleted artist {artist_id} for user {user_id}")
