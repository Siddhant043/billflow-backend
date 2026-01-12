from redis import asyncio as aioredis
from typing import Optional
import json
from app.core.config import settings

class RedisClient:
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None

    async def connect(self):
        """Connect to Redis."""
        self.redis = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()

    async def get(self, key:str) -> Optional[str]:
        """Get a value from Redis."""
        if self.redis:
            return await self.redis.get(key)
        return None

    async def set(self, key:str, value:str, expire: Optional[int] = 3600 ) -> bool:
        """Set a value in Redis."""
        if self.redis:
            await self.redis.set(key, value, ex=expire)
            return True
        return False
    
    async def delete(self, key:str) -> bool:
        """Delete a key from Redis."""
        if self.redis:
            await self.redis.delete(key)
            return True
        return False
    
    async def exists(self, key:str) -> bool:
        """Check if a key exists in Redis."""
        if self.redis:
            return await self.redis.exists(key) > 0
        return False
    
    async def get_json(self, key:str) -> Optional[dict]:
        """Get and parse JSON value."""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None

    async def set_json(self, key:str, value: dict, expire: Optional[int] = 3600) -> bool:
        """Set a JSON value in Redis."""
        if self.redis:
            return await self.redis.set(key, json.dumps(value), ex=expire)
        return False

    async def invalidate_pattern(self, pattern:str) -> bool:
        """Delete all keys matching pattern."""
        if not self.redis:
            return
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern)
            if keys:
                await self.redis.delete(*keys)
            if cursor == 0:
                break

# Global Redis Client Instance
redis_client = RedisClient()