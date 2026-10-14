from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Response,
)
from sqlalchemy.orm import Session

from app.core.auth import (
    Principal,
    require_principal,
)
from app.db.session import get_tenant_db
from app.schemas.summaries import (
    CreateSummaryRequest,
    SummaryResponse,
)
from app.services.summary_service import (
    SummaryService,
)


router = APIRouter(
    prefix="/api/v1/summaries",
    tags=["summaries"],
)


def to_response(
    job,
    *,
    cached: bool,
):
    return SummaryResponse(
        id=job.id,
        video_id=job.video_id,
        transcript_id=(
            job.transcript_id
        ),
        status=job.status,
        cached=cached,
        target_minutes=(
            job.target_seconds
            / 60
        ),
        model_id=job.model_id,
        algorithm_version=(
            job.algorithm_version
        ),
        candidate_count=(
            job.candidate_count
        ),
        selected_seconds=(
            job.selected_seconds
        ),
        budget_usage_pct=(
            job.budget_usage_pct
        ),
        coverage_topics=(
            job.coverage_topics
            or []
        ),
        notes=(
            job.notes
            or {}
        ),
        selections=(
            job.selected_segments
            or []
        ),
        failure_reason=(
            job.failure_reason
        ),
        created_at=(
            job.created_at
        ),
        completed_at=(
            job.completed_at
        ),
    )


@router.post(
    "",
    response_model=SummaryResponse,
)
def create_summary(
    body: CreateSummaryRequest,
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
):
    service = SummaryService(
        db
    )

    job, cached = (
        service.create(
            video_id=body.video_id,
            target_minutes=(
                body.target_minutes
            ),
        )
    )

    response.status_code = (
        200
        if cached
        else 202
    )

    return to_response(
        job,
        cached=cached,
    )


@router.get(
    "/{summary_id}",
    response_model=SummaryResponse,
)
def get_summary(
    summary_id: str,
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
    job = SummaryService(
        db
    ).get(
        summary_id
    )

    return to_response(
        job,
        cached=False,
    )
