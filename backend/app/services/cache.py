import json
import logging
import time
from typing import Optional

from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)


class ResponseCache:
    """Redis 우선 응답 캐시, 장애 시 메모리 폴백."""

    def __init__(self):
        self._redis: Optional[Redis] = None
        self._memory_cache: dict[str, tuple[float, str]] = {}

    async def _get_redis(self) -> Optional[Redis]:
        if self._redis is not None:
            return self._redis
        try:
            client = Redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
            await client.ping()
            self._redis = client
            return self._redis
        except Exception as exc:
            logger.warning("Redis unavailable, fallback to in-memory cache: %s", exc)
            return None

    async def get(self, key: str) -> Optional[str]:
        redis_client = await self._get_redis()
        if redis_client is not None:
            try:
                return await redis_client.get(key)
            except Exception as exc:
                logger.warning("Redis get failed, using memory fallback: %s", exc)

        entry = self._memory_cache.get(key)
        if not entry:
            return None

        expires_at, payload = entry
        if expires_at < time.time():
            self._memory_cache.pop(key, None)
            return None
        return payload

    async def set(self, key: str, payload: str, ttl_seconds: int) -> None:
        redis_client = await self._get_redis()
        if redis_client is not None:
            try:
                await redis_client.set(key, payload, ex=ttl_seconds)
                return
            except Exception as exc:
                logger.warning("Redis set failed, using memory fallback: %s", exc)

        self._memory_cache[key] = (time.time() + ttl_seconds, payload)


response_cache = ResponseCache()
