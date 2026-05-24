import json
import logging
from typing import Any, Callable

import redis

from app.core.config import get_settings

logger = logging.getLogger("kapak.redis")
settings = get_settings()

try:
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_timeout=2,
        socket_connect_timeout=2
    )
    # Test connection
    redis_client.ping()
    logger.info("✅ Connected to Redis successfully")
except Exception as e:
    logger.warning(f"⚠️ Redis connection failed: {str(e)}. Caching will be disabled.")
    redis_client = None

def get_or_set_cache(key: str, ttl_seconds: int, fetch_func: Callable[[], Any]) -> Any:
    """
    Reusable cache helper.
    Attempts to fetch from Redis. If miss or Redis is down, calls fetch_func().
    If it was a miss, saves the result to Redis.
    """
    if redis_client is None:
        return fetch_func()

    try:
        cached_data = redis_client.get(key)
        if cached_data is not None:
            return json.loads(cached_data)
    except Exception as e:
        logger.error(f"Redis get error for key {key}: {str(e)}")

    # Cache miss or error reading
    data = fetch_func()

    if redis_client is not None:
        try:
            redis_client.setex(key, ttl_seconds, json.dumps(data))
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {str(e)}")

    return data

def invalidate_cache(key: str):
    """Deletes a key from Redis."""
    if redis_client is not None:
        try:
            redis_client.delete(key)
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {str(e)}")
