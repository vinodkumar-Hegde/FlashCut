from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
)


class WordRange(BaseModel):
    start_word_id: int = Field(
        ge=1
    )

    end_word_id: int = Field(
        ge=1
    )


class CreateSelectionRequest(BaseModel):
    video_id: str
    summary_id: str | None = None


class UpdateSelectionRequest(BaseModel):
    revision: int = Field(
        ge=1
    )

    selected_segment_ids: list[int] = Field(
        default_factory=list,
        max_length=1000,
    )

    word_ranges: list[WordRange] = Field(
        default_factory=list,
        max_length=1000,
    )


class ApproveSelectionRequest(BaseModel):
    revision: int = Field(
        ge=1
    )


class ResolvedClip(BaseModel):
    clip_id: int
    start: float
    end: float
    duration: float

    start_word_id: int | None
    end_word_id: int | None

    segment_ids: list[int]
    word_ranges: list[WordRange]

    text: str


class SelectionResponse(BaseModel):
    id: str

    video_id: str
    transcript_id: str
    summary_id: str | None

    status: str
    revision: int

    selected_segment_ids: list[int]
    word_ranges: list[WordRange]

    resolved_clips: list[
        ResolvedClip
    ]

    total_seconds: float

    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
