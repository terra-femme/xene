# Xene — Project Brief for Claude Code

## What is this app?

Xene is a fan-facing artist feed aggregator — a "moving magazine" that pulls together posts, tracks, and releases from a user's favorite artists across Instagram, SoundCloud, Bandcamp, and Beatport into one unified, animated interface. Think of it as a personal music press, not a generic social media manager.

The target user is someone who follows underground or independent artists across multiple platforms and is tired of switching between apps to catch new drops, posts, and releases.

---

## Platform Strategy

**Phase 1 — PWA (build this first)**
Deploy as a Progressive Web App. No App Store fees, no review process. Android users get a near-native install prompt. iOS users get a custom "Add to Home Screen" prompt. Validate the concept before investing in native.

**Phase 2 — Native (if validated)**
Wrap with Capacitor to convert the React codebase into a native iOS/Android app with minimal rewriting. Submit to App Store only after real usage data confirms demand.

---

## Tech Stack

### Frontend
- **React + Vite** — UI framework with fast hot reload
- **Framer Motion** — magazine animations, card transitions, scroll-triggered reveals
- **Tailwind CSS** — utility styling, dark theme
- **vite-plugin-pwa** — auto-generates service worker + manifest for PWA installability
- **TanStack React Query** — API caching, smart refetch, prevents battery-draining polling
- **React Router v6** — client-side routing

### Backend
- **FastAPI (Python 3.11+)** — existing stack, OAuth routes + feed aggregation endpoints
- **httpx** — async HTTP client for calling platform APIs
- **cryptography (Fernet)** — encrypts OAuth tokens before DB storage
- **APScheduler** — background job to refresh Instagram tokens before 60-day expiry
- **python-jose** — JWT handling for user sessions

### Database + Auth
- **Supabase** — managed Postgres + built-in auth (email/OAuth login for app users)
- **supabase-py** — Python client for backend DB operations

### Deployment
- **Railway** — hosts FastAPI backend, Hobby plan ($5/mo), auto-deploys from GitHub
- **Vercel** — hosts React PWA frontend, free tier, auto-deploys from GitHub
- **Cloudflare** — domain registrar + DNS + free SSL (~$10/yr for domain)

---

## Platform APIs

| Platform | Method | Cost | Notes |
|----------|--------|------|-------|
| Instagram | Meta Graph API (OAuth) | Free | Requires Meta app review for public launch. Dev mode supports 25 test users immediately. |
| SoundCloud | Official API | Free | Open registration at soundcloud.com/you/apps. Returns tracks, waveform data, play counts as JSON. |
| Bandcamp | RSS feed | Free | No API needed. Every artist has a public feed at `artist.bandcamp.com/feed`. Parse with `feedparser`. |
| Beatport | Partner API | Free (if approved) | Requires partnership application. Chart data, new releases. **Bottleneck risk** — approval is slow and opaque. Defer to Phase 2. Fallback: their public release pages are scrapeable for chart/release data if partnership stalls. |
| TikTok | Display API / oEmbed | Free | Requires app review. Without OAuth: iFrame embeds only, no metadata. |
| YouTube | YouTube Data API v3 | Free (quota-based) | Better fit than TikTok for underground music — sets, live footage, Boiler Room recordings. Search by artist name. No OAuth required for public content. |

---

## File Structure

### Frontend (`xene-frontend/`)
```
src/
  components/
    MagazineGrid.jsx        # main animated feed layout
    ArtistCard.jsx          # individual post card with platform badge
    SoundCloudPlayer.jsx    # waveform visualizer + playback controls
    ArtistStrip.jsx         # horizontal scrollable artist pill selector
    PlatformBadge.jsx       # SC / IG / BC / BP platform tags
    InstallPrompt.jsx       # iOS "Add to Home Screen" custom modal
  pages/
    Feed.jsx                # main magazine view
    ArtistDetail.jsx        # single artist all-platform view
    Connections.jsx         # connect Instagram / SoundCloud
    Login.jsx               # Supabase auth
  hooks/
    useFeed.js              # React Query feed fetcher with smart caching
    useAuth.js              # Supabase auth state
    usePWAInstall.js        # beforeinstallprompt handler + iOS detection
  lib/
    supabase.js             # Supabase client init
    api.js                  # fetch wrapper pointing to FastAPI backend
  App.jsx                   # router + query provider setup
  main.jsx
vite.config.js              # PWA plugin config lives here
tailwind.config.js
.env                        # VITE_API_URL, VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
```

