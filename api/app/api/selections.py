from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Response,
    status,
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
from app.db.session import get_tenant_db
from app.schemas.selections import (
    ApproveSelectionRequest,
    CreateSelectionRequest,
    SelectionResponse,
    UpdateSelectionRequest,
)
from app.services.selection_service import (
    SelectionService,
)


router = APIRouter(
    prefix="/api/v1/selections",
    tags=["selections"],
)


def to_response(
    selection,
):
    clips = (
        selection.resolved_clips
        or []
    )

    return SelectionResponse(
        id=selection.id,
        video_id=selection.video_id,
        transcript_id=(
            selection.transcript_id
        ),
        summary_id=(
            selection.summary_id
        ),
        status=selection.status,
        revision=selection.revision,
        selected_segment_ids=(
            selection.selected_segment_ids
            or []
        ),
        word_ranges=(
            selection.word_ranges
            or []
        ),
        resolved_clips=clips,
        total_seconds=round(
            sum(
                float(
                    clip["duration"]
                )
                for clip in clips
            ),
            3,
        ),
        created_at=(
            selection.created_at
        ),
        updated_at=(
            selection.updated_at
        ),
        approved_at=(
            selection.approved_at
        ),
    )


@router.post(
    "",
    response_model=SelectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_selection(
    body: CreateSelectionRequest,
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
                "create-selection"
            ),
            payload=body.model_dump(
                mode="json"
            ),
        )
        if key
        else None
    )

    selection, replayed = (
        SelectionService(db)
        .create(
            video_id=body.video_id,
            summary_id=body.summary_id,
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
        selection
    )


@router.get(
    "/{selection_id}",
    response_model=SelectionResponse,
)
def get_selection(
    selection_id: str,
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
    selection = (
        SelectionService(db)
        .get(selection_id)
    )

    return to_response(
        selection
    )


@router.put(
    "/{selection_id}",
    response_model=SelectionResponse,
)
def update_selection(
    selection_id: str,
    body: UpdateSelectionRequest,
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
    selection = (
        SelectionService(db)
        .update(
            selection_id=selection_id,
            expected_revision=(
                body.revision
            ),
            segment_ids=(
                body.selected_segment_ids
            ),
            word_ranges=[
                item.model_dump()
                for item
                in body.word_ranges
            ],
        )
    )

    return to_response(
        selection
    )


@router.post(
    "/{selection_id}/approve",
    response_model=SelectionResponse,
)
def approve_selection(
    selection_id: str,
    body: ApproveSelectionRequest,
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
    selection = (
        SelectionService(db)
        .approve(
            selection_id=selection_id,
            expected_revision=(
                body.revision
            ),
        )
    )

    return to_response(
        selection
    )
