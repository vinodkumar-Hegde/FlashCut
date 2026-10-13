from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

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
        return self.db.get(
            RenderJob,
            render_id,
        )

    def find_reusable(
        self,
        *,
        selection_id: str,
        profile: str,
    ) -> RenderJob | None:
        statement = (
            select(RenderJob)
            .where(
                RenderJob.selection_id
                == selection_id,
                RenderJob.render_profile_version
                == profile,
                RenderJob.status.in_(
                    [
                        "queued",
                        "processing",
                        "completed",
                    ]
                ),
            )
            .order_by(
                RenderJob.created_at.desc()
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
                RenderOutbox.next_attempt_at
                <= now,
            )
            .order_by(
                RenderOutbox.created_at
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
