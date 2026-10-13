from pathlib import PurePosixPath

from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
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

    def _validate_source_key(
        self,
        key: str,
    ) -> None:
        prefix = (
            self.settings
            .s3_video_prefix
        )

        if not key.startswith(
            prefix
        ):
            raise AppError(
                400,
                "INVALID_VIDEO_KEY",
                (
                    "Video must belong "
                    "to the configured "
                    "source prefix."
                ),
            )

        relative = key[
            len(prefix):
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