### Backend (`xene-backend/`)
```
routers/
  auth.py                   # GET /auth/instagram, GET /auth/instagram/callback
  feed.py                   # GET /feed/instagram, GET /feed/soundcloud, GET /feed/bandcamp
  artists.py                # CRUD for user's followed artists list
services/
  instagram.py              # Meta Graph API calls using stored token
  soundcloud.py             # SoundCloud API calls
  bandcamp.py               # RSS feed parsing with feedparser
  token_store.py            # Fernet encrypt/decrypt for OAuth tokens
jobs/
  token_refresh.py          # APScheduler job — refreshes Instagram tokens before expiry
main.py                     # FastAPI app init, router includes, CORS config
database.py                 # Supabase client init
models.py                   # Pydantic request/response schemas
Procfile                    # web: uvicorn main:app --host 0.0.0.0 --port $PORT
requirements.txt
.env                        # all secrets — never commit this
```

---

## Start Up
  Terminal 1 — Backend (in xene-backend, venv active): <br>
  uvicorn main:app --reload --log-level debug <br>
  You should see Application startup complete.

  Terminal 2 — Frontend (in xene-frontend): <br>
  npm run dev <br>
  You should see Local: http://localhost:5173

  Then open http://localhost:5173 in your browser.

  That's the full startup sequence every time.


## Database Schema (Supabase / Postgres)

### `users`
Handled by Supabase Auth — no manual table needed for basic auth.

### `platform_connections`
```sql
CREATE TABLE platform_connections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  platform TEXT NOT NULL,           -- 'instagram' | 'soundcloud' | 'tiktok'
  encrypted_token TEXT NOT NULL,    -- Fernet-encrypted access token
  token_expires_at TIMESTAMPTZ,     -- for Instagram 60-day expiry tracking
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `artists`
```sql
CREATE TABLE artists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  instagram_username TEXT,
  soundcloud_username TEXT,
  bandcamp_url TEXT,
  beatport_artist_id TEXT,
  tiktok_username TEXT,
  youtube_channel_id TEXT,           -- added: YouTube for sets/live footage
  manually_verified BOOLEAN DEFAULT FALSE,  -- added: distinguishes confirmed vs guessed platform links
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

> **Gap note:** Without `manually_verified`, there's no way to distinguish "user typed in this Bandcamp URL" from "we found this by searching." Underground artists with common names are high risk for false matches on RSS feeds. A `FALSE` default means all links start unverified — the UI can surface a "confirm this is them?" prompt.

---

## Key Implementation Details

### PWA Install Flow
```js
// hooks/usePWAInstall.js
// On Android Chrome: intercept beforeinstallprompt, hold it, fire at the right moment
// On iOS Safari: detect iOS + not standalone, show custom bottom sheet UI

let deferredPrompt;

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
});

export function triggerInstall() {
  if (deferredPrompt) {
    deferredPrompt.prompt();
  }
}

export const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
export const isInstalled = window.matchMedia('(display-mode: standalone)').matches;
```

**Trigger install prompt** immediately after user connects their first platform account — not on first page load. That's when they've experienced value for the first time.

### Battery-Safe Feed Design
- Use `IntersectionObserver` on every card — only animate and load media for cards in the viewport
- Pause all animations and audio for cards that scroll off screen
- Never autoplay video — load thumbnail, play on explicit tap only
- Set React Query `staleTime: 5 * 60 * 1000` (5 minutes) — prevents polling on every focus
- Disable `refetchOnWindowFocus` for feed data
- Only pulse the waveform animation on the actively playing card, not all cards

### Instagram OAuth Flow (FastAPI)
```
GET /auth/instagram
  → build Meta auth URL with IG_APP_ID + state param
  → redirect user to instagram.com/oauth/authorize

GET /auth/instagram/callback
  → receive ?code= from Meta
  → POST to Meta token endpoint to exchange code for short-lived token
  → GET from Meta to exchange short-lived → long-lived token (60 days)
  → encrypt token with Fernet
  → store in platform_connections table
  → redirect user back to frontend /connections page
```

