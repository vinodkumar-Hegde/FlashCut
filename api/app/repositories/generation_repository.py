from datetime import datetime

from sqlalchemy import (
    and_,
    or_,
    select,
)
from sqlalchemy.orm import Session

from app.db.tenant import (
    tenant_get,
    tenant_select,
)
from app.models.learning_pipeline import (
    LearningMaterialJob,
    QuickSummaryJob,
)


def _claim_statement(
    model,
    *,
    now: datetime,
    stale_before: datetime,
):
    return (
        select(model)
        .where(
            or_(
                and_(
                    model.status.in_([
                        "queued",
                        "waiting_for_transcript",
                    ]),
                    or_(
                        model.next_attempt_at
                        .is_(None),

                        model.next_attempt_at
                        <= now,
                    ),
                ),
                and_(
                    model.status
                    == "processing",
                    or_(
                        model.heartbeat_at
                        .is_(None),

                        model.heartbeat_at
                        <= stale_before,
                    ),
                ),
            )
        )
        .order_by(
            model.created_at
        )
        .with_for_update(
            skip_locked=True
        )
        .limit(1)
    )


class QuickSummaryRepository:
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
            QuickSummaryJob,
            job_id,
        )

    def get_by_idempotency_key(
        self,
        key: str,
    ):
        return self.db.scalar(
            tenant_select(
                self.db,
                QuickSummaryJob,
            )
            .where(
                QuickSummaryJob
                .idempotency_key
                == key
            )
            .limit(1)
        )

    def claim_next(
        self,
        *,
        now: datetime,
        stale_before: datetime,
    ):
        job = self.db.scalar(
            _claim_statement(
                QuickSummaryJob,
                now=now,
                stale_before=(
                    stale_before
                ),
            )
        )

        if job is None:
            return None

        job.status = "processing"
        job.next_attempt_at = None
        job.heartbeat_at = now

        if job.started_at is None:
            job.started_at = now

        self.db.commit()
        self.db.refresh(job)

        return job


class LearningMaterialRepository:
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
            LearningMaterialJob,
            job_id,
        )

    def get_by_idempotency_key(
        self,
        key: str,
    ):
        return self.db.scalar(
            tenant_select(
                self.db,
                LearningMaterialJob,
            )
            .where(
                LearningMaterialJob
                .idempotency_key
                == key
            )
            .limit(1)
        )

    def claim_next(
        self,
        *,
        now: datetime,
        stale_before: datetime,
    ):
        job = self.db.scalar(
            _claim_statement(
                LearningMaterialJob,
                now=now,
                stale_before=(
                    stale_before
                ),
            )
        )

        if job is None:
            return None

        job.status = "processing"
        job.next_attempt_at = None
        job.heartbeat_at = now

        if job.started_at is None:
            job.started_at = now

        self.db.commit()
        self.db.refresh(job)

        return job
