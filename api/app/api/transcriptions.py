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
from app.schemas.transcriptions import (
    StartTranscriptionRequest,
    TranscriptResponse,
    TranscriptWordsResponse,
    TranscriptionJobResponse,
)
from app.services.transcription_service import (
    TranscriptionService,
)


router = APIRouter(
    tags=["transcriptions"]
)


def job_response(
    *,
    job,
    transcript,
    cached: bool,
):
    if cached:
        return TranscriptionJobResponse(
            id=None,
            video_id=(
                transcript.video_id
            ),
            status="completed",
            cached=True,
            transcript_id=(
                transcript.id
            ),
            completed_at=(
                transcript.updated_at
            ),
        )

    return TranscriptionJobResponse(
        id=job.id,
        video_id=job.video_id,
        status=job.status,
        cached=False,
        transcript_id=(
            transcript.id
            if transcript
            else None
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
    "/api/v1/transcriptions",
    response_model=(
        TranscriptionJobResponse
    ),
)
def start_transcription(
    body: StartTranscriptionRequest,
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
    service = (
        TranscriptionService(
            db
        )
    )

    result = service.start(
        body.video_id
    )

    if result["cached"]:
        response.status_code = 200

    else:
        response.status_code = 202

    return job_response(
        job=result["job"],
        transcript=(
            result["transcript"]
        ),
        cached=(
            result["cached"]
        ),
    )


@router.get(
    "/api/v1/transcriptions/{job_id}",
    response_model=(
        TranscriptionJobResponse
    ),
)
def transcription_status(
    job_id: str,
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
    service = (
        TranscriptionService(
            db
        )
    )

    job, transcript = (
        service.refresh(
            job_id
        )
    )

    return job_response(
        job=job,
        transcript=transcript,
        cached=False,
    )


@router.get(
    "/api/v1/videos/{video_id}/transcript",
    response_model=TranscriptResponse,
)
def get_transcript(
    video_id: str,
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
    service = (
        TranscriptionService(
            db
        )
    )

    transcript = (
        service.get_transcript(
            video_id
        )
    )

    return TranscriptResponse(
        id=transcript.id,
        video_id=(
            transcript.video_id
        ),
        language_code=(
            transcript.language_code
        ),
        full_text=(
            transcript.full_text
        ),
        segments=(
            transcript.segments
        ),
        word_count=len(
            transcript.words
        ),
        updated_at=(
            transcript.updated_at
        ),
    )


@router.get(
    "/api/v1/videos/{video_id}/transcript/words",
    response_model=(
        TranscriptWordsResponse
    ),
)
def get_transcript_words(
    video_id: str,
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
    service = (
        TranscriptionService(
            db
        )
    )

    transcript = (
        service.get_transcript(
            video_id
        )
    )

    return TranscriptWordsResponse(
        transcript_id=(
            transcript.id
        ),
        video_id=(
            transcript.video_id
        ),
        words=transcript.words,
        word_count=len(
            transcript.words
        ),
    )
