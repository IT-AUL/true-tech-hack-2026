import json
import logging
from typing import Any, Optional

from open_webui.utils.redis import get_redis_client

log = logging.getLogger(__name__)

# Fallback in-memory dictionary if Redis is not available
_LOCAL_CACHE: dict[str, Any] = {}

class SessionMemoryCache:
    """Session Memory Cache wrapper for thread context and topic hashes.
    Uses Redis if available, otherwise falls back to a local dictionary.
    """

    def __init__(self):
        self.redis = get_redis_client(async_mode=True)
        if hasattr(self.redis, 'get_connection_kwargs'):
            pass  # It's a standard redis asyncio client
        
    async def get(self, key: str) -> Optional[Any]:
        if self.redis:
            try:
                data = await self.redis.get(key)
                if data:
                    return json.loads(data)
                return None
            except Exception as e:
                log.warning(f'Redis get error (fallback to local): {e}')
        return _LOCAL_CACHE.get(key)

    async def set(self, key: str, value: Any, ttl_seconds: int = 900) -> bool:
        if self.redis:
            try:
                data = json.dumps(value)
                await self.redis.set(key, data, ex=ttl_seconds)
                return True
            except Exception as e:
                log.warning(f'Redis set error (fallback to local): {e}')

        # Fallback
        _LOCAL_CACHE[key] = value
        # Note: Local cache does not automatically expire TTL in this simple fallback
        return True

    async def delete(self, key: str) -> bool:
        if self.redis:
            try:
                await self.redis.delete(key)
                return True
            except Exception as e:
                log.warning(f'Redis delete error (fallback to local): {e}')
        if key in _LOCAL_CACHE:
            del _LOCAL_CACHE[key]
            return True
        return False

# Global instance
session_cache = SessionMemoryCache()
