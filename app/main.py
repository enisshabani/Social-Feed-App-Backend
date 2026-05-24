import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.middleware import logging_middleware, tenant_middleware

# Krijohet direktoria përpara se FastAPI të bëjë mount StaticFiles
os.makedirs("uploads/avatars", exist_ok=True)
os.makedirs("uploads/posts", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("kapak")

settings = get_settings()


def ensure_lightweight_schema_updates():
    """Apply small SQLite-safe schema updates for local/dev databases."""
    try:
        with engine.begin() as conn:
            if engine.dialect.name == "sqlite":
                columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(post_likes)").fetchall()]
                if columns and "reaction_type" not in columns:
                    conn.exec_driver_sql("ALTER TABLE post_likes ADD COLUMN reaction_type VARCHAR(16) DEFAULT 'star' NOT NULL")
                    logger.info("Added post_likes.reaction_type column")
            else:
                conn.exec_driver_sql("ALTER TABLE post_likes ADD COLUMN IF NOT EXISTS reaction_type VARCHAR(16) DEFAULT 'star' NOT NULL")
                logger.info("Added post_likes.reaction_type column")
    except Exception as exc:
        logger.warning("Could not apply lightweight schema updates: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    Base.metadata.create_all(bind=engine)
    ensure_lightweight_schema_updates()
    logger.info("✅ Database tables created/verified")

    yield

    logger.info(f"👋 Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "KaPak - A social media platform similar to Twitter. "
        "Built as a university project for Distributed Systems 2025/26."
    ),
    version=settings.APP_VERSION,
    contact={
        "name": "KaPak Team",
        "url": "https://github.com/kapak",
        "email": "contact@kapak.dev",
    },
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",  # Vite default
        "http://127.0.0.1:5173",
        "https://kapak-496319.web.app",
        "https://kapak-496319.firebaseapp.com",
        "https://kapak-3af75.web.app",
        "https://kapak-3af75.firebaseapp.com",
    ],
    allow_origin_regex=r"^http://([a-zA-Z0-9-]+\.)?(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.middleware("http")(tenant_middleware)
app.middleware("http")(logging_middleware)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ─── Routers ────────────────────────────────────────────────
# Personi 1 - Auth & Users
# Personi 3 - Follows & Notifications
from app.modules.follows.router import router as follows_router
from app.modules.notifications.router import router as notifications_router

# Personi 2 - Posts & Feed
# Personi 4 - Search & Hashtags
from app.routers import ai, auth, feeds, hashtags, posts, search, tasks, users

app.include_router(auth.router,          prefix="/api/v1/auth",          tags=["Authentication"])
app.include_router(users.router,         prefix="/api/v1/users",         tags=["Users"])
app.include_router(posts.router,         prefix="/api/v1/posts",         tags=["Posts & Feed"])
app.include_router(feeds.router,         prefix="/api/v1/feeds",         tags=["Feeds"])
app.include_router(follows_router,       prefix="/api/v1/follows",       tags=["Follows"])
app.include_router(notifications_router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(hashtags.router,      prefix="/api/v1/hashtags",      tags=["Hashtags"])
app.include_router(search.router,        prefix="/api/v1/search",        tags=["Search"])
app.include_router(ai.router,            prefix="/api/v1",               tags=["AI"])
app.include_router(tasks.router,         prefix="/api/v1",               tags=["Tasks"])

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API health check."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "message": "Welcome to KaPak API! 🎒",
    }


@app.get("/health", tags=["Root"])
async def health_check():
    """Health check endpoint for monitoring and Docker."""
    return {
        "status": "healthy",
        "database": "connected",
    }
