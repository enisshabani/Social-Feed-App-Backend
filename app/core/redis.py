import json
import logging
from typing import Any, Callable

from app.core.config import get_settings
from app.core.cache import cache_service

logger = logging.getLogger("kapak.redis")
settings = get_settings()

def get_or_set_cache(key: str, ttl_seconds: int, fetch_func: Callable[[], Any]) -> Any:
    """
    Reusable cache helper.
    Attempts to fetch from unified cache_service.
    If it was a miss, saves the result to cache.
    """
    try:
        cached_data = cache_service.get(key)
        if cached_data is not None:
            return cached_data
    except Exception as e:
        logger.error(f"Redis get error for key {key}: {str(e)}")

    # Cache miss or error reading
    data = fetch_func()

    if data is not None:
        try:
            cache_service.set(key, data, expire_seconds=ttl_seconds)
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {str(e)}")

    return data

def invalidate_cache(key: str):
    """Deletes a key from cache."""
    try:
        cache_service.delete(key)
    except Exception as e:
        logger.error(f"Redis delete error for key {key}: {str(e)}")
