import json
import logging
import os
import re
import shutil
import tempfile
import threading
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import (
    Path,
    PurePosixPath,
)

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.providers.aws import (
    s3_client,
    sqs_client,
)
from app.repositories.render_repository import (
    RenderRepository,
)
from app.repositories.render_asset_repository import (
    RenderAssetRepository,
)
from app.repositories.selection_repository import (
    SelectionRepository,
)
from app.repositories.video_repository import (
    VideoRepository,
)
from app.services.render_engine import (
    render_video,
)


configure_logging()

logger = logging.getLogger(
    "flashcut.render_worker"
)

settings = get_settings()
s3 = s3_client()
sqs = sqs_client()


def utcnow():
    return datetime.now(
        timezone.utc
    )


def safe_filename(
    filename: str,
) -> tuple[str, str]:
    original = PurePosixPath(
        filename
    )

    extension = (
        original.suffix.lower()
    )

    if extension not in {
        ".mp4",
        ".webm",
    }:
        raise RuntimeError(
            "Unsupported source container."
        )

    stem = re.sub(
        r"[^A-Za-z0-9._-]+",
        "-",
        original.stem,
    ).strip("-._")

    if not stem:
        stem = "video"

    return (
        f"{stem}-edited{extension}",
        extension.lstrip("."),
    )


def dispatch_pending_messages():
    now = utcnow()

    with SessionLocal() as db:
        repo = RenderRepository(
            db
        )

        pending = repo.pending_outbox(
            now=now,
            limit=10,
        )

        if not pending:
            return

        for item in pending:
            try:
                sqs.send_message(
                    QueueUrl=(
                        settings
                        .render_queue_url
                    ),
                    MessageBody=json.dumps({
                        "version": 1,
                        "render_id":
                            item.render_id,
                    }),
                )

            except Exception as exc:
                item.attempt_count += 1

                item.last_error = (
                    f"{type(exc).__name__}: "
                    f"{str(exc)}"
                )[:2000]

                if (
                    item.attempt_count
                    >= settings
                    .render_queue_publish_max_attempts
                ):
                    item.status = "failed"
                    item.next_attempt_at = None

                    job = repo.get(
                        item.render_id
                    )

                    if (
                        job is not None
                        and job.status
                        == "queued"
                    ):
                        job.status = "failed"
                        job.error_code = (
                            "QUEUE_PUBLISH_FAILED"
                        )
                        job.error_message = (
                            "Render job could not "
                            "be queued."
                        )
                        job.completed_at = utcnow()

                    logger.error(
                        "Render queue publish "
                        "permanently failed: %s",
                        item.render_id,
                    )

                else:
                    delay_seconds = min(
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
                            seconds=delay_seconds
                        )
                    )

                    logger.warning(
                        "Render queue publish "
                        "failed; retry scheduled: %s",
                        item.render_id,
                    )

            else:
                item.status = "sent"
                item.attempt_count += 1
                item.last_error = None
                item.next_attempt_at = None
                item.sent_at = utcnow()

                logger.info(
                    "Render queued: %s",
                    item.render_id,
                )

        db.commit()


def claim(
    render_id: str,
):
    with SessionLocal() as db:
        repo = RenderRepository(
            db
        )

        job = repo.lock_job(
            render_id
        )

        if job is None:
            return "missing", None

        if job.status == "completed":
            return "completed", None

        if job.status == "failed":
            return "failed", None

        if job.status == "processing":
            heartbeat = (
                job.heartbeat_at
                or job.started_at
            )

            if heartbeat is not None:
                age = (
                    utcnow()
                    - heartbeat
                ).total_seconds()

                if (
                    age
                    < settings
                    .render_stale_after_seconds
                ):
                    return "busy", None

        job.status = "processing"

        job.started_at = (
            job.started_at
            or utcnow()
        )

        job.heartbeat_at = utcnow()
        job.attempt_count += 1
        job.error_code = None
        job.error_message = None

        db.commit()

        return (
            "claimed",
            job.attempt_count,
        )


