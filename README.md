# Xene

**Your artists. Every platform. One feed.**

Xene is a personal artist aggregator for music fans. You add the artists you follow — their SoundCloud, Bandcamp, Twitch, and more — and Xene assembles a single chronological feed of everything they publish, across every platform, in real time.

Every item in the feed links directly back to the artist's original platform. Xene does not host, stream, cache, or redistribute audio or content of any kind. We surface metadata and links. The platforms remain the destination.

---

## What Xene does and does not do

| Does | Does not |
|---|---|
| Aggregate publicly available artist activity via official APIs and public RSS | Host, re-stream, or redistribute audio or video |
| Send every click directly to the artist's original platform | Replicate platform experiences or intercept traffic |
| Display platform branding so fans always know the content's origin | Sell, license, or monetize any artist's content |
| Notify fans when artists go live on Twitch, linking to the Twitch stream | Allow users to download or own third-party content |
| Operate within rate limits and developer terms of every API it uses | Scrape beyond what is publicly permitted |

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, Framer Motion, React Query |
| Backend | Python 3.13, FastAPI, Uvicorn |
| Database | Supabase (Postgres) |
| Frontend deploy | Vercel |
| Backend deploy | Render |
| Auth | Supabase Auth |

---

## Project structure

```
xene/
├── landing/          # Vercel landing page (index.html)
├── xene-frontend/    # React/Vite PWA
└── xene-backend/     # FastAPI service
```

---

## Running locally

### Prerequisites
- Node 20+
- Python 3.13+
- A Supabase project (for auth and artist storage)

### Frontend

```bash
cd xene-frontend
npm install
cp .env.example .env          # fill in VITE_API_URL
npm run dev                   # http://localhost:5173
```

The frontend runs without a backend — it falls back to mock data automatically when `VITE_API_URL` is not set.

### Backend

```bash
cd xene-backend
python -m venv venv
venv\Scripts\activate         # Windows
pip install -r requirements.txt
cp .env.example .env          # fill in all values
uvicorn main:app --reload     # http://localhost:8000
```

### Environment variables

See `xene-backend/.env.example` for the full list. Required:

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `TWITCH_CLIENT_ID` | Twitch Helix API client ID |
| `TWITCH_CLIENT_SECRET` | Twitch Helix API client secret |
| `TOKEN_ENCRYPTION_KEY` | Fernet key for OAuth token storage |
| `FRONTEND_URL` | CORS origin (e.g. `http://localhost:5173`) |

---

## API integrations

| Platform | What Xene uses | Purpose |
|---|---|---|
| SoundCloud | Public RSS feeds + oEmbed | Track and release activity |
| Bandcamp | Public RSS feeds | Release activity |
| Twitch | Helix API — streams endpoint | Live stream status |
| Instagram | Meta Graph API | Post activity (in progress) |

All integrations use public APIs or official developer programs. API credentials are never exposed to the frontend.

---

## Contact

Platform partnership and API inquiries: [collab.xene@gmail.com](mailto:collab.xene@gmail.com?subject=Xene%20API%20Partnership%20Inquiry)
