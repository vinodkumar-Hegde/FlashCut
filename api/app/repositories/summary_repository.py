from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.summary import SummaryJob


class SummaryRepository:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def get(
        self,
        summary_id: str,
    ) -> SummaryJob | None:
        return self.db.get(
            SummaryJob,
            summary_id,
        )

    def find_active(
        self,
        *,
        transcript_id: str,
        target_seconds: int,
        model_id: str,
        algorithm_version: str,
    ) -> SummaryJob | None:
        statement = (
            select(
                SummaryJob
            )
            .where(
                SummaryJob.transcript_id
                == transcript_id,
                SummaryJob.target_seconds
                == target_seconds,
                SummaryJob.model_id
                == model_id,
                SummaryJob.algorithm_version
                == algorithm_version,
                SummaryJob.status.in_(
                    [
                        "queued",
                        "processing",
                    ]
                ),
            )
            .order_by(
                SummaryJob.created_at.desc()
            )
            .limit(1)
        )

        return self.db.scalar(
            statement
        )

    def find_completed(
        self,
        *,
        transcript_id: str,
        target_seconds: int,
        model_id: str,
        algorithm_version: str,
    ) -> SummaryJob | None:
        statement = (
            select(
                SummaryJob
            )
            .where(
                SummaryJob.transcript_id
                == transcript_id,
                SummaryJob.target_seconds
                == target_seconds,
                SummaryJob.model_id
                == model_id,
                SummaryJob.algorithm_version
                == algorithm_version,
                SummaryJob.status
                == "completed",
            )
            .order_by(
                SummaryJob.completed_at.desc()
            )
            .limit(1)
        )

        return self.db.scalar(
            statement
        )

    def claim_next(
        self,
    ) -> SummaryJob | None:
        statement = (
            select(
                SummaryJob
            )
            .where(
                SummaryJob.status
                == "queued"
            )
            .order_by(
                SummaryJob.created_at
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
        self.db.refresh(
            job
        )

        return job
