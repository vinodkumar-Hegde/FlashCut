import re
import uuid
from datetime import (
    datetime,
    timezone,
)
from pathlib import PurePosixPath

from botocore.exceptions import (
    ClientError,
)
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.tenant import (
    current_tenant_id,
)
from app.models.render_asset import (
    RenderAsset,
)
from app.providers.aws import s3_client
from app.repositories.render_asset_repository import (
    RenderAssetRepository,
)


class RenderAssetService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.settings = get_settings()

        self.repo = (
            RenderAssetRepository(
                db
            )
        )

        self.s3 = s3_client()

    @staticmethod
    def _safe_filename(
        filename: str,
    ) -> str:
        original = PurePosixPath(
            filename
        )

        if (
            original.suffix.lower()
            != ".mp4"
        ):
            raise AppError(
                400,
                "RENDER_ASSET_TYPE_INVALID",
                (
                    "Intro and outro videos "
                    "must be MP4 files."
                ),
            )

        stem = re.sub(
            r"[^A-Za-z0-9._-]+",
            "-",
            original.stem,
        ).strip(
            "-._"
        )

        if not stem:
            stem = "video"

        return (
            stem[:480]
            + ".mp4"
        )

    def create_upload(
        self,
        *,
        kind: str,
        filename: str,
        content_type: str,
        size_bytes: int,
    ):
        if (
            content_type
            != "video/mp4"
        ):
            raise AppError(
                400,
                "RENDER_ASSET_TYPE_INVALID",
                (
                    "Intro and outro videos "
                    "must use video/mp4."
                ),
            )

        if (
            size_bytes
            > self.settings
            .render_asset_max_bytes
        ):
            raise AppError(
                413,
                "RENDER_ASSET_TOO_LARGE",
                (
                    "The intro or outro video "
                    "exceeds the upload limit."
                ),
            )

        tenant_id = current_tenant_id(
            self.db
        )

        if not tenant_id:
            raise AppError(
                500,
                "TENANT_CONTEXT_MISSING",
                (
                    "Tenant context is "
                    "unavailable."
                ),
            )

        asset_id = str(
            uuid.uuid4()
        )

        safe_name = self._safe_filename(
            filename
        )

        key = (
            self.settings
            .s3_render_asset_prefix
            + "tenants/"
            + tenant_id
            + "/"
            + asset_id
            + "/"
            + safe_name
        )

        asset = RenderAsset(
            id=asset_id,
            kind=kind,
            filename=safe_name,
            s3_key=key,
            content_type=content_type,
            size_bytes=size_bytes,
            status="uploading",
        )

        self.db.add(
            asset
        )

        self.db.commit()

        self.db.refresh(
            asset
        )

        expires = (
            self.settings
            .render_asset_upload_presign_seconds
        )

        upload = (
            self.s3
            .generate_presigned_post(
                Bucket=(
                    self.settings
                    .s3_bucket
                ),
                Key=key,
                Fields={
                    "Content-Type":
                        "video/mp4",
                },
                Conditions=[
                    {
                        "Content-Type":
                            "video/mp4"
                    },
                    [
                        "content-length-range",
                        1,
                        self.settings
                        .render_asset_max_bytes,
                    ],
                ],
                ExpiresIn=expires,
            )
        )

        return (
            asset,
            {
                "asset_id":
                    asset.id,

                "kind":
                    asset.kind,

                "upload_method":
                    "POST",

                "upload_url":
                    upload["url"],

                "upload_fields":
                    upload["fields"],

                "expires_in":
                    expires,
            },
        )

    def get(
        self,
        asset_id: str,
    ) -> RenderAsset:
        asset = self.repo.get(
            asset_id
        )

        if asset is None:
            raise AppError(
                404,
                "RENDER_ASSET_NOT_FOUND",
                "Render asset not found.",
            )

        return asset

    def complete(
        self,
        asset_id: str,
    ) -> RenderAsset:
        asset = self.get(
            asset_id
        )

        if asset.status == "ready":
            return asset

        if asset.status == "rejected":
            raise AppError(
                409,
                "RENDER_ASSET_REJECTED",
                (
                    "The render asset "
                    "was rejected."
                ),
            )

        try:
            head = self.s3.head_object(
                Bucket=(
                    self.settings
                    .s3_bucket
                ),
                Key=asset.s3_key,
            )

        except ClientError as exc:
            code = str(
                exc.response
                .get(
                    "Error",
                    {},
                )
                .get(
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
                    409,
                    "RENDER_ASSET_UPLOAD_NOT_FOUND",
                    (
                        "The uploaded render "
                        "asset was not found."
                    ),
                ) from exc

            raise AppError(
                503,
                "RENDER_ASSET_STORAGE_UNAVAILABLE",
                (
                    "Render asset storage "
                    "is unavailable."
                ),
            ) from exc

        actual_size = int(
            head.get(
                "ContentLength",
                0,
            )
        )

        actual_type = str(
            head.get(
                "ContentType",
                "",
            )
        ).split(
            ";",
            1,
        )[0].strip().lower()

        etag = str(
            head.get(
                "ETag",
                "",
            )
        ).strip(
            '"'
        )

        invalid = (
            actual_size <= 0
            or actual_size
            > self.settings
            .render_asset_max_bytes
            or actual_size
            != asset.size_bytes
            or actual_type
            != "video/mp4"
            or not etag
        )

        if invalid:
            asset.status = (
                "rejected"
            )

            self.db.commit()

            try:
                self.s3.delete_object(
                    Bucket=(
                        self.settings
                        .s3_bucket
                    ),
                    Key=asset.s3_key,
                )

            except Exception:
                pass

            raise AppError(
                400,
                "RENDER_ASSET_INVALID",
                (
                    "The uploaded intro or "
                    "outro video failed "
                    "validation."
                ),
            )

        asset.size_bytes = (
            actual_size
        )

        asset.content_type = (
            actual_type
        )

        asset.etag = etag

        asset.status = "ready"

        asset.completed_at = (
            datetime.now(
                timezone.utc
            )
        )

        self.db.commit()

        self.db.refresh(
            asset
        )

        return asset

    def preview(
        self,
        asset_id: str,
    ):
        asset = self.get(
            asset_id
        )

        if asset.status != "ready":
            raise AppError(
                409,
                "RENDER_ASSET_NOT_READY",
                (
                    "The render asset is "
                    "not ready."
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
                        asset.s3_key,
                },
                ExpiresIn=expires,
            )
        )

        return {
            "asset_id":
                asset.id,

            "expires_in":
                expires,

            "url":
                url,
        }
