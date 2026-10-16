from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.tenant import (
    tenant_get,
    tenant_select,
)
from app.models.learning_pipeline import (
    LearningMaterialJob,
    LearningMaterialOutbox,
    QuickSummaryJob,
    QuickSummaryOutbox,
)


class GenerationRepository:
    job_model = None
    outbox_model = None

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def get(
        self,
        job_id: str,
    ):
        return tenant_get(
            self.db,
            self.job_model,
            job_id,
        )

    def get_by_idempotency_key(
        self,
        key: str,
    ):
        return self.db.scalar(
            tenant_select(
                self.db,
                self.job_model,
            )
            .where(
                self.job_model
                .idempotency_key
                == key
            )
            .limit(1)
        )

    def lock_job(
        self,
        job_id: str,
    ):
        return self.db.scalar(
            select(
                self.job_model
            )
            .where(
                self.job_model.id
                == job_id
            )
            .with_for_update()
        )

    def pending_outbox(
        self,
        *,
        now: datetime,
        limit: int,
    ):
        return list(
            self.db.scalars(
                select(
                    self.outbox_model
                )
                .where(
                    self.outbox_model
                    .status
                    == "pending",

                    self.outbox_model
                    .next_attempt_at
                    <= now,
                )
                .order_by(
                    self.outbox_model
                    .created_at
                )
                .with_for_update(
                    skip_locked=True
                )
                .limit(limit)
            )
        )

    def outbox_for_job(
        self,
        job_id: str,
    ):
        return self.db.scalar(
            select(
                self.outbox_model
            )
            .where(
                self.outbox_model
                .job_id
                == job_id
            )
            .with_for_update()
        )

    def reschedule_outbox(
        self,
        *,
        job_id: str,
        next_attempt_at: datetime,
        last_error: str | None = None,
    ):
        item = self.outbox_for_job(
            job_id
        )

        if item is None:
            raise RuntimeError(
                "Generation outbox row "
                "is missing."
            )

        item.status = "pending"
        item.attempt_count = 0

        item.next_attempt_at = (
            next_attempt_at
        )

        item.last_error = (
            last_error
        )

        item.sent_at = None

        return item


class QuickSummaryRepository(
    GenerationRepository
):
    job_model = QuickSummaryJob
    outbox_model = QuickSummaryOutbox


class LearningMaterialRepository(
    GenerationRepository
):
    job_model = LearningMaterialJob
    outbox_model = (
        LearningMaterialOutbox
    )
