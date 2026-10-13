from sqlalchemy import select
from sqlalchemy.orm import Session

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
        return self.db.get(
            TranscriptionJob,
            job_id,
        )

    def find_active_job(
        self,
        *,
        video_id: str,
        source_etag: str,
    ) -> TranscriptionJob | None:
        statement = (
            select(
                TranscriptionJob
            )
            .where(
                TranscriptionJob.video_id
                == video_id,
                TranscriptionJob.source_etag
                == source_etag,
                TranscriptionJob.status.in_(
                    [
                        "queued",
                        "in_progress",
                    ]
                ),
            )
            .order_by(
                TranscriptionJob.created_at.desc()
            )
            .limit(1)
        )

        return self.db.scalar(
            statement
        )

    def get_transcript(
        self,
        video_id: str,
    ) -> Transcript | None:
        statement = (
            select(
                Transcript
            )
            .where(
                Transcript.video_id
                == video_id
            )
            .limit(1)
        )

        return self.db.scalar(
            statement
        )

    def save_transcript(
        self,
        *,
        video_id: str,
        source_etag: str,
        language_code: str | None,
        full_text: str,
        segments: list,
        words: list,
        raw_output_key: str,
    ) -> Transcript:
        transcript = self.get_transcript(
            video_id
        )

        if transcript is None:
            transcript = Transcript(
                video_id=video_id,
                source_etag=source_etag,
                language_code=language_code,
                full_text=full_text,
                segments=segments,
                words=words,
                raw_output_key=raw_output_key,
            )

            self.db.add(
                transcript
            )

        else:
            transcript.source_etag = (
                source_etag
            )

            transcript.language_code = (
                language_code
            )

            transcript.full_text = (
                full_text
            )

            transcript.segments = (
                segments
            )

            transcript.words = (
                words
            )

            transcript.raw_output_key = (
                raw_output_key
            )

        return transcript
