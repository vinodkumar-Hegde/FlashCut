import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.render import (
    RenderJob,
    RenderOutbox,
)
from app.providers.aws import s3_client
from app.repositories.render_repository import (
    RenderRepository,
)
from app.repositories.selection_repository import (
    SelectionRepository,
)
from app.repositories.video_repository import (
    VideoRepository,
)


class RenderService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.settings = get_settings()

        self.repo = RenderRepository(
            db
        )

        self.selection_repo = (
            SelectionRepository(
                db
            )
        )

        self.video_repo = (
            VideoRepository(
                db
            )
        )

        self.s3 = s3_client()

    def create(
        self,
        selection_id: str,
    ):
        selection = (
            self.selection_repo.get(
                selection_id
            )
        )

        if selection is None:
            raise AppError(
                404,
                "SELECTION_NOT_FOUND",
                "Selection not found.",
            )

        if selection.status != "approved":
            raise AppError(
                409,
                "SELECTION_NOT_APPROVED",
                (
                    "The selection must be "
                    "approved before rendering."
                ),
            )

        if not selection.resolved_clips:
            raise AppError(
                400,
                "EMPTY_SELECTION",
                (
                    "The approved selection "
                    "contains no clips."
                ),
            )

        if (
            len(selection.resolved_clips)
            > self.settings.render_max_clips
        ):
            raise AppError(
                400,
                "TOO_MANY_CLIPS",
                "The selection has too many clips.",
            )

        selected_seconds = sum(
            float(
                item["duration"]
            )
            for item
            in selection.resolved_clips
        )

        if (
            selected_seconds
            > self.settings
            .render_max_total_seconds
        ):
            raise AppError(
                400,
                "RENDER_TOO_LONG",
                (
                    "The selected duration "
                    "exceeds the render limit."
                ),
            )

        video = self.video_repo.get(
            selection.video_id
        )

        if video is None:
            raise AppError(
                404,
                "VIDEO_NOT_FOUND",
                "Video not found.",
            )

        if (
            video.etag
            and video.etag
            != selection.source_etag
        ):
            raise AppError(
                409,
                "SOURCE_CHANGED",
                (
                    "The source video changed "
                    "after this selection was "
                    "created."
                ),
            )

        profile = (
            self.settings
            .render_profile_version
        )

        existing = (
            self.repo.find_reusable(
                selection_id=selection.id,
                profile=profile,
            )
        )

        if existing is not None:
            return (
                existing,
                existing.status
                == "completed",
            )

        job = RenderJob(
            id=str(uuid.uuid4()),
            video_id=video.id,
            selection_id=selection.id,
            source_etag=(
                selection.source_etag
            ),
            status="queued",
            render_profile_version=profile,
            selected_seconds=round(
                selected_seconds,
                3,
            ),
            attempt_count=0,
        )

        outbox = RenderOutbox(
            id=str(uuid.uuid4()),
            render_id=job.id,
            status="pending",
            attempt_count=0,
        )

        self.db.add(job)
        self.db.add(outbox)

        try:
            self.db.commit()

        except IntegrityError:
            self.db.rollback()

            existing = (
                self.repo.find_reusable(
                    selection_id=(
                        selection.id
                    ),
                    profile=profile,
                )
            )

            if existing is not None:
                return (
                    existing,
                    existing.status
                    == "completed",
                )

            raise

        self.db.refresh(job)

        return (
            job,
            False,
        )

    def get(
        self,
        render_id: str,
    ) -> RenderJob:
        job = self.repo.get(
            render_id
        )

        if job is None:
            raise AppError(
                404,
                "RENDER_NOT_FOUND",
                "Render job not found.",
            )

        return job

    def result(
        self,
        render_id: str,
    ) -> dict:
        job = self.get(
            render_id
        )

        if (
            job.status != "completed"
            or not job.output_key
            or not job.output_filename
        ):
            raise AppError(
                409,
                "RENDER_NOT_READY",
                (
                    "The rendered video is "
                    "not available yet."
                ),
            )

        expires = (
            self.settings
            .render_presign_seconds
        )

        url = (
            self.s3
            .generate_presigned_url(
                "get_object",
                Params={
                    "Bucket":
                        self.settings
                        .s3_bucket,

                    "Key":
                        job.output_key,
                },
                ExpiresIn=expires,
            )
        )

        return {
            "render_id":
                job.id,

            "filename":
                job.output_filename,

            "container_format":
                job.container_format,

            "size_bytes":
                job.output_size_bytes,

            "expires_in":
                expires,

            "url":
                url,
        }
