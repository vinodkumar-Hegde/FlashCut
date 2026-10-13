from datetime import datetime

from pydantic import BaseModel


class StartTranscriptionRequest(BaseModel):
    video_id: str


class TranscriptionJobResponse(BaseModel):
    id: str | None
    video_id: str
    status: str
    cached: bool
    transcript_id: str | None = None
    failure_reason: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class TranscriptSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    start_word_id: int
    end_word_id: int


class TranscriptWord(BaseModel):
    id: int
    start: float
    end: float
    text: str


class TranscriptResponse(BaseModel):
    id: str
    video_id: str
    language_code: str | None
    full_text: str
    segments: list[TranscriptSegment]
    word_count: int
    updated_at: datetime


class TranscriptWordsResponse(BaseModel):
    transcript_id: str
    video_id: str
    words: list[TranscriptWord]
    word_count: int
