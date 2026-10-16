import logging
import time
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from app.core.config import (
    get_settings,
)
from app.core.logging import (
    configure_logging,
)
from app.db.session import (
    SessionLocal,
)
from app.repositories.generation_repository import (
    QuickSummaryRepository,
)
from app.services.quick_summary_service import (
    QuickSummaryService,
)


configure_logging()

logger = logging.getLogger(
    "flashcut.quick_summary_worker"
)

settings = get_settings()


def utcnow():
    return datetime.now(
        timezone.utc
    )


def run():
    logger.info(
        "Quick summary worker started"
    )

    while True:
        job_id = None
        tenant_id = None

        try:
            with SessionLocal() as db:
                now = utcnow()

                job = (
                    QuickSummaryRepository(
                        db
                    ).claim_next(
                        now=now,

                        stale_before=(
                            now
                            - timedelta(
                                seconds=(
                                    settings
                                    .generation_stale_after_seconds
                                )
                            )
                        ),
                    )
                )

                if job is not None:
                    job_id = job.id
                    tenant_id = (
                        job.tenant_id
                    )

            if job_id is None:
                time.sleep(
                    settings
                    .generation_worker_poll_seconds
                )

                continue

            logger.info(
                "Processing quick summary %s",
                job_id,
            )

            with SessionLocal() as db:
                db.info[
                    "tenant_id"
                ] = tenant_id

                QuickSummaryService(
                    db
                ).process(
                    job_id
                )

        except Exception:
            logger.exception(
                "Quick summary failed: %s",
                job_id,
            )

            if (
                job_id is not None
                and tenant_id is not None
            ):
                try:
                    with SessionLocal() as db:
                        db.info[
                            "tenant_id"
                        ] = tenant_id

                        QuickSummaryService(
                            db
                        ).mark_failure(
                            job_id
                        )

                except Exception:
                    logger.exception(
                        "Could not persist quick "
                        "summary failure: %s",
                        job_id,
                    )


if __name__ == "__main__":
    run()
