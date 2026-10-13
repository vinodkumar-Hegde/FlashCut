from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.render import RenderJob


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
