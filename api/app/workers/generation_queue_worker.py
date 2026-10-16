import json
import logging
import threading
from datetime import (
    datetime,
    timedelta,
    timezone,
)


from app.core.config import (
    get_settings,
)
from app.db.session import (
    SessionLocal,
)
from app.providers.aws import (
    sqs_client,
)


settings = get_settings()
sqs = sqs_client()


def utcnow():
    return datetime.now(
        timezone.utc
    )


def claim(
    *,
    repo_class,
    job_id,
):
    now = utcnow()

    with SessionLocal() as db:
        repo = repo_class(
            db
        )

        job = repo.lock_job(
            job_id
        )

        if job is None:
            return (
                "missing",
                None,
                0,
            )

        tenant_id = (
            job.tenant_id
        )

        prior_attempt_count = (
            job.attempt_count
        )

        if job.status in {
            "completed",
            "partial",
            "failed",
        }:
            return (
                "terminal",
                tenant_id,
                prior_attempt_count,
            )

        if (
            job.status
            in {
                "queued",
                "waiting_for_transcript",
            }
            and job.next_attempt_at
            is not None
            and job.next_attempt_at
            > now
        ):
            return (
                "deferred",
                tenant_id,
                prior_attempt_count,
            )

        if (
            job.status
            == "processing"
        ):
            heartbeat = (
                job.heartbeat_at
                or job.started_at
            )

            if heartbeat is not None:
                age = (
                    now
                    - heartbeat
                ).total_seconds()

                if (
                    age
                    < settings
                    .generation_stale_after_seconds
                ):
                    return (
                        "busy",
                        tenant_id,
                        prior_attempt_count,
                    )

        job.status = "processing"
        job.heartbeat_at = now
        job.next_attempt_at = None

        if job.started_at is None:
            job.started_at = now

        db.commit()

        return (
            "claimed",
            tenant_id,
            prior_attempt_count,
        )


class MessageLease:
    def __init__(
        self,
        *,
        queue_url,
        receipt_handle,
        job_id,
        tenant_id,
        repo_class,
        logger,
    ):
        self.queue_url = (
            queue_url
        )

        self.receipt_handle = (
            receipt_handle
        )

        self.job_id = job_id
        self.tenant_id = tenant_id
        self.repo_class = repo_class
        self.logger = logger

        self.stop_event = (
            threading.Event()
        )

        self.thread = threading.Thread(
            target=self._run,
            name=(
                "generation-lease-"
                + job_id
            ),
            daemon=True,
        )

    def __enter__(self):
        self.thread.start()

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        self.stop_event.set()

        self.thread.join(
            timeout=5
        )

    def _run(self):
        interval = max(
            10,
            min(
                settings
                .generation_heartbeat_interval_seconds,

                settings
                .generation_visibility_timeout_seconds
                // 3,
            ),
        )

        while not self.stop_event.wait(
            interval
        ):
            try:
                sqs.change_message_visibility(
                    QueueUrl=(
                        self.queue_url
                    ),

                    ReceiptHandle=(
                        self.receipt_handle
                    ),

                    VisibilityTimeout=(
                        settings
                        .generation_visibility_timeout_seconds
                    ),
                )

            except Exception:
                self.logger.exception(
                    "Could not extend SQS lease "
                    "for generation job %s",
                    self.job_id,
                )

            try:
                with SessionLocal() as db:
                    db.info[
                        "tenant_id"
                    ] = self.tenant_id

                    job = (
                        self.repo_class(
                            db
                        ).get(
                            self.job_id
                        )
                    )

                    if (
                        job is not None
                        and job.status
                        == "processing"
                    ):
                        job.heartbeat_at = (
                            utcnow()
                        )

                        db.commit()

            except Exception:
                self.logger.exception(
                    "Could not update generation "
                    "heartbeat %s",
                    self.job_id,
                )


def delete_message(
    *,
    queue_url,
    receipt_handle,
):
    sqs.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle,
    )


