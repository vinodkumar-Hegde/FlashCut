from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


NoteStyle = Literal[
    "standard",
    "crisp",
    "high_yield",
]

VisualKind = Literal[
    "mindmap",
    "flowchart",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )


class CreateNoteRequest(StrictModel):
    video_id: str

    style: NoteStyle = (
        "standard"
    )


class NoteBullet(StrictModel):
    text: str = Field(
        min_length=1,
        max_length=1200,
    )

    source_segment_ids: list[int] = Field(
        default_factory=list,
        max_length=50,
    )


class NoteSection(StrictModel):
    heading: str = Field(
        min_length=1,
        max_length=200,
    )

    bullets: list[NoteBullet] = Field(
        default_factory=list,
        max_length=20,
    )


class NoteContent(StrictModel):
    title: str = Field(
        min_length=1,
        max_length=300,
    )

    overview: str = Field(
        default="",
        max_length=5000,
    )

    sections: list[NoteSection] = Field(
        default_factory=list,
        max_length=20,
    )

    key_takeaways: list[NoteBullet] = Field(
        default_factory=list,
        max_length=20,
    )


class UpdateNoteRequest(StrictModel):
    revision: int = Field(
        ge=1,
    )

    content: NoteContent


class GenerateVisualRequest(StrictModel):
    revision: int = Field(
        ge=1,
    )

    kind: VisualKind


class NoteResponse(StrictModel):
    id: str
    video_id: str
    transcript_id: str | None
    transcription_job_id: str | None

    style: NoteStyle
    status: str

    model_id: str
    algorithm_version: str

    revision: int

    content: dict
    visuals: list[dict]

    failure_reason: str | None

    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
