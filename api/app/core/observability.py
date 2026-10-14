import logging
import time
import uuid
from functools import partial

from anyio import to_thread

from app.core.audit import (
    write_audit_event,
)


logger = logging.getLogger(
    "flashcut.request"
)


WRITE_METHODS = {
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
}


RESOURCE_ID_KEYS = (
    "video_id",
    "transcription_id",
    "job_id",
    "summary_id",
    "selection_id",
    "render_id",
    "note_id",
)


def resource_type_from_path(
    path: str,
) -> str | None:
    parts = [
        item
        for item
        in path.strip("/").split("/")
        if item
    ]

    if (
        len(parts) >= 3
        and parts[0] == "api"
        and parts[1] == "v1"
    ):
        return parts[2][
            :64
        ]

    return None


def resource_id_from_params(
    params: dict,
) -> str | None:
    for key in RESOURCE_ID_KEYS:
        value = params.get(
            key
        )

        if value is not None:
            return str(
                value
            )[:128]

    for key, value in params.items():
        if (
            key.endswith(
                "_id"
            )
            and value is not None
        ):
            return str(
                value
            )[:128]

    return None


def safe_path_params(
    params: dict,
) -> dict:
    result = {}

    for key, value in params.items():
        result[
            str(key)[:64]
        ] = str(
            value
        )[:128]

    return result


def outcome_for_status(
    status_code: int,
) -> str:
    if (
        200
        <= status_code
        < 400
    ):
        return "succeeded"

    if status_code in {
        401,
        403,
        429,
    }:
        return "denied"

    return "failed"


class ObservabilityMiddleware:
    def __init__(
        self,
        app,
    ):
        self.app = app

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

        started = (
            time.perf_counter()
        )

        status_code = 500

        async def tracked_send(
            message,
        ):
            nonlocal status_code

            if (
                message["type"]
                == "http.response.start"
            ):
                status_code = int(
                    message[
                        "status"
                    ]
                )

            await send(
                message
            )

        try:
            await self.app(
                scope,
                receive,
                tracked_send,
            )

        finally:
            duration_ms = round(
                (
                    time.perf_counter()
                    - started
                )
                * 1000,
                3,
            )

            state = scope.setdefault(
                "state",
                {},
            )

            request_id = str(
                state.get(
                    "request_id"
                )
                or uuid.uuid4()
            )[:128]

            tenant_id = state.get(
                "tenant_id"
            )

            subject = state.get(
                "subject"
            )

            error_code = state.get(
                "error_code"
            )

            method = str(
                scope.get(
                    "method",
                    "",
                )
            ).upper()[:16]

            path = str(
                scope.get(
                    "path",
                    "",
                )
            )[:2048]

            route_object = (
                scope.get(
                    "route"
                )
            )

            route = getattr(
                route_object,
                "path",
                None,
            )

            if route is not None:
                route = str(
                    route
                )[:512]

            route_name = getattr(
                route_object,
                "name",
                None,
            )

            if route_name is not None:
                route_name = str(
                    route_name
                )[:128]

            path_params = dict(
                scope.get(
                    "path_params",
                    {},
                )
                or {}
            )

            resource_type = (
                resource_type_from_path(
                    path
                )
            )

            resource_id = (
                resource_id_from_params(
                    path_params
                )
            )

            outcome = (
                outcome_for_status(
                    status_code
                )
            )

            action = (
                route_name
                or (
                    method.lower()
                    + ":"
                    + (
                        resource_type
                        or "api"
                    )
                )
            )[:128]

            level = logging.INFO

            if (
                status_code
                >= 500
            ):
                level = logging.ERROR

            elif (
                status_code
                >= 400
            ):
                level = logging.WARNING

            logger.log(
                level,
                "HTTP request completed",
                extra={
                    "event":
                        "http_request",

                    "request_id":
                        request_id,

                    "tenant_id":
                        tenant_id,

                    "subject":
                        subject,

                    "method":
                        method,

                    "route":
                        route,

                    "path":
                        path,

                    "status_code":
                        status_code,

                    "duration_ms":
                        duration_ms,

                    "action":
                        action,

                    "outcome":
                        outcome,

                    "resource_type":
                        resource_type,

                    "resource_id":
                        resource_id,

                    "error_code":
                        error_code,
                },
            )

            if (
                method
                not in WRITE_METHODS
                or not path.startswith(
                    "/api/"
                )
            ):
                return

            details = {}

            if path_params:
                details[
                    "path_params"
                ] = safe_path_params(
                    path_params
                )

            try:
                await to_thread.run_sync(
                    partial(
                        write_audit_event,
                        tenant_id=(
                            str(
                                tenant_id
                            )[:128]
                            if tenant_id
                            else None
                        ),
                        actor_subject=(
                            str(
                                subject
                            )[:256]
                            if subject
                            else None
                        ),
                        request_id=(
                            request_id
                        ),
                        method=method,
                        route=route,
                        path=path,
                        status_code=(
                            status_code
                        ),
                        action=action,
                        outcome=outcome,
                        resource_type=(
                            resource_type
                        ),
                        resource_id=(
                            resource_id
                        ),
                        duration_ms=(
                            duration_ms
                        ),
                        error_code=(
                            str(
                                error_code
                            )[:128]
                            if error_code
                            else None
                        ),
                        details=details,
                    )
                )

            except Exception:
                logger.exception(
                    "Audit event persistence failed",
                    extra={
                        "event":
                            "audit_write_failed",

                        "request_id":
                            request_id,

                        "tenant_id":
                            tenant_id,

                        "subject":
                            subject,

                        "method":
                            method,

                        "path":
                            path,

                        "status_code":
                            status_code,

                        "action":
                            action,
                    },
                )
