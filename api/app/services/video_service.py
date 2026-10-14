from pathlib import PurePosixPath

from botocore.exceptions import ClientError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.tenant import current_tenant_id
from app.models.video import Video
from app.providers.aws import s3_client
from app.repositories.video_repository import (
    VideoRepository,
)


ALLOWED_EXTENSIONS = {
    ".mp4",
    ".webm",
}


class VideoService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.settings = get_settings()
        self.s3 = s3_client()
        self.repo = VideoRepository(
            db
        )

    def _allowed_source_prefix(
        self,
    ) -> str:
        base_prefix = (
            self.settings
            .s3_video_prefix
        )

        template = (
            self.settings
            .s3_tenant_prefix_template
            or ""
        ).strip()

        if not template:
            return base_prefix

        tenant_id = (
            current_tenant_id(
                self.db
            )
        )

        if not tenant_id:
            raise AppError(
                403,
                "TENANT_CONTEXT_REQUIRED",
                (
                    "A tenant context is "
                    "required to resolve "
                    "source videos."
                ),
            )

        try:
            prefix = template.format(
                tenant_id=tenant_id
            )

        except (
            KeyError,
            ValueError,
        ) as exc:
            raise RuntimeError(
                "Invalid "
                "S3_TENANT_PREFIX_TEMPLATE."
            ) from exc

        prefix = (
            prefix
            .strip()
            .lstrip("/")
        )

        if not prefix:
            raise RuntimeError(
                "Tenant source prefix "
                "cannot be empty."
            )

        if not prefix.endswith("/"):
            prefix += "/"

        if not prefix.startswith(
            base_prefix
        ):
            raise RuntimeError(
                "Tenant source prefix must "
                "remain inside "
                "S3_VIDEO_PREFIX."
            )

        return prefix


    def _validate_source_key(
        self,
        key: str,
        *,
        prefix: str | None = None,
    ) -> None:
        key = key.strip()

        allowed_prefix = (
            prefix
            or self.settings
            .s3_video_prefix
        )

        if not key.startswith(
            allowed_prefix
        ):
            raise AppError(
                400,
                "INVALID_VIDEO_KEY",
                (
                    "Video must belong "
                    "to an allowed source "
                    "prefix."
                ),
            )

        relative = key[
            len(allowed_prefix):
        ]

        if (
            not relative
            or relative.startswith("/")
            or "\x00" in relative
        ):
            raise AppError(
                400,
                "INVALID_VIDEO_KEY",
                "Invalid video key.",
            )

        path = PurePosixPath(
            relative
        )

        if ".." in path.parts:
            raise AppError(
                400,
                "INVALID_VIDEO_KEY",
                "Invalid video key.",
            )

        if (
            path.suffix.lower()
            not in ALLOWED_EXTENSIONS
        ):
            raise AppError(
                400,
                "UNSUPPORTED_VIDEO_FORMAT",
                (
                    "Only MP4 and WebM "
                    "videos are supported."
                ),
            )


    def list_for_api(
        self,
    ) -> list[Video]:
        # Local development retains the convenient
        # S3 discovery workflow. Authenticated
        # environments only list videos explicitly
        # owned/resolved by the current tenant.
        if (
            self.settings.auth_disabled
            and self.settings
            .app_env
            .strip()
            .lower()
            == "local"
        ):
            return (
                self.sync_from_s3()
            )

        return (
            self.repo.list_all()
        )


    def resolve_source(
        self,
        *,
        bucket: str,
        key: str,
        expected_etag: str | None,
    ) -> tuple[Video, bool]:
        bucket = bucket.strip()
        key = key.strip()

        if (
            bucket
            != self.settings.s3_bucket
        ):
            raise AppError(
                403,
                "SOURCE_BUCKET_NOT_ALLOWED",
                (
                    "The requested source "
                    "bucket is not allowed."
                ),
            )

        prefix = (
            self._allowed_source_prefix()
        )

        self._validate_source_key(
            key,
            prefix=prefix,
        )

        try:
            head = self.s3.head_object(
                Bucket=bucket,
                Key=key,
            )

        except ClientError as exc:
            code = str(
                exc.response.get(
                    "Error",
                    {},
                ).get(
                    "Code",
                    "",
                )
            )

            if code in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                raise AppError(
                    404,
                    "SOURCE_VIDEO_NOT_FOUND",
                    (
                        "The source video "
                        "does not exist."
                    ),
                ) from exc

            if code in {
                "403",
                "AccessDenied",
            }:
                raise AppError(
                    403,
                    "SOURCE_VIDEO_ACCESS_DENIED",
                    (
                        "The source video "
                        "cannot be accessed."
                    ),
                ) from exc

            raise AppError(
                502,
                "SOURCE_VIDEO_LOOKUP_FAILED",
                (
                    "The source video "
                    "could not be verified."
                ),
            ) from exc

        size_bytes = int(
            head.get(
                "ContentLength",
                0,
            )
            or 0
        )

        if size_bytes <= 0:
            raise AppError(
                400,
                "SOURCE_VIDEO_EMPTY",
                (
                    "The source video "
                    "is empty."
                ),
            )

        etag = str(
            head.get(
                "ETag",
                "",
            )
        ).strip().strip('"')

        if not etag:
            raise AppError(
                502,
                "SOURCE_ETAG_UNAVAILABLE",
                (
                    "The source video "
                    "ETag is unavailable."
                ),
            )

        if expected_etag:
            normalized_expected = (
                expected_etag
                .strip()
                .strip('"')
            )

            if (
                normalized_expected
                != etag
            ):
                raise AppError(
                    409,
                    "SOURCE_VERSION_MISMATCH",
                    (
                        "The source video "
                        "changed before it "
                        "was resolved."
                    ),
                )

        existing = (
            self.repo.get_by_key(
                key
            )
        )

        created = (
            existing is None
        )

        filename = (
            PurePosixPath(
                key
            ).name
        )

        video = self.repo.upsert(
            key=key,
            filename=filename,
            etag=etag,
        )

        try:
            self.db.commit()

        except IntegrityError:
            # Concurrent resolver calls for the same
            # tenant/key are idempotent.
            self.db.rollback()

            video = (
                self.repo.get_by_key(
                    key
                )
            )

            if video is None:
                raise

            created = False

            video.filename = filename
            video.etag = etag

            self.db.commit()

        self.db.refresh(
            video
        )

        return (
            video,
            created,
        )


    def sync_from_s3(
        self,
    ) -> list[Video]:
        prefix = (
            self.settings
            .s3_video_prefix
        )

        paginator = (
            self.s3.get_paginator(
                "list_objects_v2"
            )
        )

        count = 0

        for page in paginator.paginate(
            Bucket=self.settings.s3_bucket,
            Prefix=prefix,
        ):
            for obj in page.get(
                "Contents",
                [],
            ):
                key = obj["Key"]

                try:
                    self._validate_source_key(
                        key
                    )
                except AppError:
                    continue

                filename = (
                    PurePosixPath(
                        key
                    ).name
                )

                etag = str(
                    obj.get(
                        "ETag",
                        "",
                    )
                ).strip('"')

                self.repo.upsert(
                    key=key,
                    filename=filename,
                    etag=etag or None,
                )

                count += 1

                if (
                    count
                    >= self.settings
                    .max_video_list
                ):
                    break

            if (
                count
                >= self.settings
                .max_video_list
            ):
                break

        self.db.commit()

        return (
            self.repo.list_all()
        )

    def rename(
        self,
        *,
        video_id: str,
        new_name: str,
    ) -> Video:
        video = self.repo.get(
            video_id
        )

        if video is None:
            raise AppError(
                404,
                "VIDEO_NOT_FOUND",
                "Video not found.",
            )

        self._validate_source_key(
            video.s3_key
        )

        new_name = (
            new_name.strip()
        )

        if (
            not new_name
            or len(new_name) > 255
            or "\x00" in new_name
            or "/" in new_name
            or "\\" in new_name
        ):
            raise AppError(
                400,
                "INVALID_VIDEO_NAME",
                "Invalid video name.",
            )

        old_extension = (
            PurePosixPath(
                video.filename
            )
            .suffix
            .lower()
        )

        new_extension = (
            PurePosixPath(
                new_name
            )
            .suffix
            .lower()
        )

        if (
            new_extension
            not in ALLOWED_EXTENSIONS
        ):
            raise AppError(
                400,
                "UNSUPPORTED_VIDEO_FORMAT",
                (
                    "Only MP4 and WebM "
                    "videos are supported."
                ),
            )

        if (
            new_extension
            != old_extension
        ):
            raise AppError(
                400,
                "FORMAT_CHANGE_NOT_ALLOWED",
                (
                    "Renaming cannot "
                    "change the video "
                    "container format."
                ),
            )

        new_key = (
            self.settings
            .s3_video_prefix
            + new_name
        )

        self._validate_source_key(
            new_key
        )

        if new_key == video.s3_key:
            return video

        try:
            self.s3.head_object(
                Bucket=(
                    self.settings
                    .s3_bucket
                ),
                Key=new_key,
            )

        except ClientError as exc:
            code = str(
                exc.response.get(
                    "Error",
                    {},
                ).get(
                    "Code",
                    "",
                )
            )

            if code not in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                raise

        else:
            raise AppError(
                409,
                "VIDEO_ALREADY_EXISTS",
                (
                    "A video with that "
                    "name already exists."
                ),
            )

        old_key = video.s3_key

        self.s3.copy_object(
            Bucket=(
                self.settings
                .s3_bucket
            ),
            CopySource={
                "Bucket":
                    self.settings
                    .s3_bucket,
                "Key":
                    old_key,
            },
            Key=new_key,
        )

        self.s3.delete_object(
            Bucket=(
                self.settings
                .s3_bucket
            ),
            Key=old_key,
        )

        video.s3_key = new_key
        video.filename = new_name

        self.db.commit()
        self.db.refresh(
            video
        )

        return video
