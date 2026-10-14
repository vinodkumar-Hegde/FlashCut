from datetime import datetime

from sqlalchemy import (
    or_,
    select,
)
from sqlalchemy.orm import Session

from app.db.tenant import (
    tenant_get,
)
from app.models.note import NoteJob


class NoteRepository:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def get(
        self,
        note_id: str,
    ) -> NoteJob | None:
        return tenant_get(
            self.db,
            NoteJob,
            note_id,
        )

    def claim_next(
        self,
        *,
        now: datetime,
    ) -> NoteJob | None:
        statement = (
            select(NoteJob)
            .where(
                NoteJob.status.in_(
                    [
                        "queued",
                        "waiting_for_transcript",
                    ]
                ),
                or_(
                    NoteJob
                    .next_attempt_at
                    .is_(None),

                    NoteJob
                    .next_attempt_at
                    <= now,
                ),
            )
            .order_by(
                NoteJob.created_at
            )
            .with_for_update(
                skip_locked=True
            )
            .limit(1)
        )

        job = self.db.scalar(
            statement
        )

        if job is None:
            return None

        job.status = "processing"

        self.db.commit()
        self.db.refresh(job)

        return job
