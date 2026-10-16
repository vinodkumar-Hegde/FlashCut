from io import BytesIO
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
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
from app.core.idempotency import (
    idempotency_hash,
    normalize_idempotency_key,
)
from app.db.session import (
    get_tenant_db,
)
from app.schemas.learning_materials import (
    CreateLearningMaterialRequest,
    LearningMaterialResponse,
    LearningMaterialResult,
)
from app.services.learning_material_service import (
    LearningMaterialService,
)


router = APIRouter(
    prefix="/api/v1/learning-materials",
    tags=["learning-materials"],
)


def to_response(job):
    return LearningMaterialResponse(
        id=job.id,
        video_id=job.video_id,

        transcript_id=(
            job.transcript_id
        ),

        transcription_job_id=(
            job.transcription_job_id
        ),

        notes_style=job.notes_style,

        include_mind_map=(
            job.include_mind_map
        ),

        include_flowchart=(
            job.include_flowchart
        ),

        status=job.status,

        model_id=job.model_id,

        algorithm_version=(
            job.algorithm_version
        ),

        component_status=(
            job.component_status
            or {}
        ),

        component_errors=(
            job.component_errors
            or {}
        ),

        revision=job.revision,

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
    response_model=LearningMaterialResponse,
    status_code=202,
)
def create_learning_material(
    body: CreateLearningMaterialRequest,
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
                "create-learning-material"
            ),
            payload=body.model_dump(
                mode="json"
            ),
        )
        if key
        else None
    )

    job, replayed = (
        LearningMaterialService(
            db
        ).create(
            video_id=body.video_id,

            notes_style=(
                body.notes_style
            ),

            include_mind_map=(
                body.include_mind_map
            ),

            include_flowchart=(
                body.include_flowchart
            ),

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
    "/{learning_material_id}",
    response_model=LearningMaterialResponse,
)
def get_learning_material(
    learning_material_id: str,

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
        LearningMaterialService(
            db
        ).get(
            learning_material_id
        )
    )


@router.get(
    "/{learning_material_id}/result",
    response_model=LearningMaterialResult,
)
def get_learning_material_result(
    learning_material_id: str,

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
    job = LearningMaterialService(
        db
    ).result(
        learning_material_id
    )

    return LearningMaterialResult(
        id=job.id,
        status=job.status,
        revision=job.revision,

        notes=(
            job.content
            or {}
        ),

        mind_map=(
            job.mind_map
            or {}
        ),

        flowchart=(
            job.flowchart
            or {}
        ),

        component_status=(
            job.component_status
            or {}
        ),

        component_errors=(
            job.component_errors
            or {}
        ),
    )


@router.get(
    "/{learning_material_id}/pdf",
)
def get_learning_material_pdf(
    learning_material_id: str,

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
        LearningMaterialService(
            db
        ).pdf(
            learning_material_id
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
