import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.summary import SummaryJob
from app.repositories.summary_repository import (
    SummaryRepository,
)
from app.repositories.transcription_repository import (
    TranscriptionRepository,
)
from app.repositories.video_repository import (
    VideoRepository,
)
from app.services.summary_engine import (
    generate_summary,
)


def utcnow():
    return datetime.now(
        timezone.utc
    )


class SummaryService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.settings = get_settings()

        self.repo = SummaryRepository(
            db
        )

        self.transcript_repo = (
            TranscriptionRepository(
                db
            )
        )

        self.video_repo = (
            VideoRepository(
                db
            )
        )

    def create(
        self,
        *,
        video_id: str,
        target_minutes: int,
    ):
        video = self.video_repo.get(
            video_id
        )

        if video is None:
            raise AppError(
                404,
                "VIDEO_NOT_FOUND",
                "Video not found.",
            )

        transcript = (
            self.transcript_repo
            .get_transcript(
                video_id
            )
        )

        if transcript is None:
            raise AppError(
                409,
                "TRANSCRIPT_REQUIRED",
                (
                    "The video must be "
                    "transcribed before a "
                    "summary can be generated."
                ),
            )

        if (
            video.etag
            and transcript.source_etag
            != video.etag
        ):
            raise AppError(
                409,
                "TRANSCRIPT_STALE",
                (
                    "The source video changed. "
                    "Transcribe it again before "
                    "creating a summary."
                ),
            )

        target_seconds = (
            target_minutes
            * 60
        )

        model_id = (
            self.settings
            .bedrock_model_id
        )

        version = (
            self.settings
            .summary_algorithm_version
        )

        cached = (
            self.repo.find_completed(
                transcript_id=(
                    transcript.id
                ),
                target_seconds=(
                    target_seconds
                ),
                model_id=model_id,
                algorithm_version=version,
            )
        )

        if cached is not None:
            return (
                cached,
                True,
            )

        active = (
            self.repo.find_active(
                transcript_id=(
                    transcript.id
                ),
                target_seconds=(
                    target_seconds
                ),
                model_id=model_id,
                algorithm_version=version,
            )
        )

        if active is not None:
            return (
                active,
                False,
            )

        job = SummaryJob(
            id=str(
                uuid.uuid4()
            ),
            video_id=video.id,
            transcript_id=(
                transcript.id
            ),
            source_etag=(
                transcript.source_etag
            ),
            target_seconds=(
                target_seconds
            ),
            status="queued",
            model_id=model_id,
            algorithm_version=(
                version
            ),
            selected_segments=[],
            notes={},
            coverage_topics=[],
            candidate_count=0,
            selected_seconds=0.0,
            budget_usage_pct=0.0,
        )

        self.db.add(
            job
        )

        try:
            self.db.commit()

        except IntegrityError:
            self.db.rollback()

            active = (
                self.repo.find_active(
                    transcript_id=(
                        transcript.id
                    ),
                    target_seconds=(
                        target_seconds
                    ),
                    model_id=model_id,
                    algorithm_version=(
                        version
                    ),
                )
            )

            if active is not None:
                return (
                    active,
                    False,
                )

            raise

        self.db.refresh(
            job
        )

        return (
            job,
            False,
        )

    def get(
        self,
        summary_id: str,
    ) -> SummaryJob:
        job = self.repo.get(
            summary_id
        )

        if job is None:
            raise AppError(
                404,
                "SUMMARY_NOT_FOUND",
                "Summary job not found.",
            )

        return job

    def process(
        self,
        summary_id: str,
    ):
        job = self.repo.get(
            summary_id
        )

        if job is None:
            return

        transcript = (
            self.transcript_repo
            .get_transcript(
                job.video_id
            )
        )

        if transcript is None:
            raise RuntimeError(
                "Transcript disappeared."
            )

        if (
            transcript.id
            != job.transcript_id
            or transcript.source_etag
            != job.source_etag
        ):
            raise RuntimeError(
                "Transcript changed while "
                "summary was queued."
            )

        result = generate_summary(
            transcript.segments,
            job.target_seconds,
        )

        job.selected_segments = (
            result[
                "selected_segments"
            ]
        )

        job.notes = (
            result["notes"]
        )

        job.coverage_topics = (
            result[
                "coverage_topics"
            ]
        )

        job.candidate_count = (
            result[
                "candidate_count"
            ]
        )

        job.selected_seconds = (
            result[
                "selected_seconds"
            ]
        )

        job.budget_usage_pct = (
            result[
                "budget_usage_pct"
            ]
        )

        job.status = "completed"
        job.failure_reason = None
        job.completed_at = utcnow()

        self.db.commit()

        self.db.refresh(
            job
        )
