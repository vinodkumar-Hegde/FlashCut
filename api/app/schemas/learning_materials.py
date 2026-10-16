from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
)


NotesStyle = Literal[
    "standard",
    "crisp",
    "high_yield",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )


class CreateLearningMaterialRequest(
    StrictModel
):
    video_id: str

    notes_style: NotesStyle = (
        "standard"
    )

    include_mind_map: bool = True
    include_flowchart: bool = True


class LearningMaterialResponse(
    StrictModel
):
    id: str
    video_id: str

    transcript_id: str | None
    transcription_job_id: str | None

    notes_style: NotesStyle

    include_mind_map: bool
    include_flowchart: bool

    status: str

    model_id: str
    algorithm_version: str

    component_status: dict
    component_errors: dict

    revision: int
    attempt_count: int

    error_code: str | None
    error_message: str | None

    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class LearningMaterialResult(
    StrictModel
):
    id: str
    status: str
    revision: int

    notes: dict
    mind_map: dict
    flowchart: dict

    component_status: dict
    component_errors: dict
