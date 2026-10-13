import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
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


class TranscriptionJob(Base):
    __tablename__ = "transcription_jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(
            uuid.uuid4()
        ),
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

    provider_job_name: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        unique=True,
    )

    source_etag: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    output_key: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
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


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(
            uuid.uuid4()
        ),
    )

    video_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "videos.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    source_etag: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )

    language_code: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    full_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    segments: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    words: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    raw_output_key: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
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
