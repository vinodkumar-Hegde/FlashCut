import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
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


class SummaryJob(Base):
    __tablename__ = "summary_jobs"

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

    transcript_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "transcripts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    source_etag: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )

    target_seconds: Mapped[int] = mapped_column(
        Integer,
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

    selected_segments: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    notes: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    coverage_topics: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    candidate_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    selected_seconds: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    budget_usage_pct: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
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
