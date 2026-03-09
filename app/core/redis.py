import redis.asyncio as redis
from app.core.config import settings
from app.core.logging import logger
import json
import asyncio

class RedisService:
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self.enabled = settings.REDIS_ENABLED
        self.client = None
        self.pubsub_task = None

    async def connect(self):
        if not self.enabled:
            logger.info("[Redis] Disabled in settings")
            return
        
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            # Test connection
            await self.client.ping()
            logger.info(f"[Redis] Connected to {self.redis_url}")
        except Exception as e:
            logger.error(f"[Redis] Connection failed: {e}")
            self.enabled = False
            self.client = None

    async def disconnect(self):
        if self.client:
            await self.client.close()

    async def publish(self, channel: str, message: dict):
        if not self.enabled or not self.client:
            return
        try:
            await self.client.publish(channel, json.dumps(message))
        except Exception as e:
            logger.error(f"[Redis] Publish error: {e}")

    async def subscribe(self, channel: str, callback):
        """Standard pub/sub with callback"""
        if not self.enabled or not self.client:
            return

        async with self.client.pubsub() as pubsub:
            await pubsub.subscribe(channel)
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await callback(data)
                    except Exception as e:
                        logger.error(f"[Redis] PubSub callback error: {e}")

redis_service = RedisService()
