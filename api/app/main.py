import logging

from fastapi import (
    FastAPI,
    Request,
)
from fastapi.exceptions import (
    RequestValidationError,
)
from fastapi.responses import (
    JSONResponse,
)
from starlette.middleware.trustedhost import (
    TrustedHostMiddleware,
)

from app.api.health import (
    router as health_router,
)
from app.api.videos import (
    router as videos_router,
)
from app.api.transcriptions import (
    router as transcriptions_router,
)
from app.api.summaries import (
    router as summaries_router,
)
from app.api.selections import (
    router as selections_router,
)
from app.api.renders import (
    router as renders_router,
)
from app.api.render_assets import (
    router as render_assets_router,
)
from app.api.notes import (
    router as notes_router,
)
from app.api.quick_summaries import (
    router as quick_summaries_router,
)
from app.api.learning_materials import (
    router as learning_materials_router,
)
from app.core.config import (
    get_settings,
)
from app.core.errors import AppError
from app.core.logging import (
    configure_logging,
)
from app.core.observability import (
    ObservabilityMiddleware,
)
from app.core.security import (
    SecurityMiddleware,
)


configure_logging()

logger = logging.getLogger(
    "flashcut.api"
)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url=(
        "/docs"
        if settings.app_env
        != "production"
        else None
    ),
    redoc_url=None,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=(
        settings.trusted_host_list
    ),
)

app.add_middleware(
    SecurityMiddleware,
    settings=settings,
)

app.add_middleware(
    ObservabilityMiddleware,
)


@app.exception_handler(
    AppError
)
async def app_error_handler(
    request: Request,
    exc: AppError,
):
    request.state.error_code = (
        exc.code
    )

    return JSONResponse(
        status_code=(
            exc.status_code
        ),
        headers=exc.headers,
        content={
            "error": {
                "code":
                    exc.code,
                "message":
                    exc.message,
            },
            "request_id":
                getattr(
                    request.state,
                    "request_id",
                    None,
                ),
        },
    )


@app.exception_handler(
    RequestValidationError
)
async def validation_handler(
    request: Request,
    exc: RequestValidationError,
):
    request.state.error_code = (
        "VALIDATION_ERROR"
    )

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code":
                    "VALIDATION_ERROR",
                "message":
                    (
                        "The request "
                        "is invalid."
                    ),
                "details":
                    exc.errors(),
            },
            "request_id":
                getattr(
                    request.state,
                    "request_id",
                    None,
                ),
        },
    )


@app.exception_handler(
    Exception
)
async def unexpected_error_handler(
    request: Request,
    exc: Exception,
):
    request.state.error_code = (
        "INTERNAL_ERROR"
    )

    logger.exception(
        "Unhandled API exception"
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code":
                    "INTERNAL_ERROR",
                "message":
                    (
                        "An unexpected "
                        "error occurred."
                    ),
            },
            "request_id":
                getattr(
                    request.state,
                    "request_id",
                    None,
                ),
        },
    )


app.include_router(
    health_router
)

app.include_router(
    videos_router
)

app.include_router(
    transcriptions_router
)

app.include_router(
    summaries_router
)

app.include_router(
    selections_router
)

app.include_router(
    renders_router
)

app.include_router(
    render_assets_router
)

app.include_router(
    notes_router
)

app.include_router(
    quick_summaries_router
)

app.include_router(
    learning_materials_router
)
