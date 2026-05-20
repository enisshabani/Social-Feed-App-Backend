import logging
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine, Base
from app.core.middleware import logging_middleware

# Krijohet direktoria përpara se FastAPI të bëjë mount StaticFiles
os.makedirs("uploads/avatars", exist_ok=True)

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
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    Base.metadata.create_all(bind=engine)
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
    docs_url="/docs",           
    redoc_url="/redoc",         
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.middleware("http")(logging_middleware)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ─── Routers ────────────────────────────────────────────────
# Personi 1 - Auth & Users
from app.routers import auth, users

# Personi 2 - Posts & Feed
from app.routers import posts

app.include_router(auth.router,          prefix="/api/v1/auth",          tags=["Authentication"])
app.include_router(users.router,         prefix="/api/v1/users",         tags=["Users"])
app.include_router(posts.router,         prefix="/api/v1/posts",         tags=["Posts & Feed"])

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
