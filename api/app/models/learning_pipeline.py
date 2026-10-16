import uuid
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
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


class QuickSummaryJob(Base):
    __tablename__ = (
        "quick_summary_jobs"
    )

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

    idempotency_key: Mapped[
        str | None
    ] = mapped_column(
        String(128),
        nullable=True,
    )

    idempotency_hash: Mapped[
        str | None
    ] = mapped_column(
        String(64),
        nullable=True,
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

    transcript_id: Mapped[
        str | None
    ] = mapped_column(
        String(36),
        ForeignKey(
            "transcripts.id",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    transcription_job_id: Mapped[
        str | None
    ] = mapped_column(
        String(36),
        ForeignKey(
            "transcription_jobs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    source_etag: Mapped[
        str | None
    ] = mapped_column(
        String(256),
        nullable=True,
    )

    fingerprint: Mapped[str] = (
        mapped_column(
            String(64),
            nullable=False,
        )
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

    algorithm_version: Mapped[
        str
    ] = mapped_column(
        String(64),
        nullable=False,
    )

    result: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    attempt_count: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
            default=0,
        )
    )

    next_attempt_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    heartbeat_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    error_code: Mapped[
        str | None
    ] = mapped_column(
        String(128),
        nullable=True,
    )

    error_message: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    updated_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    started_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class LearningMaterialJob(Base):
    __tablename__ = (
        "learning_material_jobs"
    )

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

    idempotency_key: Mapped[
        str | None
    ] = mapped_column(
        String(128),
        nullable=True,
    )

    idempotency_hash: Mapped[
        str | None
    ] = mapped_column(
        String(64),
        nullable=True,
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

    transcript_id: Mapped[
        str | None
    ] = mapped_column(
        String(36),
        ForeignKey(
            "transcripts.id",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    transcription_job_id: Mapped[
        str | None
    ] = mapped_column(
        String(36),
        ForeignKey(
            "transcription_jobs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    source_etag: Mapped[
        str | None
    ] = mapped_column(
        String(256),
        nullable=True,
    )

    fingerprint: Mapped[str] = (
        mapped_column(
            String(64),
            nullable=False,
        )
    )

    notes_style: Mapped[str] = (
        mapped_column(
            String(32),
            nullable=False,
        )
    )

    include_mind_map: Mapped[
        bool
    ] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    include_flowchart: Mapped[
        bool
    ] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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

    algorithm_version: Mapped[
        str
    ] = mapped_column(
        String(64),
        nullable=False,
    )

    content: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    mind_map: Mapped[dict] = (
        mapped_column(
            JSONB,
            nullable=False,
            default=dict,
        )
    )

    flowchart: Mapped[dict] = (
        mapped_column(
            JSONB,
            nullable=False,
            default=dict,
        )
    )

    component_status: Mapped[
        dict
    ] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    component_errors: Mapped[
        dict
    ] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    attempt_count: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
            default=0,
        )
    )

    next_attempt_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    heartbeat_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    error_code: Mapped[
        str | None
    ] = mapped_column(
        String(128),
        nullable=True,
    )

    error_message: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    updated_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    started_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