class MessageLease:
    def __init__(
        self,
        *,
        receipt_handle: str,
        render_id: str,
    ):
        self.receipt_handle = (
            receipt_handle
        )

        self.render_id = render_id

        self.stop_event = (
            threading.Event()
        )

        self.thread = threading.Thread(
            target=self._run,
            name=(
                "render-lease-"
                + render_id
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
                .render_heartbeat_interval_seconds,
                settings
                .render_visibility_timeout_seconds
                // 3,
            ),
        )

        while not self.stop_event.wait(
            interval
        ):
            try:
                sqs.change_message_visibility(
                    QueueUrl=(
                        settings
                        .render_queue_url
                    ),
                    ReceiptHandle=(
                        self.receipt_handle
                    ),
                    VisibilityTimeout=(
                        settings
                        .render_visibility_timeout_seconds
                    ),
                )

            except Exception:
                logger.exception(
                    "Could not extend SQS lease "
                    "for render %s",
                    self.render_id,
                )

            try:
                with SessionLocal() as db:
                    job = (
                        RenderRepository(db)
                        .get(
                            self.render_id
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
                logger.exception(
                    "Could not update render "
                    "heartbeat %s",
                    self.render_id,
                )


def mark_failure(
    render_id: str,
    *,
    final: bool,
):
    with SessionLocal() as db:
        job = (
            RenderRepository(db)
            .get(render_id)
        )

        if job is None:
            return

        if final:
            job.status = "failed"
            job.error_code = (
                "RENDER_FAILED"
            )
            job.completed_at = utcnow()

        else:
            job.status = "queued"
            job.error_code = (
                "RENDER_RETRY"
            )

        job.error_message = (
            "Video rendering failed."
        )

        job.heartbeat_at = None

        db.commit()


def process(
    render_id: str,
):
    with SessionLocal() as db:
        render = (
            RenderRepository(db)
            .get(render_id)
        )

        if render is None:
            raise RuntimeError(
                "Render job disappeared."
            )

        selection = (
            SelectionRepository(db)
            .get(render.selection_id)
        )

        if (
            selection is None
            or selection.status
            != "approved"
        ):
            raise RuntimeError(
                "Approved selection unavailable."
            )

        if (
            selection.source_etag
            != render.source_etag
        ):
            raise RuntimeError(
                "Selection source changed."
            )

        video = (
            VideoRepository(db)
            .get(render.video_id)
        )

        if video is None:
            raise RuntimeError(
                "Source video unavailable."
            )

        source_key = video.s3_key
        source_name = video.filename

        asset_repo = (
            RenderAssetRepository(
                db
            )
        )

        def resolve_asset(
            asset_id,
            expected_etag,
            expected_kind,
        ):
            if asset_id is None:
                return None

            asset = asset_repo.get(
                asset_id
            )

            if (
                asset is None
                or asset.tenant_id
                != render.tenant_id
                or asset.kind
                != expected_kind
                or asset.status
                != "ready"
                or not asset.etag
                or asset.etag
                != expected_etag
            ):
                raise RuntimeError(
                    "Render asset unavailable "
                    "or changed."
                )

            return {
                "id":
                    asset.id,

                "key":
                    asset.s3_key,

                "filename":
                    asset.filename,

                "etag":
                    asset.etag,
            }

        intro_asset = resolve_asset(
            render.intro_asset_id,
            render.intro_asset_etag,
            "intro",
        )

        outro_asset = resolve_asset(
            render.outro_asset_id,
            render.outro_asset_etag,
            "outro",
        )

        clips = list(
            selection.resolved_clips
        )

    head = s3.head_object(
        Bucket=settings.s3_bucket,
        Key=source_key,
    )

    current_etag = str(
        head.get(
            "ETag",
            "",
        )
    ).strip('"')

    if (
        not current_etag
        or current_etag
        != render.source_etag
    ):
        raise RuntimeError(
            "S3 source changed after approval."
        )

    for asset in (
        intro_asset,
        outro_asset,
    ):
        if asset is None:
            continue

        asset_head = s3.head_object(
            Bucket=settings.s3_bucket,
            Key=asset["key"],
        )

        asset_etag = str(
            asset_head.get(
                "ETag",
                "",
            )
        ).strip('"')

        if (
            not asset_etag
            or asset_etag
            != asset["etag"]
        ):
            raise RuntimeError(
                "Render asset changed "
                "after render creation."
            )

    (
        output_filename,
        container_format,
    ) = safe_filename(
        source_name
    )

    output_key = (
        settings.s3_output_prefix
        + render_id
        + "/"
        + output_filename
    )

    with tempfile.TemporaryDirectory(
        prefix="flashcut-render-"
    ) as tmp:
        tmpdir = Path(tmp)

        extension = (
            PurePosixPath(
                source_name
            )
            .suffix
            .lower()
        )

        source_path = (
            tmpdir
            / f"source{extension}"
        )

        output_path = (
            tmpdir
            / output_filename
        )

        s3.download_file(
            settings.s3_bucket,
            source_key,
            str(source_path),
        )

        intro_path = None

        if intro_asset is not None:
            intro_path = (
                tmpdir
                / "intro.mp4"
            )

            s3.download_file(
                settings.s3_bucket,
                intro_asset["key"],
                str(intro_path),
            )

        outro_path = None

        if outro_asset is not None:
            outro_path = (
                tmpdir
                / "outro.mp4"
            )

            s3.download_file(
                settings.s3_bucket,
                outro_asset["key"],
                str(outro_path),
            )

        render_video(
            source_path=source_path,
            output_path=output_path,
            clips=clips,
            timeout_seconds=(
                settings
                .render_ffmpeg_timeout_seconds
            ),
            intro_path=intro_path,
            outro_path=outro_path,
            max_asset_duration_seconds=(
                settings
                .render_asset_max_duration_seconds
            ),
        )

        size_bytes = os.path.getsize(
            output_path
        )

        content_type = (
            "video/mp4"
            if container_format == "mp4"
            else "video/webm"
        )

        s3.upload_file(
            str(output_path),
            settings.s3_bucket,
            output_key,
            ExtraArgs={
                "ContentType":
                    content_type,
            },
        )

        if settings.local_output_dir:
            local_dir = Path(
                settings.local_output_dir
            )

            local_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(
                output_path,
                local_dir
                / (
                    render_id
                    + "-"
                    + output_filename
                ),
            )

    with SessionLocal() as db:
        job = (
            RenderRepository(db)
            .get(render_id)
        )

        if job is None:
            raise RuntimeError(
                "Render job disappeared."
            )

        job.status = "completed"
        job.output_filename = (
            output_filename
        )
        job.output_key = output_key
        job.output_size_bytes = (
            size_bytes
        )
        job.container_format = (
            container_format
        )

        job.error_code = None
        job.error_message = None
        job.heartbeat_at = utcnow()
        job.completed_at = utcnow()

        db.commit()


def run():
    logger.info(
        "Render worker started"
    )

    while True:
        try:
            dispatch_pending_messages()

        except Exception:
            logger.exception(
                "Render outbox dispatch failed"
            )

        response = sqs.receive_message(
            QueueUrl=(
                settings.render_queue_url
            ),
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=(
                settings
                .render_visibility_timeout_seconds
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

            render_id = str(
                body["render_id"]
            )

        except Exception:
            logger.exception(
                "Malformed render message"
            )

            sqs.delete_message(
                QueueUrl=(
                    settings
                    .render_queue_url
                ),
                ReceiptHandle=receipt,
            )

            continue

        (
            state,
            attempt,
        ) = claim(
            render_id
        )

        if state in {
            "missing",
            "completed",
        }:
            sqs.delete_message(
                QueueUrl=(
                    settings
                    .render_queue_url
                ),
                ReceiptHandle=receipt,
            )

            continue

        if state == "failed":
            continue

        if state == "busy":
            sqs.change_message_visibility(
                QueueUrl=(
                    settings
                    .render_queue_url
                ),
                ReceiptHandle=receipt,
                VisibilityTimeout=60,
            )

            continue

        logger.info(
            "Processing render %s",
            render_id,
        )

        try:
            with MessageLease(
                receipt_handle=receipt,
                render_id=render_id,
            ):
                process(
                    render_id
                )

        except Exception:
            logger.exception(
                "Render failed: %s",
                render_id,
            )

            final = bool(
                attempt is not None
                and attempt >= 3
            )

            mark_failure(
                render_id,
                final=final,
            )

            if not final:
                sqs.change_message_visibility(
                    QueueUrl=(
                        settings
                        .render_queue_url
                    ),
                    ReceiptHandle=receipt,
                    VisibilityTimeout=30,
                )

            continue

        sqs.delete_message(
            QueueUrl=(
                settings
                .render_queue_url
            ),
            ReceiptHandle=receipt,
        )

        logger.info(
            "Render completed: %s",
            render_id,
        )


if __name__ == "__main__":
    run()
