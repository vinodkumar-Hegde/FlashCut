import uuid
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
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


class AuditEvent(Base):
    __tablename__ = "audit_events"

    __table_args__ = (
        Index(
            "ix_audit_events_tenant_created_at",
            "tenant_id",
            "created_at",
        ),
        Index(
            "ix_audit_events_request_id",
            "request_id",
        ),
        Index(
            "ix_audit_events_resource",
            "tenant_id",
            "resource_type",
            "resource_id",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(
            uuid.uuid4()
        ),
    )

    tenant_id: Mapped[
        str | None
    ] = mapped_column(
        String(128),
        nullable=True,
    )

    actor_subject: Mapped[
        str | None
    ] = mapped_column(
        String(256),
        nullable=True,
    )

    request_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    method: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    route: Mapped[
        str | None
    ] = mapped_column(
        String(512),
        nullable=True,
    )

    path: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )

    status_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    outcome: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    resource_type: Mapped[
        str | None
    ] = mapped_column(
        String(64),
        nullable=True,
    )

    resource_id: Mapped[
        str | None
    ] = mapped_column(
        String(128),
        nullable=True,
    )

    duration_ms: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    error_code: Mapped[
        str | None
    ] = mapped_column(
        String(128),
        nullable=True,
    )

    details: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(
            timezone=True
        ),
        nullable=False,
        default=utcnow,
    )
