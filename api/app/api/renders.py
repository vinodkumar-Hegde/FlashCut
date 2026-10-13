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
from app.db.session import get_db
from app.schemas.renders import (
    CreateRenderRequest,
    RenderResponse,
    RenderResultResponse,
)
from app.services.render_service import (
    RenderService,
)


router = APIRouter(
    prefix="/api/v1/renders",
    tags=["renders"],
)


def to_response(
    job,
    *,
    cached: bool,
):
    return RenderResponse(
        id=job.id,
        video_id=job.video_id,
        selection_id=(
            job.selection_id
        ),
        status=job.status,
        cached=cached,
        selected_seconds=(
            job.selected_seconds
        ),
        attempt_count=(
            job.attempt_count
        ),
        container_format=(
            job.container_format
        ),
        output_filename=(
            job.output_filename
        ),
        error_code=(
            job.error_code
        ),
        error_message=(
            job.error_message
        ),
        created_at=(
            job.created_at
        ),
        started_at=(
            job.started_at
        ),
        completed_at=(
            job.completed_at
        ),
    )


@router.post(
    "",
    response_model=RenderResponse,
)
def create_render(
    body: CreateRenderRequest,
    response: Response,
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    principal: Annotated[
        Principal,
        Depends(
            require_principal
        ),
    ],
):
    job, cached = (
        RenderService(db)
        .create(
            body.selection_id
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
    "/{render_id}",
    response_model=RenderResponse,
)
def get_render(
    render_id: str,
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    principal: Annotated[
        Principal,
        Depends(
            require_principal
        ),
    ],
):
    job = RenderService(
        db
    ).get(
        render_id
    )

    return to_response(
        job,
        cached=False,
    )


@router.get(
    "/{render_id}/result",
    response_model=(
        RenderResultResponse
    ),
)
def get_render_result(
    render_id: str,
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    principal: Annotated[
        Principal,
        Depends(
            require_principal
        ),
    ],
):
    return RenderService(
        db
    ).result(
        render_id
    )
