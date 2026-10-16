from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.tenant import (
    tenant_get,
    tenant_select,
)
from app.models.render import (
    RenderJob,
    RenderOutbox,
)


class RenderRepository:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def get(
        self,
        render_id: str,
    ) -> RenderJob | None:
        return tenant_get(
            self.db,
            RenderJob,
            render_id,
        )

    def find_reusable(
        self,
        *,
        fingerprint: str,
    ) -> RenderJob | None:
        statement = (
            tenant_select(
                self.db,
                RenderJob,
            )
            .where(
                RenderJob
                .render_fingerprint
                == fingerprint,

                RenderJob.status.in_(
                    [
                        "queued",
                        "processing",
                        "completed",
                    ]
                ),
            )
            .order_by(
                RenderJob
                .created_at
                .desc()
            )
            .limit(1)
        )

        return self.db.scalar(
            statement
        )

    def lock_job(
        self,
        render_id: str,
    ) -> RenderJob | None:
        statement = (
            select(RenderJob)
            .where(
                RenderJob.id
                == render_id
            )
            .with_for_update()
        )

        return self.db.scalar(
            statement
        )

    def pending_outbox(
        self,
        *,
        now: datetime,
        limit: int = 10,
    ) -> list[RenderOutbox]:
        statement = (
            select(RenderOutbox)
            .where(
                RenderOutbox.status
                == "pending",

                RenderOutbox
                .next_attempt_at
                <= now,
            )
            .order_by(
                RenderOutbox
                .created_at
            )
            .with_for_update(
                skip_locked=True
            )
            .limit(limit)
        )

        return list(
            self.db.scalars(
                statement
            )
        )
