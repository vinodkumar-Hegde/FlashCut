import re
import uuid

from starlette.datastructures import (
    Headers,
    MutableHeaders,
)
from starlette.responses import (
    JSONResponse,
)

from app.core.config import Settings


REQUEST_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9]"
    r"[A-Za-z0-9._:-]{0,127}$"
)


class RequestTooLarge(Exception):
    pass


class SecurityMiddleware:
    def __init__(
        self,
        app,
        *,
        settings: Settings,
    ):
        self.app = app
        self.settings = settings

    async def __call__(
        self,
        scope,
        receive,
        send,
    ):
        if (
            scope["type"]
            != "http"
        ):
            await self.app(
                scope,
                receive,
                send,
            )

            return

        headers = Headers(
            scope=scope
        )

        supplied_request_id = (
            headers.get(
                "x-request-id",
                "",
            )
            .strip()
        )

        if (
            supplied_request_id
            and REQUEST_ID_PATTERN
            .fullmatch(
                supplied_request_id
            )
        ):
            request_id = (
                supplied_request_id
            )

        else:
            request_id = str(
                uuid.uuid4()
            )

        state = scope.setdefault(
            "state",
            {},
        )

        state[
            "request_id"
        ] = request_id

        async def secure_send(
            message,
        ):
            if (
                message["type"]
                == "http.response.start"
            ):
                response_headers = (
                    MutableHeaders(
                        scope=message
                    )
                )

                response_headers[
                    "X-Request-ID"
                ] = request_id

                response_headers[
                    "X-Content-Type-Options"
                ] = "nosniff"

                response_headers[
                    "X-Frame-Options"
                ] = "DENY"

                response_headers[
                    "Referrer-Policy"
                ] = "no-referrer"

                response_headers[
                    "Permissions-Policy"
                ] = (
                    "camera=(), "
                    "microphone=(), "
                    "geolocation=()"
                )

                path = scope.get(
                    "path",
                    "",
                )

                if path.startswith(
                    "/api/"
                ):
                    response_headers[
                        "Cache-Control"
                    ] = "no-store"

                    response_headers[
                        "Content-Security-Policy"
                    ] = (
                        "default-src 'none'; "
                        "frame-ancestors 'none'; "
                        "base-uri 'none'"
                    )

                if (
                    self.settings
                    .app_env
                    .strip()
                    .lower()
                    == "production"
                ):
                    response_headers[
                        "Strict-Transport-Security"
                    ] = (
                        "max-age=31536000; "
                        "includeSubDomains"
                    )

                rate_limit_limit = (
                    state.get(
                        "rate_limit_limit"
                    )
                )

                if (
                    rate_limit_limit
                    is not None
                ):
                    response_headers[
                        "RateLimit-Limit"
                    ] = str(
                        rate_limit_limit
                    )

                    response_headers[
                        "RateLimit-Remaining"
                    ] = str(
                        state.get(
                            "rate_limit_remaining",
                            0,
                        )
                    )

                    response_headers[
                        "RateLimit-Reset"
                    ] = str(
                        state.get(
                            "rate_limit_reset",
                            0,
                        )
                    )

            await send(
                message
            )

        content_length = headers.get(
            "content-length"
        )

        if content_length:
            try:
                declared_size = int(
                    content_length
                )

            except ValueError:
                await self._error(
                    scope=scope,
                    receive=receive,
                    send=secure_send,
                    request_id=request_id,
                    status_code=400,
                    code=(
                        "INVALID_CONTENT_LENGTH"
                    ),
                    message=(
                        "Invalid Content-Length "
                        "header."
                    ),
                )

                return

            if declared_size < 0:
                await self._error(
                    scope=scope,
                    receive=receive,
                    send=secure_send,
                    request_id=request_id,
                    status_code=400,
                    code=(
                        "INVALID_CONTENT_LENGTH"
                    ),
                    message=(
                        "Invalid Content-Length "
                        "header."
                    ),
                )

                return

            if (
                declared_size
                > self.settings
                .max_request_bytes
            ):
                await self._too_large(
                    scope,
                    receive,
                    secure_send,
                    request_id,
                )

                return

        received_bytes = 0

        async def limited_receive():
            nonlocal received_bytes

            message = await receive()

            if (
                message["type"]
                == "http.request"
            ):
                received_bytes += len(
                    message.get(
                        "body",
                        b"",
                    )
                )

                if (
                    received_bytes
                    > self.settings
                    .max_request_bytes
                ):
                    raise RequestTooLarge()

            return message

        try:
            await self.app(
                scope,
                limited_receive,
                secure_send,
            )

        except RequestTooLarge:
            await self._too_large(
                scope,
                receive,
                secure_send,
                request_id,
            )

    async def _too_large(
        self,
        scope,
        receive,
        send,
        request_id,
    ):
        await self._error(
            scope=scope,
            receive=receive,
            send=send,
            request_id=request_id,
            status_code=413,
            code=(
                "REQUEST_TOO_LARGE"
            ),
            message=(
                "Request body exceeds "
                "the maximum allowed size."
            ),
        )

    async def _error(
        self,
        *,
        scope,
        receive,
        send,
        request_id,
        status_code,
        code,
        message,
    ):
        state = scope.setdefault(
            "state",
            {},
        )

        state[
            "error_code"
        ] = code

        response = JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                },
                "request_id":
                    request_id,
            },
        )

        await response(
            scope,
            receive,
            send,
        )
