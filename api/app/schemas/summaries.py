from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
)


class CreateSummaryRequest(BaseModel):
    video_id: str

    target_minutes: int = Field(
        default=5,
        ge=1,
        le=30,
    )


class SummarySelection(BaseModel):
    id: int
    start: float
    end: float

    start_word_id: int | None = None
    end_word_id: int | None = None

    text: str

    importance: int = Field(
        ge=0,
        le=100,
    )

    critical: bool

    topic: str
    kind: str
    reason: str
    learning_point: str


class SummaryNotes(BaseModel):
    title: str
    bullets: list[str]


class SummaryResponse(BaseModel):
    id: str
    video_id: str
    transcript_id: str

    status: str
    cached: bool

    target_minutes: float

    model_id: str
    algorithm_version: str

    candidate_count: int

    selected_seconds: float
    budget_usage_pct: float

    coverage_topics: list[str]

    notes: SummaryNotes | dict

    selections: list[
        SummarySelection
    ]

    failure_reason: str | None

    created_at: datetime
    completed_at: datetime | None
