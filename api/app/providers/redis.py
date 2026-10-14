from functools import lru_cache

from redis import Redis

from app.core.config import (
    get_settings,
)


@lru_cache
def redis_client() -> Redis:
    settings = get_settings()

    if not settings.redis_url:
        raise RuntimeError(
            "REDIS_URL is not configured."
        )

    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
    )
