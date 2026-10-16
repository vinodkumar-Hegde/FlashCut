from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )


class CreateQuickSummaryRequest(
    StrictModel
):
    video_id: str


class QuickSummaryResponse(
    StrictModel
):
    id: str
    video_id: str

    transcript_id: str | None
    transcription_job_id: str | None

    status: str

    model_id: str
    algorithm_version: str

    attempt_count: int

    error_code: str | None
    error_message: str | None

    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class QuickSummaryResult(
    StrictModel
):
    id: str
    status: str

    summary: str
    key_points: list[str]
    topics: list[str]
