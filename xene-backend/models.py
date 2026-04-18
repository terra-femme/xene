from typing import Literal
from datetime import datetime
from pydantic import BaseModel


class FeedItem(BaseModel):
    id: str
    platform: Literal["soundcloud", "instagram", "bandcamp", "beatport", "tiktok", "youtube", "press"]
    artist_name: str
    content_type: Literal["track", "post", "release", "video", "image", "article"]
    title: str | None = None
    body: str | None = None
    media_url: str | None = None
    artwork_url: str | None = None
    external_url: str
    published_at: datetime
    play_count: int | None = None
    like_count: int | None = None
    waveform_url: str | None = None


class ArtistCreate(BaseModel):
    name: str
    soundcloud_username: str | None = None
    instagram_username: str | None = None
    bandcamp_url: str | None = None
    youtube_channel_id: str | None = None
    twitch_login: str | None = None
    beatport_artist_name: str | None = None
    beatport_artist_id: str | None = None


class ArtistOut(ArtistCreate):
    id: str
    user_id: str
    manually_verified: bool
    created_at: datetime


class BeatportArtist(BaseModel):
    beatport_id: str
    name: str
    slug: str | None = None
    image_url: str | None = None
    artist_url: str


class BeatportRelease(BaseModel):
    beatport_id: str
    title: str
    artists: list[str]
    label: str | None = None
    artwork_url: str | None = None
    release_url: str
    published_at: str | None = None
    track_count: int = 0


class TwitchStream(BaseModel):
    twitch_login: str
    stream_title: str
    game_name: str
    viewer_count: int
    started_at: str | None = None
    thumbnail_url: str | None = None
    stream_url: str
