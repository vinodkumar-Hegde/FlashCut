from dataclasses import dataclass
from typing import Annotated

from fastapi import Header

from app.core.config import get_settings
from app.core.errors import AppError


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str | None = None


def require_principal(
    authorization: Annotated[
        str | None,
        Header()
    ] = None,
) -> Principal:
    settings = get_settings()

    if settings.auth_disabled:
        return Principal(
            subject="local-development"
        )

    if not authorization:
        raise AppError(
            401,
            "AUTHENTICATION_REQUIRED",
            "Authentication is required.",
        )

    raise AppError(
        503,
        "AUTH_PROVIDER_NOT_CONFIGURED",
        (
            "Production authentication "
            "has not been configured."
        ),
    )
