import uuid
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.note import NoteJob
from app.repositories.note_repository import (
    NoteRepository,
)
from app.repositories.transcription_repository import (
    TranscriptionRepository,
)
from app.repositories.video_repository import (
    VideoRepository,
)
from app.services.notes_engine import (
    generate_notes,
    generate_visual,
)
from app.services.notes_pdf import (
    render_notes_pdf,
    safe_pdf_name,
)
from app.services.transcription_service import (
    TranscriptionService,
)


def utcnow():
    return datetime.now(
        timezone.utc
    )


class NoteService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

        self.settings = (
            get_settings()
        )

        self.repo = NoteRepository(
            db
        )

        self.video_repo = (
            VideoRepository(
                db
            )
        )

        self.transcript_repo = (
            TranscriptionRepository(
                db
            )
        )

    def create(
        self,
        *,
        video_id: str,
        style: str,
    ) -> NoteJob:
        video = self.video_repo.get(
            video_id
        )

        if video is None:
            raise AppError(
                404,
                "VIDEO_NOT_FOUND",
                "Video not found.",
            )

        transcription = (
            TranscriptionService(
                self.db
            ).start(
                video_id
            )
        )

        transcript = (
            transcription[
                "transcript"
            ]
        )

        transcription_job = (
            transcription[
                "job"
            ]
        )

        note = NoteJob(
            id=str(
                uuid.uuid4()
            ),

            video_id=video_id,

            transcript_id=(
                transcript.id
                if transcript
                else None
            ),

            transcription_job_id=(
                transcription_job.id
                if transcription_job
                else None
            ),

            source_etag=(
                transcript.source_etag
                if transcript
                else None
            ),

            style=style,

            status=(
                "queued"
                if transcript
                else
                "waiting_for_transcript"
            ),

            model_id=(
                self.settings
                .bedrock_model_id
            ),

            algorithm_version=(
                self.settings
                .notes_algorithm_version
            ),

            content={},
            visuals=[],
            revision=1,

            next_attempt_at=(
                utcnow()
                if not transcript
                else None
            ),
        )

        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)

        return note

    def get(
        self,
        note_id: str,
    ) -> NoteJob:
        note = self.repo.get(
            note_id
        )

        if note is None:
            raise AppError(
                404,
                "NOTE_NOT_FOUND",
                "Notes job not found.",
            )

        return note

    def process(
        self,
        note_id: str,
    ):
        note = self.repo.get(
            note_id
        )

        if note is None:
            return

        self.db.info[
            "tenant_id"
        ] = note.tenant_id

        transcript = None

        if note.transcript_id:
            transcript = (
                self.transcript_repo
                .get_transcript_by_id(
                    note.transcript_id
                )
            )

        elif (
            note.transcription_job_id
        ):
            (
                transcription_job,
                transcript,
            ) = (
                TranscriptionService(
                    self.db
                ).refresh(
                    note.transcription_job_id
                )
            )

            if (
                transcription_job.status
                == "failed"
            ):
                note.status = "failed"

                note.failure_reason = (
                    "Video transcription "
                    "failed."
                )

                note.completed_at = (
                    utcnow()
                )

                note.next_attempt_at = (
                    None
                )

                self.db.commit()

                return

            if transcript is None:
                note.status = (
                    "waiting_for_transcript"
                )

                note.next_attempt_at = (
                    utcnow()
                    + timedelta(
                        seconds=5
                    )
                )

                self.db.commit()

                return

            note.transcript_id = (
                transcript.id
            )

            note.source_etag = (
                transcript.source_etag
            )

        if transcript is None:
            raise RuntimeError(
                "Transcript unavailable "
                "for notes generation."
            )

        if (
            note.source_etag
            and transcript.source_etag
            != note.source_etag
        ):
            raise RuntimeError(
                "Transcript source changed "
                "while notes were queued."
            )

        note.source_etag = (
            transcript.source_etag
        )

        content = generate_notes(
            transcript.segments,
            note.style,
        )

        note.content = content
        note.visuals = []
        note.status = "completed"
        note.failure_reason = None
        note.next_attempt_at = None
        note.completed_at = utcnow()

        self.db.commit()
        self.db.refresh(note)

    def update(
        self,
        *,
        note_id: str,
        revision: int,
        content: dict,
    ) -> NoteJob:
        note = self.get(
            note_id
        )

        if note.status != "completed":
            raise AppError(
                409,
                "NOTES_NOT_READY",
                (
                    "Notes must finish "
                    "generation before editing."
                ),
            )

        if note.revision != revision:
            raise AppError(
                409,
                "NOTE_REVISION_CONFLICT",
                (
                    "The notes were changed "
                    "by another request."
                ),
            )

        note.content = content

        # Visuals describe note content.
        # Editing invalidates them.
        note.visuals = []

        note.revision += 1

        self.db.commit()
        self.db.refresh(note)

        return note

    def add_visual(
        self,
        *,
        note_id: str,
        revision: int,
        kind: str,
    ) -> NoteJob:
        note = self.get(
            note_id
        )

        if note.status != "completed":
            raise AppError(
                409,
                "NOTES_NOT_READY",
                (
                    "Notes must finish "
                    "generation first."
                ),
            )

        if note.revision != revision:
            raise AppError(
                409,
                "NOTE_REVISION_CONFLICT",
                (
                    "Save the latest notes "
                    "before generating "
                    "a diagram."
                ),
            )

        visual = generate_visual(
            note.content,
            kind,
        )

        visuals = [
            item
            for item
            in (
                note.visuals
                or []
            )
            if item.get(
                "kind"
            )
            != kind
        ]

        visuals.append(
            visual
        )

        note.visuals = visuals
        note.revision += 1

        self.db.commit()
        self.db.refresh(note)

        return note

    def pdf(
        self,
        note_id: str,
    ) -> tuple[bytes, str]:
        note = self.get(
            note_id
        )

        if note.status != "completed":
            raise AppError(
                409,
                "NOTES_NOT_READY",
                (
                    "Notes are not ready "
                    "for PDF export."
                ),
            )

        video = self.video_repo.get(
            note.video_id
        )

        filename = safe_pdf_name(
            (
                video.filename
                if video
                else "video"
            )
            .rsplit(
                ".",
                1,
            )[0]
        )

        pdf = render_notes_pdf(
            content=note.content,
            visuals=(
                note.visuals
                or []
            ),
            style=note.style,
        )

        return (
            pdf,
            f"{filename}-notes.pdf",
        )
