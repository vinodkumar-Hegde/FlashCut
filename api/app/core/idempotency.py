import hashlib
import json
import re

from app.core.errors import AppError


KEY_PATTERN = re.compile(
    r"^[A-Za-z0-9]"
    r"[A-Za-z0-9._:-]{0,127}$"
)


def normalize_idempotency_key(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    key = value.strip()

    if (
        not key
        or not KEY_PATTERN.fullmatch(
            key
        )
    ):
        raise AppError(
            400,
            "INVALID_IDEMPOTENCY_KEY",
            (
                "Idempotency-Key must be "
                "1 to 128 characters using "
                "letters, numbers, '.', '_', "
                "':' or '-'."
            ),
        )

    return key


def idempotency_hash(
    *,
    operation: str,
    payload: dict,
) -> str:
    canonical = json.dumps(
        {
            "operation": operation,
            "payload": payload,
        },
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        canonical.encode(
            "utf-8"
        )
    ).hexdigest()


def ensure_idempotency_match(
    *,
    stored_hash: str | None,
    request_hash: str | None,
) -> None:
    if (
        not stored_hash
        or not request_hash
        or stored_hash
        != request_hash
    ):
        raise AppError(
            409,
            "IDEMPOTENCY_CONFLICT",
            (
                "The Idempotency-Key was "
                "already used with a "
                "different request."
            ),
        )
