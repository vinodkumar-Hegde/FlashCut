from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.providers.aws import s3_client


router = APIRouter(
    tags=["health"]
)


@router.get(
    "/health/live"
)
def live():
    settings = get_settings()

    return {
        "status": "ok",
        "version":
            settings.app_version,
    }


@router.get(
    "/health/ready"
)
def ready():
    settings = get_settings()

    try:
        with SessionLocal() as db:
            db.execute(
                text("SELECT 1")
            )

        s3_client().head_bucket(
            Bucket=settings.s3_bucket
        )

    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status":
                    "not_ready"
            },
        )

    return {
        "status": "ready"
    }
