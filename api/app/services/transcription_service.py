import json
import uuid
from datetime import datetime, timezone
from pathlib import PurePosixPath

from botocore.exceptions import ClientError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.transcription import (
    TranscriptionJob,
)
from app.providers.aws import (
    s3_client,
    transcribe_client,
)
from app.repositories.transcription_repository import (
    TranscriptionRepository,
)
from app.repositories.video_repository import (
    VideoRepository,
)


def utcnow():
    return datetime.now(
        timezone.utc
    )


def _render_words(
    parts: list[str],
) -> str:
    return " ".join(
        part
        for part in parts
        if part
    ).strip()


def normalize_transcript(
    payload: dict,
) -> tuple[str, list, list]:
    results = payload.get(
        "results",
        {},
    )

    transcripts = results.get(
        "transcripts",
        [],
    )

    full_text = ""

    if transcripts:
        full_text = str(
            transcripts[0].get(
                "transcript",
                "",
            )
        ).strip()

    items = results.get(
        "items",
        [],
    )

    words = []
    segments = []

    current_parts: list[str] = []
    current_word_ids: list[int] = []

    segment_start = None
    segment_end = None

    def flush_segment():
        nonlocal current_parts
        nonlocal current_word_ids
        nonlocal segment_start
        nonlocal segment_end

        if (
            segment_start is None
            or segment_end is None
            or not current_parts
        ):
            return

        text = _render_words(
            current_parts
        )

        if text:
            segments.append({
                "id":
                    len(segments) + 1,

                "start":
                    round(
                        segment_start,
                        3,
                    ),

                "end":
                    round(
                        segment_end,
                        3,
                    ),

                "text":
                    text,

                "start_word_id":
                    current_word_ids[0],

                "end_word_id":
                    current_word_ids[-1],
            })

        current_parts = []
        current_word_ids = []
        segment_start = None
        segment_end = None

    for item in items:
        alternatives = item.get(
            "alternatives",
            [],
        )

        if not alternatives:
            continue

        content = str(
            alternatives[0].get(
                "content",
                "",
            )
        ).strip()

        if not content:
            continue

        item_type = item.get(
            "type"
        )

        if item_type == "pronunciation":
            try:
                start = float(
                    item["start_time"]
                )

                end = float(
                    item["end_time"]
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

            word_id = len(words) + 1

            words.append({
                "id":
                    word_id,

                "start":
                    round(
                        start,
                        3,
                    ),

                "end":
                    round(
                        end,
                        3,
                    ),

                "text":
                    content,
            })

            if segment_start is None:
                segment_start = start

            segment_end = end

            current_parts.append(
                content
            )

            current_word_ids.append(
                word_id
            )

            if (
                segment_start is not None
                and segment_end - segment_start
                >= 14.0
            ):
                flush_segment()

        elif item_type == "punctuation":
            if not current_parts:
                continue

            current_parts[-1] = (
                current_parts[-1]
                + content
            )

            if (
                content in {
                    ".",
                    "?",
                    "!",
                }
                and segment_start is not None
                and segment_end is not None
                and (
                    segment_end
                    - segment_start
                ) >= 4.0
            ):
                flush_segment()

    flush_segment()

    return (
        full_text,
        segments,
        words,
    )


class TranscriptionService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

        self.settings = (
            get_settings()
        )

        self.repo = (
            TranscriptionRepository(
                db
            )
        )

        self.video_repo = (
            VideoRepository(
                db
            )
        )

        self.s3 = s3_client()

        self.transcribe = (
            transcribe_client()
        )

    def _current_etag(
        self,
        video,
    ) -> str:
        try:
            response = (
                self.s3.head_object(
                    Bucket=(
                        self.settings
                        .s3_bucket
                    ),
                    Key=video.s3_key,
                )
            )

        except ClientError as exc:
            raise AppError(
                502,
                "SOURCE_VIDEO_UNAVAILABLE",
                (
                    "The source video "
                    "could not be accessed."
                ),
            ) from exc

        etag = str(
            response.get(
                "ETag",
                "",
            )
        ).strip('"')

        if not etag:
            raise AppError(
                502,
                "SOURCE_ETAG_UNAVAILABLE",
                (
                    "The source video "
                    "ETag is unavailable."
                ),
            )

        if video.etag != etag:
            video.etag = etag
            self.db.commit()

        return etag

    def start(
        self,
        video_id: str,
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

        source_etag = (
            self._current_etag(
                video
            )
        )

        language_code = (
            self.settings.transcribe_language
        )

        vocabulary_name = (
            self.settings.transcribe_vocabulary
            or ""
        )

        config_version = (
            self.settings
            .transcribe_config_version
        )

        transcript = (
            self.repo.find_cached_transcript(
                video_id=video_id,
                source_etag=source_etag,
                language_code=language_code,
                vocabulary_name=vocabulary_name,
                config_version=config_version,
            )
        )

        if transcript is not None:
            return {
                "job":
                    None,
                "transcript":
                    transcript,
                "cached":
                    True,
            }

        active = (
            self.repo.find_active_job(
                video_id=video_id,
                source_etag=source_etag,
                language_code=language_code,
                vocabulary_name=vocabulary_name,
                config_version=config_version,
            )
        )

        if active is not None:
            return {
                "job":
                    active,
                "transcript":
                    None,
                "cached":
                    False,
            }

        job_id = str(
            uuid.uuid4()
        )

        provider_job_name = (
            "flashcut-"
            + job_id.replace(
                "-",
                "",
            )
        )

        output_key = (
            self.settings
            .s3_transcript_prefix
            + provider_job_name
            + ".json"
        )

        job = TranscriptionJob(
            id=job_id,
            video_id=video_id,
            provider_job_name=(
                provider_job_name
            ),
            source_etag=source_etag,
            language_code=language_code,
            vocabulary_name=vocabulary_name,
            config_version=config_version,
            status="queued",
            output_key=output_key,
        )

        self.db.add(
            job
        )

        try:
            self.db.commit()

        except IntegrityError:
            self.db.rollback()

            active = (
                self.repo.find_active_job(
                    video_id=video_id,
                    source_etag=source_etag,
                    language_code=language_code,
                    vocabulary_name=vocabulary_name,
                    config_version=config_version,
                )
            )

            if active is not None:
                return {
                    "job":
                        active,
                    "transcript":
                        None,
                    "cached":
                        False,
                }

            raise

        media_format = (
            PurePosixPath(
                video.filename
            )
            .suffix
            .lower()
            .lstrip(".")
        )

        if media_format not in {
            "mp4",
            "webm",
        }:
            job.status = "failed"
            job.failure_reason = (
                "Unsupported media format."
            )

            self.db.commit()

            raise AppError(
                400,
                "UNSUPPORTED_VIDEO_FORMAT",
                (
                    "Only MP4 and WebM "
                    "are supported."
                ),
            )

        args = {
            "TranscriptionJobName":
                provider_job_name,

            "Media": {
                "MediaFileUri":
                    (
                        f"s3://"
                        f"{self.settings.s3_bucket}/"
                        f"{video.s3_key}"
                    )
            },

            "MediaFormat":
                media_format,

            "LanguageCode":
                language_code,

            "OutputBucketName":
                self.settings
                .s3_bucket,

            "OutputKey":
                output_key,
        }

        if vocabulary_name:
            args["Settings"] = {
                "VocabularyName":
                    vocabulary_name
            }

        try:
            self.transcribe.start_transcription_job(
                **args
            )

        except ClientError as exc:
            job.status = "failed"

            job.failure_reason = str(
                exc.response.get(
                    "Error",
                    {},
                ).get(
                    "Code",
                    "TRANSCRIBE_ERROR",
                )
            )

            self.db.commit()

            raise AppError(
                502,
                "TRANSCRIBE_START_FAILED",
                (
                    "Amazon Transcribe "
                    "could not start the job."
                ),
            ) from exc

        job.status = "in_progress"

        self.db.commit()

        self.db.refresh(
            job
        )

        return {
            "job":
                job,
            "transcript":
                None,
            "cached":
                False,
        }

    def refresh(
        self,
        job_id: str,
    ):
        job = self.repo.get_job(
            job_id
        )

        if job is None:
            raise AppError(
                404,
                "TRANSCRIPTION_NOT_FOUND",
                (
                    "Transcription job "
                    "not found."
                ),
            )

        if job.status in {
            "completed",
            "failed",
        }:
            transcript = (
                self.repo.get_transcript_for_job(
                    job.id
                )
            )

            return (
                job,
                transcript,
            )

        try:
            response = (
                self.transcribe
                .get_transcription_job(
                    TranscriptionJobName=(
                        job.provider_job_name
                    )
                )
            )

        except ClientError as exc:
            raise AppError(
                502,
                "TRANSCRIBE_STATUS_FAILED",
                (
                    "Amazon Transcribe "
                    "status could not be read."
                ),
            ) from exc

        provider_job = (
            response[
                "TranscriptionJob"
            ]
        )

        status = provider_job.get(
            "TranscriptionJobStatus"
        )

        if status == "FAILED":
            job.status = "failed"

            job.failure_reason = (
                provider_job.get(
                    "FailureReason"
                )
                or
                "Amazon Transcribe failed."
            )

            job.completed_at = utcnow()

            self.db.commit()

            return (
                job,
                None,
            )

        if status != "COMPLETED":
            job.status = "in_progress"

            self.db.commit()

            return (
                job,
                None,
            )

        try:
            obj = self.s3.get_object(
                Bucket=(
                    self.settings
                    .s3_bucket
                ),
                Key=job.output_key,
            )

            payload = json.loads(
                obj["Body"]
                .read()
                .decode(
                    "utf-8"
                )
            )

        except Exception as exc:
            raise AppError(
                502,
                "TRANSCRIPT_DOWNLOAD_FAILED",
                (
                    "Completed transcript "
                    "could not be loaded."
                ),
            ) from exc

        (
            full_text,
            segments,
            words,
        ) = normalize_transcript(
            payload
        )

        language_code = (
            provider_job.get(
                "LanguageCode"
            )
        )

        transcript = (
            self.repo.create_transcript(
                job=job,
                language_code=(
                    language_code
                    or job.language_code
                ),
                full_text=full_text,
                segments=segments,
                words=words,
                raw_output_key=(
                    job.output_key
                ),
            )
        )

        job.status = "completed"
        job.completed_at = utcnow()
        job.failure_reason = None

        self.db.commit()

        self.db.refresh(
            job
        )

        self.db.refresh(
            transcript
        )

        return (
            job,
            transcript,
        )

    def get_transcript(
        self,
        video_id: str,
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

        source_etag = (
            self._current_etag(
                video
            )
        )

        transcript = (
            self.repo.find_cached_transcript(
                video_id=video_id,
                source_etag=source_etag,
                language_code=(
                    self.settings
                    .transcribe_language
                ),
                vocabulary_name=(
                    self.settings
                    .transcribe_vocabulary
                    or ""
                ),
                config_version=(
                    self.settings
                    .transcribe_config_version
                ),
            )
        )

        if transcript is None:
            raise AppError(
                404,
                "TRANSCRIPT_NOT_FOUND",
                (
                    "No transcript exists "
                    "for this video."
                ),
            )

        return transcript
