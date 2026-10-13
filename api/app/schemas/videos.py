from datetime import datetime

from pydantic import BaseModel, Field


class VideoResponse(BaseModel):
    id: str
    name: str
    etag: str | None
    updated_at: datetime


class VideoListResponse(BaseModel):
    items: list[VideoResponse]
    count: int


class RenameVideoRequest(BaseModel):
    new_name: str = Field(
        min_length=1,
        max_length=255,
    )
