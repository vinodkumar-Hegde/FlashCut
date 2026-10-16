import uuid
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    String,
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


class RenderAsset(Base):
    __tablename__ = "render_assets"

    __table_args__ = (
        CheckConstraint(
            "kind IN ('intro','outro')",
            name="ck_render_assets_kind",
        ),
        CheckConstraint(
            "status IN "
            "('uploading','ready','rejected')",
            name="ck_render_assets_status",
        ),
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

    kind: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    s3_key: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        unique=True,
    )

    content_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    etag: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uploading",
        index=True,
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

    completed_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