### Token Encryption
```python
# services/token_store.py
from cryptography.fernet import Fernet

# generate once: Fernet.generate_key() → store as TOKEN_ENCRYPTION_KEY in .env
fernet = Fernet(os.environ["TOKEN_ENCRYPTION_KEY"])

def encrypt_token(token: str) -> str:
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted: str) -> str:
    return fernet.decrypt(encrypted.encode()).decode()
```

### SoundCloud Feed Response Shape
```json
{
  "platform": "soundcloud",
  "artist": "Four Tet",
  "tracks": [
    {
      "id": "12345",
      "title": "Morning Glass (rough)",
      "duration_ms": 272000,
      "play_count": 41200,
      "like_count": 1800,
      "waveform_url": "https://wave.sndcdn.com/...",
      "stream_url": "...",
      "artwork_url": "...",
      "created_at": "2026-04-11T02:14:00Z"
    }
  ]
}
```

### Feed Normalization Layer (Gap — implement before Milestone 2)
Every platform returns a different shape. Before any data hits the frontend, every service must normalize into one canonical `FeedItem` type. Without this, the frontend ends up handling every platform's quirks individually.

Add to `models.py`:
```python
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
    waveform_url: str | None = None  # SoundCloud-specific
```

Every service (`soundcloud.py`, `instagram.py`, `bandcamp.py`, etc.) must return `list[FeedItem]`. The `/feed` route assembles and sorts them. The frontend only ever sees one shape.

### Platform Data Caching (Gap — implement before public launch)
If 500 users all follow the same artist, the backend makes 500 identical SoundCloud API calls. Before hitting rate limits, add a thin cache keyed by `(artist_id, platform, date)`.

Options:
- **Supabase table** — simplest, no new infrastructure. Cache rows with a `fetched_at` timestamp, invalidate after 15 minutes.
- **Redis on Railway** — faster, purpose-built for this, adds ~$5/mo.

Not needed at prototype stage but must be planned before sharing with more than ~20 users.

### Bandcamp RSS Parsing
```python
# services/bandcamp.py
import feedparser

def get_bandcamp_feed(bandcamp_url: str):
    feed = feedparser.parse(f"{bandcamp_url}/feed")
    return [
        {
            "title": entry.title,
            "url": entry.link,
            "published": entry.published,
            "summary": entry.summary,
        }
        for entry in feed.entries
    ]
```

---

## Environment Variables

### Backend `.env`
```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
IG_APP_ID=your-meta-app-id
IG_APP_SECRET=your-meta-app-secret
IG_REDIRECT_URI=https://your-api.railway.app/auth/instagram/callback
SC_CLIENT_ID=your-soundcloud-client-id
SC_CLIENT_SECRET=your-soundcloud-client-secret
TOKEN_ENCRYPTION_KEY=your-fernet-key
FRONTEND_URL=https://your-app.vercel.app
```

