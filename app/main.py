"""
KaPak - Social Media Platform API
Main application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine, Base
from app.core.middleware import logging_middleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("kapak")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Create database tables (will be replaced by Alembic migrations later)
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables created/verified")
    
    yield
    
    # Shutdown
    logger.info(f"👋 Shutting down {settings.APP_NAME}")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "KaPak - A social media platform similar to Twitter. "
        "Built as a university project for Distributed Systems 2025/26."
    ),
    version=settings.APP_VERSION,
    docs_url="/docs",           # Swagger UI
    redoc_url="/redoc",         # ReDoc
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware - allow React frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",    # React dev server
        "http://localhost:5173"
        "http://localhost:5174",    # Vite dev server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom logging middleware
app.middleware("http")(logging_middleware)


# ─── Routers ────────────────────────────────────────────────
# Personi 1 - Auth & Users
from app.routers import auth, users

# Uncomment as each team member creates their routers:
# from app.routers import posts, feed        # Personi 2
# from app.routers import follow, notifications  # Personi 3
# from app.routers import search, ai         # Personi 4

app.include_router(auth.router,          prefix="/api/v1/auth",          tags=["Authentication"])
app.include_router(users.router,         prefix="/api/v1/users",         tags=["Users"])
# app.include_router(posts.router,         prefix="/api/v1/posts",         tags=["Posts"])
# app.include_router(feed.router,          prefix="/api/v1/feed",          tags=["Feed"])
# app.include_router(follow.router,        prefix="/api/v1/follow",        tags=["Follow"])
# app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
# app.include_router(search.router,        prefix="/api/v1/search",        tags=["Search"])
# app.include_router(ai.router,            prefix="/api/v1/ai",            tags=["AI"])


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
