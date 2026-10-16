import hashlib
import json
import uuid
from datetime import (
    datetime,
    timedelta,
    timezone,
)

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
    QuickSummaryJob,
    QuickSummaryOutbox,
)
from app.repositories.generation_repository import (
    QuickSummaryRepository,
)
from app.repositories.transcription_repository import (
    TranscriptionRepository,
)
from app.repositories.video_repository import (
    VideoRepository,
)
from app.services.quick_summary_engine import (
    generate_quick_summary,
)
from app.services.transcription_service import (
    TranscriptionService,
)


def utcnow():
    return datetime.now(
        timezone.utc
    )


class QuickSummaryService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.settings = get_settings()

        self.repo = (
            QuickSummaryRepository(
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
    ) -> str:
        payload = {
            "video_id":
                video_id,

            "source_etag":
                source_etag,

            "model_id":
                self.settings
                .bedrock_model_id,

            "algorithm_version":
                self.settings
                .quick_summary_algorithm_version,
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

        job = QuickSummaryJob(
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

            source_etag=(
                source_etag
            ),

            fingerprint=(
                self._fingerprint(
                    video_id=video_id,
                    source_etag=(
                        source_etag
                    ),
                )
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
                .quick_summary_algorithm_version
            ),

            result={},

            next_attempt_at=(
                utcnow()
            ),
        )

        self.db.add(job)

        self.db.add(
            QuickSummaryOutbox(
                job_id=job.id,
                status="pending",
                next_attempt_at=(
                    utcnow()
                ),
            )
        )

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
                "QUICK_SUMMARY_NOT_FOUND",
                "Quick summary job not found.",
            )

        return job

    def result(
        self,
        job_id: str,
    ):
        job = self.get(
            job_id
        )

        if job.status != "completed":
            raise AppError(
                409,
                "QUICK_SUMMARY_NOT_READY",
                "Quick summary is not ready.",
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
                "while quick summary was queued."
            )

        job.source_etag = (
            transcript.source_etag
        )

        job.status = "processing"
        job.attempt_count += 1
        job.heartbeat_at = utcnow()
        job.next_attempt_at = None

        self.db.commit()

        result = (
            generate_quick_summary(
                transcript.segments
            )
        )

        job.result = result
        job.status = "completed"

        job.error_code = None
        job.error_message = None

        job.heartbeat_at = utcnow()
        job.completed_at = utcnow()

        self.db.commit()
        self.db.refresh(job)

        return "completed"

    def mark_failure(
        self,
        job_id: str,
        *,
        prior_attempt_count: (
            int | None
        ) = None,
    ):
        job = self.repo.get(
            job_id
        )

        if job is None:
            return

        job.heartbeat_at = utcnow()

        if (
            prior_attempt_count
            is not None
            and job.attempt_count
            <= prior_attempt_count
        ):
            job.attempt_count = (
                prior_attempt_count
                + 1
            )

        if (
            job.attempt_count
            >= self.settings
            .generation_max_attempts
        ):
            job.status = "failed"
            job.error_code = (
                "QUICK_SUMMARY_GENERATION_FAILED"
            )
            job.error_message = (
                "Quick summary generation failed."
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