### Frontend `.env`
```
VITE_API_URL=https://your-api.railway.app
VITE_SUPABASE_URL=https://xxxx.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

---

## Setup Order (Critical — do not reorder)

1. Create GitHub repos for frontend and backend
2. Create Supabase project — get URL + keys
3. Set up FastAPI backend locally, add `.env`
4. Deploy backend to Railway (you need a live HTTPS URL before registering with Meta)
5. Register SoundCloud app at soundcloud.com/you/apps
6. Register Meta developer app using the live Railway callback URL
7. Add yourself as a Meta test user
8. Scaffold React frontend with Vite + PWA plugin
9. Deploy frontend to Vercel
10. Test full Instagram OAuth flow end-to-end
11. Wire SoundCloud feed into magazine layout
12. Test PWA install on Android (Chrome) and iOS (Safari)

---

## Cost Summary

| Item | Cost |
|------|------|
| Railway (FastAPI backend) | $5/mo |
| Vercel (React frontend) | Free |
| Supabase (DB + auth) | Free (upgrade to $25/mo at public launch) |
| All platform APIs | Free |
| Domain (Cloudflare) | ~$10/yr |
| **Prototype total** | **~$6/mo** |
| **Post-launch total** | **~$31/mo** |
| Apple Developer (iOS app, future) | $99/yr — defer until validated |
| Google Play (Android app, future) | $25 one-time — defer until validated |

---

## What to Build First (Prototype Milestones)

### Milestone 1 — Visual shell (no APIs) ✓ COMPLETE
Get the magazine grid layout rendering in the browser with mock data. Framer Motion animations, dark editorial aesthetic, artist pills, platform badges. This is the thing you show people to get feedback before writing a single backend route.

### Milestone 2 — SoundCloud live
Wire up SoundCloud API. Real tracks, real waveform data, real play counts. This is your lowest-friction real data integration — no OAuth wall, open API.

### Milestone 3 — Auth + Instagram
Supabase user login + full Instagram OAuth flow. User connects their account, sees real posts in the magazine layout.

### Milestone 4 — Bandcamp RSS
Add Bandcamp feed parsing. Simple, no auth, high value for music fans.

### Milestone 5 — PWA + install prompt
Service worker, manifest, Android install prompt, iOS custom modal. App is now installable.

### Milestone 6 — Share with 10 real people
Get 10 actual music fans using it daily. Watch what they do. Decide what comes next.

### Milestone 7 — Press layer
Surface content *about* the artist, not just *from* the artist. This is the gap between what an artist self-promotes and what's being written or recorded about them.

Sources (no scraping needed — all RSS or official API):
- **Resident Advisor, Mixmag, FACT, Pitchfork** — all publish RSS feeds. Parse with `feedparser`, same code as Bandcamp. Filter by artist name match in title/body.
- **YouTube Data API v3** — search by artist name, return videos. Catches Boiler Room sets, fan recordings, live footage the artist never posted. Free, no OAuth needed for public content.
- **Google Alerts** — set an alert for each artist name, Google generates an RSS feed of web mentions. Zero infrastructure cost.

New `content_type` values: `article`, `video`. New `platform` value: `press`, `youtube`.
New feed section in the UI: a distinct visual treatment to separate press from artist-direct posts.

### Milestone 8 — Artist search and discovery
Currently Xene assumes you already know every artist you follow. There's no way to find new ones. This is the discovery gap.

Approaches (in order of complexity):
1. **Search by name** — user types an artist name, backend searches SoundCloud + Bandcamp by name, returns matching profiles to add. Low complexity.
2. **Related artists** — SoundCloud API returns related artists for any artist. "Fans of Objekt also follow..." derived from the API, not user data.
3. **Co-follow suggestions** — once real user data exists, "other Xene users who follow Objekt also follow these artists." Requires enough users to be meaningful.
4. **Editorial picks** — curated staff picks section. Fits the magazine aesthetic. Manual curation to start, algorithmic later.

Defer until Milestone 6 is complete and real user behavior is observed.

---

## Notes for Claude Code

- Milestone 1 is complete. Frontend lives in `xene-frontend/`.
- Install: `framer-motion @tanstack/react-query react-router-dom tailwindcss vite-plugin-pwa`
- The magazine grid uses CSS Grid with asymmetric column sizing (`2fr 1fr 1fr`) for the editorial feel
- Cards use `IntersectionObserver` from day one
- Mock data lives in `src/lib/mockData.js`
- Dark background: `#0a0a0a`, accent gold: `#c9a96e`, platform colors: SC `#ff5500`, IG `#e1306c`, BC `#4e9a06`, BP `#5b7cfa`

### Known Architecture Gaps (tracked, not yet implemented)
- `FeedItem` normalization model in `models.py` — implement before Milestone 2
- Platform data caching layer — implement before public launch / >20 users
- `manually_verified` column on `artists` table — implement in Milestone 3 when real artist rows are created
- YouTube added as a platform — needs `youtube_channel_id` column on `artists` table and a `youtube.py` service
- Beatport partnership is a bottleneck — have a scraping fallback plan ready
- Press layer (Milestone 7) — `feedparser` on RA/Mixmag/FACT/Pitchfork RSS + YouTube Data API
- Discovery (Milestone 8) — SoundCloud related artists API is the lowest-friction starting point
