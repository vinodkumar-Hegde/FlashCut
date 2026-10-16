import json
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
from app.providers.aws import (
    sqs_client,
)
from app.repositories.generation_repository import (
    LearningMaterialRepository,
    QuickSummaryRepository,
)


configure_logging()

logger = logging.getLogger(
    "flashcut.generation_dispatcher"
)

settings = get_settings()
sqs = sqs_client()


def utcnow():
    return datetime.now(
        timezone.utc
    )


PIPELINES = (
    (
        "quick-summary",
        QuickSummaryRepository,
        settings.quick_summary_queue_url,
        "quick_summary_id",
        "QUICK_SUMMARY_QUEUE_PUBLISH_FAILED",
    ),
    (
        "learning-material",
        LearningMaterialRepository,
        settings.learning_material_queue_url,
        "learning_material_id",
        "LEARNING_MATERIAL_QUEUE_PUBLISH_FAILED",
    ),
)


def dispatch_pipeline(
    *,
    name,
    repo_class,
    queue_url,
    message_key,
    final_error_code,
):
    now = utcnow()

    with SessionLocal() as db:
        repo = repo_class(
            db
        )

        items = repo.pending_outbox(
            now=now,
            limit=(
                settings
                .generation_outbox_batch_size
            ),
        )

        for item in items:
            try:
                sqs.send_message(
                    QueueUrl=queue_url,

                    MessageBody=json.dumps({
                        "version": 1,
                        message_key:
                            item.job_id,
                    }),
                )

            except Exception as exc:
                item.attempt_count += 1

                item.last_error = (
                    type(exc).__name__
                )[:200]

                if (
                    item.attempt_count
                    >= settings
                    .generation_queue_publish_max_attempts
                ):
                    item.status = "failed"
                    item.next_attempt_at = None

                    job = repo.lock_job(
                        item.job_id
                    )

                    if (
                        job is not None
                        and job.status
                        not in {
                            "completed",
                            "partial",
                            "failed",
                        }
                    ):
                        job.status = "failed"

                        job.error_code = (
                            final_error_code
                        )

                        job.error_message = (
                            "Generation job could "
                            "not be queued."
                        )

                        job.completed_at = (
                            utcnow()
                        )

                    logger.error(
                        "%s queue publish "
                        "permanently failed: %s",
                        name,
                        item.job_id,
                    )

                else:
                    delay = min(
                        300,
                        5 * (
                            2 ** min(
                                item.attempt_count,
                                6,
                            )
                        ),
                    )

                    item.next_attempt_at = (
                        utcnow()
                        + timedelta(
                            seconds=delay
                        )
                    )

                    logger.warning(
                        "%s queue publish failed; "
                        "retry scheduled: %s",
                        name,
                        item.job_id,
                    )

            else:
                item.status = "sent"
                item.attempt_count = 0
                item.last_error = None
                item.next_attempt_at = None
                item.sent_at = utcnow()

                logger.info(
                    "%s queued: %s",
                    name,
                    item.job_id,
                )

        db.commit()


def run():
    logger.info(
        "Generation outbox dispatcher "
        "started"
    )

    while True:
        for (
            name,
            repo_class,
            queue_url,
            message_key,
            final_error_code,
        ) in PIPELINES:
            try:
                dispatch_pipeline(
                    name=name,
                    repo_class=repo_class,
                    queue_url=queue_url,
                    message_key=(
                        message_key
                    ),
                    final_error_code=(
                        final_error_code
                    ),
                )

            except Exception:
                logger.exception(
                    "%s outbox dispatch failed",
                    name,
                )

        time.sleep(
            settings
            .generation_dispatch_poll_seconds
        )


if __name__ == "__main__":
    run()
