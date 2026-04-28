from typing import Literal, Any
from datetime import datetime
from pydantic import BaseModel, model_validator

# ── NEC & identity types ────────────────────────────────────────────────────
EntityType = Literal["artist", "band", "label", "organization", "venue", "brand"]
IdentityConfidence = Literal["HIGH", "MEDIUM", "LOW"]
CoverageLevel = Literal["COMPLETE", "PARTIAL", "FRAGMENTED"]
EdgeAuthority = Literal["HIGH", "MEDIUM", "LOW"]
EdgeSourceType = Literal[
    "PLATFORM_IDENTITY_MATCH",
    "EXPLICIT_BIO_LINK",
    "VERIFIED_EXTERNAL_LINK",
    "USER_DECLARED",
    "AI_SUGGESTED",
]


class PlatformBinding(BaseModel):
    targetName: str
    relationship: str
    sourceUrl: str
    type: EdgeSourceType
    authorityLevel: EdgeAuthority
    lastVerified: int  # Unix timestamp ms


class FeedItem(BaseModel):
    id: str
    platform: Literal["soundcloud", "instagram", "bandcamp", "beatport", "tiktok", "youtube", "twitch", "press"]
    artist_name: str
    content_type: Literal["track", "post", "release", "video", "image", "article", "notification"]
    title: str | None = None
    body: str | None = None
    media_url: str | None = None
    artwork_url: str | None = None
    external_url: str
    published_at: datetime
    play_count: int | None = None
    like_count: int | None = None
    waveform_url: str | None = None
    duration_seconds: int | None = None
    track_count: int | None = None


class ArtistCreate(BaseModel):
    name: str
    entity_type: EntityType = "artist"
    # Feed-scraper platform fields
    soundcloud_username: str | None = None
    soundcloud_url: str | None = None
    soundcloud_authority: EdgeAuthority = "LOW"

    instagram_username: str | None = None
    instagram_url: str | None = None
    instagram_authority: EdgeAuthority = "LOW"

    bandcamp_url: str | None = None
    bandcamp_authority: EdgeAuthority = "LOW"

    youtube_channel_id: str | None = None
    youtube_url: str | None = None
    youtube_authority: EdgeAuthority = "LOW"

    twitch_login: str | None = None
    twitch_url: str | None = None
    twitch_authority: EdgeAuthority = "LOW"

    beatport_artist_name: str | None = None
    beatport_artist_id: str | None = None
    beatport_url: str | None = None
    beatport_authority: EdgeAuthority = "LOW"

    # Identity core platforms
    spotify_id: str | None = None
    spotify_url: str | None = None
    spotify_authority: EdgeAuthority = "LOW"

    apple_music_id: str | None = None
    deezer_id: str | None = None
    tidal_id: str | None = None
    website_url: str | None = None
    twitter_username: str | None = None
    twitter_url: str | None = None
    twitter_authority: EdgeAuthority = "LOW"
    # AI breadcrumb analysis text
    analysis: str | None = None

    # SoundCloud label repost tracking: list of label usernames to monitor
    soundcloud_repost_labels: list[str] | None = None


class ArtistOut(ArtistCreate):
    id: str
    user_id: str
    manually_verified: bool = False
    created_at: datetime
    # System-computed identity scores (written by identity_engine.py, never by AI)
    confidence: float = 0.0
    identity_confidence: IdentityConfidence = "LOW"
    coverage_level: CoverageLevel = "FRAGMENTED"
    conflict_state: bool = False
    edges: list[PlatformBinding] = []
    last_discovered_at: datetime | None = None
    # Backward compat: computed from entity_type so EntityFeed.jsx keeps working
    is_label: bool = False

    @model_validator(mode="after")
    def compute_is_label(self) -> "ArtistOut":
        self.is_label = self.entity_type in ("label", "organization")
        return self


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
