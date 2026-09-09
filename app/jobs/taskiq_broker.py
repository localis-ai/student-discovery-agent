from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from app.core.config import settings
from app.core.vault_loader import load_config

load_config()

result_backend = RedisAsyncResultBackend(redis_url=settings.REDIS_URL)
broker = ListQueueBroker(url=settings.REDIS_URL).with_result_backend(result_backend)

try:
    from app.modules.common.utils.logging import logger, setup_logging

    setup_logging(settings.LOG_LEVEL)
    logger.info("Configuration and logging initialized for TaskIQ worker.")
    logger.info(f"TaskIQ Redis URL: {settings.REDIS_URL}")
except ImportError:
    pass
