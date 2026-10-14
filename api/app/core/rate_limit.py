import hashlib
import time

from fastapi import Request
from redis.exceptions import RedisError

from app.core.config import (
    get_settings,
)
from app.core.errors import AppError
from app.providers.redis import (
    redis_client,
)


WRITE_METHODS = {
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
}


INCREMENT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])

if current == 1 then
    redis.call(
        'EXPIRE',
        KEYS[1],
        tonumber(ARGV[1])
    )
end

return current
"""


def _identity_hash(
    *,
    tenant_id: str,
    subject: str,
) -> str:
    value = (
        tenant_id
        + "\0"
        + subject
    )

    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


def _consume(
    *,
    identity: str,
    scope: str,
    limit: int,
    now: float,
) -> tuple[int, int, int]:
    bucket = int(
        now // 60
    )

    reset_seconds = max(
        1,
        60 - int(
            now % 60
        ),
    )

    key = (
        "flashcut:rate:"
        f"{identity}:"
        f"{scope}:"
        f"{bucket}"
    )

    try:
        current = int(
            redis_client().eval(
                INCREMENT_SCRIPT,
                1,
                key,
                70,
            )
        )

    except RedisError as exc:
        raise AppError(
            503,
            "RATE_LIMITER_UNAVAILABLE",
            (
                "Request limiting is "
                "temporarily unavailable."
            ),
            headers={
                "Retry-After": "1"
            },
        ) from exc

    remaining = max(
        0,
        limit - current,
    )

    if current > limit:
        raise AppError(
            429,
            "RATE_LIMIT_EXCEEDED",
            (
                "Too many requests. "
                "Retry after the current "
                "rate-limit window."
            ),
            headers={
                "Retry-After":
                    str(
                        reset_seconds
                    ),

                "RateLimit-Limit":
                    str(limit),

                "RateLimit-Remaining":
                    "0",

                "RateLimit-Reset":
                    str(
                        reset_seconds
                    ),
            },
        )

    return (
        limit,
        remaining,
        reset_seconds,
    )


def enforce_rate_limit(
    request: Request,
    *,
    tenant_id: str,
    subject: str,
) -> None:
    settings = get_settings()

    if not settings.rate_limit_enabled:
        return

    now = time.time()

    identity = _identity_hash(
        tenant_id=tenant_id,
        subject=subject,
    )

    selected = _consume(
        identity=identity,
        scope="all",
        limit=(
            settings
            .rate_limit_requests_per_minute
        ),
        now=now,
    )

    if (
        request.method.upper()
        in WRITE_METHODS
    ):
        write_result = _consume(
            identity=identity,
            scope="write",
            limit=(
                settings
                .rate_limit_write_requests_per_minute
            ),
            now=now,
        )

        if (
            write_result[1]
            < selected[1]
        ):
            selected = write_result

    (
        request.state.rate_limit_limit,
        request.state.rate_limit_remaining,
        request.state.rate_limit_reset,
    ) = selected
