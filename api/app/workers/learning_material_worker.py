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
    LearningMaterialRepository,
)
from app.services.learning_material_service import (
    LearningMaterialService,
)


configure_logging()

logger = logging.getLogger(
    "flashcut.learning_material_worker"
)

settings = get_settings()


def utcnow():
    return datetime.now(
        timezone.utc
    )


def run():
    logger.info(
        "Learning material worker started"
    )

    while True:
        job_id = None
        tenant_id = None

        try:
            with SessionLocal() as db:
                now = utcnow()

                job = (
                    LearningMaterialRepository(
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
                "Processing learning material %s",
                job_id,
            )

            with SessionLocal() as db:
                db.info[
                    "tenant_id"
                ] = tenant_id

                LearningMaterialService(
                    db
                ).process(
                    job_id
                )

        except Exception:
            logger.exception(
                "Learning material failed: %s",
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

                        LearningMaterialService(
                            db
                        ).mark_failure(
                            job_id
                        )

                except Exception:
                    logger.exception(
                        "Could not persist learning "
                        "material failure: %s",
                        job_id,
                    )


if __name__ == "__main__":
    run()
