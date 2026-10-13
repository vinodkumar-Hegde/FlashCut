from datetime import datetime

from pydantic import BaseModel


class CreateRenderRequest(BaseModel):
    selection_id: str


class RenderResponse(BaseModel):
    id: str
    video_id: str
    selection_id: str

    status: str
    cached: bool

    selected_seconds: float
    attempt_count: int

    container_format: str | None
    output_filename: str | None

    error_code: str | None
    error_message: str | None

    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class RenderResultResponse(BaseModel):
    render_id: str
    filename: str
    container_format: str | None
    size_bytes: int | None
    expires_in: int
    url: str
