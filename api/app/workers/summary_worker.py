import logging
import time

from app.core.logging import (
    configure_logging,
)
from app.db.session import SessionLocal
from app.repositories.summary_repository import (
    SummaryRepository,
)
from app.services.summary_service import (
    SummaryService,
)


configure_logging()

logger = logging.getLogger(
    "flashcut.summary_worker"
)


def run():
    logger.info(
        "Summary worker started"
    )

    while True:
        with SessionLocal() as db:
            repo = SummaryRepository(
                db
            )

            job = repo.claim_next()

            if job is None:
                time.sleep(2)
                continue

            job_id = job.id

        logger.info(
            "Processing summary %s",
            job_id,
        )

        with SessionLocal() as db:
            try:
                SummaryService(
                    db
                ).process(
                    job_id
                )

            except Exception:
                logger.exception(
                    "Summary failed: %s",
                    job_id,
                )

                db.rollback()

                repo = (
                    SummaryRepository(
                        db
                    )
                )

                failed = repo.get(
                    job_id
                )

                if failed is not None:
                    failed.status = (
                        "failed"
                    )

                    failed.failure_reason = (
                        "Automatic summary "

                        "generation failed."
                    )

                    db.commit()

            else:
                logger.info(
                    "Summary completed: %s",
                    job_id,
                )


if __name__ == "__main__":
    run()
