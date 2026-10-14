from sqlalchemy.orm import Session

from app.db.tenant import (
    tenant_get,
    tenant_select,
)
from app.models.transcription import (
    Transcript,
    TranscriptionJob,
)


class TranscriptionRepository:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def get_job(
        self,
        job_id: str,
    ) -> TranscriptionJob | None:
        return tenant_get(
            self.db,
            TranscriptionJob,
            job_id,
        )

    def get_transcript_by_id(
        self,
        transcript_id: str,
    ) -> Transcript | None:
        return tenant_get(
            self.db,
            Transcript,
            transcript_id,
        )

    def get_transcript_for_job(
        self,
        job_id: str,
    ) -> Transcript | None:
        statement = (
            tenant_select(
                self.db,
                Transcript,
            )
            .where(
                Transcript
                .transcription_job_id
                == job_id
            )
            .limit(1)
        )

        return self.db.scalar(
            statement
        )

    def find_cached_transcript(
        self,
        *,
        video_id: str,
        source_etag: str,
        language_code: str,
        vocabulary_name: str,
        config_version: str,
    ) -> Transcript | None:
        statement = (
            tenant_select(
                self.db,
                Transcript,
            )
            .where(
                Transcript.video_id
                == video_id,

                Transcript.source_etag
                == source_etag,

                Transcript.language_code
                == language_code,

                Transcript.vocabulary_name
                == vocabulary_name,

                Transcript.config_version
                == config_version,
            )
            .order_by(
                Transcript
                .created_at
                .desc()
            )
            .limit(1)
        )

        return self.db.scalar(
            statement
        )

    def find_active_job(
        self,
        *,
        video_id: str,
        source_etag: str,
        language_code: str,
        vocabulary_name: str,
        config_version: str,
    ) -> TranscriptionJob | None:
        statement = (
            tenant_select(
                self.db,
                TranscriptionJob,
            )
            .where(
                TranscriptionJob.video_id
                == video_id,

                TranscriptionJob.source_etag
                == source_etag,

                TranscriptionJob.language_code
                == language_code,

                TranscriptionJob.vocabulary_name
                == vocabulary_name,

                TranscriptionJob.config_version
                == config_version,

                TranscriptionJob.status.in_(
                    [
                        "queued",
                        "in_progress",
                    ]
                ),
            )
            .order_by(
                TranscriptionJob
                .created_at
                .desc()
            )
            .limit(1)
        )

        return self.db.scalar(
            statement
        )

    def create_transcript(
        self,
        *,
        job: TranscriptionJob,
        language_code: str,
        full_text: str,
        segments: list,
        words: list,
        raw_output_key: str,
    ) -> Transcript:
        existing = (
            self.get_transcript_for_job(
                job.id
            )
        )

        if existing is not None:
            return existing

        transcript = Transcript(
            tenant_id=job.tenant_id,
            video_id=job.video_id,
            transcription_job_id=(
                job.id
            ),
            source_etag=(
                job.source_etag
            ),
            language_code=(
                language_code
            ),
            vocabulary_name=(
                job.vocabulary_name
            ),
            config_version=(
                job.config_version
            ),
            full_text=full_text,
            segments=segments,
            words=words,
            raw_output_key=(
                raw_output_key
            ),
        )

        self.db.add(
            transcript
        )

        return transcript
