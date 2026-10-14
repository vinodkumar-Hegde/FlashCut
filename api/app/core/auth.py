import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt

from fastapi import Depends
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jwt import PyJWKClient
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidIssuerError,
    InvalidTokenError,
    PyJWKClientError,
)

from app.core.config import (
    Settings,
    get_settings,
)
from app.core.errors import AppError


bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description=(
        "JWT access token issued by the "
        "configured identity provider."
    ),
)


TENANT_PATTERN = re.compile(
    r"^[A-Za-z0-9]"
    r"[A-Za-z0-9._:-]{0,127}$"
)


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str


def authentication_error(
    code: str = "INVALID_TOKEN",
    message: str = (
        "The access token is invalid "
        "or has expired."
    ),
) -> AppError:
    return AppError(
        401,
        code,
        message,
        headers={
            "WWW-Authenticate":
                "Bearer"
        },
    )


def forbidden_error(
    code: str,
    message: str,
) -> AppError:
    return AppError(
        403,
        code,
        message,
    )


def jwks_url(
    settings: Settings,
) -> str:
    configured = (
        settings.auth_jwks_url
        or ""
    ).strip()

    if configured:
        return configured

    issuer = (
        settings.auth_jwt_issuer
        or ""
    ).strip().rstrip("/")

    if not issuer:
        raise RuntimeError(
            "JWT issuer is not configured."
        )

    return (
        issuer
        + "/.well-known/jwks.json"
    )


@lru_cache(maxsize=8)
def cached_jwks_client(
    url: str,
) -> PyJWKClient:
    return PyJWKClient(
        url,
        cache_keys=True,
        cache_jwk_set=True,
        lifespan=300,
        timeout=5,
    )


def algorithms(
    settings: Settings,
) -> list[str]:
    result = [
        item.strip()
        for item
        in settings
        .auth_jwt_algorithms
        .split(",")
        if item.strip()
    ]

    if not result:
        raise RuntimeError(
            "No JWT algorithms configured."
        )

    return result


def claim_matches(
    actual,
    expected: str,
) -> bool:
    if isinstance(
        actual,
        str,
    ):
        return actual == expected

    if isinstance(
        actual,
        (
            list,
            tuple,
            set,
        ),
    ):
        return expected in actual

    return False


def validate_jwt_token(
    token: str,
    *,
    settings: Settings | None = None,
    jwks_client=None,
) -> Principal:
    settings = (
        settings
        or get_settings()
    )

    issuer = (
        settings.auth_jwt_issuer
        or ""
    ).strip()

    expected_audience = (
        settings.auth_jwt_audience
        or ""
    ).strip()

    if (
        not issuer
        or not expected_audience
    ):
        raise AppError(
            503,
            "AUTH_CONFIGURATION_ERROR",
            (
                "Authentication provider "
                "configuration is incomplete."
            ),
        )

    client = (
        jwks_client
        or cached_jwks_client(
            jwks_url(
                settings
            )
        )
    )

    try:
        signing_key = (
            client
            .get_signing_key_from_jwt(
                token
            )
            .key
        )

        claims = jwt.decode(
            token,
            signing_key,
            algorithms=algorithms(
                settings
            ),
            issuer=issuer,
            leeway=max(
                0,
                settings
                .auth_clock_skew_seconds,
            ),
            options={
                "verify_aud":
                    False,

                "require": [
                    "exp",
                    "iat",
                    "iss",
                ],
            },
        )

    except ExpiredSignatureError as exc:
        raise authentication_error(
            "TOKEN_EXPIRED",
            (
                "The access token "
                "has expired."
            ),
        ) from exc

    except InvalidIssuerError as exc:
        raise authentication_error(
            "INVALID_TOKEN_ISSUER",
            (
                "The access token was "
                "issued by an unexpected "
                "identity provider."
            ),
        ) from exc

    except (
        InvalidTokenError,
        PyJWKClientError,
        ValueError,
    ) as exc:
        raise authentication_error() from exc

    audience_claim_name = (
        settings
        .auth_jwt_audience_claim
        .strip()
    )

    actual_audience = claims.get(
        audience_claim_name
    )

    if not claim_matches(
        actual_audience,
        expected_audience,
    ):
        raise authentication_error(
            "INVALID_TOKEN_AUDIENCE",
            (
                "The access token is not "
                "intended for DT-FlashCut."
            ),
        )

    expected_token_use = (
        settings
        .auth_jwt_token_use
        or ""
    ).strip()

    if expected_token_use:
        actual_token_use = str(
            claims.get(
                "token_use",
                "",
            )
        ).strip()

        if (
            actual_token_use
            != expected_token_use
        ):
            raise authentication_error(
                "INVALID_TOKEN_USE",
                (
                    "The supplied token "
                    "cannot be used to "
                    "access this API."
                ),
            )

    subject_claim = (
        settings
        .auth_subject_claim
        .strip()
    )

    subject = str(
        claims.get(
            subject_claim,
            "",
        )
    ).strip()

    if (
        not subject
        or len(subject) > 256
    ):
        raise authentication_error(
            "INVALID_TOKEN_SUBJECT",
            (
                "The access token does "
                "not identify a user."
            ),
        )

    tenant_claim = (
        settings
        .auth_tenant_claim
        .strip()
    )

    tenant_id = str(
        claims.get(
            tenant_claim,
            "",
        )
    ).strip()

    if not tenant_id:
        raise forbidden_error(
            "TENANT_ACCESS_REQUIRED",
            (
                "The authenticated identity "
                "is not assigned to a tenant."
            ),
        )

    if not TENANT_PATTERN.fullmatch(
        tenant_id
    ):
        raise forbidden_error(
            "INVALID_TENANT_CLAIM",
            (
                "The tenant identifier in "
                "the access token is invalid."
            ),
        )

    return Principal(
        subject=subject,
        tenant_id=tenant_id,
    )


def require_principal(
    credentials: Annotated[
        HTTPAuthorizationCredentials
        | None,
        Depends(
            bearer_scheme
        ),
    ] = None,
) -> Principal:
    settings = get_settings()

    if settings.auth_disabled:
        return Principal(
            subject=(
                "local-development"
            ),
            tenant_id=(
                settings.local_tenant_id
            ),
        )

    if credentials is None:
        raise authentication_error(
            "AUTHENTICATION_REQUIRED",
            "Authentication is required.",
        )

    if (
        credentials.scheme.lower()
        != "bearer"
    ):
        raise authentication_error(
            "INVALID_AUTHENTICATION_SCHEME",
            (
                "Use a Bearer access token."
            ),
        )

    token = (
        credentials.credentials
        .strip()
    )

    if not token:
        raise authentication_error(
            "AUTHENTICATION_REQUIRED",
            "Authentication is required.",
        )

    return validate_jwt_token(
        token,
        settings=settings,
    )
