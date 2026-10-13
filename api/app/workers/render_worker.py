import json
import logging
import os
import re
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

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


def claim(
    render_id: str,
):
    with SessionLocal() as db:
        job = (
            RenderRepository(db)
            .get(render_id)
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

                if age < 600:
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
        db.refresh(job)

        return (
            "claimed",
            job.attempt_count,
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
            job.completed_at = (
                utcnow()
            )

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

        render_video(
            source_path=source_path,
            output_path=output_path,
            clips=clips,
            watermark=(
                settings.watermark_text
            ),
            timeout_seconds=(
                settings
                .render_ffmpeg_timeout_seconds
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
        response = sqs.receive_message(
            QueueUrl=(
                settings.render_queue_url
            ),
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=180,
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
