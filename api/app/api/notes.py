from io import BytesIO
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Response,
)
from fastapi.responses import (
    StreamingResponse,
)
from sqlalchemy.orm import Session

from app.core.auth import (
    Principal,
    require_principal,
)
from app.db.session import get_tenant_db
from app.schemas.notes import (
    CreateNoteRequest,
    GenerateVisualRequest,
    NoteResponse,
    UpdateNoteRequest,
)
from app.services.note_service import (
    NoteService,
)


router = APIRouter(
    prefix="/api/v1/notes",
    tags=["notes"],
)


def to_response(
    note,
):
    return NoteResponse(
        id=note.id,
        video_id=note.video_id,
        transcript_id=(
            note.transcript_id
        ),
        transcription_job_id=(
            note.transcription_job_id
        ),
        style=note.style,
        status=note.status,
        model_id=note.model_id,
        algorithm_version=(
            note.algorithm_version
        ),
        revision=note.revision,
        content=(
            note.content
            or {}
        ),
        visuals=(
            note.visuals
            or []
        ),
        failure_reason=(
            note.failure_reason
        ),
        created_at=(
            note.created_at
        ),
        updated_at=(
            note.updated_at
        ),
        completed_at=(
            note.completed_at
        ),
    )


@router.post(
    "",
    response_model=NoteResponse,
    status_code=202,
)
def create_notes(
    body: CreateNoteRequest,
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
    note = NoteService(
        db
    ).create(
        video_id=body.video_id,
        style=body.style,
    )

    return to_response(
        note
    )


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
)
def get_notes(
    note_id: str,
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
        NoteService(
            db
        ).get(
            note_id
        )
    )


@router.put(
    "/{note_id}",
    response_model=NoteResponse,
)
def update_notes(
    note_id: str,
    body: UpdateNoteRequest,
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
    note = NoteService(
        db
    ).update(
        note_id=note_id,
        revision=body.revision,
        content=(
            body.content
            .model_dump()
        ),
    )

    return to_response(
        note
    )


@router.post(
    "/{note_id}/visuals",
    response_model=NoteResponse,
)
def generate_note_visual(
    note_id: str,
    body: GenerateVisualRequest,
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
    note = NoteService(
        db
    ).add_visual(
        note_id=note_id,
        revision=body.revision,
        kind=body.kind,
    )

    return to_response(
        note
    )


@router.get(
    "/{note_id}/pdf",
)
def export_note_pdf(
    note_id: str,
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
    pdf, filename = (
        NoteService(
            db
        ).pdf(
            note_id
        )
    )

    return StreamingResponse(
        BytesIO(pdf),
        media_type=(
            "application/pdf"
        ),
        headers={
            "Content-Disposition":
                (
                    "attachment; "
                    f'filename="{filename}"'
                )
        },
    )
