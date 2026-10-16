import hashlib
import json
import uuid
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from io import BytesIO

from sqlalchemy.exc import (
    IntegrityError,
)
from sqlalchemy.orm import Session

from app.core.config import (
    get_settings,
)
from app.core.errors import AppError
from app.core.idempotency import (
    ensure_idempotency_match,
)
from app.models.learning_pipeline import (
    LearningMaterialJob,
)
from app.repositories.generation_repository import (
    LearningMaterialRepository,
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


class LearningMaterialService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.settings = get_settings()

        self.repo = (
            LearningMaterialRepository(
                db
            )
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

    def _fingerprint(
        self,
        *,
        video_id: str,
        source_etag: str | None,
        notes_style: str,
        include_mind_map: bool,
        include_flowchart: bool,
    ) -> str:
        payload = {
            "video_id":
                video_id,

            "source_etag":
                source_etag,

            "notes_style":
                notes_style,

            "include_mind_map":
                include_mind_map,

            "include_flowchart":
                include_flowchart,

            "model_id":
                self.settings
                .bedrock_model_id,

            "algorithm_version":
                self.settings
                .learning_material_algorithm_version,
        }

        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        ).encode(
            "utf-8"
        )

        return hashlib.sha256(
            encoded
        ).hexdigest()

    def create(
        self,
        *,
        video_id: str,
        notes_style: str,
        include_mind_map: bool,
        include_flowchart: bool,
        idempotency_key: (
            str | None
        ) = None,
        idempotency_hash: (
            str | None
        ) = None,
    ):
        if idempotency_key:
            existing = (
                self.repo
                .get_by_idempotency_key(
                    idempotency_key
                )
            )

            if existing is not None:
                ensure_idempotency_match(
                    stored_hash=(
                        existing
                        .idempotency_hash
                    ),
                    request_hash=(
                        idempotency_hash
                    ),
                )

                return (
                    existing,
                    True,
                )

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

        source_etag = (
            transcript.source_etag
            if transcript
            else video.etag
        )

        job = LearningMaterialJob(
            id=str(
                uuid.uuid4()
            ),

            idempotency_key=(
                idempotency_key
            ),

            idempotency_hash=(
                idempotency_hash
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

            source_etag=source_etag,

            fingerprint=(
                self._fingerprint(
                    video_id=video_id,
                    source_etag=(
                        source_etag
                    ),
                    notes_style=(
                        notes_style
                    ),
                    include_mind_map=(
                        include_mind_map
                    ),
                    include_flowchart=(
                        include_flowchart
                    ),
                )
            ),

            notes_style=notes_style,

            include_mind_map=(
                include_mind_map
            ),

            include_flowchart=(
                include_flowchart
            ),

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
                .learning_material_algorithm_version
            ),

            content={},
            mind_map={},
            flowchart={},

            component_status={
                "notes":
                    "pending",

                "mind_map":
                    (
                        "pending"
                        if include_mind_map
                        else
                        "skipped"
                    ),

                "flowchart":
                    (
                        "pending"
                        if include_flowchart
                        else
                        "skipped"
                    ),
            },

            component_errors={},

            revision=1,

            next_attempt_at=(
                utcnow()
            ),
        )

        self.db.add(job)

        try:
            self.db.commit()

        except IntegrityError:
            self.db.rollback()

            if not idempotency_key:
                raise

            existing = (
                self.repo
                .get_by_idempotency_key(
                    idempotency_key
                )
            )

            if existing is None:
                raise

            ensure_idempotency_match(
                stored_hash=(
                    existing
                    .idempotency_hash
                ),
                request_hash=(
                    idempotency_hash
                ),
            )

            return (
                existing,
                True,
            )

        self.db.refresh(job)

        return (
            job,
            False,
        )

    def get(
        self,
        job_id: str,
    ):
        job = self.repo.get(
            job_id
        )

        if job is None:
            raise AppError(
                404,
                "LEARNING_MATERIAL_NOT_FOUND",
                "Learning material job not found.",
            )

        return job

    def result(
        self,
        job_id: str,
    ):
        job = self.get(
            job_id
        )

        if job.status not in {
            "completed",
            "partial",
        }:
            raise AppError(
                409,
                "LEARNING_MATERIAL_NOT_READY",
                (
                    "Learning material "
                    "is not ready."
                ),
            )

        return job

    def process(
        self,
        job_id: str,
    ):
        job = self.repo.get(
            job_id
        )

        if job is None:
            return "missing"

        transcript = None

        if job.transcript_id:
            transcript = (
                self.transcript_repo
                .get_transcript_by_id(
                    job.transcript_id
                )
            )

        elif job.transcription_job_id:
            (
                transcription_job,
                transcript,
            ) = (
                TranscriptionService(
                    self.db
                ).refresh(
                    job.transcription_job_id
                )
            )

            if (
                transcription_job.status
                == "failed"
            ):
                job.status = "failed"
                job.error_code = (
                    "TRANSCRIPTION_FAILED"
                )
                job.error_message = (
                    "Video transcription failed."
                )
                job.completed_at = utcnow()

                self.db.commit()

                return "failed"

            if transcript is None:
                job.status = (
                    "waiting_for_transcript"
                )

                job.next_attempt_at = (
                    utcnow()
                    + timedelta(
                        seconds=5
                    )
                )

                job.heartbeat_at = (
                    utcnow()
                )

                self.db.commit()

                return "waiting"

            job.transcript_id = (
                transcript.id
            )

        if transcript is None:
            raise RuntimeError(
                "Transcript unavailable."
            )

        if (
            job.source_etag
            and transcript.source_etag
            != job.source_etag
        ):
            raise RuntimeError(
                "Transcript source changed "
                "while learning material "
                "was queued."
            )

        job.source_etag = (
            transcript.source_etag
        )

        job.status = "processing"
        job.attempt_count += 1
        job.heartbeat_at = utcnow()
        job.next_attempt_at = None

        self.db.commit()

        content = generate_notes(
            transcript.segments,
            job.notes_style,
        )

        job.content = content

        component_status = {
            "notes":
                "completed",

            "mind_map":
                (
                    "pending"
                    if job.include_mind_map
                    else
                    "skipped"
                ),

            "flowchart":
                (
                    "pending"
                    if job.include_flowchart
                    else
                    "skipped"
                ),
        }

        component_errors = {}

        if job.include_mind_map:
            try:
                job.mind_map = (
                    generate_visual(
                        content,
                        "mindmap",
                    )
                )

                component_status[
                    "mind_map"
                ] = "completed"

            except Exception:
                component_status[
                    "mind_map"
                ] = "failed"

                component_errors[
                    "mind_map"
                ] = (
                    "Mind map generation failed."
                )

        if job.include_flowchart:
            try:
                job.flowchart = (
                    generate_visual(
                        content,
                        "flowchart",
                    )
                )

                component_status[
                    "flowchart"
                ] = "completed"

            except Exception:
                component_status[
                    "flowchart"
                ] = "failed"

                component_errors[
                    "flowchart"
                ] = (
                    "Flow chart generation failed."
                )

        job.component_status = (
            component_status
        )

        job.component_errors = (
            component_errors
        )

        failed_components = [
            key
            for key, value
            in component_status.items()
            if value == "failed"
        ]

        job.status = (
            "partial"
            if failed_components
            else
            "completed"
        )

        job.error_code = None
        job.error_message = None
        job.heartbeat_at = utcnow()
        job.completed_at = utcnow()

        self.db.commit()
        self.db.refresh(job)

        return job.status

    def mark_failure(
        self,
        job_id: str,
    ):
        job = self.repo.get(
            job_id
        )

        if job is None:
            return

        job.heartbeat_at = utcnow()

        if (
            job.attempt_count
            >= self.settings
            .generation_max_attempts
        ):
            job.status = "failed"

            job.error_code = (
                "LEARNING_MATERIAL_GENERATION_FAILED"
            )

            job.error_message = (
                "Learning material generation failed."
            )

            job.completed_at = utcnow()
            job.next_attempt_at = None

        else:
            job.status = "queued"

            job.next_attempt_at = (
                utcnow()
                + timedelta(
                    seconds=min(
                        120,
                        10
                        * (
                            2
                            ** max(
                                job.attempt_count
                                - 1,
                                0,
                            )
                        ),
                    )
                )
            )

        self.db.commit()

    def pdf(
        self,
        job_id: str,
    ):
        job = self.result(
            job_id
        )

        video = self.video_repo.get(
            job.video_id
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

        visuals = []

        if (
            job.include_mind_map
            and job.mind_map
        ):
            visuals.append(
                job.mind_map
            )

        if (
            job.include_flowchart
            and job.flowchart
        ):
            visuals.append(
                job.flowchart
            )

        pdf = render_notes_pdf(
            content=job.content,
            visuals=visuals,
            style=job.notes_style,
        )

        return (
            pdf,
            (
                filename
                + "-learning-material.pdf"
            ),
        )
