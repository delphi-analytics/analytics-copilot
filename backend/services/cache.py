import json
import structlog
from redis import asyncio as aioredis
from typing import Any, Optional
from backend.config import settings

log = structlog.get_logger(__name__)

class RedisCache:
    def __init__(self):
        self.redis = None

    async def connect(self):
        if not self.redis:
            self.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            try:
                await self.redis.ping()
                log.info("redis.connected", url=settings.redis_url)
            except Exception as e:
                log.error("redis.connection_failed", error=str(e))

    async def get(self, key: str) -> Optional[dict[str, Any]]:
        if not self.redis:
            await self.connect()
        try:
            val = await self.redis.get(key)
            if val:
                return json.loads(val)
        except Exception as e:
            log.warning("redis.get_failed", key=key, error=str(e))
        return None

    async def set(self, key: str, value: dict[str, Any], expire_seconds: int = 3600):
        if not self.redis:
            await self.connect()
        try:
            await self.redis.setex(key, expire_seconds, json.dumps(value))
        except Exception as e:
            log.warning("redis.set_failed", key=key, error=str(e))

redis_cache = RedisCache()