def reschedule(
    *,
    repo_class,
    tenant_id,
    job_id,
    next_attempt_at,
    last_error=None,
):
    with SessionLocal() as db:
        db.info[
            "tenant_id"
        ] = tenant_id

        repo = repo_class(
            db
        )

        repo.reschedule_outbox(
            job_id=job_id,

            next_attempt_at=(
                next_attempt_at
                or (
                    utcnow()
                    + timedelta(
                        seconds=10
                    )
                )
            ),

            last_error=last_error,
        )

        db.commit()


def run_worker(
    *,
    name,
    logger,
    queue_url,
    message_key,
    repo_class,
    service_class,
):
    logger.info(
        "%s worker started",
        name,
    )

    while True:
        response = sqs.receive_message(
            QueueUrl=queue_url,

            MaxNumberOfMessages=1,

            WaitTimeSeconds=20,

            VisibilityTimeout=(
                settings
                .generation_visibility_timeout_seconds
            ),

            AttributeNames=[
                "ApproximateReceiveCount"
            ],
        )

        messages = response.get(
            "Messages",
            []
        )

        if not messages:
            continue

        message = messages[0]

        receipt = message[
            "ReceiptHandle"
        ]

        try:
            body = json.loads(
                message["Body"]
            )

            job_id = str(
                body[
                    message_key
                ]
            )

        except Exception:
            logger.exception(
                "Malformed %s SQS message",
                name,
            )

            sqs.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=receipt,
                VisibilityTimeout=5,
            )

            continue

        (
            state,
            tenant_id,
            prior_attempt_count,
        ) = claim(
            repo_class=repo_class,
            job_id=job_id,
        )

        if state in {
            "missing",
            "terminal",
            "deferred",
            "busy",
        }:
            delete_message(
                queue_url=queue_url,
                receipt_handle=receipt,
            )

            continue

        logger.info(
            "Processing %s %s",
            name,
            job_id,
        )

        try:
            with MessageLease(
                queue_url=queue_url,

                receipt_handle=receipt,

                job_id=job_id,

                tenant_id=tenant_id,

                repo_class=repo_class,

                logger=logger,
            ):
                with SessionLocal() as db:
                    db.info[
                        "tenant_id"
                    ] = tenant_id

                    service = (
                        service_class(
                            db
                        )
                    )

                    result = (
                        service.process(
                            job_id
                        )
                    )

                    repo = (
                        repo_class(
                            db
                        )
                    )

                    job = repo.get(
                        job_id
                    )

                    if result == "waiting":
                        repo.reschedule_outbox(
                            job_id=job_id,

                            next_attempt_at=(
                                job.next_attempt_at
                                if job
                                else (
                                    utcnow()
                                    + timedelta(
                                        seconds=5
                                    )
                                )
                            ),
                        )

                        db.commit()

            delete_message(
                queue_url=queue_url,
                receipt_handle=receipt,
            )

            logger.info(
                "%s finished: %s",
                name,
                job_id,
            )

        except Exception as exc:
            logger.exception(
                "%s failed: %s",
                name,
                job_id,
            )

            handled = False

            try:
                with SessionLocal() as db:
                    db.info[
                        "tenant_id"
                    ] = tenant_id

                    service = (
                        service_class(
                            db
                        )
                    )

                    service.mark_failure(
                        job_id,

                        prior_attempt_count=(
                            prior_attempt_count
                        ),
                    )

                    repo = repo_class(
                        db
                    )

                    job = repo.get(
                        job_id
                    )

                    if (
                        job is not None
                        and job.status
                        != "failed"
                    ):
                        repo.reschedule_outbox(
                            job_id=job_id,

                            next_attempt_at=(
                                job.next_attempt_at
                                or (
                                    utcnow()
                                    + timedelta(
                                        seconds=30
                                    )
                                )
                            ),

                            last_error=(
                                type(exc).__name__
                            )[:200],
                        )

                        db.commit()

                handled = True

            except Exception:
                logger.exception(
                    "Could not persist retry "
                    "state for %s %s",
                    name,
                    job_id,
                )

            if handled:
                delete_message(
                    queue_url=queue_url,
                    receipt_handle=receipt,
                )
