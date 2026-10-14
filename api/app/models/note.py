import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.base import Base


def utcnow():
    return datetime.now(
        timezone.utc
    )


class NoteJob(Base):
    __tablename__ = "note_jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(
            uuid.uuid4()
        ),
    )

    tenant_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    video_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "videos.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    transcript_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "transcripts.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    transcription_job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "transcription_jobs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    source_etag: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
    )

    style: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    model_id: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    algorithm_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    content: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    visuals: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
