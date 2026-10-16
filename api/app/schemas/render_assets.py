from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)


class CreateRenderAssetUploadRequest(
    BaseModel
):
    kind: Literal[
        "intro",
        "outro",
    ]

    filename: str = Field(
        min_length=1,
        max_length=512,
    )

    content_type: Literal[
        "video/mp4"
    ] = "video/mp4"

    size_bytes: int = Field(
        gt=0
    )


class RenderAssetUploadResponse(
    BaseModel
):
    asset_id: str
    kind: str

    upload_method: str
    upload_url: str
    upload_fields: dict[str, str]

    expires_in: int


class RenderAssetResponse(
    BaseModel
):
    id: str
    kind: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    etag: str | None

    created_at: datetime
    completed_at: datetime | None


class RenderAssetPreviewResponse(
    BaseModel
):
    asset_id: str
    expires_in: int
    url: str
