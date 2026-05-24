"""
KaPak - Cache Module
Implements Redis caching with a seamless in-memory dictionary fallback when Redis is offline.
"""

import json
import logging
import time
from typing import Any, Dict, Optional

from app.core.config import get_settings

try:
    import redis
    redis_available = True
except ImportError:
    redis_available = False

logger = logging.getLogger(__name__)
settings = get_settings()


class InMemoryCache:
    """Fallback in-memory cache with expiration support."""

    def __init__(self):
        self._store: Dict[str, tuple[Any, float]] = {}  # key -> (value_json_string, expire_at)

    def get(self, key: str) -> Optional[str]:
        """Fetch a value from the cache, discarding if expired."""
        if key not in self._store:
            return None
        val, expire_at = self._store[key]
        if expire_at is not None and time.time() > expire_at:
            del self._store[key]
            return None
        return val

    def set(self, key: str, value: str, expire: Optional[int] = None) -> None:
        """Set a value in the cache with optional expiration in seconds."""
        expire_at = (time.time() + expire) if expire else None
        self._store[key] = (value, expire_at)

    def delete(self, key: str) -> None:
        """Delete a key."""
        if key in self._store:
            del self._store[key]

    def clear(self) -> None:
        """Clear all keys."""
        self._store.clear()

    def clear_prefix(self, prefix: str) -> None:
        """Remove keys matching a given prefix."""
        keys_to_del = [k for k in self._store.keys() if k.startswith(prefix)]
        for k in keys_to_del:
            del self._store[k]


class Cache:
    """Universal caching service: uses Redis when available, falls back to memory otherwise."""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.in_memory = InMemoryCache()
        self.is_redis_active = False

        if redis_available and settings.REDIS_URL:
            try:
                # Set a strict socket timeout so it doesn't block the app if Redis is down
                self.redis_client = redis.Redis.from_url(
                    settings.REDIS_URL,
                    socket_timeout=1.0,
                    socket_connect_timeout=1.0,
                    decode_responses=True
                )
                # Test connectivity
                self.redis_client.ping()
                self.is_redis_active = True
                logger.info("Successfully connected to Redis cache.")
            except Exception as e:
                logger.warning(
                    f"Redis connection failed ({e}). Falling back to In-Memory Caching."
                )
                self.is_redis_active = False
        else:
            logger.info("Redis library or URL missing. Standardizing on In-Memory Caching.")

    def get(self, key: str) -> Optional[Any]:
        """Get parsed JSON value from cache."""
        try:
            if self.is_redis_active and self.redis_client:
                data = self.redis_client.get(key)
            else:
                data = self.in_memory.get(key)

            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Cache get error for key '{key}': {e}")
        return None

    def set(self, key: str, value: Any, expire_seconds: Optional[int] = 300) -> None:
        """Serialize and set value in cache."""
        try:
            data = json.dumps(value)
            if self.is_redis_active and self.redis_client:
                self.redis_client.set(key, data, ex=expire_seconds)
            else:
                self.in_memory.set(key, data, expire=expire_seconds)
        except Exception as e:
            logger.error(f"Cache set error for key '{key}': {e}")

    def delete(self, key: str) -> None:
        """Invalidate a specific key in cache."""
        try:
            if self.is_redis_active and self.redis_client:
                self.redis_client.delete(key)
            else:
                self.in_memory.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error for key '{key}': {e}")

    def invalidate_prefix(self, prefix: str) -> None:
        """Invalidate all cached keys matching a specific prefix (e.g. invalidating 'feed:')."""
        try:
            if self.is_redis_active and self.redis_client:
                # Find keys using scan
                keys = []
                cursor = 0
                while True:
                    cursor, scan_keys = self.redis_client.scan(cursor, match=f"{prefix}*", count=100)
                    keys.extend(scan_keys)
                    if cursor == 0:
                        break
                if keys:
                    self.redis_client.delete(*keys)
            else:
                self.in_memory.clear_prefix(prefix)
        except Exception as e:
            logger.error(f"Cache invalidate_prefix error for prefix '{prefix}': {e}")


# Global singleton instance
cache_service = Cache()
