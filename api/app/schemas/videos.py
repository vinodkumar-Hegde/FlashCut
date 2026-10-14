from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
)


class VideoResponse(BaseModel):
    id: str
    name: str
    etag: str | None
    updated_at: datetime


class VideoListResponse(BaseModel):
    items: list[VideoResponse]
    count: int


class ResolveVideoRequest(BaseModel):
    bucket: str = Field(
        min_length=3,
        max_length=63,
    )

    key: str = Field(
        min_length=1,
        max_length=2048,
    )

    expected_etag: str | None = Field(
        default=None,
        max_length=256,
    )


class ResolveVideoResponse(
    VideoResponse
):
    created: bool


class RenameVideoRequest(BaseModel):
    new_name: str = Field(
        min_length=1,
        max_length=255,
    )
