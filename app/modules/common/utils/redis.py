# app/clients/redis_client.py
import asyncio

import redis
from redis import ConnectionPool
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.modules.common.utils.logging import logger

# Create connection pool for better performance (sync client)
redis_pool = ConnectionPool(
    host=settings.REDIS_HOST,
    port=int(settings.REDIS_PORT),
    db=int(settings.REDIS_DB),
    decode_responses=True,
    retry_on_timeout=True,
    socket_timeout=5,
    socket_connect_timeout=5,
    # socket_keepalive handled by OS; don't pass empty options
    health_check_interval=30,
    max_connections=50,
)

redis_client = redis.Redis(connection_pool=redis_pool)

# Async Redis client will be created per event loop
_async_clients = {}  # Store clients per event loop


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
    retry=retry_if_exception_type(redis.exceptions.ConnectionError),
)
def get_redis_client():
    """
    Get Redis client with error handling and retry.
    """
    try:
        # quick ping to ensure connection usable
        redis_client.ping()
        return redis_client
    except Exception as e:
        logger.exception("Redis connection error (pool): %s", e)
        # Fallback to fresh connection (no pool)
        fallback = redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            db=int(settings.REDIS_DB),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        try:
            fallback.ping()
            logger.warning("Using fallback redis connection (no pool).")
            return fallback
        except Exception as e2:
            logger.exception("Fallback redis connection also failed: %s", e2)
            raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
    retry=retry_if_exception_type(redis.exceptions.ConnectionError),
)
async def get_async_redis_client():
    """
    Get async Redis client with error handling and retry.
    Creates client per event loop to avoid multiprocessing issues.
    """
    try:
        import redis.asyncio as aioredis
    except ImportError:
        raise RuntimeError("Async Redis client not available. Please install aioredis.")

    # Get current event loop
    loop = asyncio.get_running_loop()
    loop_id = id(loop)

    # Check if we already have a client for this event loop
    if loop_id in _async_clients:
        client = _async_clients[loop_id]
        try:
            await client.ping()
            return client
        except Exception:
            # Client is dead, remove it and create a new one
            del _async_clients[loop_id]

    # Create new client for this event loop
    try:
        client = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            db=int(settings.REDIS_DB),
            decode_responses=True,
            retry_on_timeout=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            health_check_interval=30,
            max_connections=20,  # Lower for async
        )
        await client.ping()
        _async_clients[loop_id] = client
        logger.info("Async Redis client initialized for event loop %s", loop_id)
        return client
    except Exception as e:
        logger.exception("Failed to create async Redis client: %s", e)
        raise


async def publish_to_user_channel(user_id: str, message: dict) -> bool:
    """
    Publish message to user's Redis channel using hierarchical pattern.
    Channel format: user:{user_id}:{message_type}
    """
    try:
        client = await get_async_redis_client()
        channel = f"user:{user_id}:{message.get('type', 'notification')}"
        import json

        data = json.dumps(message)
        result = await client.publish(channel, data)
        logger.debug("Published to %s (subscribers=%s): %s", channel, result, message)
        return True
    except Exception as e:
        logger.exception("Failed to publish to user channel %s: %s", user_id, e)
        return False


async def get_recent_messages_for_user(user_id: str, limit: int = 10) -> list:
    """
    Get recent messages for a user from Redis for replay functionality.
    This is used when a WebSocket client reconnects.
    """
    try:
        client = await get_async_redis_client()
        # Get all task progress keys for this user
        pattern = f"task_progress:*:{user_id}"
        keys = await client.keys(pattern)

        messages = []
        for key in keys[:limit]:  # Limit to prevent overwhelming
            try:
                data = await client.hgetall(key)
                if data:
                    # Extract task_id from key: task_progress:{task_id}:{user_id}
                    parts = key.split(":")
                    task_id = parts[1] if len(parts) >= 3 else None
                    message = {
                        "type": "task_progress",
                        "data": {**data, "task_id": task_id},
                    }
                    messages.append(message)
            except Exception as e:
                logger.exception("Failed to read message from key %s: %s", key, e)

        # Sort by last_update timestamp (most recent first)
        messages.sort(key=lambda x: x["data"].get("last_update", ""), reverse=True)
        return messages[:limit]
    except Exception as e:
        logger.exception("Failed to get recent messages for user %s: %s", user_id, e)
        return []
