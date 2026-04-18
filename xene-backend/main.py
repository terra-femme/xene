import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers import feed, auth, artists, twitch, beatport
from jobs.token_refresh import start_scheduler as start_token_scheduler
from jobs.feed_poll import start_feed_scheduler
import os

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[startup] Xene API starting")
    start_token_scheduler()
    start_feed_scheduler()
    yield
    logger.info("[shutdown] Xene API stopping")


app = FastAPI(title="Xene API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(feed.router)
app.include_router(auth.router)
app.include_router(artists.router)
app.include_router(twitch.router)
app.include_router(beatport.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
