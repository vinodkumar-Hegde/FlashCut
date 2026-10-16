from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Response,
)
from sqlalchemy.orm import Session

from app.core.auth import (
    Principal,
    require_principal,
)
from app.core.idempotency import (
    idempotency_hash,
    normalize_idempotency_key,
)
from app.db.session import (
    get_tenant_db,
)
from app.schemas.quick_summaries import (
    CreateQuickSummaryRequest,
    QuickSummaryResponse,
    QuickSummaryResult,
)
from app.services.quick_summary_service import (
    QuickSummaryService,
)


router = APIRouter(
    prefix="/api/v1/quick-summaries",
    tags=["quick-summaries"],
)


def to_response(job):
    return QuickSummaryResponse(
        id=job.id,
        video_id=job.video_id,

        transcript_id=(
            job.transcript_id
        ),

        transcription_job_id=(
            job.transcription_job_id
        ),

        status=job.status,

        model_id=job.model_id,

        algorithm_version=(
            job.algorithm_version
        ),

        attempt_count=(
            job.attempt_count
        ),

        error_code=job.error_code,

        error_message=(
            job.error_message
        ),

        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


@router.post(
    "",
    response_model=QuickSummaryResponse,
    status_code=202,
)
def create_quick_summary(
    body: CreateQuickSummaryRequest,
    response: Response,

    db: Annotated[
        Session,
        Depends(get_tenant_db),
    ],

    principal: Annotated[
        Principal,
        Depends(
            require_principal
        ),
    ],

    idempotency_key_header: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key"
        ),
    ] = None,
):
    key = normalize_idempotency_key(
        idempotency_key_header
    )

    request_hash = (
        idempotency_hash(
            operation=(
                "create-quick-summary"
            ),
            payload=body.model_dump(
                mode="json"
            ),
        )
        if key
        else None
    )

    job, replayed = (
        QuickSummaryService(
            db
        ).create(
            video_id=body.video_id,
            idempotency_key=key,
            idempotency_hash=(
                request_hash
            ),
        )
    )

    if replayed:
        response.status_code = 200

        response.headers[
            "Idempotency-Replayed"
        ] = "true"

    return to_response(
        job
    )


@router.get(
    "/{quick_summary_id}",
    response_model=QuickSummaryResponse,
)
def get_quick_summary(
    quick_summary_id: str,

    db: Annotated[
        Session,
        Depends(get_tenant_db),
    ],

    principal: Annotated[
        Principal,
        Depends(
            require_principal
        ),
    ],
):
    return to_response(
        QuickSummaryService(
            db
        ).get(
            quick_summary_id
        )
    )


@router.get(
    "/{quick_summary_id}/result",
    response_model=QuickSummaryResult,
)
def get_quick_summary_result(
    quick_summary_id: str,

    db: Annotated[
        Session,
        Depends(get_tenant_db),
    ],

    principal: Annotated[
        Principal,
        Depends(
            require_principal
        ),
    ],
):
    job = QuickSummaryService(
        db
    ).result(
        quick_summary_id
    )

    result = (
        job.result
        or {}
    )

    return QuickSummaryResult(
        id=job.id,
        status=job.status,

        summary=str(
            result.get(
                "summary",
                "",
            )
        ),

        key_points=list(
            result.get(
                "key_points",
                [],
            )
            or []
        ),

        topics=list(
            result.get(
                "topics",
                [],
            )
            or []
        ),
    )
