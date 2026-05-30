"""
KaPak - Application Configuration
Loads environment variables and provides app-wide settings.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    APP_NAME: str = "KaPak"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://postgres.ivupxixbxyxddzgtvyet:Xa1qJVd6QgVkkpyy@aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require"

    # JWT Authentication
    SECRET_KEY: str = "kapak-super-secret-key-change-in-production-2025"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Redis
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # OpenAI / Google AI Studio (OpenAI-compatible endpoint)
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GOOGLE_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # Celery (background task queue)
    CELERY_BROKER_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://127.0.0.1:6379/0"

    # Email
    FRONTEND_URL: str = "http://localhost:5173"
    PUBLIC_BACKEND_URL: str = ""

    # Cloudinary Base Storage
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    MAILTRAP_TOKEN: str = ""
    MAILTRAP_SENDER_EMAIL: str = "hello@demomailtrap.co"
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_FROM_NAME: str = "KaPak App"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_mode(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"debug", "development", "dev"}:
                return True
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Returns cached settings instance."""
    return Settings()
