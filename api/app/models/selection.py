import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class Selection(Base):
    __tablename__ = "selections"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
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

    transcript_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "transcripts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    summary_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "summary_jobs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    source_etag: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
        index=True,
    )

    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    selected_segment_ids: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    word_ranges: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    resolved_clips: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
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

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
