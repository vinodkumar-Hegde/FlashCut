import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.base import Base


def utcnow():
    return datetime.now(
        timezone.utc
    )


class RenderJob(Base):
    __tablename__ = "render_jobs"

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

    selection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "selections.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
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

    render_profile_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    output_filename: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    output_key: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    output_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    container_format: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    selected_seconds: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    error_code: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
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

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class RenderOutbox(Base):
    __tablename__ = "render_outbox"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    render_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "render_jobs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=utcnow,
    )

    last_error: Mapped[str | None] = mapped_column(
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

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
